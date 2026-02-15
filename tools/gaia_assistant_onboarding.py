#!/usr/bin/env python3
"""Onboarding/auth provider registry and profile-link helpers for Gaia assistant."""

from __future__ import annotations

import base64
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple


ONBOARD_PROVIDER_CHOICES = ("openrouter", "openai", "anthropic", "openai-codex")
PROFILE_PROVIDER_CHOICES = ("openrouter", "openai", "anthropic", "openai-codex")
AUTH_PROVIDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
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


JsonLoader = Callable[[Path], Dict[str, Any]]
JsonWriter = Callable[[Path, Dict[str, Any]], None]
EnsureConfigFn = Callable[[Path], Dict[str, Any]]
NormalizeConfigFn = Callable[[Dict[str, Any]], Dict[str, Any]]
LinkProfileFn = Callable[[Path, str, str, str, Path], int]
ReadLinkedCredentialFn = Callable[[Dict[str, Any]], Tuple[Optional[Dict[str, Any]], str]]
IsExpiredFn = Callable[[Dict[str, Any]], bool]


def resolve_codex_auth_path(override_path: Optional[str], default_codex_auth_path: Path) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    return default_codex_auth_path


def resolve_gaia_auth_store(
    cfg_path: Path,
    override_path: Optional[str],
    default_gaia_auth_store: Path,
    load_json: JsonLoader,
) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    cfg = load_json(cfg_path)
    if cfg:
        store = cfg.get("auth", {}).get("store_path")
        if isinstance(store, str) and store.strip():
            return Path(store).expanduser()
    return default_gaia_auth_store


def load_gaia_auth_store(path: Path, load_json: JsonLoader) -> Dict[str, Any]:
    payload = load_json(path)
    if not payload:
        return {"version": 1, "profiles": {}}
    if not isinstance(payload.get("profiles"), dict):
        payload["profiles"] = {}
    if "version" not in payload:
        payload["version"] = 1
    return payload


def save_gaia_auth_store(path: Path, payload: Dict[str, Any], write_secret_json: JsonWriter) -> None:
    write_secret_json(path, payload)


def decode_jwt_payload(token: str) -> Dict[str, Any]:
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


def read_codex_cli_credentials(codex_auth_path: Path, load_json: JsonLoader) -> Optional[Dict[str, Any]]:
    payload = load_json(codex_auth_path)
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

    claims = decode_jwt_payload(access)
    exp_s = claims.get("exp")
    expires_ms: int
    if isinstance(exp_s, (int, float)):
        expires_ms = int(exp_s * 1000)
    else:
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


def is_expired(credential: Dict[str, Any]) -> bool:
    expires = credential.get("expires")
    if not isinstance(expires, (int, float)):
        return False
    return int(expires) <= int(datetime.now(timezone.utc).timestamp() * 1000)


def format_expiry(credential: Dict[str, Any]) -> str:
    expires = credential.get("expires")
    if not isinstance(expires, (int, float)):
        return "unknown"
    try:
        dt = datetime.fromtimestamp(int(expires) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except (OSError, ValueError):
        return "unknown"


def profile_id_for_credential(provider: str, credential: Dict[str, Any]) -> str:
    email = credential.get("email")
    if isinstance(email, str) and email.strip():
        return f"{provider}:{email.strip().lower()}"
    account_id = credential.get("account_id")
    if isinstance(account_id, str) and account_id.strip():
        return f"{provider}:{account_id.strip()}"
    return f"{provider}:default"


def can_auto_align_codex_runtime_defaults(
    cfg: Dict[str, Any],
    default_anthropic_model: str,
    normalize_bool_default: Callable[[Any, bool], bool],
) -> bool:
    reasoning = cfg.get("reasoning", {})
    reasoning = reasoning if isinstance(reasoning, dict) else {}
    profile = cfg.get("profile", {})
    profile = profile if isinstance(profile, dict) else {}

    if normalize_bool_default(reasoning.get("explicit_provider_override", False), False):
        return False

    current_provider = str(reasoning.get("provider", "")).strip().lower()
    current_model = str(reasoning.get("model", "")).strip()
    current_profile_provider = str(profile.get("default_provider", "")).strip().lower()

    has_provider_override = current_provider not in ("", "anthropic")
    has_model_override = bool(current_model and current_model != default_anthropic_model)
    has_profile_provider_override = current_profile_provider not in ("", "anthropic", "openai-codex")
    return not (has_provider_override or has_model_override or has_profile_provider_override)


def apply_oauth_runtime_defaults(
    cfg_path: Path,
    oauth_provider: str,
    *,
    ensure_config_exists: EnsureConfigFn,
    normalize_config: NormalizeConfigFn,
    write_json: JsonWriter,
    default_anthropic_model: str,
    default_openai_model: str,
    normalize_bool_default: Callable[[Any, bool], bool],
) -> bool:
    if oauth_provider != "openai-codex":
        return False

    cfg = ensure_config_exists(cfg_path)
    if not can_auto_align_codex_runtime_defaults(cfg, default_anthropic_model, normalize_bool_default):
        return False

    reasoning = cfg.setdefault("reasoning", {})
    if not isinstance(reasoning, dict):
        reasoning = {}
        cfg["reasoning"] = reasoning
    profile = cfg.setdefault("profile", {})
    if not isinstance(profile, dict):
        profile = {}
        cfg["profile"] = profile

    changed = False
    if str(reasoning.get("provider", "")).strip().lower() != "openai":
        reasoning["provider"] = "openai"
        changed = True

    existing_model = str(reasoning.get("model", "")).strip()
    if not existing_model or existing_model == default_anthropic_model:
        if existing_model != default_openai_model:
            reasoning["model"] = default_openai_model
            changed = True

    profile_provider = str(profile.get("default_provider", "")).strip().lower()
    if profile_provider in ("", "anthropic", "openai-codex") and profile_provider != "openai":
        profile["default_provider"] = "openai"
        changed = True

    if changed:
        reasoning["explicit_provider_override"] = False
        write_json(cfg_path, normalize_config(cfg))
    return changed


def import_codex_profile_to_gaia(
    cfg_path: Path,
    provider: str,
    codex_auth_path: Path,
    gaia_auth_store: Path,
    *,
    read_codex_cli_credentials_fn: Callable[[Path], Optional[Dict[str, Any]]],
    load_gaia_auth_store_fn: Callable[[Path], Dict[str, Any]],
    save_gaia_auth_store_fn: Callable[[Path, Dict[str, Any]], None],
    link_profile_fn: LinkProfileFn,
    apply_oauth_runtime_defaults_fn: Callable[[Path, str], bool],
) -> Tuple[int, str, bool]:
    if provider != "openai-codex":
        return 1, "", False
    credential = read_codex_cli_credentials_fn(codex_auth_path)
    if credential is None:
        return 1, "", False

    store = load_gaia_auth_store_fn(gaia_auth_store)
    profiles = store.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        store["profiles"] = profiles

    profile_id = profile_id_for_credential(provider, credential)
    profiles[profile_id] = credential
    save_gaia_auth_store_fn(gaia_auth_store, store)
    link_profile_fn(cfg_path, provider, profile_id, "gaia-local", gaia_auth_store)
    runtime_aligned = apply_oauth_runtime_defaults_fn(cfg_path, provider)
    return 0, profile_id, runtime_aligned


def read_linked_credential(
    active_profile: Dict[str, Any],
    load_gaia_auth_store_fn: Callable[[Path], Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], str]:
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
        profiles = load_gaia_auth_store_fn(store_path).get("profiles", {})
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


def linked_openai_oauth_access_token(
    cfg: Dict[str, Any],
    *,
    read_linked_credential_fn: ReadLinkedCredentialFn,
    is_expired_fn: IsExpiredFn,
) -> Tuple[str, str]:
    auth_cfg = cfg.get("auth", {})
    auth_cfg = auth_cfg if isinstance(auth_cfg, dict) else {}
    active_profile = auth_cfg.get("active_profile")
    if not isinstance(active_profile, dict):
        return "", "no linked OAuth profile in launcher config"

    provider = str(active_profile.get("provider", "")).strip().lower()
    if provider != "openai-codex":
        return "", "linked profile is not openai-codex"

    credential, error = read_linked_credential_fn(active_profile)
    if credential is None:
        return "", error
    if is_expired_fn(credential):
        return "", "linked OAuth profile is expired"

    access_token = str(credential.get("access", "")).strip()
    if not access_token:
        return "", "linked OAuth profile access token is missing"
    return access_token, ""


def provider_runtime_dependency_issue(provider: str, env: Dict[str, str]) -> Optional[str]:
    normalized = str(provider).strip().lower()
    if normalized == "anthropic":
        if importlib.util.find_spec("anthropic") is None:
            return "anthropic-package"
        if not env.get("ANTHROPIC_API_KEY", "").strip():
            return "anthropic-key"
        return None
    if normalized == "openai":
        if not env.get("OPENAI_API_KEY", "").strip():
            return "openai-key"
        return None
    if normalized == "openrouter":
        if not env.get("OPENROUTER_API_KEY", "").strip():
            return "openrouter-key"
        return None
    return "unsupported-provider"
