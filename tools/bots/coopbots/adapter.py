"""The action adapter: the only game specific code a co-op test needs.

One ActionAdapter object drives ONE running game instance (one player's machine). Playbooks call these methods and never
touch the game directly, so the same playbook runs on any game once its adapter exists, and on the fake co-op world in
fakecoop.py without a game.

How to write one for your game
------------------------------
1. Subclass ActionAdapter. Implement only what your game can do. Every method you leave out raises MissingAction, and
   `supports("take")` tells a playbook (and the runner) it is missing, so that playbook is reported SKIP, never PASS.
2. Implement the three engine methods first: `status()`, `snapshot()` and `capture()`. The runner uses them after every step.
3. Actions return a Result (ok, reason, data). Never raise for an ordinary refusal ("door is locked"): return
   Result(False, "door is locked"). Raise only when the game or the link is dead, so the run stops with a clear error.
4. Check the postcondition inside the action: `take` is only ok when the item count really moved. A bot that reports
   success because the call returned is the main source of hollow passes.
5. Ids ("refs") are opaque strings you choose: an editor id, a form id, a path, a name. The playbooks only pass them back.

Reference semantics used by the playbooks
-----------------------------------------
Actions (all return Result)
    goto_ref(ref, dist=150)            walk or teleport to within `dist` of the object
    goto_pos(x, y, z, cell=None)       same for a coordinate
    equip(item)  aim_at(ref)  fire(n=1)
    activate(ref)                      use the object the way a player presses the use key
    open_door(ref)  close_door(ref)  unlock(ref, key=None)
    open_container(ref)  close_container(ref)
    take(item, count, from_ref)  put(item, count, to_ref)
    pickup(ref)                        grab a world item. Fails with "already taken" for the loser of a race
    drop(item, count)                  data["ref"] is the new world object
    talk(npc)  pick_topic(topic)  end_dialogue()
    use_device(ref, entry)             a terminal, lever panel or any menu object
    set_stage(quest, stage)  start_quest(quest)
    barrier_pass(quest)                this player finished its own part of a step that waits for everybody
    answer_prompt(button)              press a button of the open message box (0 = first)
    consent(kind, quest, yes)          answer the party's "ready" or "fast travel" consent prompt
    fast_travel(marker)  spawn(base, at)  save_game(name)  load_game(name)  session_leave()  session_join()
Queries (return values)
    cell()  distance_to(ref)  inventory_count(item, holder=None)  death_count(ref)  target_alive(ref)
    ref_enabled(ref)  in_dialogue()  spectating()  is_locked(ref)  door_open(ref)  device_entry_used(ref, entry)
    quest_stage(quest)  stage_done(quest, stage)  quest_running(quest)  objective_displayed(quest, n)
    objective_completed(quest, n)  owner_of(ref) -> (owner, epoch)  ref_count(base, cell="")
    consent_pending() -> bool  rebases() -> int
Engine
    status() -> {"seq": int, "synced": bool, "counters": {name: int}}   see core.py
    snapshot() -> {"shared": {...}, "per_player": {...}}                see core.py
    capture(directory) -> dict                                          optional: write logs for a failed step
"""
from dataclasses import dataclass, field
from typing import Any, Dict


class MissingAction(NotImplementedError):
    """The adapter does not implement this action. The text says which one."""


@dataclass
class Result:
    ok: bool
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.ok


def _stub(name, doc):
    def f(self, *args, **kwargs):
        raise MissingAction("this adapter does not implement %s" % name)
    f.__name__ = name
    f.__doc__ = doc
    f._not_implemented = True
    return f


ACTIONS = {
    "goto_ref": "goto_ref(ref, dist=150) -> Result",
    "goto_pos": "goto_pos(x, y, z, cell=None) -> Result",
    "equip": "equip(item) -> Result",
    "aim_at": "aim_at(ref) -> Result",
    "fire": "fire(n=1) -> Result; fails when nothing is aimed at",
    "activate": "activate(ref) -> Result",
    "open_door": "open_door(ref) -> Result; fails with a reason when locked",
    "close_door": "close_door(ref) -> Result",
    "unlock": "unlock(ref, key=None) -> Result",
    "open_container": "open_container(ref) -> Result; fails while another player has it open",
    "close_container": "close_container(ref) -> Result",
    "take": "take(item, count, from_ref) -> Result; ok only if the container lost and the player gained `count`",
    "put": "put(item, count, to_ref) -> Result",
    "pickup": "pickup(ref) -> Result; the loser of a race gets ok=False",
    "drop": "drop(item, count) -> Result with data['ref'] = the new world object",
    "talk": "talk(npc) -> Result",
    "pick_topic": "pick_topic(topic) -> Result",
    "end_dialogue": "end_dialogue() -> Result",
    "use_device": "use_device(ref, entry) -> Result",
    "set_stage": "set_stage(quest, stage) -> Result",
    "start_quest": "start_quest(quest) -> Result",
    "barrier_pass": "barrier_pass(quest) -> Result",
    "answer_prompt": "answer_prompt(button) -> Result",
    "consent": "consent(kind, quest='', yes=True) -> Result",
    "fast_travel": "fast_travel(marker) -> Result",
    "spawn": "spawn(base, at) -> Result",
    "save_game": "save_game(name) -> Result",
    "load_game": "load_game(name) -> Result",
    "session_leave": "session_leave() -> Result",
    "session_join": "session_join() -> Result",
}
QUERIES = {
    "cell": "cell() -> str",
    "distance_to": "distance_to(ref) -> float",
    "inventory_count": "inventory_count(item, holder=None) -> int; holder None = this player",
    "death_count": "death_count(ref) -> int",
    "target_alive": "target_alive(ref) -> bool",
    "ref_enabled": "ref_enabled(ref) -> bool",
    "in_dialogue": "in_dialogue() -> bool",
    "spectating": "spectating() -> bool",
    "is_locked": "is_locked(ref) -> bool",
    "door_open": "door_open(ref) -> bool",
    "device_entry_used": "device_entry_used(ref, entry) -> bool",
    "quest_stage": "quest_stage(quest) -> int",
    "stage_done": "stage_done(quest, stage) -> bool",
    "quest_running": "quest_running(quest) -> bool",
    "objective_displayed": "objective_displayed(quest, n) -> bool",
    "objective_completed": "objective_completed(quest, n) -> bool",
    "owner_of": "owner_of(ref) -> (owner slot, epoch)",
    "ref_count": "ref_count(base, cell='') -> int; live objects of that base",
    "consent_pending": "consent_pending() -> bool",
    "rebases": "rebases() -> int; how often this client had to adopt the host's world",
}


ENGINE = {
    "status": "status() -> {'seq': int, 'synced': bool, 'counters': {name: int}}. seq: number of the last host update this "
              "machine applied (the host reports the last one it sent). synced: host only, False while any client is behind. "
              "counters: desync counters, see core.REPAIR_COUNTERS and core.HARD_COUNTERS",
    "snapshot": "snapshot() -> {'shared': {...}, 'per_player': {...}}. `shared` must be equal on every machine once synced",
}


class ActionAdapter:
    """Base class. See the module docstring."""

    name = "bot"

    # status() and snapshot() are stubs too (see ENGINE above); the runner uses them after every step.

    def capture(self, directory):
        """Optional: write logs or dumps for a failed step into `directory`; return a small dict describing them."""
        return {}

    def supports(self, action):
        m = getattr(self, action, None)
        return callable(m) and not getattr(getattr(m, "__func__", m), "_not_implemented", False)


for _n, _d in {**ENGINE, **ACTIONS, **QUERIES}.items():
    setattr(ActionAdapter, _n, _stub(_n, _d))
