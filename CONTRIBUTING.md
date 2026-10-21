# Contributing

Humans and agents follow the same flow. Agents: [AGENTS.md](AGENTS.md) has the full
rules; this page is the short version.

1. **Fork** and branch `game/<game-slug>` (or `directory/<what>` for directory-only fixes).
2. **Directory:** edit `data/directory.yaml` (schema: [data/SCHEMA.md](data/SCHEMA.md)),
   then run `python tools/build_directory.py` and commit the regenerated `DIRECTORY.md`.
   Every entry needs a source link and a `checked` date.
3. **Write-ups:** `games/<game-slug>/README.md` from [templates/game.md](templates/game.md).
   Keep raw notes in `games/<game-slug>/NOTES.md` if they help the next person.
4. **Playbook:** fix or extend a page in `playbook/` when a technique was missing or
   wrong, and say which game taught you.
5. **Open the PR** with the template filled in. One game per PR.

Please don't:

- add game files or assets (art, audio, ROMs, game data) or download links to them;
- commit a whole game's code here: decomp-based work is welcome, but it lives in the game's own repo, linked from here;
- paste personal info (names, emails, usernames in paths, tokens, private chat logs);
- claim a QA level you didn't reach. `unknown` and `untested` are fine answers.

Starting a game nobody covers? Open a **"claim a game"** issue first so people can find
each other. Spotted a co-op mod we don't list? The **"new co-op project"** issue form is
enough; someone's agent will turn it into an entry.
