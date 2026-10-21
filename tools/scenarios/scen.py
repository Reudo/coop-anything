#!/usr/bin/env python3
"""Scenario command line.

    python -I tools/scenarios/scen.py list [DIR]
    python -I tools/scenarios/scen.py validate [FILE_OR_NAME ...]        game-free; exit 1 on any error
    python -I tools/scenarios/scen.py plan NAME [--prev NAME]            show the jump decision (reload or in place), no game
    python -I tools/scenarios/scen.py run NAME ... --fake                dry run on the in-memory fake game (no game)
    python -I tools/scenarios/scen.py run NAME ... --adapter pkg.mod:factory [--players N]
                                                                         run on your game; factory(i) returns the GameAdapter
                                                                         of instance i. The tool never launches a game itself.

A NAME is the file name without .json, looked up under the examples folder (or the folder given with --dir).
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenlib  # noqa: E402
import runner  # noqa: E402


def _paths(names, directory):
    if not names:
        return scenlib.list_scenarios(directory)
    out = []
    for n in names:
        p = Path(n)
        if p.suffix == ".json":
            out.append(p)
        else:
            hits = sorted(Path(directory).rglob(n + ".json"))
            out.append(hits[0] if hits else Path(directory) / (n + ".json"))
    return out


def cmd_list(a):
    for p in scenlib.list_scenarios(a.dir):
        sc = scenlib.load_scenario(p)
        print("%-24s players=%d  %s" % (sc["name"], scenlib.players_of(sc), sc["title"]))
    return 0


def cmd_validate(a):
    paths = _paths(a.names, a.dir)
    bad = 0
    for p in paths:
        errs = scenlib.validate_file(p)
        print("%s %s" % ("FAIL" if errs else "ok  ", p.name))
        for e in errs:
            print("    " + e)
        bad += bool(errs)
    print("%d scenario file(s) checked, %d invalid" % (len(paths), bad))
    return 1 if bad else 0


def cmd_plan(a):
    sc = scenlib.load_scenario(_paths([a.name], a.dir)[0])
    state = {"loaded": False}
    if a.prev:
        pv = scenlib.load_scenario(_paths([a.prev], a.dir)[0])
        state = {"loaded": True, "save": pv["start"]["save"], "dirty": sorted(scenlib.footprint(pv)["dirty"]), "failed": False}
    print(json.dumps(scenlib.plan_jump(state, sc), indent=1))
    print("state keys reset in place:", " ".join(scenlib.reset_ids(sc)) or "(none)")
    return 0


def cmd_run(a):
    scs = [scenlib.load_scenario(p) for p in _paths(a.names, a.dir)]
    n = a.players or max(scenlib.players_of(s) for s in scs)
    if a.fake:
        import fakegame
        w, clock, games = fakegame.make(n)
        rn = runner.Runner(games, runner.StateStore(), sleep=clock.sleep, now=clock.now)
        for s in scs:
            w.load_scenario(s)
    elif a.adapter:
        sys.path.insert(0, str(Path.cwd()))
        mod, _, fn = a.adapter.partition(":")
        factory = getattr(importlib.import_module(mod), fn)
        rn = runner.Runner([factory(i) for i in range(n)], runner.StateStore(a.state))
    else:
        print("run needs --fake or --adapter pkg.mod:factory")
        return 2
    results = [rn.run(s, a.force_reload) for s in scs if scenlib.players_of(s) <= n]
    print(runner.summarize(results))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0 if results and all(r["status"] == "pass" for r in results) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(scenlib.SCEN_DIR), help="folder with scenario files (default: the shipped examples)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("validate")
    p.add_argument("names", nargs="*")
    p.set_defaults(fn=cmd_validate)
    p = sub.add_parser("plan")
    p.add_argument("name")
    p.add_argument("--prev")
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("run")
    p.add_argument("names", nargs="*")
    p.add_argument("--fake", action="store_true")
    p.add_argument("--adapter")
    p.add_argument("--players", type=int, default=0)
    p.add_argument("--state", help="file that remembers what is loaded between runs")
    p.add_argument("--json")
    p.add_argument("--force-reload", action="store_true")
    p.set_defaults(fn=cmd_run)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
