#!/usr/bin/env python3
"""Standalone Gaia personal assistant launcher.

This wrapper makes it easier for users to run Gaia's dual-track evolution loop
as a personal assistant runtime without OpenClaw as a hard dependency.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_HOME = Path(os.environ.get("GAIA_ASSISTANT_HOME", str(Path.home() / ".gaia-assistant"))).expanduser()
DEFAULT_STATE_DIR = DEFAULT_HOME / "state"
DEFAULT_CONFIG_PATH = DEFAULT_HOME / "config.json"
AGENT_CONFIG_PATH = SCRIPT_DIR / "agent-config.yml"
AGENT_LOOP_PATH = SCRIPT_DIR / "agent-loop.py"


DEFAULT_CONFIG: Dict[str, Any] = {
    "runtime": {
        "mode": "continuous",
        "interval_minutes": 60,
    },
    "auth": {
        "providers": {
            "anthropic": {
                "subscription_oauth_supported": True,
                "api_key_env": "ANTHROPIC_API_KEY",
            },
            "openai": {
                "subscription_oauth_supported": True,
                "api_key_env": "OPENAI_API_KEY",
            },
        }
    },
    "tracks": {
        "default": "auto",
    },
}


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    state_dir = Path(args.state_dir).expanduser()
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(
            "Cannot create state directory due to permissions. "
            "Set GAIA_ASSISTANT_HOME or pass --state-dir to a writable path.",
            file=sys.stderr,
        )
        return 1
    if cfg_path.exists() and not args.force:
        print(
            f"Config already exists at {cfg_path}. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1
    try:
        _write_json(cfg_path, DEFAULT_CONFIG)
    except PermissionError:
        print(
            "Cannot write config due to permissions. "
            "Set GAIA_ASSISTANT_HOME or pass --config to a writable path.",
            file=sys.stderr,
        )
        return 1
    print(f"Initialized Gaia assistant config: {cfg_path}")
    print(f"Initialized Gaia assistant state dir: {state_dir}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    _ = args
    problems = 0
    required_cmds = ["python3", "git"]
    optional_cmds = ["gh"]

    print("Gaia assistant doctor")
    print("====================")

    for name in required_cmds:
        if shutil.which(name):
            print(f"[ok] required command found: {name}")
        else:
            problems += 1
            print(f"[missing] required command not found: {name}")

    for name in optional_cmds:
        if shutil.which(name):
            print(f"[ok] optional command found: {name}")
        else:
            print(f"[warn] optional command not found: {name}")

    anth = os.environ.get("ANTHROPIC_API_KEY")
    oai = os.environ.get("OPENAI_API_KEY")
    if anth or oai:
        print("[ok] at least one API auth env var is present")
    else:
        print("[warn] no API key env vars found (ANTHROPIC_API_KEY / OPENAI_API_KEY)")
        print("       subscription OAuth profiles may still be used depending on your runtime setup")

    if not AGENT_CONFIG_PATH.exists():
        problems += 1
        print(f"[missing] agent config not found: {AGENT_CONFIG_PATH}")
    else:
        print(f"[ok] agent config found: {AGENT_CONFIG_PATH}")

    if not AGENT_LOOP_PATH.exists():
        problems += 1
        print(f"[missing] agent loop not found: {AGENT_LOOP_PATH}")
    else:
        print(f"[ok] agent loop found: {AGENT_LOOP_PATH}")

    if problems:
        print(f"\nDoctor found {problems} blocking problem(s).", file=sys.stderr)
        return 1
    print("\nDoctor finished with no blocking problems.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    if not cfg_path.exists():
        try:
            _write_json(cfg_path, DEFAULT_CONFIG)
        except PermissionError:
            print(
                "Cannot create runtime config due to permissions. "
                "Set GAIA_ASSISTANT_HOME or pass --config to a writable path.",
                file=sys.stderr,
            )
            return 1

    cmd = [
        "python3",
        str(AGENT_LOOP_PATH),
        "--config",
        str(AGENT_CONFIG_PATH),
        "--mode",
        args.mode,
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    env = os.environ.copy()
    if args.track != "auto":
        env["GAIA_ACTIVE_TRACK_OVERRIDE"] = args.track

    runtime_cfg = _load_json(cfg_path).get("runtime", {})
    if args.mode == "continuous" and "interval_minutes" in runtime_cfg:
        print(f"Running Gaia assistant in continuous mode (interval={runtime_cfg['interval_minutes']}m)")
    else:
        print(f"Running Gaia assistant in {args.mode} mode")
    if args.track != "auto":
        print(f"Track override: {args.track}")

    result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gaia standalone personal assistant launcher",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize local Gaia assistant config")
    init.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    init.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Local state directory")
    init.add_argument("--force", action="store_true", help="Overwrite config if it exists")
    init.set_defaults(func=cmd_init)

    doctor = sub.add_parser("doctor", help="Validate local environment and auth readiness")
    doctor.set_defaults(func=cmd_doctor)

    run = sub.add_parser("run", help="Run Gaia assistant loop")
    run.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Launcher config JSON path")
    run.add_argument("--mode", choices=["single", "continuous"], default="single")
    run.add_argument("--track", choices=["auto", "assistant", "framework"], default="auto")
    run.add_argument("--dry-run", action="store_true", help="Plan only, do not execute actions")
    run.add_argument("--verbose", action="store_true", help="Verbose logs")
    run.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
