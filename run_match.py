"""Run the repository's two StarCraft II bots against each other."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_MAP = "AbyssalReefLE"
COMMON_SC2_INSTALLS = (Path("D:/StarCraft II"),)


class MatchSetupError(RuntimeError):
    """Raised when the local machine is not ready to run a match."""


@dataclass(frozen=True)
class BotSpec:
    display_name: str
    race_name: str
    source_file: Path
    class_name: str


# This is the only wiring that connects the match runner to the bot files.
# Strategy code remains in the two original files and is not duplicated here.
BOT_SPECS = (
    BotSpec("Owain Bot", "Zerg", ROOT / "Owain 1.py", "SimpleZergBot"),
    BotSpec("Alexandra Bot", "Protoss", ROOT / "Version2.py", "SimpleProtossBot"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Owain Bot against Alexandra Bot in StarCraft II."
    )
    parser.add_argument(
        "--map",
        default=DEFAULT_MAP,
        help=f"installed StarCraft II map name (default: {DEFAULT_MAP})",
    )
    parser.add_argument(
        "--realtime",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="watch at normal speed; use --no-realtime for a fast simulation",
    )
    parser.add_argument(
        "--spectate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="open a fullscreen, full-map watch view (default: enabled)",
    )
    parser.add_argument(
        "--game-time-limit",
        type=float,
        metavar="SECONDS",
        help="optional in-game time limit",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        help="optional seed for a repeatable match",
    )
    replay_group = parser.add_mutually_exclusive_group()
    replay_group.add_argument(
        "--replay",
        type=Path,
        help="where to save the replay",
    )
    replay_group.add_argument(
        "--no-replay",
        action="store_true",
        help="do not save a replay",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check the installation and both bot files without starting a game",
    )
    args = parser.parse_args(argv)

    if args.game_time_limit is not None and args.game_time_limit <= 0:
        parser.error("--game-time-limit must be greater than zero")

    return args


def import_sc2() -> tuple[Any, Any, Any, Any, ModuleType, Any]:
    try:
        from sc2 import maps
        from sc2 import paths as sc2_paths
        from sc2.bot_ai import BotAI
        from sc2.data import Race, Result
        from sc2.player import Bot
    except Exception as exc:
        raise MatchSetupError(
            "The StarCraft bot packages are not ready. Run setup.bat first. "
            f"Original error: {exc}"
        ) from exc

    return maps, BotAI, Race, Result, sc2_paths, Bot


def read_sc2_path(env_file: Path) -> Path | None:
    if not env_file.is_file():
        return None

    for raw_line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "SC2PATH":
            cleaned = value.strip().strip('"').strip("'")
            if cleaned:
                return Path(os.path.expandvars(cleaned)).expanduser()
    return None


def find_sc2_install(sc2_paths: ModuleType) -> tuple[Path, Path]:
    candidates: list[tuple[str, Path]] = []

    configured = os.environ.get("SC2PATH")
    if configured:
        candidates.append(("the SC2PATH environment variable", Path(configured)))

    for env_file in (ROOT / ".env.local", ROOT / ".env"):
        configured_path = read_sc2_path(env_file)
        if configured_path is not None:
            candidates.append((env_file.name, configured_path))

    try:
        detected = sc2_paths.get_user_sc2_install()
    except Exception:
        detected = None
    if detected:
        candidates.append(("StarCraft II's ExecuteInfo.txt", Path(detected)))

    default_path = sc2_paths.BASEDIR.get(sc2_paths.PF)
    if default_path:
        candidates.append(("the normal install location", Path(default_path).expanduser()))

    for common_path in COMMON_SC2_INSTALLS:
        candidates.append(("a common alternate install location", common_path))

    checked: list[str] = []
    seen: set[str] = set()
    for source, candidate in candidates:
        candidate = candidate.resolve(strict=False)
        identity = os.path.normcase(str(candidate))
        if identity in seen:
            continue
        seen.add(identity)
        checked.append(f"{source}: {candidate}")

        versions_dir = candidate / "Versions"
        if not versions_dir.is_dir():
            continue
        try:
            executable = Path(sc2_paths.latest_executeble(versions_dir))
        except (FileNotFoundError, ValueError):
            continue
        if executable.is_file():
            os.environ["SC2PATH"] = str(candidate)
            return candidate, executable

    locations = "\n  - ".join(checked) if checked else "no locations were available"
    raise MatchSetupError(
        "A complete StarCraft II installation was not found. Install or update the "
        "game and launch it once, then try again. Locations checked:\n  - " + locations
    )


def validate_sc2_executable(executable: Path) -> None:
    """Catch missing, malformed, or corrupted game executables before launch."""
    try:
        with executable.open("rb") as executable_file:
            header = executable_file.read(2)
    except OSError as exc:
        raise MatchSetupError(
            f"StarCraft II's executable cannot be read: {executable} ({exc})"
        ) from exc

    if header != b"MZ":
        raise MatchSetupError(
            f"StarCraft II's executable is not a valid Windows program: {executable}"
        )

    if os.name != "nt":
        return

    signature_environment = os.environ.copy()
    signature_environment["SC2_EXE_TO_CHECK"] = str(executable)
    try:
        signature_check = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-AuthenticodeSignature -LiteralPath "
                "$env:SC2_EXE_TO_CHECK).Status.ToString()",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=signature_environment,
        )
    except (OSError, subprocess.SubprocessError):
        # Signature checking is an extra Windows diagnostic. Launching can still
        # proceed when PowerShell is unavailable.
        return

    signature_status = signature_check.stdout.strip()
    if signature_status == "HashMismatch":
        raise MatchSetupError(
            "The StarCraft II executable is corrupted: its Blizzard digital "
            "signature does not match the file. In Battle.net, select StarCraft II, "
            "open the menu beside Play, and run Scan and Repair. If that does not "
            "replace the file, reinstall StarCraft II."
        )
    if signature_status and signature_status != "Valid":
        raise MatchSetupError(
            "Windows could not validate the StarCraft II executable "
            f"({signature_status}): {executable}"
        )


def load_bot_class(spec: BotSpec, bot_ai_class: type) -> type:
    if not spec.source_file.is_file():
        raise MatchSetupError(
            f"{spec.display_name}'s file is missing: {spec.source_file.name}"
        )

    module_name = "match_bot_" + "_".join(spec.display_name.lower().split())
    module_spec = importlib.util.spec_from_file_location(module_name, spec.source_file)
    if module_spec is None or module_spec.loader is None:
        raise MatchSetupError(f"Could not load {spec.source_file.name}")

    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise MatchSetupError(
            f"{spec.display_name} could not be loaded from {spec.source_file.name}: {exc}"
        ) from exc

    bot_class = getattr(module, spec.class_name, None)
    if not isinstance(bot_class, type) or not issubclass(bot_class, bot_ai_class):
        raise MatchSetupError(
            f"{spec.source_file.name} must contain a {spec.class_name} class "
            "that inherits from BotAI."
        )
    return bot_class


def replay_path(args: argparse.Namespace) -> Path | None:
    if args.no_replay:
        return None
    if args.replay is not None:
        path = args.replay
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = ROOT / "replays" / f"Owain-vs-Alexandra_{timestamp}.SC2Replay"
    if not path.is_absolute():
        path = ROOT / path
    if path.suffix.lower() != ".sc2replay":
        path = path.with_suffix(".SC2Replay")
    return path.resolve(strict=False)


def describe_result(results: Any, result_enum: Any) -> str:
    if not isinstance(results, list) or len(results) != len(BOT_SPECS):
        return f"Match finished: {results}"

    for index, result in enumerate(results):
        if result == result_enum.Victory:
            return f"Winner: {BOT_SPECS[index].display_name}"

    labels = ", ".join(
        f"{spec.display_name}: {getattr(result, 'name', result)}"
        for spec, result in zip(BOT_SPECS, results)
    )
    return f"Match finished without a winner ({labels})"


def run_bot_match(
    map_settings: Any,
    players: list[Any],
    run_options: dict[str, Any],
    result_enum: Any,
) -> list[Any]:
    """Run two local bots while preserving their real startup exceptions."""
    from aiohttp import ClientConnectionResetError
    from sc2.client import Client
    from sc2.main import _host_game, _join_game
    from sc2.portconfig import Portconfig
    from sc2.protocol import ConnectionAlreadyClosedError

    host_only_options = {
        "save_replay_as",
        "rgb_render_config",
        "random_seed",
        "disable_fog",
    }
    join_options = {
        key: value
        for key, value in run_options.items()
        if key not in host_only_options
    }
    portconfig = Portconfig()

    original_observation = Client.observation

    async def safe_observation(client: Any, game_loop: int | None = None) -> Any:
        # At the instant a realtime match ends, SC2 can report a sentinel loop
        # close to the uint32 maximum. BurnySC2 adds its normal step and asks
        # protobuf for loop 2**32, which raises before it can read the result.
        if game_loop is not None and game_loop > 0xFFFFFFFF:
            game_loop = None
        return await original_observation(client, game_loop)

    Client.observation = safe_observation

    async def run_clients() -> list[Any]:
        return await asyncio.gather(
            _host_game(
                map_settings,
                players,
                **run_options,
                portconfig=portconfig,
            ),
            _join_game(players, **join_options, portconfig=portconfig),
            return_exceptions=True,
        )

    try:
        results = asyncio.run(run_clients())
    finally:
        Client.observation = original_observation
        portconfig.clean()

    bot_results = results[:2]
    disconnect_errors = (ClientConnectionResetError, ConnectionAlreadyClosedError)
    for index, result in enumerate(bot_results):
        ended_at_protocol_boundary = (
            isinstance(result, ValueError) and "4294967296" in str(result)
        )
        if not isinstance(result, disconnect_errors) and not ended_at_protocol_boundary:
            continue
        other_result = bot_results[1 - index]
        if other_result == result_enum.Victory:
            bot_results[index] = result_enum.Defeat
        elif other_result == result_enum.Defeat:
            bot_results[index] = result_enum.Victory
        elif other_result == result_enum.Tie:
            bot_results[index] = result_enum.Tie

    failures = [
        f"{spec.display_name}: {type(result).__name__}: {result}"
        for spec, result in zip(BOT_SPECS, bot_results)
        if isinstance(result, BaseException)
    ]
    if failures:
        raise MatchSetupError(
            "StarCraft II could not run both players:\n  - " + "\n  - ".join(failures)
        )
    if not all(isinstance(result, result_enum) for result in bot_results):
        raise MatchSetupError(f"StarCraft II returned unexpected results: {bot_results}")
    return bot_results


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    maps, BotAI, Race, Result, sc2_paths, Bot = import_sc2()
    install_path, executable = find_sc2_install(sc2_paths)
    validate_sc2_executable(executable)

    try:
        map_settings = maps.get(args.map)
    except KeyError as exc:
        raise MatchSetupError(
            f"Map '{args.map}' is not installed under {install_path / 'Maps'}."
        ) from exc

    bot_classes = [load_bot_class(spec, BotAI) for spec in BOT_SPECS]
    players = [
        Bot(
            getattr(Race, spec.race_name),
            bot_class(),
            name=spec.display_name,
            fullscreen=args.spectate and index == 0,
        )
        for index, (spec, bot_class) in enumerate(zip(BOT_SPECS, bot_classes))
    ]

    print(f"StarCraft II: {executable}")
    print(f"Map: {args.map}")
    print(
        "Players: "
        + " vs ".join(
            f"{spec.display_name} ({spec.race_name})" for spec in BOT_SPECS
        )
    )
    print(
        "Live watch view: "
        + ("fullscreen with fog disabled" if args.spectate else "disabled")
    )

    if args.check:
        print("Ready: StarCraft II, the map, and both bot files passed their checks.")
        return 0

    match_replay = replay_path(args)
    if match_replay is not None:
        match_replay.parent.mkdir(parents=True, exist_ok=True)
        print(f"Replay: {match_replay}")

    run_options: dict[str, Any] = {"realtime": args.realtime}
    if args.spectate:
        run_options["disable_fog"] = True
    if match_replay is not None:
        run_options["save_replay_as"] = str(match_replay)
    if args.game_time_limit is not None:
        run_options["game_time_limit"] = args.game_time_limit
    if args.random_seed is not None:
        run_options["random_seed"] = args.random_seed

    results = run_bot_match(map_settings, players, run_options, Result)
    print(describe_result(results, Result))
    return 0


def main() -> int:
    try:
        return run()
    except MatchSetupError as exc:
        print(f"Setup problem: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Match stopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
