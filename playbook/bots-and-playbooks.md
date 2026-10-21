# Bots and playbooks: scripted co-op runs with a state check after every step

[Automated QA](automated-qa.md) says what a test must prove. This page is the reusable
machinery for it: JSON **scenarios** that put every game instance into a known starting
state, **playbooks** that drive 2 to 4 bots through a co-op action, and a small **adapter**
you write for your game. The code is in [`tools/scenarios`](../tools/scenarios/README.md)
and [`tools/bots`](../tools/bots/README.md). Both run without a game first (on a fake
co-op world), so you can see them pass and see them catch bugs before you wire in your game.

## The three layers

```
scenario   JSON: start save, objects, setup, steps and checks      tools/scenarios
playbook   Python: what 2 to 4 bots do, what must be equal after    tools/bots/coopbots/playbooks
           every step
adapter    Python, one class per game: how one instance does it    your game (example: tools/bots/adapters/fnv)
```

* The **scenario** answers "where does the test start". The runner reloads the save only when
  it has to and otherwise resets quests and flags in place, so a start costs seconds, not a
  save load.
* The **playbook** answers "what do the players do, and what must be true everywhere". It
  never touches the game. It calls adapter methods such as `pickup`, `take`, `set_stage`.
* The **adapter** answers "how does my game do that". A first one is under 150 lines. Methods you
  leave out make the playbooks that need them report `SKIP`, never `PASS`.

## What gets checked after every step

The runner, not the playbook author, does the boring part every time:

1. **Settle.** Wait until every client reports the host's last update number. No fixed sleeps.
2. **Quiet window** (impaired links). Nothing is sent for a few seconds, every machine must be converged, and no repair may happen.
3. **Snapshot compare.** The shared state of the host against each client, path by path.
4. **Desync counters** must not rise: mismatches, repairs, bad messages, failed applies, forced rebases.
5. **Repairs per minute** stay inside a budget (zero by default).
6. On any failure: a `FAIL-<n>-<step>/` folder with the reason, each machine's status and snapshot, and whatever your adapter captures (logs, event trace), so the first divergence can be found afterwards.

This is what makes a playbook better than an assert at the end: a bug is caught at the step that caused it, and a run that
"looked fine" but left machines different still fails.

## Which bug class each playbook catches

| Playbook | The bug it is there for |
|---|---|
| `fight` | a kill that never reaches another machine; a second death counted when two players shoot at once; a dead enemy revived by a stale update; duplicate enemies |
| `loot_race` | two players both get the item; the item vanishes for everyone |
| `container_share` | two players inside one container; a take or put that is duplicated or lost; contents differing between machines |
| `door_lock` | a door, lock or terminal state that one machine never sees; opening a locked door |
| `dialogue_spectator` | a second speaker with the same NPC; a spectator left stuck in the view; the end script running on one machine only |
| `consent_vote` | a one-way step firing when the first player passes instead of the last; a "not yet" that does not stop it; firing twice |
| `quest_sync` | quest stages or objective flags that one side never applies; a repeated stage moving the quest |
| `fast_travel_tether` | travel without consent or in combat; a tethered player wandering off |
| `ownership_handoff` | control of an enemy not moving when the host leaves; control flapping back and forth; duplicates after the handoff |
| `save_load_rejoin` | a rejoining player receiving every reward again; a client not following when the host loads an older save |
| `spawn_once` | a spawn that exists twice on a client |

## Getting from nothing to a green run

1. **Run the fakes.** `python -I tools/bots/run_coop.py --fake --playbook all`, then add `--bug dup_pickup` to one playbook and see it fail. Read `coopbots/fakecoop.py`: it is a working adapter and a statement of the rules each playbook assumes (host is authoritative, first pickup wins, barriers wait for every player).
2. **Write the engine surface of the adapter:** `status()`, `snapshot()`, `capture()`. Any sequence number or state hash that is equal on all machines when nothing is in flight will do for `seq`. Put only shared state in `snapshot()["shared"]`.
3. **Add actions one at a time, in the order a playbook needs them.** Start with `quest_sync` (stage set and read), then `loot_race`, then `fight`. After each one run the playbook: `FAIL` shows what the game did, `SKIP` shows what is still missing.
4. **Check the postcondition in every action.** `take` is ok only when both inventories moved by the same count. A bot that reports success because the call returned is how hollow passes happen.
5. **Write scenarios for your game** (copy a file from `tools/scenarios/examples/fnv`) with a `refs` block so the same file feeds the scenario runner and the playbook.
6. **Turn on impaired links** (`--link bad_wifi`) with the chaos relay in [`tools/chaos`](../tools/chaos) between the instances, once the clean run is green.
7. **Prove the tests can fail.** Add a deliberate bug to your mod (turn one sync message off) and confirm the right playbook goes red. The fake world's `--bug` switches are the model for this.

## Rules that kept the results honest

- **A skip is not a pass.** The runner exits non-zero when nothing passed, and prints `SKIP` with the missing action.
- **A scenario step the adapter cannot do is `blocked`,** and so is every step after it. The scenario ends `partial`, never `pass`.
- **Compare per machine.** A check runs on every player it targets. A bug that shows only on the guest is the point.
- **Races use `parallel`.** `"parallel": true` runs a step on all players at the same moment, one thread each.
- **Every playbook has twins.** A twin is the same playbook against a world with one deliberately wrong behaviour. If a twin passes, the playbook was testing nothing. The tools ship 26 playbook twins, 5 scenario twins and 4 runner twins, and their test commands print `ALL OK` only when every twin is caught.
- **No fake input.** The bot calls the game's scripting or code, the way a player's action would arrive. No simulated keyboard or mouse, no desktop capture, see [automated QA](automated-qa.md).
- **Own the game processes you start,** and stop only those. Run test-heavy instances one session at a time on a normal PC ([multi-agent workflows](multi-agent-workflows.md)).

## Example: the Fallout: New Vegas port

[fnv-coop](https://github.com/cranebeaker/fnv-coop) is where these were written. `tools/scenarios/examples/fnv` has four of its scenarios
(`fight`, `loot_race`, `quest_stage_sync`, `ownership_handoff`) and a console adapter; `tools/bots/adapters/fnv` has the matching
action adapter. They are examples of the shape, not a claim that the game is solved: what an adapter implements is what its
`SKIP` list does not mention.

## What to write in your game's QA section

- Which playbooks ran, on how many players, and the summary lines (`PASS` and `SKIP` count).
- The adapter's `SKIP` list: the actions your game still lacks.
- Whether a lossy link run (`--link`) passed, and which profile.
- The suite commands and their last output.
