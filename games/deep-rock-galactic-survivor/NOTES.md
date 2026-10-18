# Deep Rock Galactic: Survivor — working notes

Slug: `deep-rock-galactic-survivor`
Goal: online co-op (2+ players) for a game that ships single-player only.

> Private, machine-specific state (real install paths, logs, dumps, saves) lives in
> `local/`, which is git-ignored. This file is meant to be public-safe.

## Identity

- **Game:** Deep Rock Galactic: Survivor. Developer **Funday Games**, publisher Ghost Ship
  Publishing. Steam-only, Windows x64.
- **Store / appid:** Steam `2321470` (depot `2321471`).
- **Engine:** Unity, **IL2CPP x64**. `GameAssembly.dll` + `DRG Survivor_Data/il2cpp_data/
  Metadata/global-metadata.dat` (IL2CPP metadata **v39**).
- **Tested build (current):** Steam buildid `23854500`, **Unity 6000.4.7f1**
  (`UnityPlayer.dll` FileVersion `6000.4.7.15975364`),
  `build-guid=86f484871c2549f690a3fdbf26aebc8c`.
  - `DRG Survivor.exe` SHA-256 `5abca214deecb763d0cec4d6194c519ac9bd215052987a601c96e75d67e8679a`
  - `GameAssembly.dll` SHA-256 `250bbb4bb0491dee3c9d7f312276d9ecfce04cd98fda14cca1ab67cb289829ba`
  - `global-metadata.dat` SHA-256 `49202e38cb7e400c6895ce6188d81bbf2676af29a90e71493bd03513178a10d8`
- **Earlier build (superseded):** Steam buildid `20237659`, Unity 2022.3.59 IL2CPP,
  `build-guid=43d5554851e8403c9db7df2bc6cc9e34`.
  - `DRG Survivor.exe` SHA-256 `b788e1755d229679140a62e14c8bc175391c064cabce60ef217aac468b47a1db`
  - `GameAssembly.dll` SHA-256 `fcbac8f75fb8e508136b240e2eac2db5fff5d9271eac43df400996672dee06a3`
- **App strings:** `app.info` = `Funday Games` / `DRG Survivor`.

## Modding stack (verified on build 23854500)

- **BepInEx 6 IL2CPP** bleeding-edge `6.0.0-be.789+6cea286` loads and runs
  (`Chainloader startup complete`) **only after a workaround** — see below. BepInEx runs
  its own bundled .NET 6 runtime and generates `BepInEx/interop/*.dll` (132 assemblies on
  this build, incl. `Assembly-CSharp.dll` and `UnityEngine.CoreModule.dll`) via Cpp2IL.
- **Unity 6 / metadata v39 workaround (reproduced, then fixed):** the default config does
  IL *unstripping* using Unity base libraries; on this game that produces a broken interop
  and the chainloader dies with
  `FileNotFoundException: Could not load ... 'UnityEngine.CoreModule'`. Fix:
  1. In `BepInEx/config/BepInEx.cfg`, blank the value:
     `UnityBaseLibrariesSource =` (keep the key, remove the URL).
  2. Delete `BepInEx/interop` and `BepInEx/unity-libs`.
  3. Relaunch; interop regenerates without unstripping
     (`Not performing unstripping as unity libs are not specified`) and the chainloader
     completes. Cost: no unstripped Unity base libs. Reported upstream in
     [BepInEx#1350](https://github.com/BepInEx/BepInEx/issues/1350).
- **Third-party tooling note:** `Il2CppDumper` v6.7.46 **cannot** read metadata v39
  ("ERROR: Metadata file supplied is not a supported version[39]"); use Cpp2IL (bundled
  with BepInEx) or BepInEx's interop output instead.
- **Game's own assemblies** (from interop): `Assembly-CSharp.dll` (main game code),
  `FundayFactory.UI.dll`, `FundayGames.Audio`, `FundayGames.Attributes`,
  `FundayGames.LocalPrefs`, `FundayGames.PlatformService` (+`.Steam`).
- **Libraries of note:** **Zenject** (dependency injection — code is wired from
  installers/singletons, not `MonoBehaviour` globals), **KDTree** (spatial queries —
  likely enemy/target lookup, relevant for interest management), **UniTask** (async),
  PrimTween/DOTween (tweening), Cinemachine (camera), Steamworks.NET.
- **Namespace:** game code sits under `DRS.*` (e.g. `DRS.UI`).

## Observations (facts from a source)

- The game is **single-player only**. The devs answered a co-op question on the official
  Discord (Feb 2024): the focus is a single-player experience; co-op is "not being worked
  on right now" and may never happen. Reported by gamepressure.
- **Modding is established and open:** BepInEx **6** (Unity IL2CPP, bleeding-edge) is the
  community loader; there is a Thunderstore community `deep-rock-galactic-survivor` with a
  preconfigured `BepInExPack_IL2CPP`, and Nexus lists a BepInEx pack plus ~15 mods.
- **Reference mod source proves the hook pattern** (BlueRaja's mods, MIT): a BepInEx
  `BasePlugin` with `Harmony.CreateAndPatchAll`, patching IL2CPP game types. It exposes the
  game's namespace and types: namespace **`DRS.*`** (e.g. `DRS.UI`), types `RarityWeight`,
  `PickupSpawner`, `Economy`, enum `ECurrency` (GOLD, NITRA, RED_SUGAR, BISMOR, ...).
  Interop assembly referenced is `BepInEx/interop/Assembly-CSharp.dll`.
- **Steamworks.NET** ships in the build (`Plugins/x86_64/steam_api64.dll`), so a Steam
  relay path (Spacewar AppID 480) is available later for host/join without port forwarding.

## Derived (my reasoning, not yet verified in-game)

- **Path 2 — build from zero.** There is no co-op to revive. Unity IL2CPP + BepInEx is the
  "easiest modern target" per the playbook's engine table.
- **Reusable models (same engine):** Nitrox (Subnautica: BepInEx + Harmony + LiteNetLib,
  server-authoritative), HKMP (Hollow Knight), Quantum Space Buddies (Outer Wilds),
  CelesteNet (Celeste). Nitrox is the closest structural match.
- **Sync model:** host-authoritative state sync (cannot make a closed binary deterministic,
  so lockstep is out).
- **Sync surface to map:** the dwarf player(s), the enemy swarm and projectiles, damage and
  deaths, XP orbs, material pickups, the run clock/objectives, boss phases, and two
  single-player-only flows that have no co-op analogue: the **level-up card choice**
  (game pauses) and **mission end / extraction**.

## Guesses (believed but untested)

- Puppet dwarves via the game's own player/NPC models are feasible; syncing hundreds of
  swarm enemies is the hard part (bandwidth and authority, not visibility).
- The level-up pause will need a policy (freeze both, or first-to-pick decides).

## Unknowns

- Can two instances run on one PC? (single-instance mutex / window check not yet tested.)
- Entity model, tick/fixed-step behaviour, and how enemies are spawned/pooled — not dumped.
- Save/run state format; where between-run progression lives.
- Version drift: community reports show a later game version on **Unity 6**
  (`1.1.73p`, Unity `6000.4.7f1`). Co-op code must pin to one build; signatures will differ.

## Sources

- https://www.gamepressure.com/newsroom/deep-rock-galactic-survivor-drg-coop-and-multiplayer-explained/za6929
- https://steamcommunity.com/app/2321470/discussions/0/4371376043390476657/
- https://github.com/BlueRaja/Deep-Rock-Galactic-Survivor-Mods
- https://www.nexusmods.com/games/deeprockgalacticsurvivor
- https://thunderstore.io/c/deep-rock-galactic-survivor/p/BepInEx/BepInExPack_IL2CPP/
- https://github.com/BepInEx/BepInEx/issues/1350

## How the game works (from the interop dump, build 23854500)

- **No netcode at all.** A tree-wide search for Photon/Mirror/Netcode/NetworkManager/
  sockets/`TcpClient`/`UdpClient` found **nothing**. The sync layer must be written from
  scratch; there is no engine multiplayer to piggyback on.
- **`Entity` (`Entity : MonoBehaviour`) is the sync anchor.** Fields: `currentHp` (long),
  `IsPlayer` (bool), `pierceStopValue`; `position` (Vector3); `isAlive`. Methods:
  `TakeDamage(long dmg, bool isCrit, EDamageType, bool doFx, EDamageSource, Entity source,
  bool ignoreReduction)`, `Heal(long, EHealType)`, `Die(EDamageType, long overkill, bool)`,
  `ApplyStatusEffect(s)`, `OnGamePaused`/`OnGameUnpaused`. Both `Player : Entity` and
  `Enemy : Entity`.
- **`Player`** adds `EMoveControlType { DISABLED, FORCED, FULL_CONTROL }` plus a companion
  `PlayerControlled : MonoBehaviour` that does movement/animation (`_moveSpeed`,
  `_origTarget`, Idle/Forward/Backward/Left/Right). A **`DummyPlayer : Player`** subclass
  already exists — a ready-made puppet base.
- **Enemies are pooled:** `EnemySpawner.poolDictionary` → `ObjectPool<Enemy>` per `EEnemy`
  type; `Enemy.OnSpawn(...)`, `Enemy.ownerPool`. Pool reuse means instance ids are not
  stable, so the sync layer needs its **own network ids**.
- **AI is centralised in `AI_Manager`** (singleton `_instance`, `_units`, `Add`/`Remove`/
  `Update`) — the lever for authority: run it on the host, suppress on clients.
- **Zenject DI:** managers are wired with `Inject(...)` (e.g. `LevelUpManager`,
  `RunStateManager`, `SaveDataManager`). That is how a mod obtains live references.
- **Level-up flow:** `LevelUpManager` (`flowActive`, `StartFlow`, `HandleLevelUps`,
  `OnPrePlayerLevelGain`/`OnPlayerLevelGain`). This is the pause-and-pick-a-card flow that
  has no single-player analogue and needs a co-op policy.
- **Run/stages:** `RunStateManager` (stage index, primary/secondary objectives,
  `SaveToMidRunData`). **Save:** `DRS.SaveSystem` (`SaveDataManager`, `PCSaveFileManager`,
  `PCMidRunSaveManager`, `MidRunSaveBuilder`, `MidRunSaveData`) with PC and GDK variants.
- **Watch out:** `Assets.Scripts.PhysicsOptimisation` uses Unity Jobs/**Burst**
  (`lib_burst_generated.dll`), and the game ships **KDTree** + `TextmeshDOTS` — enemy
  targeting/movement may be partly Burst-compiled, which is harder to hook than managed code.

### Co-op implications (design sketch — Phase 4)

- **Required co-op behaviours (owner's spec):**
  - **Both dwarves gain experience together** — XP/progression is shared, not per-player.
  - **Level-up choices synchronise:** when the reward/upgrade selection appears, the game must
    pause on **both** clients until **both** players have picked. (Today `LevelUpManager`
    pauses only the local instance.)
- Model: **host-authoritative state sync** (a closed binary cannot be made bit-deterministic).
- **Level generation must be forced identical** — see the transport milestone below: the game
  has no run seed, so the mod seeds `UnityEngine.Random` to a shared value before
  `MapGenerator.CreateMap`. Verified: identical map fingerprints on both instances.
- Puppets: spawn clones from the game's own player prefab / `DummyPlayer`; drive transform +
  animation from the network; disable their input and AI.
- Combat: replicate `Entity.TakeDamage`/`Die`/`Heal` results from the host; guests apply
  with a re-entrancy guard so an applied hit is not re-broadcast.
- Enemies: host runs `AI_Manager`, guests mirror position/HP. Milestone order: players
  visible → shared combat → swarm sync → objectives.
- Level-up: freeze both players during the card flow, or first-to-pick decides.

## Build log

- **Probe plugin v0.0.2 builds and loads** (`BepInEx` IL2CPP plugin, `net6.0`, Harmony).
  Build recipe: reference `BepInEx/core/{BepInEx.Core,BepInEx.Unity.IL2CPP,0Harmony,
  Il2CppInterop.Runtime}.dll` and the interop assemblies needed
  (`Assembly-CSharp`, `UnityEngine`, `UnityEngine.CoreModule`, `Il2Cppmscorlib`,
  `Il2CppSystem`, `Il2CppSystem.Core`), all with `Private=false`.
  Note: a `%(Item.Filename)`-batched `<Reference>` wildcard over the interop folder does
  **not** resolve; list the assemblies explicitly.
- Live in-game result: `Loading [DRG Survivor co-op probe 0.0.2]` → `probe: Load() called`
  → `probe: Harmony patches applied` → `Chainloader startup complete`. Custom managed code
  runs inside the game.
- Probe hooks: `GameController.StartGame` / `OnCoreRunStarted` (captures the run's
  `player`), `Player.Awake`, `AI_Manager.Update` (samples every 120 frames), and
  `Entity.TakeDamage`. It writes `probe.log` next to the exe plus the BepInEx log.
  Signals captured: player position, `CurrentHP`, `isAlive`, live `AI_Manager._units`
  count (peak), and player damage events.
- `GameController.stageIndex` is **not** exposed to interop (no generated property), so
  stage reporting was dropped from the probe.

## Next steps

- Build the puppeteer: spawn a remote-player puppet from the game's own player prefab and
  drive it from the received positions (the transport already carries them), then start the
  host-authoritative combat/enemy layer sized for the measured swarm.

## Transport milestone (two instances, verified)

- **Two instances run side by side on one PC** — no single-instance mutex. Both stayed alive
  (~1.34 GB each) at 1280x720/900x600 windowed.
- **Transport works:** BepInEx plugin + **LiteNetLib 2.1.4** (`lib/netstandard2.1` build —
  the `net8.0` build will not load on BepInEx's .NET 6 runtime). Host listens on UDP 9050,
  client connects to loopback; role is chosen with `-coophost` / `-coopclient`
  (plus `-coopaddr=`, `-coopport=`, `-cooplatency=`). Latency simulation is wired up for
  later loss/latency tests.
- **Bidirectional player-state exchange sustained in both directions** over ~70 s at the main
  menu: host `sent=1427 recv=1376`, client `sent=1359 recv=1409` (every 3rd frame ≈ 20 Hz,
  unreliable channel). Evidence: `local/dumps/twoclient-host.log`, `twoclient-client.log`.
  (Positions read `(0,0,0)` because both instances sat at the menu; real movement needs both
  in a run.)
- Each instance writes its own `coop-<role>.log`, because **BepInEx's `LogOutput.log` is
  shared by both instances** in the same install folder and gets clobbered.

### Environment gotchas found (needed for any two-instance work)

- **The game profile/save folder is per-user, not per-install:**
  `%USERPROFILE%\AppData\LocalLow\Funday Games\DRG Survivor\` (Steam-Cloud synced).
  Two instances, and any test copy, all read and write the *owner's* saves
  (`drg_save_slotN_*.dat`, `drg_current_run_slotN.dat`, `localprefs.dat`). Rule: back the
  folder up before testing and restore after; a proper fix (per-instance redirection) is
  still needed before real co-op play. Backup taken at
  `local/backup/localLow-DRGS-*`.
- A second instance occasionally comes up but stalls (no `Update`), so a two-instance run
  must assert both sides are ticking before trusting the result.

## Design decisions (owner's spec)

Recorded from the owner; these are requirements, not suggestions.

- **Player count: 2.** Do not design around 4.
- **Upgrades are per player** — both dwarves level together, but each picks their own card. (An
  exception for some shared upgrades may be discussed later; not now.)
- **Difficulty stays as-is** for now — no scaling for the second dwarf.
- **Objectives and loot are fully shared**, with one important exception: **drops are consumed**.
  If one dwarf picks up an XP orb or any other drop, it must disappear for the other. So pickups
  need ownership and removal sync, not just position sync.
- **Objectives are the hard part.** Examples the owner gave:
  - "Stand in a circle for a few seconds" objectives should **progress faster when both dwarves are
    in the circle**.
  - **The drill** (appears after a set time to advance to the next stage) requires **both dwarves
    to be present** to advance.
  - Newer reward/objective screens have not been tested at all yet.
- **Death and downed state:**
  - An **off-screen indicator** — a floating icon that always shows where the other dwarf is when
    they are outside the local camera view.
  - A **revive mechanic**: the surviving dwarf stands within a circle around the dead dwarf for
    roughly **5 seconds** to revive them.
- **Meta progression uses the shared real profile** — accepted. (The earlier save-isolation concern
  is therefore closed by owner decision: co-op runs may write to the normal profile.)
- **The host picks the mission**, and the client must **drop into the same mission**, with the same
  drill and same level state. This is the "settings adoption" problem, and the owner wants it fully
  automatic rather than matched by hand.
- **Scope for now: main missions only.** Other run types do not have to work yet.
- **Intended join flow (later):** the host picks a mission, the co-op partner **joins over Steam**,
  the partner presses **Ready**, and only then can the host start. So "ready" is a real gate, not a
  cosmetic button.

  This matches the automation findings nicely: on this profile the **only unlocked run type is the
  campaign Mission Road** (`UIChallengeSetButton_MissionRoad`), with Mastery, Endless, Anomaly and
  both fixed runs reported `[unavailable]`. So main missions are not just the wanted scope, they
  are the only reachable one.

## Test automation: getting both instances into a run without clicking

Starting a mission by hand in two windows is the main drag on iteration, and the mission road is
random per instance, so "pick the same mission twice" is not even reliable.

Candidate paths, best first:

- **`FixedRunManager.SetupFixedRun(FixedRunInstance, FixedRunData, EType, int)` is public**, and
  `DailyRun` / `WeeklyRun` are `FixedRunInstance` objects the game builds itself. Fixed runs are
  *seeded*, so a fixed run started identically on both instances gives identical settings **and**
  identical generation — this removes the manual mission matching problem at the same time as the
  clicking problem. `TryGetSavedFixedRun(EMissionType, int, int, out FixedRunInstance)` suggests
  fixed runs also persist, so a run can be resumed rather than re-created.
- **`RunSettingsManager.midRunSaveData`**: a mid-run save exists, so "continue run" may let a test
  resume the exact same cave instead of regenerating. Cheapest route to repeatable tests.
- **Synthetic input** (`SendInput` via PowerShell): drive Play → mission → drop in both windows
  from outside the game. No game internals and no risk to the game, but brittle against UI changes
  and animations. Good fallback if the fixed-run path resists.
- Unknown: the exact call chain from `UIFixedRunButton` / `UIPlaySelectForm` to the actual run
  start. That chain has to be traced before a `-coopauto` flag can be built.

### Traced (2026-10-17) — chain found, blocker identified

The mission-select wizard is public API on `DRS.UI.UIPlaySelectForm` (in `FundayFactory.UI`, base
class `UIForm` — a build reference is needed for it):

```
StartMainMissionsFlow() / StartFixedRunFlow() / StartEndlessFlow() / StartMasteryFlow()
PageFlowNext()                       <- the wizard's Next button
OnMissionNodeClick(MissionNodeState) / OnMissionSectorClick(...) / OnMainMissionSelect(EMainType)
OnBiomeNext(BiomeLevelData) / OnHazLevelNext(int) / OnClassPageNext(EDwarf)
TrySetPage(EPage) / BuildPageFlow() / SetupPageFlow(List<EPage>)
```

A `-coopauto` flag was implemented against this (see `CoopAuto.cs` in the plugin) and run on both
instances. Result:

- The form **is** found, but calling `StartFixedRunFlow()` on it throws `NullReferenceException`,
  and on one instance `PageFlowNext()` did nothing at all. Both are the signature of an
  **inactive, not-yet-initialised** form: `FindObjectsOfType(true)` returns it while the menu is
  still at the splash/main menu, and its injected fields are not wired until the Play menu opens.
- So the missing piece is **entering the Play menu**, not the wizard itself. The correct handles
  are `UISceneMenu.PlaySelectForm` (public getter) and `UIMenuSplashForm`; `UIManager` also
  exposes `PlaySelectForm`. `UISceneMenu` has no obvious "Play pressed" method — the buttons are
  wired as scene callbacks — so the entry point is probably on the splash form.

Two ways forward: call the splash/menu Play handler from the mod, or accept **one synthetic click**
to press Play and let the mod drive the wizard from there (the wizard calls are known to exist and
the fixed-run seed is date-derived, so both instances would land in the same run).

**Second attempt, with the missing link found — also failed.** `UIMenuSplashForm.OnPlayButton()` is
public and is the real Play button, so the chain is Play -> wizard. Driving it from the mod gives:

```
auto: find UIMenuSplashForm -> 1 found, first active=False
auto: step 1 - OnPlayButton()          -> NullReferenceException
auto: find UIPlaySelectForm  -> 1 found, first active=True
auto: step 2 - StartFixedRunFlow()     -> NullReferenceException
auto: step 3 - PageFlowNext()          -> NullReferenceException   (repeats)
```

Conclusions worth keeping:

- `FindObjectsOfType(true)` returns **inactive pre-instantiated form copies** whose injected fields
  are null; calling methods on those throws immediately. Always prefer an
  `activeInHierarchy` instance (the finder in `CoopAuto.cs` now does).
- Picking an *active* `UIPlaySelectForm` still throws from its own public methods, so the wizard
  depends on internal state that only the game's real button path establishes. **Calling the UI
  objects directly is not a viable automation route.**
- The remaining options are **synthetic input** (send a real click for Play, then drive the wizard
  with real input the way a player would), or hooking something the game already does
  automatically. Synthetic input is the pragmatic choice; `-coopauto` scaffolding in the plugin is
  reusable once the entry works.

### Third attempt: state-driven + real button invocation (2026-10-17)

This one works up to the run-type page. Findings, in the order they mattered:

1. **The boot splash needs a real mouse click.** For 150+ seconds the only active form was
   `UISplashForm` (publisher logo) while `UILoadingForm` / `UIMenuSplashForm` stayed inactive, even
   though the game was rendering fine (its tick counter kept advancing). `SendKeys` space/Enter did
   **nothing**; a real mouse click (`SetCursorPos` + `mouse_event` LEFTDOWN/LEFTUP) on the window
   centre advanced it immediately. So the launcher must click the window once after start.
2. **Do not drive by timing - drive by observed UI state.** An earlier version fired every step
   while the game was still on the logo. The current version reads which `UIForm` is active and
   reacts; that removed a whole class of silent failure.
3. **`UIMenuSplashForm.playButton.onClick.Invoke()` works** to leave the main menu. This is the
   in-process equivalent of a real click and is what reached the wizard.
4. **Wizard page 1 has no Next button - it offers run types.** Actual button names found:
   `UIMissionRoadButton_Elim/_Escort/_EggHunt`, `UIFixedRunButton_Daily/_Weekly`,
   `UISetProgressButton_Mastery/_Endless/_Anomaly`, `UIChallengeSetButton_MissionRoad`,
   `UIMasterySetButton_Weapons/_ClassMods/_Biomes`, `UIBackButton`, `UIMutatorSetEntry`, and
   `UIPlayCrumb` tabs.
5. **The daily and weekly fixed runs are LOCKED on this profile** - logged as
   `UIFixedRunButton_Daily[locked] UIFixedRunButton_Weekly[locked]`. Pressing a locked button does
   nothing, which is what made an earlier attempt loop forever with no state change. So the
   date-seeded daily run is **not** currently available as a test vehicle here.
6. `UIMissionRoadButton_Elim` exists but is **inactive** while the fixed-run/challenge page is
   showing, so a picker that requires `activeInHierarchy` falls through to the locked daily button.
   Navigating to the mission-road page goes through the crumb/tab buttons (`UIPlayCrumb`,
   `UIChallengeSetButton_MissionRoad`).

**Next step for automation:** invoke the mission-road tab/crumb to switch pages, then press the
Elimination mission-road button, and continue through the wizard. Everything needed is now mapped;
this is iteration, not discovery. The launcher script must also click the window once to clear the
splash.

### Fourth attempt: found the real button class (2026-10-17)

Two findings that matter more than anything above:

1. **The game's buttons are `DRS.UI.UIButton`, not `UnityEngine.UI.Button`.** `UIMenuSplashForm.playButton`
   is typed `UIButton`, and `UIButton` exposes its own public **`OnClick` UnityEvent**, plus
   `Interactable`, `IsAvailable`, `IsSelected`, `OnPointerDown/Up/Enter/Exit`, `OnSelect/OnDeselect`,
   and protected virtual `OnButtonClick()`. Invoking the *inner* `UnityEngine.UI.Button.onClick`
   (what the first attempts did) runs an event the game does not listen to, which is why pressing
   buttons appeared to do nothing. It also holds a `_ClickCoroutine`/`_HoldCoroutine`, so it does
   its own pointer handling rather than delegating to a plain Button.
2. **`IsAvailable` exposes per-profile unlock state**, and logging it settles the run-type page:
   ```
   UIBackButton UIChallengeSetButton_MissionRoad UISetProgressButton_Mastery[unavailable]
   UISetProgressButton_Endless[unavailable] UISetProgressButton_Anomaly[unavailable]
   UIFixedRunButton_Daily[unavailable] UIFixedRunButton_Weekly[unavailable] UIPlayCrumb
   ```
   On this profile **only the campaign Mission Road is unlocked** - Mastery, Endless, Anomaly and
   both fixed runs are `[unavailable]`. So the date-seeded daily run is genuinely off the table, and
   the campaign road is the only automatable route.

Current blocker: pressing `UIChallengeSetButton_MissionRoad` through `UIButton.OnClick` still does
not change the page. Remaining candidates, best first:

- **Compute the button's screen position from its `RectTransform` and click it with a real mouse
  event.** This is the most faithful option, it needs no assumptions about which event the game
  listens to, and we already know how to send real clicks (that is what clears the splash). The mod
  can log the coordinates; the launcher clicks them.
- Retry `UIPlaySelectForm.StartMainMissionsFlow()` / `PageFlowNext()` now that the form is known to
  be live; the earlier `NullReferenceException` was thrown while the form was still dormant, so that
  result is not conclusive.
- Drive `OnPointerDown` + `OnPointerUp` with a `PointerEventData`, since `UIButton` implements its
  own pointer handling.

Also worth noting for whoever picks this up: clicking the window centre to clear the splash can hit
menu content, so that click may be doing part of the navigation. A click targeted at a known-safe
point (or at a computed button position) would make the experiment clean.

### Two-instance launcher: two traps that cost a debugging cycle (2026-10-17, after a PC move)

Running the pair by hand is what the launcher exists for; it went wrong twice in ways worth writing
down, because both look exactly like a stalled game.

1. **Never click the BepInEx console window.** With BepInEx's console enabled
   (`[Logging.Console] Enabled = true`, the default), every instance opens a `ConsoleWindowClass`
   window titled `BepInEx <version> - DRG Survivor` alongside the game's `UnityWndClass` window.
   Clicking it while it has QuickEdit on puts it into mark/select mode, which **blocks the process's
   next console write and freezes the game**: ~180 MB working set, ~1 CPU-second, no further log
   lines, `Player.log` created but left empty. It is a hang, not a crash — no event-log entry, no
   dump, and the process eventually just exits. Fix both ends: set
   `[Logging.Console] Enabled = false` on the test install (the disk log and the mod's
   `coop-<role>.log` are enough for tests), and target the window to click **by class name** —
   `UnityWndClass` — never `Process.MainWindowHandle`, which can resolve to the console.
2. **`LogOutput.log` is append-only across runs and shared by both instances.** A stale run's lines
   read as current ones, and a stale `coop: coop loaded, role=..., gameRoot=...` line from a previous
   session can be mistaken for this session's. Two checks settle it: the file's last-write time, and
   the `gameRoot` in that line (a run from a different checkout prints a different path). The mod's
   own `coop-<role>.log` is per role and the only log worth trusting for a two-instance result —
   but BepInEx only writes it once the plugin is up, so its absence is itself a signal.

**Verified after the move** (build 23854500): host `net: host listening on udp 9050`, client
`net: peer connected id=0`, bidirectional counters climbing on both sides (`sent=307 recv=232` host /
`sent=239 recv=312` client at ~20 Hz), `bot=on` on both. One instance alone is unaffected — it
reaches ~1.3 GB and a normal tick rate, which is how the two traps above were told apart from a
genuinely broken build.

Still true from the earlier sessions: the run must be started by hand (the wizard is not automated),
so two clients still cannot reach a *run* unattended — this only proves the transport and the plugin
path on the new machine.

### Fifth: the real wizard sequence, captured by a human click-through (2026-10-17)

`-coopwatch` was built exactly for this: it logs the active form plus the wizard's active buttons and
their `UIButton.IsAvailable` state, and presses **nothing**. One instance was launched with it and a
human clicked all the way into a run. The whole sequence, in order:

```
UISplashForm                                  <- publisher logo; ignores keys, needs a real click
UIMenuSplashForm                              <- main menu; Play
UIPlaySelectForm   UIBackButton UIMissionRoadButton_Elim UIMissionRoadButton_Escort UIPlayCrumb
UIPlaySelectForm   UIBackButton MissionSectorButton_1..5 MissionGateButton_1..3
                                (sector 4,5 and gate 4 report [unavailable]) UIPlayCrumb, UIPlayCrumb (1)
UIPlaySelectForm   UIBackButton ClassSelectButton_Scout/_Gunner/_Engineer/_Driller UIPlayCrumb (1..3)
UIPlaySelectForm   UIBackButton HazLevelButton, HazLevelButton (1), HazLevelButton (2) UIPlayCrumb (1..5)
UILoadingForm
GameController.OnCoreRunStarted player=True
map: rocks=5/81 fingerprint=000000000000000000000000000000000000000000000000000000000001001000000010000000011
map: settings biome=BiomeLevelData mission=Campaign mainMission=Elimination hazard=0
```

What this settles, and what it changes:

- **There is no Next button anywhere in the wizard.** It advances by *selecting content*, in this
  order: mission type → sector/gate → dwarf class → hazard → loading. So `DriveWizard()`'s
  `next / start / confirm / continue / drop` fallback is unreachable and should be deleted, not left
  in place as a guess.
- **The sector/gate page needs two selections.** A sector *and* a gate are active in the same
  snapshot, so the old "press the first sensible button every step" loop would press the same sector
  over and over. The driver needs an ordered plan with a progress index.
- **Button names accumulate Unity clone suffixes.** `UIPlayCrumb`, `UIPlayCrumb (1)`,
  `UIPlayCrumb (2)` … so exact name matching silently misses duplicates. Match on the base name with
  any trailing `" (n)"` stripped.
- **Deterministic picks are what makes two instances meet.** Both instances share the real profile, so
  "lowest available index", the same class and the same hazard put them in the same run — which is
  what the shared-cave work needs. (`hazard=0` was simply the first hazard button.)
- **A ready-made assertion.** `map: seeds Random=… ` together with
  `map: rocks=N/81 fingerprint=<81 bits>` and `map: settings biome/mission/mainMission/hazard` is
  exactly what a two-instance test should compare, and it needs no new plumbing.
- **Still a guess:** whether the sector or the gate must be clicked *first* on that page. Both are
  visible at once and the 2 s snapshots cannot show which the human hit first. The driver assumes
  sector-then-gate and logs every press, so the next unattended run will show if the order is wrong.

### First unattended attempt: the run-type tab needs a real pointer click (2026-10-17)

With the driver in place, a two-instance `-coopauto` run gets a long way and then stops at exactly the
wall the fourth attempt hit - but this time with usable evidence:

- **Clearing the splash, pressing Play and reaching the wizard all work.** Play is
  `pressing playButton 'Button_Cut_Play'`, after which the wizard appears. So `UIButton.OnClick.Invoke()`
  is a working mechanism for at least that button.
- **The wizard's *landing* page is the run-type list, not the mission list.** The human capture starts
  at `UIMissionRoadButton_Elim / _Escort` because the human had already clicked past this page. The
  landing page is: `UIBackButton UIChallengeSetButton_MissionRoad UISetProgressButton_Mastery[unavailable]
  UISetProgressButton_Endless[unavailable] UISetProgressButton_Anomaly[unavailable]
  UIFixedRunButton_Daily[unavailable] UIFixedRunButton_Weekly[unavailable] UIPlayCrumb`.
- **Pressing `UIChallengeSetButton_MissionRoad` through `OnClick` does not change the page.** The log
  shows the press being issued over and over (via the driver's logged fallback) with the page never
  changing - the fourth attempt's result, reproduced with the one mechanism now known to work for Play.
  So `OnClick` is sufficient for some buttons and not for this tab.
- The driver consumed the tab as `plan[0]` and then stalled on `plan[1]` (`UIMissionRoadButton_`),
  because the page it expected never appeared. Feeding it a fallback press did not help; the page has
  to actually change.

Next step, in the order the evidence points:

1. **A real pointer click on the button.** Both the splash and Play behave correctly when driven by OS
   mouse events, and the fourth attempt already ranked "compute the button's screen position from its
   `RectTransform` and click it with a real mouse event" first. The mod can log the rect; the launcher
   clicks it. This is the most faithful option and needs no assumption about which event the game uses.
2. `OnPointerDown` + `OnPointerUp` with a `PointerEventData`, since `UIButton` implements its own
   pointer handling and holds `_ClickCoroutine` / `_HoldCoroutine`.
3. A real click on the *crumb* (`UIPlayCrumb`) rather than the set button, since the crumb may be the
   control that actually swaps the page.

### Solved: the wizard is driven by handler methods, not by button clicks (2026-10-17)

A second unattended run pinned it down. Two presses were issued through `UIButton.OnClick` and the log
shows plainly that neither moved the page, while one *method* call did:

```
18:04:36  pressing plan[0] UIChallengeSetButton_MissionRoad   (OnClick)  -> page did NOT change
18:04:38  nudge - calling StartMainMissionsFlow()                        -> page DID change
18:04:40  pressing plan[1] UIMissionRoadButton_Elim           (OnClick)  -> page did NOT change
```

- **`UIPlaySelectForm.StartMainMissionsFlow()` works** once the form is live. This is the transition the
  fourth attempt could not make: it called `StartFixedRunFlow()` on a *dormant* form and got a
  `NullReferenceException`, and concluded the wizard could not be driven. It can - the form just has to
  have been opened by Play first.
- **`OnClick` is inert for the wizard's selection buttons.** It works for `playButton` and it does not
  work for `UIChallengeSetButton_MissionRoad` or `UIMissionRoadButton_Elim`. So the earlier conclusion
  "`UIButton.OnClick` is the only thing that works on these screens" is wrong - it is right for the main
  menu and wrong for the wizard.
- **The real handlers are public methods on `UIPlaySelectForm`** (`DRS.UI`), each taking the thing to
  select rather than relying on a button event:

  ```
  StartMainMissionsFlow()                          <- run type;  PROVEN to advance the page
  OnMainMissionSelect(EMainMissionType)            <- mission within the road (Elimination/Escort)
  OnMissionSectorClick(MissionSectorState)
  OnMissionNodeClick(MissionNodeState)
  OnBiomeNext(BiomeLevelData)
  OnHazLevelNext(int hazLevel)
  OnClassPageNext(EDwarf)
  PageFlowNext()
  ```

  The three that take objects (`MissionSectorState`, `MissionNodeState`, `BiomeLevelData`) need the live
  state obtained from the page rather than constructed; the enum/int ones (`EMainMissionType`, `EDwarf`,
  `hazard`) do not. **This is the shape of the fix**: call these handlers in wizard order.

- **The click-coordinate fallback does not work yet.** The logged point for the tab was
  `clientx=-11 clienty=720 screensize=1280x720` - negative and exactly the screen height, i.e. nonsense,
  so treating an overlay rect's world position as client pixels is wrong here (layout group, canvas
  render mode, or a rect that is not the visual element). Do not use that path until the coordinates are
  right; the handler route above is the better one anyway.

Also worth noting: `UIMissionRoadButton_Escort` was `[available]` in the human capture but
`[unavailable]` in this run, and `MissionSectorButton_4/5` were unavailable in both. So the mission
road's availability is state-dependent, and a driver must pick *an available* option rather than a
fixed one.

### Cpp2IL dummy assemblies: what they do and do not give you (2026-10-17)

To read what a game method actually *does*, the interop assemblies are useless - they are invoke stubs
with signatures only. The next step up is Cpp2IL's dummy assemblies, which BepInEx can keep:

```
; BepInEx/config/BepInEx.cfg
[IL2CPP] DumpDummyAssemblies = true
```

Then stash `BepInEx/interop` (rename it, do not delete - if regeneration fails you want it back) and
relaunch once: Cpp2IL re-runs, and the dummies land in `BepInEx/dummy/`. On this build that produced
**129 files**, including `Assembly-CSharp.dll` (3.0 MB) and `FundayFactory.UI.dll` (75 KB). Interop
regenerated cleanly alongside them (132 files) and the chainloader still completed, so this is safe to
do on the test copy. Decompile a single type rather than the whole assembly:
`ilspycmd -t DRS.UI.UIPlaySelectForm BepInEx/dummy/Assembly-CSharp.dll`.

**But the bodies are empty.** The dummies are better than interop, not a decompilation: Cpp2IL could
not recover the IL, so every method body is `{ }` (`StartMainMissionsFlow() { }`,
`BuildPageFlow() { return null; }`). What they *do* give you, accurately, is:

- **signatures**, including the argument types that actually matter here;
- **enums with their members**, which is where the wizard order below comes from;
- **field offsets** (`[FieldOffset(Offset = "0x18")]`) and **nested types**;
- **the native address of every method** (`[Address(RVA = "0x9764A0", Offset = "0x9758F0", Length = "0x7A")]`),
  which is the entry point for real body work in Ghidra/IDA against the game binary (`GameAssembly.dll`).

**The bodies turn out not to be needed for this task.** `StartMainMissionsFlow()` demonstrably moved
the wizard page while its dummy body is empty - so these are ordinary managed methods that can be
called by name, and the game does the work natively. Knowing the *signatures* was the whole
requirement; that is the lesson worth keeping.

Practical gotcha: redirecting `ilspycmd` output from PowerShell writes **UTF-16**, which reads as
`u s i n g   S y s t e m ;` in every other tool. Pipe through `Out-File -Encoding utf8`.

### The wizard's page order, from the game's own enum

`DRS.UI.UIPlaySelectForm` declares a nested `EPage`, which is the authoritative sequence:

```
MISSION_TYPE, MAIN_MISSION_TYPE, MASTERY_TYPE, ANOMALY_TYPE,
MISSION_SECTOR, MISSION_NODE, CHALLENGE, BIOME, HAZ, CLASS, CLASS_ARTIFACT
```

So the mission road page order is **run type → main mission type → sector → node → challenge → biome →
hazard → class**, and the `On*` handlers line up with it one for one:

```
StartMainMissionsFlow()          -> enters the campaign flow (MISSION_TYPE);  PROVEN to work
OnMainMissionSelect(EMainMissionType)   -> MAIN_MISSION_TYPE (Elimination / Escort)
OnMissionSectorClick(MissionSectorState) -> MISSION_SECTOR
OnMissionNodeClick(MissionNodeState)     -> MISSION_NODE   (the "MissionGateButton" page)
OnChallengeSetNext(ChallengeDataSet) / OnChallengeNext(ChallengeData)
OnBiomeNext(BiomeLevelData)              -> BIOME
OnHazLevelNext(int hazLevel)             -> HAZ
OnClassPageNext(EDwarf)                  -> CLASS
```

This corrects the plan order guessed earlier (which had sector-then-gate and no challenge/biome step),
and it means the driver should follow `EPage`, not the button layout. All of these types are present in
the dummy `Assembly-CSharp.dll` (`MissionSectorState`, `MissionNodeState`, `BiomeLevelData`, `EDwarf`,
`EMainMissionType`), so the remaining work is obtaining the live state objects for the two that take
one, not discovering the API.

### Automated: the wizard is now driven with no human input (2026-10-17)

Verified in a two-instance `-coopauto` run. Both instances walked the whole wizard unattended and
landed in **the same cave**, with identical map fingerprints and no clicks from anyone:

```
plan[1] UIMissionRoadButton_Elim  -> plan[2] MissionSectorButton_1 -> MissionNodeButton_01
     -> UISelectable_Hex_ClassArtifact -> ClassSelectButton_Scout -> HazLevelButton
auto: IN RUN after 18 steps - automation done          (both instances)
map: rocks=3/81 fingerprint=000000000000000000000000000000000000000000000000001000000000000000000010000000001
map: settings biome=BiomeLevelData mission=Campaign mainMission=Elimination hazard=0
```

Two findings that made it work, both counter-intuitive:

1. **The button click path is `UIButton.OnButtonClick()`, not `OnClick`.** It is a `protected virtual`
   that each wizard button overrides - `UIMissionSectorButton.OnButtonClick()` calls the form's
   `OnMissionSectorClick` with *its own* `sectorState`, so the state never has to be fetched. The
   public `OnClick` UnityEvent is a different thing and is simply not wired on these buttons: invoking
   it changes nothing. Nice detail from the dummy assembly: `MissionSectorState` holds
   `List<MissionNodeState> Nodes` and `MissionNodeState GateState`, so the "gate" is itself a node.
2. **`StartMainMissionsFlow()` must be called at most once.** Calling it again while already past the
   first page restarts the flow from the top; a driver that fires it whenever the page changes will
   walk the plan and then be dragged back to the first page every time, which is exactly what the log
   showed before the fix.

### Three launcher/driver bugs worth not repeating (2026-10-17)

All three produced symptoms that looked like the *game* misbehaving:

- **`OnClick` vs `OnButtonClick`** (above). `OnClick` works on `playButton` and does nothing on the
  wizard, so "the button press did nothing" was really "the wrong event was invoked".
- **A nudge that fired too often** (above). A repeated `StartMainMissionsFlow()` silently resets
  wizard progress.
- **Splash detection built on the absence of evidence.** `coop-click.ps1` decided it was past the
  splash if the last `auto:` line was *not* a splash line. But the plugin logs
  `auto: armed, watching UI state` before it has looked at any form, so the loop declared success
  immediately, sent no click at all, and both instances sat on the publisher logo for 61 steps. Now it
  requires **positive** evidence (`UIMenuSplashForm`, `pressing playButton`, `wizard page`, `IN RUN`).
  Rule worth keeping: a wait loop should stop on proof of success, never on lack of proof of failure.

Useful side effect of the fix: `-coopauto` now removes the hand-clicking that every earlier milestone
needed, so world-state sync can be measured on a run that starts itself.

Profile note: on this run only sector 1, only `Scout` and only `UIMissionRoadButton_Elim` were
available; everything else reported `[unavailable]`. Picking "first available" is therefore the right
strategy, and since both instances share the profile they pick the same thing and meet in one run.

### Steam must be running, or the game boots to nothing (2026-10-17)

Cost an hour, so it goes first. With Steam closed, the test copy still starts: BepInEx loads, the
plugin loads, every Harmony patch installs cleanly, and the log looks healthy. But the game then sits
with **no UI form at all** - `auto: step 202 - no active form, waiting` for four straight minutes -
and never reaches the splash or the menu. `coop-click.ps1` clicks 45 times into the void.

The misleading part is that nothing reports an error: no exception in the BepInEx log, no crash, the
process stays alive, and the only symptom is that the automation says "no active form". If a run ever
stalls like that again, **check that Steam is running before suspecting the mod**.

### Enemy identity, measured: the hooks are not complete yet (2026-10-17)

Stage 1 step 1 (assign ids and compare against the spawner's own list) was built to answer exactly one
question before anything is sent over the wire: do the hooks see every enemy? They do not.

```
host:   reg=51  vs live enemies=61  | spawnAt=10  onSpawn=80  dup=10  noptr=0  die=19  despawn=0  recall=0
client: reg=44  vs live enemies=54  | spawnAt=10  onSpawn=72  dup=10  noptr=0  die=18  despawn=0  recall=0
```

What the numbers already say (records in a real run, two instances, no clicks):

- **`EnemySpawner.SpawnAt` chains into `Enemy.OnSpawn`.** Every one of the 10 `SpawnAt` calls arrived
  at an enemy already registered (`dup=10`), so `OnSpawn` is the hook that actually fires per enemy;
  `SpawnAt` is the caller-side entry. Patch both only if the caller side is needed for suppression.
- **`reg` is below the live count**, by 10 on both sides, so some enemies reach the spawner's list
  without passing through `OnSpawn`, or a pooled enemy is reused after we unregistered it (the pointer
  is the same for a reused pooled object - `ByPointer` keys on the native pointer). Identify which
  before assigning network ids: an id that the peer never learns about is a silent desync.
- **Death goes through `Die`, not `DeSpawn`/`Recall`** (`die=19`, the other two 0). `Enemy.Die` is
  therefore the only unregister path worth wiring now.

**Resolved, and the gap is narrower than it first looked (2026-10-17).** Rather than keep hunting the
one missing hook, the registry is now completed from the spawner's own list: each tick, any enemy on
`EnemySpawner.Enemies` without an id gets one, and a counter records how often that was necessary. The
list the game maintains becomes the authority, so completeness no longer depends on having found every
hook. Verified over a five-minute run, both instances:

```
host:   enemies=502  reg=502  peak=505  |  onSpawn=1165  dup=10  die=598  despawn=65  rec=10/1
client: enemies=547  reg=547  peak=547  |  onSpawn=1169  dup=10  die=582  despawn=40  rec=10/1
```

`reg` equals the live count exactly on both sides, so an id can no longer go on the wire for an enemy the
peer never learns about.

`rec=10/1` is the more interesting number. The sweep had to act **once**, picking up ten enemies, and
never again across 1165 spawns and 598 deaths. The guess recorded above - ongoing pool reuse - is
therefore **wrong**: the ten are a one-time, start-of-run population that the hooks never see (a prewarmed
pool fits, but that is not proven). Chasing it further is not worth it while the sweep closes it, and the
counter will shout if the behaviour ever changes.

**Correction:** the bullet above says death only goes through `Die`. That held in the short run it was
measured in, but over a longer run `DeSpawn` fires too (`despawn=65` against `die=598`). Both are wired,
so nothing is lost - but "only `Die`" was too strong a claim from too short a run.

### Suppressing `SpawnAt` does not silence a client: the wave path bypasses it (2026-10-17)

First attempt at stopping the client from running its own waves was a prefix on `EnemySpawner.SpawnAt`
returning false on a client. Measured result - it catches only a sliver:

```
host:   enemies=367  reg=367  |  spawnAt=10  onSpawn=943  sup=0   rec=10/1
client: enemies=193  reg=193  |  spawnAt=8   onSpawn=804  sup=8   rec=0/0   noptr=8
```

`sup=8` shows the refusal works, and `noptr=8` is its harmless side effect (the postfix then runs with a
null result and counts a missing pointer). But the client still ended up with **193 enemies**, every one
of them reported by `OnSpawn`: **943 / 804 `OnSpawn` calls against 10 / 8 `SpawnAt` calls.**

So the wave machinery does not go through `SpawnAt` at all. `EnemySpawner.Spawn(SpawnData, ...)` and
`Spawn(Enemy prefab, int count, ...)` are separate entry points, and the claim repeated in this file and
in the plan - "`SpawnAt` is the single spawn choke point" - is **wrong**.

Consequence: suppression has to cover every spawner entry point, or move to `OnSpawn`, which is the one
hook that does fire for every enemy. The same correction applies to the plan, where the network spawn
message was going to be driven off `SpawnAt` for the same reason.

### Client spawner silenced - all four entry points, verified (2026-10-17)

The refusal now covers every spawner entry point, and the signatures below are not guesses: Harmony logs
what it patched, so this is what the game actually has.

```
EnemySpawner.SpawnAt(Enemy, Vector3, EnemySpawner.EEnemyScaleMode)
EnemySpawner.SpawnAt(EEnemy, Vector3, EnemySpawner.EEnemyScaleMode)
EnemySpawner.Spawn(SpawnData, EnemySpawner.EEnemyScaleMode)                     <- bypassed SpawnAt
EnemySpawner.Spawn(Enemy, Int32, Boolean, EnemySpawner.EEnemyScaleMode, Int32)
```

Measured on a client, whole run: `enemies=0 peak=0`, while the host ran 296-315 of its own. The client
stayed healthy - the local position kept advancing between samples (`(2.6,0.0,-11.7)` -> `(11.9,0.0,-1.4)`)
- and there were **zero exceptions** in either BepInEx log.

That last point was the real question: the list-returning `Spawn(SpawnData, ...)` is now skipped entirely,
so it returns null, and its callers do not dereference it. The game tolerates a client whose wave
machinery produces nothing at all, which is a stronger result than expected - no `SuppressSpawnCount`, no
`RecallAll`, no half-measures needed.

The client is therefore a clean slate for host-authoritative enemies, which is what stage 1 needed.

Confirmed signatures, read from the log rather than guessed (Harmony prints what it patched):

```
EnemySpawner.SpawnAt(Enemy, Vector3, EnemySpawner.EEnemyScaleMode)
EnemySpawner.SpawnAt(EEnemy, Vector3, EnemySpawner.EEnemyScaleMode)
Enemy.OnSpawn(EnemySpawner, ObjectPool`1, Int32, EnemySpawner.EEnemyScaleMode, Single x6)
Enemy.Die(EDamageType, Int64, Boolean) | Enemy.DeSpawn() | Enemy.Recall()
```

The nested enum really is `EnemySpawner.EEnemyScaleMode`, and `OnSpawn`'s six `Single` parameters are
the stat modifiers.

### A blocked run: the level-up screen stops everything (2026-10-17)

A screenshot of both windows at the end of a run shows both sitting on **"LEVEL AUFSTIEG"** - the
reward-choice screen - with identical state. Two facts come out of that:

- The XP mirroring and the level-up barrier work: both dwarves levelled at the same time and both were
  held at the choice, which is what the barrier was built for.
- **Nothing dismisses the screen, because the automation deliberately stops.** `CoopAuto` sets its
  done flag the moment it enters a run: the host log holds 28 `auto:` lines in total and the last one
  is `auto: IN RUN after 19 steps - automation done` - nothing follows. Meanwhile the game pauses the
  run while the reward choice is open, so the run freezes there. Two independent measurements confirm
  it is the pause and not the sync code: the local position is frozen (`pos=(6.6,0.0,10.0)` across many
  samples) and the enemy counts are frozen (`enemies=61`, `reg=51`) while the bot's own step counter
  keeps climbing (`steps=10851 -> 11331`) - `LateUpdate` still runs, game time does not.
  So the fix is not "teach the driver about another page"; it is that the driver must keep serving
  modal screens after the run has started, instead of retiring.

This is now the first blocker: no enemy/loot/terrain measurement is meaningful until a run can get
past its first level-up unattended.

**The names, captured from a run** (the driver now keeps watching instead of retiring once in a run,
which is what produced them):

```
auto: watch: active=UICoreForm        <- the in-run HUD
auto: watch: active=UILevelUpForm     <- the screen that blocks everything
```

Frozen confirmed independently of the driver: on *both* instances the local position is byte-identical
across four consecutive samples (`(-11.7,0.0,-2.5)` on the host, `(-1.1,0.0,-11.9)` on the client) with
the enemy count constant, while `auto: watch: active=UILevelUpForm` is the last state observed. The game
really does pause the run on that screen.

`DRS.UI.UILevelUpForm` carries `skillButtons : UISkillButton[]` and `skillButtonsLeftToRight` for the
cards, `rerollButton : UIButtonPrice` for "swap all", plus `onFinishedCallback` and a `LevelUpManager`
with an `IEStartFlow` coroutine.

**Correction to an earlier claim in this file:** `UISkillButton` is declared `class UISkillButton :
UIButton`, so the cards are *not* structurally invisible to a `UIButton` enumeration - an earlier
revision of this note said they were and that was wrong. The reason nothing pressed them is simply that
the driver had already retired before any of this code ran. Worth keeping straight, because the fix
differs: it is "keep serving screens after the run starts", not "learn a second button type".

The chosen route is to press a card (any one completes the local choice; the XP barrier then waits for
the peer). It targets `UISkillButton` specifically rather than "the first pressable button on the form",
because the same screen carries the reroll control - a `UIButtonPrice` - and picking that would spend
currency to reroll the offer instead of accepting it.

The alternative, if pressing a card turns out not to complete the choice, is to finish through
`LevelUpManager`, which owns the flow and the finish callback and so bypasses the presentation.

### Resolved: the level-up no longer freezes a run (2026-10-17)

Pressing a card does not answer the choice. A measured run pressed `SelectableWindow_SkillSelect`
through the ordinary `UIButton` path - the same path that works on the wizard - and the screen stayed
up with the run still frozen. The form's own API says why: the button click lands in `OnSkillSelected`,
which only *previews* a card, while `OnSkillChosen` is the one that commits. Invoking `OnSkillChosen`
directly threw `TargetInvocationException`, and that failure was invisible for one round because the
patch was reporting `e.Message` and discarding `e.InnerException` - a reflection call hides the real
error there. **Log the inner exception whenever a reflected call can throw.**

What works is `LevelUpManager.OnLevelUpFinished()` - the entry point this module already uses to release
the XP barrier, which made it the one call in that area known to move the flow on. The driver now calls
it whenever `UILevelUpForm` is open, and the barrier still holds until the peer has answered too.

Verified in a run: `auto: level-up finished through LevelUpManager` on both instances, six times over,
with the local position changing between samples (`(1.7,0.0,-11.9)` -> `(11.9,0.0,-1.5)` ->
`(4.9,0.0,11.0)`) and enemy counts rising to 561/464. A run now survives repeated level-ups with no
human present, which is what every later measurement needs.

**Limitation, deliberately accepted:** the dwarf takes no reward from those level-ups. That is fine for
a test bot whose job is to keep a run alive, but it is not what a player wants - so this is an
automation-only shortcut, not the co-op behaviour. A real fix should go through the reward screen.

Also worth noting from the same run, because it is the next problem: host and client enemy counts have
diverged badly by this point (561 against 464). Two instances now run long enough for that to matter,
which is exactly what stage 1 exists to fix.

### A stale binary looks exactly like a fix that does not work (2026-10-17)

The first attempt to test the level-up fix silently measured the *previous* build: `Copy-Item` failed
with the DLL held open by a leftover game process, and the script carried on and launched anyway. Any
conclusion drawn from that run would have been wrong, and it would have looked like the fix failing
rather than the deploy failing.

The deploy step now kills the game, retries the copy until the file is not locked, compares source and
destination hashes, and **aborts instead of running a stale binary**. Keep that check when running
unattended: a build that never reached the plugins folder produces the same evidence as a broken change.

### Two things that now work, and one that needs tolerating

- The explicit `UISelectable_Hex_ClassArtifact` plan step is pressed by name (`plan[4] ... pressed`),
  so the artifact page no longer depends on the fallback - when it appears where the plan expects.
- **The page order varies.** On this profile the wizard went node -> class -> artifact -> hazard, not
  node -> artifact -> class as the plan lists, and the fallback absorbed it. The plan should accept
  both orders rather than assuming one.
- **Determinism extends to spawning.** Both instances created the same first enemy at the same
  coordinates - `+id=1 type=LOOTBUG/BASE pos=(82.8,0.0,24.2)` on host and client alike - because the
  seed is forced and the bots act identically. Tempting, but the counts already diverge (61 vs 54), so
  identity must still come authoritatively from the host; matching by type+position would work only
  until the first difference.

### Lesson: one bad patch must not take the mod down (2026-10-17)

`[HarmonyPatch(typeof(EnemySpawner), "SpawnAt")]` with no argument types throws
`AmbiguousMatchException` on an overloaded method. Because patch installation shared a `try` with
plugin startup, that single exception skipped `AddComponent<CoopTick>()` and `CoopNet.Init()` - the mod
was **completely dead** and the only trace was in the BepInEx log (`LogOutput*.log`, which is *not*
`coop-<role>.log`): the per-instance role log simply stayed empty, which reads like "BepInEx did not
start".

Fixed twice over: enemy hooks resolve and patch each target individually with its own log line, and
`ProbePlugin.Load()` now installs patches in their own `try` so a patch failure degrades instead of
disabling. Rule worth keeping: **never let patch installation share a `try` with startup, and read the
BepInEx log before concluding anything from the absence of a role log.**

## Next phase: world-state sync (enemies, pickups, terrain)

The puppet is presentation only. The cave, the bugs and the loot are still per-instance, which is
the remaining gap between "two dwarves see each other" and "two dwarves play together".

Survey of what the game gives us (from the IL2CPP interop stubs):

- **`Enemy.id` is *not* an instance id — it is the enemy's type.** `id` (and the `ID` property) is
  typed `EEnemy`, a 45-value enum (`GRUNT0`, `FAST_GRUNT`, `MACTERA_SEEKER`, `LOOTBUG`,
  `BOSS_DREADNOUGHT`, `COCOON`, `EXPLODER_CRYO`, …). This settles the open question flagged in the
  earlier survey: a pooled enemy is **not** individually identifiable, so the sync layer **does**
  need its own network ids. `id` is what tells the client *which* prefab to materialise.
- **The spawner exposes public spawn/despawn API**, so a client can materialise host-authoritative
  enemies without reaching into internals: `SpawnAt(EEnemy enemyId, Vector3 position,
  EEnemyScaleMode scaleMode)` and the `SpawnAt(Enemy prefab, …)` overload, plus `Spawn(SpawnData,
  EEnemyScaleMode)`, `SpawnWave(FixedWaveState)`, `AddFixedWave(...)`, `OnStageBegin()`,
  `OnStageEnd(CoreLevelEndArgs)`, `OnEnemyDeath(EnemyDeathArgs)`, `RecallAll()`,
  `GetLiveSpecialEnemies(EEnemyType)`, `SuppressSpawnCount(float duration, float regainDuration)`,
  `AddGrowth(float hpMod, float dmgMod, float speedMod)`.
  The live registry is `enemies` (`List<Enemy>`) — the field the probe already samples — and every
  enemy carries a back-reference, `Enemy.enemySpawner`, so a generic "which enemy is this" walk
  does not need a global lookup.
- **Fields worth putting on the wire:** `currentHp` (on the `Entity` base), `GetHealthNormalized()`,
  `hasAgent`/`agent` (NavMeshAgent — the thing to disable on a mirrored enemy), `baseScale`/
  `scaleMod`, `enemyGfx`/`GFXContainer`, `state` (`EEnemyState { INACTIVE, ACTIVE, KNOCKBACK,
  FEARED }`). Note `MaxHp` / `Damage` / `MoveSpeed` / `Range` / `AttackSpeed` are `EnemyStat`
  objects with their own modifier handling (see `EnemyStat.cs` / `EnemyStatHandler.cs`), not plain
  numbers — read them through the stat handler rather than expecting a float.
- **`Enemy` exposes events we can hook instead of polling:** `OnDeath`, `OnTookDamage`,
  `OnHealed`, `OnSetTargetable`, `OnAttackFrame`, `OnKnockback`. `OnDeath` is the cheap way to
  replicate kills.
- **`EnemySpawner` owns the wave machinery:** `enemies` (live registry), `enemyPrefabs`,
  `poolDictionary`, `liveElites`, `liveBosses`, `levelWaves`, and spawn bounds
  (`spawnMinX/MaxX/MinY/MaxY`). Spawning goes through an `ObjectPool`, never `Instantiate`.
- Enemy stats arrive via `_baseMaxHp`, `_baseMoveSpeed`, `_baseDamage`, `hazardHpScale`,
  `hazardSpeedScale` — relevant because hazard is one of the settings that must match.

Proposed shape (host-authoritative, matching the rest of the mod):

1. **Suppress the client's own spawner** so it does not run a second, divergent wave simulation.
2. Host broadcasts enemy state **only for enemies near the client's dwarf** (interest management,
   ~10 Hz, batched per packet) — the swarm peaks around 260 entities, so a full broadcast is off
   the table. The game already ships a KDTree (`PhysicsSimulation`) if a radius query is wanted.
3. Client spawns a *visual* enemy per received id from the same prefab table and lerps it.
4. Client damage is reported to the host ("I hit id X for N"), the host applies it, and deaths
   come back through `OnDeath`. Never let both sides own enemy HP.
5. Pickups (`PickupSpawner`) and mined terrain (drops from `MapGenerator`/tile state) follow the
   same pattern afterwards, in that order — they matter less than the bugs.

This is the largest remaining piece; it should be its own work item with the same discipline as
the player sync above (measure on two instances, log both sides, do not claim without a run).

## Milestone: shared XP and a synchronised level-up pause

Also verified live (build 23854500, 2026-10-17), and confirmed by the owner in game:

- **XP is shared, not per-player.** `Player.GainXp(float amount, bool scaleByXpGain = true)` is the
  single XP entry point; mirroring each gain to the peer and applying the peer's gains with
  `scaleByXpGain: false` keeps both dwarves on the same total. Measured: host
  `lvl=4 xp=28.0 total=153.0` (`sharedOut=95 sharedIn=58`) and client
  `lvl=4 xp=28.0 total=153.0` (`sharedOut=58 sharedIn=95`) — identical, since each total is its
  own gains plus the other's (95+58).
- **Level-up choices pause both games until both players have picked.** `LevelUpManager` runs one
  flow over a queue of level-ups (`levelUps`, `StartFlow` → `HandleLevelUps` →
  `OnLevelUpFinished`). The mod releases `OnLevelUpFinished` only when both sides report their
  picks are done, holding the flow open in the meantime. Logged hold: 15:18:27.890
  "holding until remote picks" → 15:18:32.007 "remote picks done" → "released" (~4.1 s).
  A 45 s timeout releases the hold so a lost peer cannot soft-lock the run.
- Useful details found while building this: `Player.currentXp`, `totalXp`, `currentLevel` are
  public fields and directly writable; `Player.blockLevelupScreen` exists but was not needed;
  `CoreGameEvents.OnPlayerXpGain` / `TriggerPlayerXpGain(PlayerXpGainArgs)` is the global XP
  event if an observer is preferred over patching `GainXp`; the game already ships a dormant
  `Player.RemoteXPPickUp(Vector3, float)` — unused, but evidence the game was once designed to
  have remote players.

## Milestone: both players visible in one shared cave

Verified in a live two-instance run (build 23854500, 2026-10-17):

- **Map sync works.** Both instances seed `UnityEngine.Random` to a shared value (20261017)
  in a `MapGenerator.CreateMap` prefix; map fingerprints came back **identical (0/81
  samples differ)**, and the two screenshots show the same terrain.
- **Players see each other.** Each instance clones the local player's visual subtree,
  positions it at the received remote coordinates, and both players confirmed seeing two
  dwarves in the same cave. Log evidence: `puppet: spawned #2 renderers=9 nullMeshes=0`,
  `pos=(-11.5,0,-3.5)` / `puppet pos=(-11.5,0,-3.5)` on the other side.
- **Root cause of the earlier invisible puppet:** the clone was taken from the **menu**
  player and never rebuilt (menu model = 4 renderers; in-run dwarf = 9 renderers). Fixing it
  was simply rebuilding the puppet when the run starts. An earlier theory that
  `FSG.MeshAnimator` left `sharedMesh` null was **wrong** — `nullMeshes=0` both before and
  after, and `meshesCopied=0`; that copy code is dead weight and should be removed.
- Transport sustained throughout: ~3200 packets each way, ~20 Hz, ~90 s.

Still open at this milestone: the puppet is **static** (no walk animation), enemies are not
synchronised, XP/level-ups are per-instance, and the two runs still had to be started with
matching settings (the hazard is broadcast but the client force-path was not exercised).

## Measured co-op numbers (real run, build 23854500)

From the in-game probe during a full normal mission (~5 min):

- **Live enemies ramp from 9 to a peak of 261** and stay at 220–261 late in the run.
  Progression sampled: 9, 11, 13, 16, 20, 25, 38, 57, 101, 124, 148, 189, 226, **261**.
- `liveElites` peaked at 1; `liveBosses` 0 (standard mission, not a boss run).
- Enemies are readable per entity, including prefab name:
  `enemy0 name=Lootbug(Clone) pos=(7.2,0.0,94.5) hp=80 alive=True`.
- Player: HP 210 → 220, **15** HP-drop events, positions tracked continuously, 0 at death.
- Lifecycle hooks confirmed: `GameController.OnCoreRunStarted` then `StartGame` on drop-in;
  `enemies=0` after extraction.

**Design constraint this sets:** naively syncing ~260 entities at 20 Hz is ~5k entity updates
per second per client. The entity layer therefore needs **interest management plus
priority/delta encoding**, not a full-state broadcast. (The game itself ships a KDTree used
by `PhysicsSimulation` / `PopulateKDTreeDataJob`, which is a candidate spatial index to reuse.)

**Dead end recorded:** `AI_Manager._units` is *not* the swarm registry — it stayed empty for a
whole run and its `Update` patch never fired, so the manager is inactive/unused in normal play.
The real registry is `EnemySpawner.Enemies` (`List<Enemy>`), reached via
`GameController.enemySpawner`.

## Stand-spot problem (measured, solved by self-check)

Goal was a fixed viewpoint for comparable screenshots. Measured facts, one per candidate spot:

- **Prefab origin `(0,0,0)`**: dead. 535 enemies on the list, none visible or reachable — the
  origin is inside rock/outside the cave.
- **Game-assigned spawn (landing pod)**: dead and worse — the dwarf is trapped in the pod's
  collider and can never step out.
- **Point on the walking circle `(10,0,0)`**: dead. Self-check `near=` (enemies within 15 units)
  stayed 0 for 60 s and the bot auto-fell back to walking. At the same time the host had 390
  enemies on its list — a full swarm that could not reach the player. A list count is not
  evidence of presence; only `near=` is.
- **Walking the circle** (radius 12 around `(10,0,0)`): live. Within minutes `near=445`,
  `die=589` — enemies crowd the path, weapons kill them.

Result: `CoopBot` no longer trusts any fixed point. `Still` holds a candidate; if the host sees
`near=0` for 60 s it logs `bot: spot dead, walking` and switches back. The client never runs the
fallback (its spawner is suppressed, so its `near` is 0 by design); it keeps following
`RemotePos + 2`, which also means both dwarves stay ~2 units apart during the walk — each window
shows the other dwarf throughout. `check: stand PASS` fires once when `near >= 50`.

God mode is `player.currentHp = 100000` every tick (500 was the dwarf's own max and a pack could
burn through it in one frame). Run state as of 21:33: host `enemies=560 near=445 die=589`, client
`enemies=0 sup=626`, `reg==live` holds (reconciliation makes it true by construction).

## Stage 1 enemy transport — WORKS, verified by log lines (build of 21:46)

Host-authoritative spawn/death mirroring over the existing LiteNetLib channel:

- Wire: `EnemySpawn{netId u16, EEnemy u16, q-pos 3×s16, scale u8}` (0.1 unit/step, 16-bit fixed
  point), `EnemyDeath{netId u16}`, `EnemyCensus{count u16}` every 5 s. ReliableOrdered.
- Host sends from `Register`/`OnDied`; a client never sends enemy traffic. Client re-spawns via
  `EnemySpawner.SpawnAt(EEnemy, Vector3, EEnemyScaleMode)` with `ApplyingRemote=true` (the guard the
  suppression already respects), keys mirrors by the host's id (`Entry.HostNetId`).
- Network callbacks only enqueue; `ProcessRemote()` drains on the main thread once per frame —
  Unity objects are never touched from the network thread.

Measured in a real run (client log):

- `check: freeze drift=0,00 units over 2s` — `SetAgentEnabled(false)` really freezes a mirror.
  The API names were dumped from the real assembly first (`SetAgentEnabled`, `SetBehaviour`,
  `get_Agent`, `get_Behaviour`, `hasAgent`), not assumed from the plan.
- `check: enemy transport host=30 mirrors=43 spawn=50 death=2 localDie=3 fail=0 miss=0` — the
  bookkeeping balances exactly (`spawn − death − localDie == mirrors`).
- Death transport is exact: host `die=213` matched client `death=213` in the first transport run.
- Two bugs found and fixed by the numbers: (1) the first ~20 spawn messages arrived before the
  client's spawner existed and were dropped (`fail=20`) — now they park in `PendingSpawns` and
  retry (`fail=0`); (2) the client's own weapons killed mirrors (`localDie=73` in run 1) — the
  freeze mostly removes that too (`localDie=5`), because a frozen mirror no longer walks into the
  client's weapon range; the remaining 5 died before freezing mattered.
- Remaining, honest: 2 `miss` deaths from ids spawned before the peer connected; the census lags
  by in-flight messages; mirror positions are the spawn snapshot (per-tick position snapshots are
  the follow-up, MTU-sized chunks, quantised).

The client window now shows real enemies — the host's swarm, frozen at spawn positions.

## Stage 1b — position snapshots: mirrors follow the host (build of 22:01)

Host re-broadcasts every enemy position at 2 Hz, split into 120-entry chunks (961 B < MTU),
`EnemySnapshot{count u8, (id u16, q-pos 3×s16)×N}` over `DeliveryMethod.Sequenced` (this
LiteNetLib build has no `UnreliableSequenced`). Client applies by moving the frozen mirror's
transform — frozen agent + teleport = puppet that follows without running its own AI.

Measured in a real run (client log):

- `check: sample moved total=5,4 units (id=5)` — the sample mirror demonstrably follows its
  host original.
- `check: snapshot applied=1031 missed=83 recv=1114` — misses are the cross-channel race:
  deaths are ReliableOrdered, snapshots Sequenced, so a chunk can arrive just after a death.
  Cosmetic; the next chunk omits the dead enemy.
- Run end state: host `enemies=192`, client `mirrors=172` (`census=192` lags by in-flight
  deaths); `fail=0` — the pending-retry keeps holding.
- Side effect measured: `localDie=45` — mirrors that move with the host walk into the client's
  weapon range, so the client kills a few and they drop client-only loot. Stage 2 must suppress
  loot spawned from mirror deaths (or the client's kills), otherwise the shared pool starts
  double-counting.

Stage 1 is done: both windows show the same swarm, moving together.

## Stage 2 loot — discovery run (build of 22:20)

Verified signatures from the real assembly:

- `PickupSpawner.SpawnXP(Vector3, Int32, EXPSource, Single) -> Void`
- `PickupSpawner.SpawnLargeXP(Vector3, Int32, EXPSource, Single) -> Void`
- `PickupSpawner.SpawnMaterial(ECurrency, Int32, Vector3, Single) -> Void`
- `PickupSpawner.SpawnMaterialNoForce(ECurrency, Vector3) -> Pickup` ← the only one returning a Pickup
- `Player.OnPickupClaimed(Pickup) -> Void` — the real claim path, fires with a Pickup.

Measured in a run: host `spawns=686 claims=4` in ~7 min (the walking bot rarely collects), client
`spawns=261 sup=261` — host-authority suppression holds, every client-side spawn attempt is refused.

Open: `Pickup`'s value/id fields were not found on the declared type (zero dumped members), so they
likely live in a base class — the dump must walk BaseType next. Mirror path plan: receiver uses
`SpawnMaterialNoForce` + `SetId(netId)` + set the value field via reflection; claims broadcast
`{netId}`, receiver removes the mirror and applies the delta only when `Wallet.ShouldSaveValue`
says run-local. XP orbs are NOT mirrored — the XpGain channel already carries XP.

## Stage 2 loot — transport works (build of 22:36)

- Wire: `LootSpawn{currency u8, value i32, q-pos 3×s16}`, `LootClaim{same}` — pickups are matched by
  (currency, value, position), not by id, because the void spawn overloads hand back no Pickup to
  tag. `PickupSpawner` is reached via `GameController.pickupSpawner` (found by type reflection).
- Client mirrors through `SpawnMaterialNoForce(ECurrency, Vector3)` behind `ApplyingRemoteLoot`;
  the value is set via the private `value` accessor (the public `Value` property is read-only).
- Measured: `check: loot mirrors=20 spawn=20 claim=1 miss=1 fail=0` — every spawn mirrored, first
  claim forwarded but MISSED: the host pickup had scattered (SpawnMaterial applies force), so the
  claim position no longer matches the spawn position within the 0.5-unit radius. Fix: match by
  (currency, value, nearest) within a wider radius and log the miss distance.
- Wallet API verified: `Add(CurrencyValue)`, `ShouldSaveValue(ECurrency)`, `GetAmount(ECurrency)`.
  The credit step (only run-local currencies) still needs the Wallet instance access path and the
  CurrencyValue constructor — runtime discovery like pickupSpawner.

## Stage 2 loot — full loop works (build of 00:11)

Positive evidence from a real run: `loot: credited cur=2 value=1 total=41…46` — the client's wallet
is credited when the host claims. The whole pipeline runs: host spawn (test drops via
`SpawnMaterial(NITRA, …)` behind `-cooptestloot` every 10 s, plus real mining drops from
`Player.TryMine()` called by the host bot every 30 frames) → broadcast → client mirror via
`SpawnMaterialNoForce` → host claim → broadcast → client removes the mirror and credits
(`Wallet.Add(CurrencyValue)`, gated by `ShouldSaveValue`). Nitra is run-local; the credit applies.

Measured caveats, all understood:

- Claim messages carry POOLED positions: `OnPickupClaimed` returns the pickup to its pool before
  the postfix runs, so the transform reads the pool home (miss distances grew 1273→2217 units).
  EVERY prefix variant on this method failed Harmony's IL compile (`IL Compile Error (unknown
  location)`), including a void prefix on the explicit `(Pickup)` overload — so the receiver
  matches by (currency, nearest) within 40 units instead. ~41/197 claims matched and credited;
  the rest missed. The position should be captured from a different hook (e.g. the Pickup's own
  claim method) in a follow-up.
- The credited `value=1` is also pool garbage — the host's `pk.Value` read after pooling.
- `fail=13/80` mirror spawns — transient; not yet chased.
- The client-side value setter works via the private `value` accessor (public `Value` read-only).
- `Player.TryMine()` is the real mining entry point (verified by api dump); the bot calling it
  while walking produced natural material spawns without any path change. `MapGenerator.blockList`
  is `List<MaterialBlock>` — the type is `MaterialBlock`, not `MineableBlock`.

## Stage 2 loot — COMPLETE (build of 00:52)

The full loop now runs with matching numbers, verified by positive log lines:

- Spawn broadcast moved to **`Pickup.OnSpawn`** (per-object init hook): mining drops bypass
  `SpawnMaterial`/`SpawnMaterialNoForce` entirely — measured 146 claims vs 31 broadcasts before the
  move, and `sentCur={0:12 2:151 3:4}` vs `claimCur={2:145 0:1}` after. OnSpawn sees every path,
  exactly like `Enemy.OnSpawn` did for waves.
- Client credits flow 1:1 with claims: `loot: credited cur=2 … total=146`. Currency is correct
  (claims match mirrors by FIFO — pool positions remain garbage, every prefix on
  `OnPickupClaimed` fails Harmony's IL compile).
- Early-message race fixed with the same pending-retry pattern as enemies (`fail=0` after).
- Known residue, documented: credited amounts are `value=1` — `Pickup.OnSpawn` fires BEFORE the
  game sets the pickup's value (the real value is applied afterwards via the `set_value(Int32)`
  accessor, present in the api dump). The fix is to read the value after the setter or one frame
  later; cosmetic, bookkeeping is exact.
- Test harness now: `-cooptestloot` drops NITRA(5) on the host player every 5 s; the poll loop
  proves a build within ~1 min of mission start instead of an 8-minute blind sleep.

## Stage 3 terrain — entry points verified (build of 01:02)

`MaterialBlock` (namespace `Assets_Scripts_LevelGeneration`, found by simple-name scan across all
loaded assemblies — `GetType(name)` misses namespaced types):

- `Die(Boolean, Boolean, Boolean)` — the destruction entry, the hook for the `{x,y}` broadcast.
- `Setup(MapGenerator, VFXManager, Int32, Int32, RunSettingsManager)` — the two Int32 are the grid
  coordinates; the receiver resolves the block via `MapGenerator.blockList` and destroys silently.
- `TakeDamage(Double, Player, Boolean, Boolean, Enemy, WeaponHandler)`, `UpdateNeighbors()`,
  `get_MaterialType()`, `Inject(PickupSpawner)` — supporting cast.
- Loot value residue confirmed: even one frame after `OnSpawn` the pickup's value is still 1 — the
  game applies the real value lazily (via the `set_value` accessor, likely near claim). Cosmetic;
  amounts are wrong by a constant, bookkeeping is exact.

## Roadmap (current)

A master plan with the full remaining-work list and PASS criteria lives at
`local/mod/DrgSurvivorCoop/PLAN.md` (private). Order: A character visuals → B combat visuals →
C objectives → D shop/upgrade → E loot value fix → F downed/revive → G UI + Steam lobby → H give back.

- **Milestone A (character class sync) — VERIFIED.** New `CharClass` packet (12): host sends `EDwarf`
  as byte; client stores `HostDwarf`. Two-instance run: `check: char self=3 role=host` ==
  `check: char host=3 self=3 role=client`. **Skin visual blocked** (puppet `GFXContainer` clone has no
  `PlayerSkin`; `System.Reflection.Invoke` can't pass `Component`→`PlayerSkin`; automation forces the
  same class on both sides, so it is unobservable anyway). Full detail in `PLAN.md`.
- **Milestone C (objective sync) — VERIFIED.** `Objective` packet (13): host reads
  `LevelObjectiveTracker.Primary/SecondaryObjectives → ObjectiveProgress.Progress`, client mirrors.
  Fixed two bugs: scene-walk tracker discovery (FindObjectsOfType returned 0) and secondary-objective
  determinism (seed `UnityEngine.Random` before `SetupSecondaryObjectives`). Log:
  `check: objective recv=26 applied=2 miss=0`, types match (both `COLLECT_POINTS` + `LEVEL_PICKUP`).
- **Off-screen indicator (F part 1) — VERIFIED.** `CoopIndicator.cs` draws a "REMOTE" marker at the
  screen edge when the remote dwarf is off-camera (`check: indicator offscreen remote=… edge=…`).
- **Downed-state (F) — code written, VERIFY BLOCKED by wizard-flow change.**
  - Implemented: `CoopDowned.cs` (downed flag + remote-downed detection via synced hp) and a Harmony
    prefix on `GameController.OnPlayerDeath()` that skips the game-over and marks downed
    (`check: downed role=…`). Not yet verified because the run no longer starts.
  - **New blocker:** the save game progressed (previous runs unlocked content), so the wizard flow
    changed: the landing page now shows `UIMutatorSetEntry` ×6 (mutator selection) and
    `UISetProgressButton_Mastery/Endless/Anomaly` are now available. `UIPlaySelectForm.StartMainMissionsFlow()`
    throws (`Exception thrown by target of invocation`), and pressing `UIMutatorSetEntry` does not
    advance. The `CoopAuto` wizard Plan is now out of date and needs the mutator step reverse-engineered,
    or the save game reset. Splash dismissal is now done in-mod (`UISplashForm.AdvanceFlow()`) instead of
    the flaky external mouse click.
  - `MutatorSetEntry` lives on `UIMissionRoadPage`/`UIMissionNodePage`/`UIChallengeSetSelectPage`
    (`mutatorEntries` field), so mutators are a mission-road selection step, not a landing-page tab.
- **Test harness: different classes + god-mode toggle — VERIFIED.**
  - Class page comes *before* the class-artifact page (old `CoopAuto` Plan had them swapped; fixed).
  - Save game 3 only has **Scout** unlocked (Gunner/Engineer/Driller `[unavailable]`). Forcing a locked
    class in the wizard stalls the artifact page (all artifacts become `[unavailable]`).
  - Fix: host keeps Scout, client overrides to **Engineer** via `RunSettingsManager.SetClass(EDwarf)`
    *after* the artifact step (plan index 6), not during the wizard. Verified:
    host `check: char self=3`, client `check: char host=3 self=1` (Scout=3, Engineer=1), both `alive=True`.
  - `-coopnogod` flag disables the bot's `currentHp=100000` pin → bot takes damage and dies
    (`hpDrops=6, alive=False`), the prerequisite for the downed test. Launcher: `coop-run.ps1 -NoGod`.
  - Class override needs `UIClassSelectPage.runSettingsManager`; `RunSettingsManager` is a plain
    Il2Cpp object (not a MonoBehaviour), reachable via the page field, not `FindObjectsOfType`.
- **Weapon / augment / status-effect system — MAPPED (Milestone B groundwork).**
  - `WeaponHandler` (MonoBehaviour) is the base; subclasses: `ProjectileWeaponHandler` (AutoCannon,
    AlternatingProjectile, Boomerang, ImpactAxe, Lok1, StubbySMG), `BeamWeaponHandler` (LocalSpaceBeam,
    RotatingBeam→SludgePump, ShardDiffractor), `GrenadeWeaponHandler` (Groundzone, LeadBurster,
    PlasmaBurster, Trap), `OrbitingDroneWeaponHandler` (CarrierDrone), plus CoilGun, LinkProjectile,
    RocketSwarm, Trail, Spawn, StunExplosion, WaveCooker, AttachedGroundzone. AI/turret path is
    `AIWeaponHandler` (MonoBehaviour, separate from `WeaponHandler`).
  - Augments are data (`WeaponSkillData`/`ASkillData` hierarchy; e.g. `BeamWeaponSkillData`,
    `ProjectileWeaponSkillData`→`AlternatingProjectileSkillData`, `ArtifactSkillData`). Weapon skill data
    exposes `GetStatusEffectData()` → `List<StatusEffectData>`.
  - `EDamageType` = KINETIC, CRYO, FIRE, ACID, PLASMA, ELECTRICAL. `EStatusEffect` = NONE, SLOW, STUN,
    BURN, ELECTROCUTE, CORRODE, FROZEN. So "weapon + upgrades → fire damage" is exactly
    `EDamageType.FIRE` + `EStatusEffect.BURN`, applied on the host and carried on the projectile
    (`Projectile.Shoot(... statusEffects, EDamageType damageType, ...)`).
  - **Sync conclusion:** effects are host-computed (damage + status applied on the host); the client
    already mirrors the *outcome* (enemy hp/death via enemy sync). What is NOT synced is the *visual*
    (projectile/muzzle/grenade/turret/status particles) — that is Milestone B's spawn-event work.
- **Auto-wizard FIXED (root cause found).** The wizard wedged on the Hauptmissionen screen: pressing the
  campaign card `UIChallengeSetButton_MissionRoad` did nothing, and the page never advanced (the mod then
  pressed it every 2 s via a fallback, which made it look worse).
  - Root cause: the mod cleared the publisher splash itself with `UISplashForm.AdvanceFlow()`. The splash's
    flow includes `ShowSaveSlotSelectorIfNeeded` (selecting/loading the save), so skipping it left the
    campaign half-initialized; `StartMainMissionsFlow()` then threw a NullReferenceException inside
    `UIMissionSelectPage.Show(...)` and the page could not change. (The mod's own log named the exception
    only after `Cause()` unwrapped `TargetInvocationException`.)
  - Fix: **never advance the splash from the mod.** Clear it with a real mouse click instead. Then the API
    driver works again untouched. Verified end-to-end: host `IN RUN after 20 steps`, client
    `IN RUN after 19 steps`, both `peer connected`, `alive=True`, `check: char self=0` / `host=0 self=1`.
  - Evidence that it is the splash, not the card: with a real click on the splash the campaign card
    advanced normally and the wizard walked `UIMissionRoadButton_` → `MissionSectorButton_` →
    `MissionNodeButton_` → `ClassSelectButton_` → `ClassArtifact` → `HazLevelButton` → IN RUN. A recorded
    real-mouse replay (`tools\coop-wizard.ps1`) reached IN RUN the same way, while `AdvanceFlow` did not.
  - The wizard's page flow is now logged by button signature (`auto: wizard page: …`) so the sequence is
    visible in the log instead of guessed.
  - `UIMutatorSetEntry` is display-only (`Show`/`Hide`, hover via `OnSelect`); it has no click action, so it
    must never be pressed as a fallback.
  - Level-up rewards are auto-served by the mod's `ServeLevelUp` (inside the auto driver's in-run branch);
    enabling `-coopwatch` now also clears the splash, so rewards can be automated without the wizard driver.
- **Downed / revive (F) — code done, revive not yet observed completing.** `CoopDowned` marks downed and a
  `GameController.OnPlayerDeath` prefix blocks game-over; the survivor bot rescues (walks into a 3 m circle),
  and the downed dwarf revives itself after 5 s. Two harness bugs found: relative-position rescue appeared
  frozen (the game rewrites the position between ticks; now an absolute target is written), and a false
  "remote downed" fired the moment one side started a run (now gated on having seen the remote's hp > 0).
  In an earlier full test **both** went down before the 5 s elapsed, so nobody could revive; the rescuer's
  hp is now pinned only while rescuing so it survives the rescue window.
  - **VERIFIED end-to-end, fully automated** (`coop-run.ps1 -Auto -NoGod`):
    `check: downed role=client (game-over blocked)` → host `check: downed remote role=host (remote hp=0)` →
    `check: rescue started role=host dist=11,8` → `check: revive started role=client dist=2,8` →
    `check: revived role=client hp=100 alive=True`, and the run kept going. No game-over screen appeared.
- **Combat visuals (B) — stage B1 done: the fire event is synced.** New `PacketType.Fire = 14` carrying the
  muzzle position (0.1-unit fixed point) and aim direction (1/10000), sent unreliable.
  - Hook: a Harmony *prefix* on `ProjectileWeaponHandler.ShootProjectileInDirection(pData, direction, …)`.
    It carries the firing handler, so `handler.owner` identifies the shooter; only the local player's own
    weapon forwards (`ProjectileShootPatch`). Rate-limited to ~25 events/s.
  - Verified (`coop-run.ps1 -Auto -NoGod`): host `shots 85 fireSent=85 fireRecv=115`,
    client `shots 117 fireSent=117 fireRecv=91` - each side's shots reach the peer, both directions.
  - **Rendering a visual is blocked by the build itself.** `GameObject.CreatePrimitive` returns objects
    whose material is `Hidden/InternalErrorShader` (this build ships no Unity default resources), so no
    procedural primitive can ever be visible. `Shader.Find("Sprites/Default")` / `Unlit/Color` / `Standard`
    return shaders with no compiled variants (`Shader.Find` succeeds, the draw produces nothing - the
    "applied but invisible" symptom), and a shader borrowed from a scene renderer was `FX/RT_Blobs`, a VFX
    shader that also draws nothing for a plain mesh. See the tracer attempt in `CoopCombat`.
  - Therefore the tracer is **off by default** (`-cooptrace` re-enables it) and B2 must reuse the game's
    own assets: either clone an existing visual the way `CoopPuppet` clones the player subtree, or - better
    - resolve the firing skill's real projectile/VFX prefab and spawn that. `Projectile.Shoot(WeaponHandler,
    ProjectileSettings, Vector3 origin, Vector3 direction, List<StatusEffectData>, EDamageType, float)` and
    `Projectile.SetInitialState(Vector3 origin, Vector3 direction, int pierce, ProjectileSettings, …)` are
    the spawn points; `ProjectileSettings` is small and serialisable (LifeTime, Speed,
    VFXThrottleFraction, OverrideDamageScalar, Ricochet, RicochetOnEnemy, SurvivesEnvironmentCollision).
  - `-cooptracerdebug` (and `coop-run.ps1 -TracerDebug`) still exist for re-testing a drawing approach;
    they print the chosen shader and the tracer's screen position.
- **Combat visuals (B) — stage B2: real projectile resolution works, spawning needs the game's pool.**
  The Fire packet now also carries the firing skill's asset **name**. This is the right key: both
  instances run the same content, so the host's skill asset is the client's skill asset.
  - Client indexes every `ProjectileWeaponSkillData` via `Resources.FindObjectsOfTypeAll` - **33 assets**
    in a run, and every shot resolved (`noSkill=0 noPrefab=0`). Host logs confirm the shot really carries
    the asset: `shot skill='ProjectileWeaponSkill_Subata' prefab=True`.
  - `ProjectileWeaponSkillData.ProjectilePrefab` is a `Projectile` component reference, so the real
    prefab is reachable: `Instantiate` produced `DamageProjectile_Kinetic_Medium(Clone)` with a live
    `Projectile` component and `ProjectileSettings` non-null.
  - **Blocker:** `Projectile.SetInitialState(...)` throws `Il2CppException` (masked NRE) on a bare
    `Instantiate`. The pooled projectile the game hands out has been through
    `Init(ObjectPool<Projectile>, LayerMaskLibrary)` first; a fresh clone has those fields null. Next step:
    obtain the game's projectile pool + layer-mask library (or reuse an already-`Init`ed pooled instance)
    before `SetInitialState`/`Shoot`.
  - Second finding: `ProjectileSettings.Speed` read **1000** for `Bosco_ProjectileWeaponSkill_Base`, so it
    is not a units/second muzzle velocity - the real velocity comes from the skill's `FireConfigs`
    (`FirePointOffset`, `worldDirStartOffset`, `RotateDirPerShot`, `BurstShots`, `BurstFireRate`).
  - Safety kept regardless: the mirror is spawned with `damageScalar` 0 and no status effects, so a client
    can never damage a host-owned enemy and desync the swarm.
  - All of this is behind `-cooptrace` (still off by default), so a normal run is unaffected.
- **Combat visuals (B) — stage B3: the spawn plumbing is located, one piece still missing.**
  A bare `Instantiate` cannot work, but the game has the right door: `Assets.Scripts.SkillSystem.
  ProjectileProviderStandard(WeaponSkillData data, LayerMaskLibrary layerMaskLibrary, BulletTrailVFXSystem
  bulletTrailVFXSystem)` builds a pool whose `Get()` hands out a projectile already through
  `Projectile.Init(pool, layerMaskLibrary)`. `UpdateProjectilePrefab(Projectile)` re-points one provider at
  any skill's prefab, so a single instance can serve every shot the peer fires.
  - Plumbing is borrowed from the local player's own weapon handlers (the provider is a field on
    `LinkProjectileWeaponHandler`; `LayerMaskLibrary` is a **property** on `WeaponHandler`, which is why a
    fields-only scan found nothing - the cheap mistake that cost a run).
  - Verified progress: `combat: masks=True trails=False` then
    `combat: projectile provider built for 'Bosco_ProjectileWeaponSkill_Base'`. The provider constructs.
  - The missing piece was `Player.BulletTrailVFXSystem` - a public property the player is injected with
    (vfx, layer masks and most managers all arrive on `Player.Inject(...)`). Borrowing it from the player
    instead of hunting for a projectile-carrying weapon closed the gap.
  - **Verified (client, this run):** `combat: masks=True trails=True` ->
    `combat: projectile provider built for 'ProjectileWeaponSkill_Subata'` ->
    `combat: mirror projectile #1/#2/#3 skill='ProjectileWeaponSkill_Subata'
    prefab=DamageProjectile_Kinetic_Medium go=DamageProjectile_Kinetic_Medium(Clone)`.
    Counters `proj=109/0` - 109 spawned, 0 failed (was `proj=0/98`), with `live=0`, so the game also
    reclaims them. The client now spawns real, pooled, damage-neutral game projectiles.
  - A burst screenshot of the client during combat shows a fully rendered scene with projectiles, muzzle
    flashes and impact VFX. One frame cannot attribute an individual projectile to the mirror stream, so
    the *spawn* is proven and *visibility* is strong but not yet isolated.
  - Render probe added (`-cooptrace` only): 0.4 s after spawn it reports the object's survival, distance
    travelled, every renderer's enabled/isVisible state, its shader, its layer and the camera's mask.
    Deferred on purpose - `Renderer.isVisible` is written during culling, so asking on the spawn frame
    always answers false.
  - **Probe result (client):** `active=True travelled=9,2 rends=1 drawn=0 layer=9 camHas=True on-screen
    [r0 en=True vis=False URP/URP_Matcap_Unlit_Simple]`. So the mirrored projectile is alive, has moved
    ~9 units, has exactly one renderer that is **enabled**, carries a **real game shader** (not
    `Hidden/InternalErrorShader` as the procedural primitives did), sits on layer 9 which the main camera
    **does** render, and is inside the viewport - yet Unity's culling still reports it undrawn.
  - That combination (enabled, right layer, on-screen, real shader, still `vis=False`) points at bounds or
    mesh setup that the game performs inside its own `Shoot(...)` path, which this bypasses by calling
    `SetInitialState` directly. **Control experiment before chasing it:** run the same probe against the
    host's own projectiles. If those also report `vis=False` at +0.4 s, the signal is simply unusable at
    that sampling point and the mirror visual is fine - which is the cheaper thing to rule out first.
  - Everything stays behind `-cooptrace`; a normal run is unaffected, and the Fire event itself (B1) is
    verified and always on.
