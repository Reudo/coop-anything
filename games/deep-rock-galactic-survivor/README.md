# Deep Rock Galactic: Survivor (2024)

| | |
|---|---|
| Engine | Unity 6 (IL2CPP) |
| Versions tested | Steam build `23854500` |
| Projects | none published — an unpublished prototype is described below |
| QA level | automated (with caveats, see [QA](#qa)) |
| Last updated | 2026-10-17 |

## Where things stand

There is **no co-op** in Deep Rock Galactic: Survivor and no co-op mod. The game is a
single-player survivors-like: one dwarf, one cave, no networking code of any kind in the shipped
assemblies. Playing together therefore means building co-op from scratch as a mod — there is no
"finish the existing mod" path, which is why this page records a from-zero effort.

An unpublished prototype (two instances on one PC) reaches: **same cave on both instances,
dwarves visible to each other, shared XP, and a level-up choice that pauses both games until both
players have picked**. Enemies, loot and terrain are still per-instance — that is the remaining
work, and it is the difference between "the dwarves see each other" and "the dwarves play
together".

## Existing work

Nothing to list. Searches across GitHub, Nexus, ModDB and Steam found no co-op or multiplayer
project, and a full search of the game's own assemblies found no transport, socket or Steam
networking layer. The gap entry in `data/directory.yaml` records what was searched.

## How the game works (for co-op)

Read by decompiling the shipped IL2CPP assemblies. Note **Il2CppDumper cannot read this game**
(metadata v39); Cpp2IL, which ships with BepInEx, can. Modding is BepInEx 6 (IL2CPP) plus Harmony.

- **No netcode at all.** Nothing in the game is authoritative over anything, so every sync
  decision is ours. The prototype is host-authoritative.
- **Level generation has no run seed for normal runs.** Nothing calls `Random.InitState`; only
  `FixedRunInstance` (daily/weekly) carries a seed. `MapGenerator.CreateMap` builds the cave from
  noise settings. This is why two instances generate *different* caves by default — and it is
  fixable: seeding `UnityEngine.Random` to a shared value immediately before `CreateMap` makes the
  two caves identical (proven, see below).
- **`Entity : MonoBehaviour` is the natural sync anchor** — both `Player` and `Enemy` derive from
  it, carrying `currentHp`, `position`, `isAlive`, `TakeDamage`, `Heal`, `Die`.
- **XP has a single entry point:** `Player.GainXp(float amount, bool scaleByXpGain = true)`.
  `CoreGameEvents.OnPlayerXpGain` / `TriggerPlayerXpGain(PlayerXpGainArgs)` is the matching global
  event if an observer is preferred over patching.
- **The level-up flow** lives in `LevelUpManager`: a queue (`levelUps`) drained by
  `StartFlow` → `HandleLevelUps` → `OnLevelUpFinished`, with a `flowActive` flag and a static
  `OnFlowActivity` event. `Player.currentXp`, `totalXp`, `currentLevel` are public fields.
- **Enemies** are owned by `EnemySpawner` (`enemies` registry, `enemyPrefabs`, `poolDictionary`,
  `liveElites`, `liveBosses`) and come from an `ObjectPool`, never `Instantiate`. `Enemy` already
  has an `id` field and exposes `OnDeath`, `OnTookDamage`, `OnHealed`, `OnKnockback`.
- **The game is Zenject-wired** (dependency injection), uses `FSG.MeshAnimator` for meshes, and
  ships a KDTree (`PhysicsSimulation`) that could serve interest management for the swarm.
- **Saves are per user, not per instance.** All instances on one machine share the same profile
  folder and it is Steam Cloud-synced, so two local instances write the same saves unless something
  redirects them.
- **The game hard-requires Steam to be running.** Without it, it hangs on a black screen with
  `SteamAPI_Init() failed` and never reaches a menu — worth knowing before blaming a mod.

## What we changed

Unpublished prototype: a BepInEx IL2CPP plugin using Harmony for hooks and LiteNetLib (the
transport Nitrox uses) over UDP, roles selected by command line. Every item below was verified on
two real game clients, not inferred.

- **Identical caves.** Prefix on `MapGenerator.CreateMap` that seeds `UnityEngine.Random` to a
  shared value on both instances. *Test:* sampled 81 rock positions through the game's own
  `MapGenerator.IsRockBlock` and compared the two 81-bit fingerprints — **identical, 0/81 samples
  differ**, and confirmed visually (same terrain in both windows). Before the fix the same
  comparison differed.
- **The other dwarf is visible.** Each instance clones the local player's visual subtree, positions
  it from the network and drives its animator. *Root cause of the first failure:* the clone was
  taken from the **menu** player and never rebuilt — the menu model has 4 renderers, the in-run
  dwarf has 9. Rebuilding on run start is the fix. (An earlier theory that `FSG.MeshAnimator` left
  `sharedMesh` null was wrong: `nullMeshes=0` before and after.)
- **The other dwarf moves and turns correctly.** Facing is sent as a yaw taken from the remote
  player's graphics container, so it also turns while standing still and aiming. *Root cause of the
  first failure:* speed was derived per frame from a position that only changes ~20 times a second,
  so the instantaneous value was ~3x too high and the animator never returned to idle. Measuring
  across whole packet intervals, and zeroing when the position stops changing, fixed it. The
  animator's real parameters are `isIdle`, `moveSpeed`, `isDead`, `isAngry`, `isMining`, `isPickUp`,
  `flying`, `flyType` — the idle/run switch is `isIdle`, not a "moving" flag.
- **Shared XP.** Every local XP gain is mirrored to the peer and applied there with
  `scaleByXpGain: false`. *Test:* both sides logged `lvl=4 xp=28.0 total=153.0`, each total being
  its own gains plus the other's (95 + 58).
- **Level-up choices pause both games.** `LevelUpManager.OnLevelUpFinished` is held until both
  sides report their picks are done, with a 45 s timeout so a lost peer cannot soft-lock the run.
  *Test:* the log shows a ~4.1 s hold (`holding until remote picks` → `remote picks done` →
  `released`), and both players can pick independently.

## QA

**How it is run.** Two instances of the game on one PC (one host, one client, roles by command
line), bots driving both dwarves so no human input is needed for movement, and a per-instance log.
Assertions are made by comparing the two logs rather than by eye: map fingerprints must be equal,
XP/level totals must be equal, positions must agree with what each side received, and no exceptions
may appear.

**Last result (2026-10-17):** map fingerprints identical (0/81 samples differ); XP identical on both
sides; level-up barrier held ~4.1 s until the second player picked; transport sustained ~20 Hz with
~3200 packets each way over 90 s.

**Caveats, stated plainly:** the clients are started by hand (mission select is not automated yet —
see Known issues), so this is not yet a one-command suite, and the two bots only walk and survive,
they do not fight, mine or pick upgrades. The QA level above reflects that two real clients were
driven and shared state was checked; it is not a claim of a polished automated suite.

## How to play

Not released. There is no installer, no one-click host/join, and no release repo yet.

## Known issues

Plain words, what a player would notice today:

- **Enemies, loot and mined terrain are not synced.** Each instance fights its own swarm; a bug
  killed in one window is still alive in the other, and dropped materials are per-instance.
- **The run must be started with matching settings by hand.** The two instances generate the same
  cave only when the run configuration matches, and the mission must currently be picked in both
  windows.
- **Automating the menu is unsolved.** Scripted UI driving was attempted at length and is
  documented in `NOTES.md`; the wizard can be reached but not yet walked.
- **The second dwarf's animation is approximated** from its movement rather than replicated, so it
  will not show mining or combat animations exactly.
- **Two instances share one save profile**, so a local test run writes to the same saves as a
  normal session.
- **Run the mod from a copy of the game**, never from the Steam install, and keep Steam running.

## Next steps

In the order that makes sense:

1. **Enemy sync** — host-authoritative, with interest management for a swarm that peaks around 260
   live entities. This is the piece that makes it co-op rather than two dwarves in one cave.
2. **Consumed pickups and shared objectives** — a dropped orb taken by one dwarf must disappear for
   the other; "stand in the circle" objectives should progress faster with both players present, and
   the end-of-stage drill should require both.
3. **Death and downed state** — an off-screen indicator for the other dwarf, and a revive mechanic
   (stand near the downed dwarf for ~5 seconds).
4. **Steam join** — the host picks the mission, the partner joins over Steam, the partner readies up
   and the host starts. Scope for now is **main missions only**.
5. **Menu automation** — so tests are one command instead of hand-clicking.

Scope decisions from the owner, for whoever picks this up: **2 players**, difficulty unchanged (no
scaling for the second dwarf), upgrades chosen individually per player, and the shared real save
profile is acceptable.
