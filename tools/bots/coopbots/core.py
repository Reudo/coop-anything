"""Multi-bot co-op playbook runner (game independent).

A playbook drives 2 to 4 bots at once, one per running game instance. After every step the runner:
  1. settles: waits until every machine has applied the host's last update number and stays equal for two polls,
  2. optionally waits a quiet window (impaired links): nothing new is sent, every machine must be converged and no
     repair may happen during the window,
  3. snapshots every machine and compares the `shared` part of host against each client,
  4. checks that the desync counters did not rise (repairs are allowed to be recorded on an impaired link; hard
     errors never are), and that the run stays inside its repairs-per-minute budget,
and on any failure it writes everything a human or an analyzer needs to <outdir>/FAIL-<n>-<step>/ and aborts the playbook.

What the runner needs from each machine's adapter (adapter.ActionAdapter): status(), snapshot(), optionally capture(),
plus whatever actions the playbook calls. Nothing else about the game.
"""
import contextlib
import fnmatch
import json
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .adapter import MissingAction

MUTANT = os.environ.get("COOPBOTS_MUTANT", "")   # test-only twin switch: nosettle | nosnapshot | nocounters | skipispass


class StepFailure(Exception):
    """A step did not do what the playbook expected. `reason` is shown to the human."""

    def __init__(self, reason: str, kind: str = "check"):
        super().__init__(reason)
        self.reason = reason
        self.kind = kind          # check | action | settle | snapshot | counters | quiescence | budget | bridge | exception


class PlaybookAbort(Exception):
    """Raised after a failed step has been recorded; unwinds the playbook."""


@dataclass
class Machine:
    idx: int                      # 0 = host
    name: str                     # "host", "client1", ...
    bot: Any                      # an ActionAdapter
    instance: int = 0

    @property
    def role(self) -> str:
        return "host" if self.idx == 0 else "client"


@dataclass
class StepRecord:
    name: str
    ok: bool
    reason: str = ""
    kind: str = ""
    seconds: float = 0.0
    snapshot: str = "skipped"         # equal | different | invalid | skipped
    counters_delta: Dict[str, Dict[str, int]] = field(default_factory=dict)
    fail_dir: str = ""


# ---------------------------------------------------------------------------------------------
# Counters. An adapter maps whatever its netcode counts onto these names in status()["counters"]; other names are
# kept in the records but never fail a step. Missing counters count as 0.
REPAIR_COUNTERS = ("mismatches", "repairs", "repaired_effects")   # a desync was found and healed: ok while traffic is in flight on a bad link
HARD_COUNTERS = ("bad_messages", "apply_failures", "rebases")    # never ok: malformed input, a failed apply, a client forced to rebase
MUST_NOT_RISE = REPAIR_COUNTERS + HARD_COUNTERS


def read_counters(status: dict) -> Dict[str, int]:
    c = (status or {}).get("counters") or {}
    out = {k: int(c.get(k, 0) or 0) for k in MUST_NOT_RISE}
    for k, v in c.items():
        if k not in out and isinstance(v, (int, float)):
            out[k] = int(v)
    return out


def last_seq(status: dict) -> int:
    return int((status or {}).get("seq", 0) or 0)


# ---------------------------------------------------------------------------------------------
class Comparer:
    """Takes a snapshot of each machine and diffs two of them. Replace it if your game has a better comparison."""

    def snapshot(self, m: Machine) -> Any:
        raise NotImplementedError

    def diff(self, a: Any, b: Any, ignore: Sequence[str]) -> Tuple[int, List[str]]:
        """Returns (code, lines): 0 equal, 1 different, 2 invalid input."""
        raise NotImplementedError


class DictComparer(Comparer):
    """Compares the `shared` dict of two snapshots, path by path. `ignore` holds fnmatch patterns on the printed lines,
    for example "shared/refs/*/in_use*". An empty `shared` is refused (code 2): comparing nothing proves nothing."""

    def snapshot(self, m: Machine) -> Any:
        return m.bot.snapshot()

    def diff(self, a, b, ignore):
        sa, sb = a.get("shared"), b.get("shared")
        if not sa or not sb:
            return 2, ["snapshot has an empty 'shared' section: nothing to compare"]
        lines: List[str] = []

        def walk(x, y, path):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in sorted(set(x) | set(y)):
                    if k not in x:
                        lines.append("%s/%s: only on B" % (path, k))
                    elif k not in y:
                        lines.append("%s/%s: only on A" % (path, k))
                    else:
                        walk(x[k], y[k], "%s/%s" % (path, k))
            elif x != y:
                lines.append("%s: %r != %r" % (path, x, y))

        walk(sa, sb, "shared")
        lines = [l for l in lines if not any(fnmatch.fnmatch(l, g) for g in ignore)]
        return (1 if lines else 0), lines


# ---------------------------------------------------------------------------------------------
def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


class Ctx:
    """What a playbook sees. Create with Ctx(machines, comparer, outdir, refs, opts)."""

    DEFAULTS = {"settle_s": 20.0, "settle_poll_s": 0.1, "compare": True, "strict_counters": True, "snapdiff_ignore": [],
                "save_snapshots": True, "chaos": None, "quiesce_s": None, "repair_budget_per_min": None, "fast": False}

    def __init__(self, machines: List[Machine], comparer: Optional[Comparer], outdir: str, refs: Optional[dict] = None,
                 opts: Optional[dict] = None, playbook: str = "", log: Optional[Callable[[str], None]] = None):
        self.machines = machines
        self.comparer = comparer
        self.outdir = outdir
        self.refs = dict(refs or {})
        self.opts = dict(self.DEFAULTS)
        self.opts.update(opts or {})
        self.playbook = playbook
        self.records: List[StepRecord] = []
        self._log = log or (lambda s: None)
        self._fail_n = 0
        self._counter_base: Dict[str, Dict[str, int]] = {}
        self._step_n = 0
        self.notes: List[str] = []
        self.absent: set = set()        # names of machines that left the session (excluded from settle, compare, queries)
        self._t_start = time.monotonic()
        self._repairs_at_start = 0
        self._pool: Optional[ThreadPoolExecutor] = None

    # ---- who ----
    @property
    def host(self) -> Machine:
        return self.machines[0]

    @property
    def clients(self) -> List[Machine]:
        return self.machines[1:]

    @property
    def present(self) -> List[Machine]:
        return [m for m in self.machines if m.name not in self.absent]

    def log(self, s: str) -> None:
        self._log("[%s] %s" % (self.playbook, s))

    # ---- helpers for playbook authors ----
    def ref(self, key: str) -> Any:
        if key not in self.refs:
            raise StepFailure("scenario has no ref named %r (have: %s)" % (key, sorted(self.refs)), "check")
        return self.refs[key]

    def must(self, result: Any, what: str) -> Any:
        """Action results never raise; turn a failed one into a step failure with its reason."""
        ok = getattr(result, "ok", result is True)
        if not ok:
            raise StepFailure("%s: %s" % (what, getattr(result, "reason", "") or "no reason given"), "action")
        return result

    def expect(self, cond: Any, msg: str) -> None:
        if not cond:
            raise StepFailure(msg, "check")

    def equip_all(self) -> None:
        """Everyone equips refs['weapon']. Without that ref the scenario is trusted to have armed the players."""
        w = self.refs.get("weapon")
        if not w:
            return
        for m in self.machines:
            self.must(m.bot.equip(w), "%s equips %s" % (m.name, w))

    def on_all(self, fn: Callable[[Machine], Any], machines: Optional[Sequence[Machine]] = None) -> Dict[str, Any]:
        """Run fn(machine) on every machine at the same time (threads; each bot has its own connection)."""
        ms = list(machines if machines is not None else self.present)
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=max(4, len(self.machines)), thread_name_prefix="bot")
        futures = [(m.name, self._pool.submit(fn, m)) for m in ms]
        out: Dict[str, Any] = {}
        first: Optional[BaseException] = None
        for name, fut in futures:           # wait for every machine, then raise the first error on the calling thread
            try:
                out[name] = fut.result()
            except BaseException as e:  # noqa: BLE001
                first = first or e
        if first is not None:
            raise first
        return out

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None

    def same_everywhere(self, label: str, query: Callable[[Machine], Any], machines: Optional[Sequence[Machine]] = None) -> Any:
        """Ask every machine the same question and require identical answers."""
        ms = list(machines if machines is not None else self.present)
        vals = {m.name: query(m) for m in ms}
        distinct = {json.dumps(v, sort_keys=True, default=str) for v in vals.values()}
        if len(distinct) != 1:
            raise StepFailure("%s differs between machines: %s" % (label, vals), "check")
        return vals[ms[0].name]

    def optional(self, label: str, fn: Callable[[], Any], default: Any = None) -> Any:
        """Run a check that needs an action the adapter may not have. If it is missing, note it and return `default`."""
        try:
            return fn()
        except MissingAction as e:
            self.notes.append("%s skipped: %s" % (label, e))
            return default

    def wait_until(self, label: str, pred: Callable[[], bool], timeout_s: float = 10.0, poll_s: float = 0.1) -> None:
        end = time.monotonic() + timeout_s
        while True:
            self._tick()
            if pred():
                return
            if time.monotonic() >= end:
                raise StepFailure("timed out after %gs waiting for: %s" % (timeout_s, label), "check")
            if not self.opts.get("fast"):
                time.sleep(poll_s)

    def pause(self, seconds: float) -> None:
        """Let the game run for a while (fake worlds: a few ticks instead of real time)."""
        if self.opts.get("fast"):
            for _ in range(3):
                self._tick()
            return
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self._tick()
            time.sleep(0.1)

    def _tick(self) -> None:
        """Poll statuses once (this also drives fake worlds forward)."""
        for m in self.machines:
            m.bot.status()

    # ---- settle, quiet window, counters ----
    def statuses(self) -> Dict[str, dict]:
        return {m.name: m.bot.status() for m in self.present}

    def settle(self, timeout_s: Optional[float] = None) -> None:
        """Wait until every client has applied the host's last update number and stays equal for 2 polls."""
        if MUTANT == "nosettle":
            return
        timeout_s = self.opts["settle_s"] if timeout_s is None else timeout_s
        end = time.monotonic() + timeout_s
        stable, last = 0, {}
        while True:
            st = self.statuses()
            host_seq = last_seq(st[self.host.name])
            seqs = {m.name: last_seq(st[m.name]) for m in self.present}
            synced = all(seqs[m.name] == host_seq for m in self.present[1:])
            host_ok = st[self.host.name].get("synced", True)
            if synced and host_ok and seqs == last:
                stable += 1
                if stable >= 2:
                    return
            else:
                stable = 0
            last = seqs
            if time.monotonic() >= end:
                raise StepFailure("machines did not converge within %gs: last update number per machine %s, host synced=%s"
                                  % (timeout_s, seqs, host_ok), "settle")
            if self.opts["settle_poll_s"] > 0:
                time.sleep(self.opts["settle_poll_s"])

    def _read_all_counters(self) -> Dict[str, Dict[str, int]]:
        return {n: read_counters(s) for n, s in self.statuses().items()}

    def quiesce(self) -> None:
        """Impaired link rule: transient mismatches are fine while traffic is in flight, but once nothing new has been sent
        for `quiesce_s` every machine must have converged and NO repair may happen during a further quiet window."""
        q = float(self.opts["quiesce_s"])
        self.pause(q)
        self.settle()
        base = self._read_all_counters()
        self.pause(q)
        self.settle()
        now = self._read_all_counters()
        bad = ["%s.%s +%d" % (n, k, now[n][k] - base[n][k]) for n in now for k in REPAIR_COUNTERS if now[n][k] > base[n][k]]
        if bad:
            raise StepFailure("repairs during the %gs quiet window (must be 0): %s" % (q, "; ".join(bad)), "quiescence")

    def check_repair_budget(self) -> None:
        """Total repairs per minute over the run must stay within the budget (default 0: start strict)."""
        budget = self.opts.get("repair_budget_per_min")
        if budget is None:
            return
        total = sum(c["repairs"] for c in self._read_all_counters().values()) - self._repairs_at_start
        minutes = max((time.monotonic() - self._t_start) / 60.0, 1.0)
        if total / minutes > budget:
            raise StepFailure("repairs per minute %.2f exceed the %s budget %s (%d repairs in %.1f min)"
                              % (total / minutes, self.opts.get("chaos") or "run", budget, total, minutes), "budget")

    def mark_counters(self) -> None:
        self._counter_base = self._read_all_counters()

    def check_counters(self, allow_repairs: bool = False, allow_rebase: bool = False) -> Dict[str, Dict[str, int]]:
        now = self._read_all_counters()
        delta = {n: {k: now[n][k] - self._counter_base.get(n, now[n]).get(k, 0) for k in now[n]} for n in now}
        bad = []
        for n, d in delta.items():
            for k in MUST_NOT_RISE:
                if allow_rebase and k == "rebases":
                    continue
                if (allow_repairs or not self.opts["strict_counters"]) and k in REPAIR_COUNTERS:
                    continue            # a repaired desync on an impaired link is recorded, not failed
                if d[k] > 0:
                    bad.append("%s.%s rose by %d" % (n, k, d[k]))
        self._counter_base = now
        if bad and MUTANT != "nocounters":
            raise StepFailure("desync counters rose: " + "; ".join(bad), "counters")
        return delta

    def compare_snapshots(self, tag: str) -> str:
        """Host vs each client. Returns 'equal', 'skipped' or raises StepFailure."""
        if not self.comparer or not self.opts["compare"]:
            return "skipped"
        if MUTANT == "nosnapshot":
            return "equal"
        snapdir = os.path.join(self.outdir, "snap", _safe(tag))
        os.makedirs(snapdir, exist_ok=True)
        snaps = {}
        for m in self.present:
            snaps[m.name] = self.comparer.snapshot(m)
            with open(os.path.join(snapdir, m.name + ".json"), "w", encoding="utf-8") as f:
                json.dump(snaps[m.name], f, indent=1, sort_keys=True, default=str)
        problems = []
        for c in self.present[1:]:
            code, lines = self.comparer.diff(snaps[self.host.name], snaps[c.name], self.opts["snapdiff_ignore"])
            if code == 2:
                raise StepFailure("the snapshot comparison refused the input (%s): %s" % (c.name, "; ".join(lines[:3])), "snapshot")
            if code == 1:
                problems.append("host vs %s: %d difference(s), first: %s" % (c.name, len(lines), "; ".join(lines[:3])))
        if problems:
            raise StepFailure("snapshots differ. " + " | ".join(problems), "snapshot")
        return "equal"

    # ---- steps ----
    @contextlib.contextmanager
    def step(self, name: str, *, settle: bool = True, compare: bool = True, allow_repairs: bool = False, allow_rebase: bool = False):
        """with ctx.step("both shoot"): ...  On exit: settle, quiet window, snapshot compare, counter check.
        Any failure aborts the playbook after the evidence is saved."""
        self._step_n += 1
        t0 = time.monotonic()
        rec = StepRecord(name=name, ok=False)
        label = "%02d-%s" % (self._step_n, name)
        self.log("step " + label)
        try:
            if not self._counter_base:
                self.mark_counters()
                self._repairs_at_start = sum(c["repairs"] for c in self._counter_base.values())
            yield self
            if settle:
                self.settle()
                if self.opts.get("quiesce_s"):
                    self.quiesce()
            if compare:
                rec.snapshot = self.compare_snapshots(label)
            rec.counters_delta = self.check_counters(allow_repairs, allow_rebase)
            self.check_repair_budget()
            rec.ok = True
        except StepFailure as e:
            rec.reason, rec.kind = e.reason, e.kind
            if e.kind == "snapshot":
                rec.snapshot = "different"
        except PlaybookAbort:
            raise
        except MissingAction as e:
            rec.reason, rec.kind = "%s (a playbook step needs it; list it in the playbook's `requires`)" % e, "missing"
        except Exception as e:  # noqa: BLE001  a bot or link crash is also a failed step, with a trace
            rec.reason, rec.kind = "%s: %s" % (type(e).__name__, e), "exception"
            self.notes.append(traceback.format_exc())
        finally:
            rec.seconds = round(time.monotonic() - t0, 3)
            if not rec.ok:
                rec.fail_dir = self.save_failure(label, rec)
            self.records.append(rec)
        if not rec.ok:
            self.log("FAIL %s: %s" % (label, rec.reason))
            raise PlaybookAbort(rec.reason)

    # ---- failure artifacts ----
    def save_failure(self, label: str, rec: StepRecord) -> str:
        self._fail_n += 1
        d = os.path.join(self.outdir, "FAIL-%d-%s" % (self._fail_n, _safe(label)))
        os.makedirs(d, exist_ok=True)
        manifest: Dict[str, Any] = {"playbook": self.playbook, "step": label, "reason": rec.reason, "kind": rec.kind,
                                    "machines": [], "chaos": self.opts.get("chaos")}
        for m in self.machines:
            info: Dict[str, Any] = {"name": m.name, "role": m.role, "instance": m.instance}
            try:
                info["status"] = m.bot.status()
            except Exception as e:  # noqa: BLE001
                info["status_error"] = str(e)
            try:
                info["capture"] = m.bot.capture(os.path.join(d, m.name))
            except Exception as e:  # noqa: BLE001
                info["capture_error"] = str(e)
            try:
                if self.comparer and self.opts["save_snapshots"]:
                    sp = os.path.join(d, m.name + ".snapshot.json")
                    with open(sp, "w", encoding="utf-8") as f:
                        json.dump(self.comparer.snapshot(m), f, indent=1, sort_keys=True, default=str)
                    info["snapshot"] = sp
            except Exception as e:  # noqa: BLE001
                info["snapshot_error"] = str(e)
            manifest["machines"].append(info)
        manifest["steps_so_far"] = [r.__dict__ for r in self.records] + [rec.__dict__]
        manifest["notes"] = self.notes[-3:]
        with open(os.path.join(d, "failure.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1, default=str)
        return d


# ---------------------------------------------------------------------------------------------
class Playbook:
    """Subclass, set the class attributes, implement run(ctx)."""

    name = ""
    summary = ""
    min_players = 2
    max_players = 4
    needs_refs: Tuple[str, ...] = ()          # keys the scenario's `refs` block must provide
    requires: Tuple[str, ...] = ()            # adapter methods every machine must implement, else the playbook is skipped
    snapdiff_ignore: Tuple[str, ...] = ()     # fnmatch patterns for snapshot lines that may differ
    allow_repairs = False

    def run(self, ctx: Ctx) -> None:
        raise NotImplementedError


@dataclass
class RunResult:
    playbook: str
    status: str                       # pass | fail | skip
    steps: List[StepRecord]
    outdir: str
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def to_json(self) -> dict:
        return {"playbook": self.playbook, "status": self.status, "ok": self.ok, "reason": self.reason, "outdir": self.outdir,
                "steps": [s.__dict__ for s in self.steps]}


def run_playbook(pb: Playbook, machines: List[Machine], comparer: Optional[Comparer], outdir: str,
                 refs: Optional[dict] = None, opts: Optional[dict] = None, log: Optional[Callable[[str], None]] = None) -> RunResult:
    n = len(machines)
    if not (pb.min_players <= n <= pb.max_players):
        return RunResult(pb.name, "fail", [], outdir, "%s needs %d to %d players, got %d" % (pb.name, pb.min_players, pb.max_players, n))
    missing = [k for k in pb.needs_refs if k not in (refs or {})]
    if missing:
        return RunResult(pb.name, "fail", [], outdir, "scenario is missing refs %s" % missing)
    lacking = sorted({r for r in pb.requires for m in machines if not m.bot.supports(r)})
    if lacking:
        return RunResult(pb.name, "pass" if MUTANT == "skipispass" else "skip", [], outdir, "adapter does not implement: %s" % ", ".join(lacking))
    os.makedirs(outdir, exist_ok=True)
    o = dict(opts or {})
    o["snapdiff_ignore"] = list(o.get("snapdiff_ignore", [])) + list(pb.snapdiff_ignore)
    ctx = Ctx(machines, comparer, outdir, refs, o, pb.name, log)
    reason = ""
    try:
        pb.run(ctx)
        ok = all(r.ok for r in ctx.records) and bool(ctx.records)
        if not ctx.records:
            reason = "playbook ran no steps"
    except PlaybookAbort as e:
        ok, reason = False, str(e)
    except Exception as e:  # noqa: BLE001  a failure outside a step block
        kind = e.kind if isinstance(e, StepFailure) else "exception"
        text = e.reason if isinstance(e, StepFailure) else "%s: %s" % (type(e).__name__, e)
        rec = StepRecord("(outside step)", False, text, kind)
        rec.fail_dir = ctx.save_failure("outside-step", rec)
        ctx.records.append(rec)
        ok, reason = False, text
    ctx.close()
    res = RunResult(pb.name, "pass" if ok else "fail", ctx.records, outdir, reason)
    with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(res.to_json(), f, indent=1, default=str)
    return res
