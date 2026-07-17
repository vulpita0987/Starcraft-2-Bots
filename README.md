# Owain Bot vs Alexandra Bot

This repository can run the two existing Python bots directly against each other:

| Player | Bot code | Race |
| --- | --- | --- |
| Owain Bot | `Owain 1.py` (`SimpleZergBot`) | Zerg |
| Alexandra Bot | `Version2.py` (`SimpleProtossBot`) | Protoss |

The bots' strategy code has not been moved or changed. `run_match.py` only loads both classes and gives them the two player slots in one StarCraft II game.

## First-time setup on each computer

1. Install the full StarCraft II game and launch it at least once.
2. Install Python 3.10 or newer.
3. Double-click `setup.bat` in this folder.

The setup creates a private `.venv` folder for that computer and installs the shared version of the bot library from `requirements.txt`. Do not use or edit the old tracked `venv` folder; it contains paths from a different computer and is not portable.

## Play a match

Double-click `run_match.bat`.

The default match:

- runs on `AbyssalReefLE`;
- runs in real time so it can be watched;
- opens Owain's game client fullscreen with fog disabled, allowing the camera to
  be moved around the whole map while both bots remain in control;
- saves a dated replay under `replays`;
- prints the winner when the game ends.

StarCraft II only permits the two agent clients in this kind of local 1v1, so the
watch view uses Owain's client rather than launching a separate third observer.

To check everything without starting a game, open a terminal in this folder and run:

```powershell
.\run_match.bat --check
```

Useful optional commands:

```powershell
# Simulate as quickly as possible
.\run_match.bat --no-realtime

# Run without the fullscreen watch view
.\run_match.bat --no-spectate

# Use another installed map
.\run_match.bat --map "MapName"

# Run a repeatable match and stop after one hour of in-game time
.\run_match.bat --random-seed 42 --game-time-limit 3600

# Do not save a replay
.\run_match.bat --no-replay
```

The launcher automatically checks both the normal C-drive location and
`D:\StarCraft II`. If StarCraft II is installed somewhere else, create an
untracked `.env.local` file containing its root folder:

```text
SC2PATH=D:\Games\StarCraft II
```

The root folder must contain the game's `Versions` and `Maps` folders.

## If the match closes immediately

Run `.\run_match.bat --check`. The launcher checks the StarCraft II executable
before opening the game and reports damaged installations directly. If it reports
a corrupted executable, open Battle.net, select StarCraft II, open the menu beside
Play, and choose **Scan and Repair**. Reinstall the game if Battle.net cannot repair
the file.

## Working together

- Owain edits the `SimpleZergBot` class in `Owain 1.py`.
- Alexandra edits the `SimpleProtossBot` class in `Version2.py`.
- Pull the latest GitHub changes before editing, then commit and push only the intended changes.
- Do not commit `.venv`, `.env.local`, replays, or Python cache files; they are ignored automatically.

If a bot file, class name, or race is deliberately changed later, update its one entry in `BOT_SPECS` near the top of `run_match.py`.
