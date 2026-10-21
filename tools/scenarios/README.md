# Scenarios: jump to a starting state, then test

Co-op tests need a starting state: "both players stand at the raider camp, three raiders are alive". Reloading a save for
every test costs a minute or more. This tool describes the starting state and the test as one JSON file, checks the file
without a game, and then gets every game instance into that state by resetting in place, reloading the save only when
it has to.

It is game independent. The game side is one small class (the adapter) that you write for your game.

* [SCHEMA.md](SCHEMA.md): the file format (objects, steps, checks, jump rules).
* `scenlib.py`: loading, validation, jump planning, comparison. Pure functions, standard library only.
* `runner.py`: runs a scenario over adapters, keeps what is loaded on each instance, reports `pass`, `fail`, `error`, `partial`, `invalid`.
* `gameadapter.py`: the interface you implement.
* `fakegame.py`: an in-memory fake of N instances sharing one world, with switchable bugs. For tests and dry runs.
* `scen.py`: command line (`list`, `validate`, `plan`, `run`).
* `examples/fnv/`: four Fallout: New Vegas scenarios and a small console adapter for it.

## Quick start

```
python -I tools/scenarios/scen.py list
python -I tools/scenarios/scen.py validate
python -I tools/scenarios/scen.py plan ownership_handoff --prev fight     # would this jump reload the save?
python -I tools/scenarios/scen.py run fight loot_race quest_stage_sync --fake    # dry run, no game
```

Then write your own file next to the examples (copy one), and run it on your game:

```
python -I tools/scenarios/scen.py --dir my_scenarios run my_scenario --adapter my_game:make_adapter --players 2
```

`make_adapter(i)` returns the `GameAdapter` for game instance `i`. Instance 0 is the host. The tool never starts a game;
you start the instances and join them into one session first.

## How to write an adapter for your game

Subclass `GameAdapter` (see `gameadapter.py`, about 40 lines) and fill in five things.

```python
from gameadapter import GameAdapter, ScenarioError

class MyGame(GameAdapter):
    OPS = {"op:kill", "op:move", "op:enable", "check:dead", "check:state"}   # what you can do; leave it out to claim everything

    def __init__(self, conn):                  # conn: however you reach ONE running game instance
        self.conn = conn

    def do(self, op, args):                    # op "kill", args {"ref": "<id from the scenario>"}
        if op == "kill":
            self.conn.run_script("kill %s" % args["ref"])
        elif op == "move":
            self.conn.run_script("teleport %s %s" % (args["who"], args["to"]))   # who may be "player"
        else:
            raise ScenarioError("op %s is not implemented" % op)

    def read(self, kind, args):                # a number. 1 and 0 for true and false
        if kind == "dead":
            return float(self.conn.query("is_dead %s" % args["ref"]))
        raise ScenarioError("check %s is not implemented" % kind)

    def load_save(self, name):  self.conn.load(name)
    def save_game(self, name):  self.conn.save(name)
    def reset_state(self, ids): ...            # put these quests or flags back to their start value, no reload
```

Rules that keep the results honest:

1. Raise `ScenarioError` when the game refuses something (a console parse error, a missing object). The step becomes `error`,
   never a silent pass.
2. Leave out what you cannot do. The step is then `blocked`, and the scenario ends `partial`. A scenario that cannot be run is
   not a scenario that passed.
3. `read` must ask the instance it belongs to. Every check runs on each player it targets, so a bug that only shows on the
   guest is found.
4. `reset_state` must really reset. If it cannot reset something, leave that object out of the scenario or set `start.reload`.
5. Add a validation hook if you have game data: `scenlib.validate(sc, hooks=[check_ids_exist])`. The hook gets the scenario and
   returns error strings, for example "id GSPG09Ref is not in the dump".

`examples/fnv/fnv_game.py` is a complete, small adapter for a game with a script console: each op becomes one console line,
each check one expression. Read it first.

## How it is tested

```
python -I tools/scenarios/run_tests.py
```

Prints `ALL OK` only when every test passes and every twin is caught. No game is started.

* 59 unit tests: the validator (every kind of broken file), id resolution, op and check translation, the comparison table,
  the jump rules, the runner against `fakegame.py` (including a guest that never sees changes, duplicated loot, double
  spawn, a missing ownership handoff, blocked steps, console errors, invalid files never reaching the game, in-place versus
  reload jumps, and that an in-place jump costs fewer than 20 adapter calls), the example console adapter against a
  recording bridge, and the command line.
* 5 mutation twins. The suite is run again with one behaviour broken (`SCEN_MUTANT`): no alias checking, jump never
  reloading, scenarios forgetting what they changed, every check passing, every step running only on the host. Each must
  make a test fail, and the run prints `caught` for each.

## Ported from fnv-coop commit f57aa78

Ported from the Fallout: New Vegas co-op project ([cranebeaker/fnv-coop](https://github.com/cranebeaker/fnv-coop), commit f57aa78).
The format, validator, jump planner, runner and fake were made game independent: form ids and plugin load orders became
free-form ids, the data dump checks became validation hooks, and the Fallout console lines moved into the example adapter.
