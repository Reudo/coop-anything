"""The game side of the scenario runner: one GameAdapter per running game instance (one per player).

Write one class for your game and the runner does the rest. The runner never talks to the game directly. It gives each
adapter plain strings: ids taken from the scenario's `objects` glossary and the numbers and names written in the steps.

    class MyGame(GameAdapter):
        OPS = {"op:kill", "op:move", "check:dead", "check:state", "action:fast_travel"}

        def do(self, op, args):              # args: {"ref": "<id>"} for op "kill"
            ...
        def read(self, kind, args):          # kind "dead", args {"ref": "<id>"} -> 0 or 1
            ...
        def load_save(self, name): ...
        def save_game(self, name): ...
        def reset_state(self, ids): ...      # put these state keys back to their starting value, no reload

Anything the adapter cannot do is simply left out of OPS. A step that needs it is reported `blocked`, never `pass`.
"""


class ScenarioError(Exception):
    """An action was refused or failed. The runner records it as an `error` step with this text."""


class GameAdapter:
    OPS = None   # None = "I can do everything"; otherwise a set of 'op:<op>', 'check:<kind>' and 'action:<name>' names

    def capabilities(self):
        return None if self.OPS is None else set(self.OPS)

    def do(self, op, args):
        """Run one non-check op on this instance. `op` is one of scenlib.OPS (not `wait`, `save`, `load`).
        Raise ScenarioError when the game refuses or the result is not what was asked for."""
        raise NotImplementedError("do(%r)" % op)

    def read(self, kind, args):
        """Answer one check kind (see scenlib.CHECK_KINDS) as a number. Booleans are 1 and 0."""
        raise NotImplementedError("read(%r)" % kind)

    def load_save(self, name):
        raise NotImplementedError("load_save")

    def save_game(self, name):
        raise NotImplementedError("save_game")

    def reset_state(self, ids):
        """Put the named state keys (quests, flags, script variables) back to their starting value without a reload."""
        raise NotImplementedError("reset_state")
