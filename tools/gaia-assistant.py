#!/usr/bin/env python3
"""Standalone Gaia personal assistant launcher.

This wrapper makes it easier for users to run Gaia's dual-track evolution loop
as a standalone personal assistant runtime.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import html
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import gaia_assistant_onboarding as onboarding
from gaia_assistant_parser import build_parser as build_modular_parser
from typing import Any, Dict, List, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_HOME = Path(os.environ.get("GAIA_ASSISTANT_HOME", str(Path.home() / ".gaia-assistant"))).expanduser()
DEFAULT_STATE_DIR = DEFAULT_HOME / "state"
DEFAULT_DATA_DIR = DEFAULT_HOME / "data"
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
ONBOARD_PROVIDER_CHOICES = onboarding.ONBOARD_PROVIDER_CHOICES
PROFILE_VERBOSITY_CHOICES = ("concise", "balanced", "detailed")
PROFILE_PROVIDER_CHOICES = onboarding.PROFILE_PROVIDER_CHOICES
AUTH_PROVIDER_CHOICES = onboarding.AUTH_PROVIDER_CHOICES
AUTH_SOURCE_CHOICES = onboarding.AUTH_SOURCE_CHOICES
RUNTIME_REASONING_PROVIDER_CHOICES = ("anthropic", "openai", "openrouter")
RESPONSE_PROFILE_CHOICES = ("auto", "concise", "balanced", "detailed")
RESPONSE_PROFILE_DEFAULT = "balanced"
RESPONSE_PROFILE_SYSTEM_PROMPTS: Dict[str, str] = {
    "concise": (
        "Response profile: concise. Keep replies compact and actionable. "
        "Use short bullets when useful and avoid filler."
    ),
    "balanced": (
        "Response profile: balanced. Provide clear practical detail with concise reasoning "
        "and direct next steps."
    ),
    "detailed": (
        "Response profile: detailed. Provide thorough context, explicit assumptions, and "
        "step-by-step guidance when relevant."
    ),
}
PERMISSION_LEVEL_CHOICES = ("safe", "confirm", "forbidden")
DEFAULT_SESSION_CONTEXT_TURNS = 20
SCHEDULE_STATUS_CHOICES = ("active", "paused", "canceled", "completed", "failed")
SCHEDULE_MUTABLE_STATUS_CHOICES = ("active", "paused", "canceled")
SCHEDULE_DEFAULT_WINDOW_MINUTES = 10
REMINDER_DEFAULT_CADENCE_MINUTES = 24 * 60
REMINDER_DEFAULT_WINDOW_MINUTES = 30
SKILL_CONTRACT_SCHEMA_VERSION = 1
SKILL_SOURCE_CHOICES = ("project", "local", "all")
SKILL_PROVENANCE_MODE_CHOICES = ("off", "warn", "enforce")
SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_DEFAULT = 7
SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MIN = 0
SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MAX = 10
SKILL_VALIDATION_REPORT_SCHEMA_VERSION = 1
SKILL_VALIDATION_SEVERITY_ORDER = ("info", "warn", "high", "critical")
SKILL_VALIDATION_BLOCKING_SEVERITIES = {"high", "critical"}
SKILL_VALIDATION_MAX_SCAN_FILES = 120
SKILL_VALIDATION_MAX_SCAN_FILE_BYTES = 512 * 1024
SKILL_VALIDATION_MAX_HITS_PER_RULE = 8
SKILL_VALIDATION_MAX_CANONICAL_CANDIDATES = 80
SKILL_VALIDATION_MAX_BASE64_CANDIDATES = 24
SKILL_VALIDATION_MAX_BASE64_TOKEN_CHARS = 4096
SANDBOX_PROFILE_CHOICES = ("read-only", "workspace-write")
SANDBOX_DEFAULT_PROFILE = "read-only"
POLICY_DECISION_CHOICES = ("allow", "confirm", "deny")
POLICY_RISK_CHOICES = ("low", "medium", "high", "critical")
POLICY_SOURCE_CHOICES = ("project", "local", "path", "unknown")
POLICY_SCOPE_CHOICES = ("standard", "restricted", "admin")
POLICY_DEFAULT_SCOPE = "standard"
DEFAULT_CAPABILITY_LEVELS = {
    "file_read": "safe",
    "file_write": "safe",
    "memory_read": "safe",
    "memory_write": "safe",
    "memory_delete": "safe",
    "memory_export": "confirm",
    "network_request": "safe",
    "shell_exec": "confirm",
    "delete_files": "confirm",
    "send_email": "forbidden",
    "external_messaging": "forbidden",
}
POLICY_TOOL_CHOICES = tuple(sorted(DEFAULT_CAPABILITY_LEVELS.keys()))
AUTOPILOT_STEP_CAPABILITY = {
    "capture_note": "file_write",
    "list_tasks": "file_read",
}
AUTOPILOT_PROFILES: Dict[str, Dict[str, Any]] = {
    "safe-daily": {
        "description": "Low-risk recurring assistant maintenance run",
        "allowed_capabilities": ["file_read", "file_write"],
        "steps": [
            {
                "id": "capture_daily_note",
                "action": "capture_note",
                "text": "Autopilot safe-daily checkpoint",
            },
            {
                "id": "list_open_tasks",
                "action": "list_tasks",
                "status": "open",
            },
        ],
    }
}
PROFILE_KEY_MAP = {
    "name": ("profile", "name"),
    "timezone": ("profile", "timezone"),
    "verbosity": ("profile", "verbosity"),
    "provider": ("profile", "default_provider"),
    "default_provider": ("profile", "default_provider"),
    "response_profile": ("profile", "response_profile"),
    "response-style": ("profile", "response_profile"),
    "style": ("profile", "response_profile"),
    "signals_enabled": ("signals", "enabled"),
    "signal_collection": ("signals", "enabled"),
    "signals_retention_days": ("signals", "retention_days"),
    "signals_max_records": ("signals", "max_records"),
    "skills_provenance_mode": ("skills", "provenance_mode"),
    "skills_attestation_mode": ("skills", "attestation_mode"),
    "skills_source_health_mode": ("skills", "source_health_mode"),
    "skills_source_health_min_score": ("skills", "source_health_min_score"),
}

MEMORY_STORE_SCHEMA_VERSION = 1
MEMORY_TYPE_CHOICES = ("session_short", "user_long", "project", "safety_audit")
MEMORY_CONSENT_SCOPE_CHOICES = ("session", "user", "project", "audit")
MEMORY_LIST_DEFAULT_LIMIT = 20
MEMORY_LIST_MAX_LIMIT = 200
MEMORY_RETENTION_TTL_RE = re.compile(r"^P([0-9]{1,4})D$")
FEEDBACK_SCHEMA_VERSION = 1
FEEDBACK_LABEL_CHOICES = ("helpful", "not-helpful")
FEEDBACK_LIST_DEFAULT_LIMIT = 20
FEEDBACK_LIST_MAX_LIMIT = 200
FEEDBACK_CORRECTION_MAX_CHARS = 2000
FEEDBACK_MAX_RECORDS = 500
SIGNALS_SCHEMA_VERSION = 1
SIGNALS_LEDGER_SCHEMA_VERSION = 1
SIGNALS_TRIAGE_SCHEMA_VERSION = 1
SIGNALS_TRIAGE_LEDGER_SCHEMA_VERSION = 1
SIGNALS_TYPE_CHOICES = (
    "feedback_not_helpful",
    "feedback_correction_pattern",
    "command_failure",
)
SIGNALS_TRIAGE_CLASS_CHOICES = (
    "existing-skill-enable",
    "skill-import-candidate",
    "core-feature-gap",
    "out-of-scope-or-rejected",
)
SIGNALS_LIST_DEFAULT_LIMIT = 20
SIGNALS_LIST_MAX_LIMIT = 200
SIGNALS_RETENTION_DAYS_DEFAULT = 90
SIGNALS_RETENTION_DAYS_MIN = 1
SIGNALS_RETENTION_DAYS_MAX = 3650
SIGNALS_MAX_RECORDS_DEFAULT = 300
SIGNALS_MAX_RECORDS_MIN = 1
SIGNALS_MAX_RECORDS_MAX = 2000
SIGNALS_MAX_EVENT_IDS_PER_SIGNAL = 50
SIGNALS_CORRECTION_TAG_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "response_style.concise": (
        "concise",
        "too long",
        "shorter",
        "brief",
        "less words",
        "trim",
    ),
    "response_style.detailed": (
        "more detail",
        "deeper",
        "step by step",
        "thorough",
        "expand",
        "more context",
    ),
    "response_style.actionable": (
        "actionable",
        "next steps",
        "clear actions",
        "practical",
        "specific",
    ),
    "intent.missing_capability": (
        "can't",
        "cannot",
        "missing",
        "not available",
        "unsupported",
        "doesn't support",
    ),
}
SIGNALS_TRIAGE_DANGEROUS_MARKERS: Tuple[str, ...] = (
    "reverse_shell",
    "prompt_injection",
    "prompt-injection",
    "jailbreak",
    "bypass",
    "exfiltration",
    "delete_files",
    "send_email",
    "external_messaging",
)
SIGNALS_TRIAGE_CORE_PREFIXES: Tuple[str, ...] = (
    "response_style.",
    "response_quality.",
    "memory.",
)
SIGNALS_TRIAGE_SKILLISH_PREFIXES: Tuple[str, ...] = (
    "skills.",
    "sandbox.",
    "policy.",
    "capability.",
    "auth.",
    "command.",
)
MEMORY_POLICY_RULES: Dict[str, Dict[str, int | str]] = {
    "session_short": {
        "consent_scope": "session",
        "default_retention_days": 7,
        "max_retention_days": 30,
    },
    "user_long": {
        "consent_scope": "user",
        "default_retention_days": 180,
        "max_retention_days": 730,
    },
    "project": {
        "consent_scope": "project",
        "default_retention_days": 365,
        "max_retention_days": 1095,
    },
    "safety_audit": {
        "consent_scope": "audit",
        "default_retention_days": 365,
        "max_retention_days": 3650,
    },
}


DEFAULT_CONFIG: Dict[str, Any] = {
    "runtime": {
        "mode": "continuous",
        "interval_minutes": 60,
    },
    "reasoning": {
        "provider": "anthropic",
        "model": DEFAULT_ANTHROPIC_MODEL,
        "explicit_provider_override": False,
    },
    "secrets": {
        "store_path": str(DEFAULT_SECRET_STORE),
    },
    "auth": {
        "providers": {
            name: dict(provider_cfg)
            for name, provider_cfg in onboarding.AUTH_PROVIDER_DEFAULTS.items()
        }
    },
    "tracks": {
        "default": "auto",
    },
    "profile": {
        "name": "",
        "timezone": "UTC",
        "verbosity": "balanced",
        "default_provider": "anthropic",
        "response_profile": RESPONSE_PROFILE_DEFAULT,
    },
    "capabilities": {
        "overrides": {},
    },
    "traces": {
        "dir": str(DEFAULT_HOME / "traces"),
    },
    "sessions": {
        "dir": str(DEFAULT_HOME / "sessions"),
        "max_context_turns": DEFAULT_SESSION_CONTEXT_TURNS,
    },
    "storage": {
        "dir": str(DEFAULT_DATA_DIR),
    },
    "signals": {
        "enabled": True,
        "retention_days": SIGNALS_RETENTION_DAYS_DEFAULT,
        "max_records": SIGNALS_MAX_RECORDS_DEFAULT,
    },
    "skills": {
        "local_dir": str(DEFAULT_HOME / "skills"),
        "provenance_mode": "warn",
        "attestation_mode": "warn",
        "source_health_mode": "warn",
        "source_health_min_score": SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_DEFAULT,
    },
    "sandbox": {
        "default_profile": SANDBOX_DEFAULT_PROFILE,
        "allow_network": False,
    },
    "policy": {
        "default_scope": POLICY_DEFAULT_SCOPE,
        "source_effect": {
            "project": "allow",
            "local": "confirm",
            "path": "deny",
            "unknown": "allow",
        },
        "tool_risk": {
            "file_read": "low",
            "file_write": "medium",
            "memory_read": "low",
            "memory_write": "medium",
            "memory_delete": "high",
            "memory_export": "high",
            "network_request": "high",
            "shell_exec": "high",
            "delete_files": "critical",
            "send_email": "critical",
            "external_messaging": "critical",
        },
        "scope_max_risk": {
            "standard": "high",
            "restricted": "medium",
            "admin": "critical",
        },
        "skill_tool_allowlists": {},
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


def _normalize_bool_default(value: Any, default_value: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    token = str(value).strip().lower()
    if token in ("1", "true", "yes", "on", "enabled"):
        return True
    if token in ("0", "false", "no", "off", "disabled"):
        return False
    return default_value


def _normalize_int_default(
    value: Any,
    *,
    default_value: int,
    min_value: int,
    max_value: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default_value
    return min(max(parsed, min_value), max_value)


def _normalize_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg: Dict[str, Any] = payload if isinstance(payload, dict) else {}

    runtime = cfg.setdefault("runtime", {})
    runtime.setdefault("mode", "continuous")
    runtime.setdefault("interval_minutes", 60)

    reasoning = cfg.setdefault("reasoning", {})
    reasoning.setdefault("provider", "anthropic")
    reasoning.setdefault("model", DEFAULT_ANTHROPIC_MODEL)
    reasoning["explicit_provider_override"] = _normalize_bool_default(
        reasoning.get("explicit_provider_override", False),
        False,
    )

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

    profile = cfg.setdefault("profile", {})
    profile.setdefault("name", "")
    profile.setdefault("timezone", "UTC")
    profile.setdefault("verbosity", "balanced")
    profile.setdefault("default_provider", "anthropic")
    profile.setdefault("response_profile", RESPONSE_PROFILE_DEFAULT)

    verbosity = str(profile.get("verbosity", "")).strip().lower()
    if verbosity not in PROFILE_VERBOSITY_CHOICES:
        profile["verbosity"] = "balanced"

    default_provider = str(profile.get("default_provider", "")).strip().lower()
    if default_provider not in PROFILE_PROVIDER_CHOICES:
        profile["default_provider"] = "anthropic"

    response_profile = str(profile.get("response_profile", "")).strip().lower()
    if response_profile not in RESPONSE_PROFILE_CHOICES:
        profile["response_profile"] = RESPONSE_PROFILE_DEFAULT

    capabilities = cfg.setdefault("capabilities", {})
    overrides = capabilities.setdefault("overrides", {})
    if not isinstance(overrides, dict):
        capabilities["overrides"] = {}

    traces = cfg.setdefault("traces", {})
    traces_dir = str(traces.get("dir", "")).strip()
    if not traces_dir:
        traces["dir"] = str(DEFAULT_HOME / "traces")

    sessions = cfg.setdefault("sessions", {})
    sessions_dir = str(sessions.get("dir", "")).strip()
    if not sessions_dir:
        sessions["dir"] = str(DEFAULT_HOME / "sessions")
    max_context = sessions.get("max_context_turns", DEFAULT_SESSION_CONTEXT_TURNS)
    if not isinstance(max_context, int) or max_context < 2:
        sessions["max_context_turns"] = DEFAULT_SESSION_CONTEXT_TURNS

    storage = cfg.setdefault("storage", {})
    storage_dir = str(storage.get("dir", "")).strip()
    if not storage_dir:
        storage["dir"] = str(DEFAULT_DATA_DIR)

    signals = cfg.setdefault("signals", {})
    if not isinstance(signals, dict):
        signals = {}
        cfg["signals"] = signals
    signals["enabled"] = _normalize_bool_default(signals.get("enabled", True), True)
    signals["retention_days"] = _normalize_int_default(
        signals.get("retention_days", SIGNALS_RETENTION_DAYS_DEFAULT),
        default_value=SIGNALS_RETENTION_DAYS_DEFAULT,
        min_value=SIGNALS_RETENTION_DAYS_MIN,
        max_value=SIGNALS_RETENTION_DAYS_MAX,
    )
    signals["max_records"] = _normalize_int_default(
        signals.get("max_records", SIGNALS_MAX_RECORDS_DEFAULT),
        default_value=SIGNALS_MAX_RECORDS_DEFAULT,
        min_value=SIGNALS_MAX_RECORDS_MIN,
        max_value=SIGNALS_MAX_RECORDS_MAX,
    )

    skills = cfg.setdefault("skills", {})
    local_skills_dir = str(skills.get("local_dir", "")).strip()
    if not local_skills_dir:
        skills["local_dir"] = str(DEFAULT_HOME / "skills")
    default_skills = DEFAULT_CONFIG.get("skills", {})
    provenance_mode = str(skills.get("provenance_mode", default_skills.get("provenance_mode", "warn"))).strip().lower()
    if provenance_mode not in SKILL_PROVENANCE_MODE_CHOICES:
        provenance_mode = "warn"
    skills["provenance_mode"] = provenance_mode
    attestation_mode = str(skills.get("attestation_mode", default_skills.get("attestation_mode", "warn"))).strip().lower()
    if attestation_mode not in SKILL_PROVENANCE_MODE_CHOICES:
        attestation_mode = "warn"
    skills["attestation_mode"] = attestation_mode
    source_health_mode = str(
        skills.get("source_health_mode", default_skills.get("source_health_mode", "warn"))
    ).strip().lower()
    if source_health_mode not in SKILL_PROVENANCE_MODE_CHOICES:
        source_health_mode = "warn"
    skills["source_health_mode"] = source_health_mode
    skills["source_health_min_score"] = _normalize_int_default(
        skills.get(
            "source_health_min_score",
            default_skills.get(
                "source_health_min_score",
                SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_DEFAULT,
            ),
        ),
        default_value=SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_DEFAULT,
        min_value=SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MIN,
        max_value=SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MAX,
    )

    sandbox = cfg.setdefault("sandbox", {})
    default_profile = str(sandbox.get("default_profile", SANDBOX_DEFAULT_PROFILE)).strip().lower()
    if default_profile not in SANDBOX_PROFILE_CHOICES:
        default_profile = SANDBOX_DEFAULT_PROFILE
    sandbox["default_profile"] = default_profile
    sandbox_allow_network = sandbox.get("allow_network", False)
    sandbox["allow_network"] = bool(sandbox_allow_network)

    policy = cfg.setdefault("policy", {})
    if not isinstance(policy, dict):
        policy = {}
        cfg["policy"] = policy

    default_policy = DEFAULT_CONFIG.get("policy", {})
    default_scope = str(policy.get("default_scope", default_policy.get("default_scope", POLICY_DEFAULT_SCOPE))).strip().lower()
    if default_scope not in POLICY_SCOPE_CHOICES:
        default_scope = POLICY_DEFAULT_SCOPE
    policy["default_scope"] = default_scope

    source_effect = policy.get("source_effect", {})
    if not isinstance(source_effect, dict):
        source_effect = {}
    normalized_source_effect: Dict[str, str] = {}
    default_source_effect = default_policy.get("source_effect", {})
    for source in POLICY_SOURCE_CHOICES:
        raw = source_effect.get(source, default_source_effect.get(source, "allow"))
        effect = str(raw).strip().lower()
        if effect not in POLICY_DECISION_CHOICES:
            effect = "allow"
        normalized_source_effect[source] = effect
    policy["source_effect"] = normalized_source_effect

    tool_risk = policy.get("tool_risk", {})
    if not isinstance(tool_risk, dict):
        tool_risk = {}
    normalized_tool_risk: Dict[str, str] = {}
    default_tool_risk = default_policy.get("tool_risk", {})
    for tool in POLICY_TOOL_CHOICES:
        raw = tool_risk.get(tool, default_tool_risk.get(tool, "medium"))
        risk = str(raw).strip().lower()
        if risk not in POLICY_RISK_CHOICES:
            risk = "medium"
        normalized_tool_risk[tool] = risk
    policy["tool_risk"] = normalized_tool_risk

    scope_max_risk = policy.get("scope_max_risk", {})
    if not isinstance(scope_max_risk, dict):
        scope_max_risk = {}
    normalized_scope_max: Dict[str, str] = {}
    default_scope_max = default_policy.get("scope_max_risk", {})
    for scope in POLICY_SCOPE_CHOICES:
        raw = scope_max_risk.get(scope, default_scope_max.get(scope, "high"))
        risk = str(raw).strip().lower()
        if risk not in POLICY_RISK_CHOICES:
            risk = "high"
        normalized_scope_max[scope] = risk
    policy["scope_max_risk"] = normalized_scope_max

    allowlists = policy.get("skill_tool_allowlists", {})
    if not isinstance(allowlists, dict):
        allowlists = {}
    normalized_allowlists: Dict[str, List[str]] = {}
    for raw_skill_id, raw_tools in allowlists.items():
        skill_id = str(raw_skill_id).strip()
        if not skill_id:
            continue
        tools: List[str] = []
        if isinstance(raw_tools, str):
            tools = [item.strip().lower() for item in raw_tools.split(",") if item.strip()]
        elif isinstance(raw_tools, list):
            tools = [str(item).strip().lower() for item in raw_tools if str(item).strip()]
        deduped: List[str] = []
        seen: set[str] = set()
        for tool in tools:
            if tool not in POLICY_TOOL_CHOICES or tool in seen:
                continue
            seen.add(tool)
            deduped.append(tool)
        if deduped:
            normalized_allowlists[skill_id] = deduped
    policy["skill_tool_allowlists"] = normalized_allowlists

    return cfg


def _config_path_for_key(key: str) -> Optional[Tuple[str, str]]:
    return PROFILE_KEY_MAP.get(key.strip().lower())


def _get_nested_value(cfg: Dict[str, Any], path: Tuple[str, str]) -> Any:
    section, field = path
    section_value = cfg.get(section, {})
    if not isinstance(section_value, dict):
        return None
    return section_value.get(field)


def _set_nested_value(cfg: Dict[str, Any], path: Tuple[str, str], value: Any) -> None:
    section, field = path
    section_value = cfg.setdefault(section, {})
    if not isinstance(section_value, dict):
        section_value = {}
        cfg[section] = section_value
    section_value[field] = value


def _normalize_config_value(key: str, value: str) -> Tuple[Optional[Any], Optional[str]]:
    canonical_key = key.strip().lower()
    raw = value.strip()
    if canonical_key == "verbosity":
        normalized = raw.lower()
        if normalized not in PROFILE_VERBOSITY_CHOICES:
            return None, (
                f"Invalid verbosity '{value}'. "
                f"Expected one of: {', '.join(PROFILE_VERBOSITY_CHOICES)}."
            )
        return normalized, None
    if canonical_key in ("provider", "default_provider"):
        normalized = raw.lower()
        if normalized not in PROFILE_PROVIDER_CHOICES:
            return None, (
                f"Invalid provider '{value}'. "
                f"Expected one of: {', '.join(PROFILE_PROVIDER_CHOICES)}."
            )
        return normalized, None
    if canonical_key in ("response_profile", "response-style", "style"):
        normalized = raw.lower().replace("_", "-")
        normalized = re.sub(r"\s+", "-", normalized)
        if normalized not in RESPONSE_PROFILE_CHOICES:
            return None, (
                f"Invalid response profile '{value}'. "
                f"Expected one of: {', '.join(RESPONSE_PROFILE_CHOICES)}."
            )
        return normalized, None
    if canonical_key == "timezone":
        if not raw:
            return None, "timezone cannot be empty."
        return raw, None
    if canonical_key == "name":
        return raw, None
    if canonical_key in ("signals_enabled", "signal_collection"):
        token = raw.lower()
        if token in ("1", "true", "yes", "on", "enabled"):
            return True, None
        if token in ("0", "false", "no", "off", "disabled"):
            return False, None
        return None, "Invalid signals_enabled value. Expected true/false."
    if canonical_key == "signals_retention_days":
        try:
            days = int(raw)
        except ValueError:
            return None, "Invalid signals_retention_days value. Expected an integer."
        if days < SIGNALS_RETENTION_DAYS_MIN or days > SIGNALS_RETENTION_DAYS_MAX:
            return None, (
                "Invalid signals_retention_days value. "
                f"Expected {SIGNALS_RETENTION_DAYS_MIN}..{SIGNALS_RETENTION_DAYS_MAX}."
            )
        return days, None
    if canonical_key == "signals_max_records":
        try:
            count = int(raw)
        except ValueError:
            return None, "Invalid signals_max_records value. Expected an integer."
        if count < SIGNALS_MAX_RECORDS_MIN or count > SIGNALS_MAX_RECORDS_MAX:
            return None, (
                "Invalid signals_max_records value. "
                f"Expected {SIGNALS_MAX_RECORDS_MIN}..{SIGNALS_MAX_RECORDS_MAX}."
            )
        return count, None
    if canonical_key in ("skills_provenance_mode", "skills_attestation_mode", "skills_source_health_mode"):
        normalized = raw.lower()
        if normalized not in SKILL_PROVENANCE_MODE_CHOICES:
            return None, (
                f"Invalid {canonical_key} value '{value}'. "
                f"Expected one of: {', '.join(SKILL_PROVENANCE_MODE_CHOICES)}."
            )
        return normalized, None
    if canonical_key == "skills_source_health_min_score":
        try:
            score = int(raw)
        except ValueError:
            return None, "Invalid skills_source_health_min_score value. Expected an integer."
        if (
            score < SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MIN
            or score > SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MAX
        ):
            return None, (
                "Invalid skills_source_health_min_score value. "
                f"Expected {SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MIN}.."
                f"{SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MAX}."
            )
        return score, None
    return None, f"Unsupported key: {key}"


def _resolve_trace_dir(cfg: Dict[str, Any], override_path: Optional[str] = None) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    traces = cfg.get("traces", {})
    if isinstance(traces, dict):
        configured = str(traces.get("dir", "")).strip()
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_HOME / "traces"


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _summarize_text(value: Any, max_chars: int = 180) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _trace_action_path(trace_dir: Path) -> Path:
    return trace_dir / "actions.jsonl"


def _write_action_trace(
    trace_dir: Path,
    action_type: str,
    input_summary: str,
    output_summary: str,
    duration_ms: float,
    permission_level: str,
    status: str = "ok",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "input_summary": _summarize_text(input_summary),
        "output_summary": _summarize_text(output_summary),
        "duration_ms": round(max(duration_ms, 0.0), 3),
        "permission_level": permission_level,
        "status": status,
        "schema_version": 1,
    }
    if metadata:
        record["metadata"] = metadata
    _append_jsonl(_trace_action_path(trace_dir), record)
    return record


def _read_action_traces(trace_dir: Path) -> List[Dict[str, Any]]:
    path = _trace_action_path(trace_dir)
    if not path.exists():
        return []
    traces: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            traces.append(payload)
    return traces


def _trace_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = item.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _with_trace_metadata(
    metadata: Optional[Dict[str, Any]] = None,
    *,
    correlation_id: Optional[str] = None,
    skill_id: Optional[str] = None,
    skill_source: Optional[str] = None,
    policy_decision: Optional[str] = None,
    policy_id: Optional[str] = None,
    sandbox_profile: Optional[str] = None,
    sandbox_network_mode: Optional[str] = None,
    sandbox_escalated: Optional[bool] = None,
    sandbox_approved: Optional[bool] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = dict(metadata) if isinstance(metadata, dict) else {}
    payload["trace_schema_version"] = 2
    if correlation_id:
        payload["correlation_id"] = str(correlation_id).strip()
    if skill_id:
        payload["skill_id"] = str(skill_id).strip()
    if skill_source:
        payload["skill_source"] = str(skill_source).strip().lower()
    if policy_decision:
        payload["policy_decision"] = str(policy_decision).strip().lower()
    if policy_id:
        payload["policy_id"] = str(policy_id).strip()
    if sandbox_profile:
        payload["sandbox_profile"] = str(sandbox_profile).strip().lower()
    if sandbox_network_mode:
        payload["sandbox_network_mode"] = str(sandbox_network_mode).strip().lower()
    if isinstance(sandbox_escalated, bool):
        payload["sandbox_escalated"] = sandbox_escalated
    if isinstance(sandbox_approved, bool):
        payload["sandbox_approved"] = sandbox_approved
    return payload


def _trace_skill_id(item: Dict[str, Any]) -> str:
    metadata = _trace_metadata(item)
    return str(metadata.get("skill_id", "")).strip()


def _trace_skill_source(item: Dict[str, Any]) -> str:
    metadata = _trace_metadata(item)
    value = str(metadata.get("skill_source", metadata.get("source", ""))).strip().lower()
    return value


def _trace_policy_decision(item: Dict[str, Any]) -> str:
    metadata = _trace_metadata(item)
    value: Any = metadata.get("policy_decision")
    if isinstance(value, dict):
        value = value.get("decision")
    if not value and isinstance(metadata.get("decision"), dict):
        value = metadata.get("decision", {}).get("decision")
    normalized = str(value or "").strip().lower()
    if normalized in POLICY_DECISION_CHOICES:
        return normalized
    return ""


def _trace_sandbox_profile(item: Dict[str, Any]) -> str:
    metadata = _trace_metadata(item)
    value = str(metadata.get("sandbox_profile", metadata.get("profile", ""))).strip().lower()
    if value in SANDBOX_PROFILE_CHOICES:
        return value
    return ""


def _trace_correlation_id(item: Dict[str, Any]) -> str:
    metadata = _trace_metadata(item)
    return str(metadata.get("correlation_id", "")).strip()


def _capability_registry(cfg: Dict[str, Any]) -> Dict[str, str]:
    registry = dict(DEFAULT_CAPABILITY_LEVELS)
    capabilities = cfg.get("capabilities", {})
    overrides = {}
    if isinstance(capabilities, dict):
        raw_overrides = capabilities.get("overrides", {})
        if isinstance(raw_overrides, dict):
            overrides = raw_overrides
    for capability, level in overrides.items():
        normalized_level = str(level).strip().lower()
        if normalized_level in PERMISSION_LEVEL_CHOICES:
            registry[str(capability).strip()] = normalized_level
    return registry


def _permission_for_capability(cfg: Dict[str, Any], capability: str) -> str:
    registry = _capability_registry(cfg)
    return registry.get(capability, "confirm")


def _check_capability_permission(
    cfg: Dict[str, Any],
    capability: str,
    user_prompt: Optional[str],
    non_interactive: bool,
) -> Tuple[bool, str, str]:
    level = _permission_for_capability(cfg, capability)
    if level == "safe":
        return True, level, "allowed"
    if level == "forbidden":
        return False, level, f"blocked by policy for capability '{capability}'"

    prompt = user_prompt or f"Capability '{capability}' requires confirmation. Continue?"
    allowed = _prompt_yes_no(prompt, default=False, non_interactive=non_interactive)
    if allowed:
        return True, level, "allowed after confirmation"
    return False, level, "user denied confirmation"


class ProviderError(RuntimeError):
    """Raised when the configured reasoning provider call fails."""


class ProviderTokenLimitError(ProviderError):
    """Raised when provider rejects a request due to context/token limits."""


def _resolve_session_dir(cfg: Dict[str, Any], override_path: Optional[str] = None) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    sessions = cfg.get("sessions", {})
    if isinstance(sessions, dict):
        configured = str(sessions.get("dir", "")).strip()
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_HOME / "sessions"


def _resolve_storage_dir(cfg: Dict[str, Any], override_path: Optional[str] = None) -> Path:
    if override_path:
        return Path(override_path).expanduser()
    storage = cfg.get("storage", {})
    if isinstance(storage, dict):
        configured = str(storage.get("dir", "")).strip()
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_DATA_DIR


def _load_records(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    if not payload:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get("items", [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _save_records(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def _notes_path(storage_dir: Path) -> Path:
    return storage_dir / "notes.json"


def _tasks_path(storage_dir: Path) -> Path:
    return storage_dir / "tasks.json"


def _feedback_path(storage_dir: Path) -> Path:
    return storage_dir / "feedback.json"


def _summaries_path(storage_dir: Path) -> Path:
    return storage_dir / "summaries.json"


def _plans_path(storage_dir: Path) -> Path:
    return storage_dir / "plans.json"


def _schedules_path(storage_dir: Path) -> Path:
    return storage_dir / "schedules.json"


def _schedule_runs_path(storage_dir: Path) -> Path:
    return storage_dir / "schedule-runs.jsonl"


def _reminder_events_path(storage_dir: Path) -> Path:
    return storage_dir / "reminder-events.jsonl"


def _memory_tombstones_path(storage_dir: Path) -> Path:
    return storage_dir / "memory-tombstones.jsonl"


def _memory_export_events_path(storage_dir: Path) -> Path:
    return storage_dir / "memory-export-events.jsonl"


def _memory_summary_events_path(storage_dir: Path) -> Path:
    return storage_dir / "memory-summary-events.jsonl"


def _signals_path(storage_dir: Path) -> Path:
    return storage_dir / "unmet-intent-signals.json"


def _signals_triage_path(storage_dir: Path) -> Path:
    return storage_dir / "unmet-intent-signal-triage.json"


def _signals_export_events_path(storage_dir: Path) -> Path:
    return storage_dir / "unmet-intent-signal-exports.jsonl"


def _autopilot_runs_path(trace_dir: Path) -> Path:
    return trace_dir / "autopilot-runs.jsonl"


def _autopilot_incidents_path(trace_dir: Path) -> Path:
    return trace_dir / "autopilot-incidents.jsonl"


def _snapshot_storage_state(storage_dir: Path) -> Dict[str, Dict[str, Any]]:
    snapshot: Dict[str, Dict[str, Any]] = {}
    for path in (
        _notes_path(storage_dir),
        _tasks_path(storage_dir),
        _summaries_path(storage_dir),
        _plans_path(storage_dir),
    ):
        key = str(path)
        if path.exists():
            snapshot[key] = {
                "exists": True,
                "content": path.read_text(encoding="utf-8"),
            }
        else:
            snapshot[key] = {
                "exists": False,
                "content": "",
            }
    return snapshot


def _restore_storage_state(snapshot: Dict[str, Dict[str, Any]]) -> Tuple[bool, str]:
    restored = 0
    for raw_path, payload in snapshot.items():
        path = Path(raw_path)
        expected_exists = bool(payload.get("exists", False))
        content = str(payload.get("content", ""))
        try:
            if expected_exists:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            else:
                path.unlink(missing_ok=True)
            restored += 1
        except OSError as exc:
            return False, f"rollback failed for {path}: {exc}"
    return True, f"restored {restored} file targets"


def _execute_autopilot_step(
    step: Dict[str, Any],
    storage_dir: Path,
) -> Dict[str, Any]:
    step_id = str(step.get("id", "")).strip() or _new_record_id("aps")
    action = str(step.get("action", "")).strip()

    if action == "capture_note":
        text = str(step.get("text", "")).strip()
        if not text:
            raise RuntimeError(f"autopilot step {step_id} missing text")
        path = _notes_path(storage_dir)
        items = _load_records(path)
        record = _create_note_record(text, source="autopilot")
        items.append(record)
        _save_records(path, items)
        return {
            "step_id": step_id,
            "action": action,
            "status": "ok",
            "result": f"captured note {record['id']}",
        }

    if action == "list_tasks":
        status = str(step.get("status", "open")).strip().lower()
        if status not in ("open", "done", "all"):
            status = "open"
        tasks = _load_records(_tasks_path(storage_dir))
        if status != "all":
            tasks = [
                item
                for item in tasks
                if str(item.get("status", "open")).strip().lower() == status
            ]
        return {
            "step_id": step_id,
            "action": action,
            "status": "ok",
            "result": f"{len(tasks)} tasks ({status})",
        }

    raise RuntimeError(f"unsupported autopilot action: {action}")


def _new_record_id(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}{timestamp}-{uuid.uuid4().hex[:6]}"


def _create_note_record(text: str, source: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": _new_record_id("n"),
        "text": text.strip(),
        "created_at": now,
        "updated_at": now,
        "source": source,
    }


def _create_task_record(text: str, source: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": _new_record_id("t"),
        "text": text.strip(),
        "status": "open",
        "created_at": now,
        "updated_at": now,
        "source": source,
    }


def _normalize_feedback_label(raw: str) -> str:
    value = str(raw).strip().lower()
    normalized = re.sub(r"\s+", "-", value.replace("_", "-"))
    if normalized == "nothelpful":
        normalized = "not-helpful"
    if normalized not in FEEDBACK_LABEL_CHOICES:
        raise ValueError(
            f"Invalid feedback label '{raw}'. "
            f"Expected one of: {', '.join(FEEDBACK_LABEL_CHOICES)}."
        )
    return normalized


def _feedback_label_display(label: str) -> str:
    normalized = str(label).strip().lower()
    if normalized == "not-helpful":
        return "not helpful"
    if normalized == "helpful":
        return "helpful"
    return normalized


def _sort_feedback_records(items: List[Dict[str, Any]], descending: bool) -> List[Dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (str(item.get("created_at", "")).strip(), str(item.get("id", "")).strip()),
        reverse=descending,
    )


def _trim_feedback_records(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(items) <= FEEDBACK_MAX_RECORDS:
        return items
    ordered = _sort_feedback_records(items, descending=False)
    return ordered[-FEEDBACK_MAX_RECORDS:]


def _parse_since_date(raw: str) -> Optional[datetime]:
    value = raw.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime_utc(raw: str, field_name: str) -> datetime:
    value = raw.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}. Use ISO-8601 (example: 2026-02-10T09:30:00Z).") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _memory_db_path(storage_dir: Path) -> Path:
    return storage_dir / "memory.db"


def _normalize_memory_type(raw: str) -> str:
    value = str(raw).strip().lower()
    if value not in MEMORY_TYPE_CHOICES:
        raise ValueError(
            f"Invalid memory type '{raw}'. "
            f"Expected one of: {', '.join(MEMORY_TYPE_CHOICES)}."
        )
    return value


def _normalize_memory_consent_scope(raw: str) -> str:
    value = str(raw).strip().lower()
    if value not in MEMORY_CONSENT_SCOPE_CHOICES:
        raise ValueError(
            f"Invalid consent scope '{raw}'. "
            f"Expected one of: {', '.join(MEMORY_CONSENT_SCOPE_CHOICES)}."
        )
    return value


def _parse_memory_score(raw: Optional[Any], field_name: str, default_value: float) -> float:
    if raw is None:
        return default_value
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number between 0 and 1.") from exc
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1.")
    return round(value, 6)


def _parse_retention_ttl_days(raw: str) -> Optional[int]:
    value = str(raw).strip().upper()
    if not value:
        return None
    match = MEMORY_RETENTION_TTL_RE.fullmatch(value)
    if match is None:
        raise ValueError("retention_ttl must use ISO-8601 day format PnD (example: P30D).")
    days = int(match.group(1))
    if days <= 0:
        raise ValueError("retention_ttl day count must be greater than zero.")
    return days


def _format_retention_ttl_days(days: int) -> str:
    return f"P{int(days)}D"


def _memory_policy_rule(memory_type: str) -> Dict[str, int | str]:
    normalized = _normalize_memory_type(memory_type)
    rule = MEMORY_POLICY_RULES.get(normalized, {})
    if not isinstance(rule, dict) or not rule:
        raise ValueError(f"Missing memory policy rule for memory_type '{memory_type}'.")
    return rule


def _default_memory_consent_scope(memory_type: str) -> str:
    rule = _memory_policy_rule(memory_type)
    scope = str(rule.get("consent_scope", "")).strip().lower()
    return _normalize_memory_consent_scope(scope)


def _enforce_memory_policy_contract(
    *,
    memory_type: str,
    consent_scope: str,
    retention_ttl: str,
) -> Dict[str, Any]:
    normalized_type = _normalize_memory_type(memory_type)
    normalized_scope = _normalize_memory_consent_scope(consent_scope)
    rule = _memory_policy_rule(normalized_type)

    required_scope = str(rule.get("consent_scope", "")).strip()
    if normalized_scope != required_scope:
        raise ValueError(
            f"consent_scope '{normalized_scope}' is not allowed for memory_type "
            f"'{normalized_type}'. Expected '{required_scope}'."
        )

    parsed_days = _parse_retention_ttl_days(retention_ttl)
    default_days = int(rule.get("default_retention_days", 30))
    max_days = int(rule.get("max_retention_days", default_days))
    if parsed_days is None:
        parsed_days = default_days
    if parsed_days > max_days:
        raise ValueError(
            f"retention_ttl '{retention_ttl or _format_retention_ttl_days(parsed_days)}' exceeds "
            f"max {max_days} days for memory_type '{normalized_type}'."
        )

    return {
        "memory_type": normalized_type,
        "consent_scope": required_scope,
        "retention_ttl": _format_retention_ttl_days(parsed_days),
        "retention_days": parsed_days,
        "max_retention_days": max_days,
    }


class MemoryStore:
    """Abstract memory store contract (memory.v1)."""

    def create(self, record: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def get(self, memory_id: str, include_deleted: bool = False, touch_access: bool = False) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def list(
        self,
        *,
        memory_type: Optional[str],
        subject_id: Optional[str],
        query: Optional[str],
        limit: int,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def update(self, memory_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def delete(self, memory_id: str) -> bool:
        raise NotImplementedError


class SQLiteMemoryStore(MemoryStore):
    """SQLite-backed memory.v1 store."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_records (
                    memory_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    source_trace_id TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    importance REAL NOT NULL DEFAULT 0.5,
                    retention_ttl TEXT NOT NULL DEFAULT '',
                    consent_scope TEXT NOT NULL DEFAULT 'session',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT,
                    last_accessed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_memory_subject_created
                    ON memory_records(subject_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memory_type_created
                    ON memory_records(memory_type, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memory_deleted
                    ON memory_records(deleted_at);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO memory_meta(key, value) VALUES (?, ?)",
                ("memory_store_schema_version", str(MEMORY_STORE_SCHEMA_VERSION)),
            )
            conn.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "memory_id": str(row["memory_id"]),
            "memory_type": str(row["memory_type"]),
            "subject_id": str(row["subject_id"]),
            "content": str(row["content"]),
            "summary": str(row["summary"]),
            "source_trace_id": str(row["source_trace_id"]),
            "confidence": float(row["confidence"]),
            "importance": float(row["importance"]),
            "retention_ttl": str(row["retention_ttl"]),
            "consent_scope": str(row["consent_scope"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "deleted_at": row["deleted_at"],
            "last_accessed_at": row["last_accessed_at"],
        }

    def create(self, record: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "memory_id": str(record.get("memory_id") or _new_record_id("m")),
            "memory_type": _normalize_memory_type(str(record.get("memory_type", ""))),
            "subject_id": str(record.get("subject_id", "")).strip(),
            "content": str(record.get("content", "")).strip(),
            "summary": str(record.get("summary", "")).strip(),
            "source_trace_id": str(record.get("source_trace_id", "")).strip(),
            "confidence": _parse_memory_score(record.get("confidence"), "confidence", 0.5),
            "importance": _parse_memory_score(record.get("importance"), "importance", 0.5),
            "retention_ttl": str(record.get("retention_ttl", "")).strip(),
            "consent_scope": _normalize_memory_consent_scope(str(record.get("consent_scope", "session"))),
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            "last_accessed_at": None,
        }
        if not payload["subject_id"]:
            raise ValueError("subject_id cannot be empty.")
        if not payload["content"]:
            raise ValueError("content cannot be empty.")
        policy_contract = _enforce_memory_policy_contract(
            memory_type=payload["memory_type"],
            consent_scope=payload["consent_scope"],
            retention_ttl=payload["retention_ttl"],
        )
        payload["memory_type"] = str(policy_contract["memory_type"])
        payload["consent_scope"] = str(policy_contract["consent_scope"])
        payload["retention_ttl"] = str(policy_contract["retention_ttl"])

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_records(
                    memory_id, memory_type, subject_id, content, summary,
                    source_trace_id, confidence, importance, retention_ttl,
                    consent_scope, created_at, updated_at, deleted_at, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["memory_id"],
                    payload["memory_type"],
                    payload["subject_id"],
                    payload["content"],
                    payload["summary"],
                    payload["source_trace_id"],
                    payload["confidence"],
                    payload["importance"],
                    payload["retention_ttl"],
                    payload["consent_scope"],
                    payload["created_at"],
                    payload["updated_at"],
                    payload["deleted_at"],
                    payload["last_accessed_at"],
                ),
            )
            conn.commit()
        return payload

    def get(self, memory_id: str, include_deleted: bool = False, touch_access: bool = False) -> Optional[Dict[str, Any]]:
        memory_id = str(memory_id).strip()
        if not memory_id:
            return None
        where_deleted = "" if include_deleted else "AND deleted_at IS NULL"
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT * FROM memory_records
                WHERE memory_id = ? {where_deleted}
                LIMIT 1
                """,
                (memory_id,),
            ).fetchone()
            if row is None:
                return None
            if touch_access:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE memory_records SET last_accessed_at = ?, updated_at = ? WHERE memory_id = ?",
                    (now, now, memory_id),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM memory_records WHERE memory_id = ? LIMIT 1",
                    (memory_id,),
                ).fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def list(
        self,
        *,
        memory_type: Optional[str],
        subject_id: Optional[str],
        query: Optional[str],
        limit: int,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if not include_deleted:
            clauses.append("deleted_at IS NULL")
        if memory_type:
            clauses.append("memory_type = ?")
            params.append(_normalize_memory_type(memory_type))
        if subject_id:
            clauses.append("subject_id = ?")
            params.append(str(subject_id).strip())
        if query:
            clauses.append("(content LIKE ? OR summary LIKE ?)")
            like_value = f"%{str(query).strip()}%"
            params.extend([like_value, like_value])

        if limit <= 0:
            limit = MEMORY_LIST_DEFAULT_LIMIT
        limit = min(limit, MEMORY_LIST_MAX_LIMIT)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM memory_records
                {where_sql}
                ORDER BY created_at DESC, memory_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def update(self, memory_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        memory_id = str(memory_id).strip()
        if not memory_id:
            return None
        allowed_fields = {
            "memory_type",
            "subject_id",
            "content",
            "summary",
            "source_trace_id",
            "confidence",
            "importance",
            "retention_ttl",
            "consent_scope",
        }
        with self._connect() as conn:
            existing_row = conn.execute(
                "SELECT * FROM memory_records WHERE memory_id = ? LIMIT 1",
                (memory_id,),
            ).fetchone()
            if existing_row is None:
                return None
            existing = self._row_to_record(existing_row)

            merged: Dict[str, Any] = dict(existing)
            for field in sorted(allowed_fields):
                if field not in updates or updates[field] is None:
                    continue
                value: Any = updates[field]
                if field == "memory_type":
                    value = _normalize_memory_type(str(value))
                elif field == "consent_scope":
                    value = _normalize_memory_consent_scope(str(value))
                elif field in ("confidence", "importance"):
                    value = _parse_memory_score(value, field, 0.5)
                else:
                    value = str(value).strip()
                    if field in ("subject_id", "content") and not value:
                        raise ValueError(f"{field} cannot be empty.")
                merged[field] = value

            policy_contract = _enforce_memory_policy_contract(
                memory_type=str(merged.get("memory_type", existing.get("memory_type", ""))),
                consent_scope=str(merged.get("consent_scope", existing.get("consent_scope", ""))),
                retention_ttl=str(merged.get("retention_ttl", existing.get("retention_ttl", ""))),
            )
            merged["memory_type"] = str(policy_contract["memory_type"])
            merged["consent_scope"] = str(policy_contract["consent_scope"])
            merged["retention_ttl"] = str(policy_contract["retention_ttl"])

            set_clauses: List[str] = []
            params: List[Any] = []
            for field in sorted(allowed_fields):
                if merged.get(field) == existing.get(field):
                    continue
                set_clauses.append(f"{field} = ?")
                params.append(merged.get(field))

            if not set_clauses:
                return existing

            now = datetime.now(timezone.utc).isoformat()
            set_clauses.append("updated_at = ?")
            params.append(now)
            conn.execute(
                f"UPDATE memory_records SET {', '.join(set_clauses)} WHERE memory_id = ?",
                (*params, memory_id),
            )
            conn.commit()
        return self.get(memory_id, include_deleted=True, touch_access=False)

    def delete(self, memory_id: str) -> bool:
        memory_id = str(memory_id).strip()
        if not memory_id:
            return False
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT memory_id FROM memory_records WHERE memory_id = ? LIMIT 1",
                (memory_id,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                """
                UPDATE memory_records
                SET deleted_at = COALESCE(deleted_at, ?), updated_at = ?
                WHERE memory_id = ?
                """,
                (now, now, memory_id),
            )
            conn.commit()
        return True


def _memory_store(storage_dir: Path) -> MemoryStore:
    return SQLiteMemoryStore(_memory_db_path(storage_dir))


def _skills_local_root(cfg: Dict[str, Any]) -> Path:
    skills_cfg = cfg.get("skills", {})
    if isinstance(skills_cfg, dict):
        configured = str(skills_cfg.get("local_dir", "")).strip()
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_HOME / "skills"


def _approved_skill_roots(cfg: Dict[str, Any], source_filter: str) -> List[Tuple[str, Path]]:
    want = source_filter.strip().lower()
    if want not in SKILL_SOURCE_CHOICES:
        want = "all"

    roots: List[Tuple[str, Path]] = []
    if want in ("project", "all"):
        roots.append(("project", REPO_ROOT / "skills"))
    if want in ("local", "all"):
        roots.append(("local", _skills_local_root(cfg)))
    return roots


def _parse_skill_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_index: Optional[int] = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        return {}, text

    frontmatter: Dict[str, Any] = {}
    fm_lines = lines[1:end_index]
    i = 0
    while i < len(fm_lines):
        raw = fm_lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if ":" not in stripped:
            i += 1
            continue

        key_raw, value_raw = stripped.split(":", 1)
        key = key_raw.strip().lower()
        value = value_raw.strip()

        if key == "capabilities":
            if not value:
                items: List[str] = []
                j = i + 1
                while j < len(fm_lines):
                    item_raw = fm_lines[j].strip()
                    if not item_raw:
                        j += 1
                        continue
                    if item_raw.startswith("- "):
                        items.append(item_raw[2:].strip().strip("'\""))
                        j += 1
                        continue
                    break
                frontmatter[key] = items
                i = j
                continue
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                items = [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
                frontmatter[key] = items
            else:
                items = [item.strip().strip("'\"") for item in value.split(",") if item.strip()]
                frontmatter[key] = items
            i += 1
            continue

        frontmatter[key] = value.strip().strip("'\"")
        i += 1

    body = "\n".join(lines[end_index + 1 :])
    return frontmatter, body


def _normalize_skill_capabilities(raw: Any) -> List[str]:
    values: List[str] = []
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
    elif isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]

    normalized: List[str] = []
    seen: set[str] = set()
    for item in values:
        capability = item.lower()
        if capability in seen:
            continue
        seen.add(capability)
        normalized.append(capability)
    return normalized


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 128)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _display_skill_path(source: str, path: Path) -> str:
    if source == "project":
        try:
            return str(path.relative_to(REPO_ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _skill_slug_for_entry(source_root: Path, skill_path: Path, fallback_name: str) -> str:
    try:
        relative_dir = skill_path.parent.relative_to(source_root).as_posix()
    except ValueError:
        relative_dir = skill_path.parent.name
    slug = relative_dir if relative_dir and relative_dir != "." else fallback_name
    return slug.strip()


def _build_skill_contract(
    skill_path: Path,
    *,
    source: str,
    source_root: Path,
    cfg: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    try:
        text = skill_path.read_text(encoding="utf-8")
        stat = skill_path.stat()
    except OSError:
        return None

    frontmatter, _ = _parse_skill_frontmatter(text)
    declared_name = str(frontmatter.get("name", "")).strip() or skill_path.parent.name
    if not declared_name:
        return None
    description = str(frontmatter.get("description", "")).strip()
    capabilities = _normalize_skill_capabilities(frontmatter.get("capabilities"))
    skill_slug = _skill_slug_for_entry(source_root, skill_path, declared_name)
    skill_id = f"{source}:{skill_slug}"
    capability_policy = _capability_registry(cfg)

    return {
        "schema_version": SKILL_CONTRACT_SCHEMA_VERSION,
        "skill_id": skill_id,
        "slug": skill_slug,
        "name": declared_name,
        "description": description,
        "source": source,
        "source_root": _display_skill_path(source, source_root),
        "entrypoint": _display_skill_path(source, skill_path),
        "capabilities": capabilities,
        "capability_policy": [
            {
                "capability": capability,
                "policy_level": capability_policy.get(capability, "unmapped"),
            }
            for capability in capabilities
        ],
        "provenance": {
            "sha256": _sha256_file(skill_path),
            "last_modified_at": _isoformat_utc(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
        },
        "frontmatter": {
            "keys": sorted(frontmatter.keys()),
            "declares_capabilities": bool(capabilities),
        },
    }


def _load_skill_contracts(
    cfg: Dict[str, Any],
    *,
    source_filter: str = "all",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    contracts: List[Dict[str, Any]] = []
    scanned_roots: List[str] = []

    for source, source_root in _approved_skill_roots(cfg, source_filter):
        scanned_roots.append(f"{source}:{source_root}")
        if not source_root.exists() or not source_root.is_dir():
            continue
        for skill_path in sorted(source_root.rglob("SKILL.md")):
            if not skill_path.is_file():
                continue
            contract = _build_skill_contract(
                skill_path,
                source=source,
                source_root=source_root,
                cfg=cfg,
            )
            if contract is not None:
                contracts.append(contract)

    contracts.sort(
        key=lambda item: (
            str(item.get("source", "")),
            str(item.get("name", "")),
            str(item.get("entrypoint", "")),
        )
    )
    return contracts, scanned_roots


def _resolve_skill_contract(
    contracts: List[Dict[str, Any]],
    reference: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    ref = reference.strip()
    if not ref:
        return None, "skill reference cannot be empty"

    by_id = [item for item in contracts if str(item.get("skill_id", "")).strip() == ref]
    if len(by_id) == 1:
        return by_id[0], None

    by_name = [item for item in contracts if str(item.get("name", "")).strip() == ref]
    if len(by_name) == 1:
        return by_name[0], None
    if len(by_name) > 1:
        options = ", ".join(sorted(str(item.get("skill_id", "")) for item in by_name))
        return None, f"ambiguous skill name '{ref}'. Use one of: {options}"

    return None, f"skill not found: {ref}"


def _display_runtime_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except (OSError, ValueError):
        return str(path)


def _skill_validation_reports_dir(trace_dir: Path) -> Path:
    return trace_dir / "skill-validation-reports"


def _validation_severity_rank(value: str) -> int:
    try:
        return SKILL_VALIDATION_SEVERITY_ORDER.index(value)
    except ValueError:
        return -1


def _sorted_validation_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (
            _validation_severity_rank(str(item.get("severity", "")).strip().lower()),
            str(item.get("stage", "")).strip(),
            str(item.get("code", "")).strip(),
            str(item.get("path", "")).strip(),
            int(item.get("line", 0)) if isinstance(item.get("line"), int) else 0,
        ),
        reverse=True,
    )


def _sanitize_detection_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key).strip()
        if not key:
            continue
        if isinstance(raw_value, bool):
            sanitized[key] = raw_value
            continue
        if isinstance(raw_value, (int, float)):
            sanitized[key] = raw_value
            continue
        if isinstance(raw_value, str):
            text = raw_value.strip()
            if text:
                sanitized[key] = _summarize_text(text, max_chars=220)
            continue
        if isinstance(raw_value, list):
            items: List[Any] = []
            for item in raw_value[:8]:
                if isinstance(item, bool):
                    items.append(item)
                elif isinstance(item, (int, float)):
                    items.append(item)
                else:
                    token = str(item).strip()
                    if token:
                        items.append(_summarize_text(token, max_chars=120))
            if items:
                sanitized[key] = items
    return sanitized


def _add_skill_validation_finding(
    findings: List[Dict[str, Any]],
    *,
    severity: str,
    stage: str,
    code: str,
    message: str,
    path: Optional[str] = None,
    line: Optional[int] = None,
    evidence: Optional[str] = None,
    recommendation: Optional[str] = None,
    detection: Optional[Dict[str, Any]] = None,
) -> None:
    normalized = severity.strip().lower()
    if normalized not in SKILL_VALIDATION_SEVERITY_ORDER:
        normalized = "warn"
    finding: Dict[str, Any] = {
        "severity": normalized,
        "stage": stage.strip().lower() or "unknown",
        "code": code.strip().lower() or "unspecified",
        "message": message.strip(),
        "blocking": normalized in SKILL_VALIDATION_BLOCKING_SEVERITIES,
    }
    if path:
        finding["path"] = path
    if isinstance(line, int) and line > 0:
        finding["line"] = line
    if evidence:
        finding["evidence"] = _summarize_text(evidence, max_chars=220)
    if recommendation:
        finding["recommendation"] = recommendation.strip()
    if isinstance(detection, dict):
        sanitized_detection = _sanitize_detection_metadata(detection)
        if sanitized_detection:
            finding["detection"] = sanitized_detection
    findings.append(finding)


def _resolve_skill_validation_target(
    cfg: Dict[str, Any],
    reference: str,
    *,
    source_filter: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[str]]:
    ref = reference.strip()
    if not ref:
        return None, "target cannot be empty", []

    path_candidate = Path(ref).expanduser()
    if path_candidate.exists():
        entrypoint = path_candidate
        if path_candidate.is_dir():
            entrypoint = path_candidate / "SKILL.md"
        elif path_candidate.name != "SKILL.md":
            return None, "path target must be a skill directory or SKILL.md file", []

        if not entrypoint.exists() or not entrypoint.is_file():
            return None, f"SKILL.md not found at path target: {entrypoint}", []

        try:
            entrypoint = entrypoint.resolve()
        except OSError:
            pass
        source_root = entrypoint.parent
        contract = _build_skill_contract(
            entrypoint,
            source="path",
            source_root=source_root,
            cfg=cfg,
        )
        if contract is None:
            return None, f"unable to parse target at {entrypoint}", []
        return (
            {
                "resolution": "path",
                "reference": ref,
                "entrypoint": entrypoint,
                "source_root": source_root,
                "contract": contract,
            },
            None,
            [],
        )

    contracts, scanned_roots = _load_skill_contracts(cfg, source_filter=source_filter)
    target, error_message = _resolve_skill_contract(contracts, ref)
    if target is None:
        return None, error_message or f"skill not found: {ref}", scanned_roots

    source = str(target.get("source", "")).strip().lower()
    entrypoint_raw = str(target.get("entrypoint", "")).strip()
    if source == "project":
        entrypoint = (REPO_ROOT / entrypoint_raw).expanduser()
    else:
        entrypoint = Path(entrypoint_raw).expanduser()

    if not entrypoint.exists() or not entrypoint.is_file():
        return (
            None,
            f"resolved skill entrypoint is missing: {entrypoint}",
            scanned_roots,
        )

    try:
        entrypoint = entrypoint.resolve()
    except OSError:
        pass
    source_root = entrypoint.parent
    return (
        {
            "resolution": "skill-ref",
            "reference": ref,
            "entrypoint": entrypoint,
            "source_root": source_root,
            "contract": target,
        },
        None,
        scanned_roots,
    )


def _risk_pattern_rules() -> List[Dict[str, Any]]:
    return [
        {
            "code": "critical_rm_root",
            "severity": "critical",
            "pattern": re.compile(r"\brm\s+-rf\s+/(?:\s|$)"),
            "message": "Detected destructive root-deletion command pattern.",
            "recommendation": "Remove root-level destructive shell commands.",
        },
        {
            "code": "critical_rm_no_preserve_root",
            "severity": "critical",
            "pattern": re.compile(r"\brm\s+-rf\s+--no-preserve-root\b"),
            "message": "Detected explicit no-preserve-root deletion command.",
            "recommendation": "Remove no-preserve-root usage from skill assets.",
        },
        {
            "code": "critical_fork_bomb",
            "severity": "critical",
            "pattern": re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*;\s*\}\s*;"),
            "message": "Detected fork-bomb style command pattern.",
            "recommendation": "Remove process-fork bomb patterns from skill assets.",
        },
        {
            "code": "critical_reverse_shell",
            "severity": "critical",
            "pattern": re.compile(r"\bnc\b[^\n]{0,200}\s-e\s+(/bin/)?(sh|bash)\b"),
            "message": "Detected reverse-shell style command pattern.",
            "recommendation": "Remove shell-spawning network command patterns.",
        },
        {
            "code": "critical_disk_wipe",
            "severity": "critical",
            "pattern": re.compile(r"\bdd\b[^\n]{0,200}\bof=/dev/(sd[a-z]|nvme\d+n\d+|disk\d+)"),
            "message": "Detected direct disk-write command pattern.",
            "recommendation": "Avoid raw disk write patterns in skill assets.",
        },
        {
            "code": "high_pipe_to_shell",
            "severity": "high",
            "pattern": re.compile(r"\b(curl|wget)\b[^\n|]{0,220}\|\s*(sh|bash|zsh)\b"),
            "message": "Detected network download piped directly to a shell.",
            "recommendation": "Use verified downloads and explicit script review instead of pipe-to-shell.",
        },
        {
            "code": "high_prompt_injection_directive",
            "severity": "high",
            "pattern": re.compile(
                r"\b(ignore|disregard|bypass)\b[^\n]{0,120}\b(previous|prior|system|developer)\b"
                r"[^\n]{0,120}\b(instruction|prompt|guardrail|policy)s?\b",
                re.IGNORECASE,
            ),
            "message": "Detected prompt-injection style directive intended to bypass guardrails.",
            "recommendation": "Remove prompt-injection directives and keep instructions policy-aligned.",
        },
        {
            "code": "high_sensitive_exfiltration",
            "severity": "high",
            "pattern": re.compile(
                r"\b(curl|wget|scp|sftp|nc)\b[^\n]{0,240}"
                r"(/etc/passwd|~/.ssh/id_rsa|~/.gaia-assistant/(secrets|auth-profiles)\.json|"
                r"\$GAIA_ASSISTANT_HOME/(secrets|auth-profiles)\.json)\b|"
                r"(/etc/passwd|~/.ssh/id_rsa|~/.gaia-assistant/(secrets|auth-profiles)\.json|"
                r"\$GAIA_ASSISTANT_HOME/(secrets|auth-profiles)\.json)\b[^\n]{0,240}"
                r"\b(curl|wget|scp|sftp|nc)\b",
                re.IGNORECASE,
            ),
            "message": "Detected potential sensitive data exfiltration command pattern.",
            "recommendation": "Remove network transfer commands that reference sensitive credential paths.",
        },
        {
            "code": "high_sudo_usage",
            "severity": "high",
            "pattern": re.compile(r"\bsudo\b"),
            "message": "Detected privileged command invocation.",
            "recommendation": "Avoid privileged execution in reusable skill instructions/scripts.",
        },
        {
            "code": "high_world_writable_permissions",
            "severity": "high",
            "pattern": re.compile(r"\bchmod\s+777\b"),
            "message": "Detected world-writable permission pattern.",
            "recommendation": "Use least-privilege file modes (for example 600/640/700).",
        },
    ]


def _obfuscation_compact_rules() -> List[Dict[str, Any]]:
    return [
        {
            "code": "high_prompt_injection_directive",
            "severity": "high",
            "pattern": re.compile(
                r"(ignore|disregard|bypass)"
                r"(previous|prior|system|developer)"
                r"(instruction|instructions|prompt|guardrail|policy|policies)",
                re.IGNORECASE,
            ),
            "message": "Detected obfuscated prompt-injection directive after canonicalization.",
            "recommendation": "Remove hidden/obfuscated guardrail bypass directives.",
        },
        {
            "code": "high_sensitive_exfiltration",
            "severity": "high",
            "pattern": re.compile(
                r"(curl|wget|scp|sftp|nc).{0,240}"
                r"(etcpasswd|sshidrsa|gaiaassistantsecretsjson|gaiaassistantauthprofilesjson|"
                r"gaiaassistanthomesecretsjson|gaiaassistanthomeauthprofilesjson)|"
                r"(etcpasswd|sshidrsa|gaiaassistantsecretsjson|gaiaassistantauthprofilesjson|"
                r"gaiaassistanthomesecretsjson|gaiaassistanthomeauthprofilesjson).{0,240}"
                r"(curl|wget|scp|sftp|nc)",
                re.IGNORECASE,
            ),
            "message": "Detected obfuscated sensitive data exfiltration pattern after canonicalization.",
            "recommendation": "Remove obfuscated network transfer commands targeting sensitive credential paths.",
        },
    ]


def _normalize_obfuscation_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", html.unescape(text))
    return re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", normalized)


def _compact_obfuscation_text(text: str) -> str:
    return re.sub(r"[^a-z0-9/$._-]+", "", text.lower())


def _line_number_for_offset(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _decode_base64_obfuscation_candidate(token: str) -> str:
    if not token or len(token) > SKILL_VALIDATION_MAX_BASE64_TOKEN_CHARS:
        return ""
    padded = token + ("=" * ((4 - (len(token) % 4)) % 4))
    try:
        decoded = base64.b64decode(padded, validate=True)
    except (ValueError, TypeError):
        return ""
    if len(decoded) < 12 or len(decoded) > SKILL_VALIDATION_MAX_SCAN_FILE_BYTES:
        return ""
    text = decoded.decode("utf-8", errors="replace").strip()
    if not text:
        return ""
    printable = sum(1 for ch in text if ch.isprintable())
    ratio = float(printable) / float(len(text)) if text else 0.0
    if ratio < 0.85:
        return ""
    return text


def _collect_obfuscation_candidates(text: str) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    truncated = False
    decoded_count = 0
    seen = set()
    risk_markers = (
        "ignore",
        "disregard",
        "bypass",
        "system",
        "developer",
        "instruction",
        "prompt",
        "guardrail",
        "policy",
        "curl",
        "wget",
        "scp",
        "sftp",
        "etcpasswd",
        "sshidrsa",
        "gaiaassistant",
        "secretsjson",
        "authprofilesjson",
    )

    def add_candidate(*, value: str, line: int, source: str, mode: str, evidence: str) -> None:
        nonlocal truncated
        if len(candidates) >= SKILL_VALIDATION_MAX_CANONICAL_CANDIDATES:
            truncated = True
            return
        text_value = value.strip()
        if not text_value:
            return
        fingerprint = (source, mode, line, text_value[:180])
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        candidates.append(
            {
                "text": text_value,
                "line": line,
                "source": source,
                "mode": mode,
                "evidence": _summarize_text(evidence.strip() or text_value, max_chars=220),
            }
        )

    normalized_text = _normalize_obfuscation_text(text)
    original_lines = text.splitlines()
    normalized_lines = normalized_text.splitlines()
    line_total = max(len(original_lines), len(normalized_lines))

    for idx in range(1, line_total + 1):
        original_line = original_lines[idx - 1] if idx - 1 < len(original_lines) else ""
        normalized_line = normalized_lines[idx - 1] if idx - 1 < len(normalized_lines) else ""
        if normalized_line and normalized_line != original_line:
            add_candidate(
                value=normalized_line,
                line=idx,
                source="unicode-normalized",
                mode="text",
                evidence=normalized_line,
            )
        if re.search(r"%[0-9a-fA-F]{2}", normalized_line):
            decoded_line = urllib.parse.unquote(normalized_line)
            if decoded_line != normalized_line:
                add_candidate(
                    value=decoded_line,
                    line=idx,
                    source="url-decoded",
                    mode="text",
                    evidence=normalized_line,
                )

        compact_line = _compact_obfuscation_text(normalized_line)
        if (
            compact_line
            and compact_line != _compact_obfuscation_text(original_line)
            and any(marker in compact_line for marker in risk_markers)
        ):
            add_candidate(
                value=compact_line,
                line=idx,
                source="split-token-collapsed",
                mode="compact",
                evidence=normalized_line,
            )

    for match in re.finditer(r"<!--(.*?)-->", normalized_text, flags=re.IGNORECASE | re.DOTALL):
        snippet = match.group(1).strip()
        if not snippet:
            continue
        line = _line_number_for_offset(normalized_text, match.start())
        add_candidate(
            value=snippet,
            line=line,
            source="html-comment",
            mode="text",
            evidence=snippet,
        )
        compact_snippet = _compact_obfuscation_text(snippet)
        if compact_snippet and any(marker in compact_snippet for marker in risk_markers):
            add_candidate(
                value=compact_snippet,
                line=line,
                source="html-comment-collapsed",
                mode="compact",
                evidence=snippet,
            )

    hidden_attr = re.compile(
        r"(display\s*:\s*none|visibility\s*:\s*hidden|\shidden(?:[\s=>])|aria-hidden\s*=\s*['\"]?true)",
        re.IGNORECASE,
    )
    hidden_block = re.compile(
        r"<(?P<tag>[a-z0-9]+)(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in hidden_block.finditer(normalized_text):
        attrs = str(match.group("attrs") or "")
        if not hidden_attr.search(attrs):
            continue
        body = str(match.group("body") or "")
        body_text = re.sub(r"<[^>]+>", " ", body).strip()
        if not body_text:
            continue
        line = _line_number_for_offset(normalized_text, match.start())
        add_candidate(
            value=body_text,
            line=line,
            source="hidden-html",
            mode="text",
            evidence=body_text,
        )
        compact_body = _compact_obfuscation_text(body_text)
        if compact_body and any(marker in compact_body for marker in risk_markers):
            add_candidate(
                value=compact_body,
                line=line,
                source="hidden-html-collapsed",
                mode="compact",
                evidence=body_text,
            )

    token_pattern = re.compile(r"(?<![A-Za-z0-9+/=])([A-Za-z0-9+/]{24,}={0,2})(?![A-Za-z0-9+/=])")
    for match in token_pattern.finditer(normalized_text):
        if decoded_count >= SKILL_VALIDATION_MAX_BASE64_CANDIDATES:
            truncated = True
            break
        token = str(match.group(1) or "")
        decoded_text = _decode_base64_obfuscation_candidate(token)
        if not decoded_text:
            continue
        compact_decoded = _compact_obfuscation_text(decoded_text)
        if not any(marker in compact_decoded for marker in risk_markers):
            continue
        decoded_count += 1
        line = _line_number_for_offset(normalized_text, match.start(1))
        add_candidate(
            value=decoded_text,
            line=line,
            source="base64-decoded",
            mode="text",
            evidence=f"{token[:64]}...",
        )
        if compact_decoded:
            add_candidate(
                value=compact_decoded,
                line=line,
                source="base64-decoded-collapsed",
                mode="compact",
                evidence=decoded_text,
            )

    return {
        "candidates": candidates,
        "truncated": truncated,
        "decoded_candidates": decoded_count,
    }


def _scan_obfuscation_candidates(
    *,
    text: str,
    display_path: str,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    candidate_payload = _collect_obfuscation_candidates(text)
    candidates = candidate_payload.get("candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    truncated = bool(candidate_payload.get("truncated"))
    decoded_candidates = int(candidate_payload.get("decoded_candidates", 0))

    source_counts: Dict[str, int] = {}
    hit_count = 0
    existing_signatures = {
        (
            str(item.get("code", "")).strip().lower(),
            str(item.get("path", "")).strip(),
            int(item.get("line", 0)) if isinstance(item.get("line"), int) else 0,
        )
        for item in findings
        if isinstance(item, dict)
    }

    rule_by_code = {str(rule.get("code", "")).strip().lower(): rule for rule in _risk_pattern_rules()}
    canonical_rules = [
        rule
        for code in ("high_prompt_injection_directive", "high_sensitive_exfiltration")
        for rule in [rule_by_code.get(code)]
        if isinstance(rule, dict)
    ]
    compact_rules = _obfuscation_compact_rules()

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_text = str(candidate.get("text", "")).strip()
        if not candidate_text:
            continue
        source = str(candidate.get("source", "")).strip() or "canonicalized"
        mode = str(candidate.get("mode", "")).strip().lower() or "text"
        line_value = int(candidate.get("line", 0)) if isinstance(candidate.get("line"), int) else 0
        source_counts[source] = source_counts.get(source, 0) + 1

        rules = compact_rules if mode == "compact" else canonical_rules
        for rule in rules:
            pattern = rule.get("pattern")
            if not isinstance(pattern, re.Pattern):
                continue
            if not pattern.search(candidate_text):
                continue
            code = str(rule.get("code", "")).strip().lower()
            signature = (code, display_path, line_value if line_value > 0 else 0)
            if signature in existing_signatures:
                continue
            _add_skill_validation_finding(
                findings,
                severity=str(rule.get("severity", "high")),
                stage="canonicalized",
                code=code,
                message=str(rule.get("message", "Detected obfuscated risk pattern.")),
                path=display_path,
                line=line_value if line_value > 0 else None,
                evidence=str(candidate.get("evidence", candidate_text)),
                recommendation=str(rule.get("recommendation", "")),
                detection={
                    "mode": mode,
                    "source": source,
                    "candidate_stage": "canonicalized",
                    "rule_scope": "obfuscation-aware",
                },
            )
            existing_signatures.add(signature)
            hit_count += 1

    if truncated:
        _add_skill_validation_finding(
            findings,
            severity="warn",
            stage="canonicalized",
            code="canonicalization_scan_truncated",
            message=(
                "Obfuscation-aware scan candidate budget was reached; only a bounded subset "
                "was analyzed."
            ),
            path=display_path,
            recommendation=(
                "Reduce payload size/complexity or run targeted manual review for additional "
                "encoded/hidden content."
            ),
            detection={
                "candidate_limit": SKILL_VALIDATION_MAX_CANONICAL_CANDIDATES,
                "decoded_limit": SKILL_VALIDATION_MAX_BASE64_CANDIDATES,
                "rule_scope": "obfuscation-aware",
            },
        )

    return {
        "candidate_count": len(candidates),
        "decoded_candidates": decoded_candidates,
        "hit_count": hit_count,
        "truncated": truncated,
        "source_counts": source_counts,
    }


def _collect_skill_files(skill_dir: Path, entrypoint: Path) -> Tuple[List[Path], bool]:
    discovered: List[Path] = []
    truncated = False
    for candidate in sorted(skill_dir.rglob("*")):
        if len(discovered) >= SKILL_VALIDATION_MAX_SCAN_FILES:
            truncated = True
            break
        if not candidate.is_file():
            continue
        if ".git" in candidate.parts:
            continue
        discovered.append(candidate)
    if entrypoint not in discovered:
        discovered.insert(0, entrypoint)
    return discovered, truncated


def _validate_skill_assets(
    *,
    entrypoint: Path,
    skill_dir: Path,
    findings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scanned_files, truncated = _collect_skill_files(skill_dir, entrypoint)
    scanned_report: List[Dict[str, Any]] = []
    if truncated:
        _add_skill_validation_finding(
            findings,
            severity="warn",
            stage="static",
            code="scan_truncated",
            message=(
                f"Static validation scanned only the first {SKILL_VALIDATION_MAX_SCAN_FILES} files "
                "to keep execution bounded."
            ),
            path=_display_runtime_path(skill_dir),
            recommendation="Narrow skill package scope or validate additional files manually.",
        )

    rules = _risk_pattern_rules()
    for file_path in scanned_files:
        display_path = _display_runtime_path(file_path)
        size_bytes: int = 0
        try:
            stat = file_path.stat()
            size_bytes = int(stat.st_size)
        except OSError:
            _add_skill_validation_finding(
                findings,
                severity="warn",
                stage="static",
                code="file_stat_failed",
                message="Unable to stat a file during validation.",
                path=display_path,
            )
            scanned_report.append({"path": display_path, "scanned": False, "reason": "stat_failed"})
            continue

        if size_bytes > SKILL_VALIDATION_MAX_SCAN_FILE_BYTES:
            _add_skill_validation_finding(
                findings,
                severity="warn",
                stage="static",
                code="file_skipped_too_large",
                message=(
                    f"Skipped file larger than {SKILL_VALIDATION_MAX_SCAN_FILE_BYTES} bytes "
                    "during static validation."
                ),
                path=display_path,
                recommendation="Split large files or run targeted manual review.",
            )
            scanned_report.append(
                {
                    "path": display_path,
                    "size_bytes": size_bytes,
                    "scanned": False,
                    "reason": "too_large",
                }
            )
            continue

        try:
            raw = file_path.read_bytes()
        except OSError:
            _add_skill_validation_finding(
                findings,
                severity="warn",
                stage="static",
                code="file_read_failed",
                message="Unable to read a file during static validation.",
                path=display_path,
            )
            scanned_report.append({"path": display_path, "size_bytes": size_bytes, "scanned": False, "reason": "read_failed"})
            continue

        if b"\x00" in raw:
            scanned_report.append(
                {
                    "path": display_path,
                    "size_bytes": size_bytes,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "scanned": False,
                    "reason": "binary",
                }
            )
            continue

        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        for rule in rules:
            pattern = rule["pattern"]
            hits = 0
            for idx, line in enumerate(lines, start=1):
                if not pattern.search(line):
                    continue
                _add_skill_validation_finding(
                    findings,
                    severity=str(rule["severity"]),
                    stage="static",
                    code=str(rule["code"]),
                    message=str(rule["message"]),
                    path=display_path,
                    line=idx,
                    evidence=line.strip(),
                    recommendation=str(rule["recommendation"]),
                    detection={
                        "mode": "raw-line",
                        "source": "file-text",
                        "candidate_stage": "static",
                    },
                )
                hits += 1
                if hits >= SKILL_VALIDATION_MAX_HITS_PER_RULE:
                    break

        obfuscation_scan = _scan_obfuscation_candidates(
            text=text,
            display_path=display_path,
            findings=findings,
        )

        scanned_report.append(
            {
                "path": display_path,
                "size_bytes": size_bytes,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "scanned": True,
                "canonicalization": obfuscation_scan,
            }
        )
    return scanned_report


def _skill_validation_summary(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {severity: 0 for severity in SKILL_VALIDATION_SEVERITY_ORDER}
    blocking = 0
    for finding in findings:
        severity = str(finding.get("severity", "")).strip().lower()
        if severity in counts:
            counts[severity] += 1
        if bool(finding.get("blocking")):
            blocking += 1
    return {
        "finding_count": len(findings),
        "blocking_count": blocking,
        "by_severity": counts,
    }


def _skill_provenance_policy(cfg: Dict[str, Any]) -> Dict[str, Any]:
    skills_cfg = cfg.get("skills", {})
    if not isinstance(skills_cfg, dict):
        skills_cfg = {}
    default_skills = DEFAULT_CONFIG.get("skills", {})

    def _mode(key: str, fallback: str) -> str:
        raw = str(skills_cfg.get(key, default_skills.get(key, fallback))).strip().lower()
        return raw if raw in SKILL_PROVENANCE_MODE_CHOICES else fallback

    return {
        "provenance_mode": _mode("provenance_mode", "warn"),
        "attestation_mode": _mode("attestation_mode", "warn"),
        "source_health_mode": _mode("source_health_mode", "warn"),
        "source_health_min_score": _normalize_int_default(
            skills_cfg.get(
                "source_health_min_score",
                default_skills.get(
                    "source_health_min_score",
                    SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_DEFAULT,
                ),
            ),
            default_value=SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_DEFAULT,
            min_value=SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MIN,
            max_value=SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_MAX,
        ),
    }


def _provenance_is_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _provenance_valid_git_oid(value: str) -> bool:
    token = value.strip()
    return bool(re.fullmatch(r"[0-9a-fA-F]{40}", token))


def _provenance_valid_repo(value: str) -> bool:
    token = value.strip()
    if not token:
        return False
    if token.startswith("git@"):
        return True
    parsed = urllib.parse.urlparse(token)
    return parsed.scheme in ("https", "ssh") and bool(parsed.netloc)


def _provenance_first_nonempty(
    frontmatter: Dict[str, Any],
    file_payload: Dict[str, Any],
    keys: List[str],
) -> str:
    for key in keys:
        value = frontmatter.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    for key in keys:
        value = file_payload.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _load_skill_provenance_payload(skill_dir: Path) -> Tuple[Dict[str, Any], Optional[Path]]:
    payload_path = skill_dir / "provenance.json"
    if not payload_path.exists() or not payload_path.is_file():
        return {}, None
    payload = _load_json(payload_path)
    if not isinstance(payload, dict):
        return {}, payload_path

    if isinstance(payload.get("provenance"), dict):
        merged = dict(payload)
        for key, value in payload.get("provenance", {}).items():
            if key not in merged:
                merged[key] = value
        payload = merged
    return payload, payload_path


def _extract_skill_provenance_metadata(
    *,
    skill_dir: Path,
    frontmatter: Dict[str, Any],
) -> Dict[str, Any]:
    provenance_payload, provenance_path = _load_skill_provenance_payload(skill_dir)
    frontmatter_keys = sorted(frontmatter.keys())

    source_repo = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["source_repo", "provenance_repo", "repo_url", "repo"],
    )
    source_commit = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["source_commit", "source_commit_sha", "provenance_commit", "commit_sha", "commit"],
    )
    source_tree = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["source_tree", "source_tree_sha", "provenance_tree", "tree_sha", "tree"],
    )
    attestation_ref = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["attestation_ref", "source_attestation", "provenance_attestation", "attestation"],
    )
    attestation_sha256 = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["attestation_sha256", "source_attestation_sha256", "provenance_attestation_sha256"],
    )
    score_raw = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["source_health_score", "scorecard_score", "provenance_source_health_score"],
    )
    source_health_provider = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["source_health_provider", "scorecard_provider", "provenance_source_health_provider"],
    )
    source_health_checked_at = _provenance_first_nonempty(
        frontmatter,
        provenance_payload,
        ["source_health_checked_at", "scorecard_checked_at", "provenance_source_health_checked_at"],
    )

    source_health_score: Optional[float] = None
    if score_raw:
        try:
            source_health_score = float(score_raw)
        except ValueError:
            source_health_score = None

    return {
        "source_repo": source_repo,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "attestation_ref": attestation_ref,
        "attestation_sha256": attestation_sha256.lower(),
        "source_health_score": source_health_score,
        "source_health_score_raw": score_raw,
        "source_health_provider": source_health_provider,
        "source_health_checked_at": source_health_checked_at,
        "provenance_file": _display_runtime_path(provenance_path) if provenance_path else "",
        "frontmatter_keys": frontmatter_keys,
    }


def _evaluate_skill_provenance_admission(
    *,
    cfg: Dict[str, Any],
    source: str,
    skill_dir: Path,
    frontmatter: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    policy = _skill_provenance_policy(cfg)
    normalized_source = str(source).strip().lower()
    metadata = _extract_skill_provenance_metadata(skill_dir=skill_dir, frontmatter=frontmatter)

    result: Dict[str, Any] = {
        "evaluated": False,
        "source": normalized_source,
        "policy": policy,
        "metadata": metadata,
        "checks": [],
        "overall_decision": "skipped",
    }

    if normalized_source not in ("local", "path"):
        result["checks"].append(
            {
                "name": "scope",
                "mode": "off",
                "decision": "skipped",
                "reason": "provenance admission gate applies only to local/path sources",
            }
        )
        return result

    result["evaluated"] = True
    overall_rank = 0  # 0=pass, 1=warn, 2=fail

    def _record_check(
        *,
        name: str,
        mode: str,
        decision: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        nonlocal overall_rank
        if decision == "warn":
            overall_rank = max(overall_rank, 1)
        elif decision == "fail":
            overall_rank = max(overall_rank, 2)
        payload: Dict[str, Any] = {
            "name": name,
            "mode": mode,
            "decision": decision,
            "reason": reason,
        }
        if isinstance(details, dict) and details:
            payload["details"] = details
        result["checks"].append(payload)

    def _finding_for_mode(
        *,
        mode: str,
        code: str,
        message: str,
        recommendation: str,
        evidence: Optional[str] = None,
    ) -> str:
        if mode == "off":
            return "skipped"
        severity = "high" if mode == "enforce" else "warn"
        _add_skill_validation_finding(
            findings,
            severity=severity,
            stage="provenance",
            code=code,
            message=message,
            path=_display_runtime_path(skill_dir),
            evidence=evidence,
            recommendation=recommendation,
        )
        return "fail" if mode == "enforce" else "warn"

    source_repo = str(metadata.get("source_repo", "")).strip()
    source_commit = str(metadata.get("source_commit", "")).strip()
    source_tree = str(metadata.get("source_tree", "")).strip()
    pin_mode = str(policy.get("provenance_mode", "warn"))
    if pin_mode == "off":
        _record_check(
            name="source_pinning",
            mode=pin_mode,
            decision="skipped",
            reason="source pinning policy mode is off",
        )
    else:
        repo_valid = _provenance_valid_repo(source_repo)
        oid_valid = _provenance_valid_git_oid(source_commit) or _provenance_valid_git_oid(source_tree)
        if repo_valid and oid_valid:
            _record_check(
                name="source_pinning",
                mode=pin_mode,
                decision="pass",
                reason="source repository and immutable revision pin are present",
                details={
                    "source_repo": source_repo,
                    "source_commit": source_commit,
                    "source_tree": source_tree,
                },
            )
        else:
            decision = _finding_for_mode(
                mode=pin_mode,
                code="provenance_source_pin_missing",
                message=(
                    "Missing or invalid source pinning metadata. Expected source repo URL and "
                    "a 40-character commit/tree hash."
                ),
                evidence=f"repo={source_repo or '<empty>'} commit={source_commit or '<empty>'} tree={source_tree or '<empty>'}",
                recommendation=(
                    "Provide source_repo and source_commit (or source_tree) in frontmatter "
                    "or provenance.json."
                ),
            )
            _record_check(
                name="source_pinning",
                mode=pin_mode,
                decision=decision,
                reason="source pinning metadata is incomplete or invalid",
            )

    attestation_mode = str(policy.get("attestation_mode", "warn"))
    attestation_ref = str(metadata.get("attestation_ref", "")).strip()
    attestation_sha256 = str(metadata.get("attestation_sha256", "")).strip().lower()
    if attestation_mode == "off":
        _record_check(
            name="attestation",
            mode=attestation_mode,
            decision="skipped",
            reason="attestation policy mode is off",
        )
    elif not attestation_ref:
        decision = _finding_for_mode(
            mode=attestation_mode,
            code="provenance_attestation_missing",
            message="No attestation reference provided for skill provenance.",
            recommendation="Provide attestation_ref via frontmatter or provenance.json.",
        )
        _record_check(
            name="attestation",
            mode=attestation_mode,
            decision=decision,
            reason="attestation reference is missing",
        )
    elif _provenance_is_url(attestation_ref):
        if attestation_mode == "enforce":
            decision = _finding_for_mode(
                mode=attestation_mode,
                code="provenance_attestation_unverified_remote",
                message="Attestation reference is remote and cannot be verified in deterministic local mode.",
                evidence=attestation_ref,
                recommendation="Use a locally available attestation artifact for enforce mode.",
            )
            _record_check(
                name="attestation",
                mode=attestation_mode,
                decision=decision,
                reason="remote attestation cannot be verified in enforce mode",
            )
        else:
            decision = _finding_for_mode(
                mode=attestation_mode,
                code="provenance_attestation_remote_warn",
                message="Attestation reference is remote and was not verified locally.",
                evidence=attestation_ref,
                recommendation="Prefer local attestation artifacts for deterministic verification.",
            )
            _record_check(
                name="attestation",
                mode=attestation_mode,
                decision=decision,
                reason="remote attestation reference not verified",
            )
    else:
        attestation_path = Path(attestation_ref).expanduser()
        if not attestation_path.is_absolute():
            attestation_path = (skill_dir / attestation_path).resolve()
        exists = attestation_path.exists() and attestation_path.is_file()
        if not exists:
            decision = _finding_for_mode(
                mode=attestation_mode,
                code="provenance_attestation_missing_file",
                message=f"Attestation file not found: {_display_runtime_path(attestation_path)}",
                recommendation="Provide a local attestation file or adjust attestation_ref.",
            )
            _record_check(
                name="attestation",
                mode=attestation_mode,
                decision=decision,
                reason="attestation file is missing",
            )
        else:
            local_sha = _sha256_file(attestation_path).lower()
            if attestation_sha256 and attestation_sha256 != local_sha:
                decision = _finding_for_mode(
                    mode=attestation_mode,
                    code="provenance_attestation_hash_mismatch",
                    message="Attestation SHA256 does not match attestation file.",
                    evidence=f"expected={attestation_sha256} actual={local_sha}",
                    recommendation="Update attestation_sha256 or refresh attestation artifact.",
                )
                _record_check(
                    name="attestation",
                    mode=attestation_mode,
                    decision=decision,
                    reason="attestation hash mismatch",
                )
            else:
                _record_check(
                    name="attestation",
                    mode=attestation_mode,
                    decision="pass",
                    reason="attestation reference verified locally",
                    details={
                        "attestation_path": _display_runtime_path(attestation_path),
                        "attestation_sha256": local_sha,
                    },
                )

    source_health_mode = str(policy.get("source_health_mode", "warn"))
    source_health_score = metadata.get("source_health_score")
    min_score = int(policy.get("source_health_min_score", SKILL_PROVENANCE_SOURCE_HEALTH_MIN_SCORE_DEFAULT))
    if source_health_mode == "off":
        _record_check(
            name="source_health",
            mode=source_health_mode,
            decision="skipped",
            reason="source health policy mode is off",
        )
    elif not isinstance(source_health_score, (int, float)):
        decision = _finding_for_mode(
            mode=source_health_mode,
            code="provenance_source_health_missing",
            message="No numeric source health score was provided for this skill.",
            recommendation=(
                "Provide source_health_score in frontmatter or provenance.json "
                "to support threshold gating."
            ),
        )
        _record_check(
            name="source_health",
            mode=source_health_mode,
            decision=decision,
            reason="source health score missing",
        )
    elif float(source_health_score) < float(min_score):
        decision = _finding_for_mode(
            mode=source_health_mode,
            code="provenance_source_health_below_threshold",
            message=(
                f"Source health score {float(source_health_score):.2f} is below configured threshold {min_score}."
            ),
            recommendation="Improve source health or reduce threshold only with explicit security review.",
        )
        _record_check(
            name="source_health",
            mode=source_health_mode,
            decision=decision,
            reason="source health score below threshold",
            details={"score": float(source_health_score), "threshold": min_score},
        )
    else:
        _record_check(
            name="source_health",
            mode=source_health_mode,
            decision="pass",
            reason="source health score meets threshold",
            details={"score": float(source_health_score), "threshold": min_score},
        )

    if overall_rank == 2:
        result["overall_decision"] = "fail"
    elif overall_rank == 1:
        result["overall_decision"] = "warn"
    else:
        result["overall_decision"] = "pass"
    return result


def _sandbox_default_profile(cfg: Dict[str, Any]) -> str:
    sandbox_cfg = cfg.get("sandbox", {})
    if isinstance(sandbox_cfg, dict):
        candidate = str(sandbox_cfg.get("default_profile", SANDBOX_DEFAULT_PROFILE)).strip().lower()
        if candidate in SANDBOX_PROFILE_CHOICES:
            return candidate
    return SANDBOX_DEFAULT_PROFILE


def _sandbox_default_allow_network(cfg: Dict[str, Any]) -> bool:
    sandbox_cfg = cfg.get("sandbox", {})
    if not isinstance(sandbox_cfg, dict):
        return False
    return bool(sandbox_cfg.get("allow_network", False))


def _normalize_sandbox_profile(raw: Optional[str], cfg: Dict[str, Any]) -> str:
    if raw:
        candidate = str(raw).strip().lower()
        if candidate in SANDBOX_PROFILE_CHOICES:
            return candidate
    return _sandbox_default_profile(cfg)


def _sandbox_approvals_path(trace_dir: Path) -> Path:
    return trace_dir / "sandbox-approvals.jsonl"


def _sandbox_profiles_payload(default_profile: str) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": "gaia.sandbox.v1",
        "default_profile": default_profile,
        "profiles": [
            {
                "name": "read-only",
                "filesystem_mode": "read-only",
                "network_default": "deny",
                "escalation_reasons": [
                    "filesystem_write",
                    "network_access",
                    "high_risk_command",
                ],
            },
            {
                "name": "workspace-write",
                "filesystem_mode": "workspace-write",
                "network_default": "deny",
                "escalation_reasons": [
                    "network_access",
                    "high_risk_command",
                ],
            },
        ],
    }


def _is_network_command(tokens: List[str]) -> bool:
    network_tools = {
        "curl",
        "wget",
        "ftp",
        "http",
        "https",
        "ssh",
        "scp",
        "sftp",
        "nc",
        "netcat",
        "ping",
        "dig",
        "nslookup",
        "telnet",
    }
    for token in tokens:
        value = token.strip().lower()
        if value in network_tools:
            return True
        if value.startswith(("http://", "https://")):
            return True
    return False


def _is_write_command(command_text: str, tokens: List[str]) -> bool:
    if re.search(r"(?:^|\s)>{1,2}(?:\s|$)", command_text):
        return True
    if ">>" in command_text:
        return True

    write_tools = {
        "rm",
        "mv",
        "cp",
        "mkdir",
        "touch",
        "tee",
        "truncate",
        "dd",
        "install",
        "chmod",
        "chown",
        "ln",
    }
    for token in tokens:
        if token.strip().lower() in write_tools:
            return True
    return False


def _sandbox_high_risk_matches(command_text: str) -> List[str]:
    hits: List[str] = []
    for rule in _risk_pattern_rules():
        severity = str(rule.get("severity", "")).strip().lower()
        if severity not in SKILL_VALIDATION_BLOCKING_SEVERITIES:
            continue
        pattern = rule.get("pattern")
        if hasattr(pattern, "search") and pattern.search(command_text):
            hits.append(str(rule.get("code", "high_risk_pattern")))
    return sorted(set(hits))


def _sandbox_escalation_reasons(
    *,
    command_text: str,
    command_tokens: List[str],
    profile: str,
    allow_network: bool,
) -> List[Dict[str, Any]]:
    reasons: List[Dict[str, Any]] = []
    if _is_write_command(command_text, command_tokens) and profile == "read-only":
        reasons.append(
            {
                "id": "filesystem_write",
                "message": "Command appears to write to filesystem under read-only profile.",
            }
        )
    if _is_network_command(command_tokens) and not allow_network:
        reasons.append(
            {
                "id": "network_access",
                "message": "Command appears to use network while network is denied by default.",
            }
        )

    for rule_code in _sandbox_high_risk_matches(command_text):
        reasons.append(
            {
                "id": "high_risk_command",
                "message": f"High-risk command pattern detected ({rule_code}).",
                "rule_code": rule_code,
            }
        )
    return reasons


def _shell_permission_for_sandbox(cfg: Dict[str, Any]) -> Tuple[bool, str, str]:
    level = _permission_for_capability(cfg, "shell_exec")
    if level == "forbidden":
        return False, level, "blocked by shell_exec policy"
    if level == "confirm":
        return True, level, "allowed (explicit sandbox command)"
    return True, level, "allowed"


def _network_permission_for_sandbox(cfg: Dict[str, Any]) -> Tuple[bool, str]:
    level = _permission_for_capability(cfg, "network_request")
    if level == "forbidden":
        return False, level
    return True, level


def _emit_sandbox_approval_event(
    *,
    trace_dir: Path,
    command_text: str,
    profile: str,
    allow_network: bool,
    reasons: List[Dict[str, Any]],
    approved: bool,
    source: str,
) -> Dict[str, Any]:
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "network_mode": "allow" if allow_network else "deny",
        "command_summary": _summarize_text(command_text, max_chars=240),
        "escalation_reasons": reasons,
        "decision": "approved" if approved else "denied",
        "decision_source": source,
        "schema_version": 1,
    }
    _append_jsonl(_sandbox_approvals_path(trace_dir), event)
    return event


def _policy_risk_rank(value: str) -> int:
    try:
        return POLICY_RISK_CHOICES.index(value)
    except ValueError:
        return 0


def _normalize_policy_source(raw: Optional[str]) -> str:
    value = str(raw or "").strip().lower()
    if value in POLICY_SOURCE_CHOICES:
        return value
    return "unknown"


def _normalize_policy_tool(raw: Optional[str]) -> str:
    value = str(raw or "").strip().lower()
    if value in POLICY_TOOL_CHOICES:
        return value
    return "file_read"


def _policy_default_scope(cfg: Dict[str, Any]) -> str:
    policy = cfg.get("policy", {})
    if isinstance(policy, dict):
        value = str(policy.get("default_scope", POLICY_DEFAULT_SCOPE)).strip().lower()
        if value in POLICY_SCOPE_CHOICES:
            return value
    return POLICY_DEFAULT_SCOPE


def _normalize_policy_scope(raw: Optional[str], cfg: Dict[str, Any]) -> str:
    if raw:
        value = str(raw).strip().lower()
        if value in POLICY_SCOPE_CHOICES:
            return value
    return _policy_default_scope(cfg)


def _policy_effect_for_source(cfg: Dict[str, Any], source: str) -> str:
    policy = cfg.get("policy", {})
    source_effect = policy.get("source_effect", {}) if isinstance(policy, dict) else {}
    if isinstance(source_effect, dict):
        value = str(source_effect.get(source, source_effect.get("unknown", "allow"))).strip().lower()
        if value in POLICY_DECISION_CHOICES:
            return value
    return "allow"


def _policy_risk_for_tool(cfg: Dict[str, Any], tool: str) -> str:
    policy = cfg.get("policy", {})
    tool_risk = policy.get("tool_risk", {}) if isinstance(policy, dict) else {}
    if isinstance(tool_risk, dict):
        value = str(tool_risk.get(tool, "medium")).strip().lower()
        if value in POLICY_RISK_CHOICES:
            return value
    return "medium"


def _policy_scope_max_risk(cfg: Dict[str, Any], scope: str) -> str:
    policy = cfg.get("policy", {})
    scope_map = policy.get("scope_max_risk", {}) if isinstance(policy, dict) else {}
    if isinstance(scope_map, dict):
        value = str(scope_map.get(scope, scope_map.get(POLICY_DEFAULT_SCOPE, "high"))).strip().lower()
        if value in POLICY_RISK_CHOICES:
            return value
    return "high"


def _policy_skill_allowlist(cfg: Dict[str, Any], skill_id: str) -> Optional[List[str]]:
    if not skill_id:
        return None
    policy = cfg.get("policy", {})
    allowlists = policy.get("skill_tool_allowlists", {}) if isinstance(policy, dict) else {}
    if not isinstance(allowlists, dict):
        return None
    raw = allowlists.get(skill_id)
    if not isinstance(raw, list):
        return None
    values = [str(item).strip().lower() for item in raw if str(item).strip()]
    return [tool for tool in values if tool in POLICY_TOOL_CHOICES]


def _resolve_policy_skill_reference(
    cfg: Dict[str, Any],
    reference: str,
    *,
    source_filter: str = "all",
) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[str]]:
    resolved, error_message, scanned_roots = _resolve_skill_validation_target(
        cfg,
        reference,
        source_filter=source_filter,
    )
    if resolved is None:
        return None, error_message or "unable to resolve skill", scanned_roots
    contract = resolved.get("contract", {})
    contract = contract if isinstance(contract, dict) else {}
    skill_id = str(contract.get("skill_id", "")).strip()
    if not skill_id:
        return None, "resolved skill is missing skill_id", scanned_roots
    return (
        {
            "skill_id": skill_id,
            "source": _normalize_policy_source(str(contract.get("source", "unknown"))),
            "name": str(contract.get("name", "")).strip(),
            "entrypoint": str(contract.get("entrypoint", "")).strip(),
            "reference": str(resolved.get("reference", "")).strip(),
        },
        None,
        scanned_roots,
    )


def _infer_policy_tool_from_command(command_text: str, command_tokens: List[str]) -> str:
    lowered = [token.strip().lower() for token in command_tokens]
    if any(token in ("rm", "rmdir", "unlink", "shred") for token in lowered):
        return "delete_files"
    if _is_network_command(command_tokens):
        return "network_request"
    if _is_write_command(command_text, command_tokens):
        return "file_write"
    if lowered and lowered[0] in ("sh", "bash", "zsh", "python", "python3", "node"):
        return "shell_exec"
    return "file_read"


def _evaluate_policy_decision(
    cfg: Dict[str, Any],
    *,
    tool: str,
    source: str,
    user_scope: str,
    skill_id: str = "",
) -> Dict[str, Any]:
    normalized_tool = _normalize_policy_tool(tool)
    normalized_source = _normalize_policy_source(source)
    normalized_scope = _normalize_policy_scope(user_scope, cfg)
    risk = _policy_risk_for_tool(cfg, normalized_tool)
    max_risk = _policy_scope_max_risk(cfg, normalized_scope)
    source_effect = _policy_effect_for_source(cfg, normalized_source)
    allowlist = _policy_skill_allowlist(cfg, skill_id)

    explanations: List[str] = []
    policy_id = "policy.default.v1"
    decision = "allow"

    if allowlist is not None:
        policy_id = f"policy.skill_allowlist.v1:{skill_id}"
        if normalized_tool not in allowlist:
            return {
                "schema_version": 1,
                "decision": "deny",
                "policy_id": policy_id,
                "reason": (
                    f"tool '{normalized_tool}' is not allowed for skill '{skill_id}' "
                    f"(allowlist: {', '.join(allowlist) or 'empty'})."
                ),
                "tool": normalized_tool,
                "risk": risk,
                "source": normalized_source,
                "scope": normalized_scope,
                "skill_id": skill_id,
                "explanations": explanations,
            }
        explanations.append(f"tool '{normalized_tool}' allowed by skill allowlist for '{skill_id}'")

    if source_effect == "deny":
        return {
            "schema_version": 1,
            "decision": "deny",
            "policy_id": f"policy.source.v1:{normalized_source}",
            "reason": f"source '{normalized_source}' is denied by policy.",
            "tool": normalized_tool,
            "risk": risk,
            "source": normalized_source,
            "scope": normalized_scope,
            "skill_id": skill_id,
            "explanations": explanations,
        }
    if source_effect == "confirm":
        decision = "confirm"
        policy_id = f"policy.source.v1:{normalized_source}"
        explanations.append(f"source '{normalized_source}' requires confirmation")

    if _policy_risk_rank(risk) > _policy_risk_rank(max_risk):
        return {
            "schema_version": 1,
            "decision": "deny",
            "policy_id": f"policy.scope.v1:{normalized_scope}",
            "reason": (
                f"tool risk '{risk}' exceeds scope '{normalized_scope}' max risk '{max_risk}'."
            ),
            "tool": normalized_tool,
            "risk": risk,
            "source": normalized_source,
            "scope": normalized_scope,
            "skill_id": skill_id,
            "explanations": explanations,
        }

    if decision == "confirm":
        reason = f"confirmation required for source '{normalized_source}' before running tool '{normalized_tool}'."
    else:
        reason = f"tool '{normalized_tool}' is allowed for source '{normalized_source}' under scope '{normalized_scope}'."

    return {
        "schema_version": 1,
        "decision": decision,
        "policy_id": policy_id,
        "reason": reason,
        "tool": normalized_tool,
        "risk": risk,
        "source": normalized_source,
        "scope": normalized_scope,
        "skill_id": skill_id,
        "explanations": explanations,
    }


def _policy_allowlists(cfg: Dict[str, Any]) -> Dict[str, List[str]]:
    policy = cfg.setdefault("policy", {})
    if not isinstance(policy, dict):
        policy = {}
        cfg["policy"] = policy
    allowlists = policy.setdefault("skill_tool_allowlists", {})
    if not isinstance(allowlists, dict):
        allowlists = {}
        policy["skill_tool_allowlists"] = allowlists
    normalized = _normalize_config(cfg)
    policy = normalized.get("policy", {}) if isinstance(normalized, dict) else {}
    allowlists = policy.get("skill_tool_allowlists", {}) if isinstance(policy, dict) else {}
    return allowlists if isinstance(allowlists, dict) else {}


def _load_schedule_run_keys(storage_dir: Path) -> Dict[str, Dict[str, Any]]:
    runs = _read_jsonl_records(_schedule_runs_path(storage_dir))
    keyed: Dict[str, Dict[str, Any]] = {}
    for item in runs:
        key = str(item.get("run_key", "")).strip()
        if key:
            keyed[key] = item
    return keyed


def _schedule_run_key(schedule_id: str, due_at: datetime) -> str:
    return f"{schedule_id}:{_isoformat_utc(due_at)}"


def _schedule_interval_minutes(schedule: Dict[str, Any]) -> Optional[int]:
    cadence = schedule.get("cadence", {})
    if not isinstance(cadence, dict):
        return None
    raw = cadence.get("every_minutes")
    if not isinstance(raw, int):
        return None
    return raw if raw > 0 else None


def _schedule_cadence_type(schedule: Dict[str, Any]) -> str:
    cadence = schedule.get("cadence", {})
    if not isinstance(cadence, dict):
        return "oneshot"
    cadence_type = str(cadence.get("type", "oneshot")).strip().lower()
    return cadence_type if cadence_type in ("oneshot", "interval") else "oneshot"


def _schedule_profile_name(schedule: Dict[str, Any]) -> str:
    payload = schedule.get("payload", {})
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("profile", "")).strip().lower()


def _schedule_action(schedule: Dict[str, Any]) -> str:
    return str(schedule.get("action", "")).strip().lower()


def _is_reminder_schedule(schedule: Dict[str, Any]) -> bool:
    return _schedule_action(schedule) == "reminder_emit"


def _reminder_message(schedule: Dict[str, Any]) -> str:
    payload = schedule.get("payload", {})
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("message", "")).strip()


def _schedule_window_minutes(schedule: Dict[str, Any]) -> int:
    raw = schedule.get("window_minutes", SCHEDULE_DEFAULT_WINDOW_MINUTES)
    if isinstance(raw, int) and raw > 0:
        return raw
    return SCHEDULE_DEFAULT_WINDOW_MINUTES


def _next_interval_due_after(anchor_due: datetime, every_minutes: int, reference: datetime) -> datetime:
    step = timedelta(minutes=max(every_minutes, 1))
    due = anchor_due
    while due <= reference:
        due += step
    return due


def _advance_schedule_after_due(
    schedule: Dict[str, Any],
    *,
    due_at: datetime,
    reference: datetime,
    result: str,
) -> None:
    cadence_type = _schedule_cadence_type(schedule)
    if cadence_type == "interval":
        every = _schedule_interval_minutes(schedule)
        if every is None:
            schedule["status"] = "failed"
            schedule["next_run_at"] = None
            return
        schedule["status"] = "active"
        schedule["next_run_at"] = _isoformat_utc(
            _next_interval_due_after(anchor_due=due_at, every_minutes=every, reference=reference)
        )
        return

    schedule["next_run_at"] = None
    if result == "failed":
        schedule["status"] = "failed"
    elif str(schedule.get("status", "")).strip().lower() != "canceled":
        schedule["status"] = "completed"


def _execute_schedule_action(
    schedule: Dict[str, Any],
    *,
    cfg_path: Path,
    storage_dir: Path,
    trace_dir: Path,
    due_at: Optional[datetime] = None,
) -> Tuple[bool, str]:
    action = _schedule_action(schedule)
    if action == "reminder_emit":
        reminder_text = _reminder_message(schedule)
        if not reminder_text:
            return False, "reminder message is empty"
        schedule_id = str(schedule.get("id", "")).strip()
        record: Dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "schedule_id": schedule_id,
            "triggered_at": _isoformat_utc(datetime.now(timezone.utc)),
            "message": reminder_text,
            "status": "delivered",
        }
        if due_at is not None:
            record["due_at"] = _isoformat_utc(due_at)
        _append_jsonl(_reminder_events_path(storage_dir), record)
        return True, f"reminder delivered: {_summarize_text(reminder_text, max_chars=90)}"

    if action != "autopilot_profile_run":
        return False, f"unsupported schedule action '{action}'"

    profile_name = _schedule_profile_name(schedule)
    if profile_name not in AUTOPILOT_PROFILES:
        return False, f"unknown autopilot profile '{profile_name}'"

    run_args = argparse.Namespace(
        config=str(cfg_path),
        trace_dir=str(trace_dir),
        storage_dir=str(storage_dir),
        profile=profile_name,
        dry_run=False,
        force_failure_step=None,
    )
    rc = cmd_autopilot_run(run_args)
    if rc != 0:
        return False, f"autopilot run failed for profile '{profile_name}'"
    return True, f"autopilot run succeeded for profile '{profile_name}'"


def _captures_note_intent(user_input: str) -> Optional[Tuple[str, bool]]:
    text = user_input.strip()
    lower = text.lower()
    note_markers = ("capture this as a note", "save as note", "note this")
    task_markers = ("capture this as a task", "save as task", "add task")

    for marker in note_markers:
        if lower.startswith(marker):
            content = text[len(marker) :].lstrip(" :,-")
            return (content, False)
    for marker in task_markers:
        if lower.startswith(marker):
            content = text[len(marker) :].lstrip(" :,-")
            return (content, True)
    return None


def _extract_title_and_text(raw_html: str) -> Tuple[str, str]:
    title = ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        title = html.unescape(re.sub(r"\s+", " ", title_match.group(1)).strip())

    no_script = re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    no_style = re.sub(r"<style[^>]*>.*?</style>", " ", no_script, flags=re.IGNORECASE | re.DOTALL)
    text_only = re.sub(r"<[^>]+>", " ", no_style)
    normalized = html.unescape(re.sub(r"\s+", " ", text_only)).strip()
    return title, normalized


def _fetch_url_content(url: str, timeout: int = 15) -> Tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GaiaAssistant/0.1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Network error for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError(f"Timeout fetching {url}") from exc
    return _extract_title_and_text(raw)


def _key_points_from_text(text: str, max_points: int = 4) -> List[str]:
    if not text.strip():
        return []
    pieces = re.split(r"(?<=[.!?])\s+", text.strip())
    points: List[str] = []
    for piece in pieces:
        cleaned = piece.strip()
        if len(cleaned) < 30:
            continue
        points.append(_summarize_text(cleaned, max_chars=200))
        if len(points) >= max_points:
            break
    if points:
        return points
    return [_summarize_text(text, max_chars=200)]


def _estimate_plan_complexity(goal: str) -> str:
    words = [part for part in goal.strip().split() if part]
    count = len(words)
    if count <= 5:
        return "low"
    if count <= 12:
        return "medium"
    return "high"


def _derive_plan_dependencies(goal: str) -> List[str]:
    normalized = goal.strip().lower()
    dependencies: List[str] = []
    if any(token in normalized for token in ("research", "knowledge", "study", "read")):
        dependencies.append("reference material access")
    if any(token in normalized for token in ("setup", "install", "deploy", "configure")):
        dependencies.append("runtime environment access")
    if any(token in normalized for token in ("team", "collaborate", "stakeholder")):
        dependencies.append("stakeholder coordination")
    dependencies.append("time allocation")
    seen = set()
    deduped: List[str] = []
    for item in dependencies:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _generate_plan_steps(goal: str, refinement: str = "") -> List[str]:
    steps = [
        f"Clarify the objective and success criteria for '{goal.strip()}'.",
        "Break the objective into concrete milestones with owners and deadlines.",
        "Execute the milestones in priority order and capture outputs.",
        "Review results, identify gaps, and schedule next iteration.",
    ]
    refinement_text = refinement.strip()
    if refinement_text:
        steps.append(f"Refinement request: {refinement_text}")
    return steps

def _session_file_path(session_dir: Path, session_id: str) -> Path:
    return session_dir / f"{session_id}.json"


def _load_session(session_dir: Path, session_id: str) -> Optional[Dict[str, Any]]:
    path = _session_file_path(session_dir, session_id)
    payload = _load_json(path)
    if not payload:
        return None
    if not isinstance(payload.get("turns"), list):
        payload["turns"] = []
    return payload


def _save_session(session_dir: Path, session: Dict[str, Any]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    _write_json(_session_file_path(session_dir, str(session["id"])), session)


def _list_sessions(session_dir: Path) -> List[Dict[str, Any]]:
    if not session_dir.exists():
        return []
    sessions: List[Dict[str, Any]] = []
    for path in session_dir.glob("*.json"):
        payload = _load_json(path)
        if not payload:
            continue
        session_id = str(payload.get("id", "")).strip()
        updated_at = str(payload.get("updated_at", "")).strip()
        if not session_id:
            continue
        sessions.append({"id": session_id, "updated_at": updated_at})
    sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return sessions


def _create_session(provider: str, model: str) -> Dict[str, Any]:
    session_id = datetime.now(timezone.utc).strftime("s%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": session_id,
        "created_at": now,
        "updated_at": now,
        "provider": provider,
        "model": model,
        "turns": [],
    }


def _resolve_resume_session_id(session_dir: Path, resume: str) -> Optional[str]:
    target = str(resume).strip()
    if not target:
        return None
    if target != "last":
        return target
    sessions = _list_sessions(session_dir)
    if not sessions:
        return None
    return str(sessions[0]["id"])


def _extract_last_user_text(messages: List[Dict[str, str]]) -> str:
    for msg in reversed(messages):
        if str(msg.get("role", "")).strip() == "user":
            return str(msg.get("content", "")).strip()
    return ""


def _normalize_response_profile_token(raw: str) -> str:
    normalized = str(raw).strip().lower().replace("_", "-")
    normalized = re.sub(r"\s+", "-", normalized)
    if normalized in RESPONSE_PROFILE_CHOICES:
        return normalized
    return ""


def _feedback_profile_scores(storage_dir: Path) -> Dict[str, int]:
    scores: Dict[str, int] = {
        "concise": 0,
        "balanced": 1,
        "detailed": 0,
    }
    concise_terms = ("concise", "short", "brief", "too long", "trim", "less words", "tldr")
    detailed_terms = ("detail", "deeper", "explain", "more context", "step by step", "thorough")
    balanced_terms = ("balanced", "clear", "actionable", "structured", "practical")

    for item in _load_records(_feedback_path(storage_dir)):
        if not isinstance(item, dict):
            continue
        label_raw = str(item.get("label", "")).strip()
        try:
            label = _normalize_feedback_label(label_raw)
        except ValueError:
            continue
        correction = str(item.get("correction", "")).strip().lower()
        weight = 2 if label == "not-helpful" else 1
        if correction:
            if any(term in correction for term in concise_terms):
                scores["concise"] += weight
            if any(term in correction for term in detailed_terms):
                scores["detailed"] += weight
            if any(term in correction for term in balanced_terms):
                scores["balanced"] += weight
        elif label == "helpful":
            scores["balanced"] += 1
    return scores


def _auto_response_profile_from_feedback(storage_dir: Path) -> Tuple[str, Dict[str, int]]:
    scores = _feedback_profile_scores(storage_dir)
    order = ("balanced", "concise", "detailed")
    selected = order[0]
    for profile in order[1:]:
        if scores.get(profile, 0) > scores.get(selected, 0):
            selected = profile
    return selected, scores


def _resolve_response_profile(
    cfg: Dict[str, Any],
    storage_dir: Path,
    *,
    override: Optional[str] = None,
) -> Tuple[str, str]:
    override_token = _normalize_response_profile_token(str(override or ""))
    if override_token:
        if override_token == "auto":
            selected, _ = _auto_response_profile_from_feedback(storage_dir)
            return selected, "override:auto-feedback"
        return override_token, "override"

    profile_cfg = cfg.get("profile", {})
    profile_cfg = profile_cfg if isinstance(profile_cfg, dict) else {}
    configured = _normalize_response_profile_token(str(profile_cfg.get("response_profile", "")))
    if not configured:
        configured = RESPONSE_PROFILE_DEFAULT
    if configured == "auto":
        selected, _ = _auto_response_profile_from_feedback(storage_dir)
        return selected, "config:auto-feedback"
    return configured, "config"


def _response_profile_system_prompt(profile: str, profile_source: str) -> str:
    normalized = _normalize_response_profile_token(profile)
    if not normalized or normalized == "auto":
        normalized = RESPONSE_PROFILE_DEFAULT
    base = RESPONSE_PROFILE_SYSTEM_PROMPTS.get(normalized, RESPONSE_PROFILE_SYSTEM_PROMPTS[RESPONSE_PROFILE_DEFAULT])
    return f"{base}\nProfile source: {profile_source}."


def _response_profile_display(profile: str) -> str:
    normalized = _normalize_response_profile_token(profile)
    if not normalized or normalized == "auto":
        return RESPONSE_PROFILE_DEFAULT
    return normalized


def _extract_response_profile_from_messages(messages: List[Dict[str, str]]) -> str:
    for msg in messages:
        if str(msg.get("role", "")).strip() != "system":
            continue
        content = str(msg.get("content", "")).strip()
        match = re.search(r"response profile:\s*([a-z-]+)", content, flags=re.IGNORECASE)
        if match:
            token = _normalize_response_profile_token(match.group(1))
            if token and token != "auto":
                return token
    return RESPONSE_PROFILE_DEFAULT


def _mock_provider_response(provider: str, model: str, messages: List[Dict[str, str]]) -> str:
    prompt = _extract_last_user_text(messages)
    prompt_summary = _summarize_text(prompt, max_chars=140)
    response_profile = _extract_response_profile_from_messages(messages)
    prefix = f"[local-{provider}][profile={response_profile}]"
    if response_profile == "concise":
        return f"{prefix} {prompt_summary}"
    if response_profile == "detailed":
        return (
            f"{prefix} {prompt_summary}\n"
            f"Detail: deterministic expanded context for '{_summarize_text(prompt, max_chars=80)}'.\n"
            f"Context messages: {len(messages)} | model: {model}."
        )
    return (
        f"{prefix} {prompt_summary}\n"
        f"Context messages: {len(messages)} | model: {model}."
    )


def _extract_http_error_details(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8")
    except Exception:
        return str(exc)
    if not raw:
        return str(exc)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            message = payload["error"].get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return raw


def _looks_like_token_limit(text: str) -> bool:
    normalized = text.strip().lower()
    markers = (
        "context length",
        "too many tokens",
        "token limit",
        "maximum context",
        "context_window_exceeded",
        "context_length_exceeded",
    )
    return any(marker in normalized for marker in markers)


def _http_json_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: int = 30,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = _extract_http_error_details(exc)
        if exc.code in (413, 429) or _looks_like_token_limit(details):
            raise ProviderTokenLimitError(details) from exc
        raise ProviderError(f"HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Network error: {exc.reason}") from exc

    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned non-JSON response") from exc
    if not isinstance(decoded, dict):
        raise ProviderError("Provider returned invalid payload")
    return decoded


def _call_openai_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    response = _http_json_request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        payload=payload,
    )
    choices = response.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise ProviderError("Provider returned no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderError("Provider returned invalid choice")
    message = first.get("message", {})
    if not isinstance(message, dict):
        raise ProviderError("Provider returned invalid message payload")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        merged = "\n".join([p for p in parts if p.strip()]).strip()
        if merged:
            return merged
    raise ProviderError("Provider returned empty response")


def _call_anthropic_chat(api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
    payload = {
        "model": model,
        "max_tokens": 700,
        "messages": messages,
    }
    response = _http_json_request(
        url="https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        payload=payload,
    )
    content = response.get("content", [])
    if not isinstance(content, list):
        raise ProviderError("Provider returned invalid content")
    parts: List[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        raise ProviderError("Provider returned empty response")
    return "\n".join(parts)


def _resolve_runtime_provider(cfg: Dict[str, Any]) -> Tuple[str, str]:
    reasoning = cfg.get("reasoning", {})
    reasoning = reasoning if isinstance(reasoning, dict) else {}
    profile = cfg.get("profile", {})
    profile = profile if isinstance(profile, dict) else {}

    provider = str(reasoning.get("provider", "")).strip().lower()
    if not provider:
        provider = str(profile.get("default_provider", "anthropic")).strip().lower()
    if provider not in PROFILE_PROVIDER_CHOICES:
        provider = "anthropic"

    model = str(reasoning.get("model", "")).strip()
    if not model:
        model = _default_model_for_provider(provider)
    return provider, model


def _resolve_provider_api_key(
    provider: str,
    cfg_path: Path,
    secret_store_override: Optional[str],
) -> str:
    env_key = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }.get(provider, "")
    if not env_key:
        return ""
    from_env = os.environ.get(env_key, "").strip()
    if from_env:
        return from_env
    secret_store = _resolve_secret_store(cfg_path, secret_store_override)
    return _read_secret_api_key(secret_store, env_key)


def _reasoning_response(
    provider: str,
    model: str,
    messages: List[Dict[str, str]],
    cfg_path: Path,
    secret_store_override: Optional[str],
) -> str:
    if provider == "openai-codex":
        return _mock_provider_response(provider, model, messages)

    api_key = _resolve_provider_api_key(provider, cfg_path, secret_store_override)
    if not api_key:
        return _mock_provider_response(provider, model, messages)

    if provider == "openai":
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return _call_openai_chat(base_url=base_url, api_key=api_key, model=model, messages=messages)
    if provider == "openrouter":
        return _call_openai_chat(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            model=model,
            messages=messages,
        )
    if provider == "anthropic":
        return _call_anthropic_chat(api_key=api_key, model=model, messages=messages)
    raise ProviderError(f"Unsupported provider: {provider}")


def _infer_capability_from_prompt(text: str) -> Tuple[str, Optional[str]]:
    prompt = text.strip().lower()
    if not prompt:
        return "file_read", None
    if "send email" in prompt or "email " in prompt:
        return "send_email", "This action sends outbound email. Continue?"
    if "delete" in prompt and ("file" in prompt or "folder" in prompt):
        return "delete_files", "This action may delete files. Continue?"
    if prompt.startswith("run ") or "execute " in prompt:
        return "shell_exec", "This action executes shell commands. Continue?"
    if "http://" in prompt or "https://" in prompt:
        return "network_request", "This action performs a network request. Continue?"
    return "file_read", None


def _build_context_messages(
    turns: List[Dict[str, Any]],
    user_prompt: str,
    max_turns: int,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    bounded = turns[-max_turns:] if max_turns > 0 else turns
    messages: List[Dict[str, str]] = []
    system_text = str(system_prompt or "").strip()
    if system_text:
        messages.append({"role": "system", "content": system_text})
    for turn in bounded:
        role = str(turn.get("role", "")).strip()
        content = str(turn.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})
    return messages
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
    if provider in ("openai", "openai-codex"):
        return DEFAULT_OPENAI_MODEL
    return DEFAULT_ANTHROPIC_MODEL


def _set_reasoning_config(
    cfg_path: Path,
    provider: str,
    model: Optional[str],
    *,
    explicit_provider_override: bool,
) -> None:
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
    reasoning["explicit_provider_override"] = bool(explicit_provider_override)
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

    _set_reasoning_config(
        cfg_path,
        provider,
        model,
        explicit_provider_override=True,
    )
    print("[ok] reasoning provider configured")
    print(f"     provider: {provider}")
    print(f"     model:    {model or _default_model_for_provider(provider)}")
    return 0


def _resolve_codex_auth_path(override_path: Optional[str]) -> Path:
    return onboarding.resolve_codex_auth_path(override_path, DEFAULT_CODEX_AUTH_PATH)


def _resolve_gaia_auth_store(cfg_path: Path, override_path: Optional[str]) -> Path:
    return onboarding.resolve_gaia_auth_store(
        cfg_path,
        override_path,
        cfg_path.parent / "auth-profiles.json",
        _load_json,
    )


def _load_gaia_auth_store(path: Path) -> Dict[str, Any]:
    return onboarding.load_gaia_auth_store(path, _load_json)


def _save_gaia_auth_store(path: Path, payload: Dict[str, Any]) -> None:
    onboarding.save_gaia_auth_store(path, payload, _write_secret_json)


def _read_codex_cli_credentials(codex_auth_path: Path) -> Optional[Dict[str, Any]]:
    return onboarding.read_codex_cli_credentials(codex_auth_path, _load_json)


def _is_expired(credential: Dict[str, Any]) -> bool:
    return onboarding.is_expired(credential)


def _format_expiry(credential: Dict[str, Any]) -> str:
    return onboarding.format_expiry(credential)


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


def _claude_login() -> int:
    if not shutil.which("claude"):
        print(
            "Claude CLI is not installed. Install Claude Code CLI, then run:\n"
            "  claude auth login",
            file=sys.stderr,
        )
        return 1
    return subprocess.run(["claude", "auth", "login"]).returncode


def _run_command_capture(cmd: List[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _collect_claude_cli_credentials() -> Tuple[Optional[Dict[str, Any]], str]:
    return onboarding.collect_claude_cli_credentials(_run_command_capture)


def _apply_oauth_runtime_defaults(cfg_path: Path, oauth_provider: str) -> bool:
    return onboarding.apply_oauth_runtime_defaults(
        cfg_path,
        oauth_provider,
        ensure_config_exists=_ensure_config_exists,
        normalize_config=_normalize_config,
        write_json=_write_json,
        default_anthropic_model=DEFAULT_ANTHROPIC_MODEL,
        default_openai_model=DEFAULT_OPENAI_MODEL,
        normalize_bool_default=_normalize_bool_default,
    )


def _import_codex_profile_to_gaia(
    cfg_path: Path,
    provider: str,
    codex_auth_path: Path,
    gaia_auth_store: Path,
) -> Tuple[int, str, bool]:
    rc, profile_id, runtime_aligned = onboarding.import_codex_profile_to_gaia(
        cfg_path,
        provider,
        codex_auth_path,
        gaia_auth_store,
        read_codex_cli_credentials_fn=_read_codex_cli_credentials,
        load_gaia_auth_store_fn=_load_gaia_auth_store,
        save_gaia_auth_store_fn=_save_gaia_auth_store,
        link_profile_fn=_link_profile,
        apply_oauth_runtime_defaults_fn=_apply_oauth_runtime_defaults,
    )
    if rc != 0 and provider == "openai-codex":
        print(
            "Codex credentials not found after login.\n"
            f"Expected auth file: {codex_auth_path}",
            file=sys.stderr,
        )
    return rc, profile_id, runtime_aligned


def _import_claude_profile_to_gaia(
    cfg_path: Path,
    provider: str,
    gaia_auth_store: Path,
) -> Tuple[int, str, bool]:
    rc, profile_id, runtime_aligned = onboarding.import_claude_profile_to_gaia(
        cfg_path,
        provider,
        gaia_auth_store,
        collect_claude_cli_credentials_fn=_collect_claude_cli_credentials,
        load_gaia_auth_store_fn=_load_gaia_auth_store,
        save_gaia_auth_store_fn=_save_gaia_auth_store,
        link_profile_fn=_link_profile,
        apply_oauth_runtime_defaults_fn=_apply_oauth_runtime_defaults,
    )
    if rc != 0 and provider == "claude-code":
        _, error = _collect_claude_cli_credentials()
        detail = error or "claude auth status did not return an active OAuth profile"
        print(
            "Claude Code profile metadata was not detected after login/link.\n"
            f"Details: {detail}",
            file=sys.stderr,
        )
    return rc, profile_id, runtime_aligned


def _read_linked_credential(active_profile: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    return onboarding.read_linked_credential(active_profile, _load_gaia_auth_store)


def _linked_openai_oauth_access_token(cfg: Dict[str, Any]) -> Tuple[str, str]:
    return onboarding.linked_openai_oauth_access_token(
        cfg,
        read_linked_credential_fn=_read_linked_credential,
        is_expired_fn=_is_expired,
    )


def _provider_runtime_dependency_issue(provider: str, env: Dict[str, str]) -> Optional[str]:
    return onboarding.provider_runtime_dependency_issue(provider, env)


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
    optional_cmds = ["gh", "codex", "claude"]
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
        reasoning_override_locked = False
        if isinstance(reasoning_cfg, dict):
            reasoning_provider = str(reasoning_cfg.get("provider", "")).strip()
            reasoning_override_locked = _normalize_bool_default(
                reasoning_cfg.get("explicit_provider_override", False),
                False,
            )
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
        oauth_token, oauth_error = _linked_openai_oauth_access_token(cfg)
        oauth_runtime_ready = bool(oauth_token)

        if anth or oai or openrouter or oauth_runtime_ready:
            print("[ok] at least one runtime credential is available (env/secret-store/OAuth)")
        else:
            print("[warn] no runtime credentials found (env, secret store, or linked OAuth)")
            print("       expected: ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY")

        active = cfg.get("auth", {}).get("active_profile")
        if not isinstance(active, dict):
            if reasoning_provider in ("openai-codex", "claude-code"):
                print("[warn] no linked OAuth profile in launcher config")
                print(f"       run `{_launcher_hint()} onboard --provider {reasoning_provider}`")
            else:
                print("[info] no linked OAuth profile (not required for API-key providers)")
        else:
            credential, error = _read_linked_credential(active)
            active_provider = str(active.get("provider", "")).strip().lower()
            if credential is None:
                print(f"[warn] {error}")
            else:
                profile_id = str(active.get("profile_id", "")).strip()
                expiry = _format_expiry(credential)
                if _is_expired(credential):
                    print(f"[warn] linked OAuth profile is expired: {profile_id} (expires={expiry})")
                else:
                    print(f"[ok] linked OAuth profile found: {profile_id} (expires={expiry})")
                    if oauth_runtime_ready:
                        print("[ok] linked OAuth token can satisfy OpenAI runtime preflight")
                    if active_provider == "claude-code":
                        if shutil.which("claude"):
                            print("[ok] claude-cli is available for claude-code profile checks")
                        else:
                            print("[warn] linked profile uses claude-code but `claude` CLI is missing")
                            print(f"       run `{_launcher_hint()} auth login --provider claude-code --source claude-cli`")
            if reasoning_provider == "openai" and not oauth_runtime_ready and not oai:
                print(f"[warn] OpenAI runtime credential is missing: {oauth_error}")
                print(f"       run `{_launcher_hint()} auth login --provider openai-codex --source codex-cli`")
            if reasoning_provider == "anthropic" and active_provider == "openai-codex":
                if reasoning_override_locked:
                    print("[info] anthropic runtime provider is explicitly overridden")
                    print("       linked openai-codex OAuth profile remains available as fallback")
                else:
                    print("[warn] reasoning provider is anthropic while linked OAuth profile is openai-codex")
                    print(
                        f"       run `{_launcher_hint()} run` to apply OAuth fallback, "
                        "or `gaia config set provider openai`"
                    )

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
                ("claude-code", "Claude Code (OAuth via Claude CLI)"),
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

    if provider == "claude-code":
        print("OAuth flow selected: Claude Code via Claude CLI")
        print("This runs Claude auth login and links profile metadata into Gaia local auth store.")
        should_start = _prompt_yes_no(
            "Start Claude Code OAuth login now?",
            default=True,
            non_interactive=args.yes,
        )
        if not should_start:
            print("Skipped OAuth login. Run this later:")
            print(f"  {_launcher_hint()} auth login --provider claude-code --source claude-cli")
            return 0
        login_args = argparse.Namespace(
            config=str(cfg_path),
            provider="claude-code",
            source="claude-cli",
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
    provider = str(args.provider).strip().lower()
    source = str(args.source).strip().lower()

    if provider not in AUTH_PROVIDER_CHOICES:
        print(f"Unsupported OAuth provider: {provider}", file=sys.stderr)
        print(f"Supported providers: {', '.join(AUTH_PROVIDER_CHOICES)}", file=sys.stderr)
        return 1
    allowed_sources = onboarding.AUTH_PROVIDER_SOURCES.get(provider, ())
    if source not in allowed_sources:
        expected = ", ".join(allowed_sources) if allowed_sources else "none"
        print(f"Unsupported auth source/provider combination: source={source} provider={provider}", file=sys.stderr)
        print(f"Supported source(s) for {provider}: {expected}", file=sys.stderr)
        return 1

    gaia_auth_store = _resolve_gaia_auth_store(cfg_path, args.gaia_auth_store)
    runtime_aligned = False
    profile_id = ""
    source_label = ""

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
        rc, profile_id, runtime_aligned = _import_codex_profile_to_gaia(
            cfg_path,
            provider,
            codex_auth_path,
            gaia_auth_store,
        )
        if rc != 0:
            return rc
        source_label = "gaia-local (imported from codex-cli)"
    elif source == "claude-cli":
        if not args.no_prompt:
            answer = input(
                "Gaia will run Claude Code OAuth login, then import profile metadata into Gaia local auth store.\n"
                "Continue? [Y/n]: "
            ).strip().lower()
            if answer in ("n", "no"):
                print("Canceled.")
                return 1

        rc = _claude_login()
        if rc != 0:
            return rc

        rc, profile_id, runtime_aligned = _import_claude_profile_to_gaia(
            cfg_path,
            provider,
            gaia_auth_store,
        )
        if rc != 0:
            return rc
        source_label = "gaia-local (metadata imported from claude-cli)"
    else:
        print(f"Unsupported auth source: {source}", file=sys.stderr)
        print(f"Supported sources: {', '.join(AUTH_SOURCE_CHOICES)}", file=sys.stderr)
        return 1

    store = _load_gaia_auth_store(gaia_auth_store)
    profiles = store.get("profiles", {}) if isinstance(store, dict) else {}
    credential = profiles.get(profile_id) if isinstance(profiles, dict) else {}
    expiry = _format_expiry(credential if isinstance(credential, dict) else {})

    print("[ok] OAuth profile linked for Gaia assistant")
    print(f"     source:   {source_label}")
    print(f"     provider: {provider}")
    print(f"     profile:  {profile_id}")
    print(f"     store:    {gaia_auth_store}")
    print(f"     expires:  {expiry}")
    if runtime_aligned:
        print("[ok] Runtime defaults aligned for OAuth provider: openai/gpt-4.1-mini")
    print("")
    if source == "codex-cli":
        print("Note: credentials are stored in local Gaia auth store, not in this repository.")
    else:
        print("Note: Gaia stores only Claude profile metadata; OAuth tokens remain in Claude CLI credential storage.")
    return 0


def cmd_auth_link(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    _ensure_config_exists(cfg_path)
    provider = str(args.provider).strip().lower()
    source = str(args.source).strip().lower()

    if provider not in AUTH_PROVIDER_CHOICES:
        print(f"Unsupported OAuth provider: {provider}", file=sys.stderr)
        print(f"Supported providers: {', '.join(AUTH_PROVIDER_CHOICES)}", file=sys.stderr)
        return 1
    allowed_sources = onboarding.AUTH_PROVIDER_SOURCES.get(provider, ())
    if source not in allowed_sources:
        expected = ", ".join(allowed_sources) if allowed_sources else "none"
        print(f"Unsupported auth source/provider combination: source={source} provider={provider}", file=sys.stderr)
        print(f"Supported source(s) for {provider}: {expected}", file=sys.stderr)
        return 1

    gaia_auth_store = _resolve_gaia_auth_store(cfg_path, args.gaia_auth_store)
    runtime_aligned = False
    profile_id = ""

    if source == "codex-cli":
        codex_auth_path = _resolve_codex_auth_path(args.codex_auth_path)
        rc, profile_id, runtime_aligned = _import_codex_profile_to_gaia(
            cfg_path,
            provider,
            codex_auth_path,
            gaia_auth_store,
        )
        if rc != 0:
            return rc
        print("[ok] Imported and linked Codex OAuth profile into Gaia local store")
    elif source == "claude-cli":
        rc, profile_id, runtime_aligned = _import_claude_profile_to_gaia(
            cfg_path,
            provider,
            gaia_auth_store,
        )
        if rc != 0:
            return rc
        print("[ok] Imported and linked Claude Code OAuth profile metadata into Gaia local store")
    else:
        print(f"Unsupported auth source: {source}", file=sys.stderr)
        print(f"Supported sources: {', '.join(AUTH_SOURCE_CHOICES)}", file=sys.stderr)
        return 1

    print(f"     provider: {provider}")
    print(f"     profile:  {profile_id}")
    print(f"     store:    {gaia_auth_store}")
    if runtime_aligned:
        print("[ok] Runtime defaults aligned for OAuth provider: openai/gpt-4.1-mini")
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
        reasoning_cfg = cfg.get("reasoning", {})
        reasoning_provider = ""
        if isinstance(reasoning_cfg, dict):
            reasoning_provider = str(reasoning_cfg.get("provider", "")).strip()
        print("No linked auth profile in launcher config.")
        if reasoning_provider in ("openrouter", "openai", "anthropic"):
            print("This is expected when using API-key providers.")
            return 0
        print(f"Run: {_launcher_hint()} auth login --provider openai-codex --source codex-cli")
        print(f"Or:  {_launcher_hint()} auth login --provider claude-code --source claude-cli")
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
    account_id = str(credential.get("account_id", "")).strip() or "n/a"
    organization = str(credential.get("organization", "")).strip()
    workspace = str(credential.get("workspace", "")).strip()
    plan = str(credential.get("plan", "")).strip()
    print(f"type:      {cred_type}")
    print(f"email:     {email}")
    print(f"account:   {account_id}")
    if organization:
        print(f"org:       {organization}")
    if workspace:
        print(f"workspace: {workspace}")
    if plan:
        print(f"plan:      {plan}")
    print(f"expires:   {expires}")
    if _is_expired(credential):
        print("[warn] OAuth profile is expired")
        return 1
    print("[ok] OAuth profile is ready")
    return 0


def _print_chat_help() -> None:
    print("Chat commands:")
    print("  /help      Show this help")
    print("  /session   Show current session id")
    print("  /exit      Exit chat")


def cmd_chat(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    session_dir = _resolve_session_dir(cfg, args.session_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)

    provider, model = _resolve_runtime_provider(cfg)
    sessions_cfg = cfg.get("sessions", {})
    sessions_cfg = sessions_cfg if isinstance(sessions_cfg, dict) else {}
    configured_max_turns = sessions_cfg.get("max_context_turns", DEFAULT_SESSION_CONTEXT_TURNS)
    max_turns = args.max_context_turns if args.max_context_turns else configured_max_turns
    if not isinstance(max_turns, int) or max_turns < 2:
        max_turns = DEFAULT_SESSION_CONTEXT_TURNS
    response_profile, response_profile_source = _resolve_response_profile(
        cfg,
        storage_dir,
        override=args.response_profile,
    )
    system_prompt = _response_profile_system_prompt(response_profile, response_profile_source)

    session: Optional[Dict[str, Any]] = None
    if args.resume:
        target_session_id = _resolve_resume_session_id(session_dir, str(args.resume))
        if not target_session_id:
            print("No session available to resume.", file=sys.stderr)
            return 1
        session = _load_session(session_dir, target_session_id)
        if session is None:
            print(f"Session not found: {target_session_id}", file=sys.stderr)
            return 1
        if args.response_profile:
            session["response_profile"] = response_profile
            session["response_profile_source"] = response_profile_source
        else:
            session_profile = _normalize_response_profile_token(str(session.get("response_profile", "")))
            if session_profile and session_profile != "auto":
                response_profile = session_profile
                response_profile_source = "session"
                system_prompt = _response_profile_system_prompt(response_profile, response_profile_source)
            else:
                session["response_profile"] = response_profile
                session["response_profile_source"] = response_profile_source
        print(f"Resumed session: {target_session_id}")
    else:
        session = _create_session(provider=provider, model=model)
        session["response_profile"] = response_profile
        session["response_profile_source"] = response_profile_source
        _save_session(session_dir, session)
        print(f"Started session: {session['id']}")

    assert session is not None
    print(f"Provider: {provider} | Model: {model}")
    print(f"Response profile: {response_profile} ({response_profile_source})")
    print("Type /help for commands.")

    while True:
        try:
            raw = input("you> ")
        except EOFError:
            print("")
            break
        except KeyboardInterrupt:
            print("")
            break

        user_input = raw.strip()
        if not user_input:
            continue
        if user_input in ("/exit", "exit", "quit"):
            break
        if user_input in ("/help", "help"):
            _print_chat_help()
            continue
        if user_input == "/session":
            print(session["id"])
            continue

        capture_intent = _captures_note_intent(user_input)
        if capture_intent is not None:
            captured_text, as_task = capture_intent
            if not captured_text:
                guidance = "Provide text after the capture command, for example: capture this as a note: draft agenda"
                print(f"gaia> {guidance}")
                continue

            turn_start = time.perf_counter()
            allowed, permission_level = _enforce_capability(
                cfg=cfg,
                capability="file_write",
                input_summary=user_input,
                trace_dir=trace_dir,
                non_interactive=False,
            )
            if not allowed:
                blocked_reply = "Action blocked by capability policy."
                print(f"gaia> {blocked_reply}")
                timestamp = datetime.now(timezone.utc).isoformat()
                session["turns"].append({"role": "user", "content": user_input, "timestamp": timestamp})
                session["turns"].append({"role": "assistant", "content": blocked_reply, "timestamp": timestamp})
                session["updated_at"] = timestamp
                _save_session(session_dir, session)
                _write_action_trace(
                    trace_dir=trace_dir,
                    action_type="chat_turn",
                    input_summary=user_input,
                    output_summary=blocked_reply,
                    duration_ms=(time.perf_counter() - turn_start) * 1000,
                    permission_level=permission_level,
                    status="blocked",
                    metadata={
                        "session_id": session["id"],
                        "provider": provider,
                        "model": model,
                        "response_profile": response_profile,
                        "response_profile_source": response_profile_source,
                    },
                )
                continue

            if as_task:
                items = _load_records(_tasks_path(storage_dir))
                record = _create_task_record(captured_text, source="chat")
                items.append(record)
                _save_records(_tasks_path(storage_dir), items)
                reply = f"Captured task {record['id']}"
                action_type = "task_capture"
            else:
                items = _load_records(_notes_path(storage_dir))
                record = _create_note_record(captured_text, source="chat")
                items.append(record)
                _save_records(_notes_path(storage_dir), items)
                reply = f"Captured note {record['id']}"
                action_type = "note_capture"

            print(f"gaia> {reply}")
            timestamp = datetime.now(timezone.utc).isoformat()
            session["turns"].append({"role": "user", "content": user_input, "timestamp": timestamp})
            session["turns"].append({"role": "assistant", "content": reply, "timestamp": timestamp})
            session["updated_at"] = timestamp
            _save_session(session_dir, session)
            _write_action_trace(
                trace_dir=trace_dir,
                action_type=action_type,
                input_summary=user_input,
                output_summary=reply,
                duration_ms=(time.perf_counter() - turn_start) * 1000,
                permission_level=permission_level,
                metadata={
                    "session_id": session["id"],
                    "source": "chat",
                    "response_profile": response_profile,
                    "response_profile_source": response_profile_source,
                },
            )
            continue

        capability, confirm_prompt = _infer_capability_from_prompt(user_input)
        turn_start = time.perf_counter()
        allowed, permission_level = _enforce_capability(
            cfg=cfg,
            capability=capability,
            input_summary=user_input,
            trace_dir=trace_dir,
            non_interactive=False,
            prompt=confirm_prompt,
        )
        if not allowed:
            blocked_reply = "Action blocked by capability policy."
            print(f"gaia> {blocked_reply}")
            timestamp = datetime.now(timezone.utc).isoformat()
            session["turns"].append({"role": "user", "content": user_input, "timestamp": timestamp})
            session["turns"].append({"role": "assistant", "content": blocked_reply, "timestamp": timestamp})
            session["updated_at"] = timestamp
            _save_session(session_dir, session)
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="chat_turn",
                input_summary=user_input,
                output_summary=blocked_reply,
                duration_ms=(time.perf_counter() - turn_start) * 1000,
                permission_level=permission_level,
                status="blocked",
                metadata={
                    "session_id": session["id"],
                    "provider": provider,
                    "model": model,
                    "response_profile": response_profile,
                    "response_profile_source": response_profile_source,
                },
            )
            continue

        messages = _build_context_messages(
            session["turns"],
            user_input,
            max_turns=max_turns,
            system_prompt=system_prompt,
        )
        status = "ok"
        try:
            assistant_reply = _reasoning_response(
                provider=provider,
                model=model,
                messages=messages,
                cfg_path=cfg_path,
                secret_store_override=args.secret_store,
            )
        except ProviderTokenLimitError:
            compact_turns = session["turns"][-max(4, max_turns // 2) :]
            compact_messages = _build_context_messages(
                compact_turns,
                user_input,
                max_turns=max(4, max_turns // 2),
                system_prompt=system_prompt,
            )
            try:
                assistant_reply = _reasoning_response(
                    provider=provider,
                    model=model,
                    messages=compact_messages,
                    cfg_path=cfg_path,
                    secret_store_override=args.secret_store,
                )
                status = "ok"
            except ProviderError as exc:
                assistant_reply = f"[provider-error] {exc}"
                status = "error"
        except ProviderError as exc:
            assistant_reply = f"[provider-error] {exc}"
            status = "error"

        print(f"gaia> {assistant_reply}")
        timestamp = datetime.now(timezone.utc).isoformat()
        session["turns"].append({"role": "user", "content": user_input, "timestamp": timestamp})
        session["turns"].append({"role": "assistant", "content": assistant_reply, "timestamp": timestamp})
        session["updated_at"] = timestamp
        _save_session(session_dir, session)
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="chat_turn",
            input_summary=user_input,
            output_summary=assistant_reply,
            duration_ms=(time.perf_counter() - turn_start) * 1000,
            permission_level=permission_level,
            status=status,
            metadata={
                "session_id": session["id"],
                "provider": provider,
                "model": model,
                "context_messages": len(messages),
                "response_profile": response_profile,
                "response_profile_source": response_profile_source,
            },
        )

    _save_session(session_dir, session)
    print(f"Session saved: {session['id']}")
    return 0


def cmd_config_get(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg)
    start = time.perf_counter()
    key = str(args.key).strip().lower()
    path = _config_path_for_key(key)
    if path is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="config_get",
            input_summary=f"key={key}",
            output_summary="unsupported key",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print(
            "Unsupported key. Supported keys: "
            + ", ".join(sorted(PROFILE_KEY_MAP.keys())),
            file=sys.stderr,
        )
        return 1

    value = _get_nested_value(cfg, path)
    if value is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="config_get",
            input_summary=f"key={key}",
            output_summary="empty value",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
        )
        print("", end="")
        return 0
    if isinstance(value, (dict, list)):
        print(json.dumps(value, indent=2))
    else:
        print(value)
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="config_get",
        input_summary=f"key={key}",
        output_summary=f"value={_summarize_text(value)}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level="safe",
    )
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg)
    start = time.perf_counter()
    key = str(args.key).strip().lower()
    path = _config_path_for_key(key)
    if path is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="config_set",
            input_summary=f"key={key}",
            output_summary="unsupported key",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print(
            "Unsupported key. Supported keys: "
            + ", ".join(sorted(PROFILE_KEY_MAP.keys())),
            file=sys.stderr,
        )
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary=f"config set {key}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="config_set",
            input_summary=f"key={key}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    normalized, error = _normalize_config_value(key, str(args.value))
    if error:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="config_set",
            input_summary=f"key={key}",
            output_summary=error,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(error, file=sys.stderr)
        return 1
    assert normalized is not None
    _set_nested_value(cfg, path, normalized)

    if key in ("provider", "default_provider"):
        reasoning = cfg.setdefault("reasoning", {})
        if not isinstance(reasoning, dict):
            reasoning = {}
            cfg["reasoning"] = reasoning
        reasoning["provider"] = normalized
        reasoning["model"] = _default_model_for_provider(normalized)
        reasoning["explicit_provider_override"] = True

    _write_json(cfg_path, _normalize_config(cfg))
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="config_set",
        input_summary=f"key={key}",
        output_summary=f"set to {normalized}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    print(f"{path[0]}.{path[1]}={normalized}")
    return 0


def _log_permission_decision(
    trace_dir: Path,
    capability: str,
    input_summary: str,
    allowed: bool,
    permission_level: str,
    reason: str,
    duration_ms: float,
) -> None:
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="permission_decision",
        input_summary=f"{capability}: {input_summary}",
        output_summary=reason,
        duration_ms=duration_ms,
        permission_level=permission_level,
        status="ok" if allowed else "blocked",
        metadata={"capability": capability, "allowed": allowed},
    )


def _enforce_capability(
    cfg: Dict[str, Any],
    capability: str,
    input_summary: str,
    trace_dir: Path,
    non_interactive: bool = False,
    prompt: Optional[str] = None,
) -> Tuple[bool, str]:
    start = time.perf_counter()
    allowed, level, reason = _check_capability_permission(
        cfg=cfg,
        capability=capability,
        user_prompt=prompt,
        non_interactive=non_interactive,
    )
    duration_ms = (time.perf_counter() - start) * 1000
    _log_permission_decision(
        trace_dir=trace_dir,
        capability=capability,
        input_summary=input_summary,
        allowed=allowed,
        permission_level=level,
        reason=reason,
        duration_ms=duration_ms,
    )
    return allowed, level


def cmd_capability_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary="capability list",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="capability_list",
            input_summary="capability list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    registry = _capability_registry(cfg)
    for capability in sorted(registry):
        print(f"{capability} {registry[capability]}")
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="capability_list",
        input_summary="capability list",
        output_summary=f"{len(registry)} capabilities",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    return 0


def cmd_capability_set(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg)
    start = time.perf_counter()
    capability = str(args.capability).strip()
    if not capability:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="capability_set",
            input_summary="capability empty",
            output_summary="capability cannot be empty",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print("capability cannot be empty", file=sys.stderr)
        return 1

    level = str(args.level).strip().lower()
    if level not in PERMISSION_LEVEL_CHOICES:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="capability_set",
            input_summary=f"{capability}={level}",
            output_summary="invalid level",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print(
            f"Invalid level '{args.level}'. "
            f"Expected one of: {', '.join(PERMISSION_LEVEL_CHOICES)}.",
            file=sys.stderr,
        )
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary=f"capability set {capability}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="capability_set",
            input_summary=f"{capability}={level}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    capabilities = cfg.setdefault("capabilities", {})
    if not isinstance(capabilities, dict):
        capabilities = {}
        cfg["capabilities"] = capabilities
    overrides = capabilities.setdefault("overrides", {})
    if not isinstance(overrides, dict):
        overrides = {}
        capabilities["overrides"] = overrides
    overrides[capability] = level
    _write_json(cfg_path, _normalize_config(cfg))
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="capability_set",
        input_summary=f"{capability}={level}",
        output_summary="override updated",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    print(f"capabilities.overrides.{capability}={level}")
    return 0


def _parse_policy_tools(raw: str) -> Tuple[Optional[List[str]], Optional[str]]:
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not values:
        return None, "tools list cannot be empty"
    deduped: List[str] = []
    seen: set[str] = set()
    for tool in values:
        if tool not in POLICY_TOOL_CHOICES:
            return None, (
                f"Invalid tool '{tool}'. Expected one of: {', '.join(POLICY_TOOL_CHOICES)}."
            )
        if tool in seen:
            continue
        seen.add(tool)
        deduped.append(tool)
    return deduped, None


def cmd_policy_evaluate(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    skill_id = ""
    source = _normalize_policy_source(args.source)
    scanned_roots: List[str] = []
    if args.skill:
        skill_ctx, error_message, scanned_roots = _resolve_policy_skill_reference(
            cfg,
            str(args.skill),
            source_filter=str(args.skill_source),
        )
        if skill_ctx is None:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="policy_evaluate",
                input_summary=f"skill={args.skill}",
                output_summary=error_message or "skill resolution failed",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="error",
            )
            print(error_message or "Unable to resolve skill reference.", file=sys.stderr)
            return 1
        skill_id = str(skill_ctx.get("skill_id", "")).strip()
        source = _normalize_policy_source(str(skill_ctx.get("source", source)))

    decision = _evaluate_policy_decision(
        cfg,
        tool=str(args.tool),
        source=source,
        user_scope=str(args.scope),
        skill_id=skill_id,
    )
    if args.as_json:
        print(json.dumps(decision, indent=2))
    else:
        print(
            f"decision={decision.get('decision')} policy_id={decision.get('policy_id')} "
            f"tool={decision.get('tool')} source={decision.get('source')} scope={decision.get('scope')}"
        )
        print(f"reason={decision.get('reason')}")
        explanations = decision.get("explanations", [])
        if isinstance(explanations, list):
            for item in explanations:
                print(f"- {item}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="policy_evaluate",
        input_summary=f"tool={args.tool} source={source} scope={args.scope}",
        output_summary=f"{decision.get('decision')} ({decision.get('policy_id')})",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level="safe",
        status="ok" if decision.get("decision") != "deny" else "blocked",
        metadata=_with_trace_metadata(
            {
                "decision": decision,
                "skill": args.skill,
                "skill_id": skill_id,
                "scanned_roots": scanned_roots,
            },
            skill_id=skill_id,
            skill_source=source,
            policy_decision=str(decision.get("decision", "")),
            policy_id=str(decision.get("policy_id", "")),
        ),
    )
    return 0 if decision.get("decision") != "deny" else 1


def cmd_policy_allowlist_set(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="policy allowlist set",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="policy_allowlist_set",
            input_summary=f"skill={args.skill}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    tools, parse_error = _parse_policy_tools(str(args.tools))
    if parse_error:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="policy_allowlist_set",
            input_summary=f"skill={args.skill}",
            output_summary=parse_error,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(parse_error, file=sys.stderr)
        return 1
    assert tools is not None

    skill_ctx, error_message, scanned_roots = _resolve_policy_skill_reference(
        cfg,
        str(args.skill),
        source_filter=str(args.skill_source),
    )
    if skill_ctx is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="policy_allowlist_set",
            input_summary=f"skill={args.skill}",
            output_summary=error_message or "skill resolution failed",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(error_message or "Unable to resolve skill reference.", file=sys.stderr)
        return 1

    skill_id = str(skill_ctx.get("skill_id", "")).strip()
    allowlists = _policy_allowlists(cfg)
    allowlists[skill_id] = tools
    cfg.setdefault("policy", {})["skill_tool_allowlists"] = allowlists
    _write_json(cfg_path, _normalize_config(cfg))

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="policy_allowlist_set",
        input_summary=f"skill={skill_id}",
        output_summary=f"{len(tools)} tools",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_with_trace_metadata(
            {"skill_id": skill_id, "tools": tools, "scanned_roots": scanned_roots},
            skill_id=skill_id,
            skill_source=str(skill_ctx.get("source", "")),
        ),
    )
    print(f"{skill_id}: {', '.join(tools)}")
    return 0


def cmd_policy_allowlist_clear(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="policy allowlist clear",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="policy_allowlist_clear",
            input_summary=f"skill={args.skill}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    skill_ctx, error_message, scanned_roots = _resolve_policy_skill_reference(
        cfg,
        str(args.skill),
        source_filter=str(args.skill_source),
    )
    if skill_ctx is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="policy_allowlist_clear",
            input_summary=f"skill={args.skill}",
            output_summary=error_message or "skill resolution failed",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(error_message or "Unable to resolve skill reference.", file=sys.stderr)
        return 1

    skill_id = str(skill_ctx.get("skill_id", "")).strip()
    allowlists = _policy_allowlists(cfg)
    removed = skill_id in allowlists
    allowlists.pop(skill_id, None)
    cfg.setdefault("policy", {})["skill_tool_allowlists"] = allowlists
    _write_json(cfg_path, _normalize_config(cfg))

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="policy_allowlist_clear",
        input_summary=f"skill={skill_id}",
        output_summary="removed" if removed else "not found",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_with_trace_metadata(
            {"skill_id": skill_id, "removed": removed, "scanned_roots": scanned_roots},
            skill_id=skill_id,
            skill_source=str(skill_ctx.get("source", "")),
        ),
    )
    if removed:
        print(f"{skill_id}: cleared")
    else:
        print(f"{skill_id}: no allowlist entry")
    return 0


def cmd_policy_allowlist_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    allowlists = _policy_allowlists(cfg)
    if args.skill:
        skill_ctx, error_message, scanned_roots = _resolve_policy_skill_reference(
            cfg,
            str(args.skill),
            source_filter=str(args.skill_source),
        )
        if skill_ctx is None:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="policy_allowlist_list",
                input_summary=f"skill={args.skill}",
                output_summary=error_message or "skill resolution failed",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="error",
            )
            print(error_message or "Unable to resolve skill reference.", file=sys.stderr)
            return 1
        skill_id = str(skill_ctx.get("skill_id", "")).strip()
        selected = {skill_id: allowlists.get(skill_id, [])}
        metadata: Dict[str, Any] = {
            "skill_id": skill_id,
            "skill_source": str(skill_ctx.get("source", "")),
            "scanned_roots": scanned_roots,
        }
    else:
        selected = dict(sorted(allowlists.items()))
        metadata = {"count": len(selected)}

    if args.as_json:
        print(json.dumps(selected, indent=2))
    elif not selected:
        print("No policy skill allowlists configured.")
    else:
        for skill_id in sorted(selected):
            tools = selected.get(skill_id, [])
            if isinstance(tools, list):
                print(f"{skill_id}: {', '.join(tools) if tools else '(empty)'}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="policy_allowlist_list",
        input_summary="policy allowlist list",
        output_summary=f"{len(selected)} entries",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level="safe",
        metadata=_with_trace_metadata(
            metadata,
            skill_id=str(metadata.get("skill_id", "")) if isinstance(metadata, dict) else None,
            skill_source=str(metadata.get("skill_source", "")) if isinstance(metadata, dict) else None,
        ),
    )
    return 0


def cmd_traces(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    traces = _read_action_traces(trace_dir)
    if args.type:
        wanted = str(args.type).strip()
        traces = [item for item in traces if str(item.get("action_type", "")).strip() == wanted]

    if args.skill_id:
        wanted_skill_id = str(args.skill_id).strip()
        traces = [item for item in traces if _trace_skill_id(item) == wanted_skill_id]

    if args.skill_source and str(args.skill_source).strip().lower() != "all":
        wanted_skill_source = str(args.skill_source).strip().lower()
        traces = [item for item in traces if _trace_skill_source(item) == wanted_skill_source]

    if args.policy_decision:
        wanted_policy_decision = str(args.policy_decision).strip().lower()
        traces = [item for item in traces if _trace_policy_decision(item) == wanted_policy_decision]

    if args.sandbox_profile:
        wanted_profile = str(args.sandbox_profile).strip().lower()
        traces = [item for item in traces if _trace_sandbox_profile(item) == wanted_profile]

    if args.correlation_id:
        wanted_correlation_id = str(args.correlation_id).strip()
        traces = [item for item in traces if _trace_correlation_id(item) == wanted_correlation_id]

    if args.last and args.last > 0:
        traces = traces[-args.last :]

    if not traces:
        if args.as_json:
            print("[]")
        else:
            print(f"No traces found in {trace_dir}")
        return 0

    if args.as_json:
        print(json.dumps(traces, indent=2))
        return 0

    for item in traces:
        ts = str(item.get("timestamp", "?")).strip()
        action_type = str(item.get("action_type", "?")).strip()
        level = str(item.get("permission_level", "?")).strip()
        status = str(item.get("status", "?")).strip()
        corr = _trace_correlation_id(item)
        corr_label = corr[:8] if corr else "-"
        summary = _summarize_text(item.get("output_summary", ""), max_chars=100)
        print(f"{ts} | {action_type:<20} | {level:<9} | {status:<7} | {corr_label:<8} | {summary}")
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    text = str(args.text).strip()
    if not text:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="note_capture",
            input_summary="empty input",
            output_summary="text cannot be empty",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print("note text cannot be empty", file=sys.stderr)
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary=f"note capture: {text}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="note_capture",
            input_summary=text,
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    if args.task:
        path = _tasks_path(storage_dir)
        items = _load_records(path)
        record = _create_task_record(text, source="cli")
        items.append(record)
        _save_records(path, items)
        action_type = "task_capture"
        print(f"{record['id']} open {record['text']}")
    else:
        path = _notes_path(storage_dir)
        items = _load_records(path)
        record = _create_note_record(text, source="cli")
        items.append(record)
        _save_records(path, items)
        action_type = "note_capture"
        print(f"{record['id']} {record['text']}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type=action_type,
        input_summary=text,
        output_summary=f"saved {record['id']}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"source": "cli"},
    )
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary="list tasks",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="tasks_list",
            input_summary="tasks list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    tasks = _load_records(_tasks_path(storage_dir))
    status = str(args.status).strip().lower()
    if status not in ("open", "done", "all"):
        status = "open"

    if status != "all":
        tasks = [item for item in tasks if str(item.get("status", "open")).strip().lower() == status]

    query = str(args.q or "").strip().lower()
    if query:
        tasks = [item for item in tasks if query in str(item.get("text", "")).lower()]

    since_dt = None
    if args.since:
        since_dt = _parse_since_date(str(args.since))
        if since_dt is None:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="tasks_list",
                input_summary=f"since={args.since}",
                output_summary="invalid --since date",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print("Invalid --since value. Use YYYY-MM-DD.", file=sys.stderr)
            return 1
        tasks = [
            item
            for item in tasks
            if str(item.get("created_at", ""))[:10] >= since_dt.date().isoformat()
        ]

    tasks.sort(key=lambda item: str(item.get("created_at", "")))
    if not tasks:
        print("No tasks found.")
    else:
        for task in tasks:
            task_id = str(task.get("id", "?"))
            task_status = str(task.get("status", "open"))
            created = str(task.get("created_at", "?"))
            text = str(task.get("text", ""))
            print(f"{task_id} {task_status:<4} {created} {text}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="tasks_list",
        input_summary=f"status={status} query={query}",
        output_summary=f"{len(tasks)} tasks",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    return 0


def _feedback_trace_metadata(
    *,
    feedback_id: Optional[str] = None,
    label: Optional[str] = None,
    session_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    correction_present: Optional[bool] = None,
    correction_length: Optional[int] = None,
    result_count: Optional[int] = None,
    limit: Optional[int] = None,
    with_correction: Optional[bool] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    if feedback_id:
        metadata["feedback_id"] = feedback_id
    if label:
        metadata["feedback_label"] = label
    if session_id:
        metadata["session_id"] = session_id
    if trace_id:
        metadata["linked_trace_id"] = trace_id
    if correction_present is not None:
        metadata["correction_present"] = bool(correction_present)
    if correction_length is not None:
        metadata["correction_length"] = int(correction_length)
    if result_count is not None:
        metadata["result_count"] = int(result_count)
    if limit is not None:
        metadata["limit"] = int(limit)
    if with_correction is not None:
        metadata["with_correction"] = bool(with_correction)
    return _with_trace_metadata(metadata=metadata)


def _resolve_feedback_session_id(session_dir: Path, session_ref: Optional[str]) -> Tuple[str, Optional[str]]:
    requested = str(session_ref or "").strip()
    if not requested:
        return "", None
    if requested.lower() == "last":
        resolved = _resolve_resume_session_id(session_dir, "last")
        if not resolved:
            return "", "No session available to resolve --session-id last."
        requested = resolved
    if _load_session(session_dir, requested) is None:
        return "", f"Session not found: {requested}"
    return requested, None


def _latest_feedback_session_id(session_dir: Path) -> str:
    resolved = _resolve_resume_session_id(session_dir, "last")
    if not resolved:
        return ""
    if _load_session(session_dir, resolved) is None:
        return ""
    return resolved


def _trace_id_exists(trace_dir: Path, trace_id: str) -> bool:
    wanted = str(trace_id).strip()
    if not wanted:
        return False
    traces = _read_action_traces(trace_dir)
    return any(str(item.get("id", "")).strip() == wanted for item in traces)


def _normalize_feedback_records(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get("id", "")).strip()
        if not record_id:
            continue
        try:
            label = _normalize_feedback_label(str(item.get("label", "")))
        except ValueError:
            continue
        correction = str(item.get("correction", "")).strip()
        created_at = str(item.get("created_at", "")).strip()
        raw_schema = item.get("schema_version", FEEDBACK_SCHEMA_VERSION)
        schema_version = FEEDBACK_SCHEMA_VERSION
        try:
            schema_version = int(raw_schema)
        except (TypeError, ValueError):
            schema_version = FEEDBACK_SCHEMA_VERSION
        normalized.append(
            {
                "id": record_id,
                "label": label,
                "correction": correction,
                "session_id": str(item.get("session_id", "")).strip(),
                "trace_id": str(item.get("trace_id", "")).strip(),
                "created_at": created_at,
                "updated_at": str(item.get("updated_at", created_at)).strip(),
                "source": str(item.get("source", "cli")).strip() or "cli",
                "schema_version": schema_version,
            }
        )
    return normalized


def _signals_settings(cfg: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_config(cfg)
    raw = normalized.get("signals", {})
    signals = raw if isinstance(raw, dict) else {}
    return {
        "enabled": _normalize_bool_default(signals.get("enabled", True), True),
        "retention_days": _normalize_int_default(
            signals.get("retention_days", SIGNALS_RETENTION_DAYS_DEFAULT),
            default_value=SIGNALS_RETENTION_DAYS_DEFAULT,
            min_value=SIGNALS_RETENTION_DAYS_MIN,
            max_value=SIGNALS_RETENTION_DAYS_MAX,
        ),
        "max_records": _normalize_int_default(
            signals.get("max_records", SIGNALS_MAX_RECORDS_DEFAULT),
            default_value=SIGNALS_MAX_RECORDS_DEFAULT,
            min_value=SIGNALS_MAX_RECORDS_MIN,
            max_value=SIGNALS_MAX_RECORDS_MAX,
        ),
    }


def _parse_optional_datetime_utc(raw: Any) -> Optional[datetime]:
    value = str(raw or "").strip()
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_signal_intent_tag(raw: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "_", str(raw).strip().lower()).strip("._-")
    return value or "unknown"


def _signal_id(signal_type: str, intent_tag: str) -> str:
    digest = hashlib.sha256(f"{signal_type}:{intent_tag}".encode("utf-8")).hexdigest()
    return f"sig-{digest[:12]}"


def _signal_confidence(signal_type: str, count: int) -> float:
    base = {
        "feedback_not_helpful": 0.55,
        "feedback_correction_pattern": 0.65,
        "command_failure": 0.60,
    }.get(signal_type, 0.50)
    bonus = min(0.35, max(count - 1, 0) * 0.05)
    return round(min(0.99, base + bonus), 3)


def _feedback_correction_intent_tags(correction: str) -> List[str]:
    text = str(correction).strip().lower()
    if not text:
        return []
    tags: List[str] = []
    for tag, keywords in SIGNALS_CORRECTION_TAG_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags.append("response_quality.other")
    return sorted(set(tags))


def _trace_failure_intent_tag(trace: Dict[str, Any]) -> str:
    action_type = str(trace.get("action_type", "")).strip().lower()
    status = str(trace.get("status", "")).strip().lower()
    metadata = _trace_metadata(trace)
    policy_decision = str(metadata.get("policy_decision", "")).strip().lower()
    if policy_decision == "deny":
        return "policy.denied"
    if policy_decision == "confirm":
        return "policy.confirmation_required"
    if action_type == "permission_decision" and status == "blocked":
        capability = str(metadata.get("capability", "")).strip().lower()
        if capability:
            return f"capability.{_normalize_signal_intent_tag(capability)}.blocked"
        return "capability.blocked"
    if action_type.startswith("memory_"):
        return f"memory.{_normalize_signal_intent_tag(action_type)}"
    if action_type.startswith("skill"):
        return f"skills.{_normalize_signal_intent_tag(action_type)}"
    if action_type.startswith("sandbox"):
        return f"sandbox.{_normalize_signal_intent_tag(action_type)}"
    if action_type.startswith("auth_"):
        return f"auth.{_normalize_signal_intent_tag(action_type)}"
    if action_type:
        return f"command.{_normalize_signal_intent_tag(action_type)}"
    return "command.unknown"


def _signal_sort_key(item: Dict[str, Any]) -> Tuple[int, float, str, str]:
    count = int(item.get("count", 0) or 0)
    last_seen = _parse_optional_datetime_utc(item.get("last_seen_at"))
    last_seen_epoch = last_seen.timestamp() if last_seen else 0.0
    return (
        -count,
        -last_seen_epoch,
        str(item.get("signal_type", "")),
        str(item.get("intent_tag", "")),
    )


def _build_unmet_intent_signals(
    *,
    feedback_records: List[Dict[str, Any]],
    action_traces: List[Dict[str, Any]],
    now: datetime,
    retention_days: int,
    max_records: int,
) -> List[Dict[str, Any]]:
    cutoff = now - timedelta(days=max(retention_days, 1))
    buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def ingest(
        signal_type: str,
        intent_tag: str,
        *,
        source: str,
        event_id: str,
        event_time: Optional[datetime],
    ) -> None:
        if signal_type not in SIGNALS_TYPE_CHOICES:
            return
        if event_time is None or event_time < cutoff:
            return
        normalized_event_id = str(event_id).strip()
        if not normalized_event_id:
            return
        key = (signal_type, _normalize_signal_intent_tag(intent_tag))
        bucket = buckets.setdefault(
            key,
            {
                "signal_type": signal_type,
                "intent_tag": key[1],
                "count": 0,
                "first_seen": event_time,
                "last_seen": event_time,
                "_seen_ids": set(),
                "_events": [],
            },
        )
        event_ref = f"{source}:{normalized_event_id}"
        seen_ids = bucket["_seen_ids"]
        if event_ref in seen_ids:
            return
        seen_ids.add(event_ref)
        bucket["count"] += 1
        if event_time < bucket["first_seen"]:
            bucket["first_seen"] = event_time
        if event_time > bucket["last_seen"]:
            bucket["last_seen"] = event_time
        bucket["_events"].append((event_time, event_ref))

    for record in feedback_records:
        event_time = _parse_optional_datetime_utc(
            record.get("created_at") or record.get("updated_at")
        )
        event_id = str(record.get("id", "")).strip()
        label = str(record.get("label", "")).strip().lower()
        if label == "not-helpful":
            ingest(
                "feedback_not_helpful",
                "response_quality.unsatisfied",
                source="feedback",
                event_id=event_id,
                event_time=event_time,
            )
        correction = str(record.get("correction", "")).strip()
        for intent_tag in _feedback_correction_intent_tags(correction):
            ingest(
                "feedback_correction_pattern",
                intent_tag,
                source="feedback",
                event_id=event_id,
                event_time=event_time,
            )

    for trace in action_traces:
        status = str(trace.get("status", "")).strip().lower()
        if status not in ("error", "blocked"):
            continue
        event_time = _parse_optional_datetime_utc(trace.get("timestamp"))
        event_id = str(trace.get("id", "")).strip()
        ingest(
            "command_failure",
            _trace_failure_intent_tag(trace),
            source="trace",
            event_id=event_id,
            event_time=event_time,
        )

    signals: List[Dict[str, Any]] = []
    for bucket in buckets.values():
        events = sorted(
            bucket["_events"],
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )[:SIGNALS_MAX_EVENT_IDS_PER_SIGNAL]
        count = int(bucket["count"])
        signals.append(
            {
                "signal_id": _signal_id(bucket["signal_type"], bucket["intent_tag"]),
                "signal_type": bucket["signal_type"],
                "intent_tag": bucket["intent_tag"],
                "confidence": _signal_confidence(bucket["signal_type"], count),
                "count": count,
                "first_seen_at": _isoformat_utc(bucket["first_seen"]),
                "last_seen_at": _isoformat_utc(bucket["last_seen"]),
                "source_event_ids": [event_id for _, event_id in events],
                "source_event_count": count,
                "schema_version": SIGNALS_SCHEMA_VERSION,
            }
        )

    signals.sort(key=_signal_sort_key)
    bounded_max = _normalize_int_default(
        max_records,
        default_value=SIGNALS_MAX_RECORDS_DEFAULT,
        min_value=SIGNALS_MAX_RECORDS_MIN,
        max_value=SIGNALS_MAX_RECORDS_MAX,
    )
    return signals[:bounded_max]


def _empty_signals_ledger(
    *,
    generated_at: str,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    retention_days = int(settings.get("retention_days", SIGNALS_RETENTION_DAYS_DEFAULT))
    max_records = int(settings.get("max_records", SIGNALS_MAX_RECORDS_DEFAULT))
    return {
        "schema_version": SIGNALS_LEDGER_SCHEMA_VERSION,
        "generated_at": generated_at,
        "collection_enabled": bool(settings.get("enabled", True)),
        "retention_days": retention_days,
        "max_records": max_records,
        "signal_count": 0,
        "signals": [],
        "source_summary": {
            "window_start_at": "",
            "feedback_records_scanned": 0,
            "action_traces_scanned": 0,
        },
    }


def _normalize_signals_records(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        signal_type = str(item.get("signal_type", "")).strip().lower()
        if signal_type not in SIGNALS_TYPE_CHOICES:
            continue
        intent_tag = _normalize_signal_intent_tag(str(item.get("intent_tag", "")))
        if not intent_tag:
            continue
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = round(min(max(confidence, 0.0), 1.0), 3)
        count = _normalize_int_default(
            item.get("count", 1),
            default_value=1,
            min_value=1,
            max_value=1_000_000,
        )
        first_seen = _parse_optional_datetime_utc(item.get("first_seen_at"))
        last_seen = _parse_optional_datetime_utc(item.get("last_seen_at"))
        if first_seen is None and last_seen is None:
            continue
        if first_seen is None:
            first_seen = last_seen
        if last_seen is None:
            last_seen = first_seen
        source_event_ids: List[str] = []
        raw_event_ids = item.get("source_event_ids", [])
        if isinstance(raw_event_ids, list):
            for raw_event in raw_event_ids:
                event_id = str(raw_event).strip()
                if not event_id or event_id in source_event_ids:
                    continue
                source_event_ids.append(event_id)
        normalized.append(
            {
                "signal_id": str(item.get("signal_id") or _signal_id(signal_type, intent_tag)).strip(),
                "signal_type": signal_type,
                "intent_tag": intent_tag,
                "confidence": confidence,
                "count": count,
                "first_seen_at": _isoformat_utc(first_seen),
                "last_seen_at": _isoformat_utc(last_seen),
                "source_event_ids": source_event_ids[:SIGNALS_MAX_EVENT_IDS_PER_SIGNAL],
                "source_event_count": max(
                    count,
                    _normalize_int_default(
                        item.get("source_event_count", len(source_event_ids)),
                        default_value=len(source_event_ids),
                        min_value=0,
                        max_value=1_000_000,
                    ),
                ),
                "schema_version": SIGNALS_SCHEMA_VERSION,
            }
        )
    normalized.sort(key=_signal_sort_key)
    return normalized


def _load_signals_ledger(storage_dir: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    settings = _signals_settings(cfg)
    payload = _load_json(_signals_path(storage_dir))
    if not payload or not isinstance(payload, dict):
        return _empty_signals_ledger(generated_at="", settings=settings)
    ledger = _empty_signals_ledger(
        generated_at=str(payload.get("generated_at", "")).strip(),
        settings=settings,
    )
    ledger["signals"] = _normalize_signals_records(payload.get("signals", []))
    ledger["signal_count"] = len(ledger["signals"])
    raw_summary = payload.get("source_summary", {})
    if isinstance(raw_summary, dict):
        ledger["source_summary"] = {
            "window_start_at": str(raw_summary.get("window_start_at", "")).strip(),
            "feedback_records_scanned": _normalize_int_default(
                raw_summary.get("feedback_records_scanned", 0),
                default_value=0,
                min_value=0,
                max_value=1_000_000,
            ),
            "action_traces_scanned": _normalize_int_default(
                raw_summary.get("action_traces_scanned", 0),
                default_value=0,
                min_value=0,
                max_value=1_000_000,
            ),
        }
    return ledger


def _extract_unmet_intent_signals(
    *,
    cfg: Dict[str, Any],
    storage_dir: Path,
    trace_dir: Path,
    persist: bool,
) -> Dict[str, Any]:
    settings = _signals_settings(cfg)
    now = datetime.now(timezone.utc)
    retention_days = int(settings["retention_days"])
    max_records = int(settings["max_records"])
    feedback_records = _normalize_feedback_records(_load_records(_feedback_path(storage_dir)))
    action_traces = _read_action_traces(trace_dir)
    signals = _build_unmet_intent_signals(
        feedback_records=feedback_records,
        action_traces=action_traces,
        now=now,
        retention_days=retention_days,
        max_records=max_records,
    )
    cutoff = now - timedelta(days=retention_days)
    ledger = _empty_signals_ledger(
        generated_at=_isoformat_utc(now),
        settings=settings,
    )
    ledger["signals"] = signals
    ledger["signal_count"] = len(signals)
    ledger["source_summary"] = {
        "window_start_at": _isoformat_utc(cutoff),
        "feedback_records_scanned": len(feedback_records),
        "action_traces_scanned": len(action_traces),
    }
    wrote = False
    if persist and bool(settings["enabled"]):
        _write_json(_signals_path(storage_dir), ledger)
        wrote = True
    ledger["written"] = wrote
    return ledger


def _signal_intent_tokens(raw: str) -> List[str]:
    tokens = [token for token in re.split(r"[^a-z0-9]+", str(raw).strip().lower()) if token]
    return tokens


def _signal_capability_hints(intent_tag: str) -> List[str]:
    normalized = str(intent_tag).strip().lower().replace(".", "_").replace("-", "_")
    hints: List[str] = []
    for capability in POLICY_TOOL_CHOICES:
        if capability in normalized:
            hints.append(capability)
    return sorted(set(hints))


def _skill_contract_tokens(contract: Dict[str, Any]) -> List[str]:
    tokens: List[str] = []
    for field in (
        contract.get("skill_id"),
        contract.get("slug"),
        contract.get("name"),
        contract.get("description"),
    ):
        tokens.extend(_signal_intent_tokens(str(field or "")))
    for capability in contract.get("capabilities", []):
        tokens.extend(_signal_intent_tokens(str(capability)))
    return sorted(set(tokens))


def _latest_validation_reports_by_skill_id(trace_dir: Path) -> Dict[str, Dict[str, Any]]:
    report_dir = _skill_validation_reports_dir(trace_dir)
    if not report_dir.exists() or not report_dir.is_dir():
        return {}

    reports: Dict[str, Dict[str, Any]] = {}
    for report_path in sorted(report_dir.glob("*.json"), reverse=True):
        payload = _load_json(report_path)
        if not isinstance(payload, dict):
            continue
        target = payload.get("target", {})
        if not isinstance(target, dict):
            continue
        skill_id = str(target.get("skill_id", "")).strip()
        if not skill_id or skill_id in reports:
            continue
        summary = payload.get("summary", {})
        blocking_count = 0
        if isinstance(summary, dict):
            blocking_count = _normalize_int_default(
                summary.get("blocking_count", 0),
                default_value=0,
                min_value=0,
                max_value=1_000_000,
            )
        reports[skill_id] = {
            "status": str(payload.get("status", "")).strip().lower(),
            "blocking_count": blocking_count,
            "report_id": str(payload.get("report_id", "")).strip(),
            "generated_at": str(payload.get("generated_at", "")).strip(),
            "report_path": _display_runtime_path(report_path),
        }
    return reports


def _match_signal_skill_candidate(
    *,
    signal: Dict[str, Any],
    contracts: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    intent_tag = str(signal.get("intent_tag", "")).strip().lower()
    if not intent_tag:
        return None
    intent_tokens = set(_signal_intent_tokens(intent_tag))
    capability_hints = _signal_capability_hints(intent_tag)

    best: Optional[Dict[str, Any]] = None
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        capabilities = [
            str(item).strip().lower()
            for item in contract.get("capabilities", [])
            if str(item).strip()
        ]
        capability_hits = [cap for cap in capability_hints if cap in capabilities]
        contract_tokens = set(_skill_contract_tokens(contract))
        overlap = sorted(intent_tokens.intersection(contract_tokens))
        score = (len(capability_hits) * 5) + len(overlap)

        skill_slug = str(contract.get("slug", "")).strip().lower()
        skill_name = str(contract.get("name", "")).strip().lower()
        if skill_slug and skill_slug.replace("-", "_") in intent_tag.replace("-", "_"):
            score += 2
        if skill_name and skill_name.replace("-", "_") in intent_tag.replace("-", "_"):
            score += 2

        if score <= 0:
            continue
        candidate = {
            "contract": contract,
            "score": score,
            "overlap_tokens": overlap[:12],
            "capability_hits": capability_hits,
        }
        if best is None or int(candidate["score"]) > int(best["score"]):
            best = candidate

    if best is None:
        return None
    if int(best["score"]) < 3:
        return None
    return best


def _triage_signal_record(
    *,
    signal: Dict[str, Any],
    contracts: List[Dict[str, Any]],
    validation_index: Dict[str, Dict[str, Any]],
    capability_policy: Dict[str, str],
) -> Dict[str, Any]:
    signal_id = str(signal.get("signal_id", "")).strip()
    signal_type = str(signal.get("signal_type", "")).strip().lower()
    intent_tag = _normalize_signal_intent_tag(str(signal.get("intent_tag", "")))
    signal_confidence = round(
        min(max(float(signal.get("confidence", 0.5) or 0.5), 0.0), 1.0),
        3,
    )
    intent_lower = intent_tag.lower()
    dangerous = any(marker in intent_lower for marker in SIGNALS_TRIAGE_DANGEROUS_MARKERS)
    core_feature = any(intent_lower.startswith(prefix) for prefix in SIGNALS_TRIAGE_CORE_PREFIXES)
    skillish = signal_type == "command_failure" or any(
        intent_lower.startswith(prefix) for prefix in SIGNALS_TRIAGE_SKILLISH_PREFIXES
    )

    match = _match_signal_skill_candidate(signal=signal, contracts=contracts)
    triage_class = "out-of-scope-or-rejected"
    rationale = "Signal does not map to a trusted deterministic remediation path."
    follow_up_action = "reject_without_action"
    security_gate: Dict[str, Any] = {
        "status": "not-required",
        "required_checks": [],
        "reason": "not_applicable",
    }
    matched_skill: Dict[str, Any] = {}
    triage_confidence = signal_confidence

    if dangerous:
        triage_class = "out-of-scope-or-rejected"
        rationale = "Intent tag matches safety-restricted markers and is rejected by policy."
        follow_up_action = "reject_unsafe_request"
        security_gate = {
            "status": "blocked",
            "required_checks": [],
            "reason": "dangerous_intent",
        }
        triage_confidence = max(0.05, signal_confidence - 0.25)
    elif isinstance(match, dict):
        contract = match.get("contract", {})
        contract = contract if isinstance(contract, dict) else {}
        skill_id = str(contract.get("skill_id", "")).strip()
        skill_name = str(contract.get("name", "")).strip()
        capabilities = [
            str(item).strip().lower()
            for item in contract.get("capabilities", [])
            if str(item).strip()
        ]
        forbidden_caps = sorted([cap for cap in capabilities if capability_policy.get(cap, "safe") == "forbidden"])
        validation = validation_index.get(skill_id, {})
        validation_status = str(validation.get("status", "")).strip().lower()
        validation_blocking = _normalize_int_default(
            validation.get("blocking_count", 0),
            default_value=0,
            min_value=0,
            max_value=1_000_000,
        )
        matched_skill = {
            "skill_id": skill_id,
            "name": skill_name,
            "source": str(contract.get("source", "")).strip(),
            "score": int(match.get("score", 0)),
            "capability_hits": list(match.get("capability_hits", [])),
            "overlap_tokens": list(match.get("overlap_tokens", [])),
            "validation_status": validation_status or "missing",
            "validation_blocking_count": validation_blocking,
            "validation_report_id": str(validation.get("report_id", "")).strip(),
            "validation_report_path": str(validation.get("report_path", "")).strip(),
        }

        if forbidden_caps:
            triage_class = "out-of-scope-or-rejected"
            rationale = (
                f"Matched skill '{skill_id}' declares forbidden capabilities "
                f"({', '.join(forbidden_caps)})."
            )
            follow_up_action = "reject_skill_enablement"
            security_gate = {
                "status": "blocked",
                "required_checks": [],
                "reason": "forbidden_capability",
            }
            triage_confidence = max(0.05, signal_confidence - 0.20)
        elif validation_status == "fail" or validation_blocking > 0:
            triage_class = "out-of-scope-or-rejected"
            rationale = (
                f"Matched skill '{skill_id}' has blocking validation findings "
                f"(status={validation_status or 'fail'}, blocking={validation_blocking})."
            )
            follow_up_action = "reject_until_skill_hardening"
            security_gate = {
                "status": "blocked",
                "required_checks": [
                    f"gaia skills validate {skill_id} --json",
                    "Resolve high/critical findings before activation.",
                ],
                "reason": "validation_failed",
            }
            triage_confidence = max(0.05, signal_confidence - 0.18)
        elif validation_status == "pass":
            triage_class = "existing-skill-enable"
            rationale = f"Matched validated skill '{skill_id}' with deterministic token/capability overlap."
            follow_up_action = f"enable_skill:{skill_id}"
            security_gate = {
                "status": "satisfied",
                "required_checks": [f"latest skill validation report pass ({skill_id})"],
                "reason": "validated_existing_skill",
            }
            triage_confidence = min(0.99, signal_confidence + 0.20)
        else:
            triage_class = "existing-skill-enable"
            rationale = (
                f"Matched existing skill '{skill_id}' but no recent validation report was found; "
                "enablement requires validation first."
            )
            follow_up_action = f"validate_then_enable:{skill_id}"
            security_gate = {
                "status": "required",
                "required_checks": [
                    f"gaia skills validate {skill_id} --json",
                    "Require pass with zero blocking findings before activation.",
                ],
                "reason": "missing_validation_evidence",
            }
            triage_confidence = min(0.99, signal_confidence + 0.10)
    elif core_feature:
        triage_class = "core-feature-gap"
        rationale = "Intent maps to assistant core behavior quality/style surface."
        follow_up_action = "open_core_feature_followup"
        security_gate = {
            "status": "not-required",
            "required_checks": [],
            "reason": "core_runtime_evolution",
        }
        triage_confidence = min(0.99, signal_confidence + 0.08)
    elif skillish:
        triage_class = "skill-import-candidate"
        rationale = "Intent appears workflow/tooling-oriented and no trusted local skill match was found."
        follow_up_action = "source_and_validate_skill_candidate"
        security_gate = {
            "status": "required",
            "required_checks": [
                "gaia config set skills_provenance_mode enforce",
                "gaia config set skills_attestation_mode enforce",
                "gaia config set skills_source_health_mode enforce",
                "gaia skills validate <candidate-skill-path> --json",
                "gaia policy evaluate --tool <candidate-capability> --source local --scope standard",
            ],
            "reason": "candidate_import_requires_security_gates",
        }
        triage_confidence = max(0.05, signal_confidence - 0.05)

    triage_confidence = round(min(max(triage_confidence, 0.05), 0.99), 3)
    return {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "intent_tag": intent_tag,
        "signal_confidence": signal_confidence,
        "triage_class": triage_class,
        "triage_confidence": triage_confidence,
        "rationale": rationale,
        "follow_up_action": follow_up_action,
        "security_gate": security_gate,
        "matched_skill": matched_skill,
        "count": _normalize_int_default(
            signal.get("count", 1),
            default_value=1,
            min_value=1,
            max_value=1_000_000,
        ),
        "first_seen_at": str(signal.get("first_seen_at", "")).strip(),
        "last_seen_at": str(signal.get("last_seen_at", "")).strip(),
        "source_event_count": _normalize_int_default(
            signal.get("source_event_count", signal.get("count", 1)),
            default_value=1,
            min_value=0,
            max_value=1_000_000,
        ),
    }


def _triage_class_summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
    summary = {name: 0 for name in SIGNALS_TRIAGE_CLASS_CHOICES}
    for item in items:
        if not isinstance(item, dict):
            continue
        triage_class = str(item.get("triage_class", "")).strip().lower()
        if triage_class in summary:
            summary[triage_class] += 1
    return summary


def _build_signal_triage_ledger(
    *,
    cfg: Dict[str, Any],
    trace_dir: Path,
    source_filter: str,
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    contracts, scanned_roots = _load_skill_contracts(cfg, source_filter=source_filter)
    validation_index = _latest_validation_reports_by_skill_id(trace_dir)
    capability_policy = _capability_registry(cfg)
    triaged = [
        _triage_signal_record(
            signal=signal,
            contracts=contracts,
            validation_index=validation_index,
            capability_policy=capability_policy,
        )
        for signal in signals
        if isinstance(signal, dict)
    ]
    summary = _triage_class_summary(triaged)
    return {
        "schema_version": SIGNALS_TRIAGE_LEDGER_SCHEMA_VERSION,
        "generated_at": _isoformat_utc(datetime.now(timezone.utc)),
        "source_signal_count": len(signals),
        "triage_count": len(triaged),
        "skill_source_filter": source_filter,
        "scanned_skill_roots": scanned_roots,
        "validation_reports_indexed": len(validation_index),
        "class_summary": summary,
        "items": triaged,
    }


def cmd_feedback_record(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    session_dir = _resolve_session_dir(cfg, args.session_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    raw_label = str(args.label).strip()
    try:
        label = _normalize_feedback_label(raw_label)
    except ValueError as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_record",
            input_summary=f"label={raw_label}",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print(str(exc), file=sys.stderr)
        return 1

    correction = str(args.correction or "").strip()
    if len(correction) > FEEDBACK_CORRECTION_MAX_CHARS:
        message = (
            f"Correction text exceeds {FEEDBACK_CORRECTION_MAX_CHARS} characters "
            f"(got {len(correction)})."
        )
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_record",
            input_summary=f"label={label}",
            output_summary=message,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
            metadata=_feedback_trace_metadata(label=label),
        )
        print(message, file=sys.stderr)
        return 1

    session_id, session_error = _resolve_feedback_session_id(session_dir, args.session_id)
    if session_error:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_record",
            input_summary=f"label={label}",
            output_summary=session_error,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
            metadata=_feedback_trace_metadata(label=label),
        )
        print(session_error, file=sys.stderr)
        return 1
    if not session_id:
        session_id = _latest_feedback_session_id(session_dir)

    trace_id = str(args.trace_id or "").strip()
    if trace_id and not _trace_id_exists(trace_dir, trace_id):
        message = f"Trace not found: {trace_id}"
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_record",
            input_summary=f"label={label}",
            output_summary=message,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
            metadata=_feedback_trace_metadata(label=label, session_id=session_id, trace_id=trace_id),
        )
        print(message, file=sys.stderr)
        return 1

    if not session_id and not trace_id:
        message = "Feedback requires --session-id or --trace-id linkage."
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_record",
            input_summary=f"label={label}",
            output_summary=message,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
            metadata=_feedback_trace_metadata(label=label),
        )
        print(message, file=sys.stderr)
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_write",
        input_summary=f"feedback record label={label}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_record",
            input_summary=f"label={label}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
            metadata=_feedback_trace_metadata(label=label, session_id=session_id, trace_id=trace_id),
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": _new_record_id("fb"),
        "label": label,
        "correction": correction,
        "session_id": session_id,
        "trace_id": trace_id,
        "created_at": now,
        "updated_at": now,
        "source": "cli",
        "schema_version": FEEDBACK_SCHEMA_VERSION,
    }
    path = _feedback_path(storage_dir)
    items = _normalize_feedback_records(_load_records(path))
    items.append(record)
    items = _trim_feedback_records(items)
    _save_records(path, items)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="feedback_record",
        input_summary=(
            f"label={label} session={session_id or '-'} trace={trace_id or '-'} "
            f"correction_len={len(correction)}"
        ),
        output_summary=f"saved {record['id']}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_feedback_trace_metadata(
            feedback_id=record["id"],
            label=label,
            session_id=session_id,
            trace_id=trace_id,
            correction_present=bool(correction),
            correction_length=len(correction),
        ),
    )

    try:
        _extract_unmet_intent_signals(
            cfg=cfg,
            storage_dir=storage_dir,
            trace_dir=trace_dir,
            persist=True,
        )
    except Exception:
        # Best-effort refresh; feedback capture must not fail if signal refresh
        # encounters malformed local artifacts.
        pass

    if args.as_json:
        print(json.dumps(record, indent=2))
    else:
        print(
            f"{record['id']} {_feedback_label_display(label)} "
            f"session={session_id or '-'} trace={trace_id or '-'}"
        )
    return 0


def cmd_feedback_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    session_dir = _resolve_session_dir(cfg, args.session_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    label_filter = ""
    if args.label:
        try:
            label_filter = _normalize_feedback_label(str(args.label))
        except ValueError as exc:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="feedback_list",
                input_summary=f"label={args.label}",
                output_summary=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="error",
            )
            print(str(exc), file=sys.stderr)
            return 1

    session_id_filter, session_error = _resolve_feedback_session_id(session_dir, args.session_id)
    if session_error:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_list",
            input_summary=f"session={args.session_id}",
            output_summary=session_error,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
            metadata=_feedback_trace_metadata(label=label_filter),
        )
        print(session_error, file=sys.stderr)
        return 1

    limit = int(args.limit)
    if limit < 1 or limit > FEEDBACK_LIST_MAX_LIMIT:
        message = (
            f"Invalid --limit value {limit}. "
            f"Expected 1..{FEEDBACK_LIST_MAX_LIMIT}."
        )
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_list",
            input_summary=f"limit={limit}",
            output_summary=message,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
            metadata=_feedback_trace_metadata(label=label_filter),
        )
        print(message, file=sys.stderr)
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_read",
        input_summary="feedback list",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="feedback_list",
            input_summary="feedback list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
            metadata=_feedback_trace_metadata(
                label=label_filter,
                session_id=session_id_filter,
                trace_id=str(args.trace_id or "").strip(),
                with_correction=bool(args.with_correction),
            ),
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    trace_id_filter = str(args.trace_id or "").strip()
    records = _normalize_feedback_records(_load_records(_feedback_path(storage_dir)))
    records = _sort_feedback_records(records, descending=True)
    if label_filter:
        records = [item for item in records if str(item.get("label", "")).strip().lower() == label_filter]
    if session_id_filter:
        records = [item for item in records if str(item.get("session_id", "")).strip() == session_id_filter]
    if trace_id_filter:
        records = [item for item in records if str(item.get("trace_id", "")).strip() == trace_id_filter]
    if args.with_correction:
        records = [item for item in records if str(item.get("correction", "")).strip()]
    selected = records[:limit]

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="feedback_list",
        input_summary=(
            f"label={label_filter or '-'} session={session_id_filter or '-'} "
            f"trace={trace_id_filter or '-'} with_correction={bool(args.with_correction)} limit={limit}"
        ),
        output_summary=f"{len(selected)} records",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_feedback_trace_metadata(
            label=label_filter,
            session_id=session_id_filter,
            trace_id=trace_id_filter,
            result_count=len(selected),
            limit=limit,
            with_correction=bool(args.with_correction),
        ),
    )

    if args.as_json:
        print(json.dumps(selected, indent=2))
        return 0

    if not selected:
        print("No feedback records found.")
        return 0

    for record in selected:
        line = (
            f"{record['id']} {_feedback_label_display(str(record.get('label', ''))):<11} "
            f"{str(record.get('created_at', '?')).strip()} "
            f"session={str(record.get('session_id', '')).strip() or '-'} "
            f"trace={str(record.get('trace_id', '')).strip() or '-'}"
        )
        correction = str(record.get("correction", "")).strip()
        if correction:
            line += f" correction={_summarize_text(correction, max_chars=72)}"
        print(line)
    return 0


def _signals_trace_metadata(
    *,
    signal_count: Optional[int] = None,
    triage_count: Optional[int] = None,
    written: Optional[bool] = None,
    collection_enabled: Optional[bool] = None,
    export_id: Optional[str] = None,
    export_path: Optional[str] = None,
    class_summary: Optional[Dict[str, int]] = None,
    cleared: Optional[bool] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    if signal_count is not None:
        metadata["signal_count"] = int(signal_count)
    if triage_count is not None:
        metadata["triage_count"] = int(triage_count)
    if written is not None:
        metadata["written"] = bool(written)
    if collection_enabled is not None:
        metadata["collection_enabled"] = bool(collection_enabled)
    if export_id:
        metadata["export_id"] = export_id
    if export_path:
        metadata["export_path"] = export_path
    if isinstance(class_summary, dict):
        summary: Dict[str, int] = {}
        for triage_class, count in class_summary.items():
            label = str(triage_class).strip().lower()
            if label not in SIGNALS_TRIAGE_CLASS_CHOICES:
                continue
            summary[label] = _normalize_int_default(count, default_value=0, min_value=0, max_value=1_000_000)
        if summary:
            metadata["triage_class_summary"] = summary
    if cleared is not None:
        metadata["cleared"] = bool(cleared)
    return _with_trace_metadata(metadata=metadata)


def cmd_signals_extract(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_write",
        input_summary="signals extract",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="signals_extract",
            input_summary="signals extract",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    result = _extract_unmet_intent_signals(
        cfg=cfg,
        storage_dir=storage_dir,
        trace_dir=trace_dir,
        persist=True,
    )
    signal_count = int(result.get("signal_count", 0))
    written = bool(result.get("written", False))
    collection_enabled = bool(result.get("collection_enabled", True))
    if collection_enabled:
        output_summary = f"derived {signal_count} signals (written={written})"
    else:
        output_summary = "signal collection disabled; no write"

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="signals_extract",
        input_summary="signals extract",
        output_summary=output_summary,
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_signals_trace_metadata(
            signal_count=signal_count,
            written=written,
            collection_enabled=collection_enabled,
        ),
    )

    if args.as_json:
        print(json.dumps(result, indent=2))
        return 0

    if not collection_enabled:
        print(
            "Signal collection is disabled (`signals.enabled=false`); no new signal ledger was written."
        )
    print(
        "signal_count="
        f"{signal_count} written={str(written).lower()} "
        f"retention_days={result.get('retention_days')} max_records={result.get('max_records')}"
    )
    return 0


def cmd_signals_triage(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    limit = int(args.limit)
    if limit < 1 or limit > SIGNALS_LIST_MAX_LIMIT:
        message = (
            f"Invalid --limit value {limit}. "
            f"Expected 1..{SIGNALS_LIST_MAX_LIMIT}."
        )
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="signals_triage",
            input_summary=f"limit={limit}",
            output_summary=message,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print(message, file=sys.stderr)
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_write",
        input_summary="signals triage",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="signals_triage",
            input_summary="signals triage",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    refreshed = False
    if bool(args.refresh):
        _extract_unmet_intent_signals(
            cfg=cfg,
            storage_dir=storage_dir,
            trace_dir=trace_dir,
            persist=True,
        )
        refreshed = True

    signals_ledger = _load_signals_ledger(storage_dir, cfg)
    records = _normalize_signals_records(signals_ledger.get("signals", []))
    triage_ledger = _build_signal_triage_ledger(
        cfg=cfg,
        trace_dir=trace_dir,
        source_filter=str(args.source),
        signals=records,
    )
    triage_path = _signals_triage_path(storage_dir)
    _write_json(triage_path, triage_ledger)

    triage_count = _normalize_int_default(
        triage_ledger.get("triage_count", 0),
        default_value=0,
        min_value=0,
        max_value=1_000_000,
    )
    class_summary = triage_ledger.get("class_summary", {})
    class_summary = class_summary if isinstance(class_summary, dict) else {}

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="signals_triage",
        input_summary=f"source={args.source} refresh={refreshed}",
        output_summary=f"triaged {triage_count} signals",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_signals_trace_metadata(
            signal_count=len(records),
            triage_count=triage_count,
            class_summary=class_summary,
            collection_enabled=bool(signals_ledger.get("collection_enabled", True)),
            written=True,
        ),
    )

    if args.as_json:
        print(json.dumps(triage_ledger, indent=2))
        return 0

    print(
        f"triage_count={triage_count} source_signals={len(records)} "
        f"path={triage_path} refresh={str(refreshed).lower()}"
    )
    items = triage_ledger.get("items", [])
    if not isinstance(items, list):
        items = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        print(
            f"{str(item.get('signal_id', '?')).strip()} "
            f"class={str(item.get('triage_class', '')).strip()} "
            f"confidence={float(item.get('triage_confidence', 0.0)):.3f} "
            f"intent={str(item.get('intent_tag', '')).strip()} "
            f"action={str(item.get('follow_up_action', '')).strip()}"
        )
    return 0


def cmd_signals_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    limit = int(args.limit)
    if limit < 1 or limit > SIGNALS_LIST_MAX_LIMIT:
        message = (
            f"Invalid --limit value {limit}. "
            f"Expected 1..{SIGNALS_LIST_MAX_LIMIT}."
        )
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="signals_list",
            input_summary=f"limit={limit}",
            output_summary=message,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        print(message, file=sys.stderr)
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_read",
        input_summary="signals list",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="signals_list",
            input_summary="signals list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    ledger = _load_signals_ledger(storage_dir, cfg)
    records = _normalize_signals_records(ledger.get("signals", []))
    signal_type_filter = str(args.signal_type or "").strip().lower()
    if signal_type_filter:
        records = [item for item in records if str(item.get("signal_type", "")).strip().lower() == signal_type_filter]
    intent_tag_filter = str(args.intent_tag or "").strip().lower()
    if intent_tag_filter:
        records = [item for item in records if intent_tag_filter in str(item.get("intent_tag", "")).strip().lower()]
    selected = records[:limit]

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="signals_list",
        input_summary=(
            f"type={signal_type_filter or '-'} intent_tag={intent_tag_filter or '-'} "
            f"limit={limit}"
        ),
        output_summary=f"{len(selected)} signals",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_signals_trace_metadata(
            signal_count=len(selected),
            collection_enabled=bool(ledger.get("collection_enabled", True)),
        ),
    )

    if args.as_json:
        print(json.dumps(selected, indent=2))
        return 0

    if not selected:
        print("No unmet-intent signals found.")
        return 0
    for item in selected:
        print(
            f"{str(item.get('signal_id', '?')).strip()} "
            f"{str(item.get('signal_type', '')).strip():<28} "
            f"{str(item.get('intent_tag', '')).strip():<36} "
            f"count={int(item.get('count', 0))} "
            f"confidence={float(item.get('confidence', 0.0)):.3f} "
            f"last={str(item.get('last_seen_at', '-')).strip() or '-'}"
        )
    return 0


def cmd_signals_export(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_export",
        input_summary="signals export",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="signals_export",
            input_summary="signals export",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    ledger = _load_signals_ledger(storage_dir, cfg)
    export_path = (
        Path(args.path).expanduser()
        if args.path
        else storage_dir / "unmet-intent-signals-export.json"
    )
    export_id = _new_record_id("sigexp")
    exported_at = datetime.now(timezone.utc)
    export_payload = dict(ledger)
    export_payload["export_id"] = export_id
    export_payload["exported_at"] = _isoformat_utc(exported_at)
    _write_json(export_path, export_payload)
    _append_jsonl(
        _signals_export_events_path(storage_dir),
        {
            "schema_version": SIGNALS_SCHEMA_VERSION,
            "export_id": export_id,
            "exported_at": _isoformat_utc(exported_at),
            "path": str(export_path),
            "signal_count": int(ledger.get("signal_count", 0)),
        },
    )

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="signals_export",
        input_summary=f"path={export_path}",
        output_summary=f"exported {int(ledger.get('signal_count', 0))} signals",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_signals_trace_metadata(
            signal_count=int(ledger.get("signal_count", 0)),
            export_id=export_id,
            export_path=str(export_path),
            collection_enabled=bool(ledger.get("collection_enabled", True)),
        ),
    )

    if args.as_json:
        print(
            json.dumps(
                {
                    "export_id": export_id,
                    "exported_at": _isoformat_utc(exported_at),
                    "path": str(export_path),
                    "signal_count": int(ledger.get("signal_count", 0)),
                },
                indent=2,
            )
        )
    else:
        print(
            f"Exported {int(ledger.get('signal_count', 0))} signals to {export_path} "
            f"(export_id={export_id})"
        )
    return 0


def cmd_signals_clear(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_delete",
        input_summary="signals clear",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="signals_clear",
            input_summary="signals clear",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    path = _signals_path(storage_dir)
    existed = path.exists()
    path.unlink(missing_ok=True)
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="signals_clear",
        input_summary=str(path),
        output_summary="cleared" if existed else "already empty",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_signals_trace_metadata(cleared=existed),
    )

    if existed:
        print(f"Cleared unmet-intent signal ledger: {path}")
    else:
        print("Signal ledger already empty.")
    return 0


def _memory_trace_metadata(
    *,
    memory_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    consent_scope: Optional[str] = None,
    retention_ttl: Optional[str] = None,
    policy_decision: Optional[str] = None,
    policy_reason: Optional[str] = None,
    retrieval_mode: Optional[str] = None,
    candidate_count: Optional[int] = None,
    selected_count: Optional[int] = None,
    tombstone_id: Optional[str] = None,
    export_id: Optional[str] = None,
    summary_event_id: Optional[str] = None,
    source_memory_ids: Optional[List[str]] = None,
    response_profile: Optional[str] = None,
    response_profile_source: Optional[str] = None,
    evidence_path: Optional[str] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    if memory_id:
        metadata["memory_id"] = memory_id
    if memory_type:
        metadata["memory_type"] = memory_type
    if subject_id:
        metadata["subject_id"] = subject_id
    if consent_scope:
        metadata["consent_scope"] = consent_scope
    if retention_ttl:
        metadata["retention_ttl"] = retention_ttl
    if policy_decision:
        metadata["memory_policy_decision"] = policy_decision
    if policy_reason:
        metadata["memory_policy_reason"] = _summarize_text(policy_reason, max_chars=180)
    if retrieval_mode:
        metadata["retrieval_mode"] = retrieval_mode
    if candidate_count is not None:
        metadata["candidate_count"] = int(candidate_count)
    if selected_count is not None:
        metadata["selected_count"] = int(selected_count)
    if tombstone_id:
        metadata["tombstone_id"] = tombstone_id
    if export_id:
        metadata["export_id"] = export_id
    if summary_event_id:
        metadata["summary_event_id"] = summary_event_id
    if source_memory_ids is not None:
        metadata["source_memory_ids"] = [str(item).strip() for item in source_memory_ids if str(item).strip()]
    if response_profile:
        metadata["response_profile"] = _response_profile_display(response_profile)
    if response_profile_source:
        metadata["response_profile_source"] = str(response_profile_source).strip()
    if evidence_path:
        metadata["evidence_path"] = evidence_path
    return _with_trace_metadata(metadata=metadata)


def _memory_summary_item_budget(response_profile: str) -> Tuple[int, int]:
    profile = _normalize_response_profile_token(response_profile)
    if profile == "concise":
        return 3, 100
    if profile == "detailed":
        return 8, 180
    return 5, 130


def _compose_memory_summary_payload(
    records: List[Dict[str, Any]],
    *,
    response_profile: str,
    query: str,
    subject_filter: str,
) -> Tuple[str, str, List[str]]:
    item_limit, snippet_chars = _memory_summary_item_budget(response_profile)
    selected = records[:item_limit]
    source_ids = [str(item.get("memory_id", "")).strip() for item in selected if str(item.get("memory_id", "")).strip()]
    profile_label = _response_profile_display(response_profile)

    highlights: List[str] = []
    for record in selected:
        memory_id = str(record.get("memory_id", "")).strip() or "unknown-id"
        memory_type = str(record.get("memory_type", "")).strip() or "unknown-type"
        subject_id = str(record.get("subject_id", "")).strip() or "unknown-subject"
        snippet = _summarize_text(record.get("summary") or record.get("content", ""), max_chars=snippet_chars)
        highlights.append(f"- {memory_id} ({memory_type}, {subject_id}): {snippet}")

    query_label = str(query or "").strip() or "-"
    subject_label = str(subject_filter or "").strip() or "-"
    summary_text = (
        f"{profile_label} profile memory summary from {len(records)} records "
        f"(selected {len(selected)}, query={query_label}, subject={subject_label})."
    )
    content_lines = [
        f"Memory summary profile: {profile_label}",
        f"Source count: {len(records)}",
        f"Selected source count: {len(selected)}",
        f"Source memory ids: {', '.join(source_ids) if source_ids else '-'}",
        f"Filters: query={query_label} subject={subject_label}",
        "",
        "Highlights:",
        *highlights,
    ]
    return summary_text, "\n".join(content_lines).strip(), source_ids


def _tokenize_text(raw: str) -> List[str]:
    return [token for token in re.findall(r"[a-z0-9]+", str(raw).lower()) if token]


def _token_jaccard_score(a: str, b: str) -> float:
    left = set(_tokenize_text(a))
    right = set(_tokenize_text(b))
    if not left or not right:
        return 0.0
    return len(left.intersection(right)) / len(left.union(right))


def _char_ngram_dice_score(a: str, b: str, n: int = 3) -> float:
    left_src = str(a).lower().strip()
    right_src = str(b).lower().strip()
    if not left_src or not right_src:
        return 0.0
    if len(left_src) < n or len(right_src) < n:
        return 1.0 if left_src == right_src else 0.0
    left = {left_src[idx : idx + n] for idx in range(len(left_src) - n + 1)}
    right = {right_src[idx : idx + n] for idx in range(len(right_src) - n + 1)}
    if not left or not right:
        return 0.0
    return (2.0 * len(left.intersection(right))) / (len(left) + len(right))


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recency_score(timestamp: str, reference: datetime) -> float:
    parsed = _parse_iso_datetime(timestamp)
    if parsed is None:
        return 0.0
    age_seconds = max((reference - parsed).total_seconds(), 0.0)
    day_seconds = 24.0 * 60.0 * 60.0
    # Exponential-like decay without external dependencies.
    return 1.0 / (1.0 + (age_seconds / day_seconds))


def _memory_retrieval_pipeline(
    query: str,
    candidates: List[Dict[str, Any]],
    *,
    limit: int,
    semantic_fallback: bool,
) -> List[Dict[str, Any]]:
    text_query = str(query).strip()
    if not text_query:
        return []

    now = datetime.now(timezone.utc)
    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        memory_id = str(candidate.get("memory_id", "")).strip()
        content = str(candidate.get("content", "")).strip()
        summary = str(candidate.get("summary", "")).strip()
        corpus = f"{summary} {content}".strip()

        exact_score = 1.0 if memory_id == text_query else 0.0
        lexical_score = _token_jaccard_score(text_query, corpus)
        semantic_score = 0.0
        if semantic_fallback:
            semantic_score = _char_ngram_dice_score(text_query, corpus)

        stage = ""
        base_score = 0.0
        if exact_score > 0.0:
            stage = "exact"
            base_score = exact_score
        elif lexical_score > 0.0:
            stage = "lexical"
            base_score = lexical_score
        elif semantic_score > 0.0:
            stage = "semantic"
            base_score = semantic_score

        if not stage:
            continue

        recency = _recency_score(str(candidate.get("updated_at", "")), now)
        importance = max(0.0, min(float(candidate.get("importance", 0.0)), 1.0))
        final_score = (base_score * 0.7) + (importance * 0.2) + (recency * 0.1)

        scored_item = dict(candidate)
        scored_item["retrieval_stage"] = stage
        scored_item["score_exact"] = round(exact_score, 6)
        scored_item["score_lexical"] = round(lexical_score, 6)
        scored_item["score_semantic"] = round(semantic_score, 6)
        scored_item["score_recency"] = round(recency, 6)
        scored_item["score_final"] = round(final_score, 6)
        scored.append(scored_item)

    scored.sort(
        key=lambda item: (
            float(item.get("score_final", 0.0)),
            float(item.get("score_exact", 0.0)),
            float(item.get("score_lexical", 0.0)),
            float(item.get("importance", 0.0)),
            str(item.get("updated_at", "")),
            str(item.get("memory_id", "")),
        ),
        reverse=True,
    )

    if limit <= 0:
        limit = MEMORY_LIST_DEFAULT_LIMIT
    limited = scored[: min(limit, MEMORY_LIST_MAX_LIMIT)]
    for idx, item in enumerate(limited, start=1):
        item["rank"] = idx
    return limited


def cmd_memory_add(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_write",
        input_summary=f"memory add type={args.memory_type} subject={args.subject_id}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_capture",
            input_summary="memory add",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    try:
        record = store.create(
            {
                "memory_id": args.memory_id,
                "memory_type": args.memory_type,
                "subject_id": args.subject_id,
                "content": args.content,
                "summary": args.summary,
                "source_trace_id": args.source_trace_id,
                "confidence": args.confidence,
                "importance": args.importance,
                "retention_ttl": args.retention_ttl,
                "consent_scope": args.consent_scope,
            }
        )
    except (ValueError, sqlite3.Error) as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_capture",
            input_summary=f"type={args.memory_type} subject={args.subject_id}",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
            metadata=_memory_trace_metadata(
                memory_type=args.memory_type,
                subject_id=args.subject_id,
                consent_scope=args.consent_scope,
                retention_ttl=args.retention_ttl,
                policy_decision="deny",
                policy_reason=str(exc),
            ),
        )
        print(str(exc), file=sys.stderr)
        return 1

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_capture",
        input_summary=f"type={record['memory_type']} subject={record['subject_id']}",
        output_summary=f"saved {record['memory_id']}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_memory_trace_metadata(
            memory_id=record["memory_id"],
            memory_type=record["memory_type"],
            subject_id=record["subject_id"],
            consent_scope=record["consent_scope"],
            retention_ttl=record["retention_ttl"],
            policy_decision="allow",
            policy_reason="memory policy contract satisfied",
        ),
    )
    if args.as_json:
        print(json.dumps(record, indent=2))
    else:
        print(
            f"{record['memory_id']} {record['memory_type']} {record['subject_id']} "
            f"consent={record['consent_scope']} ttl={record['retention_ttl'] or '-'}"
        )
    return 0


def cmd_memory_get(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_read",
        input_summary=f"memory get id={args.memory_id}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_retrieve",
            input_summary=f"id={args.memory_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    record = store.get(
        args.memory_id,
        include_deleted=bool(args.include_deleted),
        touch_access=True,
    )
    if record is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_retrieve",
            input_summary=f"id={args.memory_id}",
            output_summary="memory not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Memory not found: {args.memory_id}", file=sys.stderr)
        return 1

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_retrieve",
        input_summary=f"id={args.memory_id}",
        output_summary=f"retrieved {record['memory_id']}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_memory_trace_metadata(
            memory_id=record["memory_id"],
            memory_type=record["memory_type"],
            subject_id=record["subject_id"],
            retrieval_mode="get",
            candidate_count=1,
            selected_count=1,
        ),
    )
    if args.as_json:
        print(json.dumps(record, indent=2))
    else:
        print(f"memory_id: {record['memory_id']}")
        print(f"memory_type: {record['memory_type']}")
        print(f"subject_id: {record['subject_id']}")
        print(f"consent_scope: {record['consent_scope']}")
        print(f"retention_ttl: {record['retention_ttl'] or '-'}")
        print(f"confidence: {record['confidence']:.3f}")
        print(f"importance: {record['importance']:.3f}")
        print(f"source_trace_id: {record['source_trace_id'] or '-'}")
        print(f"created_at: {record['created_at']}")
        print(f"updated_at: {record['updated_at']}")
        print(f"deleted_at: {record['deleted_at'] or '-'}")
        print(f"last_accessed_at: {record['last_accessed_at'] or '-'}")
        print(f"summary: {record['summary']}")
        print("content:")
        print(record["content"])
    return 0


def cmd_memory_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_read",
        input_summary="memory list",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_retrieve",
            input_summary="memory list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    try:
        records = store.list(
            memory_type=args.memory_type,
            subject_id=args.subject_id,
            query=args.q,
            limit=int(args.limit),
            include_deleted=bool(args.include_deleted),
        )
    except ValueError as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_retrieve",
            input_summary="memory list",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(str(exc), file=sys.stderr)
        return 1

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_retrieve",
        input_summary=f"type={args.memory_type or '-'} subject={args.subject_id or '-'} q={args.q or '-'}",
        output_summary=f"{len(records)} records",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_memory_trace_metadata(
            memory_type=args.memory_type,
            subject_id=args.subject_id,
            retrieval_mode="list",
            candidate_count=len(records),
            selected_count=len(records),
        ),
    )

    if args.as_json:
        print(json.dumps(records, indent=2))
        return 0

    if not records:
        print("No memory records found.")
        return 0

    for record in records:
        summary = _summarize_text(record.get("summary") or record.get("content", ""), max_chars=80)
        print(
            f"{record['memory_id']} {record['memory_type']} {record['subject_id']} "
            f"{record['updated_at']} {summary}"
        )
    return 0


def cmd_memory_retrieve(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    query = str(args.query).strip()
    if not query:
        print("--query cannot be empty.", file=sys.stderr)
        return 1

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_read",
        input_summary=f"memory retrieve query={query}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_retrieve",
            input_summary=f"query={query}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    candidate_limit = int(args.candidate_limit)
    if candidate_limit <= 0:
        candidate_limit = MEMORY_LIST_MAX_LIMIT
    candidate_limit = min(candidate_limit, MEMORY_LIST_MAX_LIMIT)

    try:
        candidates = store.list(
            memory_type=args.memory_type,
            subject_id=args.subject_id,
            query=None,
            limit=candidate_limit,
            include_deleted=bool(args.include_deleted),
        )
    except ValueError as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_retrieve",
            input_summary=f"query={query}",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(str(exc), file=sys.stderr)
        return 1

    results = _memory_retrieval_pipeline(
        query=query,
        candidates=candidates,
        limit=int(args.limit),
        semantic_fallback=not bool(args.no_semantic_fallback),
    )
    latency_ms = (time.perf_counter() - start) * 1000

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_retrieve",
        input_summary=f"query={query} type={args.memory_type or '-'} subject={args.subject_id or '-'}",
        output_summary=f"{len(results)} retrieved",
        duration_ms=latency_ms,
        permission_level=permission_level,
        metadata=_memory_trace_metadata(
            memory_type=args.memory_type,
            subject_id=args.subject_id,
            retrieval_mode="pipeline",
            candidate_count=len(candidates),
            selected_count=len(results),
        ),
    )

    if args.as_json:
        print(json.dumps(results, indent=2))
        return 0

    if not results:
        print("No memory retrieval matches found.")
        return 0

    for item in results:
        summary = _summarize_text(item.get("summary") or item.get("content", ""), max_chars=80)
        print(
            f"rank={item.get('rank', '?')} id={item.get('memory_id', '?')} "
            f"stage={item.get('retrieval_stage', '?')} score={float(item.get('score_final', 0.0)):.3f} "
            f"type={item.get('memory_type', '?')} subject={item.get('subject_id', '?')} "
            f"summary={summary}"
        )
    return 0


def cmd_memory_summarize(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    source_subject = str(args.subject_id or "").strip()
    source_query = str(args.q or "").strip()
    source_type = str(args.memory_type or "").strip() or None
    response_profile, response_profile_source = _resolve_response_profile(
        cfg,
        storage_dir,
        override=args.response_profile,
    )
    summary_type = _normalize_memory_type(str(args.summary_memory_type))
    summary_subject = str(args.summary_subject_id or source_subject or "memory:summary").strip()
    if not summary_subject:
        print("summary subject cannot be empty.", file=sys.stderr)
        return 1
    summary_consent_scope = str(args.summary_consent_scope or "").strip()
    if summary_consent_scope:
        summary_consent_scope = _normalize_memory_consent_scope(summary_consent_scope)
    else:
        summary_consent_scope = _default_memory_consent_scope(summary_type)

    allowed_read, read_permission = _enforce_capability(
        cfg=cfg,
        capability="memory_read",
        input_summary="memory summarize read",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed_read:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_summarize",
            input_summary=f"type={source_type or '-'} subject={source_subject or '-'} q={source_query or '-'}",
            output_summary="blocked by memory_read policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=read_permission,
            status="blocked",
            metadata=_memory_trace_metadata(
                memory_type=source_type,
                subject_id=source_subject,
                retrieval_mode="summarize",
                policy_decision="deny",
                policy_reason="blocked by memory_read capability policy",
                response_profile=response_profile,
                response_profile_source=response_profile_source,
            ),
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    allowed_write, write_permission = _enforce_capability(
        cfg=cfg,
        capability="memory_write",
        input_summary="memory summarize write",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed_write:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_summarize",
            input_summary=f"type={source_type or '-'} subject={source_subject or '-'} q={source_query or '-'}",
            output_summary="blocked by memory_write policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=write_permission,
            status="blocked",
            metadata=_memory_trace_metadata(
                memory_type=summary_type,
                subject_id=summary_subject,
                consent_scope=summary_consent_scope,
                retention_ttl=str(args.retention_ttl or "").strip(),
                retrieval_mode="summarize",
                policy_decision="deny",
                policy_reason="blocked by memory_write capability policy",
                response_profile=response_profile,
                response_profile_source=response_profile_source,
            ),
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    try:
        records = store.list(
            memory_type=source_type,
            subject_id=source_subject or None,
            query=source_query or None,
            limit=int(args.limit),
            include_deleted=bool(args.include_deleted),
        )
    except ValueError as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_summarize",
            input_summary=f"type={source_type or '-'} subject={source_subject or '-'} q={source_query or '-'}",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=write_permission,
            status="error",
            metadata=_memory_trace_metadata(
                memory_type=source_type,
                subject_id=source_subject,
                retrieval_mode="summarize",
                policy_decision="deny",
                policy_reason=str(exc),
                response_profile=response_profile,
                response_profile_source=response_profile_source,
            ),
        )
        print(str(exc), file=sys.stderr)
        return 1

    if not records:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_summarize",
            input_summary=f"type={source_type or '-'} subject={source_subject or '-'} q={source_query or '-'}",
            output_summary="no matching records",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=write_permission,
            status="error",
            metadata=_memory_trace_metadata(
                memory_type=source_type,
                subject_id=source_subject,
                retrieval_mode="summarize",
                candidate_count=0,
                selected_count=0,
                policy_decision="deny",
                policy_reason="no source memory records matched summarize filters",
                response_profile=response_profile,
                response_profile_source=response_profile_source,
            ),
        )
        print("No memory records found for summarize filters.", file=sys.stderr)
        return 1

    summary_text, summary_content, source_ids = _compose_memory_summary_payload(
        records,
        response_profile=response_profile,
        query=source_query,
        subject_filter=source_subject,
    )

    try:
        summary_record = store.create(
            {
                "memory_id": args.summary_memory_id,
                "memory_type": summary_type,
                "subject_id": summary_subject,
                "content": summary_content,
                "summary": summary_text,
                "source_trace_id": str(args.source_trace_id or "").strip(),
                "confidence": args.confidence,
                "importance": args.importance,
                "retention_ttl": str(args.retention_ttl or "").strip(),
                "consent_scope": summary_consent_scope,
            }
        )
    except (ValueError, sqlite3.Error) as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_summarize",
            input_summary=f"type={source_type or '-'} subject={source_subject or '-'} q={source_query or '-'}",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=write_permission,
            status="error",
            metadata=_memory_trace_metadata(
                memory_type=summary_type,
                subject_id=summary_subject,
                consent_scope=summary_consent_scope,
                retention_ttl=str(args.retention_ttl or "").strip(),
                retrieval_mode="summarize",
                candidate_count=len(records),
                selected_count=len(source_ids),
                policy_decision="deny",
                policy_reason=str(exc),
                source_memory_ids=source_ids,
                response_profile=response_profile,
                response_profile_source=response_profile_source,
            ),
        )
        print(str(exc), file=sys.stderr)
        return 1

    summary_event_id = _new_record_id("ms")
    summary_event = {
        "schema_version": 1,
        "summary_event_id": summary_event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary_memory_id": summary_record["memory_id"],
        "summary_memory_type": summary_record["memory_type"],
        "summary_subject_id": summary_record["subject_id"],
        "response_profile": _response_profile_display(response_profile),
        "response_profile_source": response_profile_source,
        "source_count": len(records),
        "selected_source_count": len(source_ids),
        "source_memory_ids": source_ids,
        "filters": {
            "memory_type": source_type,
            "subject_id": source_subject,
            "query": source_query,
            "include_deleted": bool(args.include_deleted),
            "limit": int(args.limit),
        },
        "summary_sha256": hashlib.sha256(summary_content.encode("utf-8")).hexdigest(),
    }
    summary_events_path = _memory_summary_events_path(storage_dir)
    _append_jsonl(summary_events_path, summary_event)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_summarize",
        input_summary=f"type={source_type or '-'} subject={source_subject or '-'} q={source_query or '-'}",
        output_summary=f"summary {summary_record['memory_id']} from {len(source_ids)} sources",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=write_permission,
        metadata=_memory_trace_metadata(
            memory_id=summary_record["memory_id"],
            memory_type=summary_record["memory_type"],
            subject_id=summary_record["subject_id"],
            consent_scope=summary_record["consent_scope"],
            retention_ttl=summary_record["retention_ttl"],
            retrieval_mode="summarize",
            candidate_count=len(records),
            selected_count=len(source_ids),
            policy_decision="allow",
            policy_reason="memory summary persisted with source traceability evidence",
            summary_event_id=summary_event_id,
            source_memory_ids=source_ids,
            response_profile=response_profile,
            response_profile_source=response_profile_source,
            evidence_path=str(summary_events_path),
        ),
    )

    if args.as_json:
        print(
            json.dumps(
                {
                    "summary_memory": summary_record,
                    "summary_event": summary_event,
                    "source_memory_ids": source_ids,
                },
                indent=2,
            )
        )
        return 0

    print(
        f"{summary_record['memory_id']} {summary_record['memory_type']} {summary_record['subject_id']} "
        f"profile={_response_profile_display(response_profile)} sources={len(source_ids)} "
        f"event={summary_event_id}"
    )
    print(summary_text)
    return 0


def cmd_memory_update(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_write",
        input_summary=f"memory update id={args.memory_id}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_update",
            input_summary=f"id={args.memory_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    updates: Dict[str, Any] = {
        "memory_type": args.memory_type,
        "subject_id": args.subject_id,
        "content": args.content,
        "summary": args.summary,
        "source_trace_id": args.source_trace_id,
        "confidence": args.confidence,
        "importance": args.importance,
        "retention_ttl": args.retention_ttl,
        "consent_scope": args.consent_scope,
    }
    non_empty_updates = {key: value for key, value in updates.items() if value is not None}
    if not non_empty_updates:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_update",
            input_summary=f"id={args.memory_id}",
            output_summary="no update fields provided",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("No updates provided.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    try:
        record = store.update(args.memory_id, non_empty_updates)
    except (ValueError, sqlite3.Error) as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_update",
            input_summary=f"id={args.memory_id}",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
            metadata=_memory_trace_metadata(
                memory_id=args.memory_id,
                memory_type=args.memory_type,
                subject_id=args.subject_id,
                consent_scope=args.consent_scope,
                retention_ttl=args.retention_ttl,
                policy_decision="deny",
                policy_reason=str(exc),
            ),
        )
        print(str(exc), file=sys.stderr)
        return 1
    if record is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_update",
            input_summary=f"id={args.memory_id}",
            output_summary="memory not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Memory not found: {args.memory_id}", file=sys.stderr)
        return 1

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_update",
        input_summary=f"id={args.memory_id}",
        output_summary=f"updated {record['memory_id']}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_memory_trace_metadata(
            memory_id=record["memory_id"],
            memory_type=record["memory_type"],
            subject_id=record["subject_id"],
            consent_scope=record["consent_scope"],
            retention_ttl=record["retention_ttl"],
            policy_decision="allow",
            policy_reason="memory policy contract satisfied",
        ),
    )
    if args.as_json:
        print(json.dumps(record, indent=2))
    else:
        print(f"{record['memory_id']} updated")
    return 0


def cmd_memory_delete(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_delete",
        input_summary=f"memory delete id={args.memory_id}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_delete",
            input_summary=f"id={args.memory_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    existing = store.get(args.memory_id, include_deleted=True, touch_access=False)
    if existing is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_delete",
            input_summary=f"id={args.memory_id}",
            output_summary="memory not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Memory not found: {args.memory_id}", file=sys.stderr)
        return 1

    removed = store.delete(args.memory_id)
    if not removed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_delete",
            input_summary=f"id={args.memory_id}",
            output_summary="memory not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Memory not found: {args.memory_id}", file=sys.stderr)
        return 1

    deleted = store.get(args.memory_id, include_deleted=True, touch_access=False) or existing
    tombstone_id = _new_record_id("mt")
    deleted_at = str(deleted.get("deleted_at", "")).strip() or datetime.now(timezone.utc).isoformat()
    tombstone_path = _memory_tombstones_path(storage_dir)
    tombstone = {
        "schema_version": 1,
        "tombstone_id": tombstone_id,
        "memory_id": str(deleted.get("memory_id", args.memory_id)),
        "memory_type": str(deleted.get("memory_type", "")),
        "subject_id": str(deleted.get("subject_id", "")),
        "consent_scope": str(deleted.get("consent_scope", "")),
        "retention_ttl": str(deleted.get("retention_ttl", "")),
        "deleted_at": deleted_at,
        "record_status": "soft_deleted",
        "evidence": "sqlite_index_tombstone",
    }
    _append_jsonl(tombstone_path, tombstone)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_delete",
        input_summary=f"id={args.memory_id}",
        output_summary=f"deleted {args.memory_id} with tombstone {tombstone_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_memory_trace_metadata(
            memory_id=str(deleted.get("memory_id", args.memory_id)),
            memory_type=str(deleted.get("memory_type", "")),
            subject_id=str(deleted.get("subject_id", "")),
            consent_scope=str(deleted.get("consent_scope", "")),
            retention_ttl=str(deleted.get("retention_ttl", "")),
            policy_decision="allow",
            policy_reason="delete allowed; tombstone evidence written",
            tombstone_id=tombstone_id,
            evidence_path=str(tombstone_path),
        ),
    )
    print(f"{args.memory_id} deleted tombstone={tombstone_id}")
    return 0


def cmd_memory_export(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="memory_export",
        input_summary="memory export",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_export",
            input_summary="memory export",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
            metadata=_memory_trace_metadata(
                memory_type=args.memory_type,
                subject_id=args.subject_id,
                policy_decision="deny",
                policy_reason="blocked by capability policy",
            ),
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    store = _memory_store(storage_dir)
    try:
        records = store.list(
            memory_type=args.memory_type,
            subject_id=args.subject_id,
            query=args.q,
            limit=int(args.limit),
            include_deleted=bool(args.include_deleted),
        )
    except ValueError as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="memory_export",
            input_summary="memory export",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
            metadata=_memory_trace_metadata(
                memory_type=args.memory_type,
                subject_id=args.subject_id,
                policy_decision="deny",
                policy_reason=str(exc),
            ),
        )
        print(str(exc), file=sys.stderr)
        return 1

    export_id = _new_record_id("mx")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = Path(args.path).expanduser() if args.path else (
        storage_dir / "memory-exports" / f"memory-export-{timestamp}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "export_id": export_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "memory_type": args.memory_type,
            "subject_id": args.subject_id,
            "query": args.q,
            "include_deleted": bool(args.include_deleted),
            "limit": int(args.limit),
        },
        "record_count": len(records),
        "records": records,
    }
    text = json.dumps(payload, indent=2)
    output_path.write_text(text + "\n", encoding="utf-8")

    export_event = {
        "schema_version": 1,
        "export_id": export_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_path": str(output_path),
        "record_count": len(records),
        "memory_type": args.memory_type,
        "subject_id": args.subject_id,
        "include_deleted": bool(args.include_deleted),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    export_events_path = _memory_export_events_path(storage_dir)
    _append_jsonl(export_events_path, export_event)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="memory_export",
        input_summary=f"type={args.memory_type or '-'} subject={args.subject_id or '-'} q={args.q or '-'}",
        output_summary=f"exported {len(records)} records to {output_path}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_memory_trace_metadata(
            memory_type=args.memory_type,
            subject_id=args.subject_id,
            retrieval_mode="export",
            candidate_count=len(records),
            selected_count=len(records),
            policy_decision="allow",
            policy_reason="memory export allowed; evidence artifact written",
            export_id=export_id,
            evidence_path=str(output_path),
        ),
    )

    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"{export_id} records={len(records)} path={output_path}")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="network_request",
        input_summary="summarize urls",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="summarize_url",
            input_summary=" ".join(args.urls),
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    summaries = _load_records(_summaries_path(storage_dir))
    failed = 0
    for raw_url in args.urls:
        url = str(raw_url).strip()
        if not url:
            continue

        item_start = time.perf_counter()
        try:
            title, body_text = _fetch_url_content(url)
            points = _key_points_from_text(body_text)
        except ProviderError as exc:
            failed += 1
            message = f"[warn] {exc}"
            print(message, file=sys.stderr)
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="summarize_url",
                input_summary=url,
                output_summary=message,
                duration_ms=(time.perf_counter() - item_start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            continue

        record = {
            "id": _new_record_id("s"),
            "url": url,
            "title": title or "Untitled",
            "key_points": points,
            "date_summarized": datetime.now(timezone.utc).isoformat(),
            "source": "cli",
        }
        summaries.append(record)
        print(f"- {record['title']}")
        print(f"  URL: {url}")
        print(f"  Date: {record['date_summarized']}")
        for point in points:
            print(f"  * {point}")
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="summarize_url",
            input_summary=url,
            output_summary=f"saved summary {record['id']}",
            duration_ms=(time.perf_counter() - item_start) * 1000,
            permission_level=permission_level,
            metadata={"summary_id": record["id"]},
        )

    _save_records(_summaries_path(storage_dir), summaries)
    if failed and failed == len(args.urls):
        return 1
    return 0


def cmd_summaries(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary="list summaries",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="summaries_list",
            input_summary="summaries list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    summaries = _load_records(_summaries_path(storage_dir))
    summaries.sort(key=lambda item: str(item.get("date_summarized", "")), reverse=True)
    if args.last and args.last > 0:
        summaries = summaries[: args.last]

    if not summaries:
        print("No summaries found.")
    else:
        for item in summaries:
            summary_id = str(item.get("id", "?"))
            title = str(item.get("title", "Untitled"))
            url = str(item.get("url", ""))
            date_summarized = str(item.get("date_summarized", ""))
            print(f"{summary_id} {date_summarized} {title} ({url})")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="summaries_list",
        input_summary=f"last={args.last}",
        output_summary=f"{len(summaries)} summaries",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    plans_path = _plans_path(storage_dir)
    plans = _load_records(plans_path)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="plan create/update",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="plan_create",
            input_summary="plan command",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    if args.edit:
        plan_id = str(args.edit).strip()
        if not plan_id:
            print("--edit requires a plan id.", file=sys.stderr)
            return 1
        target = None
        for item in plans:
            if str(item.get("id", "")).strip() == plan_id:
                target = item
                break
        if target is None:
            print(f"Plan not found: {plan_id}", file=sys.stderr)
            return 1

        refinement = str(args.update or "").strip()
        if not refinement:
            if not sys.stdin.isatty():
                print("Provide --update in non-interactive mode.", file=sys.stderr)
                return 1
            refinement = input("Refinement request: ").strip()
        if not refinement:
            print("Refinement text cannot be empty.", file=sys.stderr)
            return 1

        steps = _generate_plan_steps(str(target.get("objective", "")), refinement=refinement)
        target["steps"] = steps
        target["dependencies"] = _derive_plan_dependencies(str(target.get("objective", "")))
        target["estimated_complexity"] = _estimate_plan_complexity(str(target.get("objective", "")))
        revisions = target.setdefault("revisions", [])
        if not isinstance(revisions, list):
            revisions = []
            target["revisions"] = revisions
        revisions.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "refinement": refinement,
            }
        )
        target["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_records(plans_path, plans)
        print(f"Updated plan {plan_id}")
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="plan_update",
            input_summary=f"plan_id={plan_id}",
            output_summary="plan updated",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            metadata={"plan_id": plan_id},
        )
        return 0

    goal = str(args.goal or "").strip()
    if not goal:
        print("Goal is required. Example: gaia plan \"Set up a personal knowledge base\".", file=sys.stderr)
        return 1

    plan_id = _new_record_id("p")
    now = datetime.now(timezone.utc).isoformat()
    plan_record = {
        "id": plan_id,
        "objective": goal,
        "steps": _generate_plan_steps(goal),
        "estimated_complexity": _estimate_plan_complexity(goal),
        "dependencies": _derive_plan_dependencies(goal),
        "created_at": now,
        "updated_at": now,
        "revisions": [{"timestamp": now, "refinement": "initial"}],
        "source": "cli",
    }
    plans.append(plan_record)
    _save_records(plans_path, plans)
    print(f"Plan {plan_id}")
    print(f"Objective: {plan_record['objective']}")
    print(f"Complexity: {plan_record['estimated_complexity']}")
    print("Dependencies:")
    for dependency in plan_record["dependencies"]:
        print(f"- {dependency}")
    print("Steps:")
    for idx, step in enumerate(plan_record["steps"], start=1):
        print(f"{idx}. {step}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="plan_create",
        input_summary=goal,
        output_summary=f"created {plan_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"plan_id": plan_id},
    )
    return 0


def cmd_plans(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary="list plans",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="plans_list",
            input_summary="plans list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    plans = _load_records(_plans_path(storage_dir))
    plans.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    if args.last and args.last > 0:
        plans = plans[: args.last]

    if not plans:
        print("No plans found.")
    else:
        for plan in plans:
            plan_id = str(plan.get("id", "?"))
            objective = _summarize_text(plan.get("objective", ""), max_chars=100)
            complexity = str(plan.get("estimated_complexity", "?"))
            updated_at = str(plan.get("updated_at", ""))
            print(f"{plan_id} {complexity:<6} {updated_at} {objective}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="plans_list",
        input_summary=f"last={args.last}",
        output_summary=f"{len(plans)} plans",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    return 0


def cmd_skills_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary="skills list",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="skills_list",
            input_summary=f"source={args.source}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    contracts, scanned_roots = _load_skill_contracts(cfg, source_filter=str(args.source))
    if args.as_json:
        print(json.dumps(contracts, indent=2))
    elif not contracts:
        print("No skills found.")
    else:
        for item in contracts:
            skill_id = str(item.get("skill_id", "?"))
            source = str(item.get("source", "?"))
            name = str(item.get("name", "?"))
            entrypoint = str(item.get("entrypoint", "?"))
            capability_count = len(item.get("capabilities", [])) if isinstance(item.get("capabilities"), list) else 0
            description = _summarize_text(item.get("description", ""), max_chars=80)
            print(
                f"{skill_id} {source:<7} caps={capability_count:<2} "
                f"name={name} path={entrypoint} desc={description}"
            )

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="skills_list",
        input_summary=f"source={args.source}",
        output_summary=f"{len(contracts)} skills",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_with_trace_metadata(
            {
                "source": str(args.source),
                "skill_count": len(contracts),
                "scanned_roots": scanned_roots,
            },
            skill_source=str(args.source),
        ),
    )
    return 0


def cmd_skills_inspect(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary=f"skills inspect {args.skill_id}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="skills_inspect",
            input_summary=f"skill_id={args.skill_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    contracts, scanned_roots = _load_skill_contracts(cfg, source_filter=str(args.source))
    target, error_message = _resolve_skill_contract(contracts, str(args.skill_id))
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="skills_inspect",
            input_summary=f"skill_id={args.skill_id}",
            output_summary=error_message or "skill not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
            metadata=_with_trace_metadata(
                {"source": str(args.source), "scanned_roots": scanned_roots},
                skill_source=str(args.source),
            ),
        )
        print(error_message or "Skill not found.", file=sys.stderr)
        return 1

    print(json.dumps(target, indent=2))
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="skills_inspect",
        input_summary=f"skill_id={args.skill_id}",
        output_summary=f"loaded {target.get('skill_id', '?')}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata=_with_trace_metadata(
            {
                "source": str(args.source),
                "skill_id": target.get("skill_id"),
                "entrypoint": target.get("entrypoint"),
                "scanned_roots": scanned_roots,
            },
            skill_id=str(target.get("skill_id", "")),
            skill_source=str(target.get("source", args.source)),
        ),
    )
    return 0


def cmd_skills_validate(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary=f"skills validate {args.target}",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="skills_validate",
            input_summary=f"target={args.target}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    resolved, error_message, scanned_roots = _resolve_skill_validation_target(
        cfg,
        str(args.target),
        source_filter=str(args.source),
    )
    if resolved is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="skills_validate",
            input_summary=f"target={args.target}",
            output_summary=error_message or "target resolution failed",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
            metadata=_with_trace_metadata(
                {"source": str(args.source), "scanned_roots": scanned_roots},
                skill_source=str(args.source),
            ),
        )
        print(error_message or "Unable to resolve target.", file=sys.stderr)
        return 1

    findings: List[Dict[str, Any]] = []
    entrypoint = Path(resolved["entrypoint"])
    source_root = Path(resolved["source_root"])
    contract = resolved.get("contract", {})
    contract = contract if isinstance(contract, dict) else {}

    entrypoint_display = _display_runtime_path(entrypoint)
    source_root_display = _display_runtime_path(source_root)

    if entrypoint.name != "SKILL.md":
        _add_skill_validation_finding(
            findings,
            severity="critical",
            stage="structure",
            code="invalid_entrypoint_name",
            message="Entrypoint must be named SKILL.md.",
            path=entrypoint_display,
            recommendation="Use a SKILL.md file as the validation entrypoint.",
        )

    text = ""
    try:
        text = entrypoint.read_text(encoding="utf-8")
    except OSError as exc:
        _add_skill_validation_finding(
            findings,
            severity="critical",
            stage="structure",
            code="entrypoint_read_failed",
            message=f"Unable to read SKILL.md: {exc}",
            path=entrypoint_display,
            recommendation="Fix file permissions and retry validation.",
        )

    frontmatter: Dict[str, Any] = {}
    body = ""
    declared_capabilities: List[str] = []
    if text:
        frontmatter, body = _parse_skill_frontmatter(text)
        if not frontmatter:
            _add_skill_validation_finding(
                findings,
                severity="high",
                stage="schema",
                code="missing_frontmatter",
                message="SKILL.md is missing YAML frontmatter.",
                path=entrypoint_display,
                recommendation="Add frontmatter with name, description, and optional capabilities.",
            )
        else:
            name = str(frontmatter.get("name", "")).strip()
            description = str(frontmatter.get("description", "")).strip()
            declared_capabilities = _normalize_skill_capabilities(frontmatter.get("capabilities"))

            if not name:
                _add_skill_validation_finding(
                    findings,
                    severity="high",
                    stage="schema",
                    code="missing_name",
                    message="Frontmatter is missing required field: name.",
                    path=entrypoint_display,
                    recommendation="Set a stable lowercase kebab-case name in frontmatter.",
                )
            elif not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", name):
                _add_skill_validation_finding(
                    findings,
                    severity="warn",
                    stage="schema",
                    code="noncanonical_name",
                    message="Skill name is not lowercase kebab-case.",
                    path=entrypoint_display,
                    recommendation="Prefer lowercase kebab-case for stable runtime ids.",
                    evidence=name,
                )

            if not description:
                _add_skill_validation_finding(
                    findings,
                    severity="high",
                    stage="schema",
                    code="missing_description",
                    message="Frontmatter is missing required field: description.",
                    path=entrypoint_display,
                    recommendation="Add a short purpose description in frontmatter.",
                )
            elif len(description) < 16:
                _add_skill_validation_finding(
                    findings,
                    severity="warn",
                    stage="schema",
                    code="short_description",
                    message="Skill description is very short and may reduce operator clarity.",
                    path=entrypoint_display,
                    recommendation="Use a concise but descriptive sentence for intent and scope.",
                )

            if "capabilities" not in frontmatter:
                _add_skill_validation_finding(
                    findings,
                    severity="warn",
                    stage="schema",
                    code="capabilities_not_declared",
                    message="No capabilities declared in frontmatter.",
                    path=entrypoint_display,
                    recommendation="Declare capabilities explicitly to support policy gating.",
                )
            elif not declared_capabilities:
                _add_skill_validation_finding(
                    findings,
                    severity="warn",
                    stage="schema",
                    code="capabilities_empty",
                    message="Capabilities field is present but resolves to an empty list.",
                    path=entrypoint_display,
                    recommendation="Declare one or more meaningful capabilities or remove the field.",
                )

            if not body.strip():
                _add_skill_validation_finding(
                    findings,
                    severity="warn",
                    stage="structure",
                    code="empty_body",
                    message="SKILL.md body is empty after frontmatter.",
                    path=entrypoint_display,
                    recommendation="Add usage instructions and workflow steps in the skill body.",
                )

    contract_schema = contract.get("schema_version")
    if contract_schema != SKILL_CONTRACT_SCHEMA_VERSION:
        _add_skill_validation_finding(
            findings,
            severity="high",
            stage="compatibility",
            code="unsupported_contract_schema",
            message=(
                "Resolved skill contract schema is unsupported: "
                f"{contract_schema} (expected {SKILL_CONTRACT_SCHEMA_VERSION})."
            ),
            path=entrypoint_display,
            recommendation="Regenerate/align skill metadata with the current contract schema.",
        )

    policy_registry = _capability_registry(cfg)
    capabilities = contract.get("capabilities")
    if not isinstance(capabilities, list):
        capabilities = []
    normalized_caps = [str(item).strip().lower() for item in capabilities if str(item).strip()]
    if not normalized_caps and declared_capabilities:
        normalized_caps = list(declared_capabilities)

    for capability in normalized_caps:
        level = policy_registry.get(capability, "unmapped")
        if level == "forbidden":
            _add_skill_validation_finding(
                findings,
                severity="high",
                stage="policy",
                code="forbidden_capability",
                message=f"Declared capability '{capability}' is forbidden by current policy.",
                path=entrypoint_display,
                recommendation="Remove the capability or lower policy level only with explicit review.",
            )
        elif level == "confirm":
            _add_skill_validation_finding(
                findings,
                severity="warn",
                stage="policy",
                code="confirm_capability",
                message=f"Declared capability '{capability}' requires confirmation.",
                path=entrypoint_display,
                recommendation="Document when and why this capability is needed.",
            )
        elif level == "safe":
            _add_skill_validation_finding(
                findings,
                severity="info",
                stage="policy",
                code="safe_capability",
                message=f"Declared capability '{capability}' maps to safe policy level.",
                path=entrypoint_display,
            )
        else:
            _add_skill_validation_finding(
                findings,
                severity="warn",
                stage="policy",
                code="unmapped_capability",
                message=f"Declared capability '{capability}' has no configured policy mapping.",
                path=entrypoint_display,
                recommendation="Map the capability in local policy overrides before activation.",
            )

    scanned_files = _validate_skill_assets(
        entrypoint=entrypoint,
        skill_dir=source_root,
        findings=findings,
    )

    sandbox_contract = REPO_ROOT / "infrastructure" / "sandbox-contract-v1.md"
    if sandbox_contract.exists():
        _add_skill_validation_finding(
            findings,
            severity="info",
            stage="sandbox",
            code="sandbox_contract_present",
            message="Sandbox contract reference is present for downstream dry-run integration.",
            path=_display_runtime_path(sandbox_contract),
        )
    else:
        _add_skill_validation_finding(
            findings,
            severity="high" if bool(args.require_sandbox) else "warn",
            stage="sandbox",
            code="sandbox_contract_missing",
            message="Sandbox contract is not available; dry-run integration is deferred.",
            path="infrastructure/sandbox-contract-v1.md",
            recommendation="Land P2-E sandbox contract and re-run validation with --require-sandbox.",
        )

    resolved_source = str(contract.get("source", resolved.get("resolution", ""))).strip().lower()
    provenance_admission = _evaluate_skill_provenance_admission(
        cfg=cfg,
        source=resolved_source,
        skill_dir=source_root,
        frontmatter=frontmatter,
        findings=findings,
    )

    findings = _sorted_validation_findings(findings)
    summary = _skill_validation_summary(findings)
    status = "fail" if int(summary.get("blocking_count", 0)) > 0 else "pass"
    report_id = _new_record_id("svr")
    report_path = (
        Path(args.report_path).expanduser()
        if args.report_path
        else (_skill_validation_reports_dir(trace_dir) / f"{report_id}.json")
    )

    entrypoint_stat = None
    try:
        entrypoint_stat = entrypoint.stat()
    except OSError:
        entrypoint_stat = None

    report: Dict[str, Any] = {
        "schema_version": SKILL_VALIDATION_REPORT_SCHEMA_VERSION,
        "report_type": "gaia.skill-validation.v1",
        "report_id": report_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": summary,
        "target": {
            "reference": str(resolved.get("reference", "")),
            "resolution": str(resolved.get("resolution", "")),
            "skill_id": contract.get("skill_id"),
            "name": contract.get("name"),
            "source": contract.get("source"),
            "entrypoint": entrypoint_display,
            "source_root": source_root_display,
            "scanned_roots": scanned_roots,
        },
        "contract": {
            "schema_version": contract.get("schema_version"),
            "capabilities": normalized_caps,
            "frontmatter_keys": contract.get("frontmatter", {}).get("keys", []),
        },
        "provenance": {
            "entrypoint_sha256": contract.get("provenance", {}).get("sha256")
            or _sha256_file(entrypoint),
            "entrypoint_last_modified_at": contract.get("provenance", {}).get("last_modified_at")
            or (
                _isoformat_utc(datetime.fromtimestamp(entrypoint_stat.st_mtime, tz=timezone.utc))
                if entrypoint_stat is not None
                else ""
            ),
            "scanned_files": scanned_files,
        },
        "provenance_admission": provenance_admission,
        "findings": findings,
    }

    try:
        _write_json(report_path, report)
    except OSError as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="skills_validate",
            input_summary=f"target={args.target}",
            output_summary=f"failed writing report: {exc}",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
            metadata={"status": status, "blocking_count": summary.get("blocking_count", 0)},
        )
        print(f"Failed to write validation report: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        target_label = str(contract.get("skill_id", "")).strip() or entrypoint_display
        print(f"Validation status: {status.upper()}")
        print(f"Target: {target_label}")
        print(
            f"Findings: {summary.get('finding_count', 0)} "
            f"(blocking={summary.get('blocking_count', 0)})"
        )
        counts = summary.get("by_severity", {})
        if isinstance(counts, dict):
            print(
                "Severity counts: "
                + ", ".join(
                    f"{sev}={int(counts.get(sev, 0))}"
                    for sev in ("critical", "high", "warn", "info")
                )
            )
        provenance_decision = str(provenance_admission.get("overall_decision", "skipped")).strip().lower()
        provenance_policy = provenance_admission.get("policy", {}) if isinstance(provenance_admission, dict) else {}
        if provenance_decision:
            print(
                "Provenance admission: "
                f"{provenance_decision.upper()} "
                f"(pin={provenance_policy.get('provenance_mode', 'off')}, "
                f"attestation={provenance_policy.get('attestation_mode', 'off')}, "
                f"source_health={provenance_policy.get('source_health_mode', 'off')})"
            )
        if findings:
            print("Top findings:")
            for finding in findings[:12]:
                location = str(finding.get("path", ""))
                line = finding.get("line")
                if isinstance(line, int) and line > 0:
                    location = f"{location}:{line}" if location else f"line {line}"
                prefix = f"{str(finding.get('severity', 'warn')).upper()} [{finding.get('code', '?')}]"
                if location:
                    print(f"- {prefix} {finding.get('message', '')} ({location})")
                else:
                    print(f"- {prefix} {finding.get('message', '')}")
        print(f"Report: {report_path}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="skills_validate",
        input_summary=f"target={args.target}",
        output_summary=f"{status} blocking={summary.get('blocking_count', 0)}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        status="ok" if status == "pass" else "error",
        metadata=_with_trace_metadata(
            {
                "source": str(args.source),
                "require_sandbox": bool(args.require_sandbox),
                "target": str(resolved.get("reference", "")),
                "skill_id": contract.get("skill_id"),
                "report_path": str(report_path),
                "status": status,
                "summary": summary,
                "provenance_decision": str(provenance_admission.get("overall_decision", "skipped")),
            },
            skill_id=str(contract.get("skill_id", "")),
            skill_source=str(contract.get("source", args.source)),
        ),
    )

    return 0 if status == "pass" else 1


def cmd_sandbox_profiles(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    payload = _sandbox_profiles_payload(_sandbox_default_profile(cfg))
    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"default_profile={payload['default_profile']}")
        for profile in payload["profiles"]:
            name = str(profile.get("name", ""))
            fs_mode = str(profile.get("filesystem_mode", ""))
            network_default = str(profile.get("network_default", "deny"))
            reasons = ", ".join(profile.get("escalation_reasons", []))
            print(f"{name:<16} fs={fs_mode:<15} network={network_default:<5} escalations={reasons}")

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="sandbox_profiles",
        input_summary="sandbox profiles",
        output_summary=f"{len(payload['profiles'])} profiles",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level="safe",
        metadata=_with_trace_metadata(
            {"default_profile": payload["default_profile"]},
            sandbox_profile=str(payload["default_profile"]),
        ),
    )
    return 0


def cmd_sandbox_run(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    start = time.perf_counter()

    command_tokens = list(args.command)
    if command_tokens and command_tokens[0] == "--":
        command_tokens = command_tokens[1:]
    if not command_tokens:
        print("No command provided. Usage: gaia sandbox run -- <command ...>", file=sys.stderr)
        return 1

    profile = _normalize_sandbox_profile(args.profile, cfg)
    allow_network = bool(args.allow_network or _sandbox_default_allow_network(cfg))
    network_mode = "allow" if allow_network else "deny"
    command_text = shlex.join(command_tokens)
    trace_correlation_id = str(uuid.uuid4())
    skill_id = ""
    skill_scanned_roots: List[str] = []
    policy_source = "unknown"

    def _sandbox_trace_metadata(
        base: Optional[Dict[str, Any]] = None,
        *,
        policy_state: Optional[str] = None,
        policy_rule_id: Optional[str] = None,
        escalated_state: Optional[bool] = None,
        approved_state: Optional[bool] = None,
    ) -> Dict[str, Any]:
        return _with_trace_metadata(
            base,
            correlation_id=trace_correlation_id,
            skill_id=skill_id,
            skill_source=policy_source,
            policy_decision=policy_state,
            policy_id=policy_rule_id,
            sandbox_profile=profile,
            sandbox_network_mode=network_mode,
            sandbox_escalated=escalated_state,
            sandbox_approved=approved_state,
        )

    if args.skill:
        skill_ctx, error_message, skill_scanned_roots = _resolve_policy_skill_reference(
            cfg,
            str(args.skill),
            source_filter=str(args.skill_source),
        )
        if skill_ctx is None:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="sandbox_run",
                input_summary=command_text,
                output_summary=error_message or "skill resolution failed",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="error",
                metadata=_sandbox_trace_metadata(
                    {"skill": str(args.skill), "scanned_roots": skill_scanned_roots}
                ),
            )
            print(error_message or "Unable to resolve skill reference.", file=sys.stderr)
            return 1
        skill_id = str(skill_ctx.get("skill_id", "")).strip()
        policy_source = _normalize_policy_source(str(skill_ctx.get("source", "unknown")))

    inferred_policy_tool = _infer_policy_tool_from_command(command_text, command_tokens)
    policy_tool = inferred_policy_tool
    if args.tool:
        requested_policy_tool = _normalize_policy_tool(args.tool)
        if requested_policy_tool != inferred_policy_tool:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="sandbox_run",
                input_summary=command_text,
                output_summary="policy tool assertion mismatch",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="error",
                metadata=_sandbox_trace_metadata(
                    {
                        "tool_inferred": inferred_policy_tool,
                        "tool_requested": requested_policy_tool,
                        "scope": _normalize_policy_scope(args.policy_scope, cfg),
                        "source": policy_source,
                    }
                ),
            )
            print(
                "Policy tool assertion mismatch: "
                f"inferred '{inferred_policy_tool}' from command, got '{requested_policy_tool}'.",
                file=sys.stderr,
            )
            return 1
        policy_tool = requested_policy_tool
    policy_scope = _normalize_policy_scope(args.policy_scope, cfg)
    policy_decision = _evaluate_policy_decision(
        cfg,
        tool=policy_tool,
        source=policy_source,
        user_scope=policy_scope,
        skill_id=skill_id,
    )
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="policy_decision",
        input_summary=command_text,
        output_summary=(
            f"{policy_decision.get('decision')} "
            f"({policy_decision.get('policy_id', 'policy.default.v1')})"
        ),
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level="safe",
        status="blocked" if policy_decision.get("decision") == "deny" else "ok",
        metadata=_sandbox_trace_metadata(
            {
                "decision": policy_decision,
                "tool": policy_tool,
                "scope": policy_scope,
                "source": policy_source,
                "skill_scanned_roots": skill_scanned_roots,
            },
            policy_state=str(policy_decision.get("decision", "")),
            policy_rule_id=str(policy_decision.get("policy_id", "")),
        ),
    )

    policy_decision_state = str(policy_decision.get("decision", "allow")).strip().lower()
    policy_confirmed = policy_decision_state != "confirm"
    if policy_decision_state == "deny":
        policy_id = str(policy_decision.get("policy_id", "policy.default.v1"))
        reason = str(policy_decision.get("reason", "action denied by policy"))
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="sandbox_run",
            input_summary=command_text,
            output_summary=f"policy denied ({policy_id})",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="blocked",
            metadata=_sandbox_trace_metadata(
                {
                    "policy_decision": policy_decision,
                    "tool": policy_tool,
                    "scope": policy_scope,
                    "source": policy_source,
                },
                policy_state=policy_decision_state,
                policy_rule_id=policy_id,
            ),
        )
        print(f"Policy denied ({policy_id}): {reason}", file=sys.stderr)
        return 1
    if policy_decision_state == "confirm":
        if args.approve_policy or args.approve_escalation:
            policy_confirmed = True
        else:
            policy_confirmed = _prompt_yes_no(
                (
                    "Policy confirmation required "
                    f"({policy_decision.get('policy_id', 'policy.source.v1')}). Approve command execution?"
                ),
                default=False,
                non_interactive=not sys.stdin.isatty(),
            )
        if not policy_confirmed:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="sandbox_run",
                input_summary=command_text,
                output_summary="policy confirmation denied",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="blocked",
                metadata=_sandbox_trace_metadata(
                    {
                        "policy_decision": policy_decision,
                        "tool": policy_tool,
                        "scope": policy_scope,
                        "source": policy_source,
                    },
                    policy_state=policy_decision_state,
                    policy_rule_id=str(policy_decision.get("policy_id", "")),
                ),
            )
            print(
                "Policy confirmation required but not approved. Re-run with --approve-policy to continue.",
                file=sys.stderr,
            )
            return 1

    shell_allowed, permission_level, shell_reason = _shell_permission_for_sandbox(cfg)
    if not shell_allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="sandbox_run",
            input_summary=command_text,
            output_summary=shell_reason,
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
            metadata=_sandbox_trace_metadata(
                {
                    "shell_reason": shell_reason,
                },
                policy_state=policy_decision_state,
                policy_rule_id=str(policy_decision.get("policy_id", "")),
            ),
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    if allow_network:
        network_allowed, network_level = _network_permission_for_sandbox(cfg)
        if not network_allowed:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="sandbox_run",
                input_summary=command_text,
                output_summary="blocked by network_request policy",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=network_level,
                status="blocked",
                metadata=_sandbox_trace_metadata(
                    {"network_policy": "blocked by network_request"},
                    policy_state=policy_decision_state,
                    policy_rule_id=str(policy_decision.get("policy_id", "")),
                ),
            )
            print("Action blocked by capability policy.", file=sys.stderr)
            return 1

    reasons = _sandbox_escalation_reasons(
        command_text=command_text,
        command_tokens=command_tokens,
        profile=profile,
        allow_network=allow_network,
    )
    escalated = bool(reasons)
    approved = not escalated
    decision_source = "not-required"
    event: Optional[Dict[str, Any]] = None

    if escalated:
        if args.approve_escalation:
            approved = True
            decision_source = "flag"
        else:
            reason_summary = ", ".join(str(item.get("id", "")) for item in reasons if item.get("id")) or "unknown"
            approved = _prompt_yes_no(
                (
                    "Sandbox escalation required "
                    f"({reason_summary}) for profile '{profile}'. Approve command execution?"
                ),
                default=False,
                non_interactive=not sys.stdin.isatty(),
            )
            decision_source = "prompt"

        event = _emit_sandbox_approval_event(
            trace_dir=trace_dir,
            command_text=command_text,
            profile=profile,
            allow_network=allow_network,
            reasons=reasons,
            approved=approved,
            source=decision_source,
        )
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="sandbox_approval",
            input_summary=command_text,
            output_summary="approved" if approved else "denied",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="ok" if approved else "blocked",
            metadata=_sandbox_trace_metadata(
                {
                    "decision_source": decision_source,
                    "reasons": reasons,
                    "event_id": event.get("event_id") if isinstance(event, dict) else None,
                },
                policy_state=policy_decision_state,
                policy_rule_id=str(policy_decision.get("policy_id", "")),
                escalated_state=True,
                approved_state=approved,
            ),
        )

        if not approved:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="sandbox_run",
                input_summary=command_text,
                output_summary="escalation denied",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="blocked",
                metadata=_sandbox_trace_metadata(
                    {
                        "escalation_reasons": reasons,
                        "event_id": event.get("event_id") if isinstance(event, dict) else None,
                    },
                    policy_state=policy_decision_state,
                    policy_rule_id=str(policy_decision.get("policy_id", "")),
                    escalated_state=True,
                    approved_state=False,
                ),
            )
            print(
                "Escalation required but not approved. Re-run with --approve-escalation to continue.",
                file=sys.stderr,
            )
            return 1

    run_cwd = Path(args.cwd).expanduser() if args.cwd else REPO_ROOT
    sandbox_env = os.environ.copy()
    sandbox_env["GAIA_SANDBOX_PROFILE"] = profile
    sandbox_env["GAIA_SANDBOX_NETWORK_MODE"] = network_mode
    sandbox_env["GAIA_SANDBOX_ESCALATION"] = "approved" if escalated else "not-required"
    sandbox_env["GAIA_POLICY_DECISION"] = policy_decision_state
    sandbox_env["GAIA_POLICY_ID"] = str(policy_decision.get("policy_id", "policy.default.v1"))

    if args.dry_run:
        print(f"Sandbox dry-run profile={profile} network={network_mode}")
        print(
            "Policy: "
            f"{policy_decision.get('decision')} "
            f"({policy_decision.get('policy_id', 'policy.default.v1')})"
        )
        print(f"Command: {command_text}")
        if escalated:
            reason_ids = ", ".join(str(item.get("id", "")) for item in reasons if item.get("id"))
            print(f"Escalation: approved ({reason_ids})")
        else:
            print("Escalation: not required")
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="sandbox_run",
            input_summary=command_text,
            output_summary="dry-run",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            metadata=_sandbox_trace_metadata(
                {
                    "dry_run": True,
                    "escalated": escalated,
                    "approved": approved,
                    "policy_confirmed": policy_confirmed,
                    "policy_decision": policy_decision,
                    "reasons": reasons,
                    "event_id": event.get("event_id") if isinstance(event, dict) else None,
                },
                policy_state=policy_decision_state,
                policy_rule_id=str(policy_decision.get("policy_id", "")),
                escalated_state=escalated,
                approved_state=approved,
            ),
        )
        return 0

    proc = subprocess.run(
        command_tokens,
        cwd=str(run_cwd),
        env=sandbox_env,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        print(f"Sandbox command exited with status {proc.returncode}.", file=sys.stderr)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="sandbox_run",
        input_summary=command_text,
        output_summary=f"exit_code={proc.returncode}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        status="ok" if proc.returncode == 0 else "error",
        metadata=_sandbox_trace_metadata(
            {
                "dry_run": False,
                "escalated": escalated,
                "approved": approved,
                "policy_confirmed": policy_confirmed,
                "policy_decision": policy_decision,
                "reasons": reasons,
                "event_id": event.get("event_id") if isinstance(event, dict) else None,
                "cwd": str(run_cwd),
                "return_code": proc.returncode,
            },
            policy_state=policy_decision_state,
            policy_rule_id=str(policy_decision.get("policy_id", "")),
            escalated_state=escalated,
            approved_state=approved,
        ),
    )
    return int(proc.returncode)


def _find_schedule(schedules: List[Dict[str, Any]], schedule_id: str) -> Optional[Dict[str, Any]]:
    for item in schedules:
        if str(item.get("id", "")).strip() == schedule_id:
            return item
    return None


def _find_reminder(schedules: List[Dict[str, Any]], reminder_id: str) -> Optional[Dict[str, Any]]:
    item = _find_schedule(schedules, reminder_id)
    if item is None:
        return None
    if not _is_reminder_schedule(item):
        return None
    return item


def _format_schedule_cadence(schedule: Dict[str, Any]) -> str:
    cadence_type = _schedule_cadence_type(schedule)
    if cadence_type == "interval":
        every = _schedule_interval_minutes(schedule)
        if every is None:
            return "interval(?)"
        return f"interval/{every}m"
    return "oneshot"


def _format_reminder_summary(schedule: Dict[str, Any]) -> str:
    message = _reminder_message(schedule)
    if not message:
        return "(empty)"
    return _summarize_text(message, max_chars=80)


def cmd_schedule_create(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="schedule create",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_create",
            input_summary="schedule create",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    profile_name = str(args.profile).strip().lower()
    if profile_name not in AUTOPILOT_PROFILES:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_create",
            input_summary=f"profile={profile_name}",
            output_summary="unknown profile",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Unknown profile: {profile_name}", file=sys.stderr)
        return 1

    every_minutes: Optional[int] = args.every_minutes if args.every_minutes is not None else None
    if every_minutes is not None and every_minutes <= 0:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_create",
            input_summary=f"profile={profile_name}",
            output_summary="invalid --every-minutes",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("--every-minutes must be a positive integer.", file=sys.stderr)
        return 1

    if every_minutes is None and not args.at:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_create",
            input_summary=f"profile={profile_name}",
            output_summary="missing cadence",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("Provide --at for one-shot schedules, --every-minutes for recurring schedules, or both.", file=sys.stderr)
        return 1

    window_minutes = int(args.window_minutes)
    if window_minutes <= 0:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_create",
            input_summary=f"profile={profile_name}",
            output_summary="invalid --window-minutes",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("--window-minutes must be a positive integer.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    try:
        first_due = _parse_datetime_utc(str(args.at), "--at") if args.at else None
    except ValueError as exc:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_create",
            input_summary=f"profile={profile_name}",
            output_summary=str(exc),
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(str(exc), file=sys.stderr)
        return 1

    cadence_type = "interval" if every_minutes is not None else "oneshot"
    if cadence_type == "interval" and first_due is None:
        first_due = now + timedelta(minutes=every_minutes or 1)
    if first_due is None:
        print("Internal error: schedule due time could not be resolved.", file=sys.stderr)
        return 1

    schedule_id = _new_record_id("sch")
    timestamp = _isoformat_utc(now)
    schedule_record: Dict[str, Any] = {
        "id": schedule_id,
        "action": "autopilot_profile_run",
        "payload": {"profile": profile_name},
        "status": "active",
        "cadence": {
            "type": cadence_type,
            "timezone": "UTC",
        },
        "window_minutes": window_minutes,
        "next_run_at": _isoformat_utc(first_due),
        "last_run_at": None,
        "last_run_key": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    if every_minutes is not None:
        schedule_record["cadence"]["every_minutes"] = every_minutes

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    schedules.append(schedule_record)
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="schedule_create",
        input_summary=f"profile={profile_name}",
        output_summary=f"created {schedule_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={
            "schedule_id": schedule_id,
            "profile": profile_name,
            "cadence": cadence_type,
            "next_run_at": schedule_record["next_run_at"],
        },
    )
    print(f"{schedule_id} active next={schedule_record['next_run_at']} profile={profile_name} cadence={_format_schedule_cadence(schedule_record)}")
    return 0


def cmd_schedule_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary="schedule list",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_list",
            input_summary="schedule list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    wanted_status = str(args.status).strip().lower()
    schedules = _load_records(_schedules_path(storage_dir))
    if wanted_status != "all":
        schedules = [
            item
            for item in schedules
            if str(item.get("status", "active")).strip().lower() == wanted_status
        ]

    schedules.sort(
        key=lambda item: (
            str(item.get("next_run_at", "")) == "",
            str(item.get("next_run_at", "")),
            str(item.get("id", "")),
        )
    )

    if not schedules:
        print("No schedules found.")
    else:
        for item in schedules:
            schedule_id = str(item.get("id", "?"))
            status = str(item.get("status", "?")).strip().lower()
            next_run_at = str(item.get("next_run_at", "")).strip() or "-"
            profile_name = _schedule_profile_name(item) or "unknown"
            cadence = _format_schedule_cadence(item)
            window_minutes = _schedule_window_minutes(item)
            print(
                f"{schedule_id} {status:<9} next={next_run_at} "
                f"profile={profile_name} cadence={cadence} window={window_minutes}m"
            )

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="schedule_list",
        input_summary=f"status={wanted_status}",
        output_summary=f"{len(schedules)} schedules",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    return 0


def cmd_schedule_update(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="schedule update",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_update",
            input_summary=f"schedule_id={args.schedule_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    schedule_id = str(args.schedule_id).strip()
    target = _find_schedule(schedules, schedule_id)
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_update",
            input_summary=f"schedule_id={schedule_id}",
            output_summary="schedule not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Schedule not found: {schedule_id}", file=sys.stderr)
        return 1

    if (
        args.profile is None
        and args.every_minutes is None
        and args.at is None
        and args.window_minutes is None
        and args.status is None
    ):
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_update",
            input_summary=f"schedule_id={schedule_id}",
            output_summary="no updates provided",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("No updates requested. Provide one or more update flags.", file=sys.stderr)
        return 1

    if args.profile is not None:
        profile_name = str(args.profile).strip().lower()
        if profile_name not in AUTOPILOT_PROFILES:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="schedule_update",
                input_summary=f"schedule_id={schedule_id}",
                output_summary="unknown profile",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(f"Unknown profile: {profile_name}", file=sys.stderr)
            return 1
        payload = target.setdefault("payload", {})
        if not isinstance(payload, dict):
            payload = {}
            target["payload"] = payload
        payload["profile"] = profile_name

    if args.window_minutes is not None:
        window_minutes = int(args.window_minutes)
        if window_minutes <= 0:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="schedule_update",
                input_summary=f"schedule_id={schedule_id}",
                output_summary="invalid --window-minutes",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print("--window-minutes must be a positive integer.", file=sys.stderr)
            return 1
        target["window_minutes"] = window_minutes

    parsed_at: Optional[datetime] = None
    if args.at is not None:
        try:
            parsed_at = _parse_datetime_utc(str(args.at), "--at")
        except ValueError as exc:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="schedule_update",
                input_summary=f"schedule_id={schedule_id}",
                output_summary=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(str(exc), file=sys.stderr)
            return 1

    if args.every_minutes is not None:
        every_minutes = int(args.every_minutes)
        if every_minutes <= 0:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="schedule_update",
                input_summary=f"schedule_id={schedule_id}",
                output_summary="invalid --every-minutes",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print("--every-minutes must be a positive integer.", file=sys.stderr)
            return 1
        cadence = target.setdefault("cadence", {})
        if not isinstance(cadence, dict):
            cadence = {}
            target["cadence"] = cadence
        cadence["type"] = "interval"
        cadence["every_minutes"] = every_minutes
        cadence["timezone"] = "UTC"
        if parsed_at is None:
            reference = datetime.now(timezone.utc)
            parsed_at = _next_interval_due_after(
                anchor_due=reference,
                every_minutes=every_minutes,
                reference=reference,
            )

    if parsed_at is not None:
        target["next_run_at"] = _isoformat_utc(parsed_at)

    if args.status is not None:
        status = str(args.status).strip().lower()
        if status not in SCHEDULE_MUTABLE_STATUS_CHOICES:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="schedule_update",
                input_summary=f"schedule_id={schedule_id}",
                output_summary="invalid --status",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(
                f"Invalid --status '{status}'. "
                f"Expected one of: {', '.join(SCHEDULE_MUTABLE_STATUS_CHOICES)}.",
                file=sys.stderr,
            )
            return 1
        target["status"] = status
        if status == "canceled":
            target["next_run_at"] = None
            target["canceled_at"] = _isoformat_utc(datetime.now(timezone.utc))
        elif status == "active" and not str(target.get("next_run_at", "")).strip():
            cadence_type = _schedule_cadence_type(target)
            if cadence_type == "interval":
                every = _schedule_interval_minutes(target)
                if every is None:
                    print("Cannot activate interval schedule with invalid cadence.", file=sys.stderr)
                    return 1
                target["next_run_at"] = _isoformat_utc(
                    datetime.now(timezone.utc) + timedelta(minutes=every)
                )
            else:
                print("Cannot activate one-shot schedule without --at.", file=sys.stderr)
                return 1

    target["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="schedule_update",
        input_summary=f"schedule_id={schedule_id}",
        output_summary=f"updated {schedule_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={
            "schedule_id": schedule_id,
            "status": target.get("status"),
            "next_run_at": target.get("next_run_at"),
        },
    )
    print(
        f"{schedule_id} {target.get('status', '?')} next={target.get('next_run_at') or '-'} "
        f"profile={_schedule_profile_name(target) or 'unknown'} cadence={_format_schedule_cadence(target)}"
    )
    return 0


def cmd_schedule_cancel(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="schedule cancel",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_cancel",
            input_summary=f"schedule_id={args.schedule_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    schedule_id = str(args.schedule_id).strip()
    target = _find_schedule(schedules, schedule_id)
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_cancel",
            input_summary=f"schedule_id={schedule_id}",
            output_summary="schedule not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Schedule not found: {schedule_id}", file=sys.stderr)
        return 1

    target["status"] = "canceled"
    target["next_run_at"] = None
    target["canceled_at"] = _isoformat_utc(datetime.now(timezone.utc))
    target["updated_at"] = target["canceled_at"]
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="schedule_cancel",
        input_summary=f"schedule_id={schedule_id}",
        output_summary=f"canceled {schedule_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"schedule_id": schedule_id},
    )
    print(f"{schedule_id} canceled")
    return 0


def cmd_schedule_run_due(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="schedule run-due",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_run_due",
            input_summary="schedule run-due",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    reference = datetime.now(timezone.utc)
    if args.at is not None:
        try:
            reference = _parse_datetime_utc(str(args.at), "--at")
        except ValueError as exc:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="schedule_run_due",
                input_summary=f"at={args.at}",
                output_summary=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(str(exc), file=sys.stderr)
            return 1

    override_window: Optional[int] = args.window_minutes
    if override_window is not None and override_window <= 0:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="schedule_run_due",
            input_summary=f"at={_isoformat_utc(reference)}",
            output_summary="invalid --window-minutes",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("--window-minutes must be a positive integer.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    run_index = _load_schedule_run_keys(storage_dir)

    executed = 0
    skipped = 0
    failed = 0

    for schedule in schedules:
        status = str(schedule.get("status", "active")).strip().lower()
        if status != "active":
            continue
        is_reminder = _is_reminder_schedule(schedule)

        raw_due = str(schedule.get("next_run_at", "")).strip()
        if not raw_due:
            continue

        try:
            due_at = _parse_datetime_utc(raw_due, "schedule.next_run_at")
        except ValueError:
            schedule["status"] = "failed"
            schedule["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
            failed += 1
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_fail" if is_reminder else "schedule_fail",
                input_summary=f"schedule_id={schedule.get('id', '?')}",
                output_summary="invalid next_run_at",
                duration_ms=0.0,
                permission_level=permission_level,
                status="error",
                metadata={"schedule_id": schedule.get("id"), "schedule_action": _schedule_action(schedule)},
            )
            continue

        lag_minutes = (reference - due_at).total_seconds() / 60.0
        if lag_minutes < 0:
            continue

        effective_window = override_window if override_window is not None else _schedule_window_minutes(schedule)
        schedule_id = str(schedule.get("id", "")).strip()
        run_key = _schedule_run_key(schedule_id, due_at)

        if lag_minutes > float(effective_window):
            skipped += 1
            _append_jsonl(
                _schedule_runs_path(storage_dir),
                {
                    "run_key": run_key,
                    "schedule_id": schedule_id,
                    "due_at": _isoformat_utc(due_at),
                    "executed_at": _isoformat_utc(datetime.now(timezone.utc)),
                    "status": "skipped",
                    "reason": "missed_window",
                },
            )
            run_index[run_key] = {"status": "skipped", "reason": "missed_window"}
            _advance_schedule_after_due(schedule, due_at=due_at, reference=reference, result="skipped")
            schedule["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_skip" if is_reminder else "schedule_skip",
                input_summary=f"schedule_id={schedule_id}",
                output_summary=f"missed window ({lag_minutes:.2f}m > {effective_window}m)",
                duration_ms=0.0,
                permission_level=permission_level,
                metadata={
                    "schedule_id": schedule_id,
                    "run_key": run_key,
                    "reason": "missed_window",
                    "schedule_action": _schedule_action(schedule),
                },
            )
            print(f"- skipped {schedule_id}: missed window")
            continue

        if run_key in run_index:
            skipped += 1
            _advance_schedule_after_due(schedule, due_at=due_at, reference=reference, result="duplicate")
            schedule["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_skip" if is_reminder else "schedule_skip",
                input_summary=f"schedule_id={schedule_id}",
                output_summary="duplicate run key",
                duration_ms=0.0,
                permission_level=permission_level,
                metadata={
                    "schedule_id": schedule_id,
                    "run_key": run_key,
                    "reason": "duplicate_run_key",
                    "schedule_action": _schedule_action(schedule),
                },
            )
            print(f"- skipped {schedule_id}: duplicate run key")
            continue

        run_start = time.perf_counter()
        ok, result_message = _execute_schedule_action(
            schedule,
            cfg_path=cfg_path,
            storage_dir=storage_dir,
            trace_dir=trace_dir,
            due_at=due_at,
        )
        duration_ms = (time.perf_counter() - run_start) * 1000
        now_ts = _isoformat_utc(datetime.now(timezone.utc))
        _append_jsonl(
            _schedule_runs_path(storage_dir),
            {
                "run_key": run_key,
                "schedule_id": schedule_id,
                "due_at": _isoformat_utc(due_at),
                "executed_at": now_ts,
                "status": "success" if ok else "failed",
                "result": result_message,
            },
        )
        run_index[run_key] = {"status": "success" if ok else "failed", "result": result_message}
        schedule["last_run_at"] = now_ts
        schedule["last_run_key"] = run_key
        _advance_schedule_after_due(
            schedule,
            due_at=due_at,
            reference=reference,
            result="success" if ok else "failed",
        )
        schedule["updated_at"] = now_ts

        if ok:
            executed += 1
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_run" if is_reminder else "schedule_run",
                input_summary=f"schedule_id={schedule_id}",
                output_summary=result_message,
                duration_ms=duration_ms,
                permission_level=permission_level,
                metadata={
                    "schedule_id": schedule_id,
                    "run_key": run_key,
                    "due_at": _isoformat_utc(due_at),
                    "schedule_action": _schedule_action(schedule),
                },
            )
            print(f"- executed {schedule_id}: {result_message}")
        else:
            failed += 1
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_fail" if is_reminder else "schedule_fail",
                input_summary=f"schedule_id={schedule_id}",
                output_summary=result_message,
                duration_ms=duration_ms,
                permission_level=permission_level,
                status="error",
                metadata={
                    "schedule_id": schedule_id,
                    "run_key": run_key,
                    "due_at": _isoformat_utc(due_at),
                    "schedule_action": _schedule_action(schedule),
                },
            )
            print(f"- failed {schedule_id}: {result_message}", file=sys.stderr)

    _save_records(schedules_path, schedules)
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="schedule_run_due",
        input_summary=f"at={_isoformat_utc(reference)}",
        output_summary=f"executed={executed} skipped={skipped} failed={failed}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"executed": executed, "skipped": skipped, "failed": failed},
    )
    print(f"run-due summary: executed={executed} skipped={skipped} failed={failed}")
    return 1 if failed > 0 else 0


def cmd_reminder_create(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="reminder create",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_create",
            input_summary="reminder create",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    message = str(args.message).strip()
    if not message:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_create",
            input_summary="reminder create",
            output_summary="empty message",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("Reminder message cannot be empty.", file=sys.stderr)
        return 1

    every_minutes: Optional[int] = args.every_minutes if args.every_minutes is not None else None
    if every_minutes is not None and every_minutes <= 0:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_create",
            input_summary="reminder create",
            output_summary="invalid --every-minutes",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("--every-minutes must be a positive integer.", file=sys.stderr)
        return 1

    window_minutes = int(args.window_minutes)
    if window_minutes <= 0:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_create",
            input_summary="reminder create",
            output_summary="invalid --window-minutes",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("--window-minutes must be a positive integer.", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    parsed_at: Optional[datetime] = None
    if args.at is not None:
        try:
            parsed_at = _parse_datetime_utc(str(args.at), "--at")
        except ValueError as exc:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_create",
                input_summary="reminder create",
                output_summary=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(str(exc), file=sys.stderr)
            return 1

    if every_minutes is None and parsed_at is None:
        every_minutes = REMINDER_DEFAULT_CADENCE_MINUTES

    cadence_type = "interval" if every_minutes is not None else "oneshot"
    if cadence_type == "interval" and parsed_at is None:
        parsed_at = now + timedelta(minutes=every_minutes or REMINDER_DEFAULT_CADENCE_MINUTES)
    if parsed_at is None:
        print("Internal error: reminder due time could not be resolved.", file=sys.stderr)
        return 1

    reminder_id = _new_record_id("rem")
    timestamp = _isoformat_utc(now)
    reminder_record: Dict[str, Any] = {
        "id": reminder_id,
        "action": "reminder_emit",
        "payload": {"message": message},
        "status": "active",
        "cadence": {
            "type": cadence_type,
            "timezone": "UTC",
        },
        "window_minutes": window_minutes,
        "next_run_at": _isoformat_utc(parsed_at),
        "last_run_at": None,
        "last_run_key": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    if every_minutes is not None:
        reminder_record["cadence"]["every_minutes"] = every_minutes

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    schedules.append(reminder_record)
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="reminder_create",
        input_summary="reminder create",
        output_summary=f"created {reminder_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={
            "reminder_id": reminder_id,
            "cadence": cadence_type,
            "next_run_at": reminder_record["next_run_at"],
        },
    )
    print(
        f"{reminder_id} active next={reminder_record['next_run_at']} cadence={_format_schedule_cadence(reminder_record)} "
        f"window={window_minutes}m message={_format_reminder_summary(reminder_record)}"
    )
    return 0


def cmd_reminder_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_read",
        input_summary="reminder list",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_list",
            input_summary="reminder list",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    wanted_status = str(args.status).strip().lower()
    reminders = [item for item in _load_records(_schedules_path(storage_dir)) if _is_reminder_schedule(item)]
    if wanted_status != "all":
        reminders = [
            item
            for item in reminders
            if str(item.get("status", "active")).strip().lower() == wanted_status
        ]

    reminders.sort(
        key=lambda item: (
            str(item.get("next_run_at", "")) == "",
            str(item.get("next_run_at", "")),
            str(item.get("id", "")),
        )
    )

    if not reminders:
        print("No reminders found.")
    else:
        for item in reminders:
            reminder_id = str(item.get("id", "?"))
            status = str(item.get("status", "?")).strip().lower()
            next_run_at = str(item.get("next_run_at", "")).strip() or "-"
            cadence = _format_schedule_cadence(item)
            window_minutes = _schedule_window_minutes(item)
            print(
                f"{reminder_id} {status:<9} next={next_run_at} cadence={cadence} "
                f"window={window_minutes}m message={_format_reminder_summary(item)}"
            )

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="reminder_list",
        input_summary=f"status={wanted_status}",
        output_summary=f"{len(reminders)} reminders",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
    )
    return 0


def cmd_reminder_update(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="reminder update",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_update",
            input_summary=f"reminder_id={args.reminder_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    if (
        args.message is None
        and args.every_minutes is None
        and args.at is None
        and args.window_minutes is None
    ):
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_update",
            input_summary=f"reminder_id={args.reminder_id}",
            output_summary="no updates provided",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print("No updates requested. Provide one or more update flags.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    reminder_id = str(args.reminder_id).strip()
    target = _find_reminder(schedules, reminder_id)
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_update",
            input_summary=f"reminder_id={reminder_id}",
            output_summary="reminder not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Reminder not found: {reminder_id}", file=sys.stderr)
        return 1

    if args.message is not None:
        message = str(args.message).strip()
        if not message:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_update",
                input_summary=f"reminder_id={reminder_id}",
                output_summary="empty message",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print("Reminder message cannot be empty.", file=sys.stderr)
            return 1
        payload = target.setdefault("payload", {})
        if not isinstance(payload, dict):
            payload = {}
            target["payload"] = payload
        payload["message"] = message

    if args.window_minutes is not None:
        window_minutes = int(args.window_minutes)
        if window_minutes <= 0:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_update",
                input_summary=f"reminder_id={reminder_id}",
                output_summary="invalid --window-minutes",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print("--window-minutes must be a positive integer.", file=sys.stderr)
            return 1
        target["window_minutes"] = window_minutes

    parsed_at: Optional[datetime] = None
    if args.at is not None:
        try:
            parsed_at = _parse_datetime_utc(str(args.at), "--at")
        except ValueError as exc:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_update",
                input_summary=f"reminder_id={reminder_id}",
                output_summary=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(str(exc), file=sys.stderr)
            return 1

    if args.every_minutes is not None:
        every_minutes = int(args.every_minutes)
        if every_minutes <= 0:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_update",
                input_summary=f"reminder_id={reminder_id}",
                output_summary="invalid --every-minutes",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print("--every-minutes must be a positive integer.", file=sys.stderr)
            return 1
        cadence = target.setdefault("cadence", {})
        if not isinstance(cadence, dict):
            cadence = {}
            target["cadence"] = cadence
        cadence["type"] = "interval"
        cadence["every_minutes"] = every_minutes
        cadence["timezone"] = "UTC"
        if parsed_at is None:
            parsed_at = datetime.now(timezone.utc) + timedelta(minutes=every_minutes)

    if parsed_at is not None:
        target["next_run_at"] = _isoformat_utc(parsed_at)

    target["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="reminder_update",
        input_summary=f"reminder_id={reminder_id}",
        output_summary=f"updated {reminder_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={
            "reminder_id": reminder_id,
            "status": target.get("status"),
            "next_run_at": target.get("next_run_at"),
        },
    )
    print(
        f"{reminder_id} {target.get('status', '?')} next={target.get('next_run_at') or '-'} "
        f"cadence={_format_schedule_cadence(target)} window={_schedule_window_minutes(target)}m "
        f"message={_format_reminder_summary(target)}"
    )
    return 0


def cmd_reminder_pause(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="reminder pause",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_pause",
            input_summary=f"reminder_id={args.reminder_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    reminder_id = str(args.reminder_id).strip()
    target = _find_reminder(schedules, reminder_id)
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_pause",
            input_summary=f"reminder_id={reminder_id}",
            output_summary="reminder not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Reminder not found: {reminder_id}", file=sys.stderr)
        return 1

    status = str(target.get("status", "active")).strip().lower()
    if status in ("canceled", "completed", "failed"):
        print(f"Cannot pause reminder in '{status}' state.", file=sys.stderr)
        return 1

    target["status"] = "paused"
    target["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="reminder_pause",
        input_summary=f"reminder_id={reminder_id}",
        output_summary=f"paused {reminder_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"reminder_id": reminder_id},
    )
    print(f"{reminder_id} paused next={target.get('next_run_at') or '-'}")
    return 0


def cmd_reminder_resume(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="reminder resume",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_resume",
            input_summary=f"reminder_id={args.reminder_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    reminder_id = str(args.reminder_id).strip()
    target = _find_reminder(schedules, reminder_id)
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_resume",
            input_summary=f"reminder_id={reminder_id}",
            output_summary="reminder not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Reminder not found: {reminder_id}", file=sys.stderr)
        return 1

    status = str(target.get("status", "active")).strip().lower()
    if status in ("canceled", "completed", "failed"):
        print(f"Cannot resume reminder in '{status}' state.", file=sys.stderr)
        return 1

    parsed_at: Optional[datetime] = None
    if args.at is not None:
        try:
            parsed_at = _parse_datetime_utc(str(args.at), "--at")
        except ValueError as exc:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_resume",
                input_summary=f"reminder_id={reminder_id}",
                output_summary=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(str(exc), file=sys.stderr)
            return 1

    if parsed_at is not None:
        target["next_run_at"] = _isoformat_utc(parsed_at)
    elif not str(target.get("next_run_at", "")).strip():
        cadence_type = _schedule_cadence_type(target)
        if cadence_type == "interval":
            every = _schedule_interval_minutes(target)
            if every is None:
                print("Cannot resume interval reminder with invalid cadence.", file=sys.stderr)
                return 1
            target["next_run_at"] = _isoformat_utc(datetime.now(timezone.utc) + timedelta(minutes=every))
        else:
            print("Cannot resume one-shot reminder without --at.", file=sys.stderr)
            return 1

    target["status"] = "active"
    target["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="reminder_resume",
        input_summary=f"reminder_id={reminder_id}",
        output_summary=f"resumed {reminder_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"reminder_id": reminder_id, "next_run_at": target.get("next_run_at")},
    )
    print(f"{reminder_id} active next={target.get('next_run_at') or '-'}")
    return 0


def cmd_reminder_snooze(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="reminder snooze",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_snooze",
            input_summary=f"reminder_id={args.reminder_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    reminder_id = str(args.reminder_id).strip()
    target = _find_reminder(schedules, reminder_id)
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_snooze",
            input_summary=f"reminder_id={reminder_id}",
            output_summary="reminder not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Reminder not found: {reminder_id}", file=sys.stderr)
        return 1

    status = str(target.get("status", "active")).strip().lower()
    if status in ("canceled", "completed", "failed"):
        print(f"Cannot snooze reminder in '{status}' state.", file=sys.stderr)
        return 1

    due_at: Optional[datetime] = None
    if args.until is not None:
        try:
            due_at = _parse_datetime_utc(str(args.until), "--until")
        except ValueError as exc:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_snooze",
                input_summary=f"reminder_id={reminder_id}",
                output_summary=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print(str(exc), file=sys.stderr)
            return 1
    else:
        minutes = int(args.minutes)
        if minutes <= 0:
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="reminder_snooze",
                input_summary=f"reminder_id={reminder_id}",
                output_summary="invalid --minutes",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="error",
            )
            print("--minutes must be a positive integer.", file=sys.stderr)
            return 1
        due_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    target["status"] = "active"
    target["next_run_at"] = _isoformat_utc(due_at)
    target["updated_at"] = _isoformat_utc(datetime.now(timezone.utc))
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="reminder_snooze",
        input_summary=f"reminder_id={reminder_id}",
        output_summary=f"snoozed {reminder_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"reminder_id": reminder_id, "next_run_at": target.get("next_run_at")},
    )
    print(f"{reminder_id} snoozed next={target.get('next_run_at') or '-'}")
    return 0


def cmd_reminder_dismiss(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    allowed, permission_level = _enforce_capability(
        cfg=cfg,
        capability="file_write",
        input_summary="reminder dismiss",
        trace_dir=trace_dir,
        non_interactive=False,
    )
    if not allowed:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_dismiss",
            input_summary=f"reminder_id={args.reminder_id}",
            output_summary="blocked by permission policy",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="blocked",
        )
        print("Action blocked by capability policy.", file=sys.stderr)
        return 1

    schedules_path = _schedules_path(storage_dir)
    schedules = _load_records(schedules_path)
    reminder_id = str(args.reminder_id).strip()
    target = _find_reminder(schedules, reminder_id)
    if target is None:
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="reminder_dismiss",
            input_summary=f"reminder_id={reminder_id}",
            output_summary="reminder not found",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level=permission_level,
            status="error",
        )
        print(f"Reminder not found: {reminder_id}", file=sys.stderr)
        return 1

    now_ts = _isoformat_utc(datetime.now(timezone.utc))
    target["status"] = "canceled"
    target["next_run_at"] = None
    target["dismissed_at"] = now_ts
    target["updated_at"] = now_ts
    _save_records(schedules_path, schedules)

    _write_action_trace(
        trace_dir=trace_dir,
        action_type="reminder_dismiss",
        input_summary=f"reminder_id={reminder_id}",
        output_summary=f"dismissed {reminder_id}",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level=permission_level,
        metadata={"reminder_id": reminder_id},
    )
    print(f"{reminder_id} dismissed")
    return 0


def cmd_autopilot_run(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    storage_dir = _resolve_storage_dir(cfg, args.storage_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    profile_name = str(args.profile).strip().lower()
    profile = AUTOPILOT_PROFILES.get(profile_name)
    if not isinstance(profile, dict):
        available = ", ".join(sorted(AUTOPILOT_PROFILES.keys()))
        print(f"Unknown profile '{profile_name}'. Available profiles: {available}", file=sys.stderr)
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="autopilot_run",
            input_summary=f"profile={profile_name}",
            output_summary="unknown profile",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        return 1

    profile_steps = profile.get("steps", [])
    if not isinstance(profile_steps, list) or not profile_steps:
        print(f"Profile '{profile_name}' has no runnable steps.", file=sys.stderr)
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="autopilot_run",
            input_summary=f"profile={profile_name}",
            output_summary="profile has no steps",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        return 1

    declared_caps_raw = profile.get("allowed_capabilities", [])
    declared_caps = (
        [str(item).strip() for item in declared_caps_raw if str(item).strip()]
        if isinstance(declared_caps_raw, list)
        else []
    )
    if not declared_caps:
        print(f"Profile '{profile_name}' has no declared capabilities.", file=sys.stderr)
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="autopilot_run",
            input_summary=f"profile={profile_name}",
            output_summary="profile has no declared capabilities",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            status="error",
        )
        return 1

    capability_levels: Dict[str, str] = {}
    for capability in declared_caps:
        allowed, permission_level = _enforce_capability(
            cfg=cfg,
            capability=capability,
            input_summary=f"autopilot profile={profile_name}",
            trace_dir=trace_dir,
            non_interactive=True,
            prompt=f"Autopilot requires capability '{capability}'. Allow run?",
        )
        capability_levels[capability] = permission_level
        if not allowed:
            print(
                f"Autopilot blocked by policy for capability '{capability}' "
                f"(level={permission_level}).",
                file=sys.stderr,
            )
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="autopilot_run",
                input_summary=f"profile={profile_name}",
                output_summary=f"blocked capability {capability}",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=permission_level,
                status="blocked",
                metadata={
                    "profile": profile_name,
                    "capability": capability,
                    "dry_run": bool(args.dry_run),
                },
            )
            return 1

    for step in profile_steps:
        if not isinstance(step, dict):
            continue
        action = str(step.get("action", "")).strip()
        step_id = str(step.get("id", "")).strip() or "unknown-step"
        required_capability = AUTOPILOT_STEP_CAPABILITY.get(action, "")
        if not required_capability:
            print(
                f"Profile '{profile_name}' contains unsupported step action '{action}' "
                f"({step_id}).",
                file=sys.stderr,
            )
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="autopilot_run",
                input_summary=f"profile={profile_name}",
                output_summary=f"unsupported action {action}",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="error",
                metadata={"profile": profile_name, "step_id": step_id},
            )
            return 1
        if required_capability not in declared_caps:
            print(
                f"Profile '{profile_name}' step '{step_id}' requires undeclared "
                f"capability '{required_capability}'.",
                file=sys.stderr,
            )
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="autopilot_run",
                input_summary=f"profile={profile_name}",
                output_summary=f"undeclared capability {required_capability}",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level="safe",
                status="error",
                metadata={
                    "profile": profile_name,
                    "step_id": step_id,
                    "required_capability": required_capability,
                },
            )
            return 1

    run_id = _new_record_id("apr")
    run_record: Dict[str, Any] = {
        "run_id": run_id,
        "profile": profile_name,
        "description": str(profile.get("description", "")).strip(),
        "dry_run": bool(args.dry_run),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "capabilities": capability_levels,
        "steps": [],
        "status": "running",
    }

    if args.dry_run:
        run_record["status"] = "dry-run"
        run_record["finished_at"] = datetime.now(timezone.utc).isoformat()
        run_record["planned_steps"] = [
            {
                "id": str(step.get("id", "")).strip(),
                "action": str(step.get("action", "")).strip(),
            }
            for step in profile_steps
            if isinstance(step, dict)
        ]
        _append_jsonl(_autopilot_runs_path(trace_dir), run_record)
        _write_action_trace(
            trace_dir=trace_dir,
            action_type="autopilot_run",
            input_summary=f"profile={profile_name}",
            output_summary="dry-run preview complete",
            duration_ms=(time.perf_counter() - start) * 1000,
            permission_level="safe",
            metadata={
                "run_id": run_id,
                "profile": profile_name,
                "dry_run": True,
                "step_count": len(run_record["planned_steps"]),
            },
        )
        print(f"Dry-run autopilot plan for profile '{profile_name}' ({len(run_record['planned_steps'])} steps)")
        for idx, step in enumerate(run_record["planned_steps"], start=1):
            print(f"{idx}. {step.get('id', '?')} ({step.get('action', '?')})")
        return 0

    snapshot = _snapshot_storage_state(storage_dir)
    for raw_step in profile_steps:
        if not isinstance(raw_step, dict):
            continue
        step_id = str(raw_step.get("id", "")).strip() or _new_record_id("aps")
        action = str(raw_step.get("action", "")).strip()
        required_capability = AUTOPILOT_STEP_CAPABILITY.get(action, "confirm")
        allowed, step_level = _enforce_capability(
            cfg=cfg,
            capability=required_capability,
            input_summary=f"autopilot step {step_id}",
            trace_dir=trace_dir,
            non_interactive=True,
            prompt=f"Autopilot step '{step_id}' requires '{required_capability}'. Allow?",
        )
        if not allowed:
            incident = {
                "incident_id": _new_record_id("api"),
                "run_id": run_id,
                "profile": profile_name,
                "step_id": step_id,
                "error": f"blocked by capability policy: {required_capability}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            rollback_ok, rollback_message = _restore_storage_state(snapshot)
            incident["rollback"] = {
                "status": "ok" if rollback_ok else "failed",
                "details": rollback_message,
            }
            _append_jsonl(_autopilot_incidents_path(trace_dir), incident)
            run_record["status"] = "failed"
            run_record["finished_at"] = datetime.now(timezone.utc).isoformat()
            run_record["steps"].append(
                {
                    "step_id": step_id,
                    "action": action,
                    "status": "blocked",
                    "error": incident["error"],
                }
            )
            run_record["rollback"] = incident["rollback"]
            _append_jsonl(_autopilot_runs_path(trace_dir), run_record)
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="autopilot_run",
                input_summary=f"profile={profile_name}",
                output_summary=f"failed at step {step_id}",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=step_level,
                status="blocked",
                metadata={
                    "run_id": run_id,
                    "profile": profile_name,
                    "step_id": step_id,
                    "rollback": run_record.get("rollback", {}),
                },
            )
            print(f"Autopilot run failed at step '{step_id}': {incident['error']}", file=sys.stderr)
            return 1

        forced_failure = str(args.force_failure_step or "").strip()
        if forced_failure and forced_failure == step_id:
            error_text = f"forced failure at step {step_id}"
            incident = {
                "incident_id": _new_record_id("api"),
                "run_id": run_id,
                "profile": profile_name,
                "step_id": step_id,
                "error": error_text,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            rollback_ok, rollback_message = _restore_storage_state(snapshot)
            incident["rollback"] = {
                "status": "ok" if rollback_ok else "failed",
                "details": rollback_message,
            }
            _append_jsonl(_autopilot_incidents_path(trace_dir), incident)
            run_record["status"] = "failed"
            run_record["finished_at"] = datetime.now(timezone.utc).isoformat()
            run_record["steps"].append(
                {
                    "step_id": step_id,
                    "action": action,
                    "status": "error",
                    "error": error_text,
                }
            )
            run_record["rollback"] = incident["rollback"]
            _append_jsonl(_autopilot_runs_path(trace_dir), run_record)
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="autopilot_run",
                input_summary=f"profile={profile_name}",
                output_summary=error_text,
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=step_level,
                status="error",
                metadata={
                    "run_id": run_id,
                    "profile": profile_name,
                    "step_id": step_id,
                    "rollback": run_record.get("rollback", {}),
                },
            )
            print(f"Autopilot run failed: {error_text}", file=sys.stderr)
            return 1

        try:
            step_result = _execute_autopilot_step(raw_step, storage_dir)
            run_record["steps"].append(step_result)
        except Exception as exc:
            incident = {
                "incident_id": _new_record_id("api"),
                "run_id": run_id,
                "profile": profile_name,
                "step_id": step_id,
                "error": str(exc),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            rollback_ok, rollback_message = _restore_storage_state(snapshot)
            incident["rollback"] = {
                "status": "ok" if rollback_ok else "failed",
                "details": rollback_message,
            }
            _append_jsonl(_autopilot_incidents_path(trace_dir), incident)
            run_record["status"] = "failed"
            run_record["finished_at"] = datetime.now(timezone.utc).isoformat()
            run_record["steps"].append(
                {
                    "step_id": step_id,
                    "action": action,
                    "status": "error",
                    "error": str(exc),
                }
            )
            run_record["rollback"] = incident["rollback"]
            _append_jsonl(_autopilot_runs_path(trace_dir), run_record)
            _write_action_trace(
                trace_dir=trace_dir,
                action_type="autopilot_run",
                input_summary=f"profile={profile_name}",
                output_summary=f"failed at step {step_id}",
                duration_ms=(time.perf_counter() - start) * 1000,
                permission_level=step_level,
                status="error",
                metadata={
                    "run_id": run_id,
                    "profile": profile_name,
                    "step_id": step_id,
                    "rollback": run_record.get("rollback", {}),
                },
            )
            print(f"Autopilot run failed at step '{step_id}': {exc}", file=sys.stderr)
            return 1

    run_record["status"] = "success"
    run_record["finished_at"] = datetime.now(timezone.utc).isoformat()
    run_record["rollback"] = {"status": "not-needed", "details": ""}
    _append_jsonl(_autopilot_runs_path(trace_dir), run_record)
    _write_action_trace(
        trace_dir=trace_dir,
        action_type="autopilot_run",
        input_summary=f"profile={profile_name}",
        output_summary=f"completed {len(run_record['steps'])} steps",
        duration_ms=(time.perf_counter() - start) * 1000,
        permission_level="safe",
        metadata={
            "run_id": run_id,
            "profile": profile_name,
            "dry_run": False,
            "step_count": len(run_record["steps"]),
        },
    )

    print(f"Autopilot run complete: {run_id}")
    for step in run_record["steps"]:
        print(f"- {step.get('step_id', '?')}: {step.get('result', step.get('status', 'ok'))}")
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

    active_profile = cfg.get("auth", {}).get("active_profile")
    active_profile = active_profile if isinstance(active_profile, dict) else {}
    active_profile_provider = str(active_profile.get("provider", "")).strip().lower()

    # Ensure old launcher configs linked to OAuth profiles converge to the
    # runtime-compatible provider defaults unless an explicit override exists.
    if not args.reasoning_provider and _apply_oauth_runtime_defaults(cfg_path, active_profile_provider):
        cfg = _ensure_config_exists(cfg_path)
        print("[ok] aligned runtime defaults from linked OAuth profile: openai/gpt-4.1-mini")

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

    oauth_error = ""
    loaded_from_oauth = False
    oauth_access_token, oauth_error = _linked_openai_oauth_access_token(cfg)
    if oauth_access_token and not env.get("OPENAI_API_KEY", "").strip():
        env["OPENAI_API_KEY"] = oauth_access_token
        loaded_from_oauth = True

    reasoning_cfg = cfg.get("reasoning", {})
    reasoning_cfg = reasoning_cfg if isinstance(reasoning_cfg, dict) else {}
    reasoning_override_locked = _normalize_bool_default(
        reasoning_cfg.get("explicit_provider_override", False),
        False,
    )
    profile_cfg = cfg.get("profile", {})
    profile_cfg = profile_cfg if isinstance(profile_cfg, dict) else {}
    profile_provider = str(profile_cfg.get("default_provider", "")).strip().lower()
    configured_provider = str(reasoning_cfg.get("provider", "")).strip().lower()
    configured_model = str(reasoning_cfg.get("model", "")).strip()
    effective_provider = str(args.reasoning_provider or configured_provider or profile_provider).strip().lower()
    effective_model = str(args.reasoning_model or configured_model).strip()

    if not effective_provider:
        effective_provider = "anthropic"

    if effective_provider == "openai-codex" and active_profile_provider == "openai-codex":
        effective_provider = "openai"
        if not effective_model or effective_model == DEFAULT_ANTHROPIC_MODEL:
            effective_model = DEFAULT_OPENAI_MODEL
        print("[warn] mapped runtime provider openai-codex -> openai for run compatibility")
    elif effective_provider not in RUNTIME_REASONING_PROVIDER_CHOICES:
        print(
            f"Unsupported runtime reasoning provider in launcher config: {effective_provider}",
            file=sys.stderr,
        )
        print(
            "Supported runtime providers: "
            + ", ".join(RUNTIME_REASONING_PROVIDER_CHOICES),
            file=sys.stderr,
        )
        print(
            f"Hint: run `{_launcher_hint()} config set provider openai` "
            "(or anthropic/openrouter).",
            file=sys.stderr,
        )
        return 1

    # If a linked OAuth profile exists and anthropic deps are not ready,
    # prefer OAuth-compatible OpenAI runtime unless user explicitly overrode.
    if (
        not args.reasoning_provider
        and not reasoning_override_locked
        and active_profile_provider == "openai-codex"
        and effective_provider == "anthropic"
    ):
        issue = _provider_runtime_dependency_issue(effective_provider, env)
        if issue in ("anthropic-package", "anthropic-key"):
            effective_provider = "openai"
            if not effective_model or effective_model == DEFAULT_ANTHROPIC_MODEL:
                effective_model = DEFAULT_OPENAI_MODEL
            print(
                "[warn] anthropic runtime dependencies are unavailable; "
                "falling back to linked OAuth OpenAI provider."
            )

    if not args.dry_run:
        issue = _provider_runtime_dependency_issue(effective_provider, env)
        if issue == "anthropic-package":
            print(
                "Reasoning provider is 'anthropic' but the 'anthropic' package is missing.",
                file=sys.stderr,
            )
            print("Install it: pip install anthropic  (or pip install -r requirements.txt)", file=sys.stderr)
            if active_profile_provider == "openai-codex":
                print(
                    f"Fallback: run `{_launcher_hint()} run --reasoning-provider openai` "
                    "to use the linked OAuth profile.",
                    file=sys.stderr,
                )
            return 1
        if issue == "anthropic-key":
            print(
                "Reasoning provider is 'anthropic' but ANTHROPIC_API_KEY is not set.",
                file=sys.stderr,
            )
            print(
                f"Set it, or run `{_launcher_hint()} onboard --provider anthropic --api-key \"$ANTHROPIC_API_KEY\"`.",
                file=sys.stderr,
            )
            if active_profile_provider == "openai-codex":
                print(
                    f"Fallback: run `{_launcher_hint()} run --reasoning-provider openai` "
                    "to use the linked OAuth profile.",
                    file=sys.stderr,
                )
            return 1
        if issue == "openai-key":
            print(
                "Reasoning provider is 'openai' but OPENAI_API_KEY is not set.",
                file=sys.stderr,
            )
            if active_profile_provider == "openai-codex":
                print(
                    "Linked OAuth profile exists but could not provide an OpenAI runtime token: "
                    f"{oauth_error}.",
                    file=sys.stderr,
                )
                print(
                    f"Remediation: run `{_launcher_hint()} auth login --provider openai-codex --source codex-cli`.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Set OPENAI_API_KEY, or run `{_launcher_hint()} onboard --provider openai --api-key \"$OPENAI_API_KEY\"`.",
                    file=sys.stderr,
                )
            return 1
        if issue == "openrouter-key":
            print(
                "Reasoning provider is 'openrouter' but OPENROUTER_API_KEY is not set.",
                file=sys.stderr,
            )
            print(
                f"Set OPENROUTER_API_KEY, or run `{_launcher_hint()} onboard --provider openrouter --api-key \"$OPENROUTER_API_KEY\"`.",
                file=sys.stderr,
            )
            return 1
        if issue == "unsupported-provider":
            print(
                f"Unsupported runtime reasoning provider: {effective_provider}",
                file=sys.stderr,
            )
            print(
                "Supported runtime providers: "
                + ", ".join(RUNTIME_REASONING_PROVIDER_CHOICES),
                file=sys.stderr,
            )
            return 1

    if args.track != "auto":
        env["GAIA_ACTIVE_TRACK_OVERRIDE"] = args.track
    if effective_provider:
        env["GAIA_REASONING_PROVIDER"] = effective_provider
    if effective_model:
        env["GAIA_REASONING_MODEL"] = effective_model
    env["GAIA_AGENT_MEMORY_DIR"] = str(state_dir)
    env["GAIA_ASSISTANT_VERBOSITY"] = str(profile_cfg.get("verbosity", "balanced")).strip() or "balanced"
    profile_tz = str(profile_cfg.get("timezone", "UTC")).strip()
    if profile_tz:
        env["TZ"] = profile_tz

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
    profile_name = str(profile_cfg.get("name", "")).strip()
    if profile_name:
        print(f"Profile name: {profile_name}")
    print(f"Profile verbosity: {env['GAIA_ASSISTANT_VERBOSITY']}")
    print(f"Profile timezone: {profile_tz or 'UTC'}")
    if loaded_from_secret:
        print(f"Loaded API credentials from secret store: {', '.join(loaded_from_secret)}")
    if loaded_from_oauth:
        print("Loaded OpenAI runtime token from linked OAuth profile.")

    if active_profile:
        print(
            "Auth profile: "
            f"{active_profile.get('provider', '?')}/{active_profile.get('profile_id', '?')} "
            f"({active_profile.get('source', '?')})"
        )

    result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    return build_modular_parser(globals())


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
