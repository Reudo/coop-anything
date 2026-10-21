# The Witcher 3: Wild Hunt: agent notes

Raw notes, newest phase last. Paths use `<game dir>`.

## Session 2026-10-18: triage and research (phases 0 and 1)

### Game identity (tested build)

| | |
|---|---|
| Store | Steam, app 292030, buildid 25773555 |
| Edition | "The Witcher 3: Wild Hunt — Remastered" (patch 5.0 line, released 2026-09-29) |
| Exe | `<game dir>\bin\x64_dx12\witcher3.exe`, FileVersion 5.0.0.1048522, PE timestamp 2026-10-06 |
| Exe SHA-256 | `2df765398a3d1f165db418271be7200178320a4466817379f2fa0dc0001fb101` |
| Engine | REDengine 3 |
| OS | Windows 11 (10.0.26200) |

### Observations (checked directly)

- 5.x ships DX12 only (`bin\x64_dx12`), no `bin\x64`. DLC content is merged into
  `content\content0` (63 GB, 31 bundles) with empty `dlc-tombstones\<dlc>\*.tombstone` markers.
- Script source still ships: 1525 `.ws` files in `content\content0\scripts`, now UTF-8
  (4.04 mods ship UTF-16LE), plus `cookedfinal.redscripts`.
- Format versions changed versus 4.04-era mod files: `.w3strings` header 0xA4 (164) vs 0xA2 (162);
  `metadata.store` VTM version 7 vs 6. Bundles are still `POTATO70`.
- Gwent natives changed in 5.0: vanilla `gwintManager.ws` declares `SDynamicCard`,
  `SGwintCardNameProperty`, `GetGwentCard`, `GetDeck`, `GetDynamicCards`; the 5.01 exe contains no
  `cardIndices`, `leaderIndex` or `dynamicCardRequirements` strings.
- **Witcher Online** (rejuvenate7, GPL-3.0, GitHub HEAD `4755ee7`, 2026-08-29), static checks
  against this build:
  - 71 of 76 script annotations (`@wrapMethod`/`@addMethod`/`@addField`) match 5.01 vanilla
    classes and signatures. Of the rest, 3 are checker false positives (whitespace in generics; two
    methods the mod adds in its own `gwintGameMenu.ws`) and 2 target dependency mods (`ChillOut`,
    `NR_PlayerManager` from Custom Player Characters), not checked.
  - Full-file overrides `game/gui/menus/gwintManager.ws` and `gwintGameMenu.ws` are 4.04-based.
    They declare `import struct CollectionCard` and `import var cardIndices/leaderIndex/
    dynamicCardRequirements` (gone in 5.01) and drop `GetGwentCard`, `GetDeck`,
    `GetDynamicCards`, `IsKingCard` and others that 8 other 5.01 vanilla scripts call
    (`playerWitcher.ws`, `r4Player.ws`, `quest_function.ws`, `deckBuilderMenu.ws`, ...).
  - Client `.asi` has no hooks of its own; it registers script natives through
    WitcherNativeBridge and only rejects a bridge API older than its own (built for v1, bridge is v2).
  - Ships `.w3strings` v162 and `metadata.store` v6 files.
  - Wiki says 4.04 is required and needs `-net -debugscripts`, Shared Imports, Custom Player
    Characters and Chill Out. Server is Java, UDP 40000, official public server or self-host with
    port forwarding.
- **WitcherNativeBridge** (rejuvenate7 and Flawkee, MIT, `415e1c1`, 2026-10-08 "update for 5.01
  remastered"): offline replay of its binding logic on this exe: 279 registration sites, all 7
  resolved helpers agree 279/279, `registerGlobal` prologue matches, the 5.01 LogChannel string
  pattern matches once and the 5.00 one zero times. Done with a small Python script that parses
  the PE sections and repeats the bridge's pattern scan on the file (read-only, nothing executed);
  not committed yet.
- **WitcherMMO** (eofim): one commit on top of Witcher Online (2026-10-02) that renames the project.
- **werasik2aa/Witcher3-Multiplayer** (AGPL-3.0): last commit 2026-01-15 "DS DISCONTINUED";
  README claims position/rotation sync, fight sync "10%", NPC sync "30% buggy". Credited by
  Witcher Online.
- **momo5502/w3m** (GPL-3.0, C++): native hooks at hardcoded absolute addresses (for example
  `0x14027E700`), own launcher, updater and server; last code commit 2026-01-01. Pre-remaster.
- **Hyjarion/Witcher3-MP** (AGPL-3.0): single upload 2023-05-29, release v0.0.1.

### Derived (reasoned from the above, not run)

- This exe is patch 5.01 (built 2026-10-06; 5.01 shipped 2026-10-08; the bridge's 5.01-only
  pattern matches).
- The public Witcher Online build cannot compile its scripts on 5.0/5.01 because of the two Gwent
  overrides. The fix is to rebase those overrides on the 5.01 Gwent API (card names instead of
  indices) or replace them with annotations.
- WitcherNativeBridge 5.01 should bind on this exe (every check the bridge makes before hooking
  passes offline), except the opcode table, which is filled at runtime.

### Guesses (unverified)

- The author is porting Witcher Online to the remaster (bridge updated 2026-10-06/08 with
  a "Remastered" release); a 5.x Witcher Online build may already be on Nexus or Discord.
- The UTF-16 mod scripts, v162 `.w3strings` and v6 `metadata.store` may need re-encoding or
  repacking for 5.x.
- Steam keeps "Patch 4.04" (Next-Gen) and "Patch 1.32" (Classic) beta branches next to the
  remaster (web search results only; not checked in the Steam client).

### Unknowns

- Whether a remaster build of Witcher Online exists on Nexus (Nexus returns 403 to fetches;
  Discord not checked).
- Remaster status of Chill Out and Community Patch Shared Imports. Custom Player Characters has a
  5.01 compatibility fix (Nexus 13735).
- Whether `-net -debugscripts` and the scriptslog channel still behave the same on 5.x.
- Whether 5.x saves load on the Steam "Patch 4.04" branch.
- Whether two game instances can run on one PC (single-instance locks, Steam launch).

### Searched

coop-anything directory, `games/`, issues and PRs (unauthenticated API, "witcher", "redengine":
0 hits); GitHub repos above plus their commits, releases and issues; web search (patch 5.0/5.01
notes, Witcher Online remaster status, Steam 4.04 branch, Script Merger and ASI loader on 5.x);
Witcher Online GitBook wiki. Not checked: Nexus pages directly (403), Discord, Reddit, YouTube.

### Sources

- https://github.com/rejuvenate7/WitcherOnline
- https://github.com/rejuvenate7/WitcherNativeBridge
- https://rejuvenate.gitbook.io/witcheronline/guides/getting-started
- https://rejuvenate.gitbook.io/witcheronline/guides/client-setup/required-mods
- https://rejuvenate.gitbook.io/witcheronline/guides/server-setup
- https://rejuvenate.gitbook.io/witcheronline/general-information/playguide
- https://github.com/eofim/WitcherMMO
- https://github.com/werasik2aa/Witcher3-Multiplayer
- https://github.com/momo5502/w3m
- https://github.com/Hyjarion/Witcher3-MP
- https://witcher.fandom.com/wiki/Patch_5.0_(The_Witcher_3)
- https://gamerant.com/the-witcher-3-remastered-patch-50-notes/
- https://gamersuniverse.eu/en/roll-back-witcher-3-remastered-old-version
- https://www.nexusmods.com/witcher3/mods/13076 (Script Merger - Remastered: 5.x scripts are UTF-8)
- https://www.nexusmods.com/witcher3/mods/13735 (Custom Player Characters remaster fix)

## Session 2026-10-18 (later): workspace, toolchain, first launches

Goal from here: port Witcher Online to 5.01, then work toward shared enemies and quests.

### Observations (runs on the tested build)

- `witcher3.exe -verifyscriptsandexit` compiles all scripts (vanilla + mods) and exits (rc=3 whether or
  not it failed). Errors show in a window titled "The Witcher 3: Wild Hunt - Script Compilation
  Errors" whose Edit control holds the full list (read it with WM_GETTEXT). About 10 to 40 s per run.
- The remaster loads **Steam Workshop mods** from `steamapps\workshop\content\292030\<item>\mods\`.
  The 4.04-era workshop mod "Fast travel from anywhere" (3253049013) overrides
  `game\gui\menus\mapMenu.ws` and breaks script compilation for every launch (78 errors, all from that
  file, including one reported in vanilla `player.ws` because it calls the mod's `GetShownMapType`).
  Errors from mod files print without the `[content0]` prefix.
- Vanilla 5.01 scripts compile cleanly once that mod is off.
- Per-mod `Documents\The Witcher 3\mods.settings` with `[modName]` `Enabled=0` is honored by the
  script compiler. `[ContentManager/Mods] EnabledWorkshop=false` in `dx12user.settings` is not (it
  is the in-game "Enable Steam mods" toggle; it did not stop compilation).
- 5.01 reads only `dx12user.settings` (plus `profile.settings`); the exe has no `user.settings` string.
- UTF-16LE mod scripts with a BOM still compile on 5.01 (workshop "Candle interactions" mod).
- Useful flags found in the exe: `-windowed -width -height -borderless`, `-world`, `-position`,
  `-noplayer`, `-net`, `-debugscripts`, `-show_script_log_channels`, `-forcescriptcompilation`,
  `-verifyscriptsandexit`, `-silentscripts`, `-scriptdefines=`, `-compile_nonstrict`,
  `-disablemods`, `-noninteractivecrash`, `-silentcrash`; a `commandline.txt` is also read.
- WitcherNativeBridge 415e1c1 built with VS 2022 (v143) and loaded by Ultimate ASI Loader 9.7.4 as
  `bin\x64_dx12\dinput8.dll`. Log: `registration sites=279 consensus=279`, string marshalling OK,
  hook installed, `native registration: WNB_GetApiVersion=OK`. The exe's numeric version is
  5.0.15.65482.
- The bridge's remaster update shows the engine's script strings and CNames are now UTF-8 (`char`),
  not UTF-16. Witcher Online's client still reads `WNB_String.data` as `wchar_t`, so its outbound
  payloads would be garbled on 5.01.
- 5.0 replaced the `EAreaName` enum in script APIs with CNames (`GetCurrentArea() : name`,
  `GetCurrentJournalArea(out name)`, new `GetDeprecatedAreaName(int) : name`); `AreaTypeToName` is
  gone. Witcher Online uses the old API in about 30 places.
- Custom Player Characters, Chill Out and Shared Imports have no public source; Witcher Online uses
  CPC's `ENR_PlayerType` about 500 times and Chill Out's `ChillSpot`/`CO_*` about 20 times.

## Session 2026-10-18 (later): port compiles, two clients see each other

### Observations (game 5.01)

- Witcher Online port (branch `remastered-5.01` of a local clone, uncommitted) compiles on 5.01 with
  Gwent PvP fenced off (`#ifdef WO_GWENT_PVP`) and compile stubs standing in for Custom Player
  Characters and Chill Out. Changes needed: `map` is a new keyword (rename variables);
  `@addMethod(CInputManager) import function IgnoreGameInput(...)` instead of a bodiless addMethod;
  area API ported to names with old numeric codes kept on the wire (`areaCompat.ws`); client reads
  script strings as UTF-8 on 5.x.
- 5.x script preprocessor works: `#ifdef/#ifndef/#else/#endif` at top level and inside function
  bodies (directive strings `define`, `-scriptdefines=` also exist; `#define` not tested yet).
- `@addMethod(Class) import function X(...)` is the 5.x way to expose an undeclared native method.
- Single-instance lock is a named mutex `cdprojekt_red_the_witcher_3_wild_hunt` (CreateMutexA).
  Renaming it in-process (IAT hook in a test ASI) lets several instances run; without it the second
  one shows "game is already launched" and exits with rc=1.
- Unattended runs need, in test mode only: GetForegroundWindow faked to the game window plus
  WM_ACTIVATE/WM_ACTIVATEAPP/WM_KILLFOCUS filtered (no pause when alt-tabbed); ClipCursor,
  SetCursorPos, SetForegroundWindow, GetAsyncKeyState and raw-input INPUTSINK neutralized so test
  windows never grab the owner's mouse, focus or typing; per-process audio session muted.
- Startup sequence: StartupMoviesMenu (bumpers), RecapMoviesMenu (`gamestart/recap_wip.usm`, about
  3 min), StartupExperienceMenu, CommonMainMenu. Closing the two movie menus in OnConfigUI cuts start
  to main menu to about 12 s.
- Loading a 4.04 save in 5.01 shows a one-time modal dialog "Skill points reset / new skill system"
  (UDB_Ok). It pauses the game until answered; all dialogs go through
  `CR4GuiManager.ShowProgressDialog`, so a test wrapper can log and answer them.
- 4.04 saves load in 5.01 (`LoadLastGameInit` from a CommonMainMenuBase.OnConfigUI wrapper).
- Witcher Online's 4.04 DLC (metadata.store v6, bundles) loads on 5.01: remote players' ghosts
  spawn from `dlc\dlc_mpmod\data\entities\geralt_npc.w2ent`.
- **Automated test `see_each_other` PASS** (2 game clients + local server, same save): each client
  spawned the other's ghost at the reported position (502.48, 1715.15, 3.61). Run
  `20261018-162109-see_each_other`, about 2.5 min unattended.
- The mod's own bundle is only `gwint_game.redswf` (4.04 Gwent board); not installed on 5.x.

### Derived

- QA level for "players visible": automated (2 clients, one PC). Everything else untested.

## Session 2026-10-18 (evening): unattended multi-instance QA

### Observations

- `movement` scenario PASS (2 clients): the mover teleports 6 m back and forth; the observer's copy of
  its ghost lands within about 1.5 m of the networked position after each move (4 moves seen). Run
  `20261018-171106-movement`. `see_each_other` also PASS earlier.
- A test instance must not use the real Documents folder: the main menu calls `SaveUserSettings`,
  so `-width/-height` test flags end up in the real `dx12user.settings` (and `.bak`). Fixed by
  hooking `SHGetKnownFolderPath(FOLDERID_Documents)` and `SHGetFolderPathW/A(CSIDL_PERSONAL)` in the
  test ASI and seeding a per-bot sandbox (settings copies, `mods.settings`, one save copy); the ASI
  refuses to start a test without it.
- Two instances with ray-traced settings ended in a GPU device-removed crash (DXGI 0x887A0020) and
  a driver reset (WER LiveKernelEvent). Test sandboxes now get the game's own "low" preset
  (expanded from `user_config_matrix/pc/graphics.xml`), RT off, `-noraytracing`,
  `[Engine] LimitFPS=30`, 640x360.
- Per instance at that preset: about 10.5 GB private RAM and about 4 GB VRAM. On a 12 GB card shared
  with desktop apps, two instances can overcommit VRAM and drop to a few FPS; the observer counts
  moves cumulatively so slow ticks do not fail the test.
- First-run screens an unattended bot must handle: StartupMoviesMenu, RecapMoviesMenu (about 3 min),
  StartupExperienceMenu (CDPR account link, then telemetry consent; tests close it without answering
  so no consent is stored), the one-time "skill points reset" dialog for 4.04 saves.

## Session 2026-10-18 (night): Steam relay and player package

### Observations

- The game's own `bin\x64_dx12\steam_api64.dll` (10.87.46.89) exports `SteamAPI_InitFlat`, manual
  dispatch and the `SteamUser_v023`, `SteamMatchmaking_v009`, `SteamFriends_v018`,
  `SteamNetworkingMessages_SteamAPI_v002` interfaces, so a separate Spacewar (480) relay process can
  load it; nothing to redistribute.
- `w3relay` (HXCoop pattern): host gives each lobby member a local UDP socket to the Witcher Online
  server; join binds 127.0.0.1 and forwards to the lobby owner. Witcher Online needs no change: its
  client just connects to 127.0.0.1.
- Relay self-test over a mock `steam_api64.dll` PASS, including a game client starting 25 s late and a
  non-member whose traffic must not reach the server.
- First relay version failed the two-client test: the host only answered keep-alives from players that
  had sent game data, so the joiner (still loading) saw 20 s of silence and quit. Fixed (host tracks all
  members on the control channel; joiner rejoins instead of exiting).
- Real Steam: init as 480, lobby creation and clean shutdown work. `LobbyCreated` arrives twice
  (call result and broadcast); made idempotent.
- `movement --relay` PASS (second client only through the relays), also with the built player
  package installed byte for byte.
- Player package (179 MB): ported mod + stand-ins, DLC, ASI loader, bridge, client, relay, server jar,
  Host/Join launchers, licenses and source of the GPL parts.

### Unknowns

- A join between two real Steam accounts on two PCs (relay latency, invite and Join Game flow).
- Chat, emotes, horses, party/dialog sync on 5.01 (not exercised by the bots yet).
