---
name: coop-contribute
description: Send what you learned back to coop-anything: update the directory, write up the game, improve the playbook, and open a draft pull request after the owner reviews the diff.
---

# Contribute back

1. Fork, branch `game/<slug>`.
2. Directory: edit `data/directory.yaml`, run `python tools/build_directory.py`.
3. Write-up: `games/<slug>/README.md` from `templates/game.md`, with the QA level and what works (no "not yet proven" lists; open items go in issues).
4. Playbook: fix or extend the page whose advice was wrong or missing.
5. Scrub: no personal info, no tokens, no game files or assets. Decomp-based code is welcome; put a game's full code in its own repo and link it.
6. Show the owner the diff, then `gh pr create --draft` with the template filled in.

Details: `AGENTS.md`, `CONTRIBUTING.md`.
