# Console games on PC as source code: decomp, recomp, reimplementation

Many of the best co-op mods for console games (Ocarina of Time on Ship of Harkinian, Super
Mario 64 on sm64coopdx) did not reverse engineer a running binary. They started from source
code: a decompilation turned into a PC port, where co-op is ordinary game programming. This
page is how to get a console game to that point, or to find out someone already did.

Status snapshot is October 2026. This area moves monthly, so re-check every project's
repository before relying on a row. Items marked **(unverified)** came from one secondary
source, a search snippet, or my own memory, and were not confirmed on the project's own page.
Everything else links to the page it came from.

## 1. Four ways to get a console game's logic into your hands

| Approach | What you get | Typical effort | Output readable by humans? | Co-op work afterwards |
|---|---|---|---|---|
| **Matching decompilation** | C/C++ that compiles to the exact original bytes, then ported to PC with a graphics/audio shim | Years of community work for a big game; weeks to months for a small one | Yes (the whole point) | Normal gameplay programming: add puppets, host authority, sync flags |
| **Non-matching / functional decompilation** | C that behaves the same but does not byte-match | Faster than matching, less rigorous | Yes | Same as above, but compiler-sensitive bugs are more likely |
| **Static recompilation** | Original machine code translated to C/C++/Rust once, ahead of time, linked with a runtime that replaces the OS and hardware | Weeks to months for the tool plus per-game fixes | No (machine-generated) | Hooks and patches at function level, usually through the project's mod API |
| **Engine reimplementation** | A new engine that loads the original data files | Years; scope equals the engine | Yes (new code) | Add netcode to your own engine |

Rule of thumb for agents: a finished decomp port is the best case (readable source, free to
edit). Static recomp is second best (you can patch, but not read the output). Starting your
own matching decomp is a long project; do it only when nothing exists and the owner
accepts that timeline.

### 1.1 Matching decompilation

A matching decomp recreates source that, when built with the original compiler and flags,
yields a binary identical to the retail one. The identical-bytes check is what makes the work
verifiable: the compiler and a diff tool referee every function.

Tool stack (all open source):

| Tool | Job | Platforms | Source |
|---|---|---|---|
| splat | Split a ROM/binary into code and asset segments, emit assembly | N64, PSX, PS2, PSP | [ethteck/splat](https://github.com/ethteck/splat) |
| decomp-toolkit (dtk) | Analyze DOL/REL, split into relocatable objects, generate linker script, diff vs ELF | GameCube, Wii (Metrowerks CodeWarrior) | [encounter/decomp-toolkit](https://github.com/encounter/decomp-toolkit) |
| dtk-template | Project skeleton using dtk, the recommended way to start a GC/Wii decomp | GameCube, Wii | linked from the dtk README above |
| m2c | First-draft C from assembly | MIPS, PowerPC, ARM, GBA ARM, SuperH; IDO, GCC, mwcc | [matt-kempster/m2c](https://github.com/matt-kempster/m2c) |
| objdiff | Local diff of target vs built object, per function, plus progress reports | ARM, ARM64, MIPS, PowerPC, SuperH, x86 | [encounter/objdiff](https://github.com/encounter/objdiff) |
| asm-differ | Older diff script, better line-to-asm mapping than objdiff per one author | many | mentioned in [Macabeus's write-up](https://macabeus.medium.com/development-journey-on-game-decompilation-using-ai-part-3-a0a322e0d274) |
| decomp-permuter | Random and manual rewrites of C to lower the diff score | MIPS (IDO, maybe GCC), PowerPC, ARM32 | [simonlindholm/decomp-permuter](https://github.com/simonlindholm/decomp-permuter) |
| decomp.me | Web scratchpad: paste C, compile with the right compiler, see the diff, share | many compiler presets | [decomp.me](https://decomp.me) **(unverified: site not fetched; widely documented in the repos above)** |
| DecompPipeline | Agent-driven decomp: Ghidra prepares each function, cheap model workers (Haiku) write the C, and an emulator-based test oracle judges PASS or FAIL by behaviour, not bytes; a `port/` stage builds the readable C as a native program | Dreamcast SH-4 today; new CPUs are new targets (Xbox / Xbox 360 planned by the author) | [GeneralAtrox/DecompPipeline](https://github.com/GeneralAtrox/DecompPipeline) (MIT, community contribution) |
| decomp.dev | Progress hub fed by objdiff reports | many | [decomp.dev](https://decomp.dev). Its front page now says the index and new submissions are being sunset while existing pages stay (fetched Oct 2026). |

Matching versus non-matching: matching projects pin the exact compiler (IDO, mwcc, agbcc, MSVC
and so on). Non-matching ones accept equivalent behavior. Ports usually need only behavior, so
a 100% match is not required to ship a port, but a high match percentage means the
reconstructed code is trustworthy.

**Decomp with agents.** [DecompPipeline](https://github.com/GeneralAtrox/DecompPipeline) is a
full workflow for decompiling a game with AI agents, shared by its author for Dreamcast. Each
function goes to a locked-down small model; a machine judge runs the original and the new C
on the same generated inputs in an emulator-based oracle and returns only PASS or FAIL, so the
agent can't argue or game the score. Functions are clustered into systems, worked in parallel,
then made readable and built as a native port. The tool holds no game data: each game is a
project folder, each CPU a target, so the author expects it to retarget to other consoles.

Mature projects to know (not exhaustive):

| Project | Platform | State | Link |
|---|---|---|---|
| Ocarina of Time, Majora's Mask | N64 | Complete enough to port | [zeldaret](https://github.com/zeldaret) |
| Twilight Princess | GameCube | Reported 100% decompiled; README says GameCube releases fully match | [zeldaret/tp README](https://raw.githubusercontent.com/zeldaret/tp/main/README.md) |
| Super Mario 64 | N64 | Mature; the base of sm64ex and sm64coopdx | see sm64coopdx below |
| Perfect Dark | N64 | Both NTSC versions decompiled; status page about 97.4% with the remainder called a technicality by the lead | [VGC](https://www.videogameschronicle.com/news/perfect-dark-and-banjo-kazooie-could-be-the-next-n64-pc-ports/) |
| Paper Mario | N64 | Fully decompiled | [VGC](https://www.videogameschronicle.com/news/paper-mario-has-been-fully-decompiled-meaning-pc-ports-and-mods-are-possible/) |
| Animal Crossing (GC) | GameCube | ac-decomp; PC port exists (section 2) | [Korben](https://korben.info/en/animal-crossing-gamecube-pc-native-port-recompilation.html) |
| Pokemon (pret) | GBA/GB/DS | Emerald, Red, etc. build a bit-identical ROM; SHA-1 given in README | [pret/pokeemerald](https://github.com/pret/pokeemerald) |
| Super Smash Bros. Melee | GameCube | 100% decomp, no port yet per a list | [Held Games list](https://heldgames.com/guides/recompiled-games-list) |
| Super Mario Galaxy (Petari) | Wii | 100% matched code; README says not intended as a PC port | [Held Games list](https://heldgames.com/guides/recompiled-games-list) |
| Super Mario Odyssey | Switch | Well under half; sources disagree (about 10% to 15%) | [TweakTown/DSOGaming search](https://www.tweaktown.com/news/114036/super-mario-odyssey-is-getting-a-native-pc-port-hits-almost-60-fps-on-an-rtx-3050/index.html), [CCC talk](https://events.ccc.de/congress/2025/hub/en/event/detail/super-mario-odysseydecomp-a-tale-about-decompiling) |

Licensing note: many decomps carry no license file. For example, the pret/pokeemerald page
shows no LICENSE file (checked via fetch; verify in the repo). Ports built on a decomp inherit
whatever the decomp allows; see section 5.

### 1.2 PC ports built on decomps

Typical architecture: take the decomp, replace the platform layer (graphics API, audio, input,
OS calls) with a PC one, and load assets from the user's own dump at runtime.

| Port | Base | How it runs | Notes | Link |
|---|---|---|---|---|
| Ship of Harkinian (OoT) | zeldaret/oot decomp | Built on libultraship (LUS), which mimics libultra on modern hardware; ROM converted to an `.o2r` archive | No copyrighted assets shipped; has an Anchor co-op layer (section 4) | [Shipwright](https://github.com/HarbourMasters/Shipwright) |
| 2 Ship 2 Harkinian (MM) | MM decomp | Also on libultraship; repo listed CC0-1.0; nightly builds exist | Fetched page mentions no online features | [2ship2harkinian](https://github.com/HarbourMasters/2ship2harkinian) |
| sm64ex / sm64coopdx | SM64 decomp | PC port with online multiplayer that syncs enemies, events, every level; Lua mod API | Continuation of sm64ex-coop by djoslin0; repo shows sha1 files and an `extract_assets.py`, which suggests asset extraction from the user's ROM (inference). License not confirmed **(unverified)** | [sm64coopdx](https://github.com/coop-deluxe/sm64coopdx) |
| Dusklight (Twilight Princess) | zeldaret/tp | Native on Windows, macOS, Linux, mobile per press; user supplies GC disc dump | Reported CC0 code; v2.0.0 with mod system and randomizer | [Time Extension](https://timeextension.com/news/2026/05/the-legend-of-zelda-twilight-princess-has-unofficially-been-ported-to-the-pc), [Korben](https://korben.info/en/dusklight-zelda-twilight-princess-native-pc-mac-linux-mobile.html) |
| ACGC-PC-Port (Animal Crossing) | ac-decomp | GX replaced by OpenGL 3.3; US Rev 0 (GAFE01) only; Windows only at time of reporting; GBA link, town visiting, NES emulation missing | One press source says AI coding tools were used for the port (not the decomp) | [Korben](https://korben.info/en/animal-crossing-gamecube-pc-native-port-recompilation.html), [Notebookcheck](https://www.notebookcheck.net/Animal-Crossing-for-the-Nintendo-GameCube-just-received-an-unofficial-native-PC-release-with-support-for-4K-widescreen.1253295.0.html) |
| Perfect Dark | PD decomp | Port possible; a confirmed release was not found in my search **(unverified)** | | [VGC](https://www.videogameschronicle.com/news/perfect-dark-and-banjo-kazooie-could-be-the-next-n64-pc-ports/) |
| Halo: Combat Evolved (Xbox) | **(unverified how built)** | Linux, Windows, Android arm64; system link works cross-platform | Listed with multiplayer, which makes it a co-op candidate | [Held Games list](https://heldgames.com/guides/recompiled-games-list) |
| Jak and Daxter (OpenGOAL) | Decompiler turns GOAL bytecode to GOAL source; own GOAL compiler targets x86-64 | PS2 game, needs the user's own copy; ISC license; Jak 1 complete, Jak 2 beta, Jak 3 in progress; x86-64 with AVX | No multiplayer in the repo page | [jak-project](https://github.com/open-goal/jak-project) |
| Zelda Oracle games native port | oracles-disasm | **(unverified: not researched in detail)** | | [oracles-disasm](https://github.com/Stewmath/oracles-disasm) |

### 1.3 Static recompilation

A recompiler reads the retail executable plus metadata (symbols, jump tables), then emits C,
C++ or Rust per function. The output only runs together with a runtime that stands in for the
console OS, GPU and audio. The user supplies the game files; nothing from the game ships.

| Tool | Source arch | Output | Needs | Known limits | Link |
|---|---|---|---|---|---|
| N64Recomp | N64 MIPS | C | Runtime (N64ModernRuntime, with RT64 as renderer in Zelda64Recomp); ELF-based metadata | No RSP overlay support yet; TLB relocation pending; tested mostly on old MIPS compilers; MIT | [N64Recomp](https://github.com/N64Recomp/N64Recomp) |
| Zelda64Recomp | built on N64Recomp | native Majora's Mask | User's US N64 MM ROM; D3D12, Vulkan 1.2 or Metal GPU; GPL-3.0; mod menu, Thunderstore mods, randomizer; README does not mention multiplayer | | [Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp) |
| XenonRecomp (+ XenosRecomp for shaders) | Xbox 360 PowerPC (VMX128) | C++ | Clang 18+, game XEX and XEXP patch, TOML config, you write the runtime | MMIO (e.g. XMA) unimplemented, no exceptions, jump table detection tuned to Sonic Unleashed | [XenonRecomp](https://github.com/hedge-dev/XenonRecomp) |
| ReXGlue SDK | Xbox 360 | C++ ahead-of-time, built on Xenia's codebase | Game files | Early development | [rexglue-sdk](https://github.com/rexglue/rexglue-sdk) |
| PSXRecomp | PS1 MIPS | C, then native or WebAssembly | PS1 runtime; open BIOS (OpenBIOS) or user's BIOS | Young; Pepsiman reported running in a browser | [mstan/psxrecomp](https://github.com/mstan/psxrecomp), [Held Games](https://heldgames.com/guides/ps1-recompilation-explained) |
| RecompOne | PS1 | C# | Runtime layer | Young | [RecompOne](https://raw.githubusercontent.com/BlackLabelHQ/RecompOne/HEAD/README.md) |
| PS2Recomp | PS2 R5900 MIPS | C++ | Runtime layer for PS2 hardware; GPL-3.0 | Early 2026 coverage: experimental, no playable games **(re-check; a later date may differ)** | [ran-j/PS2Recomp](https://github.com/ran-j/PS2Recomp), [Time Extension](https://www.timeextension.com/news/2026/01/native-pc-ports-of-ps2-games-could-be-on-the-way-thanks-to-new-recompilation-experiment) |
| ps3recomp | PS3 Cell PPU | C/C++ | Many subsystems per game | Developer toolkit, no public builds per a list; games reach init or menus; one reported 2-player network match in a small arcade game | [sp00nznet/ps3recomp](https://github.com/sp00nznet/ps3recomp), [Generation Amiga](https://www.generationamiga.com/2026/06/15/ps3recomp-the-new-tool-bringing-native-playstation-3-ports-closer-to-pc/), [Held Games](https://heldgames.com/guides/recompiled-games-list) |
| DolRecomp / GCRecomp | GameCube/Wii PowerPC | C or Rust | You bring runtime and renderer (DolRecomp first release is CPU only) | Early | [Steam Deck HQ](https://steamdeckhq.com/news/we-may-see-more-gamecube-wii-pc-ports-soon/) **(unverified: repos not opened)** |
| Mario Kart Wiicompiled | Wii | native | PAL only; beta 0.2.32; reportedly AI-assisted; reports claim online play | Release status disputed across outlets | [Held Games](https://heldgames.com/guides/mario-kart-wiicompiled-first-wii-recomp), [Notebookcheck](https://www.notebookcheck.net/Mario-Kart-Wii-gets-native-PC-port-with-60-FPS-and-online-play-even-as-fans-decry-AI-use.1346163.0.html) **(unverified)** |
| Switch static recomp | AArch64 | native | | Super Mario Odyssey build reported at 58-59 FPS on a laptop RTX 3050, no audio, graphics bugs | [TweakTown](https://www.tweaktown.com/news/114036/super-mario-odyssey-is-getting-a-native-pc-port-hits-almost-60-fps-on-an-rtx-3050/index.html) **(unverified: single outlet)** |

Finished recomp ports reported so far (see [Held Games list](https://heldgames.com/guides/recompiled-games-list),
a secondary source, so verify per game): Majora's Mask, Banjo-Kazooie and other N64 titles,
Donkey Kong 64 (v1.0 August 2026), Sonic Unleashed, Lost Odyssey, Ninja Gaiden II, several
other Xbox 360 titles, Pepsiman, Mario Kart Wii (beta).

Why recomp is harder to extend than a decomp: the generated code is not meant to be read, and
gameplay changes happen as function hooks or mod-API patches. N64Recomp's TOML config describes
hooks, but the README says hooks are not yet implemented at the time of the fetch **(re-check)**.
Zelda64Recomp's mod menu is the practical route for gameplay changes today.

### 1.4 Engine reimplementations

| Project | Reimplements | Notes |
|---|---|---|
| OpenGOAL | Jak and Daxter engine and GOAL language | Listed above. A decompiler plus a custom compiler plus asset tools. |
| OpenMW | Morrowind engine | **(unverified: not fetched)** Multiplayer exists as TES3MP, a separate project. |
| Source ports (dhewm3, etc.) | id Tech engines | See [engine-families.md](engine-families.md). |

Reimplementations load the original data files, so the same "user supplies game data" legal
model applies. Co-op is added to code you control, like a decomp.

## 2. AI-assisted decompilation, 2025 and 2026

Matching decomp is a near-ideal agent task: the compiler plus a diff tool is an objective
referee, and work splits cleanly per function. Public evidence, newest practices first:

| Write-up | Platform / game | What it shows | Link |
|---|---|---|---|
| Macabeus, 60-function benchmark | GBA (agbcc) | Pipeline runs m2c, compiler, objdiff and decomp-permuter first, then a Claude loop. Best run matched 80% of functions, six-run average 74%, 88% of functions gave the same outcome every run, 12 functions always failed | [Medium](https://macabeus.medium.com/can-llms-really-do-matching-decompilation-i-tested-60-functions-to-find-out-4e39b0ae4288) (via search summary) |
| Macabeus, Klonoa: Empire of Dreams | GBA | Claude Code wrote the splitter and build tooling and decompiled functions; 51% of code bytes at time of writing. Built asmlift, Transmuter, gba-kit | [Gambiconf](https://gambiconf.substack.com/p/starting-a-decompilation-project) |
| freeqaz, Rock Band 3 / Dance Central 3 | Xbox 360 PPC (MSVC), no symbols | Dozens of concurrent Claude Code agents via an orchestrator MCP server with a SQLite match DB; 44,226 of 69,301 functions matched over ten weeks in the repo; game code 81.7%, whole binary 46.4%; byte-exact compile as the only judge | [freeqaz.com](https://freeqaz.com/blog/how-agent-swarms-decompile-games) |
| Stephen Jayakar, Melee | GameCube | Planner, worker and judge agents; workers wrote their own wrappers around m2c, the compiler and objdiff; about 20 merged and about 80 in review at time of writing | [Magic decomp](https://stephenjayakar.com/posts/magic-decomp/) |
| Community skills for Melee | GameCube | A decomp skills PR and a record matches-per-PR PR | [doldecomp/melee #2076](https://github.com/doldecomp/melee/pull/2076), [#2102](https://github.com/doldecomp/melee/pull/2102) |
| decomp.wtf | general | Agent that decompiles games you own into C that compiles to the same bytes; runs locally | [i12bp8/decomp.wtf](https://github.com/i12bp8/decomp.wtf) **(unverified: not opened)** |

### Where agents help

- First-draft C per function, then iterating on the objdiff score. Deterministic first pass
  (m2c, then permuter) before spending model tokens.
- Boring infrastructure: splitters, linker scripts, symbol naming, build scripts.
- Parallelism: one worktree per agent, a shared match database, merge only byte-exact results.
- Running several models. In the Rock Band 3 write-up, three models together cracked 19 of 30
  benchmark functions versus 13 to 15 for any one alone.

### Where agents struggle (all reported in the sources above)

- Cheating the score: forking the compiler or pinning registers to force a match (Klonoa), or
  gaming a fitness function (Rock Band 3). Make byte-exact compile with the stock compiler the
  only terminal judge and reject compiler tweaks.
- Bad splits and data-as-code: fragments that fall through, literal-pool data disassembled as
  instructions, functions reachable only through pointer tables (about 20% in Klonoa).
- Hard residue: the last 10 to 20% of functions (register allocation, scheduling, unusual
  compiler idioms). A frontier model's whole-function byte-exact rate in one sweep was 12% on
  the hardest set.
- Reasoning budget: bounded thinking beat unbounded; low token ceilings produced blank answers.
- Code quality: matched C is often ugly and over-commented; plan a cleanup pass.
- Community norms: parts of the decomp community object to AI-generated decomps and ports.
  Banjo: Recompiled's developer called AI-generated ports a race to the bottom
  ([VGC](https://www.videogameschronicle.com/news/banjo-kazooie-pc-port-decomp-developer-says-ai-generated-pc-ports-are-a-race-to-the-bottom-and-disrespectful/)).
  Disclose AI use in PRs to existing projects and follow their policy.

Realistic speed: no reliable per-function figure exists. The Melee author went from about one
day per function by hand to batches of dozens merged; the Rock Band 3 run produced tens of
thousands of matches in ten weeks with dozens of agents and heavy tooling. Budget for tooling
work first; matching is the second half.

## 3. Per-console feasibility

Difficulty is for "reach a playable PC build from source or recomp", not for co-op afterwards.

| Console | CPU | Decomp tooling | Recomp tooling | Notable finished or near PC ports | Difficulty |
|---|---|---|---|---|---|
| N64 | MIPS R4300i (big endian) | Very mature: splat, m2c, IDO/GCC compilers, permuter | N64Recomp + RT64; RSP microcode still a gap | OoT, MM, SM64, Banjo, DK64, Mario Kart 64, Star Fox 64 | Low to medium |
| GameCube / Wii | PowerPC Gekko/Broadway | Mature: decomp-toolkit, dtk-template, mwcc compilers, objdiff | DolRecomp, GCRecomp early; Wiicompiled for Mario Kart Wii | Twilight Princess (Dusklight), Animal Crossing | Medium |
| PS1 | MIPS R3000 | splat supports PSX; fewer finished decomps (Legend of Mana NA 100% per a list) | PSXRecomp, RecompOne | Pepsiman, Ape Escape (reported early) | Medium |
| PS2 | MIPS R5900 (128-bit SIMD, VUs) | splat supports PS2; OpenGOAL-style custom approach for Jak | PS2Recomp experimental | Jak trilogy via OpenGOAL | High |
| PS3 | Cell (PPU + SPUs) | Little | ps3recomp, developer stage | None public | Very high |
| Xbox (original) | x86 Pentium III | x86 is easier to disassemble; **(unverified)** | not researched | Halo CE native port reported | Medium **(unverified)** |
| Xbox 360 | PowerPC Xenon (VMX128) | Early: AI swarm RB3 and DC3 work, custom splitters | XenonRecomp, ReXGlue; the most productive recomp scene | Sonic Unleashed, Lost Odyssey, Ninja Gaiden II and others | Medium to high |
| GBA / DS | ARM7/ARM9 | Very mature: pret, agbcc, m2c ARM modes, permuter ARM32 | not the usual route (decomp is easy) | Pokemon decomps; Klonoa in progress | Low |
| Switch | AArch64 | Early: OdysseyDecomp under half done | A Switch recomp of Odyssey reported, early | None finished | Very high |

## 4. Agent procedure

### (a) Check what exists, in this order

1. [DIRECTORY.md](../DIRECTORY.md) and `games/` in this repo.
2. decomp.dev index (read-only now, see table above) and the GitHub org pages: zeldaret, pret,
   doldecomp, open-goal, HarbourMasters, N64Recomp, Zelda64Recomp, hedge-dev.
3. Search `"<game> decompilation"`, `"<game> recompiled"`, `"<game> PC port"`, plus the Held
   Games lists linked above for recent recomps.
4. Record version, region, build, and ROM/ISO hash for the match: ports usually support one
   region (Animal Crossing: US Rev 0 only; Mario Kart Wii: PAL only; Banjo: Recompiled: NA 1.0).

### (b) A port exists: add networking in code

Both reference projects follow the same pattern. Read them before designing anything.

- **Ship of Harkinian + Anchor.** [Anchor](https://github.com/garrettjoecox/anchor) is a
  client plus server. A public server is listed in the README. Clients hold the game state;
  joining loads the other player's save state; flag sets and item gives are broadcast to
  everyone in a room or team. The README fetched did not describe actor puppets; whether the
  client shows other players is **(unverified)**, read the Shipwright network code to confirm.
- **sm64coopdx.** [sm64coopdx](https://github.com/coop-deluxe/sm64coopdx) synchronizes
  entities and every level across players and exposes a Lua modding API. Its architecture
  (host versus peer) is not described on the repo front page **(unverified)**; read the source.
- **Recomp ports** have no uniform route. Zelda64Recomp offers a mod menu and Thunderstore
  mods; multiplayer is not in its README. Look at the mod API first.

Design checklist, applied to a port:

1. Pick host authority for world state (quests, flags, NPCs, enemies) and client authority for
   the local player's movement. See [networking.md](networking.md).
2. Add a player-puppet actor type for remote players (model, animation id, position, a few
   state bits), spawned and destroyed on join and leave.
3. Sync discrete state first (flags, inventory, scene/level id), then actors by id with
   position and health. Loading zones need a policy: all players follow, or per-player scenes.
4. Replace one-global-player assumptions in code (camera, UI, input, save slot). In a decomp
   these are plain globals, so grep for them.
5. Keep the sync layer a thin patch on the port so upstream updates merge; upstream ports move
   fast.
6. Test with bots, not people: headless clients and scripted inputs, see
   [automated-qa.md](automated-qa.md).

### (c) Only a partial decomp exists

- Contribute to it rather than forking. Read its contributing guide; use its own build and
  diff flow; follow its AI policy.
- Co-op rarely needs 100%. Often the parts that matter (player, actor system, save, scene
  loader) are matched first. Check the project's progress by translation unit.
- If a static recomp tool already supports the platform (table 1.3), recomp the game and
  use the mod API or hooks for co-op instead of waiting for the decomp.
- A hybrid is legitimate: a decomp for the subsystems you need plus original binary for the
  rest. Check the project's design.

### (d) Starting a new decomp

1. Confirm the ROM/ISO hash, find the original compiler and flags (map files, strings,
   compiler version in the binary, community compiler archives). decomp.me has presets for
   many compilers **(unverified)**.
2. Set up the project skeleton: dtk-template for GC/Wii, splat config for N64/PS1/PS2/PSP,
   pret-style Makefile for GBA/DS. Get the build to reproduce the original ROM from
   assembly first (all functions as `INCLUDE_ASM` stubs).
3. Split correctly. Bad splits are the top agent failure (Klonoa, Rock Band 3). Verify
   function boundaries, data inside code, and pointer-table targets before matching begins.
4. Matching loop per function, with objdiff as the oracle:
   - m2c draft, compile with the original compiler, objdiff, then permuter or agent edits.
   - Accept only a byte-exact result built with the stock compiler flags.
   - Mark unmatched functions non-matching but behavior-equivalent if you need a playable build
     sooner.
5. Parallelize across agents: a planner lists unmatched functions (sorted by size or by
   dependency), each worker takes one in its own worktree, a judge reruns the real build and
   merges only byte-exact results, and a shared database records attempts and failures so
   agents do not repeat work (the pattern in [freeqaz](https://freeqaz.com/blog/how-agent-swarms-decompile-games)
   and [Jayakar](https://stephenjayakar.com/posts/magic-decomp/)). Use a private scratch
   directory per agent; see [multi-agent-workflows.md](multi-agent-workflows.md).
6. Name things from evidence (strings, debug info, runtime observation), not guesses.
7. Port layer next: choose a render/audio/input shim (libultraship for N64-style, a custom
   GX-to-OpenGL layer as in Animal Crossing, or similar), and an asset extractor that reads the
   user's dump at first launch.
8. Only then add networking (section 4b).

### (e) Legal

- Never ship or commit ROMs, ISOs, extracted assets, or the assembly that splat/dtk produce
  from them. Reproducible scripts that read the user's own dump are the norm. Klonoa's repo
  generates assembly with a setup script so none is committed
  ([source](https://gambiconf.substack.com/p/starting-a-decompilation-project)).
- Ports load assets from the user's own dump at runtime. Shipwright and 2Ship state they
  include no copyrighted assets; Zelda64Recomp, Banjo: Recompiled and Dusklight require the
  user's copy.
- Licenses vary: CC0 (2Ship, Dusklight code per press), GPL-3.0 (Zelda64Recomp, PS2Recomp),
  MIT (N64Recomp), ISC (OpenGOAL), and some decomps have none. No license means all rights
  reserved: ask or do not copy code. Check the actual LICENSE file, not a news article.
- Legal risk for decomps depends on jurisdiction; press summaries are not legal advice
  ([Kingy AI overview](https://kingy.ai/blog/ai-video-game-decompilation-legality/)
  **(unverified: not opened)**).
- Do not use a decomp or port to bypass online-service DRM or anti-cheat, and do not publish
  your owner's extracted data. Follow AGENTS.md rules 7 and 10.

## Sources index

Tools: [splat](https://github.com/ethteck/splat),
[decomp-toolkit](https://github.com/encounter/decomp-toolkit),
[m2c](https://github.com/matt-kempster/m2c),
[objdiff](https://github.com/encounter/objdiff),
[decomp-permuter](https://github.com/simonlindholm/decomp-permuter),
[N64Recomp](https://github.com/N64Recomp/N64Recomp),
[XenonRecomp](https://github.com/hedge-dev/XenonRecomp).
Ports: [Shipwright](https://github.com/HarbourMasters/Shipwright),
[Anchor](https://github.com/garrettjoecox/anchor),
[2ship2harkinian](https://github.com/HarbourMasters/2ship2harkinian),
[sm64coopdx](https://github.com/coop-deluxe/sm64coopdx),
[Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp),
[jak-project](https://github.com/open-goal/jak-project).
Roundups: [Held Games recompiled list](https://heldgames.com/guides/recompiled-games-list)
(secondary, dated Oct 2026).

## Real co-op on recompilations

Recompiled games can get co-op in code too, not just through hooks:

- [MegaManXSNESRecomp](https://github.com/mstan/MegaManXSNESRecomp): Mega Man X (SNES) as a native
  PC program with playable Zero, couch co-op and online netplay.
- [MegaManX4Recomp](https://github.com/mstan/MegaManX4Recomp): Mega Man X4 (PS1, PSXRecomp) with
  two-player co-op through X's or Zero's campaign, local or online, and an experimental split camera.

- [Birdman64](https://github.com/NoahVl/Birdman64): Pilotwings 64 built natively from its
  decompilation, with two-player split-screen added to a game that never had it. It downloads and
  compiles the decompilation on the player's machine, so no game code is redistributed.

The two Mega Man projects use **recomp-net**, a shared netplay layer for these recompilations: sign-in, lobby and
NAT traversal over ICE/STUN/TURN, plus LAN and direct IP
([netplay notes](https://github.com/mstan/MegaManXSNESRecomp/blob/main/docs/netplay.md)). Design
points worth copying: both players supply their own ROM, the room adopts the host's mods and
options and refuses mismatches, and Player 1 owns story progress while Player 2 joins.
