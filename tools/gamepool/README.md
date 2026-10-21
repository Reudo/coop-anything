# gamepool: run several copies of a game for tests

Tools to run 2 or more copies of any Windows game on one PC, keep them running between tests, and read
what they left behind when one crashes. They were built to test a co-op mod with real game clients; nothing in
the code is specific to one game. Everything game specific lives in one JSON file.

| Part | What it does |
|---|---|
| **Isolated installs** (`provision`) | Builds `<instances>/0`, `1`, ... that mirror the game folder with hard links (almost no disk), with private copies of the files the game writes (settings, saves, plugin folders). The original install is only read. |
| **Launch helpers** (`up`, `down`, `status`, `job`) | Takes game slots, starts copies one after the other, minimized and without taking focus, from a detached process so they outlive the command. Reports a copy that exits early (the usual sign of a single-instance check). Kills only the processes it started. |
| **Warm pool** (`pool up`, `pool lease`, ...) | A daemon keeps N copies running and hands them to tests as leases. A copy is restarted when it dies, stops answering, grew too much RAM, was marked dirty or its lease expired. Starting a big game takes minutes; a lease takes milliseconds. |
| **Low-cost profile** (`lowcost`) | Edits only the private settings of an instance: small window, frame cap, no shadows, no intro movies. The rows are data in your config. |
| **Smoke and probe** (`smoke`, `probe`) | Start copies, check them for a while (alive, ready, RAM, CPU, windows minimized), or log the window states of one fresh copy. |
| **Crash evidence** (`crashlog`) | Copies the game's logs, picks out crash marker lines and adds the Windows application crash record. |
| **Measure** (`measure`) | Samples RAM and CPU of the pooled copies, so you can compare profiles with numbers. |

The slot lock is a separate tool, [`tools/gameslot`](../gameslot/README.md). Every launch here takes a slot first.
For the techniques behind it (hard links, single-instance games, minimized launches) read
[playbook/multi-instance-testing.md](../../playbook/multi-instance-testing.md).

Python standard library only (3.8 or newer; tested on 3.11). Windows only.

## Quick start

1. Copy [examples/fnv.json](examples/fnv.json) to `local/mygame.json` (git ignores `local/`) and edit it:
   set `game_dir` to the install folder, `process_name` to the image name of the game process, `launch.exe`
   to what starts it, and the `link` section to the files your game writes. The tools refuse to run while
   `game_dir` still contains a `<placeholder>`.
2. Build the copies (as many as game slots exist, default 2):

   ```
   python -I tools/gamepool/gamepool.py --config local/mygame.json provision --n 2
   ```

3. Start them, look, stop them:

   ```
   python -I tools/gamepool/gamepool.py --config local/mygame.json up --n 2
   python -I tools/gamepool/gamepool.py --config local/mygame.json status
   python -I tools/gamepool/gamepool.py --config local/mygame.json down
   ```

   `up` refuses to start next to a game process it did not start (the owner may be playing). Pass
   `--allow-foreign` once you know the copies cannot collide with it.

4. Run a test against copies: `job --id t1 --n 2 -- python my_test.py` takes 2 slots, runs the command with
   `GAMEPOOL_INSTANCES=0,1` and `GAMEPOOL_JOB=t1` in its environment, copies the logs from `collect_logs`
   to `<state>/runs/t1/`, and always frees the slots.

5. Or keep copies warm for many tests:

   ```
   python -I tools/gamepool/gamepool.py --config local/mygame.json pool up --size 2
   python -I tools/gamepool/gamepool.py pool lease --owner t1 --n 2        # prints the lease as JSON
   python -I tools/gamepool/gamepool.py pool release --id L1 [--dirty]
   python -I tools/gamepool/gamepool.py pool status
   python -I tools/gamepool/gamepool.py pool down
   ```

   In Python:

   ```python
   sys.path.insert(0, "tools/gamepool"); from gplib.client import lease
   with lease("my-test", n=2, ttl_s=900, timeout_s=600) as L:
       L.instances                     # [0, 1], host first
       L.check(0)                      # raises PoolError if instance 0 was restarted under you
       L.dirty(0, "loaded a foreign save")   # recycled when the lease ends
       L.renew()                       # extend during a long test
   ```

   Leaving the block releases the lease; an exception inside marks every instance dirty. How your test talks to
   the game (a bridge, a socket, files in the instance folder) is up to the test.

The pool daemon listens on 127.0.0.1 only; its port and a random token are in `<state>/pool/pool.json`.
`pool up --fake` runs a pool of in-memory fake instances (nothing is launched) so you can try the lease
commands. State lives in `GAMEPOOL_DIR`, else `<repo>/local/gamepool`.

## Config file

One JSON file per game. `_notes` and other keys starting with `_` are ignored. Paths may use `%VARS%`.
`{i}` (instance number), `{instance_dir}`, `{game_dir}` and `{role}` are filled in where the table says so.

| Key | Meaning |
|---|---|
| `name` | Display name; also names the default instances folder |
| `game_dir` | The install to mirror. Only read, never written |
| `instances_root` | Where the copies go (default `<state>/instances/<name>`). Hard links need the same NTFS volume as `game_dir`. Must not contain `game_dir` or be inside it |
| `process_name` | Image name of the game process, for example `Game.exe`. Used to recognise a copy and to list strangers |
| `launch.exe` | What to start, relative to the instance folder or absolute. `launch.args` and `launch.env` may use `{i}`; the copy also gets `GAMEPOOL_INSTANCE` and `GAMEPOOL_INSTANCE_DIR` |
| `launch.window` | `minimized` (default, no focus change), `hidden` or `normal` |
| `launch.spawns_game` | `true` when `exe` is a loader that starts the real game and exits. The real process is found in the process tree below the loader |
| `launch.stagger_s`, `child_wait_s`, `watch_s` | Pause after each start, how long to look for the loader's child, how long a copy must survive to count as started |
| `link.modes` | Order to try: `hardlink`, `symlink`, `copy` |
| `link.per_instance_files` | Files that must be real private files per copy (settings the game rewrites, markers). Never linked |
| `link.empty_dirs`, `link.per_instance_dirs` | Folders created empty per copy (saves, screenshots) or whose contents are not linked (plugin folders) |
| `link.root_skip_suffixes` | Root-level runtime output (`.log`, `.dmp`) that is never shared |
| `link.pinned_files` | Files whose SHA-256 is recorded at `provision` and checked before a `job` |
| `config_files` | For each private settings file: `base` (read only start file, optional), `fallback_base`, `encoding` (default `latin-1`, which keeps any bytes), `edits` as `[section, key, value]`. Every name here must also be in `per_instance_files` |
| `write_files` | Extra private files to create: `{ "relative/path": "text with {i}" }` |
| `protected_paths` | Folders no tool may ever write to (the owner's own settings and saves) |
| `ready` | How a copy is declared ready. `type` is `process`, `window`, `file`, `log_line`, `tcp_port` or `named_pipe`, plus the fields that type needs (`path`, `text`, `base_port`, `name`, `title_contains`), `timeout_s`, `poll_s`, `settle_s` |
| `crash` | `logs` (relative to the instance), `markers` (text that marks a crash line), `wer_match` (regex for the Windows crash record) |
| `collect_logs` | Globs relative to the instance that `job` copies after a run |
| `lowcost.rows`, `lowcost.post_checks` | The cheap-settings profile and values that must hold after it is applied |
| `adapter` | Optional `"file.py:Class"` for game-specific behaviour, see below |
| `pool` | Defaults for the daemon: `recycle_after`, `ws_growth_mb`, `ws_max_mb`, `slot_ttl_s`, `tick_s` |

A `file` readiness probe is deleted before each launch, so a restarted copy is not taken for ready because of
the previous run's file. A `log_line` probe reads a log that your game must start fresh on every launch.

[examples/fnv.json](examples/fnv.json) holds the values the Fallout: New Vegas co-op project used, with
`<game dir>` placeholders. It is a good model for a Gamebryo-style game with INI files.

### Low-cost rows

Each row is `{file, section, key, value, why, status}`. `status` is free text shown in the table
(`required`, `standard`, `guess`, `opt-in` in the example). A row with `"opt_in": "name"` is applied only when
you pass `--opt name=value` (`pool up --opt grids=3`, `lowcost apply --instance 0 --opt grids=3`);
`"value_from_option": true` uses that value and `"option_regex"` rejects other values. `lowcost doc` prints
the profile as a markdown table and `lowcost verify` lists which keys exist in your base files.

### Adapters

The pool needs four answers from a running copy: ready, healthy, "now do this once" (load a save) and "the
lease ended" (drop a game-side lock). The built-in probes answer the first two from the `ready` block. A game
with an in-game bridge (a script plugin that answers pings and loads saves) uses a few lines of Python instead:

```python
# my_adapter.py, next to your config
from gplib.adapter import Adapter

class MyAdapter(Adapter):
    def probe(self, i, pid):            # healthy right now?
        return my_bridge_ping(i)
    def after_ready(self, i, pid):      # once after each start and restart
        my_bridge_load_save(i, "base")
    def on_release(self, i):            # a lease ended
        my_bridge_unlock(i)
```

and `"adapter": "my_adapter.py:MyAdapter"` in the config. The file is your own code and runs with your rights.
The tool the New Vegas project used for this (a pipe client for its in-game plugin) was not ported; it is
exactly the kind of thing an adapter holds.

## What it never does

- Write inside `game_dir`, or into a file with more than one hard link, a link, a folder outside
  `instances_root`, or anything under `protected_paths` (`instances.guard_write`).
- Kill a process it did not start. Each launched pid is recorded with its image name and creation time and
  registered with `gameslot`; a kill happens only while all three still match.
- Find the game behind a loader by "a new process with that name appeared". It walks the process tree below
  the loader, so a game that someone else started at the same moment is never picked up.
- Close handles in, inject into or read the memory of another process.
- Start two copies at once or launch without holding a slot.

## How it is tested

```
python -I tools/gamepool/run_tests.py       # prints ALL OK only if every check passes and every twin is caught
```

43 checks and 31 mutation twins at the time of writing; it takes about three minutes because it starts real
processes. No real game is started. The game is `tests/fake_game.py`, a Python script that can hold a named
mutex, look for a window class, write a ready file, listen on a port or crash, and shows no visible window.

- **Config and installs:** the New Vegas example loads and still refuses to run with its placeholders; unlinked
  config files, unknown keys and an instances folder that contains the install or sits inside it are refused; hard links for big files and private files for
  settings; the original install and the owner's settings and saves are hashed before and after; provisioning
  over an old link never writes through it; destroy leaves the install intact; pinned hashes; the disk check;
  copy mode.
- **Real stand-in processes:** launch two copies side by side, register their pids with the game slot, stop
  them and prove that a decoy process with the same image name keeps running; a tampered record (a reused pid)
  is not killed; a loader's child is found by process tree while strangers are ignored; a fixed-name mutex and a
  fixed window class stop the second copy and the early exit is reported with its exit code, while a
  per-process name lets both run; a crash writes marker lines the crash report finds; jobs pass, fail, time
  out, find a missing pinned file and always free their slots; instance file locks.
- **Readiness:** the file, log line, TCP port, named pipe and process probes, the wait with timeout and death, a
  custom adapter loaded from the config.
- **Pool policy (in-memory fakes):** exclusive leases, host first, recycle after K leases, dirty and expired
  leases, renewal, kills only own pids, reaping a crashed daemon's pids, crash restart, no dead instance handed
  out, unresponsive copies, RAM growth, failed starts, slot renewal and pid registration.
- **Whole stack:** a loopback daemon and client, real game slots, a pool of two real stand-in processes that
  survives a killed copy and a dirty release and ends with every pooled copy gone and the decoy alive, a smoke
  run that cleans up after a good run and after a copy that never becomes ready, a launch probe that starts and
  stops one copy, and the command line end to end
  (provision, status, up, down, crashlog, job, `pool up --fake` with lease, release, status and down).
- **Twins:** each breaks one guard (config validation, root check, private files, write through links, disk
  check, pins, write guard, opt-in rows, probes, `after_ready`, early-exit report, child lookup by name, slot
  release, instance locks, stand-ins left running, double lease, no recycling, no expiry, kill of foreign
  processes, crashes not noticed, dead instances handed out, ...) and the same check runs again against it.

Not part of the test suite: real games, `measure`, minimizing visible windows (the stand-in shows none, so the tests do
not touch the screen), and hard links across two volumes (the disk check is exercised with a fake free-space value).

## Files

`gamepool.py` (command line), `gplib/` (`config`, `instances`, `inifile`, `lowcost`, `launcher`, `jobqueue`,
`adapter`, `poolcore`, `backend`, `fakes`, `daemon`, `client`, `poolcli`, `smoke`, `crashlog`, `measure`,
`winproc`), `examples/fnv.json`, `tests/fake_game.py`, `run_tests.py`.

## Ported from fnv-coop commit f57aa78

Ported from `tools/pool/`, `tools/runner/` (`instances`, `winproc`, `launchprobe`, `crashlog`, `jobqueue`,
`multismoke`, `run`) and their tests in [fnv-coop](https://github.com/cranebeaker/fnv-coop) (commit f57aa78).
What changed:

- Fallout: New Vegas paths, exe names, INI keys and the pipe bridge client are gone from the code. Settings,
  low-cost rows, log names and readiness are now config. The New Vegas values are in `examples/fnv.json`.
- The bridge calls became the adapter interface and the `ready` probes.
- Instances are numbered by game slot, and state is kept per owner so two agents never share a state file.
- The loader lookup uses the process tree instead of "a new process with that name".
- Guards are stricter: a write must be inside the instances folder and outside every protected path.
- The tests were rebuilt around fake stand-in processes, and every twin is applied by the test runner from
  outside the code (the old pool code carried test-only switches).
