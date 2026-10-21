"""In-memory stand-in for 1..N game instances sharing one world (tests and dry runs only; never launches a game).

It models just enough for the shipped example scenarios: state keys, kills, locks, item counts, spawns, positions,
stats, loot pickup, followers, an owner of the world's actors, leave and join, and a few named actions. Flags switch on
deliberate bugs that the scenario checks must catch:

    desync_guest  the guest instance reads zeros for everything (the guest never sees the host's changes)
    double_spawn  every spawn creates two
    dup_loot      a picked up world item can be picked up again
    no_handoff    walking away from the actors does not hand them to the guest

A FakeGame is a GameAdapter, so the same Runner code that drives a real game drives it.
"""
import threading

import scenlib
from gameadapter import GameAdapter, ScenarioError

ALL_CAPS = ({"op:" + o for o in scenlib.OPS if o != "check"} | {"check:" + k for k in scenlib.CHECK_KINDS}
            | {"action:fast_travel", "action:say"})


class Clock:
    """Virtual time: sleeping just advances a number, so tests finish in milliseconds."""

    def __init__(self):
        self.t = 0.0

    def sleep(self, s):
        self.t += s

    def now(self):
        return self.t


class World:
    def __init__(self, **flags):
        self.flags = flags
        self.nplayers = 2
        self.pickups = {}            # id of a world item -> id of the item type it gives
        self.coords = {}             # id -> (x, y) for distance checks; unknown ids get a stable made-up spot
        self.values = {}             # answers for the free `value` check
        self.loads, self.saves, self.calls = [], {}, []
        self.lock = threading.RLock()    # parallel steps run in threads; one action at a time keeps the fake deterministic
        self.reset_world()

    def reset_world(self):
        self.state, self.reached = {}, {}
        self.dead, self.disabled, self.locked, self.taken = set(), set(), {}, set()
        self.items, self.stats, self.team, self.spawned = {}, {}, set(), {}
        self.pos, self.area, self.owner, self.left = {}, {}, 0, set()

    def load_scenario(self, sc):
        """Learn which world objects hand out an item when activated (objects with a `base`)."""
        for o in (sc.get("objects") or {}).values():
            if o.get("base"):
                self.pickups[str(o["id"])] = str(o["base"])
        far = (scenlib.playbook_refs(sc).get("far_pos") or {}).get("ref")   # convention: walking the host there hands the actors to the guest
        if far:
            self.flags.setdefault("handoff_place", far)

    def where(self, key):
        if key not in self.pos:
            self.pos[key] = self.coords.get(key, (sum(map(ord, key)) * 37 % 9000 + 2000, 0))
        return self.pos[key]


class FakeGame(GameAdapter):
    def __init__(self, world, i, clock, lacks=()):
        self.w, self.i, self.clock = world, i, clock
        self.OPS = ALL_CAPS - set(lacks)

    # -- helpers
    def _log(self, kind, text):
        self.w.calls.append((self.i, kind, text))

    def _key(self, who):
        return "player%d" % self.i if who == "player" else who

    def _blind(self):
        return bool(self.w.flags.get("desync_guest")) and self.i == 1

    # -- adapter surface
    def do(self, op, args):
        with self.w.lock:
            self._do(op, args)

    def _do(self, op, args):
        w, i = self.w, self.i
        self._log("do", "%s %r" % (op, args))
        if op == "set_state":
            w.state[args["key"]] = args["value"]
            w.reached.setdefault(args["key"], set()).add(args["value"])
        elif op == "move":
            who, to = self._key(args["who"]), args["to"]
            w.pos[who] = w.where(to)
            w.area[who] = to
            if args["who"] == "player" and i == 0 and w.flags.get("handoff_place") == to and not w.flags.get("no_handoff"):
                w.owner = 1
        elif op == "spawn":
            n = args.get("count", 1) * (2 if w.flags.get("double_spawn") else 1)
            k = (args["at"], args["base"])
            w.spawned[k] = w.spawned.get(k, 0) + n
        elif op in ("give", "take"):
            k = (self._key(args["who"]), args["item"])
            delta = args["count"] if op == "give" else -args["count"]
            w.items[k] = max(0, w.items.get(k, 0) + delta)
        elif op == "kill":
            w.dead.add(args["ref"])
        elif op == "revive":
            w.dead.discard(args["ref"])
        elif op == "enable":
            w.disabled.discard(args["ref"])
        elif op == "disable":
            w.disabled.add(args["ref"])
        elif op == "lock":
            w.locked[args["ref"]] = args["level"]
        elif op == "unlock":
            w.locked.pop(args["ref"], None)
        elif op == "activate":
            ref = args["ref"]
            if ref in w.pickups and (ref not in w.taken or w.flags.get("dup_loot")):
                w.taken.add(ref)
                k = ("player%d" % i, w.pickups[ref])
                w.items[k] = w.items.get(k, 0) + 1
        elif op == "leave":
            w.left.add(i)
        elif op == "join":
            w.left.discard(i)
        elif op == "action":
            name, a = args["name"], args.get("args") or {}
            if name == "fast_travel":
                for p in range(w.nplayers):
                    w.pos["player%d" % p] = w.where(a["marker"])
                    w.area["player%d" % p] = a["marker"]
            elif name == "say":
                w.state[a["quest"]] = a.get("sets", 25)
                w.reached.setdefault(a["quest"], set()).add(a.get("sets", 25))
            else:
                raise ScenarioError("fake game has no action %r" % name)
        else:
            raise ScenarioError("fake game cannot do op %r" % op)

    def read(self, kind, args):
        w = self.w
        self._log("read", kind)
        if self._blind():
            return 0.0
        if kind == "state":
            return float(w.state.get(args["key"], 0))
        if kind == "state_reached":
            return float(args["at"] in w.reached.get(args["key"], set()))
        if kind == "item_count":
            return float(w.items.get((self._key(args["who"]), args["item"]), 0))
        if kind == "dead":
            return float(args["ref"] in w.dead)
        if kind == "disabled":
            return float(args["ref"] in w.disabled)
        if kind == "locked":
            return float(w.locked.get(args["ref"], 0) > 0)
        if kind == "in_area":
            return float(w.area.get(self._key(args["ref"])) == args["place"])
        if kind == "distance":
            a, b = w.where(self._key(args["a"])), w.where(self._key(args["b"]))
            return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
        if kind == "stat":
            return float(w.stats.get((args["ref"], args["stat"]), 200.0))
        if kind == "follower":
            return float(args["ref"] in w.team)
        if kind == "count":
            return float(sum(n for (_, b), n in w.spawned.items() if b == args["base"]))
        if kind == "owner":
            return float(w.owner)
        if kind == "value":
            return float(w.values.get(args["query"], 0))
        raise ScenarioError("fake game cannot read %r" % kind)

    def reset_state(self, ids):
        self._log("reset", ",".join(ids))
        for q in ids:
            self.w.state.pop(q, None)
            self.w.reached.pop(q, None)

    def load_save(self, name):
        self._log("load", name)
        self.w.loads.append((self.i, name))
        self.w.reset_world()
        snap = self.w.saves.get(name)
        if snap:
            self.w.state, self.w.reached = dict(snap[0]), {k: set(v) for k, v in snap[1].items()}

    def save_game(self, name):
        self._log("save", name)
        self.w.saves[name] = (dict(self.w.state), {k: set(v) for k, v in self.w.reached.items()})


def make(n=2, lacks=(), **flags):
    w = World(**flags)
    clock = Clock()
    return w, clock, [FakeGame(w, i, clock, lacks) for i in range(n)]
