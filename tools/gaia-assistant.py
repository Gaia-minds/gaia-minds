#!/usr/bin/env python3
"""Standalone Gaia personal assistant launcher.

This wrapper makes it easier for users to run Gaia's dual-track evolution loop
as a standalone personal assistant runtime.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_HOME = Path(os.environ.get("GAIA_ASSISTANT_HOME", str(Path.home() / ".gaia-assistant"))).expanduser()
DEFAULT_STATE_DIR = DEFAULT_HOME / "state"
DEFAULT_CONFIG_PATH = DEFAULT_HOME / "config.json"
DEFAULT_SECRET_STORE = DEFAULT_HOME / "secrets.json"
AGENT_CONFIG_PATH = SCRIPT_DIR / "agent-config.yml"
AGENT_LOOP_PATH = SCRIPT_DIR / "agent-loop.py"
DEFAULT_LAUNCHER_HINT = "python3 tools/gaia-assistant.py"
DEFAULT_GAIA_AUTH_STORE = DEFAULT_HOME / "auth-profiles.json"
DEFAULT_CODEX_AUTH_PATH = Path(
    os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
).expanduser() / "auth.json"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"
ONBOARD_PROVIDER_CHOICES = ("openrouter", "openai", "anthropic", "openai-codex")


DEFAULT_CONFIG: Dict[str, Any] = {
    "runtime": {
        "mode": "continuous",
        "interval_minutes": 60,
    },
    "reasoning": {
        "provider": "anthropic",
        "model": DEFAULT_ANTHROPIC_MODEL,
    },
    "secrets": {
        "store_path": str(DEFAULT_SECRET_STORE),
    },
    "auth": {
        "providers": {
            "anthropic": {
                "subscription_oauth_supported": False,
                "api_key_env": "ANTHROPIC_API_KEY",
            },
            "openai": {
                "subscription_oauth_supported": True,
                "api_key_env": "OPENAI_API_KEY",
            },
            "openai-codex": {
                "subscription_oauth_supported": True,
                "api_key_env": "",
            },
            "openrouter": {
                "subscription_oauth_supported": False,
                "api_key_env": "OPENROUTER_API_KEY",
            },
        }
    },
    "tracks": {
        "default": "auto",
    },
}


def _launcher_hint() -> str:
    hint = os.environ.get("GAIA_ASSISTANT_CLI_HINT", "").strip()
    return hint if hint else DEFAULT_LAUNCHER_HINT


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

    reasoning = cfg.setdefault("reasoning", {})
    reasoning.setdefault("provider", "anthropic")
    reasoning.setdefault("model", DEFAULT_ANTHROPIC_MODEL)

    secrets = cfg.setdefault("secrets", {})
    secrets.setdefault("store_path", str(DEFAULT_SECRET_STORE))

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


def _prompt_yes_no(question: str, default: bool = True, non_interactive: bool = False) -> bool:
    if non_interactive:
        return default
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{question} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _prompt_choice(
    question: str,
    options: List[Tuple[str, str]],
    default_index: int = 0,
    non_interactive: bool = False,
) -> str:
    if not options:
        raise ValueError("options list cannot be empty")
    if default_index < 0 or default_index >= len(options):
        default_index = 0
    if non_interactive:
        return options[default_index][0]

    print(question)
    for idx, (_, label) in enumerate(options, start=1):
        marker = " (default)" if idx - 1 == default_index else ""
        print(f"  {idx}) {label}{marker}")

    while True:
        raw = input(f"Select [1-{len(options)}] (default {default_index + 1}): ").strip()
        if not raw:
            return options[default_index][0]
        if raw.isdigit():
            selected = int(raw)
            if 1 <= selected <= len(options):
                return options[selected - 1][0]
        print("Invalid selection. Please enter a valid number.")


def _resolve_secret_store(cfg_path: Path, override_path: Optional[str]) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    cfg = _load_json(cfg_path)
    if cfg:
        store = cfg.get("secrets", {}).get("store_path")
        if isinstance(store, str) and store.strip():
            return Path(store).expanduser()
    return cfg_path.parent / "secrets.json"


def _load_secret_store(path: Path) -> Dict[str, Any]:
    payload = _load_json(path)
    if not payload:
        return {"version": 1, "api_keys": {}}
    if not isinstance(payload.get("api_keys"), dict):
        payload["api_keys"] = {}
    if "version" not in payload:
        payload["version"] = 1
    return payload


def _save_secret_store(path: Path, payload: Dict[str, Any]) -> None:
    _write_secret_json(path, payload)


def _read_secret_api_key(path: Path, env_var: str) -> str:
    payload = _load_secret_store(path)
    api_keys = payload.get("api_keys", {})
    if not isinstance(api_keys, dict):
        return ""
    value = api_keys.get(env_var)
    if not isinstance(value, str):
        return ""
    return value.strip()


def _write_secret_api_key(path: Path, env_var: str, value: str) -> None:
    payload = _load_secret_store(path)
    api_keys = payload.setdefault("api_keys", {})
    if not isinstance(api_keys, dict):
        api_keys = {}
        payload["api_keys"] = api_keys
    api_keys[env_var] = value
    _save_secret_store(path, payload)


def _default_model_for_provider(provider: str) -> str:
    if provider == "openrouter":
        return DEFAULT_OPENROUTER_MODEL
    if provider == "openai":
        return DEFAULT_OPENAI_MODEL
    return DEFAULT_ANTHROPIC_MODEL


def _set_reasoning_config(cfg_path: Path, provider: str, model: Optional[str]) -> None:
    cfg = _ensure_config_exists(cfg_path)
    reasoning = cfg.setdefault("reasoning", {})
    if not isinstance(reasoning, dict):
        reasoning = {}
        cfg["reasoning"] = reasoning

    reasoning["provider"] = provider
    if model and model.strip():
        reasoning["model"] = model.strip()
    else:
        reasoning["model"] = _default_model_for_provider(provider)
    _write_json(cfg_path, cfg)


def _set_secret_store_config(cfg_path: Path, store_path: Path) -> None:
    cfg = _ensure_config_exists(cfg_path)
    secrets = cfg.setdefault("secrets", {})
    if not isinstance(secrets, dict):
        secrets = {}
        cfg["secrets"] = secrets
    secrets["store_path"] = str(store_path)
    _write_json(cfg_path, cfg)


def _is_zero_pricing(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return float(value) == 0.0
    if isinstance(value, str):
        try:
            return float(value.strip()) == 0.0
        except ValueError:
            return False
    return False


def _fetch_openrouter_free_models(api_key: str) -> List[str]:
    if not api_key:
        return []
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return []

    data = payload.get("data", [])
    if not isinstance(data, list):
        return []

    free: List[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        if ":free" in model_id:
            free.append(model_id)
            continue
        pricing = item.get("pricing", {})
        if isinstance(pricing, dict):
            prompt = pricing.get("prompt")
            completion = pricing.get("completion")
            if _is_zero_pricing(prompt) and _is_zero_pricing(completion):
                free.append(model_id)
    seen = set()
    uniq = []
    for model in sorted(free):
        if model in seen:
            continue
        uniq.append(model)
        seen.add(model)
    return uniq[:8]


def _select_openrouter_model(
    api_key: str,
    explicit_model: Optional[str],
    non_interactive: bool,
) -> str:
    if explicit_model and explicit_model.strip():
        return explicit_model.strip()
    if non_interactive:
        return DEFAULT_OPENROUTER_MODEL

    free_models = _fetch_openrouter_free_models(api_key)
    options: List[Tuple[str, str]] = [("openrouter/auto", "openrouter/auto (recommended)")]
    for model in free_models:
        options.append((model, f"{model} (detected free model)"))
    options.append(("__custom__", "Custom model id"))

    selection = _prompt_choice(
        "Choose your OpenRouter model:",
        options,
        default_index=0,
        non_interactive=non_interactive,
    )
    if selection != "__custom__":
        return selection

    while True:
        custom = input("Enter OpenRouter model id (example: provider/model:free): ").strip()
        if custom:
            return custom
        print("Model id cannot be empty.")


def _configure_api_key_provider(
    cfg_path: Path,
    provider: str,
    api_key_env: str,
    model: Optional[str],
    api_key: Optional[str],
    secret_store_override: Optional[str],
    no_prompt: bool,
    no_store_api_key: bool,
) -> int:
    secret_store = _resolve_secret_store(cfg_path, secret_store_override)
    _set_secret_store_config(cfg_path, secret_store)
    env_value = os.environ.get(api_key_env, "").strip()
    secret_value = _read_secret_api_key(secret_store, api_key_env)
    provided = api_key.strip() if isinstance(api_key, str) else ""

    selected_key = provided or env_value or secret_value
    if not selected_key and no_prompt:
        print(
            f"API key for {provider} is required in non-interactive mode.\n"
            f"Provide --api-key or set {api_key_env}.",
            file=sys.stderr,
        )
        return 1

    if not selected_key:
        selected_key = getpass.getpass(f"Enter {api_key_env}: ").strip()
        if not selected_key:
            print(f"{api_key_env} was empty; onboarding canceled.", file=sys.stderr)
            return 1

    should_store = not no_store_api_key
    if not no_prompt and not no_store_api_key:
        should_store = _prompt_yes_no(
            f"Store {api_key_env} in local secret store ({secret_store})?",
            default=True,
            non_interactive=no_prompt,
        )

    if should_store:
        _write_secret_api_key(secret_store, api_key_env, selected_key)
        print(f"[ok] stored {api_key_env} in local secret store: {secret_store}")
    else:
        print(f"[warn] {api_key_env} not stored; keep it exported in your shell.")

    _set_reasoning_config(cfg_path, provider, model)
    print("[ok] reasoning provider configured")
    print(f"     provider: {provider}")
    print(f"     model:    {model or _default_model_for_provider(provider)}")
    return 0


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
    optional_cmds = ["gh", "codex"]
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

    cfg = _load_json(cfg_path)
    if not cfg:
        print(f"[warn] launcher config not found yet: {cfg_path}")
        launcher = _launcher_hint()
        print(f"       run `{launcher} init` or `{launcher} onboard`")
    else:
        cfg = _normalize_config(cfg)
        reasoning_cfg = cfg.get("reasoning", {})
        reasoning_provider = ""
        if isinstance(reasoning_cfg, dict):
            reasoning_provider = str(reasoning_cfg.get("provider", "")).strip()
            print(
                "[ok] reasoning config: "
                f"{reasoning_cfg.get('provider', '?')}/{reasoning_cfg.get('model', '?')}"
            )

        secret_store = _resolve_secret_store(cfg_path, None)
        anth = os.environ.get("ANTHROPIC_API_KEY", "").strip() or _read_secret_api_key(secret_store, "ANTHROPIC_API_KEY")
        oai = os.environ.get("OPENAI_API_KEY", "").strip() or _read_secret_api_key(secret_store, "OPENAI_API_KEY")
        openrouter = os.environ.get("OPENROUTER_API_KEY", "").strip() or _read_secret_api_key(
            secret_store, "OPENROUTER_API_KEY"
        )
        if anth or oai or openrouter:
            print("[ok] at least one API auth credential is available (env or secret store)")
        else:
            print("[warn] no API credentials found (env or secret store)")
            print("       expected: ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY")

        active = cfg.get("auth", {}).get("active_profile")
        if not isinstance(active, dict):
            if reasoning_provider == "openai-codex":
                print("[warn] no linked OAuth profile in launcher config")
                print(f"       run `{_launcher_hint()} onboard --provider openai-codex`")
            else:
                print("[info] no linked OAuth profile (not required for API-key providers)")
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
    provider = (args.provider or "").strip().lower()
    if not provider:
        provider = _prompt_choice(
            "Choose provider to connect:",
            [
                ("openrouter", "OpenRouter (API key + model selection)"),
                ("openai", "OpenAI (API key)"),
                ("anthropic", "Anthropic (API key)"),
                ("openai-codex", "OpenAI Codex (OAuth via Codex CLI)"),
            ],
            default_index=0,
            non_interactive=args.yes,
        )

    if provider not in ONBOARD_PROVIDER_CHOICES:
        print(f"Unsupported onboarding provider: {provider}", file=sys.stderr)
        print(f"Supported providers: {', '.join(ONBOARD_PROVIDER_CHOICES)}", file=sys.stderr)
        return 1
    print(f"[ok] selected provider: {provider}")

    if provider == "openai-codex":
        print("OAuth flow selected: OpenAI Codex via Codex CLI")
        print("This opens browser/device auth and links profile into Gaia local auth store.")
        should_start = _prompt_yes_no(
            "Start OpenAI Codex OAuth login now?",
            default=True,
            non_interactive=args.yes,
        )
        if not should_start:
            print("Skipped OAuth login. Run this later:")
            print(f"  {_launcher_hint()} auth login --provider openai-codex")
            return 0
        login_args = argparse.Namespace(
            config=str(cfg_path),
            provider="openai-codex",
            source="codex-cli",
            codex_auth_path=args.codex_auth_path,
            gaia_auth_store=args.gaia_auth_store,
            no_prompt=True,
            profile_id=None,
        )
        return cmd_auth_login(login_args)

    api_key_env_by_provider = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    api_key_env = api_key_env_by_provider.get(provider, "")
    if not api_key_env:
        print(f"Provider is not configured for API-key onboarding: {provider}", file=sys.stderr)
        return 1

    provider_model: Optional[str] = args.model
    if provider == "openrouter":
        seed_key = (
            (args.api_key.strip() if isinstance(args.api_key, str) else "")
            or os.environ.get(api_key_env, "").strip()
            or _read_secret_api_key(_resolve_secret_store(cfg_path, args.secret_store), api_key_env)
        )
        provider_model = _select_openrouter_model(
            api_key=seed_key,
            explicit_model=args.model,
            non_interactive=args.yes,
        )
    elif not provider_model or not provider_model.strip():
        provider_model = _default_model_for_provider(provider)

    rc = _configure_api_key_provider(
        cfg_path=cfg_path,
        provider=provider,
        api_key_env=api_key_env,
        model=provider_model,
        api_key=args.api_key,
        secret_store_override=args.secret_store,
        no_prompt=args.yes,
        no_store_api_key=args.no_store_api_key,
    )
    if rc != 0:
        return rc

    print("")
    print("Onboarding complete.")
    print(f"Next: {_launcher_hint()} doctor")
    print(f"Then: {_launcher_hint()} run --mode single --dry-run")
    return 0


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

    print(f"Unsupported auth source: {source}", file=sys.stderr)
    print("Supported sources: codex-cli", file=sys.stderr)
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

    print(f"Unsupported auth source: {source}", file=sys.stderr)
    print("Supported sources: codex-cli", file=sys.stderr)
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
        reasoning_cfg = cfg.get("reasoning", {})
        reasoning_provider = ""
        if isinstance(reasoning_cfg, dict):
            reasoning_provider = str(reasoning_cfg.get("provider", "")).strip()
        print("No linked auth profile in launcher config.")
        if reasoning_provider in ("openrouter", "openai", "anthropic"):
            print("This is expected when using API-key providers.")
            return 0
        print(f"Run: {_launcher_hint()} auth login --provider openai-codex")
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
    state_dir = Path(args.state_dir).expanduser()
    try:
        cfg = _ensure_config_exists(cfg_path)
    except PermissionError:
        print(
            "Cannot create runtime config due to permissions. "
            "Set GAIA_ASSISTANT_HOME or pass --config to a writable path.",
            file=sys.stderr,
        )
        return 1
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(
            "Cannot create runtime state directory due to permissions. "
            "Set GAIA_ASSISTANT_HOME or pass --state-dir to a writable path.",
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
    secret_store = _resolve_secret_store(cfg_path, args.secret_store)
    loaded_from_secret: List[str] = []
    for env_var in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        if env.get(env_var, "").strip():
            continue
        stored = _read_secret_api_key(secret_store, env_var)
        if stored:
            env[env_var] = stored
            loaded_from_secret.append(env_var)

    reasoning_cfg = cfg.get("reasoning", {})
    reasoning_cfg = reasoning_cfg if isinstance(reasoning_cfg, dict) else {}
    configured_provider = str(reasoning_cfg.get("provider", "")).strip()
    configured_model = str(reasoning_cfg.get("model", "")).strip()
    effective_provider = str(args.reasoning_provider or configured_provider).strip()
    effective_model = str(args.reasoning_model or configured_model).strip()

    if args.track != "auto":
        env["GAIA_ACTIVE_TRACK_OVERRIDE"] = args.track
    if effective_provider:
        env["GAIA_REASONING_PROVIDER"] = effective_provider
    if effective_model:
        env["GAIA_REASONING_MODEL"] = effective_model
    env["GAIA_AGENT_MEMORY_DIR"] = str(state_dir)

    runtime_cfg = cfg.get("runtime", {})
    if args.mode == "continuous" and "interval_minutes" in runtime_cfg:
        print(f"Running Gaia assistant in continuous mode (interval={runtime_cfg['interval_minutes']}m)")
    else:
        print(f"Running Gaia assistant in {args.mode} mode")
    if args.track != "auto":
        print(f"Track override: {args.track}")
    if args.reasoning_provider:
        print(f"Reasoning provider override: {args.reasoning_provider}")
    elif effective_provider:
        print(f"Reasoning provider: {effective_provider} (from launcher config)")
    if args.reasoning_model:
        print(f"Reasoning model override: {args.reasoning_model}")
    elif effective_model:
        print(f"Reasoning model: {effective_model} (from launcher config)")
    if loaded_from_secret:
        print(f"Loaded API credentials from secret store: {', '.join(loaded_from_secret)}")

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

    onboard = sub.add_parser("onboard", help="Guided provider onboarding (OAuth or API key)")
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
    onboard.add_argument(
        "--provider",
        choices=list(ONBOARD_PROVIDER_CHOICES),
        default=None,
        help="Provider to onboard (interactive if omitted)",
    )
    onboard.add_argument(
        "--api-key",
        default=None,
        help="API key for API-key providers (openrouter/openai/anthropic)",
    )
    onboard.add_argument(
        "--model",
        default=None,
        help="Reasoning model to set during onboarding",
    )
    onboard.add_argument(
        "--secret-store",
        default=None,
        help="Path to local secrets.json store (optional override)",
    )
    onboard.add_argument(
        "--no-store-api-key",
        action="store_true",
        help="Do not store API key in local secret store",
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
        choices=["codex-cli"],
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
    auth_login.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    auth_login.add_argument("--no-prompt", action="store_true", help="Skip confirmation prompts")
    auth_login.set_defaults(func=cmd_auth_login)

    auth_link = auth_sub.add_parser("link", help="Link an existing profile without logging in")
    auth_link.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_link.add_argument("--provider", default="openai-codex", help="Provider id (default: openai-codex)")
    auth_link.add_argument(
        "--source",
        choices=["codex-cli"],
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
    auth_link.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    auth_link.set_defaults(func=cmd_auth_link)

    auth_status = auth_sub.add_parser("status", help="Show linked auth profile status")
    auth_status.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_status.set_defaults(func=cmd_auth_status)

    run = sub.add_parser("run", help="Run Gaia assistant loop")
    run.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Launcher config JSON path")
    run.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Local state directory for memory files")
    run.add_argument(
        "--secret-store",
        default=None,
        help="Path to local secrets.json store (optional override)",
    )
    run.add_argument("--mode", choices=["single", "continuous"], default="single")
    run.add_argument("--track", choices=["auto", "assistant", "framework"], default="auto")
    run.add_argument(
        "--reasoning-provider",
        choices=["anthropic", "openai", "openrouter"],
        default=None,
        help="Override reasoning provider for this run",
    )
    run.add_argument(
        "--reasoning-model",
        default=None,
        help="Override reasoning model for this run",
    )
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
