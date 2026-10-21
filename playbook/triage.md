# Triage: can this game go co-op, and where do I start?

Answer these in order and write the answers into `games/<slug>/NOTES.md`.

1. **Which exact game?** Title, year, store (Steam, GOG, disc), version or build number,
   remaster or original. Co-op mods often support one version only.
2. **Is it already done?** Check [DIRECTORY.md](../DIRECTORY.md) and `games/`. Then run
   the searches in [research.md](research.md). Half-finished projects are the best
   starting points.
3. **Which engine?** Look at the install: file extensions, DLL names, the exe's version
   info. Then check [engine-families.md](engine-families.md): another game on the same
   engine may already have a co-op framework you can reuse.
4. **How much source is there?**
   - Full source or a matching decompilation (Ocarina of Time, Super Mario 64, Animal
     Crossing, KeeperFX): add networking to the code directly.
   - Script source shipped with the game (Unreal Engine 1 and 2, Source SDK, STALKER
     scripts, Papyrus): most game logic is moddable without native code.
   - Plugin or script extender (xNVSE, SKSE, Lua hooks): hook the engine from a DLL.
   - Nothing: closed binary only. Expect heavy reverse engineering; look harder for an
     existing project to join.
5. **Does the engine have any multiplayer?** A shipped deathmatch mode (Deus Ex, STALKER,
   Unreal) means replication, a server and a client already exist. Co-op then means
   making the single-player logic (story scripts, AI, triggers, saves) run on that
   netcode. No netcode at all means building a sync layer: lockstep for deterministic
   games, host authority with state sync for the rest.
6. **Shipping check.** Can you ship your
   changes without shipping the game's files? Is there anti-cheat or an online service
   you must stay away from?

## Rough difficulty

| Situation | Typical path |
|---|---|
| Abandoned co-op mod exists | Revive it: [reviving-abandoned-mods.md](reviving-abandoned-mods.md) |
| Decomp or open source port exists | Add host-authority networking in the code (the sm64coopdx model) |
| Engine has MP plus script source | Make story logic network-aware with script mods |
| Same-engine co-op framework exists | Port the framework (Skyrim Together style work for other Creation Engine games) |
| Console game, no PC version | PC port from a decomp or recompilation if one exists, else emulator co-op: [decomp-and-recomp.md](decomp-and-recomp.md), [console-emulators.md](console-emulators.md) |
| Closed binary, no MP, no scripting | Very hard. Find collaborators, start with research and a design doc |
