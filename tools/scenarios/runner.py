"""Scenario runner: jump to a scenario on warm game instances, then run its steps and checks.

The runner is duck-typed over GameAdapter objects (see adapter.py), one per player, host first. Tests drive it with the
in-memory fake in fakegame.py; a real run hands it adapters for your game.

Jump = (reload the start save only when plan_jump says so) -> reset the scenario's state keys in place -> setup steps.
On a warm instance with a clean world that is a handful of calls instead of a full save load.
"""
import json
import os
import threading
import time
from pathlib import Path

import scenlib
from gameadapter import ScenarioError

MUTANT = os.environ.get("SCEN_MUTANT", "")   # test-only twin switch: noreload | passall | firsthost | nodirty


class StateStore:
    """Memory of what is loaded on each instance and what the last scenario changed. Keyed by instance plus a
    generation, so a restarted game (new generation) counts as empty."""

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.data = {}
        if self.path and self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except ValueError:
                self.data = {}

    def get(self, key):
        return self.data.get(key)

    def put(self, key, st):
        self.data[key] = st
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")

    @staticmethod
    def key(instance, generation):
        return "%s@%s" % (instance, generation)


class Runner:
    def __init__(self, adapters, store=None, keys=None, capabilities=None, sleep=time.sleep, now=time.monotonic,
                 load_wait_s=1.0, settle_s=0.2, poll_s=0.25, hooks=()):
        self.games = list(adapters)
        self.store = store or StateStore()
        self.keys = list(keys) if keys else [StateStore.key(i, 0) for i in range(len(self.games))]
        self.sleep, self.now = sleep, now
        self.load_wait_s, self.settle_s, self.poll_s, self.hooks = load_wait_s, settle_s, poll_s, hooks
        if capabilities is not None:
            self.caps = set(capabilities)
        else:
            sets = [g.capabilities() for g in self.games]
            known = [s for s in sets if s is not None]
            self.caps = None if not known else set.intersection(*known)   # None: everything is available

    # ---- shared world state, stored per instance
    def _same_world(self):
        sts = [self.store.get(k) for k in self.keys]
        return sts[0] if all(s == sts[0] for s in sts) else None

    # ---- one step on one instance
    def _do(self, game, step, res):
        op = step["op"]
        if op == "wait":
            self.sleep(float(step["seconds"]))
        elif op == "load":
            game.load_save(step["name"])
            self.sleep(self.load_wait_s)
        elif op == "save":
            game.save_game(step["name"])
        else:
            game.do(op, scenlib.resolve_args(step, res))

    def _check(self, sc, st, res):
        idx = scenlib.step_target(st, sc)
        args = scenlib.resolve_args(st, res)
        cmp_, value, agg = st.get("cmp", "=="), st.get("value"), st.get("agg")
        tol, timeout = st.get("tol", 0), float(st.get("timeout", 5))
        t0 = self.now()
        while True:
            vals = [float(self.games[i].read(st["kind"], args)) for i in idx]
            if scenlib.compare(vals, cmp_, value, agg, tol) or MUTANT == "passall":
                return {"status": "pass", "values": vals}
            if self.now() - t0 >= timeout:
                return {"status": "fail", "values": vals,
                        "detail": "%s %s %s%s (agg %s) not met after %.1fs; values per player %s" % (
                            st["kind"], cmp_, value, " +-%s" % tol if tol else "", agg, timeout, vals)}
            self.sleep(self.poll_s)

    def _step(self, sc, st, res):
        rec = {"id": st["id"], "op": st["op"], "status": "pass"}
        miss = sorted(scenlib.needs_of(st) - self.caps) if self.caps is not None else []
        if miss:
            rec.update(status="blocked", detail="the adapter does not provide: %s" % ", ".join(miss))
            return rec
        try:
            if st["op"] == "check":
                rec.update(self._check(sc, st, res))
            else:
                idx = scenlib.step_target(st, sc)
                if MUTANT == "firsthost":
                    idx = [0]
                if st.get("parallel") and len(idx) > 1:
                    errs = []

                    def guarded(i):
                        try:
                            self._do(self.games[i], st, res)
                        except Exception as ex:   # noqa: BLE001
                            errs.append(ex)
                    ths = [threading.Thread(target=guarded, args=(i,)) for i in idx]
                    for t in ths:
                        t.start()
                    for t in ths:
                        t.join()
                    if errs:
                        raise errs[0]
                else:
                    for i in idx:
                        self._do(self.games[i], st, res)
                if st["op"] in scenlib.SETTLE_OPS:
                    self.sleep(self.settle_s)
        except ScenarioError as e:
            rec.update(status="error", detail=str(e))
        except Exception as e:   # noqa: BLE001
            rec.update(status="error", detail="%s: %s" % (type(e).__name__, str(e)[:200]))
        return rec

    # ---- jump
    def jump(self, sc, force_reload=False):
        """Bring every instance into the scenario's starting state. Returns {reload, reasons, seconds, setup, reset}."""
        t0 = self.now()
        res = scenlib.Resolver(sc)
        fp = scenlib.footprint(sc)
        st = self._same_world()
        plan = scenlib.plan_jump(st, sc, fp, force_reload)
        if MUTANT == "noreload":
            plan = {"reload": False, "reasons": []}
        save = sc["start"]["save"]
        if plan["reload"]:
            for g in self.games:
                g.load_save(save)
            self.sleep(self.load_wait_s)
        ids = scenlib.reset_ids(sc)
        prev = set((st or {}).get("state_ids") or [])
        # state left changed by the previous scenario is reset too: an in-place jump must not inherit it
        ids = sorted(set(ids) | (prev if not plan["reload"] else set()))
        for g in self.games:
            g.reset_state(ids)
        out = []
        for s in sc.get("setup") or []:
            rec = self._step(sc, s, res)
            out.append(rec)
            if rec["status"] in ("error", "blocked"):
                break
        new = {"loaded": True, "save": save, "dirty": sorted(fp["dirty"]), "failed": False, "state_ids": ids, "scenario": sc["name"]}
        for k in self.keys:
            self.store.put(k, new)
        return {"reload": plan["reload"], "reasons": plan["reasons"], "seconds": round(self.now() - t0, 2), "setup": out, "reset": ids}

    # ---- run
    def run(self, sc, force_reload=False):
        t0 = self.now()
        errs = scenlib.validate(sc, hooks=self.hooks)
        if errs:
            return {"scenario": sc.get("name"), "status": "invalid", "errors": errs, "steps": [], "seconds": 0.0}
        res = scenlib.Resolver(sc)
        j = self.jump(sc, force_reload)
        steps = list(j["setup"])
        if not [r for r in steps if r["status"] == "error"]:
            blocked_by = None
            for s in sc["steps"]:
                if blocked_by:
                    # what follows a step that could not run is undefined: report it as blocked instead of guessing
                    steps.append({"id": s["id"], "op": s["op"], "status": "blocked", "detail": "skipped: depends on blocked step %s" % blocked_by})
                    continue
                rec = self._step(sc, s, res)
                steps.append(rec)
                if rec["status"] == "blocked":
                    blocked_by = s["id"]
        fp = scenlib.footprint(sc)
        stats = [r["status"] for r in steps]
        if "fail" in stats:
            status = "fail"
        elif "error" in stats:
            status = "error"
        elif "blocked" in stats:
            status = "partial"
        else:
            status = "pass"
        if MUTANT == "nodirty":
            fp = {"dirty": set(), "touched": fp["touched"], "state": fp["state"]}
        st = {"loaded": True, "save": sc["start"]["save"], "dirty": sorted(fp["dirty"]), "failed": status in ("fail", "error"),
              "state_ids": j["reset"], "scenario": sc["name"]}
        for k in self.keys:
            self.store.put(k, st)
        return {"scenario": sc["name"], "status": status, "jump": {k: j[k] for k in ("reload", "reasons", "seconds")},
                "steps": steps, "seconds": round(self.now() - t0, 2)}


def summarize(results):
    lines = []
    for r in results:
        j = r.get("jump") or {}
        lines.append("%-8s %-28s %6.1fs  jump:%s" % (r["status"].upper(), r["scenario"], r["seconds"], "reload" if j.get("reload") else "in-place"))
        for s in r.get("steps", []):
            if s["status"] != "pass":
                lines.append("    %s %s: %s" % (s["status"], s["id"], s.get("detail", "")))
        for e in r.get("errors", []):
            lines.append("    invalid: %s" % e)
    return "\n".join(lines)
