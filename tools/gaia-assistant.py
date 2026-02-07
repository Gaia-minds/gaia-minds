#!/usr/bin/env python3
"""Standalone Gaia personal assistant launcher.

This wrapper makes it easier for users to run Gaia's dual-track evolution loop
as a personal assistant runtime without OpenClaw as a hard dependency.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_HOME = Path(os.environ.get("GAIA_ASSISTANT_HOME", str(Path.home() / ".gaia-assistant"))).expanduser()
DEFAULT_STATE_DIR = DEFAULT_HOME / "state"
DEFAULT_CONFIG_PATH = DEFAULT_HOME / "config.json"
AGENT_CONFIG_PATH = SCRIPT_DIR / "agent-config.yml"
AGENT_LOOP_PATH = SCRIPT_DIR / "agent-loop.py"
DEFAULT_GAIA_AUTH_STORE = DEFAULT_HOME / "auth-profiles.json"
DEFAULT_CODEX_AUTH_PATH = Path(
    os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
).expanduser() / "auth.json"
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


def _write_secret_json(path: Path, payload: Dict[str, Any]) -> None:
    _write_json(path, payload)
    try:
        os.chmod(path, 0o600)
    except OSError:
        # Best effort: on some filesystems chmod may not be supported.
        pass


def _normalize_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg: Dict[str, Any] = payload if isinstance(payload, dict) else {}

    runtime = cfg.setdefault("runtime", {})
    runtime.setdefault("mode", "continuous")
    runtime.setdefault("interval_minutes", 60)

    auth = cfg.setdefault("auth", {})
    providers = auth.setdefault("providers", {})
    auth.setdefault("store_path", str(DEFAULT_GAIA_AUTH_STORE))
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


def _resolve_openclaw_auth_store(openclaw_agent: str, override_path: Optional[str]) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    return DEFAULT_OPENCLAW_STATE_DIR / "agents" / openclaw_agent / "agent" / "auth-profiles.json"


def _resolve_codex_auth_path(override_path: Optional[str]) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    return DEFAULT_CODEX_AUTH_PATH


def _resolve_gaia_auth_store(cfg_path: Path, override_path: Optional[str]) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    cfg = _load_json(cfg_path)
    if cfg:
        store = cfg.get("auth", {}).get("store_path")
        if isinstance(store, str) and store.strip():
            return Path(store).expanduser()
    return cfg_path.parent / "auth-profiles.json"


def _load_gaia_auth_store(path: Path) -> Dict[str, Any]:
    payload = _load_json(path)
    if not payload:
        return {"version": 1, "profiles": {}}
    if not isinstance(payload.get("profiles"), dict):
        payload["profiles"] = {}
    if "version" not in payload:
        payload["version"] = 1
    return payload


def _save_gaia_auth_store(path: Path, payload: Dict[str, Any]) -> None:
    _write_secret_json(path, payload)


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        claims = json.loads(raw)
        return claims if isinstance(claims, dict) else {}
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _read_codex_cli_credentials(codex_auth_path: Path) -> Optional[Dict[str, Any]]:
    payload = _load_json(codex_auth_path)
    if not payload:
        return None
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        return None

    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    account_id = tokens.get("account_id")
    if not isinstance(access, str) or not access.strip():
        return None
    if not isinstance(refresh, str) or not refresh.strip():
        return None

    claims = _decode_jwt_payload(access)
    exp_s = claims.get("exp")
    expires_ms: int
    if isinstance(exp_s, (int, float)):
        expires_ms = int(exp_s * 1000)
    else:
        # Conservative fallback if JWT claims aren't available.
        expires_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + 3600 * 1000

    profile_claims = claims.get("https://api.openai.com/profile")
    email = ""
    if isinstance(profile_claims, dict):
        raw_email = profile_claims.get("email")
        if isinstance(raw_email, str):
            email = raw_email.strip()

    auth_claims = claims.get("https://api.openai.com/auth")
    if not account_id and isinstance(auth_claims, dict):
        auth_account_id = auth_claims.get("chatgpt_account_id")
        if isinstance(auth_account_id, str) and auth_account_id.strip():
            account_id = auth_account_id.strip()

    return {
        "type": "oauth",
        "provider": "openai-codex",
        "access": access,
        "refresh": refresh,
        "expires": expires_ms,
        "account_id": str(account_id).strip() if isinstance(account_id, str) else "",
        "email": email,
        "source": "codex-cli",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


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


def _pick_profile_id(profiles: Dict[str, Dict[str, Any]]) -> Optional[str]:
    if not profiles:
        return None

    ranked: List[Tuple[int, int, str]] = []
    for profile_id, credential in profiles.items():
        expires = credential.get("expires")
        exp = int(expires) if isinstance(expires, (int, float)) else 0
        expired = 1 if _is_expired(credential) else 0
        ranked.append((expired, -exp, profile_id))
    ranked.sort()
    return ranked[0][2]


def _profile_id_for_credential(provider: str, credential: Dict[str, Any]) -> str:
    email = credential.get("email")
    if isinstance(email, str) and email.strip():
        return f"{provider}:{email.strip().lower()}"
    account_id = credential.get("account_id")
    if isinstance(account_id, str) and account_id.strip():
        return f"{provider}:{account_id.strip()}"
    return f"{provider}:default"


def _link_profile(
    cfg_path: Path,
    provider: str,
    profile_id: str,
    source: str,
    store_path: Path,
) -> int:
    cfg = _ensure_config_exists(cfg_path)
    auth = cfg.setdefault("auth", {})
    auth["store_path"] = str(store_path)
    auth["active_profile"] = {
        "provider": provider,
        "profile_id": profile_id,
        "source": source,
        "store_path": str(store_path),
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(cfg_path, cfg)
    return 0


def _codex_login() -> int:
    if not shutil.which("codex"):
        print(
            "Codex CLI is not installed. Install it, then run:\n"
            "  codex login",
            file=sys.stderr,
        )
        return 1
    cmd = ["codex", "login", "--device-auth"]
    return subprocess.run(cmd).returncode


def _import_codex_profile_to_gaia(
    cfg_path: Path,
    provider: str,
    codex_auth_path: Path,
    gaia_auth_store: Path,
) -> Tuple[int, str]:
    if provider != "openai-codex":
        return 1, ""
    credential = _read_codex_cli_credentials(codex_auth_path)
    if credential is None:
        print(
            "Codex credentials not found after login.\n"
            f"Expected auth file: {codex_auth_path}",
            file=sys.stderr,
        )
        return 1, ""

    store = _load_gaia_auth_store(gaia_auth_store)
    profiles = store.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        store["profiles"] = profiles

    profile_id = _profile_id_for_credential(provider, credential)
    profiles[profile_id] = credential
    _save_gaia_auth_store(gaia_auth_store, store)
    _link_profile(cfg_path, provider, profile_id, "gaia-local", gaia_auth_store)
    return 0, profile_id


def _link_openclaw_profile(
    cfg_path: Path,
    provider: str,
    profile_id: str,
    openclaw_store: Path,
) -> int:
    return _link_profile(cfg_path, provider, profile_id, "openclaw", openclaw_store)


def _read_linked_credential(active_profile: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    source = str(active_profile.get("source", "")).strip()
    provider = str(active_profile.get("provider", "")).strip()
    profile_id = str(active_profile.get("profile_id", "")).strip()
    store_raw = str(active_profile.get("store_path", "")).strip()
    if not store_raw:
        return None, "linked profile store_path is empty"

    store_path = Path(store_raw).expanduser()
    if not store_path.exists():
        return None, f"linked profile store not found: {store_path}"

    if source == "gaia-local":
        profiles = _load_gaia_auth_store(store_path).get("profiles", {})
    elif source == "openclaw":
        profiles = _load_openclaw_profiles(store_path)
    else:
        return None, f"unknown auth source: {source}"

    if not isinstance(profiles, dict):
        return None, f"profile store is invalid: {store_path}"

    credential = profiles.get(profile_id)
    if not isinstance(credential, dict):
        return None, f"linked profile missing in store: {profile_id} ({store_path})"

    if provider and credential.get("provider") != provider:
        return None, (
            f"linked profile provider mismatch for {profile_id}: "
            f"expected {provider}, got {credential.get('provider')}"
        )

    return credential, ""


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
    optional_cmds = ["gh", "codex", "openclaw"]
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
    if not cfg:
        print(f"[warn] launcher config not found yet: {cfg_path}")
        print("       run `python3 tools/gaia-assistant.py init` or `... onboard`")
    else:
        cfg = _normalize_config(cfg)
        active = cfg.get("auth", {}).get("active_profile")
        if not isinstance(active, dict):
            print("[warn] no linked OAuth profile in launcher config")
            print("       run `python3 tools/gaia-assistant.py onboard`")
        else:
            credential, error = _read_linked_credential(active)
            if credential is None:
                print(f"[warn] {error}")
            else:
                profile_id = str(active.get("profile_id", "")).strip()
                expiry = _format_expiry(credential)
                if _is_expired(credential):
                    print(f"[warn] linked OAuth profile is expired: {profile_id} (expires={expiry})")
                else:
                    print(f"[ok] linked OAuth profile found: {profile_id} (expires={expiry})")

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
    print("Auth flow selected: Gaia native profile store + Codex web OAuth broker")
    print("This opens a browser/device auth flow through Codex CLI.")
    print("Tokens are copied into Gaia local auth store (outside this repository).")
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
        source="codex-cli",
        codex_auth_path=args.codex_auth_path,
        gaia_auth_store=args.gaia_auth_store,
        openclaw_agent="main",
        openclaw_auth_store=None,
        no_prompt=True,
    )
    return cmd_auth_login(login_args)


def cmd_auth_login(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    _ensure_config_exists(cfg_path)
    provider = str(args.provider).strip()
    source = str(args.source).strip()

    if provider != "openai-codex":
        print(f"Unsupported OAuth provider: {provider}", file=sys.stderr)
        print("Supported provider for now: openai-codex", file=sys.stderr)
        return 1

    if source == "codex-cli":
        if not args.no_prompt:
            answer = input(
                "Gaia will run Codex web OAuth login, then import credentials into Gaia local auth store.\n"
                "Continue? [Y/n]: "
            ).strip().lower()
            if answer in ("n", "no"):
                print("Canceled.")
                return 1

        rc = _codex_login()
        if rc != 0:
            return rc

        codex_auth_path = _resolve_codex_auth_path(args.codex_auth_path)
        gaia_auth_store = _resolve_gaia_auth_store(cfg_path, args.gaia_auth_store)
        rc, profile_id = _import_codex_profile_to_gaia(cfg_path, provider, codex_auth_path, gaia_auth_store)
        if rc != 0:
            return rc

        store = _load_gaia_auth_store(gaia_auth_store)
        profiles = store.get("profiles", {}) if isinstance(store, dict) else {}
        credential = profiles.get(profile_id) if isinstance(profiles, dict) else {}
        expiry = _format_expiry(credential if isinstance(credential, dict) else {})

        print("[ok] OAuth profile linked for Gaia assistant")
        print(f"     source:   gaia-local (imported from codex-cli)")
        print(f"     provider: {provider}")
        print(f"     profile:  {profile_id}")
        print(f"     store:    {gaia_auth_store}")
        print(f"     expires:  {expiry}")
        print("")
        print("Note: credentials are stored in local Gaia auth store, not in this repository.")
        return 0

    if source == "openclaw":
        if not args.no_prompt:
            answer = input(
                "OAuth login opens a browser and stores tokens in OpenClaw local state.\n"
                "Continue? [Y/n]: "
            ).strip().lower()
            if answer in ("n", "no"):
                print("Canceled.")
                return 1

        if not shutil.which("openclaw"):
            print(
                "OpenClaw CLI is not installed. Install it, or use --source codex-cli.",
                file=sys.stderr,
            )
            return 1

        rc = subprocess.run(["openclaw", "models", "auth", "login", "--provider", provider]).returncode
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
            print(
                f"Requested profile not found for provider {provider}: {selected_profile_id}",
                file=sys.stderr,
            )
            return 1

        _link_openclaw_profile(cfg_path, provider, selected_profile_id, store_path)
        credential = provider_profiles[selected_profile_id]
        print("[ok] OAuth profile linked for Gaia assistant")
        print(f"     source:   openclaw")
        print(f"     provider: {provider}")
        print(f"     profile:  {selected_profile_id}")
        print(f"     store:    {store_path}")
        print(f"     expires:  {_format_expiry(credential)}")
        print("")
        print("Note: tokens are not written to this repository.")
        return 0

    print(f"Unsupported auth source: {source}", file=sys.stderr)
    print("Supported sources: codex-cli, openclaw", file=sys.stderr)
    return 1


def cmd_auth_link(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    _ensure_config_exists(cfg_path)
    provider = str(args.provider).strip()
    source = str(args.source).strip()

    if source == "codex-cli":
        codex_auth_path = _resolve_codex_auth_path(args.codex_auth_path)
        gaia_auth_store = _resolve_gaia_auth_store(cfg_path, args.gaia_auth_store)
        rc, profile_id = _import_codex_profile_to_gaia(cfg_path, provider, codex_auth_path, gaia_auth_store)
        if rc != 0:
            return rc
        print("[ok] Imported and linked Codex OAuth profile into Gaia local store")
        print(f"     provider: {provider}")
        print(f"     profile:  {profile_id}")
        print(f"     store:    {gaia_auth_store}")
        return 0

    if source == "openclaw":
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

    print(f"Unsupported auth source: {source}", file=sys.stderr)
    print("Supported sources: codex-cli, openclaw", file=sys.stderr)
    return 1


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

    credential, error = _read_linked_credential(active)
    if credential is None:
        print(f"[warn] {error}")
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

    onboard = sub.add_parser("onboard", help="Guided onboarding with Gaia-native OAuth linking")
    onboard.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    onboard.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Local state directory")
    onboard.add_argument(
        "--gaia-auth-store",
        default=None,
        help="Path to Gaia auth-profiles.json (optional override)",
    )
    onboard.add_argument(
        "--codex-auth-path",
        default=None,
        help="Path to Codex auth.json (optional override)",
    )
    onboard.add_argument("--yes", action="store_true", help="Skip onboarding confirmations")
    onboard.set_defaults(func=cmd_onboard)

    doctor = sub.add_parser("doctor", help="Validate local environment and auth readiness")
    doctor.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    doctor.set_defaults(func=cmd_doctor)

    auth = sub.add_parser("auth", help="Manage OAuth profile linkage for Gaia assistant")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    auth_login = auth_sub.add_parser("login", help="Run web OAuth login and link profile")
    auth_login.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_login.add_argument("--provider", default="openai-codex", help="Provider id (default: openai-codex)")
    auth_login.add_argument(
        "--source",
        choices=["codex-cli", "openclaw"],
        default="codex-cli",
        help="OAuth source (default: codex-cli)",
    )
    auth_login.add_argument(
        "--gaia-auth-store",
        default=None,
        help="Path to Gaia auth-profiles.json (optional override)",
    )
    auth_login.add_argument(
        "--codex-auth-path",
        default=None,
        help="Path to Codex auth.json (optional override)",
    )
    auth_login.add_argument("--openclaw-agent", default="main", help="OpenClaw agent id (openclaw source only)")
    auth_login.add_argument(
        "--openclaw-auth-store",
        default=None,
        help="Path to OpenClaw auth-profiles.json (openclaw source only)",
    )
    auth_login.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    auth_login.add_argument("--no-prompt", action="store_true", help="Skip confirmation prompts")
    auth_login.set_defaults(func=cmd_auth_login)

    auth_link = auth_sub.add_parser("link", help="Link an existing profile without logging in")
    auth_link.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_link.add_argument("--provider", default="openai-codex", help="Provider id (default: openai-codex)")
    auth_link.add_argument(
        "--source",
        choices=["codex-cli", "openclaw"],
        default="codex-cli",
        help="Profile source (default: codex-cli)",
    )
    auth_link.add_argument(
        "--gaia-auth-store",
        default=None,
        help="Path to Gaia auth-profiles.json (optional override)",
    )
    auth_link.add_argument(
        "--codex-auth-path",
        default=None,
        help="Path to Codex auth.json (optional override)",
    )
    auth_link.add_argument("--openclaw-agent", default="main", help="OpenClaw agent id (openclaw source only)")
    auth_link.add_argument(
        "--openclaw-auth-store",
        default=None,
        help="Path to OpenClaw auth-profiles.json (openclaw source only)",
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
