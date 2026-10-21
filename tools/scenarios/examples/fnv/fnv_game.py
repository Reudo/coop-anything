"""Example GameAdapter for a Gamebryo game with a script console (Fallout: New Vegas), about 100 lines.

It shows the whole job of "write an adapter for your game": turn each scenario op into one console line, turn each
check kind into one expression, and say which ones you cannot do. The scenario ids are editor IDs, which the console
accepts in place of numeric form ids.

The bridge object is yours. It only needs these methods (any in-process bridge to the running game works):

    bridge.exec(line)            -> {"ok": bool, "output": str}   run one console line
    bridge.eval(expr)            -> number                        evaluate one console expression
    bridge.load_save(name)       / bridge.save_game(name)
    bridge.call(method, params)  -> dict                          optional, for project specific methods

The console lines below are the usual command spellings. Check each one against your own bridge before you trust it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gameadapter import GameAdapter, ScenarioError  # noqa: E402

PARSE_ERRORS = ("could not parse", "error line", "unknown", "invalid")


def _who(v):
    return "player" if v == "player" else v


class FnvGame(GameAdapter):
    """One instance of the game, reached through `bridge`."""

    def __init__(self, bridge, with_project_methods=False):
        self.bridge = bridge
        self.project = with_project_methods          # True when the bridge also has call() with dev methods
        ops = {"op:" + o for o in ("move", "spawn", "give", "take", "kill", "revive", "enable", "disable", "lock", "unlock",
                                   "activate", "set_state", "wait", "save", "load")}
        checks = {"check:" + k for k in ("state", "state_reached", "item_count", "dead", "disabled", "locked", "in_area",
                                         "distance", "stat", "follower")}
        self.OPS = ops | checks | ({"check:owner", "check:count"} if with_project_methods else set())

    def _console(self, line):
        r = self.bridge.exec(line)
        out = (r.get("output") or "") if isinstance(r, dict) else ""
        if (isinstance(r, dict) and r.get("ok") is False) or any(p in out.lower() for p in PARSE_ERRORS):
            raise ScenarioError("%s -> %s" % (line, out.strip()[:120] or r))

    def do(self, op, a):
        if op == "set_state":
            self._console("setstage %s %d" % (a["key"], int(a["value"])))
        elif op == "move":
            self._console("%s.moveto %s" % (_who(a["who"]), a["to"]))
        elif op == "spawn":
            self._console("%s.placeatme %s %d" % (_who(a["at"]), a["base"], a.get("count", 1)))
        elif op in ("give", "take"):
            self._console("%s.%s %s %d" % (_who(a["who"]), "additem" if op == "give" else "removeitem", a["item"], a["count"]))
        elif op == "revive":
            self._console("%s.resurrect" % a["ref"])
        elif op in ("kill", "enable", "disable", "unlock"):
            self._console("%s.%s" % (a["ref"], op))
        elif op == "lock":
            self._console("%s.lock %d" % (a["ref"], a["level"]))
        elif op == "activate":
            self._console("%s.activate player 1" % a["ref"])
        else:
            raise ScenarioError("no console line for op %r" % op)

    EXPR = {
        "state": "GetStage {key}",
        "state_reached": "GetStageDone {key} {at}",
        "item_count": "{who}.GetItemCount {item}",
        "dead": "{ref}.GetDead",
        "disabled": "{ref}.GetDisabled",
        "locked": "{ref}.GetLocked",
        "in_area": "{ref}.GetInCell {place}",
        "distance": "{a}.GetDistance {b}",
        "stat": "{ref}.GetAV {stat}",
        "follower": "{ref}.GetPlayerTeammate",
    }

    def read(self, kind, a):
        if kind == "owner":
            return float(self.bridge.call("coop.owner", {"ref": a["ref"]})["owner"])   # project specific method
        if kind == "count":
            return float(self.bridge.call("dev.countRefs", {"base": a["base"]})["count"])
        return float(self.bridge.eval(self.EXPR[kind].format(**a)))

    def load_save(self, name):
        self.bridge.load_save(name)

    def save_game(self, name):
        self.bridge.save_game(name)

    def reset_state(self, ids):
        if self.project:
            self.bridge.call("test.quest.reset", {"quests": list(ids)})
        else:
            for q in ids:
                self._console("setstage %s 0" % q)   # plain fallback: stage 0 (does not clear script variables)
