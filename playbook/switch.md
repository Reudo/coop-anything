# Nintendo Switch: co-op and local wireless mods

Switch games are the hardest console target legally and technically, but people are already
modding them. This page collects the routes and starting points. Everything here assumes **your
console with custom firmware**. Nintendo is very protective: never link or host game
files, keys, firmware or leaked source code, and nothing for online cheating.

## Routes

| Route | When | Difficulty |
|---|---|---|
| **Hook the game on a console with custom firmware** | Change how an existing game behaves: add local wireless, open its online mode over a different transport, sync more state | Hard |
| **Local wireless over a network** | The game already has local wireless and you want to play it at a distance | Easy, tools exist |
| **Decompilation** | A decomp of the game exists (a few big titles) | Very hard, but the most powerful |
| **Static recompilation to PC** | Experimental for Switch; early tools and claims only | Hardest, unproven |

## Adding local wireless to a game (the common request)

Switch local wireless runs through the system's `ldn` service, and Nintendo's networking
library (PIA) usually sits on top of it.

- A game that already has **online or LAN** multiplayer often has most of the session code. Adding
  local wireless can mean hooking the game so its existing multiplayer session runs over `ldn`
  instead of the internet.
- A game with **only split-screen** needs real network sync first (see
  [how-coop-mods-work.md](how-coop-mods-work.md)), then a transport.
- A **single-player** game needs the full co-op build first, like any other platform.

Steps for an agent:
1. Confirm what multiplayer the game already has (online, LAN, local wireless, split-screen).
2. Find where it creates sessions: decompile the game's main executable with Ghidra (plus REA or
   GhidraMCP) and look for PIA and `nn::ldn` calls, using community SDK headers to name them.
3. Hook those functions with a code-injection framework and redirect the session type.
4. Test with two consoles, or one console against kinnay/LDN on a Linux PC.

## Starting points

| Tool | What it gives you |
|---|---|
| [Atmosphère](https://github.com/Atmosphere-NX/Atmosphere) | The open source custom firmware nearly all Switch modding runs on (GPL-2.0). Game mods load through its LayeredFS and exefs patches. |
| [exlaunch](https://github.com/shadowninja108/exlaunch) | A framework for injecting C/C++ code into Switch applications to hook game functions (GPL-2.0). |
| [Skyline](https://github.com/skyline-dev/skyline) | The same idea, but for Smash Bros. Ultimate only. |
| [nnheaders](https://github.com/open-ead/nnheaders) | Community headers for the Switch SDK, so decompiled calls get readable names. |
| [kinnay/LDN](https://github.com/kinnay/LDN) | A Python implementation of the local wireless protocol, for learning it and testing against a real console from a Linux PC. |
| [kinnay/NintendoClients](https://github.com/kinnay/NintendoClients) | Python clients and a wiki documenting Nintendo's network protocols, including PIA. |
| [ldn_mitm](https://github.com/spacemeowx2/ldn_mitm) + [switch-lan-play](https://github.com/spacemeowx2/switch-lan-play) | Route local wireless traffic over a network: play existing local-wireless games at a distance, and observe how they behave. |
| Ghidra + [REA](https://github.com/morluto/rea) or [GhidraMCP](https://github.com/LaurieWired/GhidraMCP) | Decompile the game's executable to find its session and networking code. |

## Decompilations

A few big Switch games have active decompilations, written as C++ from the game's code:

- [Super Mario Odyssey](https://github.com/MonsterDruide1/OdysseyDecomp)
- [The Legend of Zelda: Breath of the Wild](https://github.com/zeldaret/botw) (Switch 1.5.0)

Neither is a finished PC port, but both are readable maps of how the game works, which makes
hooking far easier. See [decomp-and-recomp.md](decomp-and-recomp.md) for how decompilations
become ports.

## Static recompilation

Turning Switch games into native PC programs is experimental. Projects have been announced, and
one has been publicly disputed as being built on emulator code. Treat claims carefully, use only
projects with public source and a clear license, and never use leaked code.

## Emulators

Switch emulators exist, but many have been taken down or received legal notices. This playbook
does not link them. If you use one, know that its future
may be uncertain.

## Rules

- No keys, firmware, game files or links to them in this repo.
- No leaked or stolen source code.
- No online cheating, no use against Nintendo's online services.
- Document findings and your own code; never redistribute game code.
