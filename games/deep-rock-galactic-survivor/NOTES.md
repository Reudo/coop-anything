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
- **Meta progression uses the HOST profile for both dwarves** (owner decision, supersedes the earlier
  "shared real profile"). Unlocks come from the host only: if the host has the Driller, the partner may
  play it, otherwise not. Progress is credited to the host's profile for **both** characters, so a host
  on Scout with a partner on Driller advances both the Scout and the Driller in the host's save. The
  partner's own save is neither read for the run nor written. How the client's run results are fed into
  the host's save path is **unknown** and must be measured before it is built.
- **Team economy:** Gold and Nitra are one shared pot; spending (shop, rerolls, artifact rerolls) is
  arbitrated by the host. **Bosco:** one per player, host simulates both. **Supply Pod:** one global
  pod, each player picks their own artifact. **Damage model:** client weapons run locally, the client
  reports hits and the host applies them (cheat exposure accepted for 2 friends).
- **The host picks the mission**, and the client must **drop into the same mission**, with the same
  drill and same level state. This is the "settings adoption" problem, and the owner wants it fully
  automatic rather than matched by hand.
- **Scope for now: main missions only** (Elimination, Escort Duty). Other run types do not have to work
  yet, and **Egg Hunt is explicitly out of scope** (it needs the Heavy Duty DLC).
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

**Limitation that WAS accepted here and has since been removed:** the dwarf took no reward from those
level-ups, because `OnLevelUpFinished` finishes the screen *without* committing a card. That kept a run
alive but meant every automated run tested a game with no upgrades at all. Superseded - see
"Level-up cards" below for the real pick path and its evidence.

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
  `check: char host=3 self=3 role=client`. **Skin visual VERIFIED (2026-10-20).** The earlier block was
  the **pre-run** puppet: it has no `PlayerSkin` component. After the run starts the puppet is respawned
  and does have one, so the typed re-wrap plus `ActivateSkin(playerSkin, skinData, false)` succeeds.
  Run `20261020-030131-skin` (`-SkinTest`, host class 0 / local 1): client `ActivateSkin ok dwarf=0
  meshes=4`, `check: skin ... applied=1 meshes=4`, PASS both. Negative `-SkinOff`
  (`20261020-030403-skin`): client FAIL `applied=0 meshes=0`. The blank-`AddComponent` path is not
  used. Full detail in `PLAN.md`.
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

- **Test stimulus for weapons: any of the 75 weapon skills can be equipped on demand (build 14:34).**
  The blocker below ("nothing throws, and one cannot be attached") turned out to be the *wrong entry point*,
  not a missing fixture. The game has a named, public way to hand a weapon to a player, and it works:

  ```text
  check: dev weapons n=75 role=host [0]AlternatingProjectileSkillData_Boltshark [1]BeamWeaponSkill_Electrical_TH0R
    [2]BeamWeaponSkill_RotatingBeam_CryoCannon … [25]Driver_ProjectileWeaponSkill_ChimeraFragcannon
    … [43]GrenadeWeaponSkillData_Leadburster [44]GrenadeWeaponSkill_Cryo [45]GrenadeWeaponSkill_HEGrenade
    … [48]ImpactAxeSkillData … [61]ProjectileWeaponSkill_AutoCannon …
  check: dev give 'GrenadeWeaponSkill_HEGrenade' via=EquipNewWeapon handler=yes data='…' owner=self
    weapons=1->2 registered=1 role=host
  grenade: throw #1 handler skill='GrenadeWeaponSkill_HEGrenade' own=1 dir=-0,15/0,99
  grenade: throw #1/1 base skill='GrenadeWeaponSkill_HEGrenade' prefab='Grenade_HE' from=(9.8,1.0,7.0)
  RESULT: grenade PASS reason=handlerThrows=7 baseThrows=7        (host)
  RESULT: grenade PASS reason=handlerThrows=12 baseThrows=12      (client)
  ```

  - **The path:** `Player.EquipNewWeapon(WeaponSkillData, bool)`, plus `EquipNewWeaponAtActionbarIndex`,
    `EquipBoscoWeapon`, `RemoveEquippedWeapon`, `HasWeapon`, `GetWeaponCount`, and the list the game
    actually drives: `Player.weapons` (`List<WeaponHandler>`) with `WeaponAdded`.
  - **The flag aids:** `-coopdev-weapons` lists every `WeaponSkillData` asset once; `-coopdev-give=<name[,name]>`
    equips them at run start (`coop-run.ps1 -DevWeapons -DevGive <names>`). Every give logs the weapon count
    before/after, so "the game accepted it" is a number and not an assumption.
  - **Why the first attempt failed, precisely:** `GrenadeWeaponSkillData.AddWeaponHandler(go)` +
    `Init(data, owner, firePoint)` produces a handler that looks complete (right data, right owner) but is
    never inserted into `Player.weapons` - so the game never drives it. Correct initialisation is necessary
    and not sufficient; *registration* is the missing half.
  - **`weapons=1` at run start**, even though the dwarf visibly carries the Subata and Bosco: the drawn
    starting weapon is not in that list either. Worth knowing before reading a count as "number of guns".
  - **Weapon catalogue facts this produced:** 75 weapon skill assets on both instances, including the
    `Driver_*` line (a whole dwarf's set), `BeamWeaponSkill_*`, `ImpactAxeSkillData`, `CoilGun`,
    `DefenseDrone*`, `Boomerang`, `AlternatingProjectile*`, `LinkProjectile*` and eight grenade skills;
    the list also contains the **enemy** weapons (`EnemyProjectile*`, `ExploderWeaponData*`), so a name
    filter has to exclude those.
  - **Turrets are cards too:** `SpawnWeaponSkill_Turret_Flamethrower` was offered at a level-up, so the
    "turret" part of milestone B is a `SpawnWeaponSkill` weapon, not a `Turret` type.

- **An instrument trap now measured twice: on interop objects, `GetType()` and `is` describe the wrapper.**
  A grenade equipped through the game threw seven times in one run while the probe reported
  `grenade handlers=0`, because `h is GrenadeWeaponHandler` was false for it. `GetType().Name` is no better -
  every level-up card printed the declared base type `ASkillData`. Both are trustworthy only for objects this
  mod created itself through the managed type (a runtime `AddComponent<GrenadeWeaponHandler>()` did satisfy
  `is`). **The reliable discriminator is the asset name** from the game (`data.name`), which is what the
  grenade checks use now. The same mistake had been built into the card-offer log and into the fixture
  preference; both are name-based after this.

- **Launcher: the "stuck on splash" console was a real defect, and it also clicked into live runs.**
  `coop-click.ps1` ran synchronously for up to 240 s and clicked **every** game window each round, with the
  role mapped only through log markers. So (a) the console kept showing its last `host=on-splash` line while
  `coop-run.ps1` waited silently, and (b) an instance already in the menu or in a run kept receiving centre
  clicks - which presses UI buttons. Two runs today "hung on the splash" and silently doomed themselves.
  Now: role→PID from the process command line (`-coophost`/`-coopclient`), clicks only for instances that are
  still before the splash, a named `GAVE UP after Ns` warning, and a live per-role progress line during the
  result wait (plus an early "no instance has reached a run after 90s" warning). Verified in the next run:
  `phase: run-started t=+31,5s` / `auto: IN RUN after 14 steps`.

- **Combat visuals (B) — grenades: the fixture has no grenade weapon, and one cannot be attached (build 13:42).**
  The plan said "hook `Grenade.Throw`/`ShootGrenade`, broadcast, spawn on the client". Measured first, in three
  steps, each of which answered a different question:

  1. **Does anything throw a grenade?** No. `check: grenade dump weapons=2
     [WeaponHandler:'ProjectileWeaponSkill_Subata':self, WeaponHandler:'Bosco_ProjectileWeaponSkill_Base':self]
     grenadeHandlers=0 inScene=13 active=0 skillAssets=10` on **both** roles - the dwarf has its primary and
     Bosco, no grenade handler, and the 13 pooled `Grenade` objects were never active. So the fixture has
     nothing to measure: this profile has **nothing equipped** (`EquippedGear = []` in the save, the `eq=0`
     gap already noted for I1).
  2. **Can the game's own factory attach one?** Not this way.
     `GrenadeWeaponSkillData.AddWeaponHandler(player.gameObject)` returned a plain **`WeaponHandler`** (not a
     `GrenadeWeaponHandler`), owner set by a follow-up `Init(...)`; `grenadeHandlers=0` afterwards and zero
     throws in 25 s. The factory adds what the *base* class adds - the wrong door for a grenade.
  3. **Can the grenade component itself be attached?** It can be created, but it is not driven.
     `AddComponent<GrenadeWeaponHandler>()` + `Init(data, player, player.FirePoint, null)` with
     `GrenadeWeaponSkill_HEGrenade` gives a real handler -
     `check: grenade give 'GrenadeWeaponSkill_HEGrenade' via=AddComponent+Init handler=GrenadeWeaponHandler
     isGrenade=1 data='GrenadeWeaponSkill_HEGrenade' owner=self` - and still **zero throws in 25 s**. A
     correctly initialised handler (data, owner, fire point) is necessary but not sufficient: the weapon list
     is built by the game from class and loadout at run start, and a handler attached afterwards is not part
     of it.

  Two further runs of step 3 (`20261019-135025`, `20261019-135619`) produced **no data**: the automation sat
  on `auto: waiting on splash (leave it to a real click)` - the launcher's click did not land - and the test
  timed out. That is harness flake, recorded so it is not read as a result.

  **What was gained anyway, and it is not nothing:**
  - The grenade asset inventory is identical on both instances (10 assets), so a mirror can resolve a skill
    by name exactly as the projectile mirror does: `Bosco_GrenadeGroundzone_Fire:GRENADE`,
    `Bosco_GrenadeWeaponSkill_Cryo:GRENADE`, `Driver_GrenadeWeaponSkill_ProximityMines:TRAP`,
    `GrenadeWeaponSkillData_Groundzone_Acid|Fire:GRENADE`, `GrenadeWeaponSkillData_Leadburster:GRENADE`,
    `GrenadeWeaponSkill_Cryo|HEGrenade|PlasmaBurster|ShredderSwarm:GRENADE`.
  - `Grenade.Throw` has overrides (`GrenadeShredderSwarm`, `LeadBursterGrenade`) that do not call base, so it
    is **not** the single entry; `GrenadeWeaponHandler.ThrowGrenadeInDirection` is, and only `TrapWeaponHandler`
    overrides that. Both hooks are installed and counted side by side, so a throw seen in one and not the
    other names a subclass prefab instead of hiding it.
  - The saves live in a **Steam-ID subfolder**: `%USERPROFILE%\AppData\LocalLow\Funday Games\DRG Survivor\
    steam\<SteamID>\drg_save_slot{1..3}_{0..3}.dat` (the earlier notes said "the same folder" - it is one
    level deeper than that).
  - A named outcome now separates the two zeros: `NO_GRENADE_THROWN` (no weapon at all) from
    `HANDLER_NOT_DRIVEN` (handler present, game never fires it). The wording is in the build; the two runs
    that would have shown it flaked, so it is **unobserved** until the next successful run.

  **Superseded by the build above:** the blocker was not a missing fixture but the wrong entry point. A
  grenade *can* be equipped on demand through `Player.EquipNewWeapon` and the game throws it (7/12 throws,
  PASS both roles). The gear/loadout hypothesis was wrong on its own terms as well: `EGearSlotType` is
  `TOOL, ARMOR, GRINDER, WEAPON_MOD, TANK, COMPANION` - there is no weapon or grenade slot in the loadout, and
  `GearData` carries stats, no `WeaponSkillData`. A grenade mirror is now a code task with a working stimulus.

- **Combat visuals (B) — the draw oracle: five in-process paths closed, all with evidence (build 03:30).**
  The open gap after B3 was narrow and honest: the client spawns real pooled projectiles (`proj=109/0`) and a
  screenshot of a fight looks right, but "the mirrored projectile is actually drawn" was never *proven*.
  Chasing it produced a result of its own kind - **every in-process reading this build offers is closed**, and
  each one with the exact evidence, so nobody has to walk them again:

  1. `Renderer.isVisible` - no information (B3's A/B control: the game's own projectiles read `vis=False`
     exactly like the mirror's, at every offset).
  2. A managed `MonoBehaviour` added at runtime to count `OnWillRenderObject` -
     `TypeInitializationException -> NullReferenceException`, i.e. the il2cpp class for a runtime-injected
     managed component does not come up. (`AddComponent<CoopTick>()` at plugin load does work, so it is the
     *injected* type that fails, not the mechanism.)
  3. `Camera.Render()` - **not in the interop assembly at all**; the game never calls it and IL2CPP only
     ships what the build uses.
  4. `Camera.CopyFrom()` - same.
  5. `Texture2D.ReadPixels` from a RenderTexture - **returns black**. That one is decisive: the probe tried
     all five cameras in the run, one frame each, and every single read was `mean=0`
     (`Camera(en=1) RT_Camera(en=1,rt) Camera(en=1) Main Camera(en=0) UICamera(en=1)`), *including* reading
     `RT_Camera`'s own 256x256 texture, which the game certainly renders every frame. So it is the read path,
     not the camera choice.

  ```text
  03:26:32.280 check: b3draw cameras Camera(en=1) RT_Camera(en=1,rt) Camera(en=1) Main Camera(en=0) UICamera(en=1) -> trying 'Camera'
  03:26:32.397 check: b3draw camera 'Camera' rendered nothing, trying 'Camera'
  03:26:34.108 check: b3draw camera 'Camera' rendered nothing, trying 'RT_Camera'
  03:26:34.165 check: b3draw camera 'RT_Camera' rendered nothing, trying 'Main Camera'
  03:26:34.207 check: b3draw camera 'Main Camera' rendered nothing, trying 'UICamera'
  03:26:34.252 RESULT: b3draw FAIL reason=verdict=NO_RENDERING_CAMERA
  ```

  **The control earned its place here.** `NO_RENDERING_CAMERA` is the outcome the positive control is for:
  without it this run would have reported `MIRROR_NOT_DRAWN` and sent the next agent hunting a visual bug
  that the measurement never looked at. Hiding the dwarf - which is certainly on screen - moved zero pixels
  too, and that is what said "the instrument is blind", not "the mirror is missing".

  Two facts about the build that fell out and are worth keeping:
  - **`Camera.main` is `UICamera`**, and `Camera.allCameras` lists *only enabled* cameras - one in-run, the
    UI camera. The world is drawn by cameras that are not in that list, which is why the search had to go
    through `Resources.FindObjectsOfTypeAll<Camera>()`.
  - A parked projectile can be produced on demand: `CoopCombat.SpawnParkedMirror` spawns through the normal
    mirror path and zeroes its velocity, which is what any future oracle needs (a flying projectile answers
    "was it drawn" only sometimes).

  **What is unchanged:** the mirror spawns, is pooled, damage-neutral, carries a real game shader, sits on a
  rendered layer - and no available reading contradicts that it is drawn. What is still not proven is that it
  is drawn. The remaining oracle is **outside the process** (capture the game window while a parked mirror is
  held in front of a camera and diff two frames); every in-process path is now known to be closed.

- **Combat visuals (B) — stage B3 control experiment: the `isVisible` signal is unusable, not the visual.**
  The open question was whether the mirror is really drawn, because the probe reported `vis=False` for an
  object that was alive, moving, enabled, on the right layer and on screen. The fix was to stop measuring
  the mirror against nothing: `-cooptraceab` puts **both kinds in one instance**. A Harmony prefix on
  `Projectile.SetInitialState` (the single private method every projectile goes through) registers the
  game's own projectiles as `kind=local`, `CoopCombat.InMirrorSpawn` marks the mod's own call so its
  projectile registers as `kind=mirror`, and the *same* probe samples both at +0.1/0.25/0.4/0.8 s. The flag
  also loops the local shot back into the mirror path, so real and mirror are spawned from the same muzzle
  in the same frame.
  - **Observation** (`coop-run.ps1 -Deploy -Auto -Test b3 -TracerAB -Only host`, archived log):
    `check: B3 result=PASS verdict=SIGNAL_UNUSABLE local_vis=0/33(n=36 done=6) other_vis=0/0 mirror_vis=0/8(n=8 done=2)`
    - All 33 alive observations of the game's **own** projectiles read `vis=False`, at every offset, with
      `rends=1 en=True layer=9 camHas=True on-screen` and a real shader
      (`URP/URP_Matcap_Unlit_Simple`) - byte-for-byte the same reading as the mirror's 8 observations.
    - `combat: probe kind=local … travelled=2,4 / 5,2 / 8,0 / 16,0` is the same ~22 u/s curve as the
      mirror's `3,1 / 6,6 / 9,7 / 18,0`, so both kinds did travel and were sampled mid-flight.
    - Recycled projectiles are visibly different (`active=False`), so the probe does distinguish states.
    - Hook counters prove the plumbing: `hookReal=11 hookMirror=3`.
  - **Derived:** at these offsets `Renderer.isVisible` carries **no information** about whether a
    game-drawn projectile is on screen in this build. The earlier `vis=False` on the mirror is therefore
    **not evidence** that the mirror visual is broken, and B3's "chase the game's `Shoot(...)` path" branch
    is closed. The instrument was the broken part, not the visual.
  - **Unchanged by this run:** `Renderer.bounds.extents` came back `bounds=n/a` for every renderer, so the
    bounds hypothesis was neither confirmed nor refuted - the property is not reachable the way the probe
    asks for it (same reflection gap that hides `isVisible`).
  - **Unknown (honest gap):** "the mirrored projectile is actually drawn" is still **not proven**. What is
    proven is that no available reading contradicts it, and that the one reading which seemed to had no
    signal. Both oracles named here were tried later and are **closed**: the parked-object pixel diff cannot
    read a frame (see the draw-oracle section further down - `Texture2D.ReadPixels` returns black, and
    `Camera.Render`/`Camera.CopyFrom` do not exist in the interop assembly), and the injected
    `MonoBehaviour` for `OnWillRenderObject` fails to construct. **The only oracle left is outside the
    process:** hold a parked mirror in front of a camera (the parking helper exists and works) and diff two
    captures of the game window taken from outside.
  - **Side effect of the run that is worth keeping:** the automation reached the mission in **~54 s** from
    plugin load (phases: menu at +19 s, wizard 7 steps at 2 s each, `run-started` at +35,6 s, first shot at
    +48 s, verdict at +49 s). The old "3-4 minutes to mission start plus a fixed 80 s wait" was mostly the
    guessed wait, not the boot.
- **Test harness (repo-relevant technique, not just this game).** Three things made the run above possible
  and are reusable for every later milestone:
  - The mod ends its own test: `-cooptest=<name>` makes it decide when the question is answered, write
    `RESULT: <name> PASS|FAIL reason=… role=…` into the per-role log and quit. The launcher polls that line
    instead of sleeping a guessed number of seconds, and an unanswered test reports FAIL after a timeout
    (`-cooptesttimeout`, default 420 s) rather than producing no line at all. Verdicts name their
    inconclusive outcomes (`MIRROR_MISSED`, `NO_REAL_ALIVE`) instead of hiding them.
  - Every step from plugin load to in-run logs `phase: <name> t=+Ns dt=Ms`, so boot cost is attributed
    instead of guessed. (Caveat: markers logged before the first frame report a different time base -
    `plugin-load t=+2,0s` precedes `first-tick t=+0,3s` - so only `dt` between frame-time markers is
    trustworthy.)
  - Deploy is verified: the DLL copy is checked by SHA-256 against the build output, because a stale binary
    looks exactly like a fix that does nothing. Test runs archive their logs and screenshots under
    `local/work/runs/<stamp>-<test>/`, back the save profile up first, and always stop the processes they
    started.

## Stage 1 damage — client hits now reach the host (build of 18:22)

The client's weapons used to hit only its own frozen mirrors; the host never learned about the damage, so
the client contributed nothing to a kill except its own local miskill (`localDie`). The accepted model is
now in place: **the client runs its weapons locally and reports the damage, the host applies it to the
enemy it owns**.

- Observed: `check: hit sent=20 dmgTotal=532 flushes=15` (client) and
  `check: hit recv=20 applied=20 missed=0 unmatched=0 dmgTotal=532` (host) in the same run. Both damage
  totals are **identical**, and every one of the 20 hits was applied - so the two sides agree on the
  number, not just on the count.
- Wire: `EnemyHit` (0x0F) = `count(u16) × (hostId u16, dmg i32)`, ReliableOrdered. Reported damage is the
  **hp delta the client's own `TakeDamage` produced**, not the incoming number: the mirror carries the
  same armor as the original, so the delta is already final and the host applies it with
  `ignoreReduction: true`. A second armor pass would have made the two sides disagree by a fixed factor.
- Hits are summed **per enemy** and flushed at ~16 Hz, so a burst of splash damage costs one entry, not one
  packet (20 hits over 15 flushes). Applied in `CoopEnemy.DrainHits` on the main thread.
- Host applies through the game's own path, `Enemy.TakeDamage(dmg, false, KINETIC, doFx:false,
  PROJECTILE, hostPlayer, ignoreReduction:true)`, so death, kill credit and loot follow from the real code
  instead of being reproduced by hand. `entitySource` is the host's dwarf (the real remote player does not
  exist on this side), so kills are currently attributed to the host dwarf - a known gap for the
  per-dwarf stats work (PLAN.md I2).

### Cost: patching a virtual method *and* its override kills the game

The first attempt patched **both** `Entity.TakeDamage` (virtual) and `Enemy.TakeDamage` (its override).
Both instances died ~1 s after the plugin loaded, deterministically, with
`0xc0000005` (access violation) in `coreclr.dll` at the same offset; the mod log simply stopped after
`test: begin` and BepInEx showed `Il2CppInterop ... During invoking native->managed trampoline`.
No Player.log, no dump - and the launcher reported `verdict: FAIL` with no RESULT line, which is the
intended shape for "the processes died".

Patching only the override (`Enemy.TakeDamage`) works, and that is the rule: **patch the override, never the
virtual+override pair.** The existing hooks already followed it (`Enemy.Die`/`DeSpawn`/`Recall` are
overrides and are patched that way); `TakeDamage` was the first place it was violated. Confirmed from the
Cpp2IL dummies: `Entity.TakeDamage` is `public virtual bool`, `Enemy.TakeDamage` is `public override bool`,
and both were being detoured.

Also learned from the same dummies, and worth keeping: the signature and its defaults are
`Entity.TakeDamage(long dmg, bool isCrit=false, EDamageType=KINETIC, bool doFx=false,
EDamageSource source=PROJECTILE, Entity entitySource=null, bool ignoreReduction=false)`. Knowing that
replaced the reflection call with a direct one, which is both simpler and safer on IL2CPP.

## Incoming damage — the client's dwarf is already in danger (build of 18:39)

Before writing anything for "enemies must be able to hurt the client", we measured whether they already
do. They do, and the reason is structural rather than lucky:

- A mirror is a **real `Enemy` created by the client's own spawner**, so the game handed it the client's
  player at spawn. The client's mirror swarm regards the client's dwarf as its target and attacks it.
- Measured with `-coopnogod -coopswarm -cooptest=damage -cooptestmin=120` (god mode off, client glued to
  the nearest mirror so the dwarf is actually in reach): the client lost **8×10 hp in ~34 s**, every hit
  logged with the distance that makes it attributable - `nearestMirror=0,7–1,2`,
  `type=GRUNT0/BASE`/`FAST_GRUNT/BASE`, `enemiesWithin5=2–7`. The host took **8×10 hp in the same
  window**. Both sides are hurt at the same rate while both are in the swarm.

So no damage packet is needed in this direction either. Each side is authoritative for its own dwarf's hp:
the client computes its own hits, the host reads the result as `remoteHp` in `PlayerState`, and
downed/revive already keys off that number. `EnemyHit` (client -> host) and this (client-local) are the
same rule, "whoever runs the simulation of an entity owns its hp", applied to the two entity kinds.

### Still open: aggro, and it is not a cheap fix

`Enemy.Player` is a **getter-only** property backed by a private field that
`OnCreated(..., Player player, ...)` sets once at spawn, and an instance has exactly one `Player`. On the
host every enemy therefore aims at the host's dwarf, and nothing on the host can be aimed at the client's
dwarf. "Host aggro on the puppet" is not a target reassignment; it needs a second *real* `Player` on the
host (DI init, HUD, camera). Consequence today: the swarm follows the host, and the client is hit because
it stands in the same space - not because the enemies chose it.

**Owner decision (18:40):** the partner *should* ideally have its own aggro, but this is **recorded as a
later goal and deliberately not prioritised now**. Parked in PLAN.md B2 and in the plan file under
"Später (bewusst NICHT priorisiert)". The cheap thing to try first when it is picked up is dropping
`SetAgentEnabled(false)` to see whether an unfrozen mirror chooses the client by itself; the proof has to
be a *closing distance* over several seconds, not an accidental hit.

### Two measurement traps this cost

- **God mode hides all damage.** The test bot pins hp to 100000, so every earlier run reported
  `hpDrops=0` — which says nothing about enemies and was briefly read as "the client is safe". Damage
  questions require `-coopnogod`.
- **One instance quitting invalidated the other's window.** The host reached its threshold after 12 s and
  exited; the client then spent 85 s alone with no partner, a pending level-up barrier (`barrier=both`)
  and a frozen mirror set, and its "1 hit, then nothing" was drawn from that dead window. The first
  conclusion ("frozen mirrors do not attack") was wrong for exactly this reason. `CoopTest.MinSec`
  (`-cooptestmin=<s>`) now holds a verdict until both sides have had the same observation window, and the
  re-run reversed the finding. A two-instance test has to treat the other instance's lifetime as part of
  its own measurement.

## Level-up cards: the reward screen is drivable, and every earlier run took no reward (build of 18:52)

The automation answered level-ups by calling `LevelUpManager.OnLevelUpFinished`. That moves the flow on
and keeps a run alive, which is why it was chosen - but it also finishes the screen **without committing
a card**. The consequence had never been noticed: *no* automated run had ever applied an upgrade, so the
whole upgrade system was untested and "the run passed" meant "the run passed with no upgrades".

The screen is drivable; the earlier attempt to press a card failed for a documented reason worth keeping:

- `UISkillButton`'s press callback lands in `UILevelUpForm.OnSkillSelected`, which only **previews** a
  card. That is why pressing it left the run frozen.
- The commit is the public **`UILevelUpForm.OnSkillChosen(UISkillButton, SkillRaritySet)`** - the call the
  game makes when the player confirms.
- The card's data is reachable without naming private fields: `UISkillButton.SkillRarity` (public) gives
  the `SkillRaritySet`, and `SkillRaritySet.SkillData.name` is the readable card name.

`CoopUpgrade.cs` (new) does the pick; `CoopAuto.ServeLevelUp` now tries a real card **first** and keeps the
manager bypass only as the last resort that stops a screen from wedging the run - and counts it
(`Skipped`), so "the run continued" can no longer hide "the dwarf gained nothing".

Measured (`-Test levelup -TestMinSec 120`), PASS on both roles with `skipped=0`:

```
host   picked=3   SupportSkill_MoveSpeed / SupportSkill_MiningSpeed / SupportSkill_MoveSpeed   (index 0)
client picked=3   WeaponUpgradeSkill_FireRate ×3                                               (index 1)
```

- The two sides take **different cards**, which is the point: the pick is per player, not one shared
  choice echoed twice. Each instance is offered its own list (observed order differs: host
  `Damage/FireRate/ReloadSpeed`, client `FireRate/Damage/ReloadSpeed`), and the mod deliberately prefers a
  different index per role so a run cannot pass by both sides happening to agree.
- The XP barrier is unaffected: `local picks done, holding until remote picks` → `remote picks done`
  around every pick.
- The test needs **two** picks, not one: the interesting failure is the second time the form is opened
  after the flow has already been through the barrier once.

This removed the last "automation-only shortcut" in the level-up path: a run now applies real upgrades,
so later damage/progression measurements are measuring a real game.

## Run settings adoption: the levels matched by coincidence, and now they match on purpose (build of 19:09)

Both instances generated an identical map long before any of this existed. The reason was not
synchronisation - it was that the test bot walks both wizards through the same fixed page order on
saves that look alike, so both sides clicked the same biome, the same sector and the same node. Only the
hazard was ever forced across the wire (and the seed). Anything that broke the resemblance - a different
save, a different unlock state, a human choosing on one side - would have put the two dwarves in
different caves, and nothing would have caught it.

`RunConfig` now carries the whole run identity: hazard, seed, biome, sector, node, mission type, main
mission type. The host reads it out of its own `RunSettingsManager` and broadcasts it on a 1 s heartbeat
from `CoopTick`; the client applies it in the `MapGenerator.CreateMap` prefix.

- **The heartbeat is not a nicety.** The client reaches its own run preparation *before* the host starts
  its run: the client presses Play when the bot's wizard finishes, and if the config only went out at
  host run start, the client could be past its preparation already. Resending is idempotent.
- **Node identity is (biome, sector index, node index)**, not an object. Both instances read the same
  `MissionSectorData` assets, so the same three indices name the same node on both sides. The client
  resolves it through its own mission road and applies it with the game's own
  `SetupMissionRoadNode(nodeState)` - the call the game makes when a player clicks that node. Setting the
  derived fields by hand would have meant guessing which ones matter.
- **The test needs a deliberate disagreement.** `-coopdrift` (client only) makes the client press the
  *highest* available `MissionNodeButton_` where the host presses the lowest. Without that, both sides
  agree by construction and "settings matched" proves nothing.

Measured (`-Test settings -Drift -TestMinSec 60`), PASS both roles:

```
host   check: settings role=host gathered  settings biome=Crystalline Cavern(0) hazard=0 sector=0 node=0 mission=0/0 mutators=off
client auto: DRIFT - client takes 'MissionNodeButton_05' instead of the lowest node
client check: settings role=client applied=1 drift=1 (CreateMap) settings biome=Crystalline Cavern(0) hazard=0 sector=0 node=0 mission=0/0 mutators=off
```

`drift=1` is the whole point: the client really did choose node 5, the adoption really did pull it back
to the host's node 0, and the game's own state then reads the same on both sides. The other four fields
agreed already (both wizards picked the same hazard/mission/sector pages), so the node is the field this
run actually proves - which is also the field that decides which cave you get.

**Two things measured the hard way:**

- **`PrepNewRun` is not the hook.** It reads like the right place - it builds the level configs and run
  mods from the settings, so adopting before its body runs would beat adopting before terrain
  generation. It never fired. Every run reported the adoption happening at `CreateMap` instead, and the
  method has no caller anywhere in the decompiled `Assembly-CSharp` (it is `internal`, so the UI assembly
  may call it, or it may serve the challenge/endless/retry paths rather than a run started from the
  mission wizard). The patch was removed rather than kept as unexercised code. The honest consequence:
  the adoption lands before terrain generation but not provably before the level configs - everything
  read later reads the corrected manager, and the map fingerprint is identical.
- **A run-start reset wiped the evidence and made a working feature look broken.** The client applies the
  settings in the menu, i.e. before the run exists; clearing the counters at run start left a log
  showing `applied=1 drift=1` next to a test that timed out with `drift=0 none`. Reset only per-run
  bookkeeping, never the facts that describe what happened before the run.

## Readiness handshake: the client may not choose before it holds the host's data (build of 19:26)

"Both sides generated the same map" was, until now, a matter of timing. The host broadcast its settings
once per second and the client's wizard takes ~40 s, so the data always won the race - but nothing
*guaranteed* it, and the guarantee is what a co-op session actually needs: the client must not create its
run from whatever its own menu happened to have selected. So the client now waits.

**The exchange**, all of it headless and testable without any UI:

1. The client sends `Hello` (16) as soon as a peer socket exists - and keeps re-asking every 2 s while it
   is waiting (see the trap below).
2. The host answers with the full `RunConfig`.
3. The client confirms with `ReadyEcho` (17), reporting the values it holds.
4. The host compares that against what it sent and reports `echo=1`.

**The gate** is `CoopAuto.HoldForHandshake`: the client's wizard does not press anything until step 3 has
happened, with a 30 s escape that logs and proceeds, so a lost peer cannot wedge the wizard - the same
shape as the 45 s level-up barrier timeout.

Measured, PASS on both roles, twice:

```
normal                 client: check: handshake role=client ready=1 held=10,1s helloTx=7
                       host:   check: handshake role=host peer-hello=1 peer-ready=1 echo=1 cfgTx=4
gate forced (-ConfigDelaySec 15)
                       client: held=20,3s        host: echo=1
```

**Two checks, not one, on purpose.** The handshake answers "did the data arrive" and the `settings` test
answers "does the game run with it". Collapsing them into one verdict would leave a failure unable to say
which half broke - and they really can fail independently: a value can arrive intact and still be
overwritten by the wizard afterwards.

**The trap that made the handshake look done while it carried nothing.** The `Hello` is sent once at mod
load (~3 s in), and the host has no `RunSettingsManager` until ~25 s in, so the reply was "nothing to send
yet" and the 1 Hz broadcast quietly did all the work. The round trip was implemented, logged, and
useless. It is now re-asked every 2 s while the gate waits, which is what makes it a real
request/response - and the `helloTx=7` in the evidence above is exactly what proves it was exercised
rather than merely present.

**What is left of the plan's G milestone** is only packaging: the in-game host/join screen, the Steam
lobby and invites. The protocol underneath it (settings, handshake, ready gate) now exists and is
verified - which is also why the flags can stay the test path: the harness needs a headless join.

## Where the unlocks live, and whether the game reads them live (build of 20:01)

Host-profile adoption (I1) starts with a measurement, because the plan says so and because guessing here
would have been expensive: the answer decides whether adoption is a memory swap or a save-file reload.

`SaveData` is the object that holds everything worth adopting:

```
Version Timestamp
Challenges
WeaponSaveData          ClassModSaveData        BiomeSaveData      MutatorSaveData
MetaStatUpgrades        MileStoneStates
UnlockedChallengeSetIds UnlockedWeaponIds       UnlockedArtifactIds
UnlockedClassArtifactIds OverclockUnlockedWeaponIds UnlockedClassIds
DailyScore WeeklyScore BiomeScore ...
```

The probe mutated one of those lists in memory and asked the game's own query again:

```
check: profile role=client profile cls=4 wpn=29 art=13 mod=9 oc=0 meta=18 wpnSave=0 dwarf=11110000
check: profile live=yes cleared=4 before=11110000 afterClear=00000000 restored=11110000
```

`live=yes` is the result: clearing `UnlockedClassIds` made `SaveDataManager.IsClassUnlocked` return
false for every dwarf **in the same frame**, and restoring the list brought them all back. So the unlock
state is read live out of `SaveData` - no cache built at load, no reload needed. Adoption can therefore
happen in the menu, before the client picks a class, which is exactly the window the readiness gate from
the previous section already provides. Gear quirks and meta upgrade levels read from the same object, so
"adoption is a save-data swap" stops being the plan's guess and becomes a measured property.

**Three attempts to reach the save, and the reason each failed is the useful part:**

- `GameController` does not exist in the menu. It appears when a run starts - so the natural path
  (`gc.saveDataManager`) is unreachable during the one window adoption needs, and the probe sat in the
  menu reporting "no GameController yet" while the wizard ran without it.
- `SaveDataManager.SaveData` and `PCSaveFileManager.Data` are both **get-only**. Neither can simply be
  assigned, so adoption is either a getter patch or an in-place mutation of the existing object.
- The actual blocker: **`MetaManager.saveDataManager` is not a field on the interop type.** Fields and
  properties both look plausible from a decompile, and only dumping the members settled it:

```
type DRS.Meta.MetaManager fields={ isWrapped pooledPtr}
type DRS.Meta.MetaManager props={ OldPriceData statUpgradeCollection ... saveDataManager wallet
                                  runSettingsManager ... ArtifactRerolls ... transform gameObject ...}
```

  `GetFields()` returns only Il2CppInterop's own bookkeeping, while every real member - including the
  private ones - is a *property*. Reading a private field by name finds nothing and the code fails
  silently, at the most misleading moment. This is worth knowing for every future manager lookup in this
  game, so it is in the playbook gotchas too.

**One more finding with teeth:** both test instances read the *same* save profile
(`%USERPROFILE%\AppData\LocalLow\Funday Games\DRG Survivor\steam`). So at the time of this measurement
"the host's save" and "the client's save" were the same file, and a profile-adoption test would have had
nothing to adopt. Both halves of that are fixed in the next section: the launcher can now put the two
instances on different save slots, and it gives the saves back afterwards.

**Not measured yet:** I2 - how a run end turns stats into rank, mastery and milestones. That is the
plan's second unknown and the prerequisite for crediting the client's progress to the host.

## Two separate save profiles - and giving the owner's saves back (build 20:24)

I1 needs the host and the client to have *different* profiles, otherwise there is nothing to adopt. Two
things had to be fixed before that could even be tested.

**Separate slots.** The game keeps three save slots side by side in one folder
(`drg_save_slot{N}_{rotation}.dat`), so the instances can be pointed at different ones. The persisted
choice lives in `PlayerPrefs`, which both instances share - forcing it there would move both - so the mod
forces the slot at `PCSaveFileManager.Load` instead, and only when the launcher asks (`-coopsave=N`).
Measured:

```
host   save: forced slot0 (read back Slot1) before load 1
client save: forced slot1 (read back Slot2) before load 1
host   check: saves peerSlot=1 mySlot=0 separateFiles=yes sameProfile=yes
```

`separateFiles=yes` is the harness property that now has a test (`-Test saves`, PASS on both sides).

**But the slots hold the same progression.** `sameProfile=yes`: Slot1 and Slot2 both report
`cls=4 wpn=29 art=13 mod=9 oc=0 meta=18`. So pointing the two instances at different slots separates the
*files* but not the *content* - the owner has played all three slots to the same point. That matters for
the test design, and it is why the `saves` verdict is "different files", not "different numbers": the
latter would fail for a reason that has nothing to do with the code under test. I1 will instead *scrub*
the client's unlock lists in memory before the wizard, so the host has something real to give it.

The same measurement answered a second question: the client's profile travels over the wire
(`ProfileReport = 18`, plain ints like the rest of the handshake), so the host compares against numbers
the client actually holds rather than against what the host hoped it sent.

**The harness was writing the owner's saves and never restoring them.** `Backup-Saves` copied the profile
before a test and nothing ever put it back - so every test run left its progress in the real save. That
is fixed: `Restore-Saves` runs in the `finally` after the game processes are gone, and it verifies itself
against the backup. Two things came out of doing that honestly:

```
saves: restored and verified (14 files, canary removed)
```

- **First attempt broke the save layout**, and the hash check is what caught it. The backup root is the
  *contents* of `steam`, not the folder; restoring one directory level too high left the game with no
  `steam` folder at all. It was repaired from the backup and verified byte-identical (14 files,
  `differences=0`) before anything else ran. Both functions now share one `$script:saveDir` so the two
  copies cannot disagree again.
- **Timestamps cannot prove a restore ran.** `Copy-Item` preserves `LastWriteTime`, so an unchanged mtime
  means "faithful copy" *or* "nothing happened" - and a run that never reached gameplay writes nothing at
  all, which is exactly the case `-Test saves` produces. The restore therefore creates a canary file
  *after* taking the backup and requires it to be gone afterwards; the archive line above is the proof.

**Status:** `saves` PASS (both roles), restore verified, saves byte-identical to the pre-run state.
Next: I1 itself - the host's unlock lists to the client, applied in the menu before the class pick, with
the client's own profile scrubbed so the adoption is visible.

## The host's unlocks now reach the client before it picks a class (build 20:38)

I1's first real increment, and the measurement from the two sections above is what decided its shape: the
game reads `SaveData` live, so adoption is an in-memory swap that can happen in the menu - and the menu is
exactly where the readiness gate from the handshake step already holds the client.

**The six unlock lists travel verbatim.** `UnlockedClassIds`, `UnlockedClassArtifactIds`,
`UnlockedWeaponIds`, `UnlockedArtifactIds`, `OverclockUnlockedWeaponIds`, `UnlockedChallengeSetIds` are
read out of the host's `SaveData` as the strings the game itself stores, and arrive as strings
(`ProfileAdopt = 19`). Nothing in the protocol needs to know what an id *means*: `IsUnlocked` and
`IsClassUnlocked` compare against exactly these strings, so a format guessed wrong cannot half-work. The
counts are bounded on receipt (16 lists, 8192 items per list) because they come off the wire.

**Ordering is what makes it correct rather than lucky.** The client applies the lists inside the same
`TryConfirmConfig` gate that holds its wizard, and the gate now also waits for the payload when adoption
is on. So the class page - built after the gate opens - can only ever show the host's pool.

**And the client stops writing its profile.** `PCSaveFileManager.RequestSave` and `ForceSave` are skipped
while the client runs with borrowed unlocks; otherwise a save request would persist them into the
client's own file, turning "borrowed for this run" into "permanently mine". That is the core of I3.

`-Test profile-adopt` passes both sides, with the client's `SaveData` emptied first so there is something
to adopt (the three save slots all hold identical progression, measured earlier):

```
client  check: profile-scrub role=client cleared before={4 9 29 13 0 1} after={0 0 0 0 0 0} dwarf=00000000
client  check: profile-adopt role=client received {cls=4 mod=9 wpn=29 art=13 oc=0 sets=1}
client  check: profile-adopt role=client applied  {cls=4 mod=9 wpn=29 art=13 oc=0 sets=1}
client  auto: wizard page: UIBackButton ClassSelectButton_Scout ClassSelectButton_Gunner
                     ClassSelectButton_Engineer ClassSelectButton_Driller UIPlayCrumb ...
client  auto: step 22 - pressing (OnButtonClick) plan[4] ClassSelectButton_ 'ClassSelectButton_Driller'
client  RESULT: profile-adopt PASS reason=applied={...} class=ENGINEER classPageButtons=4 received=2
host    RESULT: profile-adopt PASS reason=peerClasses=0 deficit=1 adoptSent=2 mine={... dwarf=15}
```

The client's own save offered **no** classes (`dwarf=00000000`), the host handed over 56 ids, and the
class page then offered **four** - Driller among them, a class that client's save never unlocked.

**Why the assertion is on the class page and not on the final class:** this harness overrides the
client's class afterwards by design (`OverrideClientClass`, from the character-visuals work), so
`class=ENGINEER` is the harness talking. "The page offered four classes to a client whose own save offered
none" cannot be true for the wrong reason; "the client plays Driller" could be.

**Two harness bugs this run exposed**, both of which had been silently shaping results:

- **The game skips wizard steps on its own.** The client stood on `plan[3] MissionNodeButton_` while the
  *class* page was up, because that save remembers its last node and the node page's buttons are all
  inactive - so a rigid plan waits there forever, and the symptom is indistinguishable from a broken
  adoption. The plan now advances to a later step whose button is actually on the page and logs
  `auto: skipped plan[3]` when it does.
- **`classPageButtons` was the *last* page's count, not the class page's.** Every page change refilled it,
  so the hazard page left it at zero and a *passing* adoption reported failure. It is a maximum now: a
  fact about a run must survive the pages that come after it.

**Not in this increment, and worth saying rather than implying:** meta upgrade levels, gear
inventory/loadout and player rank. The six lists decide *what the client may pick*; those decide *how
strong it is*. I2 (crediting the client's progress back to the host at run end) is untouched.

## The corpse that keeps walking: `Die` runs, the animator never comes back - FIXED (build of 23:06)

Owner-reported: "the other dwarf sometimes keeps running around as a corpse after a revive." Measured, and
the cause is not where it looks:

```
host  check: corpse die       dmg=KINETIC hp=0 alive=0 anim=Idle#1432961145 t=12.96
host  check: downed role=host (game-over blocked)
host  check: corpse anim-end  Walk condition=DIE hp=0 alive=0 anim=Idle#1432961145 t=12.96
host  check: revived          hp=100 alive=True | after={hp=100 alive=1 anim=Dying#-1546996312}
host  check: corpse after-revive hp=100 alive=1 anim=Dying#-1546996312 t=2.64
client  downed: stood up on its own (hp=13) hp=13 alive=1 anim=Dying#-1546996312 t=0.74
```

- **`Player.Die(EDamageType, long, bool)` runs.** The mod only skips `GameController.OnPlayerDeath`, so the
  death itself - and with it the death animation - still happens.
- **`Player.IsAlive` is a get-only property (derived), but the animation is a separate state.**
  `WalkPlayerAnimator.HandleEndCondition(DIE)` switches the animator to `Dying` (hash `-1546996312`; normal
  `Idle` is `1432961145`). Writing `currentHp` back does not touch it.
- **So the pose stays dead while the dwarf moves**, and it is the same for the game's own recovery: hp 0 to
  13 leaves the animator in `Dying` too. "Sometimes" is about which path came first, not about the pose
  sometimes recovering - neither path recovers it.

`BasePlayerAnimator` declares no counterpart to `HandleEndCondition` in the stubs (only `UpdateAnimator`,
`SetIdle`, `SetMiningWeight`), so the way back had to be found by measurement, and the measurement is what
settled it (`20261018-225649-corpse`, both roles byte-identical):

```
corpse params   n=8 {isIdle:Bool isDead:Trigger isAngry:Trigger moveSpeed:Float
                     isMining:Trigger isPickUp:Bool flying:Bool flyType:Int}
corpse baseline hp=145 alive=1 anim=Idle#1432961145 t=0,00 trueBools=[isIdle]
```

**The death pose is put on by a Trigger (`isDead`), not by a boolean** - so there is no latch to clear:
`SetBool` cannot clear a trigger, and the only boolean ever set is `isIdle`, the normal idle state that
the game re-writes every frame. A "clear every boolean" step was written first, ran, and was removed
again: it changed nothing and mutated unrelated state. The pose has to be reset at the **state** level,
and `Animator.Rebind()` + `Update(0f)` is exactly that:

```
corpse reset where=revive before={hp=100 alive=1 anim=Dying#-1546996312 trueBools=[isIdle]}
             step1(rebind)={hp=100 alive=1 anim=Idle#1432961145 t=0,00} fixedBy=rebind
corpse stable t=+1,0s hp=100 alive=1 anim=Idle#1432961145 dying=0 restores=1/1
```

The reset runs in **both** paths that bring a dwarf back - the mod's own revive (`CoopDowned.ReviveTick`)
and the game's self-heal (`downed: stood up on its own`), which produce the corpse equally - and
`BasePlayerAnimator.SetIdle(false)` is kept behind it as the handoff named it.

**Verified end to end, twice**, `-Test corpse -NoGod -TestQuit none` (`20261018-230341-corpse` and
`20261018-230838-corpse`), PASS on both roles both times:

```
host   RESULT: corpse PASS reason=restores=1 clean=1 stable=1/1 last='revive fixedBy=rebind' anim=Idle#1432961145
client RESULT: corpse PASS reason=restores=1 clean=1 stable=1/1 last='self-stand fixedBy=rebind' anim=Idle#1432961145
```

The second run had eight further revives and every one was reset the same way
(`corpse stable ... dying=0 restores=8/8`, `fixedBy=rebind` each time). `-TestQuit none` matters: the
launcher otherwise lets the first instance that finishes quit, and the peer then has no partner left to
drive the revive it is still waiting for.

**Two defects in the check itself, both found by the check failing for the wrong reason.** The first
version sampled the pose once at +1 s regardless of state and failed the client
(`20261018-225649-corpse`) - but that client had **re-died 0.7 s after a reset that had demonstrably
worked**, so `hp=0` with `Dying` was the game being right, not the bug. The sample now only counts while
the dwarf is **alive**, and an alive dwarf in `Dying` still fails immediately. The second is the one the
playbook warns about: a check that cannot fail proves nothing, so `-CorpseNoReset` runs the same test with
the reset deliberately left out. It reports the bug and FAILs (`20261018-231400-corpse`):

```
corpse reset  where=revive skip=flag(nreset) fixedBy=none
corpse stable alive-but-dying hp=100 alive=1 anim=Dying#-1546996312 t=2,15 restores=1/0
RESULT: corpse FAIL reason=restores=1 clean=0 stable=0/1 last='revive fixedBy=none(flag)' anim=Dying#-1546996312
```

**Honest gap:** neither passing run had a re-death land inside the 1 s window, so the alive-gate was not
exercised again after the run that motivated it; what the passing runs prove is that the gate cannot
produce a false PASS. And this fixed the *local* dwarf's pose - the puppet's animation is still not synced
at all (`CoopPuppet` drives only position), which is a separate item.

## Both down ends the run - and two ways the first attempts were wrong

Owner decision: when both dwarves are down, the run ends the way it does in solo. The owner also supplied
the mechanism behind the game's *own* natural end, which is worth writing down because it explains every
unforced end in this session: **the first elite dies, the transport-capsule phase starts with a short
countdown (21 s in the observed case), and missing the capsule ends the run immediately** -
`MISSED_DROPPOD`. That is why runs ended on their own after ~4-5 minutes and why a run that never got
there never ended.

**Attempt 1 - only in the death patch.** The patch can ask "is my partner down right now", but the partner's
hp arrives a round trip later: measured, both dwarves died 40 ms apart and each still saw a live partner, so
both took the normal downed path and the run hung for minutes.

**Attempt 2 - in the tick, on the flags.** `IsDowned && RemoteDowned` fired while the dwarf was *up*: the
client's `IsDowned` stayed set while its own hp was 13 (`downed=1` in the tick log, hp=13 in the same line),
so the run was declared both-down off a stale flag. That also exposed the stale flag itself - the bot's
`Tick` returns early while `IsDowned` is set, so the dwarf had been standing still while alive.

**Attempt 3 - what is in place now.** One shared test, `CoopDowned.CannotRevive()`, reads the hp both sides
actually have (with the `everSawRemoteAlive` gate so the menu's hp=0 dummy is not a downed partner), and
*both* callers use it - the death patch (may the game's own game-over run?) and the tick (end the run) - so
the two cannot disagree about what "down" means. The tick also clears a flag that outlives its down, keyed
on hp, because `isAlive` is derived from hp. And the rule is gated on `ProbeState.Gc != null`: measured, an
ungated version fired in the menu (`selfHp=0 remoteHp=0 haveRemote=0`) and asked to end a run that does not
exist.

**Verified:** the menu false positive is gone with the gate, and the stale-flag clear fired repeatedly in
one run (`stood up on its own (hp=13), flag cleared`). The game's own game-over *does* run when the patch
lets it through - an earlier run ended for the client with `end screen setup condition=DIE` while its own
log read `both down ... remoteHp=0`.

**Not verified end to end, and a new finding while trying:** the game **stands a downed dwarf back up on its
own** - hp 0 to 13 within about a second, three times in one run, without the mod's revive path (its
`check: revived` line never appeared). So "both down" is a window of about one second rather than a stuck
state, and it is only terminal when both are at hp <= 0 long enough for the other side's hp to arrive. The
rule therefore stays conservative: it fires only when the run genuinely cannot continue, which is the safe
direction to be wrong in - but the run that verifies it end to end still has to be produced. What the game
does with a downed dwarf (self-recovery, and how that interacts with the mod's downed state) is the open
question here.

## The loan ends with the run, and the client keeps what it earned (build 21:56)

**Owner decision** (asked, because the two rules contradicted each other): the client keeps its own earned
progress, and only the borrowed data stays borrowed. Nothing in I1's transfer and nothing in I3's block was
weakened to get there - instead the loan is now *given back* at the moment the run ends, so the game's own
save then writes a profile that is the client's plus everything it earned while playing.

- **Captured before the loan is applied**: `CaptureOwnBorrowed()` records the six lists, the meta levels and
  the gear as they stand, because after `ApplyPeerAdopt` they are no longer the client's.
- **Given back at the run end**: `EndLoan()` runs from the postfix of `GainRunEndRankXp` (after the credit,
  so the credit is part of what gets written) and from `UIEndScreen.Setup` as a backstop, because a run can
  end through `DIE`, `WIN`, `MISSED_DROPPOD` or `ABORT`. It is idempotent.
- **Per field, and "earned" is a subtraction, not a wildcard**: an id is dropped when the host lent it and
  the client did not have it (`host \ own`), so anything the client gained during the run - which is in
  neither - survives. Meta levels keep the client's own plus its rise above the borrowed level; gear items
  are matched by `HC` (the per-item hash, not `ID`, which is only the type) so a drop in the run is not
  mistaken for a lent instance.
- **Then** `BlockWrites` is released and the game's own `SaveDataManager.Save(true)` writes. I3 still blocks
  everything *during* the run, which is what keeps the loan out of the file mid-run.

**Lifetime bug hit on the first attempt, worth recording because it was invisible:** the snapshot was
cleared by `Reset("StartGame")`, but the loan is taken *in the menu*, before the run - so the run-end
log said `nothing to give back (own=False peer=True)` and the whole feature was a no-op that still *looked*
wired up. The loan's life now hangs off the adoption, not the run start.

**Verified at the file level, not from the mod's own log lines.** The save files are **JSON**
(`drg_save_slot{N}_{rotation}.dat`, `{"Version":9,...}`), so the runner now copies the used slots into the
run archive before restoring the owner's saves, and the end state can simply be read:

```
client  check: loan ended why=rankXp wpn=29->0 cls=0 metaSum=90 gear=0

client slot after the run     UnlockedClassIds  weapons  meta levels  gear  classXp  credits
  drg_save_slot1_1/2.dat (*)  []                0        18 x 5       0     5958     141836
  drg_save_slot1_3.dat        []                0        18 x 5       0     5935     141818
  drg_save_slot1_0.dat        []                0        18 x 5       0     5956     141834
```
(*) the newest write (`Timestamp` 214523795, matching the run).

- **The borrowed half is absent**: the host lent 4 classes, 29 weapons, 18 meta entries at level 0 and 6
  gear items; the client's file has none of them.
- **The earned half is present**: the file's class XP total is 5958, and the client's own log measured
  `classXp 5956 -> 5958` for `perfXp=2`. The credits moved with it (141834 -> 141836). That is the thing
  that used to be computed and then thrown away.

**Not yet exercised by the fixture, and labelled as such:** the "earned beyond the loan" rules need
something earned during a co-op run - a weapon or gear item dropped on the client's side - and the client's
world has its spawner suppressed, so neither the set difference nor the `HC` subtraction has been seen to
fire in a run yet.

## I2, first measurement: what a run end does - and two harness defects found on the way

The question for I2 is what a run end turns into permanent progress, because that is where I1's borrowed
profile and the client's own profile would collide. The entry point is declared rather than guessed, and
the credit is direct:

```
host  runend: GainRunEndRankXp(161) BEFORE classXp=5956 playerRank=19 classLevels=58 runStartRank=DRILLER:14/3155
host  runend: GainRunEndRankXp AFTER  classXp=6117 playerRank=19 classLevels=58
host  runend: end screen setup condition=MISSED_DROPPOD
```

`PlayerRankManager.GainRunEndRankXp(int performanceXp)` is public, and the class XP total moved by exactly
its argument (5956 + 161 = 6117). The end screen then reports the condition. Around it, from the
*declarations* (bodies are stubs, so this is what exists, not what was called):

- `ScoreManager` turns the run into a score with explicit weights - `GOLD=5`, `NITRA=7`,
  `CRAFTING_MATERIAL=15`, `RED_SUGAR=3`, `SECONDARY_OBJECTIVE=500`, `PLAYER_LEVEL=100`, `ARTIFACT=1000`,
  `WIN_MOD=1.25`, plus a hazard table - and raises `OnFinalScore`.
- `UIEndScreen.ShowProgression(int rankXpEarned, int creditsEarned)` is the display side of the two numbers.
- Mastery has four writers: `SaveDataManager.TrySetWeaponMastery`, `TrySetClassModMastery`,
  `TrySetBiomeMastery`, `TrySetMutatorMastery`.
- Milestones go through `MilestoneTracker.GiveMilestoneReward(MilestoneData, doSave)` and
  `MilestoneSaveUpdate.NewlyCompletedMilestones`.

**Defect 1 - the rescue aid was permanent.** The bot's rescue branch lifts its own hp to 100000 so the
rescuer survives the 5 s revive window. The game does *not* clamp `currentHp` to the dwarf's max hp, so
that 100000 simply stayed: measured, a client whose rescue branch fired once sat at ~99900 for the rest of
the run taking 10 damage per hit, and **its run could no longer end by death at all** while the host's did.
That is a harness aid silently deleting a whole outcome from every test that touches it. Fixed: the pre-pin
hp is captured and given back when the rescue branch ends (`bot: rescue pin released, hp back to 63`).

**Defect 2 - both dwarves down at once wedges the run.** With `-NoGod`, both went down within seconds of
each other and stayed down: `hp=0 alive=False` for 139 host ticks and 119 client ticks (~3.5 minutes) with
no `UIEndScreen.Setup` and no credit. Nothing can revive anyone - there is no live partner - and the mod's
downed state holds the game away from its game over. A solo run would have ended. This belongs to the
downed/revive item (F), not to I2, but it is recorded here because it silently removes the run end from any
test that dies twice, and because "both down" needs a decided behaviour anyway.

**The reliable way to reach a run end in this harness** is to leave god mode on and let the mission run to
its own outro, which the autopilot already watches:

```
auto: watch: active=CoreOutro      <- the mission is ending (drop pod phase)
runend: GainRunEndRankXp(161) ...
auto: watch: active=UIEndScreen
```

**Seen once and worth knowing (F, not I2):** the downed/revive path demonstrably ran in the same session -
`check: downed remote role=client (remote hp=0)`, `check: rescue started role=client dist=13,3`,
`check: revived role=host hp=100 alive=True`. Noted as an observation; F's own test is still open.

**Still open:** mastery and milestone writes need a run that actually plays (the trigger below ends one on
demand, but the run it ends has nothing to complete).

**A run end can be forced, and that is what made the rest measurable.** Waiting for a mission to end by
itself is not a test: of four attempts, one reached the outro, one wedged with both dwarves down, and one
had not ended after 9 minutes. `CoreGameEvents.TriggerCoreRunOutro(ECoreRunEndCondition)` is public and
static, and it is the same door the mission's own end goes through, so `-cooprunendforce=<win|die|abort>`
runs the real chain on demand. Whole measurement: ~90 seconds instead of ~9 minutes, both sides, twice.

```
host    runend: forcing condition=DIE via CoreGameEvents.TriggerCoreRunOutro
host    GainRunEndRankXp(2)  BEFORE classXp=5956  AFTER classXp=5958   end screen condition=DIE    writesBlocked=0
client  GainRunEndRankXp(3)  BEFORE classXp=5956  AFTER classXp=5959   end screen condition=DIE    writesBlocked=0

host    GainRunEndRankXp(17) classXp 5956->5973   condition=WIN   stages=1
client  GainRunEndRankXp(18) classXp 5956->5974   condition=WIN   stages=1
```

**Each side credits its own profile with its own performance** (`runStartRank` names the class each one
actually played: host DRILLER, client ENGINEER). The `WIN` path behaves the same as `DIE` in this respect,
so the credit is not conditioned on winning.

Milestones stood still at 78/281 in every *forced* run, including the wins - but a forced win 20 seconds
into a run has no stage progression, no hazard and no milestones to complete, so that is a limit of the
fixture and **not** evidence that milestones are unaffected. A *real* run end (god mode off, 592 kills) did
move them: `milestones 78/281 -> 79/282`, so the milestone write path is live and writes at the run end.

> **Corrected later** ("A run that actually plays", below). Counting only *completions* hid the thing that
> moves constantly: the summed `Progress` of the same list advances by half a million in a three-minute run,
> per instance and in proportion to that instance's own kills. And a forced run end *does* reach the
> milestone completion path - what it does not reach unattended is the end screen, because a won run puts up
> a gear-found popup that nothing dismissed. So the fixture limit above was real but localised, and the
> "writes at the run end" sentence was right for the wrong reason.

**The collision I2 exists to find, measured.** With adoption on and the same forced end:

```
client  check: profile-scrub ... after={0 0 0 0 0 0} metaSum=90
client  check: profile-adopt ... applied {cls=4 mod=9 wpn=29 art=13 oc=0 sets=1}
client  save: blocking the client's writes (RequestSave) - adopted unlocks are in memory only
client  runend: GainRunEndRankXp(3) BEFORE classXp=5956 AFTER classXp=5959  writesBlocked=2
client  runend: end screen setup condition=DIE
```

The client plays the run, the game computes and applies its rank XP, and then I3's write block throws the
whole thing away: the client's own earned progress never reaches its file, because the block is on the save
request rather than on the borrowed data inside it. That is a design decision, not a bug in either half -
I3 is right that borrowed unlocks must not become permanent, and I2 is right that the game credits the run -
but the two rules now contradict each other at exactly this point.

## Gear transport works, and the cache needed rebuilding (build 21:03)

The third piece of I1: the client's *inventory*, not just its unlocks and its strength. Gear is the first
thing in this mod that is **structured** rather than a list of strings, and that changed the shape of the
work in two places.

**1. Gear cannot travel as live objects.** `GearSaveData` has twelve members, three of them arrays
(`S`, `SG`, `ST`); `GearEquipSaveData` has six arrays. The runtime dump settled what they actually are:

```
GearSaveData      props={ HC:Int32 ID:String R:Int32 L:Int32 U:Int32 N:Boolean
                          S:Il2CppStructArray`1 SG:Il2CppStructArray`1 ST:Il2CppStructArray`1
                          RQ:Int32 LQ:Int32 F:Int32 ... }
GearEquipSaveData props={ ID:String A,C,G,Ta,To,W:Il2CppStructArray`1 ... }
```

So everything is a *property* (the interop rule again) and every `int[]` is an `Il2CppStructArray<int>`.
Putting a `GearSaveData` on the wire would mean both sides agreeing on a runtime detail; instead the mod
carries wire-shaped items (`GearItem`/`EquipItem`, plain ints and arrays, arrays as count + values), and
the client rebuilds game objects from them - arrays built by indexed fill, properties written through the
same generic accessor used for reading.

**2. The save is not what the game shows.** `GearManager` holds `AllGear` (`List<GearView>`), and measured
at the handshake it *mirrors the save exactly* - host `allGear=6 saveGear=6`, client `allGear=0 saveGear=0`
- which is what a load-time cache looks like. Replacing `SaveData.GearSaveData` and stopping there would
have left the inventory screen showing the client's own items while the save said otherwise.

The rebuild goes through the game's own loader, and the log was arranged to say *which* half of that call
does the work, because the decompiled bodies are stubs and neither half can be read off them:

```
client  RESULT: profile-adopt PASS ... {gear 0->6 hostGear=6 collected=6 glvl=18 load=3
                                        manager=0->6 loaderFilled=0} hostGear=6 loadedGear=6
```

**`loaderFilled=0` is the finding**: `SaveDataManager.LoadGear(GearManager)` *returns* the rebuilt list
(6 items) but does **not** store it in the `AllGear` field the UI reads. The mod assigns it. Had I assumed
"the loader loads", the inventory would have stayed empty and the save would have looked perfectly
adopted - the same shape of bug as the meta wallet, in a different subsystem.

The counters were written and read back (`collected=6 glvl=18 load=3`), so those are not "no exception, so
presumably fine" but a value that is demonstrably in the save afterwards.

**Gap, stated rather than implied: the loadout half is unverified.** `EquippedGear` is transported and
rebuilt, but *both* profiles have nothing equipped (`saveEquipped=0` on both, and the host's own
`equippedList=15` with an empty save list is consistent with "15 slot records, none of them filled"). A
fixture with an equipped loadout would be needed to show that the client's equip slots follow - which means
driving the gear UI to equip something on the host first.

## Player rank: measured, and deliberately not adopted

The last item of I1 turned out not to be worth building, and the evidence is in the settings rather than in
a run:

- `PlayerRankSettings` has one member: `ClassRanksPerPlayerRank`. `ClassRankSettings` has one: `RankXP`.
- So `Rank` is derived per class from `Xp` via XP thresholds, and `PlayerRank` is an *aggregate* of the
  class ranks. Neither adds a stat mod, a currency or an item.

Rank drives milestones, the progression screens and `UIEndScreen`'s "XP gained" display - not the run's
power. A low-rank client is therefore not a weaker player, which is the only reason I1 exists. And since
rank *is* progress, adopting it would actively work against I3 (the client's own progress must stay its
own) once the run-end credit (I2) lands.

There is a second, mechanical reason not to touch it: `PlayerRankManager` caches the ranks it read at load
(`ranks`, `dataLoaded`, `PlayerRank`, `TotalClassLevels`) - the same cache-versus-save split as gear, but
with nothing to gain from bridging it.

## Meta levels, and the cached values they feed (build 20:45)

The second half of I1: not just what the client may *pick*, but how strong it is. Meta upgrade levels live
in `SaveData.MetaStatUpgrades` as `{Id, Level}` pairs, so they travel as pairs and are rebuilt with the
game's own constructor - the same verbatim rule as the id lists.

**The part that would have quietly not worked.** `MetaManager` does not read the levels when the run needs
them: it computes `StartingGold`, `StartingNitra` and `ArtifactRerolls` into cached fields, and the only
call to `UpdateWalletUpgrades()` is inside `MetaManager` itself. Replacing the levels and stopping there
would leave the list looking perfectly adopted and the run using the old numbers - a change that appears
to work and does not. So the mod calls `UpdateWalletUpgrades()` after applying, the game's own refresh
rather than a reimplementation of it.

**Measured, including the derived values:**

```
client  check: profile-scrub role=client ... dwarf=00000000 metaSum=90
client  check: profile-adopt role=client received {cls=4 mod=9 wpn=29 art=13 oc=0 sets=1}
                                        meta=18 metaSum=0 gold=0 rerolls=0
client  RESULT: profile-adopt PASS ... meta 90->0 hostMetaSum=0 gold 10->0 hostGold=0 goldMoved=1
host    RESULT: profile-adopt PASS reason=peerClasses=0 deficit=1 adoptSent=2
```

`gold 10->0`: with the scrubbed level 5 the game's own wallet computation produced 10 starting gold, and
after adopting the host's level 0 levels and refreshing it produced the host's 0. The adoption reaches the
game's derived state, not only its storage.

**The fixture had nothing to measure - the third time this pattern bit.** The host's 18 meta entries are
*all at level 0*, so `0 -> 0` reads identically whether the adoption happened or never touched anything.
The scrub therefore sets the client's levels to a distinctive 5 instead of 0: its job is to make the
client's profile *different* from the host's, not poorer. The verdict compares sums, so an untouched
profile cannot pass - and `goldMoved` is reported explicitly, so a wallet check that was skipped for lack
of a difference is visible rather than silently green.

**Still open in I1:** gear inventory/loadout and player rank. Then I2, crediting the client's progress back
to the host at run end.

## A run that actually plays: milestones complete at the end screen, and mastery is empty (build of 23:45)

I2's last open item was the one fixture that could not answer it: the forced end ran the run-end chain 20
seconds into a mission, so there were no stages, no hazard and nothing to complete. The fixture now exists
- `-RunEndDelay 180` plays for three minutes and *then* ends through `CoreGameEvents.TriggerCoreRunOutro`,
so the run has kills, levels and a stage behind it. Extending the probe to the number that had been
invisible turned three separate "nothing happened" readings into results.

**Milestones: the completed count was the wrong thing to watch.** `MileStoneStates` entries are
`{Guid, Progress, IsCompleted}` - read out of the save file, which is JSON - and the probe only counted
completions. So `78/281 -> 78/281` in every earlier run read as "the write path is dead" when it only meant
"nothing crossed its threshold yet". Summed over the list, a three-minute run moves it by half a million:

```
host    milestonesStart=78/281 p=2452142  -> 78/281 p=3022974  -> end screen: 82/284 p=3022983   kills=456
client  milestonesStart=78/281 p=2452142  -> 78/281 p=2719156  -> end screen: 78/281 p=2719156   kills=221
```

Three facts in one line, none of them visible before:

- **Progress is written during the run**, per instance, and it is proportional to that instance's *own*
  play: +570 832 on the host against +267 014 on the client, with 456 against 221 kills (ratio 2.14 against
  2.06). The same shape in the run before it (+543 036 / +266 941 against 457 / 210 kills). Each side
  advances its own copy of the profile, which is exactly what the later "the client keeps what it earned"
  decision assumes.
- **The credit itself moves nothing** (`p=3022974 -> p=3022974`), so the run-end credit is not where
  milestone progress comes from.
- **The completion path runs at the end screen, and only there**: the host went `78/281 -> 82/284`, i.e. four
  milestones completed *and* three new entries appeared in the list. That is `PostEvaluateMilestones` /
  `GiveMilestoneReward` doing their work - the path that every earlier run reported as inactive because the
  end screen never ran.

**Mastery is empty on this profile, and the save file says so.** After a three-minute run with 445 kills:

```
"WeaponSaveData":[],"BiomeSaveData":[],"MutatorSaveData":[],"ClassModSaveData":[]
```

That is the owner's own played slot read straight out of a backup, not a runtime misread - all four mastery
lists are empty and a played run creates no entry in any of them. It matches the profile's run-type page,
where only the campaign Mission Road is unlocked and **Mastery is `[unavailable]`**. So the plan's "mastery
write path" item is **blocked on a fixture, not open**: it needs the Mastery mode unlocked (or a profile
that has played it), and no amount of code on this profile will produce a number to read.

**The blocker between the credit and the end screen is a popup nobody dismissed.** A won run puts up
`UIGearFoundForm` before the end screen, and the autopilot - which already learned to serve `UILevelUpForm`
- had no case for it, so the host sat on the gear popup while the client (which won no gear) sailed through:

```
host  runend: GainRunEndRankXp AFTER  ... 23:44:44.660
host  phase: gearfound-open                23:44:46.024
host  runend: end screen setup condition=WIN milestones=82/284   23:44:46.058   <- 1.4 s after the credit
```

`UIGearFoundForm.OnContinueButton()` is the button's own handler, so the autopilot now calls it, the same
way it calls `UILevelUpForm.OnSkillChosen`. With that, both roles report `endScreens=1 condition=WIN`.

**And a verdict that described a chain that had not finished.** The `runend` verdict is written from the
credit postfix, which is *before* the end screen - so it printed `endScreens=0 condition=none` and empty
end-screen reads (`->?`) about a chain that was still running. That was read as "the forced end never
reaches the end screen" and was simply wrong: in the run where the host's end screen did not appear, the
gear popup above is why, not the force. The verdict is now deferred a tick or two (15 s grace, so a run
that genuinely never reaches an end screen still gets a verdict) and carries the real values.

**Correction to the earlier section:** "milestones 78/281 -> 79/282 in a real run" is consistent with this,
and the sentence next to it - that a forced end "has no stage progression, no hazard and no milestones to
complete" - was only half right. A forced end *does* run the completion path; what it cannot do is reach
the end screen unattended, because of the gear popup.

**What is still not exercised:** the client completed no milestones in these runs (its own progress is
lower), so "both sides complete their own" is inferred from the host's result plus the per-instance
progress, not measured on the client. And mastery remains unmeasurable here.

## The partner's dwarf: the puppet now plays the pose the remote is actually in (build 00:01)

The other half of the owner's "corpse" report, and the half the earlier fix did not touch: the local dwarf's
pose is repaired, but the *partner* sees a `CoopPuppet` that was driven from position and rotation only.
A downed dwarf stops moving, so the puppet came out as `Idle` - a dwarf standing there where the partner's
screen should show a corpse.

**Measured first, and the measurement changed the plan.** The obvious fix is to drive the puppet's
`Animator`, so the first question was whether the pose lives there. Reading the player tree off a real run
(20261018-234503) settled it: **not one `SkinnedMeshRenderer` anywhere** (`[m/0]` on every node, 8 renderers
in `GFXContainer`), and the mesh sets do not change between alive and down:

```
puppet: view local=alive ... localMesh=[6:,TankBody_Model,Cube,Cube,Quad_1x1m,GraplingHook]
puppet: view local=down  ... localMesh=[6:,TankBody_Model,Cube,Cube,Quad_1x1m,GraplingHook]
```

So two candidate layers were wrong before writing anything: it is neither a skinned rig nor a mesh swap of
the body. What *does* differ is the animator state (`Idle#1432961145` vs `Dying#-1546996312`), and the puppet
already followed that for locomotion (`Idle`/`Running`), so the pose is carried by **transform animation on
the body-part hierarchy** - which is exactly what the `Animator` drives. That made the animator the right
layer, but it also ruled out the cheap version of the fix: *deriving* down/dead from hp means guessing a
parameter name, and the earlier measurement (20261018-235525) showed the guess landing on `Idle` for a downed
remote.

**So the state travels instead of being guessed.** New packet `AnimState` (its own type, not a field on
`PlayerState`: a peer on an older build would read `PlayerState` short and desync every packet after it,
while an unknown type is simply ignored). It carries the local player's `GetCurrentAnimatorStateInfo(0)
.fullPathHash`, sent when it changes plus once a second, because the channel is unreliable and a lost
"I am dying" would leave the partner's puppet standing on a corpse until the next state change. The puppet
plays it:

```
puppet: played remote anim Idle#1432961145            <- and Running#256545655 while walking
puppet: mirror remote=down puppet={Idle#1432961145}   <- the remote is a corpse, the puppet is standing
puppet: played remote anim Dying#-1546996312          <- 100 ms later the pose is on it
puppet: sample down +1,0s dying=1 puppet={Dying#-1546996312} remoteAnim=-1546996312
puppet: played remote anim Idle#1432961145
puppet: sample up +1,0s dying=0
RESULT: puppet PASS reason=down=1/1 up=1/1            <- both roles
```

`-Test puppet` (`-NoGod -TestQuit none`, the same fixture as `corpse`) samples **1 s after each flip of the
remote's life state** and counts clean or not - the shape the `corpse` check already uses, so the verdict is a
ratio and not an opinion. It needs **both** halves: a puppet stuck in `Dying` passes the first and fails the
second, which is the same bug from the other end.

**Negative control is a real run, not a flag.** Before the puppet played the remote's state
(20261018-235525) the same sample would have read `dying=0` with the remote down - the log line is in the run
above (`puppet: view local=alive remote=down ... puppetAnim=Idle#1432961145`). So the check is not blind; it
was failing an hour before it passed.

The parameter-derived drive in `CoopPuppet.UpdateAnimation` stays, but only as the **fallback** for a peer
that has never sent a state: it is a guess (it maps a derived speed onto whichever names look like movement)
and it would otherwise fight the real answer by transitioning the state machine away from it.

**What this does not claim:** the verdict is about the *pose state*, not pixels. The puppet now plays the
same animator state the partner's dwarf plays, on a clone with the same meshes and the same controller -
that the death pose then reads as a corpse on screen is inferred from that, and was not verified with a
screenshot. The samples are also thin: one down/up pair per instance per run, same convention as `corpse`.

### The walk cycle now follows the same phase (build 22:31)

`AnimState` carried only `fullPathHash`, so the puppet played the right state from its **own** clip
time: the pose was right, the two walk cycles were not in step. `AnimPhase` (packet 28, unreliable,
~10 Hz) adds `normalizedTime`; it repeats the state hash so a lost `AnimState` is also recovered
from a phase packet. The puppet uses `Animator.Play(hash, 0, phase)` when the state changes and,
for the same state, only corrects when the phase error exceeds 0.1 - playing the state every packet
would reset the pose ten times a second.

- `-Test animphase` on the walking bot: **PASS both roles**, `good=15/15 moved=1`
  (`20261019-223142-animphase`). Host `lastErr=0.08 corrections=0`, client `lastErr=0.00
  corrections=12`. `moved=1` means the remote phase changed between samples, so this is not the
  constant-Idle trivial pass.
- Negative `-AnimPhaseOff` (`-coopanimphaseoff`, `20261019-223338-animphase`): both sides FAIL on
  state (`phase=off (negative control)`), not by test timeout.
- Still open: the correction is discrete (10 Hz + 0.1 threshold), so a very fast state change can
  show a short mismatch before the next packet. Weapon/equipment animations, Bosco/turret
  animations and enemy animator state remain unsynced.

## The loot value was never wrong - the plan was (build 00:37)

The plan carried an open item since the stage-2 loot work: *"the broadcast value reads 1, because
`Pickup.OnSpawn` fires before the game sets the value; hook `set_value` or read one frame later -
cosmetic"*. It has read one frame later for a long time (the `SpawnedQueue` drain), so the honest question
was whether that deferral buys anything. Measuring it turned the item inside out.

**The deferral buys nothing, and there was nothing to buy.** Both fields, at spawn *and* one tick later, over
130 samples:

```
loot: send read=1 atSpawn=1 differs=0 type=CURRENCY Value=1 value=1
check: loot value= send={sent n=50 min=1 max=1 sum=50 differs=0} ...
```

`Value` is a getter *method* on this build and `value` the raw field, so both were read. Neither ever
changes, on the fixture's own drops or on the natural mining drops mixed in.

**Why 1 is the truth, two independent ways:**

- **The API says so.** `SpawnMaterial(ECurrency material, int count, Vector3 position, float forceMod)` -
  the parameter is a **`count`**, not an amount. `SpawnMaterial(NITRA, 5, …)` makes *five one-unit pickups*,
  and the host broadcast exactly five per drop. There is no "real value applied afterwards" for a material
  pickup; one pickup is one unit.
- **The game's own wallet says so.** The host claims its own drops, so its wallet is the *game's* accounting,
  and it rises 1:1 with claims:

```
check: loot value= send={sent n=10 ...} wallet={Nitra=10} pickups=10 claims=10
check: loot value= send={sent n=50 ...} wallet={Nitra=50} pickups=50 claims=50
check: loot value= send={sent n=80 ...} wallet={Nitra=80} pickups=80 claims=80
```

**So the plan's PASS criterion was unsatisfiable.** It asked for `value != 1`, which is the one thing this
build can never produce - the item would have sent the next agent to "fix" correct behaviour, and any check
written to it could only ever fail. The `loot` check now asserts the invariant that actually has to hold -
one pickup carries one unit and the sum matches the count (`min == max == 1`, `sum == n`), on both halves of
the pipe - and PASSes on both roles (`20261019-003708-loot`).

**A flag that controlled nothing, removed.** A `-cooplootvaloff` switch was written to put the old
spawn-time read back for a negative control, and then deleted: it selects between two numbers that are
*always* equal (`differs=0`), so it cannot make the check fail, and a control that cannot fail is not a
control. The evidence for that is the `differs=0` column, not an argument.

**Two harness notes from the three runs it took:** the check fired after five broadcasts and the host quit
(the default `-TestQuit both`), so the client - which had mirrored nothing yet - lost its partner and timed
out; this check needs `-TestQuit none` like `corpse` does. And the wallet figures in the *verdict* are read
at that instant (`hostWallet={Nitra=0} hostClaims=0` in the PASS reason), so the 1:1 series above is the
thing to read, from the periodic log line, not the verdict.

## The shop between stages is reachable, and the currency now runs both ways (build 01:52)

Milestone D had one half left: the level-up cards are done, the post-stage shop was not. It is now
reachable on purpose and its economy is measured - and the owner settled the design question in the middle
of it.

**A stage end can be forced, and that is what opens the shop.** Waiting for a stage to end by itself is the
same kind of maybe the run end was (`~9 minutes, or never`), and the game has the same kind of door:
`CoreGameEvents.TriggerStageEnd(CoreLevelEndArgs)` is public and static, and the args carry the same
`ECoreRunEndCondition` the run end uses. New test aid `-StageEnd win`, and the shop appears **~20 ms later on
both instances**:

```
shop: forcing stage end condition=WIN via CoreGameEvents.TriggerStageEnd role=host
shop: show #1 baseReroll=5 reroll=0/0 heal=30/0 wallet={GOLD=0 ... NITRA=35 ...} role=host
shop: caller of Show = ... < CoreGameEvents.TriggerStageEnd < CoopShop.Tick < CoopTick.Update < ...
```

Both sides show the **same prices** (`baseReroll=5 reroll=0/0 heal=30/0`), and a purchase is local and
personal: the game's own chain runs `Show -> SelectBestButton -> OnButtonSelect -> OnPurchaseComplete`, the
two instances bought *different* items (`WeaponUpgradeSkill_Damage` vs `SupportSkill_Armor`), each paid from
its own wallet. **The mod presses nothing in the shop** - all six shop hooks are listeners.

**The owner's decision, because it is not what the code did:** each player has their **own shop** (the
rewards are personal - a weapon upgrade improves *that* player's weapon), but the **currency is shared**:
claims run in both directions and both sides always credit, so the two wallets stay identical. Plus a shop
barrier like the level-up one - **built and measured further down**.

**What the code actually did, in three places, all now fixed:**

- `ClaimPostfix` was **host-only**, so a client that collected a mirrored pickup told nobody. The host kept
  the original (the same loot, collectable twice) and its wallet never moved for it.
- The claim queue was drained **inside the client-only block** of `CoopLoot.Tick`, so `ApplyClaim` never ran
  on the host at all. Measured: the client sent 3 claims and the host counted 0 received.
- `CreditWallet` **skipped the currencies the game saves** (`Wallet.ShouldSaveValue`), which left the claimer
  the only one paid for persistent currency - drift in exactly the currencies a shop spends.

Now: both roles broadcast claims, both roles drain them, the receiving side removes its *own* copy (the
host's original, the client's mirror) and credits it, and the gate is gone rather than inverted. The fixture
drops nitra **and** gold on the *client's* dwarf (`-TestLoot`, with `-Still` so neither dwarf wanders off
it), which exercises the direction that used to be silent:

```
host:   claimsSent=7 claimsRecv=2 miss=0 credited=2 walletDelta={GOLD=+3 NITRA=+6}
client: claimsSent=2 claimsRecv=7 miss=0 credited=7 walletDelta={GOLD=+3 NITRA=+6}
```

The directions mirror each other exactly (7/2 against 2/7), every received claim found its local copy
(`miss=0`), every one credited once (`credited == claimsRecv`) - and **the two wallets rose by the same
amount**, which is the thing the owner asked for. PASS on both roles, twice.

**Two defects found on the way, both of the silent kind this project keeps paying for:**

- The claim broadcast sat in a bare `catch { }`. A run showed the client counting 7 claims with
  `claimsSent=0`: the broadcast was failing and nothing said so. It now logs once - a swallowed exception in
  a code path whose whole job is to send is indistinguishable from "nothing happened".
- The client's `MirrorList` kept entries for mirrors the *client itself* had claimed (the game pools the
  object, the list did not care). That is the symmetric counterpart of the host's `ForgetOrigin`, and with
  every pickup worth 1 in this fixture the resulting wrong FIFO match would be invisible - in the real game
  it would credit a value that belongs to loot nobody collected. Both sides now forget what they claimed.

## A stage end reached nobody - the client played stage 1 forever (build 02:28)

The shop barrier left a question behind that turned out to be the bigger one. In its fixture the two shops
opened ~14 s apart because **each** instance forced its own stage end - which only works because a test aid
did it. A real run has no such aid, so: when one player's stage ends, does the other's?

**Measured first, with the client unable to force anything** (`-StageEndHostOnly`, so the host's stage end is
the only one there is):

```
host   02:18:06  check: stage starts=1 endsGame=0 endsAid=1 forced=1
host   02:18:51  check: stage starts=2 endsGame=0 endsAid=1 forced=1     <- host is in stage 2
client 02:21:54  check: stage starts=1 endsGame=0 endsAid=0 forced=0     <- 300 s later, still stage 1
host   RESULT: stage PASS reason=starts=2 …        client   RESULT: stage FAIL reason=timeout after 300s
```

**A stage end does not propagate at all.** The client sat in stage 1 for the whole run. The objectives are
mirrored (`CoopObjective`, milestone C) and that was never enough: mirroring the *progress* does not end the
other instance's stage. The host's 45 s shop-barrier timeout is the only reason it did not wedge there - a
single-run fixture hiding a two-player break.

**Finding the signal took one wrong turn worth recording:** `GameController.stageIndex` looks like the obvious
read-out and does not compile - in the dump it belongs to a compiler-generated nested iterator class
(`__4__this`, `__2__current` right above it), not to `GameController`. What works is the door this file
already used: a postfix on `CoreGameEvents.TriggerStageEnd`, which fires on whichever instance's stage ends,
with the source counted separately (`aid` / `game` / `remote`). That distinction is the entire measurement -
the forced end and a real one are the same call.

**The fix** is a `StageEnd` packet (22) carrying `CoreLevelEndArgs.EndCondition`, host -> client. The client
raises the *same* door locally, with `ApplyingRemote` set so it never echoes the packet back. Reusing
`TriggerStageEnd` means the client runs its own real stage-end chain - shop, next stage - rather than
anything invented. Measured after the relay:

```
client 02:25:29.234  stage: peer ended its stage (condition=0, recv #1) -> raising it locally
client 02:25:29.251  shop: show #1 …                     <- its shop, 17 ms after the host's stage end (was 14 s)
client 02:25:30.348  shop: released after holding 0,5s    <- the barrier held 0.5 s, not the 45 s timeout
client 02:25:31.145  GameController.StartGame             <- stage 2
host   RESULT: stage PASS reason=starts=2 endsAid=1 peerShopDone=1 sent=1
client RESULT: stage PASS reason=starts=2 endsRemote=1 recv=1
```

Two things fall out of that: the shops now open together, and the barrier's hold dropped from the 45 s
emergency exit to 0.5 s of real handshake. The barrier was working all along; the split stages were hiding it.

**The negative control** (`-StageEndNoRelay`, the host ends its stage and says nothing) is red on *both*
sides, and each side's reason is different on purpose:

```
host   FAIL reason=starts=2 endsAid=1 sent=0 peerShopDone=0                                <- "I got there, alone"
client FAIL reason=no new stage 120s after the end: starts=1 ends=0/0/0 recv=0             <- the diagnosis
```

That shape comes from one rule the check follows: **each side must show evidence from the peer, and a
timeout is not evidence.** The host reaching stage 2 by itself is exactly what the broken run did, so its
criterion is the peer's `ShopDone` - which only exists if the peer had a shop - rather than "I advanced". The
client's criterion is `endsRemote`, since in this fixture it can only get a stage end from the other side.
And because the side that hears nothing has no end to measure from, the client's clock also starts at its own
stage start; without that anchor the red side could only have reported a bare "timeout after 300s", which is
the unhelpful verdict this project keeps running into.

**Two transitions, because one cannot fail.** Both halves of the chain carry re-arm logic - the barrier
resets when a shop opens and the peer's `done` flag is *consumed* when this side leaves - so a single
transition measures only the case that works even if neither re-arms. The aid now repeats
(`-StageEndRepeat`, the clock restarting after each fire so the next end lands after the shop and the new
stage):

```
02:44:43.232 client shop: show #1 …                    -> released after holding 0,8s
02:44:44.981 client GameController.StartGame            <- stage 2
02:45:03.718 client shop: show #2 … (reroll=5/0)        <- the second shop, re-armed
02:45:03.727 client stage: end #2 (from the peer)
02:45:06.258 client GameController.StartGame            <- stage 3

host   PASS reason=starts=3 want=3 endsAid=2 peerShopDone=2 sent=2 forced=2
client PASS reason=starts=3 want=3 endsRemote=2 recv=2
```

Both re-arm paths hold, and the relay fires twice with no echo (`endsRemote=2` on the client, `sent=0`).
The first run of this fixture was a **false green on the client**: I had put `-coopstageendrepeat` inside the
launcher's host-only guard, so the client kept the default of 1, checked for *one* transition and wrote its
verdict after the first one - the second transition was in the log and in nobody's verdict. The count is an
expectation, not a force, and it now sits outside that guard. Worth generalising: **a parameter that decides
what a check expects does not belong in a block that decides what one role is allowed to do.**

**Limits, stated rather than implied:** the relay is host -> client only, because the host is the authority
for the stage (the client's objectives are mirrors). A stage end the client raises by itself is logged as
`stage: end #N (game's own)` and *not* relayed - if that turns out to be reachable, that is the place to
extend. Two transitions are measured, both forced; a stage that ends *by itself* (objective complete) was
never observed on either side, and how the chain behaves when both sides end a stage within the same second
is untested.

## The shop barrier: built, and the two bugs it took (build 02:09)

The owner asked for it ("Ja, Barriere wie beim Level-up"), and it is in: `UIShopScreen.OnPlayButton` is held
with a `false`-returning prefix until the peer reports done, and released by re-invoking that same method -
the shape `CoopXp` already uses on `LevelUpManager.OnLevelUpFinished`. The message is a new packet
(`ShopDone = 21`), its own type for the same reason `AnimState` has one: an older build ignores an unknown
type instead of desyncing on a longer packet.

```
green  host:   show=1 play=2 holds=1 heldFor=15,6 releases=1 timedOut=0 remoteDone=1 sent=1 left=stage-start screenActive=0   PASS
       client: show=1 play=1 holds=0 heldFor=0,0  releases=0 timedOut=0 remoteDone=1 sent=1 left=stage-start screenActive=0   PASS
red    both:   show=1 play=1 holds=0 timedOut=0 remoteDone=0 sent=0                                                 (barrier off)
```

The red run is the negative control (`-ShopNoBarrier`): same fixture, every continue goes straight through,
`remoteDone=0` - so the check distinguishes a barrier that talked from one that did not.

**The autopilot had to learn to press it first.** Nothing has ever closed a shop in an automated run: the
first room that reached one left it open, and a barrier with no way out of the shop could not be measured at
all. `CoopAuto` now presses the screen's own `OnPlayButton`, which is also exactly the call the barrier holds,
so an automated press and a player's press go through the same logic.

**Bug 1, and the reason the first check could not have worked: `UIShopScreen.Hide` is never called.** The
first barrier run held and released *correctly* - host pressed at `02:05:45.886`, held, got the client's done
at `02:06:01.126`, released after 15,2 s - and the run carried on (`GameController.StartGame` 0.6 s later),
while `hide` stayed 0. The check waited on `hide` and timed out on both sides. The observed way out of a shop
is the **next stage starting**, which now triggers the verdict, and the screen's own active state is recorded
at that moment (`left=stage-start screenActive=0`) so that claim is evidence rather than belief.

**Bug 2, mine: `OnRemoteShopDone` never set `_remoteDone`.** The message was counted, logged, and acted on -
but only in the branch for "I am already holding". So it worked on whichever side happened to press first and
was invisible on the other. Measured signature: the client held for exactly `heldFor=45,0` (the safety
timeout) while the host looked perfect, and the peer's `ShopDone` had arrived *13 s before the client's shop
even opened*:

```
02:05:45.895 client: shop: remote done (localDone=False holding=False)   <- arrives with no shop open yet
02:06:00.238 client: shop: show #1 ...
02:06:01.105 client: shop: local done, holding until the peer leaves the shop
02:06:46.117 client: shop: hold timed out after 45s -> releasing
```

That is not a corrupt corner case, it is the normal shape of a stage-transition gap: the two shops do **not**
open together. This fixture forces the stage end independently on each instance (each has its own 30 s timer
after its own run start, and the run starts were ~14 s apart), so the host had shopped, left, and told the
world before the client's shop existed. **A `ShopDone` that arrives before this side's shop opens means "my
partner is already through"** - the exact thing the barrier exists to establish - so the flag is now kept
across `Show` and *consumed* when this side leaves (`Release`, or the immediate pass-through). Wiping it on
`Show` threw the message away; never clearing it would disarm the barrier after one use.

**And the check did not catch bug 2.** It asserted `!holding` at the end, and a *timeout* releases the run
exactly like the peer's message does - so a 45 s wedge and a clean handshake looked identical. `timedOut` is
now counted and the check fails on it. Worth keeping in mind for the other checks in this repo: when a
safety net has the same visible effect as success, "it recovered" is not "it worked".

**The stagger that this section explained away turned out to be a real bug.** I wrote here that the two
shops going up ~14 s apart was a property of the fixture (each instance forcing its own stage end), and that
whether a real stage end propagates was "a stage-progress question, not a shop question". The first half was
right, the second was wrong: **a stage end did not reach the other instance at all** - measured, fixed and
written up in the next section. The barrier itself behaves correctly in both orders, which is what this
fixture could measure.

## Owner observations, recorded for later (2026-10-19)

Four points the owner raised after a play session. Recorded with what the code does *today*, so the next
session starts from facts instead of re-reading everything. None of these is built unless stated.

### 1. Revive amount: flat or percentage? (DECIDED — 50% of max hp, `-coopreviveflat` keeps 100)

Today it is **flat and hard-coded**: `CoopDowned.ReviveHp = 100` (with `ReviveRadius = 3.0`,
`ReviveSeconds = 5.0`). The downed dwarf therefore stands up with exactly 100 hp whatever its maximum is: at
a 400 hp pool that is a 25% revive, at 150 hp it is 67%. Which one is wanted is a real decision, because the
two produce very different difficulty curves in a long run. Changing it is a constant plus a measurement, not
a design overhaul. Worth deciding together with point 2.

**Decided (2026-10-20):** 50% of max hp is the default; `-coopreviveflat` restores the old flat 100.
`CoopDowned.ReviveHpFor(maxHp)` is the single rule used by the revive path. A live check in
`-Test revivecircle` logged host `maxHp=145 hp=72` and client `maxHp=130 hp=65`, both `mode=50%`.
The downed/revive flow itself was verified earlier (`check: revived ... hp=100`); this run verifies the
new rule on a live `Player.maxHp` (`Stat.Value`), not a hand-computed constant.

### 2. A visible fill circle like the mission objectives (IMPLEMENTED)

There is **no visual** today: the revive is a 3-unit radius and a 5 s timer, and the only trace is a log line
(`revive: started` / `revived`). The game already draws a filling circle for mission objectives, so the cheap
route is to reuse that: a ground-zone decal anchored on the downed dwarf, filling while the survivor stays
inside. Constraint learned from the HUD work: procedural meshes and built-in shaders do **not** render in this
build, so it has to reuse the game's own ground-zone visual rather than to draw a circle.

**Implemented (2026-10-20):** `CoopReviveVisual` clones `ActivationZone.areaProjector` (the real mission
circle, shader `FX/FX_Decal_Zone`) into a local `DecalProjector`, scales it with progress, and writes the
shader's `_Fill_Factor`. The downed player sees the circle around itself; the survivor runs the same 3 m /
5 s timer against `CoopNet.RemotePos` and sees it around the partner. No packet is needed because only the
visual is computed. `-Test revivecircle` positive `20261020-011703-revivecircle`: `prefab=Projector`,
`hasFillFactor=1`, 329/332 updates, PASS both; negative `-ReviveVisualOff`
`20261020-011516-revivecircle`: `created=0`, FAIL both. The GroundZone fallback remains for runs with no
`ActivationZone` in the scene; the current test mission has two.

### 3. Monsters stutter and never turn on the client (FIXED — see "Enemy mirror smoothing + facing" below)

- **Stutter:** enemy positions travel host -> client as `EnemySnapshot` at **2 Hz**
  (`CoopEnemy.SendSnapshots`, `Time.frameCount % 30 == 0`) and the client **sets the position directly**, with
  no interpolation. Two position updates per second, snapped - that is the judder that is being seen.
- **No rotation:** rotation is **not on the wire at all**. Packet 8 carries `(id u16, q-pos 3s16)` only, and
  the mirrors are additionally frozen (`SetAgentEnabled(false)`), so their own AI cannot turn them either.
- This is not a regression, it is the visible edge of the current design. The fix has two independent halves:
  (a) smooth the existing 2 Hz stream (move towards the last snapshot instead of snapping, or raise the rate /
  send deltas), and (b) put facing on the wire so a mirror can turn - a packed u8 angle costs one byte per
  enemy per snapshot. The swarm peaks near 260 live entities, so per-enemy per-tick work has to stay cheap.
- Already measured and worth not confusing with this: `check: snapshot applied=… missed=…` shows the
  *positions* arrive and land. The complaint is about smoothness and orientation, not about missing data.
- **Resolved (2026-10-20):** facing is now a packed byte in the snapshot and the client moves each
  mirror towards the newest position with a speed and per-frame cap instead of snapping. Positive and
  both negative controls are recorded in the section at the end of this file.

### 4. XP on the ground is not synced (FIXED — see "XP orb sync" below)

- What **is** synced is the **XP total**: every `Player.GainXp` is mirrored as `XpGain` (packet 3) and applied
  with `scaleByXpGain: false`, so both dwarves level together (verified: identical totals on both sides).
- What is **not** synced are the **orbs on the floor**. Unlike currencies, which travel as
  `LootSpawn`/`LootClaim`, XP pickups have no packet. Each instance only sees the orbs its *own* kills
  dropped: the host kills, the host sees orbs, the client does not - and the XP still arrives as a number,
  which is exactly why the totals match while the floor looks empty.
- If the orbs should be visible to both (a fair ask - they are the main "the fight pays off" feedback), the
  shape is the same as loot: broadcast the orb spawn, remove it on both sides when either player collects it,
  and have the collecting side send the claim. Care is needed to avoid double XP: the total is already
  mirrored, so a mirrored orb must not also grant XP locally.
- **Resolved (2026-10-20):** orbs travel as packet 30 (`XPManager.Spawn`), claims as packet 31
  (`XPManager.Claim`/`FinishPickup`). The receiver finds the orb in the static
  `XPManager.xpPositions` buffer and removes it under `ApplyingRemoteXp`; `Player.GainXp` is
  suppressed for that copy, so only the collector's `XpGain` lands. `-Test xpsync`
  `20261020-005304-xpsync` PASS both (`spawnSent=16`, `claimSent=15`, client `applied=16`,
  `suppressed=8`); `-XpOff` `20261020-005512-xpsync` FAIL. Details at the end of this file.

## Arena test fixture (2026-10-19)

The walking bot is a poor fixture for static checks: the dwarves circle, terrain and wave timing change
the camera, and a projectile or dummy cannot be parked at a known distance. An opt-in arena was added to
the local prototype and measured.

- Flags: `-Arena` (host + client), `-ArenaProbe` (measure only), `-ArenaNoClear` and `-ArenaWaves`
  (negative controls), plus radius/ separation/ dummy-distance/ dummy-type overrides. Defaults are
  `radius=10`, `separation=2`, `dummy distance=2`, `dummy=GRUNT0`. The old walking bot remains the
  default for swarm/objective tests.
- The arena anchors in the cave around the player start (not the map centre; the centre was a wall and
  the camera stayed at the drop pod), clears that radius through the game's own `MineableBlock.Die`,
  suppresses host waves, spawns one `LEVEL_START` dummy, and stands both dwarves at fixed spots.
- **Measured:** `check: arena-clear role=host cleared=57 open=0 rocks=57 veins=0 ms=2
  anchor=(17.2,0.0,39.9)` and the same on the client; `check: arena dummy role=host type=GRUNT0 id=1
  pos=(17.2,0.0,41.9) hp=1000000000 pinned=1 enemies=1`; client `check: arena info ...
  dummyPos=(17.2,0.0,41.9) ... near=1 mirrors=1`; both sides `RESULT: arena PASS ...`.
- Negative controls are named: `-ArenaWaves` → host `RESULT: arena FAIL reason=WAVES_LEAKED ...`, and
  `-ArenaNoClear` → both `RESULT: arena FAIL reason=NOT_CLEARED ...`.
- Two bugs the fixture exposed and fixed: the clear test compared a distance against a **squared**
  radius (`d <= r2`), so a radius-10 arena cleared 1872 blocks (almost the whole map) and left both
  cameras framing unrelated cave parts; and the host splash detector read only a 60-line log tail,
  so it kept clicking the centre of already-running games. The client's remote indicator also used
  `Camera.main` (the UI camera in this build) instead of `CameraController.cam` and reported every
  remote dwarf as off-screen. The capture helper now places the two game windows side by side.
- **Not claimed:** the arena `hit` test (`-Test hit -Arena`) still reports `HitsSent=0`; the client's
  fire events are forwarded but the dummy mirror is not damaged. The normal `hit` fixture already
  verifies client damage reaching the host (`sent=20 applied=20`), so this is arena targeting, not a
  newly found co-op defect. The game camera still has its look-ahead and puts the local dwarf near the
  bottom edge; that is cosmetic and was not pursued.

**Verdict:** keep the arena as an opt-in static fixture (fixed positions, one dummy, wave suppression,
block clearing) and stop investing in its camera/hit sub-cases. It has already paid for itself by
finding the over-clear, splash and indicator bugs. Use the walking fixture for swarm/objective tests and
move on to the next co-op milestone; revisit the arena only when a static combat/visual check is needed.

## Objective state at run start (the Boolo-Kappe 8/12)

Observed: the secondary objective showed `SAMMLE BOOLO-KAPPE 8/12` from the start of every mission,
even though nothing had been collected. Two separate facts were behind that:

1. **The 8/12 is the objective's target, not its progress.** The `ObjectiveProgress.progress` is 0 at
   the start (`check: objective-start role=host primary[COLLECT_POINTS=0] secondary[LEVEL_PICKUP=0]`).
   The HUD text `8/12` is the objective's target/definition (its required Boolo-Cap amount), not the
   runtime progress we mirror, so "nothing collected yet" is correct and the label does not move until
   the objective itself changes. The actual collected value is the `ObjectiveProgress.progress` field,
   which is 0 at the start.
2. **Every mission picked the same secondary because the seed was fixed.** `CoopNet.SharedSeed` was
   the constant `20261017`; `CoopObjective.SeedPrefix` seeded `UnityEngine.Random` with it before
   `SetupSecondaryObjectives`. Worse, the first attempt generated the new seed in
   `OnCoreRunStarted`, which runs *after* `SetupSecondaryObjectives` on the host: the host chose its
   secondary with the old constant while the client used the new seed (observed host
   `objective: seeded Random=20261017`, client `objective: seeded Random=901174632`).

Fix: the host now generates a fresh random seed in the `SetupSecondaryObjectives` prefix, immediately
before `UnityEngine.Random.InitState`, and the client receives that seed through the existing
`RunConfig` heartbeat; `MapGenerator.CreateMap` uses the same value. A fixed seed is available only
for reproducible tests (`-coopseed=<int>` / `coop-run.ps1 -Seed <int>`). Measured with a random-seed
arena run: host `run: new shared seed=-802946283`, both peers
`objective: seeded Random=-802946283` before `SetupSecondaryObjectives`, both
`map: seeded Random=-802946283`, and the arena test PASS (`cleared=35`). The cave and the secondary
objective are now random per mission and identical on both peers.

`CoopObjective.Reset` on `StartGame` and `OnCoreRunStarted` only clears the cached tracker, the
`Latest` map and queued packets so the next stage/run cannot keep writing into the previous tracker.
It deliberately does **not** zero the host's objective progress: that would alter the game's real
state and did not update the HUD. If the 8/12 target still appears, it is the Boolo-Cap secondary
being selected for that seed; the actual progress is the separate `ObjectiveProgress` value.

## Milestone G: in-game host/join UI (2026-10-19)

- `CoopJoinUI.cs` draws a direct-IP/LAN panel (address, port, Host, Join, F8 hide) before the run,
  including the publisher splash, and calls the same runtime `CoopNet.Init` the `-coophost` /
  `-coopclient` flags use. It sets the client's bot phase; the existing run-config/map/objective gates
  are unchanged, so the host still starts the run and the client follows.
- The launcher's `-Ui` mode starts both instances **without** role flags, passes `-coopui` and
  `-cooplog=host|client` (separate logs for the two concurrent processes), and the click helper
  presses Host on the host window and Join on the client window at the fixed panel coordinates.
- **Verified:** `RESULT: ui PASS reason=ui role=host peer=1 peers=1` and the same for the client, with
  no role flags. The end-to-end `-Ui -Arena -Test arena` run also PASSed (`cleared=26`, `peer=1`,
  `peerMirrors=1`) with UI-selected roles. The `ui` test fails at 45 s if either role or the peer is
  missing.
- **Not included:** Steam lobby/relay/invite. That needs the owner's Steam account and explicit
  approval; the current UI is LAN/direct-IP only (UDP 9050 by default, same game build on both
  sides). F8 hides the panel; the command-line role path remains for every other test.

The panel's text fields are a small click-to-focus button plus IMGUI characters because the interop
assembly exposes no `GUI.TextField`; the default address/port (`127.0.0.1:9050`) need no typing for
two instances on one PC.

## Grenade mirror with different loadouts (2026-10-19)

The throw itself was already mirrored (`GrenadeThrow`, packet 25): skill name, origin and direction,
replayed with `Grenade.Throw(..., isOriginal:false)` and a damage-suppressed explosion. It passed
only when **both** dwarves had the same grenade. The realistic case - the receiver does not have the
host's grenade - failed with `NO_EXPLOSION`: the receiver fell back to a bare
`Object.Instantiate` of the prefab, which has no initialized grenade pool/handler, so the grenade flew
but never exploded.

What did not work, both measured:

- Creating the handler at throw time (`AddWeaponHandler` + `Init`, with and without adding it to
  `Player.weapons`) throws a masked NRE or leaves a handler whose `GetGrenadeFromPool()` is null.
  A handler created after the run has started is not driven.
- Treating "a `WeaponHandler` with this skill name exists" as "I already have it" was a false signal:
  the half-created handler matched by name while its pool was still null, so adoption skipped the one
  call that would have fixed it. **`Player.HasWeapon(data)` is the only reliable predicate.**

The fix has two halves:

1. `GrenadeLoadout` (packet 26), host -> client: the grenade skills the host's `Player.weapons`
   actually holds, sent at run start and again whenever the set changes (a card can add one).
2. `CoopGrenade.TryAdoptPending` equips each one through the game's own
   `Player.EquipNewWeapon(data, false)` in the window between `OnCoreRunStarted` and `StartGame`
   (the same window the `-DevGive` stimulus uses), retrying for 20 s because `EquipNewWeapon` throws
   until the run player is really up. `Adopted` is cumulative, not zeroed at `StartGame`: the
   run-start reset had wiped the very fact the verdict reports.

Measured (`coop-run.ps1 -Deploy -Auto -Arena -Test grenade-mirror-damage -DevGiveHostOnly
-DevGive GrenadeWeaponSkill_HEGrenade`, run `20261019-201723`):

```
client: check: grenade host-loadout recv=2 n=1 [GrenadeWeaponSkill_HEGrenade]
client: check: grenade adopt 'GrenadeWeaponSkill_HEGrenade' via=EquipNewWeapon handler=yes weapons=1->2 registered=1
client: check: grenade mirror spawned skill='GrenadeWeaponSkill_HEGrenade' … via=pool
client: grenade: mirror exploding (damage suppressed)
client: RESULT: grenade-mirror-damage PASS reason=sent=1 spawned=1 exploded=1 adopted=1
host:   RESULT: grenade-mirror-damage PASS reason=sent=1
```

Three things this run changed beyond the feature:

- A throw that arrives while the receiver is still in the **menu** is dropped (`Gc == null`) instead
  of spawning against the menu dwarf. The old mid-run handler creation did exactly that in the first
  attempt and poisoned the later adoption.
- The test is role-aware: the host may pass as sender, but the **client must show the received mirror
  spawn and explode**. With adoption, the client also throws its own grenade, and the old
  `sender || receiver` rule greened the client before the received mirror had exploded
  (`sent=1 spawned=1 exploded=0`).
- **Known side effect, not yet changed:** adoption gives the receiver the weapon, so it fires that
  grenade too. A visual-only variant - create the handler/pool at run start, then remove it from
  `Player.weapons` so the game does not drive it - would keep loadouts distinct and still needs its
  own measurement.

## Run-start load barrier (2026-10-19)

Owner requirement: the host starts the run; the client adopts every setting and only picks its own
character; and the two runs must not begin until **both** sides have finished loading. Settings
adoption already did the second part. The timing problem was real: in the runs above the host's
`StartGame` and the client's were **14-16 s apart**, so one dwarf was already in the cave while the
other was still loading.

`CoopLoad.cs` implements the barrier with the game's own pause door:

- `OnCoreRunStarted` arms it (a new run, not a stage transition).
- The `GameController.StartGame` postfix marks "loaded", and the next tick calls the public
  `GameController.PauseCore()` and sends `RunLoaded(ready)`.
- The host waits for its own ready **and** the client's, then sends `RunLoaded(go)` and calls
  `UnpauseCore()`; the client unpauses when `go` arrives. A 30 s timeout releases a lost peer, so the
  barrier cannot soft-lock a session (the same shape as the level-up, shop and stage barriers).

Two findings the test produced:

- **The faster side's `ready` can arrive before the slower side has even armed.** Measured: client
  `load peer-ready` at 20:09:52, its own `OnCoreRunStarted` at 20:10:05. The first version reset
  `PeerReady` while arming and the client then reported `peer=0` despite `readyRx=1`. The packet now
  carries the **shared seed as a run epoch**; a ready for the current epoch survives arming, a stale
  one cannot release the new run.
- **`PauseCore` really pauses the game.** During the host's 23.7 s hold its position and enemy count
  were constant while its bot's `steps` counter kept climbing (the mod's `Update` runs, game time
  does not). `IsPaused()` read 1 on both sides.

Measured with a deliberately delayed client (`-Test load -LoadDelay 8`, which passes
`-cooploaddelay=8` to the client only; run `20261019-202123-load`, and the same run reports
`saves: restored and verified (14 files, canary removed)`):

```
host:   check: load held role=host paused=1
host:   check: load go sent role=host wait=23,5s
host:   RESULT: load PASS reason=local=1 peer=1 go=1 paused=1 held=23,5s timeout=0
client: check: load held role=client paused=1 delay=8,0s
client: check: load local-ready role=client after=8,0s
client: check: load released role=client via=go held=8,0s peer=1 go=1 paused=1
```

The negative control is a single instance (`-Only host`): no peer ever reports ready, so the run must
release on the timeout and the verdict must be `FAIL timeout=1`.

**Honest scope:** "loaded" is `GameController.StartGame`, the point the level is playable, not a hook
on the literal loading-screen form. The visible result is the level on screen, frozen until the partner
is ready, then both unpause.

## Camera frames both dwarves (2026-10-19)

The camera follows one `Player`, so on the test bot's circle the partner is simply not on screen:
the two bots run the same circle in opposite phase, i.e. **20–23 units apart** for the whole run.
The off-screen marker (`CoopIndicator`) was compensating, but a marker is not the partner.

The projectile origin was **not** the bug: the grenade run logs
`mirror spawned … from=(97.7,1.0,68.7)` against `remotePos=(97.7,0.0,68.7)` (run
`20261019-201723`) — the mirror starts at the remote dwarf's fire point, one unit above the feet.
What made it look like "from nowhere" was that the fire point could be outside the local view.

Measured camera (probe `-coopcameraprobe`, run `20261019-203618-camera`):

```
vcam=CinemachineVirtualCamera follow=Player lookAt=none
pipeline=CinemachineTransposer/CinemachineComposer/CinemachineBasicMultiChannelPerlin
lensFov=25,0 lensOrtho=0 aspect=1,78 (host) / 1,50 (client)
transposer followOffset=(-9.6,33.9,-26.0) binding=LockToTargetWithWorldUp
```

So the game **does not use a FramingTransposer**, and native `CinemachineTargetGroup` group-framing
(the clean solution, its enums and fields are exposed by the interop) would require replacing the
game's body component. That was not done. Instead:

- A `CoopCameraFocus` transform sits at the **midpoint** of the two dwarves and is assigned as
  `vCam.Follow`; the existing `CinemachineComposer` aims there, so both dwarves are symmetric.
- The transposer's own `m_FollowOffset` is scaled by `1 + max(0, sep-10)/40`, capped at 1.6. This
  dollies out along the game's isometric direction: the view widens without changing FOV/perspective
  and without moving the camera into the cave.
- `Follow`, the offset and every field the module touches are restored on run start and whenever no
  remote exists, so solo/menu are untouched. `-coopcameraoff` keeps vanilla follow for the control.

Measured on the final build (run `20261019-204847-camera`, no arena):

```
host:   RESULT: camera PASS reason=mode=focus+dolly samples=20 far=20 farVisible=19 both=19 maxSep=21,8
client: RESULT: camera PASS reason=mode=focus+dolly samples=20 far=20 farVisible=20 both=20 maxSep=20,6
```

The immediately preceding build (run `20261019-204538-camera`) measured **20/20 both** on both sides;
the one missing final-build sample is a camera-damping transient, and the off-screen marker covers
that instant. Viewport z of the dwarves rose from ~40–48 (vanilla) to ~49–63 with the dolly; every
sampled frame but that one had both inside the viewport. The negative control is the same measurement
with `-coopcameraoff`:

```
host:   RESULT: camera FAIL reason=mode=none … far=20 farVisible=5
client: RESULT: camera FAIL reason=mode=none … far=20 farVisible=1
```

The `camera` test only counts samples at separation ≥ 12 and requires ≥ 90% of them to contain the
remote in the viewport; it is state-based, not a timeout. The off-screen marker remains the fallback
for the extreme case (a player who runs far away).

## Enemy hp sync; the client keeps its own damage numbers (2026-10-19)

Owner clarification: the client must not see the host's damage numbers - its own are enough. I had
built a host->client `EnemyDamage` channel first (client `events=10 total=400 text=10/0` through
`DamageTextAnimationSystem.SpawnText`, which needs `PreWarm()` on the `DamageTextSystem(Clone)`),
measured it, and then removed it. What was actually missing was the health value.

- `EnemySnapshot` now carries `hp(i32)` per entry (100-entry chunks, 12 B each instead of 120 x 8 B).
  The client applies it damage-only: `currentHp = min(currentHp, snapshotHp)`. A snapshot that
  predates the client's own reported hit can therefore never heal the mirror; the next host update
  catches up.
- The client's own weapons already call `TakeDamage` on the mirror locally, so its numbers are
  immediate. No host number event exists, and the host still applies client hits with `doFx=false`.
- PASS (`20261019-210726-hpsync`, arena): host `hits=10 total=351 dummyHp=999999856 snapSent=34`;
  client `snapSeen=11 equal=6 drops=1/82 above=4`. The client's own hits never landed in this
  fixture (`hit sent=0/0`), so every drop it saw was host-originated - direct evidence of the
  host->client path.
- Control (`20261019-211019-hpsync`, `-HpSyncOff`): client FAILs on state
  (`snapEntries=31 hpSeen=0 hpSync=off`), not on the generic test timeout; the host still PASSes.
- Known limit: damage-only, so enemy healing is not mirrored. No healing enemy appears in the
  tested content. The arena dummy sits at ~1e9 hp, so the absolute numbers are small relative to
  its pool; the drop counters, not the pool, are the evidence.

## Mirrored muzzle flash (2026-10-19)

The game's muzzle flash is a light, not a prefab: `ProjectileWeaponSkillData.FlashSettings`
(`ImpactFlashSettings`: color/range/duration/delay/Enabled) is handed to
`Assets.Scripts.VFXSystem.ImpactLightsManager.AddLight(position, settings)`. `CoopCombat.Drain` now
calls `Flash(e)` for every received Fire, before and independent of the projectile mirror (with
`-cooptrace` off there is no projectile, but the flash still happens). `Lights()` finds the scene
manager through `Resources.FindObjectsOfTypeAll`, caches it, and logs found/MISSING on first use.

- Verified (`20261019-213116-muzzle`): client `flashes=8 disabled=2 failures=0` (host's
  `ProjectileWeaponSkill_Subata`), host `flashes=0 disabled=10` (client's
  `Bosco_ProjectileWeaponSkill_Base`, whose `FlashSettings.Enabled=false` in the game's own data).
  The host's `disabled=10` with `flashes=0` initially looked like "the code never ran" because the
  tick line omitted the disabled counter; the `coop flags: muzzle=True` startup line and the
  `disabled` field in the verdict settled it. Counters are displayed as
  `muzzle=flashes/noSettings/failures/disabled`.
- Negative (`20261019-213321-muzzle`, `-MuzzleOff`): both FAIL on state
  `fireRecv=10 flashes=0 muzzle=off`, not on the generic timeout.
- The automation's client carries Bosco, which the game does not flash; that direction is
  "respected disabled", not "no flash code". A client with a gun produces the same AddLight calls on
  the host. No flash is invented for a weapon that explicitly disables it; only a **missing**
  settings asset falls back to a small warm default.

## Weapon coverage, per-handler vs per-weapon, and the muzzle origin (2026-10-19)

Owner question: does every weapon need its own code? **No for projectile weapons.** The Fire hook sits
on `ProjectileWeaponHandler.ShootProjectileInDirection`; the peer resolves
`ProjectileWeaponSkillData` by asset name and uses that asset's `ProjectilePrefab` and
`ProjectileSettings`. One code path serves all of them. Per-weapon **testing** is still needed because
the assets carry different prefabs/settings, and per-**category** code is needed for handlers that are
not `ProjectileWeaponHandler` at all.

Measured with `-Test weapons -Mirror -DevGive "…"` (run `20261019-215130-weapons`, 10 skills):

- mirrored on both sides: `Subata`, `Bosco_ProjectileWeaponSkill_Base`, `M1000`, `Boomstick`,
  `ImpactAxeSkillData` - `noAsset=0 noPrefab=0 failed=0`.
- never fired by the plain `-DevGive` path: `AutoCannon`, `Leadstorm_Minigun`,
  `GrenadeLauncher_PGL`, `AlternatingProjectileSkillData_Boltshark`,
  `LinkProjectileSkillData_BreachCutter`, `BeamWeaponSkill_Electrical_TH0R`. The plain path adds all
  weapons, but the automation only fires the weapon that was active at run start plus Bosco.

The sweep (`-DevSweep <sec>`) makes the matrix real: it clears `Player.weapons`, equips one skill at a
time into action-bar slot 0, and fires it through `ProjectileWeaponHandler.ShootProjectileInDirection`
(the same path the hook observes). Runs:

- `20261019-220450-weapons`: `AutoCannon` 9/10 and `Leadstorm_Minigun` 9/9 applied on both sides;
  `Boltshark` reached the mirror but `noPrefab`; `PGL` returned from the manual call without a Fire;
  `BreachCutter` was `not-projectile`; the last weapon (beam) was skipped by an ordering bug.
- `20261019-220839-weapons` with the alternating resolver: `Boltshark` mirrors both prefabs,
  `DamageProjectile_Electric_Bolt` and `DamageProjectile_Acid_Bolt` (27/28 host, 32/33 client,
  `applied`), and the last weapon now gets its window.
- `AlternatingProjectileSkillData` inherits `ProjectileWeaponSkillData` but has `Projectiles[]`, not a
  single `ProjectilePrefab`; `SpawnMirrorProjectile` now indexes that array round-robin.

What is left is genuinely per handler category, not per weapon:

- `LinkProjectileSkillData_BreachCutter` — **done.** The handler is `LinkProjectileWeaponHandler`
  (not `ProjectileWeaponHandler`); a Harmony postfix on its public `Get()` sends the same Fire packet
  with `pData.name`, `firePoint` and the base `externalAimDirection`. Verified
  (`20261019-222018-weapons`): `LinkProjectileSkillData_BreachCutter` applied 9/10 on both sides,
  `noAsset=0 noPrefab=0 failed=0`.
- `ProjectileWeaponSkill_GrenadeLauncher_PGL` — **done.** The sweep now holds the trigger
  (`CoopDev.HoldTrigger`, dev-only; `Player.ShouldManualTriggerWeapon` returns true and
  `primaryTriggerDown` is re-asserted after `Player.Update`) instead of writing the field once, so the
  game's own activation logic fires it. The shot is observed on
  `Grenade.ShootGrenade(WeaponHandler, Vector2, GrenadeLauncherSkillData, Vector3, bool)`, a base
  method with no override. The base `ProjectileWeaponHandler.ShootProjectileInDirection` hook cannot
  see the PGL's override, and patching the virtual plus its override is the documented `0xc0000005`
  crash, so the grenade launch entry is the safe hook. Runs `20261019-233339-weapons` (6 s window)
  and `20261019-235051-weapons` (15 s window, final build): `expected=1 received=1 notFired=0`,
  `RESULT: PASS` on both roles; the host sees the client's and the client sees the host's
  `ProjectileWeaponSkill_GrenadeLauncher_PGL` Fire event. The 15 s window matters: the PGL can need
  ~4 s to become ready, and a 6 s rerun failed (`20261019-234848-weapons`, `notFired=1`). The
  receiver still goes through the normal Fire/mirror path.
- `BeamWeaponSkill_Electrical_TH0R` — **done, but it is not a `BeamWeaponHandler`.** The asset is a
  `LightningBeamSkillData` (subclass of `BeamWeaponSkillData`) and its `AddWeaponHandler` creates
  `LightningBeamHandler : WeaponHandler`, with its own `ActivateWeapon`, `ActivationLogic` and an
  `IEActivate` coroutine. It has no `isBeaming` and never calls `StartBeaming`; the earlier re-wrap as
  `BeamWeaponHandler` read the wrong offsets, which is why the old run saw `beaming=0`. The sweep now
  calls `LightningBeamHandler.ActivateWeapon()`; a postfix on that method sends one `BeamState` (29)
  per burst and the remote line lives 0.2 s. Run `20261019-234302-weapons`: `RESULT: PASS` on both
  roles, `beam=3/2` host and `3/3` client, `skills=1/1`, `notFired=0`; the first host call reported
  `fired=1`. Negative control `-BeamOff` (`20261019-234645-weapons`): both roles FAIL
  `notFired=1`, `beam=0/0`, so the pass is the mirror path, not the activation log.
- `BeamWeaponSkill_RotatingBeam_CryoCannon` — **done, continuous path.** This is a real
  `BeamWeaponHandler` (`StartBeaming`/`StopBeaming`). Sweep `20261020-012001-weapons`
  (`-DevSweep 15`): host `beam=98/91`, client `100/98`, `skills=1/1`, `RESULT: PASS` both;
  `beam: local start/send/applied` lines present. The first two sweep logs still read
  `beaming=0` because the beam starts ~3 s after equip; the 15 s window covers it. ShardDiffractor,
  SludgePump and LocalSpaceBeam share this handler path but were not individually swept.
  **Game BeamVFX - DONE (20261020-133051-beamgame).** `CoopBeam` resolves
  `BeamWeaponSkillData.BeamVFX` (`VFXAssetGeneric`), keeps one live prefab per beam, sets
  `Hovl_Laser.MaxLength`, and falls back to the debug cube. `-Test beamgame` uses a direct
  `CoopDev` stimulus (`isBeaming=true` + `OnLocalStart`, never `StartBeaming`): positive PASS both,
  host `sent=56`, client `applied=68`, `game=1/0/0`, `noAsset=0`, `fallback=0`, and
  `beam: game vfx ... prefab='CryoBeam_VFX' range=5.0`. Negative `-BeamOff`
  (`20261020-133207-beamgame`) FAIL both `sent=0 applied=0 game=0`; negative `-GameBeamOff`
  (`20261020-133320-beamgame`) host PASS/client FAIL `game=0 fallback=68`. The earlier `notFired`
  runs used the short give name `RotatingBeam_CryoCannon`; the asset is
  `BeamWeaponSkill_RotatingBeam_CryoCannon`, so `CoopDev` reported `NOT_FOUND` and never equipped
  it. The direct stimulus is a test fixture; the game's own `ActivationLogic` did not start the
  beam in the auto-start runs. Asset path verified; exact length/alignment not pixel-checked.

The `weapons` test is per-role and excludes a skill this side fired from `missingRecv` (the peer
mirrors it; it is not echoed back to the sender). PGL, TH0R and the continuous rotating beam are
green; the untested variants of the continuous path are named above rather than implied done.

**Origin bug (owner: "the client's projectiles come from the wrong direction").** `OnLocalShot` used
`Player.FirePoint` for every handler. Bosco/drone handlers fire from their own
`WeaponHandler.firePoint`, so the mirror started at the dwarf's gun. Measured (`20261019-214847-hpsync`,
client): `from=(51.6,1,84.5) handlerFP=(51.6,1,84.5) playerFP=(53.6,1,82.4)`,
`dir=(0.2,-1,-0.1)`. The direction is world-space and points at the dummy; only the origin was wrong.
`handler.firePoint` is now preferred, with `Player.FirePoint` as fallback.

**HUD probe (`-coophudprobe`).** On both sides slot #1 is `ProjectileWeaponSkill_Subata`,
`handler=Subata`, `ownerSelf=1`, `inPlayerWeapons=1`; slots 2-4 are empty. The client's bot fires
Bosco, which is a drone weapon and does not sit in the action bar, so the bar's Subata slot is idle
and shows no fire/reload status. The binding is correct; this is a stimulus/loadout difference, not a
missing handler. In normal play the bar weapon is the one the player fires.

## The partner's projectiles were gated off by default (2026-10-19)

Owner observation: both players fire their own weapons, but nothing from the partner is visible.
Cause: `CoopCombat.Enabled` defaulted to **false** and was only switched on by `-cooptrace`/`-Mirror`.
The Fire packet was received and `Flash(e)` played the muzzle light, but `SpawnMirrorProjectile`
returned immediately, so the peer never spawned a visual. This was the B3 experiment gate, not a
rendering bug.

`Enabled` is now true by default; `-coopmirroroff` is the negative control. The per-projectile
`isVisible` probe stays opt-in (`CoopCombat.Probe`, set by `-cooptrace`/`-coopb3draw`) because that
signal read false even for the game's own projectiles - it is not a gameplay gate and not proof of
invisibility.

Verified in a normal co-op run with no `-Mirror` (`20261019-221411-hpsync`): the host mirrors the
client's `Bosco_ProjectileWeaponSkill_Base` and the client mirrors the host's
`ProjectileWeaponSkill_Subata`, both as the real prefab `DamageProjectile_Kinetic_Medium`, with
`applied=N dropped=0` and no `combat: probe` lines. `hpsync` PASS on both sides.

## Harness: the restore canary had become permanent (2026-10-19)

Every run from 19:25 onwards ended with `saves: VERIFY FAILED - hashes match but the canary survived`.
The cause was a previous partial restore leaving `coop-restore-canary.txt` in the save folder; the next
backup copied it, so the restore faithfully restored a tree containing the marker and then reported a
failure forever. `Backup-Saves` now removes the marker from the backup before recording it, and the
stray file was deleted. Save data itself was verified intact (`drg_save_slot*.dat`, `localprefs.dat`);
only the harness marker was wrong.

## Enemy VAT animation sync (2026-10-19)

The snapshot's `Anim` field now carries the host enemy's VAT state: clip index + 1 in the high 16
bits, normalized phase in the low 16. The host reads
`EnemyAnimator.meshAnim.currentAnimIndex/currentAnimTime/currentAnimation.length`; the client
resolves the mirror's `meshAnim` clip by index (same prefab/order), calls `meshAnim.Play(idx)` on a
clip change and sets `currentAnimTime = phase * length` when the phase is off by more than 0.2.
Playing the mesh directly avoids routing through `EnemyAnimator.PlayVATClip` and its animation-event
path on a mirror.

- The first attempt used a standard `Animator` state hash and timed out (`20261019-230123`): the
  swarm animates through `Assets.Scripts.EnemyAnimator` / `ShaderMeshAnimator` (VAT), not an
  `Animator` state. That wrong channel was removed.
- PASS (`20261019-231004-enemyanim`, normal swarm): host `sent=196`; client `seen=42 applied=7
  sampled=21 match=21` - every sampled mirror held the last applied clip.
- Negative (`20261019-231303-enemyanim`, `-EnemyAnimOff`): client FAILs on state
  `seen=0 enemyanim=off`; the host has no `SnapAnimSent` and times out. That is the control.
- Limits: clip index/phase only, no blend/parameter state; the index order is assumed identical for
  the same prefab (held on the tested swarm); phase is corrected at the 2 Hz snapshot rate; mirrors
  were not checked for animation-event gameplay (test runs use god mode). The mirror's own
  `EnemyAnimator` did not override the mesh during the test.

## Enemy mirror smoothing + facing (2026-10-20)

Owner observation #3 is fixed: the client no longer teleports mirrors at the 2 Hz snapshot rate, and
the host's facing now reaches the mirror.

- **Wire:** `SnapEntry` carries a packed yaw byte (0..255 = 0..360 degrees). The entry is 17 bytes;
  56-entry chunks stay under the MTU (60 entries were rejected by SteamNetworkingSockets at 1020
  bytes once the yaw byte was added). The snapshot rate is still 2 Hz — the frame loop supplies the
  missing frames.
- **Position:** `CoopEnemy.TickMirrors` runs every frame on the client and moves each mirror towards
  the newest snapshot with `Vector3.MoveTowards`, capped at 12 m/s and 0.5 m per frame. A large gap
  (spawn, pool reuse, a hitch) closes over several frames instead of one jump.
- **Facing:** the packed yaw is applied with `Quaternion.Slerp` (same 10 Hz convergence constant);
  a frozen mirror now turns with its original.
- **Positive** (`20261020-001101-enemysmooth`, normal swarm): host `sentChunks=66 facing=846`;
  client `applied=731 maxStep=0.412 facingApplied=142`, `RESULT: PASS` both roles.
- **Negative smoothing** (`20261020-000933-enemysmooth`, `-SnapSmoothOff`): client FAIL
  `maxStep=2.002`; the old snap path is the control.
- **Negative facing** (`20261020-001231-enemysmooth`, `-EnemyFaceOff`): host FAIL `facing=0`,
  client FAIL `facingApplied=0`.
- The test (`-Test enemysmooth`) requires the client to have moved in many small steps
  (`maxStep <= 0.75`) and to have applied at least 10 host turns; the host must have sent both
  chunks and facing. Both negative controls are state-based, not timeouts.
- **Final-build rerun** (`20261020-005713-enemysmooth`, build `2C4B9760140340BE`, 56-entry chunks):
  host `sentChunks=65 facing=953`; client `applied=770 maxStep=0.500 facingApplied=364`,
  `RESULT: PASS` both roles. No "packet size exceeded" line in this run.

## Soak 2026-10-20 (600 s, two instances)

- `20261020-040552-soak`: PASS both after 600 s post-release. Host 2900 live enemies, client
  2915; 618,215 snapshots applied / 3671 missed; 928 projectile events each way; no matches for
  `Exception`, `NullReference`, `0xc0000005`, snapshot-size, disconnect or spawn-failure patterns.
  Saves restored and verified (14 files, canary removed).
- **Fixed during the soak:** `SpawnMirror` called `SpawnAt`, then looked the returned `Enemy` up in
  `ByPointer`; the registration postfix had not run yet, so 29/50 mirrors were dropped as
  `MirrorSpawnFailed`. It now calls the idempotent `Register(e, "mirror-spawn", scale)` before the
  lookup. After: `fail=0 null=0 noEntry=0 noPtr=0` at `spawn=3921`. Also fixed the
  `SpawnWeaponHandler.Despawn` Harmony parameter (`ws`, not `spawn`).
- **Fixed (2026-10-20):** `localDie=0`, `miss=0` in `20261020-043000-soak` (600 s, 624 spawns,
  580 deaths on each side; `blocked local mirror death id=...` in the client log). The client's local
  `Enemy.Die` for mirrors is blocked (`OnDiePrefix`), the killing hit is still reported, and
  `OnDamageEnd` clamps the mirror to 1 hp; the host's `DeSpawn` removes it. The previous
  `localDie=249`/`miss=249` is gone.
- The `hp hurt ... nearestMirror` drops are expected: each instance's mirrored swarm attacks its own
  dwarf (see `CoopDamage`).

## XP orb sync (2026-10-20)

Owner observation #4 is fixed: both instances now see the same XP orbs and each orb grants once.

- **Spawn:** a postfix on `XPManager.Spawn(Vector3, float)` sends packet 30 with the quantized
  position and the force modifier. The host is the only sender; the client applies it inside
  `ApplyingRemoteXp` and records the new orb as a mirror.
- **Claim:** prefixes on `XPManager.Claim(int)` and `XPManager.FinishPickup(int)` send packet 31
  with the orb's position. A quantized-position set stops the same local orb from sending twice.
- **Removal without double XP:** the receiver resolves the orb through the static
  `XPManager.xpPositions` buffer (`NativeArray<float3>`, read by reflection because the interop
  does not expose the element type), calls `Claim` + `FinishPickup` under `ApplyingRemoteXp`, and
  the `Player.GainXp` prefix returns false for that copy. The collector's normal `GainXp` is the
  only grant and is mirrored as packet 3.
- **Positive** (`20261020-005304-xpsync`, normal swarm): host `spawnSent=16 claimSent=15
  finishCalls=8`; client `spawnRecv=16 applied=16 mirrorSeen=16 claimRecv=15 claimApplied=8
  suppressed=8`, `RESULT: PASS` both roles.
- **Negative** (`20261020-005512-xpsync`, `-XpOff`): host `spawnSent=0`, client
  `spawnRecv=0`, `RESULT: FAIL` both roles. That is the control.
- **Limits:** claims are matched by nearest position (6 m), so a mirror that drifted further is a
  miss; the run sent 15 claims for 8 finishes because `Claim` and `FinishPickup` can both fire on
  the same orb at slightly different positions. The 8 host finishes matched the client's 8 remote
  gains, so no double XP was observed, but a longer two-player soak is still needed for the
  simultaneous-collection race.

## Trail ground zones (2026-10-20)

Trail weapons are not projectiles and do not call `GroundZone.Init`; they drop zones through
`GroundZoneDispenser.TryPlaceGroundZone`, so neither the projectile nor the old GroundZone.Init hook
saw them.

- **Stimulus:** `CoopDev` detects `TrailWeaponSkillData`, re-wraps the handler as
  `TrailWeaponHandler`, calls `ActivateWeapon()`, then `EnableGroundZones()` if the dispenser is
  missing and `BaseLogicTick(0.5f)`. A freshly equipped test weapon does not get the game's own
  handler tick; driving it is what makes the dispenser place zones.
- **Wire:** postfix on `GroundZoneDispenser.TryPlaceGroundZone` sends packet 32 with the skill name,
  quantized position, radius and lifetime. Only trail skills are sent (ground-zone grenades already
  create their zone from the mirrored explosion).
- **Client:** resolves the trail asset by name, takes
  `TrailWeaponSkillData.GroundZoneParams.GroundZonePrefab`, instantiates it, calls
  `InitVisualsOnly(life, radius, null)` and positions it. The visual expires with its lifetime.
- **Positive** (`20261020-015745-trail`): host `sent=34`; client `recv=38 applied=38 miss=0`,
  `RESULT: PASS` both roles.
- **Negative** (`20261020-015907-trail`, `-ZoneOff`): host `sent=0`; client `applied=0`,
  `RESULT: FAIL` both roles.
- **Limits:** the client zone is visual-only; it does not apply the host's damage/slow. Zone count
  differs (34 sent vs 38 applied) because the client's own trail also drops local zones that are not
  counted as remote; the test only counts the remote path. The first `GroundZone.Init` patch was
  ambiguous/fired for nothing and is retained only as a no-op guard; the dispenser hook is the
  reliable path.

## Remote weapon visual — not applicable (no held model) (2026-10-20)

The `WeaponState` packet (36) and a visual-only prop path are in place, but the tested Driller
weapons have **no held model** to clone:

- The `WeaponHandler` GameObject is the shared `Player/WeaponHandlers` object
  (`DropPod/DropPodModel/PlayerPoint/Player/WeaponHandlers`) with **0 renderers**. The only
  weapon-ish renderers in the player tree are the hand bones (`mixamorigHand.L/R`, 1 each); there is
  no `PGL`/`Subata` model node.
- Cloning that handler therefore produces 0 renderers; `-Test weaponvisual`
  (`20261020-025641-weaponvisual`) ends client `applied=0 renderers=0 miss=255`. The host sends the
  last-equipped skill (PGL); the client finds the handler but no model.
- The current class-skin/mod swap works (the remote GFX takes the host's class mod), so the old
  "skin blocker" is gone. The game has **no separate held weapon model**: `WeaponHandlers` is the
  shared empty container, `WeaponSkillData` carries no model prefab, and no `WeaponSkinData` /
  `WeaponModel` type exists in the assembly. The class-mod skin is the character visual; the
  weapon is represented by the skill/projectile/beam VFX. A held prop is not applicable here.
- Do not claim a held-prop visual. The packet is harmless and the prop path is guarded (no empty
  object is left in the scene); retire `-Test weaponvisual` from the matrix. `-WeaponVisualOff`
  remains the negative control.

## Turret visual mirror (2026-10-20)

The turret is not a projectile and is not a `WeaponSpawnTurret.OnSpawn` call on the tested asset:
`SpawnWeaponSkill_TurretThumper` creates `WeaponSpawnThumperTurret`, which overrides `OnSpawn` and
`DeSpawn`. Patching the base virtual and the override together is the documented 0xc0000005 crash, so
the hook sits on `SpawnWeaponHandler.Spawn`/`Despawn` instead.

- **Host:** `Spawn(Vector3)` postfix registers the handler + spawn skill and watches the public
  `activeSpawns` list. Once the turret instance appears, `TurretSpawn` (33, id/skill/position/life)
  is sent; `TickHostState` sends `TurretState` (34, quantized position + packed yaw, 4 Hz); `Despawn`
  sends `TurretDespawn` (35). The sweep calls `SpawnWeaponHandler.Spawn(player position)` directly
  because a freshly equipped test weapon does not get the game's own deploy tick.
- **Client:** resolves the spawn skill, clones the turret hierarchy and disables every
  `WeaponHandler`/`Collider` on the clone. The spawn skill's `_turretTop` is **null** on the client
  (the reference is resolved on the spawned instance), so the visual source falls back through the
  derived `animatingTop`, `TurretDeploymentPrefab`, and a live local turret. It never calls
  `OnSpawn`/`DoUpdate`, so it cannot shoot or damage.
- **Positive** (`20261020-022442-turret`): host `sent=1 stateSent=56`; client `spawned=1 states=42
  miss=14 prefab='Turret_THUMPER'`, `RESULT: PASS` both roles.
- **Negative** (`20261020-022622-turret`, `-TurretOff`): both `sent=0 spawned=0`, `RESULT: FAIL`.
- **Limits:** the clone is a static visual. Firing VFX/animation, per-part aim and the exact prefab
  source still need work; the client state misses before the visual source is available are counted
  as `miss` (14 in the run), not as failures.

### Turret fire VFX — client side added, still blocked on the host firing (2026-10-20)

The client mirror now has the real light flash, not only the scale pulse:

- `CoopCombat.FlashAt(from, settings, skill)` is the shared light path (the remote-shot `Flash(e)`
  now calls it too); `CoopCombat.MuzzleAt(WeaponHandler, fallbackFrom)` resolves the turret clone's
  own `WeaponHandler.data.FlashSettings` and `firePoint` and calls the same `ImpactLightsManager`.
- `CoopTurret` stores a `WeaponHandler` from the cloned hierarchy (preferring a
  `ProjectileWeaponHandler`), calls `MuzzleAt` on `TurretFire`, and counts `FireFlashes` /
  `FireFlashMiss`. The `turretfire` client verdict now requires `FireFlashes > 0`, so the scale pulse
  alone cannot pass it any more.
- `OnTurretShot` also searches the turret's child `ProjectileWeaponHandler`s; the spawn's
  `weaponHandler`/`spawnWeaponHandler` are not always the firing handler. Only turret-like unmatched
  handlers are logged now, so Bosco/drone shots no longer spam the hook.

Measured (`20261020-125033-turretfire`, direct `SpawnWeaponSkill_TurretThumper` spawn, reliable
auto-start):

```
host:   turret: spawn sent id=1 skill='SpawnWeaponSkill_TurretThumper' native='WeaponSpawnThumperTurret'
host:   turret: fire hook unmatched handler='Bosco_ProjectileWeaponSkill_Base' (x5)
host:   check: turretfire sent=0 recv=0 applied=0 flashes=0
client: turret: spawned id=1 ... prefab='Turret_THUMPER'
client: check: turretfire sent=0 recv=0 applied=0 flashes=0
RESULT: FAIL (both)
```

So the visual mirror and the spawning are still correct, but the direct dev-spawned Thumper turret
never fires: the only `ProjectileWeaponHandler.ShootProjectileInDirection` events are Bosco's. The
client muzzle path is ready and unexercised; it only runs once the host sends `TurretFire`.

**Field probe (`20261020-125843-turretfire`): the handler is initialized, it is just a plain
`WeaponHandler`.** The spawn logs its actual fields:

```
turret: fields wh='Sub_ThumperWeaponSkill' swh='SpawnWeaponSkill_TurretThumper'
        wsd='Sub_ThumperWeaponSkill' owner=1 ext='SpawnWeaponSkill_TurretThumper' fire='FirePoint'
turret: child[0] type='WeaponHandler' data='Sub_ThumperWeaponSkill' dType='WeaponSkillData'
        proj=0 beam=0 lightning=0 expl=0 melee=0 ground=0 auto=0 enabled=1 owner=1 fire='FirePoint'
```

So the direct spawn is fully wired; the Thumper simply does not use a projectile/beam/explosion
handler, and its `OnShoot` action is not invoked by the plain handler either. The actual thump is
the **`OnReloadUpdate(t)` animation callback**, normally driven by the spawn handler's reload. The
direct dev spawn has no live spawn-handler reload, so the callback never ran.

**Fix and verification (`20261020-131050-turretfire`, `20261020-131227-turretfire`).** The turret
state tick (`CoopTurret.OnUpdate`, already the 4 Hz host tick) now advances a 0..1 `ThumperClock` for
a `WeaponSpawnThumperTurret`, calls `OnReloadUpdate`, and `OnReloadFire` mirrors the thump as a
`TurretFire` (0.5 s rate limit). The client `ApplyFire` uses `CoopCombat.MuzzleAt`, so the clone
shows a real `ImpactLightsManager` flash at its `FirePoint`; the `turretfire` verdict requires
`flashes > 0`.

```
positive 20261020-131050:
host:   turret: thump fire id=1 t=0.25 / 0.50 / ...
host:   check: turretfire sent=5 recv=0 applied=0 flashes=0
client: check: turretfire sent=0 recv=5 applied=5 flashes=5
RESULT: PASS both

negative 20261020-131227 (-TurretFireOff):
both:   check: turretfire sent=0 recv=0 applied=0 flashes=0
RESULT: FAIL both
```

The client tick also shows `muzzle=5/5/...` next to the player muzzle, so the turret flash is
counted separately from the scale pulse. The `OnShoot` listener remains a harmless fallback: it
preserves the original game callback and the 0.5 s rate limit prevents a double send if the real
reload path is also active.

Limitations: the 4 Hz `OnReloadUpdate` drive is a dev-spawn approximation of the spawn handler's
real reload cadence; the mirror is **visual**, the host turret's damage path is unchanged; the
natural deploy path is still unverified. Do not claim the exact thump interval until the natural
deploy is tested.

### Reliable test auto-start (2026-10-20)

The desktop click into a background window is not reliable for automation. `-LobbyAutoPlay` reuses
the lobby's tested auto-join + `UISplashForm.AdvanceFlow` + save-slot + `OnPlayButton` path with
`-LobbyUIOff`, so no lobby screen is built and `CoopAuto` drives the wizard. Command shape:

```
coop-run.ps1 -Ui -Auto -Test <name> -LobbyAutoPlay -LobbyUIOff ...
```

`20261020-125033-turretfire` reached the run, the turret spawn and the test verdict in 1m18s; the
earlier desktop-click attempts timed out after 3m48s without reaching the run. This is a harness
change only; normal play still uses the real Play button.

## Co-op lobby — L0 measurement (2026-10-20)

Owner goals recorded for milestone G: a real in-game lobby (own screen), the host sets mission and
difficulty there and the client sees the changes live, the client picks only **class + class mod**,
and the host may start only after the client is ready. Keeping the loading screen up with
"Fertig geladen - warte auf Spieler 2" is explicitly lower priority than the lobby.

Probe: `-cooplobbyprobe` / `-cooptest=lobbyflow` (`CoopLobby.cs`), one host instance:

```
coop-run.ps1 -Deploy -Auto -Test lobbyflow -LobbyProbe -TestQuit both -Only host
```

Archive: `local/work/runs/20261020-053637-lobbyflow/`.

```
RESULT: lobbyflow PASS reason=sources=1 sectors=5 nodes=6 hazards=0 classes=5 mods=15
  hide=ok handlers=8 errors=4 fallbacks=1 driveErrors=0 launched=1 role=host
```

Observations (from the log):

- **The menu-time source is `UIPlaySelectForm.runSettingsManager` + `form.missionRoadManager`.**
  `rs.MissionRoadState` is null in the Play menu; it is assigned only after a main mission is chosen.
  `missionRoadManager.GetMissionRoadState(Elimination)` / `.EliminationState` returns the live road:
  **5 sectors x 6 nodes**, each with `Data.Biome`, `IsLocked`, `MinHazIndex` and `IsCompleted()`.
  This is what the lobby lists.
- **`rs.GetHazardLevels()` NREs in the menu** before a biome is selected
  (`lobbyflow: step=rs.GetHazardLevels failed ... NullReferenceException`). Hazard index 0 still
  works through `OnHazLevelNext(0)` once the hazard page is up. The lobby must read the hazard list
  after the node step (or from the hazard page's own buttons), not at Play time.
- **`form.SetVisibility(false, true)` does not deactivate the form** (`hide=ok hidden=0`), and a
  handler still runs while it is "hidden". The lobby cannot hide the wizard with that call; it must
  **cover** it with its own full-screen surface.
- **Handler route measured:** `StartMainMissionsFlow` -> `OnMainMissionSelect` -> sector -> class ->
  class artifact -> `OnHazLevelNext` -> `UILoadingForm`. `OnMainMissionSelect`,
  `OnClassPageNext`, `OnClassArtifactPageNext` and `OnHazLevelNext` all worked.
- **`OnMissionSectorClick` NREs** with the `MissionSectorState` from the road manager *and* with the
  button's own `sectorState` (4 errors in the run). The game's own `UIMissionSectorButton.OnButtonClick`
  is the working route: the probe pressed `MissionSectorButton_1` and the page advanced to CLASS
  (index 4). The sector page is a **combined page**: it keeps the sector tabs and adds
  `MissionNodeButton_01..06` plus display-only `UIMutatorSetEntry` rows. The first node is selected
  by default, so the node page was skipped and the node handler was not exercised.
- The wizard hands over to `UILoadingForm` **before `GameController` exists**; the probe counts that
  as `launched=1 why=loadingform`. In this fixture the loading form then waits for input (it stayed
  up for 80 s in an earlier run). The load-screen milestone must also **continue** the form, not only
  keep it visible.
- Client class/mod lists are the live `ClassData` / `ClassArtifactData` assets filtered through
  `SaveDataManager.IsClassUnlocked` / `IsUnlocked` (the adopted host profile, I1). Measured:
  **5 class assets, 15 class-mod assets**; the first unlocked class was DRILLER and its first
  unlocked mod `ClassArtifactData_Driller_Interrogator`.

Derived (design consequences):

- The lobby uses the **button path** for mission/sector/node (the game's own `OnButtonClick`), and
  may use the handler path for class, class mod and hazard. The button path is the one proven for
  every selection.
- The lobby screen **covers** `UIPlaySelectForm`; it does not hide it.
- Hazard levels are read after the node selection; at Play time only mission/sector/node data is
  guaranteed.
- The owner's "client picks class + class mod" is exactly what the game exposes; mission, sector,
  node, biome, hazard and mutators are host-side, and skin/starting weapon follow the class mod.

Unknowns (honest):

- Whether `OnMissionSectorClick` can be made to work with another state object (e.g. a state taken
  from the form's current page). Not needed while the button path works, but it is the cleaner API
  if it is ever fixed.
- Why the loading form waits for input in this fixture (auto-continue setting vs. a required input).
  The load-screen milestone starts with a probe of `UILoadingForm.Show`/`SetVisibility`/`OnInput`.

### L1 — protocol + ready/start gate (2026-10-20)

Packets **38 `LobbyState`, 39 `LobbyChoice`, 40 `LobbyStart`** in `CoopNet.cs`; the state machine and
the gate live in `CoopLobby.cs` (`-cooplobbystate`, `-cooptest=lobby-state`). The test runs both
instances in the main menu through the join panel, with no wizard and no run.

**Positive** (`20261020-054247-lobby-state`, `-Ui -Lobby -Test lobby-state`):

```
host:   RESULT: lobby-state PASS reason=host rev=2 blockedPeer=1 blockedStale=1 allowed=1
        choiceRecv=2
client: RESULT: lobby-state PASS reason=client state=2 choice=2 start=1 rev=2
        stateRecv=2 choiceSent=2
```

Sequence: host `rev=1` -> `TryStart` blocked `peer-not-ready` -> client choice on `rev=1`
(ENGINEER / `ClassArtifactData_Engineer_Maintenance`) -> host bumps `rev=2`, `hazard=2` ->
`TryStart` blocked `stale-rev` (the peer's ready still belongs to rev 1) -> client choice on `rev=2`
-> `TryStart` allowed -> `LobbyStart` rev=2 seed=20261017 -> client receives it.

**Negative** (`20261020-054515-lobby-state`, `-LobbyNoReadyGate`):

```
host:   RESULT: lobby-state FAIL reason=ready-gate-off start allowed before peer ready, rev=1
client: RESULT: lobby-state FAIL reason=timeout after 120s
```

The gate is therefore not vacuous: with it disabled the host starts before the client is ready and
the test fails.

Derived: the revision echo is sufficient to invalidate an old ready on a host-side change, and the
start is host-authoritative - the client never starts from its own choice, it waits for
`LobbyStart`. Still open for L2/L3: host-side validation of the client's class/mod against the host
profile, the actual lobby screen, and the handoff of the selected values into the wizard.

### L2 — the real lobby screen (2026-10-20)

The screen is a **clone of the game's root UI canvas** with all children removed, plus cloned
`Image`/`UIButton`/`TextMeshProUGUI` objects for panels, buttons and labels
(`CoopLobbyUI.cs`). It is a ScreenSpaceOverlay canvas with `sortingOrder = 1000`, covers
`UIPlaySelectForm` and blocks its raycasts. The wizard is not driven while it is active
(`CoopAuto.DriveWizard` returns early).

**Positive** (`20261020-063928-lobby-ui`, `-Ui -Lobby -Test lobby-ui`):

```
host:   RESULT: lobby-ui PASS reason=host active=1 sectors=5 classes=5 mods=3 hazard=1
        start=1 rev=2
client: RESULT: lobby-ui PASS reason=client active=1 stateRecv=2 choiceSent=6 start=1 rev=2
```

Sequence: host opens at `rev=1`; host clicks hazard H2 -> `rev=2`; client receives rev 2, selects
ENGINEER / `ClassArtifactData_Engineer_Maintenance`, presses READY; host sees `peerRev=2` and START
is allowed; `LobbyStart` rev=2 reaches the client. The screen exposes 5 sectors, 6 nodes, 5 class
assets, 3 class mods for the local class and 5 hazard levels; the data comes from
`form.missionRoadManager` and is read after the asynchronous load.

**Negative** (`20261020-063812-lobby-ui`, `-LobbyUIOff`): both instances stay `role=solo` and time
out, `RESULT: ... FAIL`. The screen is the thing under test, not a no-op.

Measured implementation facts (these cost several runs, keep them):

- **`AddComponent<T>` is not usable for the UI types.** The Il2CppInterop generic method store
  (`MethodInfoStoreGeneric_AddComponent_Public_T_0`) throws in its type initializer for
  `RectTransform`/`Canvas`/`Image`/`TMP`. `Instantiate` of the game's own root canvas, Images,
  UIButtons and TMP texts works and is the route the screen uses. The root clone keeps the game's
  `CanvasScaler`, `GraphicRaycaster` and the scene's EventSystem; only Canvas/CanvasScaler/
  GraphicRaycaster survive the component filter.
- `CanvasGroup.blocksRaycasts` is **read-only** in the interop; the root CanvasGroup is removed by
  the filter instead of being configured.
- **The splash flow needs the save-slot selection.** `UISplashForm.AdvanceFlow()` alone reached
  `SAVE_SLOT` but never selected a slot, so `SaveDataManager` stayed empty and the menu's Play
  button threw a `NullReferenceException` inside its click. `OnSaveSlotSelected(ESaveSlot.Slot1)`
  is the working path; the test profile's main save is Slot1.
- **The menu Play press needs the managers and a settle.** Wait for
  `UIMenuSplashForm.saveDataManager.SaveData != null` and `metaManager != null`, then 2 s, then call
  `UIMenuSplashForm.OnPlayButton()` directly.
- **The Play form's mission road loads asynchronously.** A single `ReadMenuData` immediately after
  opening saw `sectors=0`. `CoopLobby.EnsureMenuData` retries on the main thread until the road has
  sectors; only then does it send the first `LobbyState`. The panel rebuilds when `UiDataReady`
  flips.
- **Button actions:** `UnityEngine.UI.Button.onClick` cannot take a managed `Action` directly.
  `DelegateSupport.ConvertDelegate<UnityAction>(new Action(...))` + `onClick.AddListener` works; the
  L2 test invokes the exact `Button.onClick` a pointer click reaches. The cloned button's original
  `UIButton` component is destroyed and its event replaced, so a cloned Back button cannot fire the
  game's Back.

Unknowns (honest):

- The screen is verified structurally and by programmatic clicks. A physical mouse click on the
  lobby buttons has not been separately exercised; it goes through the same `Button.onClick`, but
  the EventSystem/pointer path is not independently proven.
- `ScreenCapture.CaptureScreenshot` did not produce a file in this environment (no exception was
  logged either). A visual screenshot/layout review is still open; the screen is built from the
  game's own assets and the test proves it is active and interactive.
- The host's default class came from `runSettingsManager.selectedClass` (Engineer in this run), not
  a fixed class. Both players happened to choose Engineer/Maintenance in the positive run; a
  different-class end-to-end run belongs to L3.

### L3 — start through the real wizard (2026-10-20)

L2's START now drives the game's own `UIPlaySelectForm` with the lobby's selection and creates a
real run. Test `-cooplobbystart` / `-cooptest=lobby-start`, run
`20261020-064751-lobby-start`, `-Ui -Lobby -Test lobby-start`:

```
RESULT: lobby-start PASS host   active=1 sectors=5 classes=5 mods=3 hazard=1 start=1 rev=2
  run=1 dwarf=0 mod='ClassArtifactData_Driller_Interrogator'
RESULT: lobby-start PASS client active=1 stateRecv=2 choiceSent=6 start=1 rev=2
  run=1 dwarf=1 mod='ClassArtifactData_Engineer_Maintenance'
saves: restored and verified (14 files, canary removed)
```

- **Both run settings are the host's lobby choice:** `main=0 biome=0 sector=0 node=0 hazard=1`
  on both sides; host class Driller/Interrogator, client Engineer/Maintenance. Same level,
  different classes.
- **The driver is page-driven, not step-indexed.** The observed order was
  `CAMPAIGN -> CLASS -> NODE -> CLASS -> ARTIFACT -> HAZ`: the game reused the previous
  mission/sector and revisited the class page. Each tick reads the active buttons and presses the
  one carrying the chosen object: sector/node by name, class by dwarf name, class mod by
  `UIClassArtifactButton.data.name`, hazard by `UIHazLevelButton.hazLevel`. The L0/L2 button path
  is the only reliable route, so the driver never calls the handler API directly.
- **Loading form:** the wizard hands over to `UILoadingForm`; the automation continues it with
  `UILoadingForm.OnLoadingComplete()` while `waitingForInput` is true. That is what lets the run
  reach `GameController.StartGame` and the `CoopLoad` barrier. In normal play a key press does
  this; the P2 load-screen work will hold the form with "Fertig geladen - warte auf Spieler 2"
  instead of continuing immediately.
- **Host validation:** `HostStartClicked` checks the client's `PeerDwarf`/`PeerClassMod` against
  `SaveDataManager.IsClassUnlocked`/`IsUnlocked` before sending `LobbyStart`. The client's screen
  already filters the choices, so this is a wire-level safety net.
- **Test timing:** `lobby-start` waits for `ProbeState.Gc != null` plus 5 s before finishing, so
  `run=1` means a real level, not just the loading form or a start packet.
- **Still open:** a visual/layout review of the lobby screen. The screen is functionally verified
  (data, live updates, ready gate, start, programmatic `Button.onClick`); a physical pointer click
  and screenshot are not independently proven. The next visual polish list (turret firing VFX,
  beam visual, held weapon prop, Bosco/turret entity+animation sync, grenade visual-only) is
  unchanged from the last handoff.

### P2 — loading-screen hold (2026-10-20)

The owner's load-screen point is implemented. `CoopLoad` caches the active `UILoadingForm` while
the run is armed, pauses at `StartGame`, re-shows the same form over the paused game, sets
`tipText = "Fertig geladen - warte auf Spieler 2"`, clears the press-any-key prompt, and hides the
form only when the barrier releases. `-cooploadformoff` / `-LoadFormOff` is the negative control.

Positive run `20261020-123303-loadform` PASS both roles:

```
check: load started role=host delay=0.0s timeout=30s
check: load form shown=1 role=host text='Fertig geladen - warte auf Spieler 2' paused=1
check: load held role=host paused=1 form=1 delay=0.0s
check: load released role=host via=both held=1.4s peer=1 timeout=0 paused=1 wait=1
RESULT: loadform PASS reason=host ... run=1 wait=1
```

Negative run `20261020-123406-loadform` (`-LoadFormOff`): both `FAIL reason=loadform wait=0`,
`check: load held ... form=0`. So the test is not vacuous.

Measured/derived:

- The real form survives the game's completion; `SetVisibility(true, true)` re-shows it and the
  `tipText` assignment takes effect. No custom overlay was needed.
- The form's `locPressAnyKey` is a Unity Localization `LocalizedString`, not a TMP; setting
  `pressAnyKeyText.text = ""` is the working prompt hide.
- The hold lasts until the host's `PeerReady`, i.e. exactly the peer-load delta (1.4 s in this
  run). The game is paused behind the form, so the level is never visible while waiting.
- The `loadform` test waits for `ProbeState.Gc` + 5 s and requires `CoopLoad.WaitShownEver`, so a
  PASS means the real run started **and** the wait screen was actually shown.
- A visual check of the form's exact layout (title/logo, tip placement) is still open; the log
  proves it was visible and the text was set.

## Bosco mirror — done (2026-10-20)

Both players have their own live `Bosco`; the client uses its own as the visual source for the
host's companion.

- Packet 41 `BoscoState` at 10 Hz: position x/y/z, yaw (ushort), `state`, `speedFrac`, slowing/
  active flags. The host finds its live `Bosco` (`player.Pointer == Player.Pointer`, enabled) and
  sends position/yaw/state/speed/flags.
- The client drains the queue, clones its **own** live Bosco once, disables the `Bosco` component,
  the `WeaponHandler`s and the `Collider`s, keeps the `Animator`, applies position/yaw and sets
  `ID_SPEED`/`ID_BRAKE`; `ID_SALUTE` fires on a state transition. The clone is visual-only and
  named `CoopPuppetBosco`; the client's own Bosco stays visible.
- Positive `20261020-134658-bosco`: host `RESULT: bosco PASS sent=164`; client `recv=173 spawned=1
  statesApplied=194 renderers=3 miss=0`; launcher `RESULT: PASS`.
- Negative `-BoscoOff` `20261020-134912-bosco`: both FAIL `sent=0 recv=0 spawned=0 statesApplied=0
  renderers=0`; launcher `RESULT: FAIL`. `CoopBosco.Tick` runs `MaybeTest` even when disabled, so
  the negative produces the Bosco verdict instead of a timeout.
- Limits: the clone animation is approximate (speed/brake/salute; no full lean/vertical
  parameters); the clone carries no host Bosco damage/behaviour. The client's own Bosco remains
  authoritative for its own actions. A visual check of the clone is still open.




