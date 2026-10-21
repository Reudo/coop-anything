"""Example ActionAdapter for a Gamebryo game with a script console (Fallout: New Vegas). Small on purpose.

It shows how little a first adapter needs: a handful of console lines, a postcondition check after each action, and a
status mapping. Everything it does not implement is left out, so the playbooks that need it are skipped and reported.

The bridge is yours. It only needs:

    bridge.exec(line)            -> {"ok": bool, "output": str}   run one console line in the game
    bridge.eval(expr)            -> number                        evaluate one console expression
    bridge.call(method, params)  -> dict                          the co-op mod's own status and state dump

Ids are editor ids or hex ids the console accepts. There is no engine address in here, only console commands. Check each
console spelling against your own build before you trust it.
"""
import json
import os
from typing import Dict

from coopbots.adapter import ActionAdapter, Result

PARSE_ERRORS = ("could not parse", "error line", "unknown", "invalid")


class FnvBot(ActionAdapter):
    def __init__(self, bridge, name="bot"):
        self.b = bridge
        self.name = name

    # ---- plumbing ----
    def _run(self, line) -> Result:
        r = self.b.exec(line)
        out = (r.get("output") or "") if isinstance(r, dict) else ""
        if (isinstance(r, dict) and r.get("ok") is False) or any(p in out.lower() for p in PARSE_ERRORS):
            return Result(False, "%s -> %s" % (line, out.strip()[:100] or "refused"))
        return Result(True)

    def _num(self, expr) -> float:
        return float(self.b.eval(expr))

    @staticmethod
    def _who(holder):
        return "player" if holder is None else holder

    # ---- engine surface: map the co-op mod's status onto the runner's counters ----
    COUNTER_PATHS = {                       # runner counter -> path in the mod's status reply
        "mismatches": ("desyncs", "digests", "mismatch"), "repairs": ("desyncs", "digests", "repairs"),
        "repaired_effects": ("desyncs", "digests", "effectsRepaired"), "bad_messages": ("host", "badMessages"),
        "apply_failures": ("counters", "applyFailed"), "rebases": ("client", "rebases"),
    }

    def status(self):
        st = self.b.call("coop.status", {})
        counters: Dict[str, int] = {}
        for k, path in self.COUNTER_PATHS.items():
            v = st
            for p in path:
                v = v.get(p) if isinstance(v, dict) else None
            counters[k] = int(v or 0)
        return {"seq": int(st.get("lastSeq", 0) or 0), "synced": bool((st.get("host") or {}).get("allSynced", True)), "counters": counters}

    def snapshot(self):
        return self.b.call("state", {})      # must return {"shared": {...}, "per_player": {...}}

    def capture(self, directory):
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "events.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.b.call("events", {"since": 0}), f, indent=1)
        return {"events": path}

    # ---- actions ----
    def goto_ref(self, ref, dist=150):
        r = self._run("player.moveto %s" % ref)
        if not r:
            return r
        d = self._num("player.GetDistance %s" % ref)
        return Result(d <= max(dist, 250), "" if d <= max(dist, 250) else "still %.0f units from %s after moveto" % (d, ref), {"distance": d})

    def activate(self, ref):
        return self._run("%s.activate player 1" % ref)

    def pickup(self, ref):
        if self._num("%s.GetDisabled" % ref):
            return Result(False, "already taken")
        r = self.activate(ref)
        if not r:
            return r
        gone = bool(self._num("%s.GetDisabled" % ref))
        return Result(gone, "" if gone else "the object is still in the world after activating it")

    def take(self, item, count, from_ref):
        return self._transfer(item, count, src=from_ref, dst=None)

    def put(self, item, count, to_ref):
        return self._transfer(item, count, src=None, dst=to_ref)

    def _transfer(self, item, count, src, dst) -> Result:
        """Move items between the player and a container; ok only when BOTH counts moved (catches duplication and loss)."""
        s, d = self._who(src), self._who(dst)
        s0, d0 = self.inventory_count(item, src), self.inventory_count(item, dst)
        r = self._run("%s.RemoveItemTarget %s %s %d 1" % (s, item, d, count))
        if not r:
            return r
        s1, d1 = self.inventory_count(item, src), self.inventory_count(item, dst)
        if (s0 - s1, d1 - d0) != (count, count):
            return Result(False, "transfer of %d x %s moved %d out and %d in" % (count, item, s0 - s1, d1 - d0))
        return Result(True)

    def set_stage(self, quest, stage):
        return self._run("setstage %s %d" % (quest, stage))

    def unlock(self, ref, key=None):
        r = self._run("%s.unlock" % ref)
        return r if not r else Result(not self.is_locked(ref), "still locked after unlock")

    # ---- queries ----
    def inventory_count(self, item, holder=None):
        return int(self._num("%s.GetItemCount %s" % (self._who(holder), item)))

    def target_alive(self, ref):
        return not self._num("%s.GetDead" % ref) and not self._num("%s.GetDisabled" % ref)

    def ref_enabled(self, ref):
        return not self._num("%s.GetDisabled" % ref)

    def is_locked(self, ref):
        return bool(self._num("%s.GetLocked" % ref))

    def door_open(self, ref):
        return self._num("%s.GetOpenState" % ref) == 1

    def distance_to(self, ref):
        return self._num("player.GetDistance %s" % ref)

    def quest_stage(self, quest):
        return int(self._num("GetStage %s" % quest))

    def stage_done(self, quest, stage):
        return bool(self._num("GetStageDone %s %d" % (quest, stage)))
