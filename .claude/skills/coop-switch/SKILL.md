---
name: coop-switch
description: Mod Nintendo Switch games for co-op or local wireless on a console: find a game's session code (PIA, nn::ldn) with Ghidra, hook it with exlaunch on Atmosphere, test with ldn_mitm or kinnay/LDN, and use Switch decompilations where they exist.
---

# Switch co-op and local wireless

1. A console with custom firmware (Atmosphere). Never put keys, firmware or game files in a repo, and stay away from Nintendo's online services.
2. Find out what multiplayer the game already has: online, LAN, local wireless, split-screen.
3. Already has online or LAN: find where it creates sessions (PIA and `nn::ldn` calls) with Ghidra plus REA or GhidraMCP, naming SDK calls with nnheaders.
4. Hook those functions with exlaunch (Skyline for Smash Ultimate) and redirect the session type to local wireless.
5. Only split-screen or single-player: build the co-op sync first (`coop-build-from-zero`).
6. Check for a decompilation of the game first (Super Mario Odyssey, Breath of the Wild).
7. Test with two consoles, or a console against kinnay/LDN on a Linux PC; ldn_mitm shows how existing local-wireless games behave.

Details: `playbook/switch.md`.
