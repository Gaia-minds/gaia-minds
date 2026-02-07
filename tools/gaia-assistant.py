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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_HOME = Path(os.environ.get("GAIA_ASSISTANT_HOME", str(Path.home() / ".gaia-assistant"))).expanduser()
DEFAULT_STATE_DIR = DEFAULT_HOME / "state"
DEFAULT_CONFIG_PATH = DEFAULT_HOME / "config.json"
AGENT_CONFIG_PATH = SCRIPT_DIR / "agent-config.yml"
AGENT_LOOP_PATH = SCRIPT_DIR / "agent-loop.py"
DEFAULT_OPENCLAW_STATE_DIR = Path(
    os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw"))
).expanduser()


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


def _normalize_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg: Dict[str, Any] = payload if isinstance(payload, dict) else {}

    runtime = cfg.setdefault("runtime", {})
    runtime.setdefault("mode", "continuous")
    runtime.setdefault("interval_minutes", 60)

    auth = cfg.setdefault("auth", {})
    providers = auth.setdefault("providers", {})
    default_providers = DEFAULT_CONFIG.get("auth", {}).get("providers", {})
    for provider_name, provider_defaults in default_providers.items():
        provider_cfg = providers.setdefault(provider_name, {})
        if isinstance(provider_cfg, dict):
            for key, value in provider_defaults.items():
                provider_cfg.setdefault(key, value)
    auth.setdefault("active_profile", None)

    tracks = cfg.setdefault("tracks", {})
    tracks.setdefault("default", "auto")
    return cfg


def _ensure_config_exists(cfg_path: Path) -> Dict[str, Any]:
    cfg = _load_json(cfg_path)
    if not cfg:
        cfg = _normalize_config(dict(DEFAULT_CONFIG))
        _write_json(cfg_path, cfg)
        return cfg

    cfg = _normalize_config(cfg)
    _write_json(cfg_path, cfg)
    return cfg


def _resolve_openclaw_auth_store(openclaw_agent: str, override_path: str | None) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    return DEFAULT_OPENCLAW_STATE_DIR / "agents" / openclaw_agent / "agent" / "auth-profiles.json"


def _load_openclaw_profiles(path: Path) -> Dict[str, Any]:
    payload = _load_json(path)
    profiles = payload.get("profiles", {})
    return profiles if isinstance(profiles, dict) else {}


def _is_expired(credential: Dict[str, Any]) -> bool:
    expires = credential.get("expires")
    if not isinstance(expires, (int, float)):
        return False
    return int(expires) <= int(datetime.now(timezone.utc).timestamp() * 1000)


def _format_expiry(credential: Dict[str, Any]) -> str:
    expires = credential.get("expires")
    if not isinstance(expires, (int, float)):
        return "unknown"
    try:
        dt = datetime.fromtimestamp(int(expires) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except (OSError, ValueError):
        return "unknown"


def _collect_provider_profiles(profiles: Dict[str, Any], provider: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for profile_id, credential in profiles.items():
        if not isinstance(credential, dict):
            continue
        if credential.get("provider") != provider:
            continue
        out[profile_id] = credential
    return out


def _pick_profile_id(profiles: Dict[str, Dict[str, Any]]) -> str | None:
    if not profiles:
        return None

    ranked: list[tuple[int, int, str]] = []
    for profile_id, credential in profiles.items():
        expires = credential.get("expires")
        exp = int(expires) if isinstance(expires, (int, float)) else 0
        expired = 1 if _is_expired(credential) else 0
        ranked.append((expired, -exp, profile_id))
    ranked.sort()
    return ranked[0][2]


def _openclaw_login(provider: str) -> int:
    if not shutil.which("openclaw"):
        print(
            "OpenClaw CLI is not installed. Install it, then run:\n"
            "  openclaw models auth login --provider openai-codex",
            file=sys.stderr,
        )
        return 1
    cmd = ["openclaw", "models", "auth", "login", "--provider", provider]
    return subprocess.run(cmd).returncode


def _link_openclaw_profile(
    cfg_path: Path,
    provider: str,
    profile_id: str,
    openclaw_store: Path,
) -> int:
    cfg = _ensure_config_exists(cfg_path)
    auth = cfg.setdefault("auth", {})
    auth["active_profile"] = {
        "provider": provider,
        "profile_id": profile_id,
        "source": "openclaw",
        "store_path": str(openclaw_store),
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(cfg_path, cfg)
    return 0


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
    problems = 0
    required_cmds = ["python3", "git"]
    optional_cmds = ["gh"]
    cfg_path = Path(args.config).expanduser()

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

    cfg = _load_json(cfg_path)
    if cfg:
        cfg = _normalize_config(cfg)
        active = cfg.get("auth", {}).get("active_profile")
        if isinstance(active, dict) and active.get("source") == "openclaw":
            profile_id = str(active.get("profile_id", "")).strip()
            store_path = Path(str(active.get("store_path", "")).strip()).expanduser()
            provider = str(active.get("provider", "")).strip()
            if not store_path.exists():
                print(f"[warn] linked OpenClaw profile store not found: {store_path}")
            else:
                profiles = _load_openclaw_profiles(store_path)
                credential = profiles.get(profile_id)
                if isinstance(credential, dict) and credential.get("provider") == provider:
                    expiry = _format_expiry(credential)
                    if _is_expired(credential):
                        print(f"[warn] linked OAuth profile is expired: {profile_id} (expires={expiry})")
                    else:
                        print(f"[ok] linked OAuth profile found: {profile_id} (expires={expiry})")
                else:
                    print(
                        "[warn] linked OAuth profile missing in OpenClaw store: "
                        f"{profile_id} ({store_path})"
                    )
        else:
            print("[warn] no linked OAuth profile in launcher config")
    else:
        print(f"[warn] launcher config not found yet: {cfg_path}")
        print("       run `python3 tools/gaia-assistant.py init` or `... onboard`")

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


def cmd_onboard(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    cfg_created = not cfg_path.exists()
    _ensure_config_exists(cfg_path)

    print("Gaia assistant onboarding")
    print("=========================")
    if cfg_created:
        print(f"[ok] created launcher config: {cfg_path}")
    else:
        print(f"[ok] using existing launcher config: {cfg_path}")
    print(f"[ok] state directory ready: {state_dir}")
    print("")
    print("Auth flow selected: openclaw OAuth (openai-codex)")
    print("This will open a browser/web flow through OpenClaw.")
    print("Tokens stay in OpenClaw local state; Gaia stores only a profile reference.")
    sys.stdout.flush()

    proceed = "y"
    if not args.yes:
        proceed = input("Start web OAuth login now? [Y/n]: ").strip().lower()
    if proceed in ("n", "no"):
        print("Skipped OAuth login. Run this later:")
        print("  python3 tools/gaia-assistant.py auth login --provider openai-codex")
        return 0

    login_args = argparse.Namespace(
        config=str(cfg_path),
        provider="openai-codex",
        openclaw_agent=args.openclaw_agent,
        openclaw_auth_store=args.openclaw_auth_store,
        profile_id=args.profile_id,
        no_prompt=True,
    )
    return cmd_auth_login(login_args)


def cmd_auth_login(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    _ensure_config_exists(cfg_path)
    provider = str(args.provider).strip()

    if provider != "openai-codex":
        print(f"Unsupported OAuth provider: {provider}", file=sys.stderr)
        print("Supported provider for now: openai-codex", file=sys.stderr)
        return 1

    if not args.no_prompt:
        answer = input(
            "OAuth login opens a browser and stores tokens in OpenClaw local state.\n"
            "Continue? [Y/n]: "
        ).strip().lower()
        if answer in ("n", "no"):
            print("Canceled.")
            return 1

    rc = _openclaw_login(provider)
    if rc != 0:
        return rc

    store_path = _resolve_openclaw_auth_store(args.openclaw_agent, args.openclaw_auth_store)
    profiles = _load_openclaw_profiles(store_path)
    provider_profiles = _collect_provider_profiles(profiles, provider)
    if not provider_profiles:
        print(
            "OAuth login finished but no matching OpenClaw profile was found.\n"
            f"Expected store: {store_path}",
            file=sys.stderr,
        )
        return 1

    selected_profile_id = args.profile_id or _pick_profile_id(provider_profiles)
    if selected_profile_id not in provider_profiles:
        print(f"Requested profile not found for provider {provider}: {selected_profile_id}", file=sys.stderr)
        return 1

    _link_openclaw_profile(cfg_path, provider, selected_profile_id, store_path)
    credential = provider_profiles[selected_profile_id]
    print("[ok] OAuth profile linked for Gaia assistant")
    print(f"     provider: {provider}")
    print(f"     profile:  {selected_profile_id}")
    print(f"     store:    {store_path}")
    print(f"     expires:  {_format_expiry(credential)}")
    print("")
    print("Note: tokens are not written to this repository.")
    return 0


def cmd_auth_link(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    _ensure_config_exists(cfg_path)
    provider = str(args.provider).strip()
    store_path = _resolve_openclaw_auth_store(args.openclaw_agent, args.openclaw_auth_store)
    profiles = _load_openclaw_profiles(store_path)
    provider_profiles = _collect_provider_profiles(profiles, provider)
    if not provider_profiles:
        print(
            f"No profiles found for provider '{provider}' in {store_path}.",
            file=sys.stderr,
        )
        return 1

    selected_profile_id = args.profile_id or _pick_profile_id(provider_profiles)
    if selected_profile_id not in provider_profiles:
        print(f"Requested profile not found: {selected_profile_id}", file=sys.stderr)
        return 1

    _link_openclaw_profile(cfg_path, provider, selected_profile_id, store_path)
    print("[ok] Linked existing OpenClaw auth profile")
    print(f"     provider: {provider}")
    print(f"     profile:  {selected_profile_id}")
    print(f"     store:    {store_path}")
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _load_json(cfg_path)
    if not cfg:
        print(f"Launcher config not found: {cfg_path}")
        return 1

    cfg = _normalize_config(cfg)
    active = cfg.get("auth", {}).get("active_profile")
    if not isinstance(active, dict):
        print("No linked auth profile in launcher config.")
        print("Run: python3 tools/gaia-assistant.py auth login --provider openai-codex")
        return 1

    provider = str(active.get("provider", "")).strip()
    profile_id = str(active.get("profile_id", "")).strip()
    source = str(active.get("source", "")).strip()
    store_path = Path(str(active.get("store_path", "")).strip()).expanduser()

    print("Gaia assistant auth status")
    print("==========================")
    print(f"source:    {source}")
    print(f"provider:  {provider}")
    print(f"profile:   {profile_id}")
    print(f"store:     {store_path}")

    if source == "openclaw":
        profiles = _load_openclaw_profiles(store_path)
        credential = profiles.get(profile_id)
        if not isinstance(credential, dict):
            print("[warn] linked profile not found in OpenClaw store")
            return 1
        cred_type = str(credential.get("type", "unknown"))
        expires = _format_expiry(credential)
        email = str(credential.get("email", "")).strip() or "n/a"
        print(f"type:      {cred_type}")
        print(f"email:     {email}")
        print(f"expires:   {expires}")
        if _is_expired(credential):
            print("[warn] OAuth profile is expired")
            return 1
        print("[ok] OAuth profile is ready")
        return 0

    print("[warn] unknown auth source; re-link with auth login/link")
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    try:
        cfg = _ensure_config_exists(cfg_path)
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

    runtime_cfg = cfg.get("runtime", {})
    if args.mode == "continuous" and "interval_minutes" in runtime_cfg:
        print(f"Running Gaia assistant in continuous mode (interval={runtime_cfg['interval_minutes']}m)")
    else:
        print(f"Running Gaia assistant in {args.mode} mode")
    if args.track != "auto":
        print(f"Track override: {args.track}")

    active_profile = cfg.get("auth", {}).get("active_profile")
    if isinstance(active_profile, dict):
        print(
            "Auth profile: "
            f"{active_profile.get('provider', '?')}/{active_profile.get('profile_id', '?')} "
            f"({active_profile.get('source', '?')})"
        )

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

    onboard = sub.add_parser("onboard", help="Guided onboarding with web OAuth linking")
    onboard.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    onboard.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Local state directory")
    onboard.add_argument("--openclaw-agent", default="main", help="OpenClaw agent id")
    onboard.add_argument(
        "--openclaw-auth-store",
        default=None,
        help="Path to OpenClaw auth-profiles.json (optional override)",
    )
    onboard.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    onboard.add_argument("--yes", action="store_true", help="Skip onboarding confirmations")
    onboard.set_defaults(func=cmd_onboard)

    doctor = sub.add_parser("doctor", help="Validate local environment and auth readiness")
    doctor.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    doctor.set_defaults(func=cmd_doctor)

    auth = sub.add_parser("auth", help="Manage OAuth profile linkage for Gaia assistant")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    auth_login = auth_sub.add_parser("login", help="Run web OAuth login via OpenClaw and link profile")
    auth_login.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_login.add_argument("--provider", default="openai-codex", help="Provider id (default: openai-codex)")
    auth_login.add_argument("--openclaw-agent", default="main", help="OpenClaw agent id")
    auth_login.add_argument(
        "--openclaw-auth-store",
        default=None,
        help="Path to OpenClaw auth-profiles.json (optional override)",
    )
    auth_login.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    auth_login.add_argument("--no-prompt", action="store_true", help="Skip confirmation prompts")
    auth_login.set_defaults(func=cmd_auth_login)

    auth_link = auth_sub.add_parser("link", help="Link an existing OpenClaw profile without logging in")
    auth_link.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_link.add_argument("--provider", default="openai-codex", help="Provider id (default: openai-codex)")
    auth_link.add_argument("--openclaw-agent", default="main", help="OpenClaw agent id")
    auth_link.add_argument(
        "--openclaw-auth-store",
        default=None,
        help="Path to OpenClaw auth-profiles.json (optional override)",
    )
    auth_link.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    auth_link.set_defaults(func=cmd_auth_link)

    auth_status = auth_sub.add_parser("status", help="Show linked auth profile status")
    auth_status.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_status.set_defaults(func=cmd_auth_status)

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
