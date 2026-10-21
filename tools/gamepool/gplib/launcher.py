"""Start, watch and stop several game copies, and run a test command against them.

    gamepool.py --config game.json up --n 2          take 2 game slots, start the copies, wait until ready
    gamepool.py --config game.json status
    gamepool.py --config game.json down              kill only the processes `up` started, free the slots
    gamepool.py --config game.json job --id t1 --n 2 -- python my_test.py
        takes n slots, runs the command with GAMEPOOL_INSTANCES=0,1 in its environment, copies the logs the
        config lists (collect_logs) to <state>/runs/<id>/, always frees the slots

Rules this file keeps (each has a test):
  * Every launch holds a game slot first (tools/gameslot). The instance numbers are the slot numbers, so two
    agents never use the same instance folder, pipe name or port.
  * Only processes this tool started are ever killed, and only while pid, image name and creation time still
    match what was recorded at launch (a reused pid is a different process).
  * Copies are started one after the other: copy k must be ready before copy k+1 starts.
  * A copy that exits within watch_s seconds of launch is reported with its exit code. That is how a
    single-instance check ("already running") shows up. See playbook/multi-instance-testing.md.
  * A copy is started from a long-lived detached process group, so it is not killed when this command ends.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import instances, jobqueue, winproc
from .adapter import Adapter, load_adapter
from .config import HUB, Config, ConfigError, state_dir

GAMESLOT = HUB / "tools" / "gameslot" / "gameslot.py"
DEFAULT_OWNER = os.environ.get("GAMEPOOL_OWNER", "gamepool")
DETACH_FLAGS = 0x00000008 | 0x00000200 | 0x01000000    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB


class SlotBusy(Exception):
    pass


class LaunchError(Exception):
    pass


# ------------------------------------------------------------------------------------------ game slots
def gameslot_cli(*args: str) -> Tuple[int, str]:
    cp = subprocess.run([sys.executable, "-I", str(GAMESLOT), *args], capture_output=True, text=True)
    return cp.returncode, (cp.stdout + cp.stderr).strip()


def slot_acquire(owner: str = DEFAULT_OWNER, ttl: int = 900, wait: int = 3600, slots: int = 1) -> List[int]:
    """Take slots; returns their indices. Idempotent for the same owner (renews)."""
    code, out = gameslot_cli("acquire", "--owner", owner, "--ttl", str(ttl), "--wait", str(wait), "--slots", str(slots))
    if code != 0:
        raise SlotBusy(out)
    m = re.search(r"SLOTS ([0-9,]+)", out)
    return [int(x) for x in m.group(1).split(",")] if m else []


def slot_release(owner: str = DEFAULT_OWNER) -> str:
    return gameslot_cli("release", "--owner", owner)[1]


def register_pid(pid: int, owner: str = DEFAULT_OWNER) -> None:
    gameslot_cli("register-pid", "--owner", owner, "--pid", str(pid))


# ------------------------------------------------------------------------------------------ recorded processes
def state_path(cfg: Config, owner: str = DEFAULT_OWNER) -> Path:
    return cfg.instances_root / f"state-{owner}.json"


def load_state(cfg: Config, owner: str = DEFAULT_OWNER) -> Dict:
    try:
        d = json.loads(state_path(cfg, owner).read_text())
        d.setdefault("procs", {})
        return d
    except (OSError, ValueError):
        return {"procs": {}}


def save_state(cfg: Config, st: Dict, owner: str = DEFAULT_OWNER) -> None:
    p = state_path(cfg, owner)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=1))


def record_proc(cfg: Config, i: int, pid: int, owner: str = DEFAULT_OWNER) -> None:
    info = winproc.process_info(pid) or {"name": "", "created": 0}
    st = load_state(cfg, owner)
    st["procs"][str(i)] = {"pid": pid, "created": info["created"], "name": info["name"]}
    save_state(cfg, st, owner)


def is_recorded_process(cfg: Config, pid: int, owner: str = DEFAULT_OWNER) -> bool:
    """True only if pid is a process this owner recorded, and it is still that same process."""
    for rec in load_state(cfg, owner)["procs"].values():
        if rec["pid"] == pid:
            info = winproc.process_info(pid)
            return bool(info) and info["created"] == rec["created"] and info["name"] == rec["name"]
    return False


def all_recorded_pids(cfg: Config) -> List[int]:
    pids: List[int] = []
    root = cfg.instances_root
    if root.exists():
        for f in root.glob("state-*.json"):
            try:
                pids += [r["pid"] for r in json.loads(f.read_text()).get("procs", {}).values()]
            except (OSError, ValueError, KeyError):
                pass
    return pids


def forget_pid(cfg: Config, pid: int, owner: str = DEFAULT_OWNER) -> None:
    st = load_state(cfg, owner)
    st["procs"] = {i: r for i, r in st["procs"].items() if r["pid"] != pid}
    save_state(cfg, st, owner)


def kill_recorded(cfg: Config, i: int, owner: str = DEFAULT_OWNER) -> bool:
    st = load_state(cfg, owner)
    rec = st["procs"].pop(str(i), None)
    save_state(cfg, st, owner)
    if rec and is_recorded_process_rec(rec):
        winproc.kill_pid(rec["pid"])
        return True
    return False


def is_recorded_process_rec(rec: Dict) -> bool:
    info = winproc.process_info(rec["pid"])
    return bool(info) and info["created"] == rec["created"] and info["name"] == rec["name"]


# ------------------------------------------------------------------------------------------ launching
def spawn_detached(cmd, cwd, env, startupinfo=None) -> subprocess.Popen:
    """Start a process that outlives us: outside our job object (breakaway), no console, own process group.
    Without this, a game started by a short-lived command dies with it when the parent's job closes. If the
    job forbids breakaway (access denied) fall back to the same flags without it."""
    kw = dict(cwd=cwd, env=env, startupinfo=startupinfo, close_fds=True,
              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        return subprocess.Popen(cmd, creationflags=DETACH_FLAGS, **kw)
    except OSError:
        return subprocess.Popen(cmd, creationflags=DETACH_FLAGS & ~0x01000000, **kw)


def launch_command(cfg: Config, i: int) -> Tuple[List[str], str, Dict[str, str]]:
    """(argv, cwd, env) for instance i. The copy starts in its own folder with its own number in the env."""
    launch = cfg["launch"]
    if not launch["exe"]:
        raise ConfigError("launch.exe is not set")
    d = cfg.instance_dir(i)
    exe = Path(cfg.fmt(launch["exe"], i))
    if not exe.is_absolute():
        exe = d / exe
    env = dict(os.environ)
    env.update({k: cfg.fmt(v, i) for k, v in launch["env"].items()})
    env["GAMEPOOL_INSTANCE"] = str(i)
    env["GAMEPOOL_INSTANCE_DIR"] = str(d)
    return [str(exe)] + [cfg.fmt(a, i) for a in launch["args"]], str(d), env


def find_game_child(cfg: Config, loader_pid: int, skip: List[int]) -> int:
    """The real game process behind a loader: a descendant of the loader with the game's image name.
    Found by process tree, not by 'a new process with that name appeared', so a game another agent or the
    owner started at the same moment is never picked up."""
    deadline = time.time() + float(cfg["launch"]["child_wait_s"])
    while time.time() < deadline:
        for cand in winproc.descendants(loader_pid, cfg.require_process_name()):
            if cand not in skip:
                return cand
        time.sleep(0.2)
    raise LaunchError(f"loader pid {loader_pid} started no {cfg.process_name} within {cfg['launch']['child_wait_s']} s")


def launch_instance_ex(cfg: Config, i: int, owner: Optional[str] = DEFAULT_OWNER) -> Tuple[int, subprocess.Popen]:
    """Start instance i. Returns (game pid, the Popen of the launched exe). The pid is recorded under owner
    (state file and game slot) so only this tool can kill it later."""
    argv, cwd, env = launch_command(cfg, i)
    p = spawn_detached(argv, cwd, env, winproc.startup_info(cfg["launch"]["window"]))
    pid = p.pid
    if cfg["launch"]["spawns_game"]:
        pid = find_game_child(cfg, p.pid, all_recorded_pids(cfg))
    if owner:
        record_proc(cfg, i, pid, owner)
        register_pid(pid, owner)
    if cfg["launch"]["window"] == "minimized":
        threading.Thread(target=winproc.minimize_windows, args=(pid,), daemon=True).start()
    return pid, p


def launch_instance(cfg: Config, i: int, owner: Optional[str] = DEFAULT_OWNER) -> int:
    return launch_instance_ex(cfg, i, owner)[0]


def wait_alive(pid: int, seconds: float) -> bool:
    """True if pid is still running after `seconds`; returns False as soon as it is gone."""
    end = time.time() + seconds
    while time.time() < end:
        if not winproc.pid_alive(pid):
            return False
        time.sleep(0.1)
    return winproc.pid_alive(pid)


# ------------------------------------------------------------------------------------------ up / down / status
def start_instances(cfg: Config, ids: List[int], owner: str, adapter: Adapter, stagger_s: float, wait_ready_each: float) -> int:
    """Start the copies in `ids` one after the other. Returns 0, 2 (not provisioned) or 3 (a copy exited or never became ready)."""
    st = load_state(cfg, owner)
    for i in ids:
        if not instances.provisioned(cfg, i):
            print(f"instance {i} is not provisioned; run `provision --n {max(ids) + 1}` first", file=sys.stderr)
            return 2
        rec = st["procs"].get(str(i))
        if rec and is_recorded_process_rec(rec):
            print(f"instance {i} already up (pid {rec['pid']})")
            continue
        adapter.prepare(i)
        pid, popen = launch_instance_ex(cfg, i, owner)
        time.sleep(stagger_s)
        if not wait_alive(pid, float(cfg["launch"]["watch_s"])):
            code = popen.poll()
            print(f"instance {i} (pid {pid}) exited within {cfg['launch']['watch_s']} s"
                  + (f" with exit code {code}" if code is not None else "")
                  + ". A single-instance check is a common cause; read the instance's logs.", file=sys.stderr)
            return 3
        if not adapter.wait_ready(i, pid, winproc.pid_alive, wait_ready_each):
            print(f"instance {i}: not ready (pid alive={winproc.pid_alive(pid)}) after {wait_ready_each:.0f} s; "
                  "no further copies are started", file=sys.stderr)
            return 3
        print(f"instance {i} ready (pid {pid})")
    return 0


def foreign_pids(cfg: Config) -> List[int]:
    """Running processes with the game's image name that no owner of this tool recorded (maybe the owner's own game)."""
    mine = set(all_recorded_pids(cfg))
    return [p for p in winproc.list_pids(cfg.require_process_name()) if p not in mine]


def stop_owner(cfg: Config, owner: str) -> List[int]:
    """Kill the recorded processes of owner (only while they are still the same process) and forget them."""
    st = load_state(cfg, owner)
    killed = []
    for i, rec in list(st["procs"].items()):
        if is_recorded_process_rec(rec):          # never kill a reused pid
            winproc.kill_pid(rec["pid"])
            killed.append(rec["pid"])
            print(f"killed instance {i} (pid {rec['pid']})")
        st["procs"].pop(i)
    save_state(cfg, st, owner)
    return killed


def cmd_up(cfg: Config, a, adapter: Optional[Adapter] = None) -> int:
    cfg.require_dirs()
    cfg.require_process_name()
    adapter = adapter or load_adapter(cfg)
    try:
        ids = slot_acquire(a.owner, ttl=a.ttl, wait=a.slot_wait, slots=a.n)
    except SlotBusy as e:
        print(f"game slot busy: {e}", file=sys.stderr)
        return 3
    foreign = foreign_pids(cfg)
    if foreign and not a.allow_foreign:
        print(f"{cfg.process_name} already running (pids {foreign}) and not ours. It may be the owner's own game; "
              "nothing was started. Use --allow-foreign to start copies next to it.", file=sys.stderr)
        if not load_state(cfg, a.owner)["procs"]:       # keep the slots while copies of ours are running
            slot_release(a.owner)
        return 2
    print("instances:", ids)
    return start_instances(cfg, ids, a.owner, adapter, a.stagger, a.wait_ready_each)


def cmd_down(cfg: Config, a) -> int:
    stop_owner(cfg, a.owner)
    print(slot_release(a.owner))
    return 0


def cmd_status(cfg: Config, a) -> int:
    root = cfg.instances_root
    recorded: Dict[str, Dict] = {}
    if root.exists():
        for f in root.glob("state-*.json"):
            for i, rec in load_state(cfg, f.stem[len("state-"):])["procs"].items():
                recorded[i] = dict(rec, owner=f.stem[len("state-"):])
    rows = []
    for dd in sorted(p for p in root.glob("*") if p.name.isdigit()) if root.exists() else []:
        i = dd.name
        rec = recorded.get(i)
        rows.append({"instance": int(i), "dir": str(dd), "provisioned": (dd / "instance.json").exists(),
                     "pid": rec["pid"] if rec else None, "owner": rec["owner"] if rec else None,
                     "alive": bool(rec and is_recorded_process_rec(rec)), "lock": jobqueue.holder(root, int(i))})
    print(json.dumps(rows, indent=1))
    return 0


# ------------------------------------------------------------------------------------------ jobs
def collect_logs(cfg: Config, i: int, since: float, dest: Path) -> List[str]:
    """Copy files of instance i that match collect_logs globs and changed after `since` into dest/inst<i>/."""
    d = cfg.instance_dir(i)
    out = dest / f"inst{i}"
    got = []
    for pat in cfg["collect_logs"]:
        for f in d.glob(pat):
            if f.is_file() and f.stat().st_mtime >= since:
                rel = f.relative_to(d)
                tgt = out / rel
                tgt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, tgt)
                got.append(str(rel))
    return got


def run_job(cfg: Config, job_id: str, n: int, cmd: List[str], *, timeout_s: float = 900.0, owner: str = DEFAULT_OWNER,
            use_slot: bool = True, pool: int = 2, slot_wait_s: int = 3600, check_pins: bool = True,
            require: Optional[List[str]] = None, extra_env: Optional[Dict[str, str]] = None,
            runs_dir: Optional[Path] = None) -> Dict:
    """Run cmd with the instances it may use in GAMEPOOL_INSTANCES. With use_slot the instances are the game
    slots taken from gameslot; otherwise they are leased by file lock out of range(pool)."""
    runs = Path(runs_dir or state_dir() / "runs") / job_id
    runs.mkdir(parents=True, exist_ok=True)
    result: Dict = {"job": job_id, "n": n, "cmd": cmd, "status": "error"}
    t_queue = time.time()
    held = None
    if use_slot:
        try:
            inst = slot_acquire(owner, ttl=int(timeout_s) + 300, wait=slot_wait_s, slots=n)
        except SlotBusy as e:
            result.update(status="slot_busy", message=str(e))
            (runs / "result.json").write_text(json.dumps(result, indent=1))
            return result
    else:
        held = jobqueue.acquire(cfg.instances_root, n, pool=pool, job=job_id, timeout_s=slot_wait_s)
        inst = jobqueue.instance_ids(held)
    try:
        result.update(instances=inst, queued_s=round(time.time() - t_queue, 2))
        problems: List[str] = []
        if check_pins:
            for i in inst:
                if not instances.provisioned(cfg, i):
                    problems.append(f"inst{i}: not provisioned")
                else:
                    problems += [f"inst{i}: {p}" for p in instances.verify_pins(cfg, i, require)]
        if problems:
            result.update(status="pin_mismatch", problems=problems)
        else:
            env = dict(os.environ)
            env.update(extra_env or {})
            env["GAMEPOOL_INSTANCES"] = ",".join(map(str, inst))
            env["GAMEPOOL_JOB"] = job_id
            t0 = time.time()
            try:
                cp = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout_s)
                result.update(status="pass" if cp.returncode == 0 else "fail", returncode=cp.returncode)
                (runs / "stdout.txt").write_text(cp.stdout)
                (runs / "stderr.txt").write_text(cp.stderr)
            except subprocess.TimeoutExpired as e:
                result.update(status="timeout")
                so = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
                (runs / "stdout.txt").write_text(so)
            result["duration_s"] = round(time.time() - t0, 2)
            result["logs"] = {str(i): collect_logs(cfg, i, t0, runs) for i in inst}
    finally:
        if use_slot:
            slot_release(owner)
        else:
            for lk in held or []:
                lk.release()
    (runs / "result.json").write_text(json.dumps(result, indent=1))
    return result


def main(cfg: Config, argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="gamepool up|down|status|job")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("up")
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--stagger", type=float, default=cfg["launch"]["stagger_s"])
    p.add_argument("--ttl", type=int, default=1800, help="game slot lease in seconds (released by `down`)")
    p.add_argument("--slot-wait", type=int, default=3600)
    p.add_argument("--wait-ready-each", type=float, default=float(cfg["ready"].get("timeout_s", 300)))
    p.add_argument("--allow-foreign", action="store_true", help="start copies although another copy of the game is running")
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p = sub.add_parser("down")
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p = sub.add_parser("status")
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p = sub.add_parser("job")
    p.add_argument("--id", required=True)
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--pool", type=int, default=2, help="instances to choose from with --no-slot")
    p.add_argument("--timeout", type=float, default=900)
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p.add_argument("--require", action="append", default=[], metavar="REL", help="file that must exist in every instance")
    p.add_argument("--no-pin-check", action="store_true")
    p.add_argument("--no-slot", action="store_true", help="the job does not run the game: lease instances by file lock only")
    p.add_argument("cmd_", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.cmd == "up":
        return cmd_up(cfg, a)
    if a.cmd == "down":
        return cmd_down(cfg, a)
    if a.cmd == "status":
        return cmd_status(cfg, a)
    cmd = [c for c in a.cmd_ if c != "--"]
    if not cmd:
        ap.error("job needs a command after --")
    cfg.require_dirs()
    r = run_job(cfg, a.id, a.n, cmd, timeout_s=a.timeout, owner=a.owner, use_slot=not a.no_slot, pool=a.pool,
                check_pins=not a.no_pin_check, require=a.require)
    print(json.dumps(r, indent=1))
    return 0 if r["status"] == "pass" else 1
