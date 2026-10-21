#!/usr/bin/env python3
"""One command for the bots tool:   python -I tools/bots/run_tests.py     (prints ALL OK only when everything passes)

Part 1: the unit tests (tests/), which include every playbook twin: a playbook plus a deliberately wrong fake behaviour
        must FAIL. Fakes only; no game is ever started.
Part 2: engine twins. The same tests run again under each COOPBOTS_MUTANT value; each breaks one check of the runner itself
        (settle, snapshot compare, counters, skip handling) and must make at least one test fail.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE / "tests"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TESTS))

ENGINE_MUTANTS = {
    "nosettle": "the runner stops waiting for machines to converge",
    "nosnapshot": "the runner stops comparing snapshots",
    "nocounters": "the runner stops checking the desync counters",
    "skipispass": "a skipped playbook is reported as a pass",
}


def run_suite(quiet):
    suite = unittest.defaultTestLoader.discover(str(TESTS), top_level_dir=str(TESTS))
    stream = open(os.devnull, "w") if quiet else sys.stderr
    return unittest.TextTestRunner(stream=stream, verbosity=0 if quiet else 1, failfast=quiet).run(suite)


def main():
    if os.environ.get("COOPBOTS_MUTANT"):
        return 0 if run_suite(True).wasSuccessful() else 1
    res = run_suite(False)
    print("tests run: %d" % res.testsRun)
    if not res.wasSuccessful():
        print("FAILED")
        return 1
    from coopbots import registry, fakecoop
    print("playbooks: %d, playbook twins caught: %d, other fake bugs caught: %d (every one of the %d fake bugs has a twin)"
          % (len(registry.REGISTRY), len(registry.TWINS), len(registry.UNIVERSAL), len(fakecoop.BUGS)))
    bad = []
    for m, what in ENGINE_MUTANTS.items():
        env = dict(os.environ, COOPBOTS_MUTANT=m)
        p = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve())], env=env, capture_output=True, text=True)
        caught = p.returncode != 0
        print("engine twin %-11s %-52s %s" % (m, what, "caught" if caught else "NOT CAUGHT"))
        if not caught:
            bad.append(m)
    if bad:
        print("FAILED: engine twins not caught: %s" % bad)
        return 1
    print("engine twins caught: %d of %d" % (len(ENGINE_MUTANTS), len(ENGINE_MUTANTS)))
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
