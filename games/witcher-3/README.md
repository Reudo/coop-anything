# The Witcher 3: Wild Hunt (2015)

| | |
|---|---|
| Engine | REDengine 3 (WitcherScript source + closed native exe) |
| Versions tested | Steam, Remastered patch 5.01 (exe 5.0.0.1048522, build 25773555, DX12 only) |
| Projects | Witcher Online, W3Coop (its 5.01 port), WitcherMMO, w3m, Witcher3-Multiplayer, Witcher3-MP ([directory](../../DIRECTORY.md)) |
| QA level | W3Coop (Witcher Online on 5.01): automated (2 tests, see QA). Other projects on 5.x: none |
| Last updated | 2026-10-18 |

## Where things stand

Witcher Online is the only usable project: players see each other, chat, ride together and share
dialog choices in a party, but enemies, NPCs and quests are not shared. It supports 4.04 only; the
Remastered update (5.0, September 2026) breaks its public build. W3Coop, a port to 5.01 with a Steam
relay (pre-release v0.1.0), compiles and passes two automated two-client tests (players visible,
movement); it is not yet tested between two real Steam accounts. Story co-op with shared enemies and
quests does not exist for any version yet.

## Existing work

- [Witcher Online](https://github.com/rejuvenate7/WitcherOnline) (rejuvenate7, GPL-3.0, last push
  2026-08): WitcherScript mod + native client ASI (via
  [WitcherNativeBridge](https://github.com/rejuvenate7/WitcherNativeBridge), MIT, updated for 5.01 on
  2026-10-08) + Java UDP server. Requires Custom Player Characters, Chill Out and Shared Imports
  (Nexus only, no public source).
- [W3Coop](https://github.com/Emillock/witcher3-coop): Witcher Online ported to 5.01
  ([fork, branch `remastered-5.01`](https://github.com/Emillock/WitcherOnline/tree/remastered-5.01)),
  plus a Steam relay, a player package and the test harness described below. Built in this playbook's
  workflow.
- [WitcherMMO](https://github.com/eofim/WitcherMMO): a rename fork of Witcher Online; its NPC/quest
  goals are not implemented.
- [w3m](https://github.com/momo5502/w3m) (momo5502): native hooks at hardcoded addresses of a
  pre-remaster exe; own launcher and server.
- [Witcher3-Multiplayer](https://github.com/werasik2aa/Witcher3-Multiplayer) (discontinued
  2026-01) and [Witcher3-MP](https://github.com/Hyjarion/Witcher3-MP) (one upload, 2023).

## How the game works (for co-op)

- **No netcode.** Every multiplayer attempt adds its own transport; Witcher Online uses a separate
  UDP server and spawns "ghost" NPCs from its own DLC entity templates for remote players.
- **Script source ships** in `content\content0\scripts` (1525 `.ws` files; UTF-8 in 5.x). Mods
  live in `<game dir>\mods\<mod>\content\scripts` and are compiled at startup together with vanilla.
  Annotations `@wrapMethod`, `@addMethod`, `@addField`, `@replaceMethod` avoid full-file overrides.
  In 5.x, `@addMethod(Class) import function X(...)` exposes an undeclared native method, and the
  preprocessor (`#ifdef`/`#ifndef`/`#else`/`#endif`, `-scriptdefines=`) works, also inside function
  bodies.
- **Natives from C++**: WitcherNativeBridge (loaded as an `.asi` by Ultimate ASI Loader as
  `bin\x64_dx12\dinput8.dll`) lets other ASI plugins register script natives. Script strings and
  CNames are UTF-8 bytes in 5.x (UTF-16 in 4.x).
- **Compile check**: `witcher3.exe -verifyscriptsandexit` compiles and exits; errors appear in the
  "Script Compilation Errors" window (read its Edit control with `WM_GETTEXT`). Errors from mod files
  print without the `[content0]` prefix.
- **5.0 API changes that break 4.04 mods**: `map` is a keyword; areas are CNames
  (`GetCurrentArea() : name`, `GetDeprecatedAreaName(int)`, no `AreaTypeToName`); Gwent card data
  moved to natives keyed by card name (`GetGwentCard`, `GetDeck`, no `cardIndices`);
  `CInputManager.IgnoreGameInput` is now native; `.w3strings` v164 and `metadata.store` v7 (4.04 v6
  DLC bundles still load).
- **Mods from Steam Workshop load automatically** from `steamapps\workshop\content\292030`; one
  4.04-era workshop mod breaks compilation for every launch. `Documents\The Witcher 3\mods.settings`
  with `[modName] Enabled=0` disables a single mod and is honored by the compiler.
- **User data**: `Documents\The Witcher 3` (`dx12user.settings` only in 5.x, `gamesaves\`,
  `mods.settings`). 4.04 saves load in 5.01 and show a one-time "skill points reset" dialog.
- **Single instance**: named mutex `cdprojekt_red_the_witcher_3_wild_hunt` (CreateMutexA); the second
  copy shows "game is already launched" and exits.

## What the 5.01 port changes

- Client: read and write script strings as UTF-8 on 5.x (UTF-16 on 4.x), optional
  `WO_USERNAME`/`WO_SERVER_IP`/`WO_SERVER_PORT` overrides for several instances on one install.
- Scripts: rename `map` variables; `import` the native `IgnoreGameInput`; area handling on CNames
  with the old numeric codes kept on the wire (server and protocol unchanged).
- Gwent duels fenced off with `#ifdef WO_GWENT_PVP`: they need a new Gwent board for 5.x (the mod's
  4.04 `gwint_game.redswf` would replace the remaster's Gwent UI, so it is not installed).
- Custom Player Characters and Chill Out replaced by stand-in declarations.

## QA

Harness: a local server plus two game clients on one PC. Each client runs in its own Documents
sandbox (settings copies + one save copy), with the game's own "low" preset, RT off, a 30 FPS cap,
muted audio, and in-process hooks so test windows keep running unfocused without capturing the mouse,
focus or keyboard. An in-game bot (script mod + a test ASI providing `W3T_GetEnv`, `W3T_Log`,
`W3T_Quit`) skips the movies, closes the account prompt without answering consent questions,
answers system dialogs, loads the save and reports once per second; the harness requires every
bot's PASS line.

| Test | What it asserts | Result (2026-10-18) |
|---|---|---|
| `see_each_other` | each client spawns the other player's ghost at the networked position | PASS (2 clients) |
| `movement` | one player teleports back and forth; the other's copy of the ghost lands within 2 m of the networked position after each move | PASS (2 clients, 4 moves seen) |
| `movement --relay` | same, with the second client connected only through the Steam relay (host + join relay over a mock `steam_api64.dll`) | PASS (2 clients, also against the built player package) |
| relay self-test | 20 UDP packets through host and join relays, game client starting 25 s late; a Steam user outside the lobby must not reach the server | PASS |

Steam relay ("w3relay", the HXCoop pattern from
[networking-steam-spacewar.md](../../playbook/networking-steam-spacewar.md)): a helper exe runs as
Spacewar (AppID 480), creates a friends-only lobby and carries Witcher Online's UDP packets over
Steam, so nobody types an IP or forwards ports. It loads the game's own `steam_api64.dll`. A real-Steam
smoke test (init, lobby create, clean exit) passed; a join between two real Steam accounts is not
tested yet.

## How to play

Download `W3Coop-0.1.0.zip` from the
[W3Coop releases](https://github.com/Emillock/witcher3-coop/releases) and copy its contents into the
game folder. The host runs `bin\w3coop\Host co-op.cmd` (needs Java 21+) and invites friends; friends run
`Join co-op.cmd`; then everyone starts the game and loads a save. It is a pre-release: the join
between two real Steam accounts is not tested yet.

## Known issues

- Gwent duels are off in the 5.x port.
- Character customization and tavern sitting (from the two dependency mods) are stand-ins.
- Two instances of the remaster need about 4 GB VRAM and 10 GB RAM each; with other apps holding
  most of a 12 GB card they slow to a few FPS.

## Next steps

- A real two-account test of the relay; more bot tests (chat, emotes, party sync).
- A 5.x Gwent board for duels.
- Shared enemies (host authority over NPC state, damage forwarded to the host) and quest progress
  (facts sync): not started anywhere.
