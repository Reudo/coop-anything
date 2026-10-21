# Co-op bots and playbooks

Co-op breaks in ways one player never sees: two players grab the same item, one player's kill never reaches the other
machine, a quest step fires twice, a rejoining player gets every reward again. These tests run 2 to 4 real game
instances, drive each with a bot, and after every step check that all machines agree.

It is game independent. The runner and the twelve playbooks know nothing about any game. Everything game specific is one
class, the **action adapter**, that you write for your game.

```
playbook (what to do, what must hold)  ->  runner (settle, compare, counters, evidence)  ->  ActionAdapter (your game)
```

* `coopbots/adapter.py`: the adapter interface (`ActionAdapter`, `Result`, `MissingAction`). Read the module docstring.
* `coopbots/core.py`: the runner: steps, settle, quiet windows, repair budgets, snapshot compare, desync counters, failure evidence.
* `coopbots/playbooks/`: the playbooks, written against the adapter only.
* `coopbots/fakecoop.py`: a fake co-op session (a host and 1 to 3 lagging clients) with 27 switchable bugs. It is the test adapter.
* `coopbots/links.py`: options for impaired links. `coopbots/refs.py`: playbook refs from a scenario file.
* `adapters/fnv/`: a small example adapter for a Gamebryo game with a script console.
* `run_coop.py`: the command line. `run_tests.py`: the tests.

## Quick start

No game needed for the first run:

```
python -I tools/bots/run_coop.py --list
python -I tools/bots/run_coop.py --fake --playbook all
python -I tools/bots/run_coop.py --fake --playbook loot_race --bug dup_pickup      # must FAIL: the bug is caught
python -I tools/bots/run_coop.py --fake --playbook quest_sync --link bad_wifi      # lossy link with quiet windows
```

On your game, once you have an adapter (you start the instances and join them into one session; the tool never launches a game):

```
python -I tools/bots/run_coop.py --adapter my_game:make_adapter --players 2 \
    --scenario my_scenarios/fight.json --playbook fight
```

`make_adapter(i)` returns the adapter for instance `i`; instance 0 is the host. `--scenario` is a scenario file from
[tools/scenarios](../scenarios/README.md) whose `refs` block names what the playbook needs (`--refs file.json` does the
same with plain JSON). Exit code 0 means at least one playbook passed and none failed. A `SKIP` (the adapter lacks an
action the playbook needs) is never a pass, so a run where everything skipped exits 1.

## How to write an adapter for your game

One adapter object drives one running game instance. Subclass `ActionAdapter`, implement the engine surface first, then
the actions the playbooks you want need. Anything you leave out raises `MissingAction`, `supports("take")` says it is
missing, and every playbook that needs it is reported `SKIP` with the name of the missing action.

### 1. The engine surface (the runner uses these after every step)

```python
from coopbots.adapter import ActionAdapter, Result

class MyGame(ActionAdapter):
    def __init__(self, conn, name="bot"):
        self.conn, self.name = conn, name

    def status(self):
        s = self.conn.sync_status()                  # whatever your netcode can tell you
        return {"seq": s.last_applied,               # number of the last host update this machine applied
                "synced": s.all_clients_caught_up,   # host only; leave out on clients
                "counters": {"mismatches": s.digest_mismatches, "repairs": s.repairs,
                             "bad_messages": s.bad_messages, "apply_failures": s.apply_failures, "rebases": s.rebases}}

    def snapshot(self):
        return {"shared": self.conn.dump_world(),    # must be EQUAL on every machine once synced
                "per_player": self.conn.dump_me()}   # inventory, position: allowed to differ

    def capture(self, directory):                    # optional: logs for a failed step
        ...
```

* `seq` is how the runner knows the machines converged: it waits until every client reports the host's number and keeps
  it for two polls. If your netcode has no sequence number, use any counter that equals on all machines when nothing is in
  flight (a state hash works).
* `counters` are optional. Use the names `mismatches`, `repairs`, `repaired_effects` (a desync was found and healed) and
  `bad_messages`, `apply_failures`, `rebases` (never acceptable). A counter that rises during a step fails the step.
  Names you add are kept in the records but never fail anything.
* `shared` is compared path by path between the host and each client. Keep per-player or cosmetic things out of it, or list
  them in `snapdiff_ignore` (fnmatch patterns such as `shared/refs/*/in_use*`). An empty `shared` is refused.

### 2. Actions: return a `Result`, check the postcondition

```python
    def take(self, item, count, from_ref):
        before = (self.inventory_count(item), self.inventory_count(item, from_ref))
        self.conn.run("transfer %s %s %d" % (from_ref, item, count))
        after = (self.inventory_count(item), self.inventory_count(item, from_ref))
        if after[0] - before[0] != count or before[1] - after[1] != count:
            return Result(False, "transfer moved %d in and %d out" % (after[0] - before[0], before[1] - after[1]))
        return Result(True)
```

* An ordinary refusal (a locked door, a lost race) is `Result(False, "reason")`. Raise only when the game or the link is
  dead; the runner records a crash as a failed step with a trace.
* Check that the thing really happened, not that the call returned. A bot that reports success because the call went
  through is the main source of hollow passes. The example adapter shows the pattern for `take`, `pickup`, `unlock`, `goto_ref`.
* Ids (`ref`, `item`, `quest`) are opaque strings. The playbooks only hand back what the scenario gave them.
* The full list of actions and queries, with what each must return, is in the `coopbots/adapter.py` docstring. The playbook
  table below says which ones each playbook needs.

### 3. Run it

Run one playbook with `--adapter`. Fix what `SKIP` and `FAIL` tell you, one action at a time. Then keep the adapter next to
your game's tests. `adapters/fnv/fnv_adapter.py` (under 150 lines) is a complete small example: console lines for the
actions, expressions for the queries, and a status mapping.

## The playbooks

Each playbook is a short script of steps. After every step the runner settles, compares snapshots and checks counters.
`refs` are the names the scenario (or `--refs`) must provide. `requires` are the adapter methods every machine needs; without
them the playbook is skipped.

| playbook | players | refs | requires | what each step proves |
|---|---|---|---|---|
| `fight` | 2-4 | `raiders` (list), `raider_base?`, `weapon?` | goto_ref, aim_at, fire, target_alive | everyone shoots the same enemies; dead on every machine, each dies exactly once, enemy count constant (needs `ref_count`, skipped with a note otherwise) |
| `ownership_handoff` | 2-4 | `raiders`, `far_pos`, `near_pos` | goto_ref, goto_pos, aim_at, fire, target_alive, owner_of | the host walks away: control moves once to the client, no flapping when the host returns, the fight continues |
| `loot_race` | 2-4 | `item`, `item_base` | goto_ref, pickup, inventory_count, ref_enabled, drop | exactly one pickup wins and the party holds exactly 1; two more rounds by dropping and racing again |
| `container_share` | 2-4 | `container`, `item_a`, `item_b` | goto_ref, open_container, close_container, take, put, inventory_count | one "in use" lock; take and put replicate; nothing duplicated or lost |
| `door_lock` | 2-4 | `door`, `locked_door`, `device`, `device_entry`, `locked_box`, `key` | doors, unlock, use_device, is_locked, containers | door open and close from host and client, a locked door refuses, unlock with a key, a device entry unlocks a box |
| `fast_travel_tether` | 2-4 | `marker`, `anchor`, `tether_radius`, `far_pos`, `hostile?`, `weapon?` | goto_ref, fast_travel, consent, distance_to, cell | refused without consent and in combat; all arrive together; a wanderer is held by the tether |
| `dialogue_spectator` | 2-4 | `npc`, `topics`, `speakers?`, `done_quest?`, `done_stage?` | talk, pick_topic, end_dialogue, in_dialogue, spectating | the speaker talks, the others spectate and are released, no second speaker, roles swap |
| `consent_vote` | 2-4 | `barrier_quest`, `barrier_stage` and/or `confirm_ref`, `confirm_quest`, `confirm_from`, `confirm_to` | set_stage, barrier_pass, activate, answer_prompt, consent | a barrier holds until the last player passes and applies once; a ready check: decline, a guest's "not yet" vetoes, all ready applies once |
| `consent_vote_guest_declines` | 2-4 | same | same | the ready check stops after the veto: the stage holds everywhere |
| `quest_sync` | 2-4 | `quest`, `stages` | set_stage, start_quest, stage_done, objective flags | stages and objective flags match on every machine; repeating a stage is a no-op |
| `save_load_rejoin` | 2-4 | `quest`, `stage_a`, `stage_b`, `reward_item?`, `save_name?` | save_game, load_game, session_leave, session_join, rebases | a client leaves, the host moves on, the client rejoins and catches up with each reward once; the host loads the older save and every client rebases; a second rejoin adds nothing |
| `spawn_once` | 2-4 | `marker`, `base` | goto_ref, spawn, ref_count | the host spawns one; exactly one exists on every machine and it stays one |

`far_pos` and `near_pos` are `{"ref": id, "dist": units}` or `{"x": .., "y": .., "z": .., "cell": ..}`. `stages` is
`[[stage, [[objective, "displayed" or "completed", 0 or 1], ...]], ...]`.

A playbook is a class: set `name`, `needs_refs`, `requires`, write `run(ctx)` with `with ctx.step("..."):` blocks, and add
it to `coopbots/registry.py`. The helpers on `ctx` are `must`, `expect`, `on_all` (every machine at the same moment, one
thread each), `same_everywhere`, `wait_until`, `pause`, `settle`, `optional` (run a check that may need an action the adapter
lacks) and `equip_all`.

## What the runner checks after every step

1. **Settle:** every machine reports the host's last update number, stable for two polls, or the step fails and names the
   machines and numbers.
2. **Quiet window** (option `quiesce_s`, for impaired links): nothing is sent for that long, every machine must be converged,
   and then no repair may happen during a second quiet window.
3. **Snapshot compare:** the `shared` part of each client against the host.
4. **Counters:** repairs and mismatches must not rise (unless `strict_counters` is off, see below); bad messages, failed
   applies and rebases must never rise (a step that expects a rebase passes `allow_rebase=True`).
5. **Repair budget** (option `repair_budget_per_min`): repairs per minute over the whole run. Default is none set; with an
   impaired link the default is 0. A budget above 0 in the profiles file needs a `repair_budget_reason` next to it.

On any failure the runner writes `FAIL-<n>-<step>/` with `failure.json` (reason, per machine status, capture, steps so far),
each machine's snapshot, and whatever your `capture()` wrote, plus `result.json` and `snap/` for the whole run.

### Impaired links

`--link bad_wifi` (or `links.link_options("bad_wifi")`) turns strict counters off, adds the quiet window and a budget. It
does not impair the network itself: start the chaos relay in `tools/chaos` between the instances. Profiles: `lan`,
`good_wifi`, `bad_wifi`, `mobile_tether`, `transatlantic`, `hell`. Repairs are never ignored: they are recorded per step, must
stop once the world is quiet, and are budgeted.

## How it is tested

```
python -I tools/bots/run_tests.py
```

Prints `ALL OK` only when every test passes and every twin is caught. Fakes only: no game is started.

* 59 unit tests. Every playbook passes on the fake world with 2, 3 and 4 players and with a laggy link, and on a lossy link.
  A playbook whose adapter lacks an action is skipped, never passed. A playbook with no steps is not a pass. A wrong
  player count or a missing ref is a clear failure. A failed step saves its evidence. The example adapter runs against an
  in-memory console and each of its postconditions is checked with a console that lies. The command line is tested for exit
  codes, `--link`, a run through `--adapter` with refs read from a scenario file.
* 26 playbook twins: a playbook plus one deliberately wrong behaviour of the fake world (a duplicated pickup, a barrier that
  releases early, a tether that is not enforced, a client that never rebases, a stale health echo, ...). Each must make that
  playbook FAIL, and a test checks that every one of the 27 fake bugs has a twin. `counter_noise` (counters that rise) must
  fail all 12 playbooks. A test proves the snapshot comparison alone catches a double spawn that no query asks about.
* Impaired-link tests: every playbook passes on a lossy link; a message lost for good, a repair in the quiet window and repairs over budget each fail; a budget above 0 needs a written reason.
* 4 engine twins: the suite is run again with one check of the runner itself broken (`COOPBOTS_MUTANT`: no settle, no snapshot
  compare, no counter check, skips counted as passes). Each must make a test fail.

## Ported from fnv-coop commit f57aa78

Ported from the Fallout: New Vegas co-op project ([cranebeaker/fnv-coop](https://github.com/cranebeaker/fnv-coop), commit f57aa78),
where these playbooks and the runner were first written against its game bridge. The runner, the playbooks and the fake co-op
world were made game independent (ids are opaque strings, the story and netcode names are generic, the per-game action
layer became the adapter interface). Left in the Fallout project: the questline plan for its opening quests, the
animation and pose checks, and the code that drives the game's own input and engine functions. The Fallout console
adapter in `adapters/fnv/` shows the shape of a first adapter without any of that.
