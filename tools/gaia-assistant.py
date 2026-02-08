#!/usr/bin/env python3
"""Standalone Gaia personal assistant launcher.

This wrapper makes it easier for users to run Gaia's dual-track evolution loop
as a standalone personal assistant runtime.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
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
ONBOARD_PROVIDER_CHOICES = ("openrouter", "openai", "anthropic", "openai-codex")
PROFILE_VERBOSITY_CHOICES = ("concise", "balanced", "detailed")
PROFILE_PROVIDER_CHOICES = ("openrouter", "openai", "anthropic", "openai-codex")
PERMISSION_LEVEL_CHOICES = ("safe", "confirm", "forbidden")
DEFAULT_SESSION_CONTEXT_TURNS = 20
DEFAULT_CAPABILITY_LEVELS = {
    "file_read": "safe",
    "file_write": "safe",
    "network_request": "safe",
    "shell_exec": "confirm",
    "delete_files": "confirm",
    "send_email": "forbidden",
    "external_messaging": "forbidden",
}
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
}


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
    "profile": {
        "name": "",
        "timezone": "UTC",
        "verbosity": "balanced",
        "default_provider": "anthropic",
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

    profile = cfg.setdefault("profile", {})
    profile.setdefault("name", "")
    profile.setdefault("timezone", "UTC")
    profile.setdefault("verbosity", "balanced")
    profile.setdefault("default_provider", "anthropic")

    verbosity = str(profile.get("verbosity", "")).strip().lower()
    if verbosity not in PROFILE_VERBOSITY_CHOICES:
        profile["verbosity"] = "balanced"

    default_provider = str(profile.get("default_provider", "")).strip().lower()
    if default_provider not in PROFILE_PROVIDER_CHOICES:
        profile["default_provider"] = "anthropic"

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


def _normalize_profile_value(key: str, value: str) -> Tuple[Optional[str], Optional[str]]:
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
    if canonical_key == "timezone":
        if not raw:
            return None, "timezone cannot be empty."
        return raw, None
    if canonical_key == "name":
        return raw, None
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


def _summaries_path(storage_dir: Path) -> Path:
    return storage_dir / "summaries.json"


def _plans_path(storage_dir: Path) -> Path:
    return storage_dir / "plans.json"


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


def _parse_since_date(raw: str) -> Optional[datetime]:
    value = raw.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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


def _mock_provider_response(provider: str, model: str, messages: List[Dict[str, str]]) -> str:
    prompt = _extract_last_user_text(messages)
    prompt_summary = _summarize_text(prompt, max_chars=140)
    return (
        f"[local-{provider}] {prompt_summary}\n"
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
) -> List[Dict[str, str]]:
    bounded = turns[-max_turns:] if max_turns > 0 else turns
    messages: List[Dict[str, str]] = []
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
        print(f"Resumed session: {target_session_id}")
    else:
        session = _create_session(provider=provider, model=model)
        _save_session(session_dir, session)
        print(f"Started session: {session['id']}")

    assert session is not None
    print(f"Provider: {provider} | Model: {model}")
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
                    metadata={"session_id": session["id"], "provider": provider, "model": model},
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
                metadata={"session_id": session["id"], "source": "chat"},
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
                metadata={"session_id": session["id"], "provider": provider, "model": model},
            )
            continue

        messages = _build_context_messages(session["turns"], user_input, max_turns=max_turns)
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

    normalized, error = _normalize_profile_value(key, str(args.value))
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


def cmd_traces(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config).expanduser()
    cfg = _ensure_config_exists(cfg_path)
    trace_dir = _resolve_trace_dir(cfg, args.trace_dir)
    traces = _read_action_traces(trace_dir)
    if args.type:
        wanted = str(args.type).strip()
        traces = [item for item in traces if str(item.get("action_type", "")).strip() == wanted]

    if args.last and args.last > 0:
        traces = traces[-args.last :]

    if not traces:
        print(f"No traces found in {trace_dir}")
        return 0

    for item in traces:
        ts = str(item.get("timestamp", "?")).strip()
        action_type = str(item.get("action_type", "?")).strip()
        level = str(item.get("permission_level", "?")).strip()
        status = str(item.get("status", "?")).strip()
        summary = _summarize_text(item.get("output_summary", ""), max_chars=100)
        print(f"{ts} | {action_type:<20} | {level:<9} | {status:<7} | {summary}")
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
    profile_cfg = cfg.get("profile", {})
    profile_cfg = profile_cfg if isinstance(profile_cfg, dict) else {}
    profile_provider = str(profile_cfg.get("default_provider", "")).strip()
    configured_provider = str(reasoning_cfg.get("provider", "")).strip()
    configured_model = str(reasoning_cfg.get("model", "")).strip()
    effective_provider = str(args.reasoning_provider or configured_provider or profile_provider).strip()
    effective_model = str(args.reasoning_model or configured_model).strip()

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

    config = sub.add_parser("config", help="Read or write local assistant preferences")
    config_sub = config.add_subparsers(dest="config_command", required=True)

    config_set = config_sub.add_parser("set", help="Set a preference value")
    config_set.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    config_set.add_argument("key", choices=sorted(PROFILE_KEY_MAP.keys()), help="Preference key")
    config_set.add_argument("value", help="Preference value")
    config_set.set_defaults(func=cmd_config_set)

    config_get = config_sub.add_parser("get", help="Get a preference value")
    config_get.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    config_get.add_argument("key", choices=sorted(PROFILE_KEY_MAP.keys()), help="Preference key")
    config_get.set_defaults(func=cmd_config_get)

    capability = sub.add_parser("capability", help="Inspect or override capability permissions")
    capability_sub = capability.add_subparsers(dest="capability_command", required=True)

    capability_list = capability_sub.add_parser("list", help="List effective capability levels")
    capability_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    capability_list.set_defaults(func=cmd_capability_list)

    capability_set = capability_sub.add_parser("set", help="Set local capability override")
    capability_set.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    capability_set.add_argument("capability", help="Capability name (for example: shell_exec)")
    capability_set.add_argument("level", choices=list(PERMISSION_LEVEL_CHOICES), help="Permission level")
    capability_set.set_defaults(func=cmd_capability_set)

    traces = sub.add_parser("traces", help="Show structured action traces")
    traces.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    traces.add_argument("--trace-dir", default=None, help="Trace directory override")
    traces.add_argument("--last", type=int, default=20, help="Number of recent trace entries to show")
    traces.add_argument("--type", default=None, help="Filter by action type")
    traces.set_defaults(func=cmd_traces)

    chat = sub.add_parser("chat", help="Start an interactive Gaia chat session")
    chat.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    chat.add_argument("--secret-store", default=None, help="Path to local secrets.json store (optional override)")
    chat.add_argument("--session-dir", default=None, help="Session directory override")
    chat.add_argument("--storage-dir", default=None, help="Data storage directory override")
    chat.add_argument("--trace-dir", default=None, help="Trace directory override")
    chat.add_argument("--resume", default=None, help="Session id or 'last'")
    chat.add_argument("--max-context-turns", type=int, default=None, help="Override max context turns")
    chat.set_defaults(func=cmd_chat)

    note = sub.add_parser("note", help="Capture a note or task")
    note.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    note.add_argument("--storage-dir", default=None, help="Data storage directory override")
    note.add_argument("--trace-dir", default=None, help="Trace directory override")
    note.add_argument("--task", action="store_true", help="Store as task instead of note")
    note.add_argument("text", help="Note/task text")
    note.set_defaults(func=cmd_note)

    tasks = sub.add_parser("tasks", help="List saved tasks")
    tasks.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    tasks.add_argument("--storage-dir", default=None, help="Data storage directory override")
    tasks.add_argument("--trace-dir", default=None, help="Trace directory override")
    tasks.add_argument("--q", default=None, help="Filter tasks by keyword")
    tasks.add_argument("--since", default=None, help="Filter tasks created since YYYY-MM-DD")
    tasks.add_argument("--status", choices=["open", "done", "all"], default="open", help="Filter by task status")
    tasks.set_defaults(func=cmd_tasks)

    summarize = sub.add_parser("summarize", help="Fetch and summarize one or more URLs")
    summarize.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    summarize.add_argument("--storage-dir", default=None, help="Data storage directory override")
    summarize.add_argument("--trace-dir", default=None, help="Trace directory override")
    summarize.add_argument("urls", nargs="+", help="One or more URLs to summarize")
    summarize.set_defaults(func=cmd_summarize)

    summaries = sub.add_parser("summaries", help="List saved URL summaries")
    summaries.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    summaries.add_argument("--storage-dir", default=None, help="Data storage directory override")
    summaries.add_argument("--trace-dir", default=None, help="Trace directory override")
    summaries.add_argument("--last", type=int, default=20, help="Number of entries to show")
    summaries.set_defaults(func=cmd_summaries)

    plan = sub.add_parser("plan", help="Generate or refine an actionable plan from a goal")
    plan.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    plan.add_argument("--storage-dir", default=None, help="Data storage directory override")
    plan.add_argument("--trace-dir", default=None, help="Trace directory override")
    plan.add_argument("--edit", default=None, help="Existing plan id to refine")
    plan.add_argument("--update", default=None, help="Refinement instructions for --edit")
    plan.add_argument("goal", nargs="?", help="Goal description")
    plan.set_defaults(func=cmd_plan)

    plans = sub.add_parser("plans", help="List saved plans")
    plans.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    plans.add_argument("--storage-dir", default=None, help="Data storage directory override")
    plans.add_argument("--trace-dir", default=None, help="Trace directory override")
    plans.add_argument("--last", type=int, default=20, help="Number of entries to show")
    plans.set_defaults(func=cmd_plans)

    autopilot = sub.add_parser("autopilot", help="Run scoped autopilot profiles")
    autopilot_sub = autopilot.add_subparsers(dest="autopilot_command", required=True)

    autopilot_run = autopilot_sub.add_parser("run", help="Run an approved autopilot profile")
    autopilot_run.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    autopilot_run.add_argument("--storage-dir", default=None, help="Data storage directory override")
    autopilot_run.add_argument("--trace-dir", default=None, help="Trace directory override")
    autopilot_run.add_argument(
        "--profile",
        choices=sorted(AUTOPILOT_PROFILES.keys()),
        required=True,
        help="Approved autopilot profile name",
    )
    autopilot_run.add_argument("--dry-run", action="store_true", help="Preview steps without executing")
    autopilot_run.add_argument(
        "--force-failure-step",
        default=None,
        help="Force failure at a step id for rollback validation",
    )
    autopilot_run.set_defaults(func=cmd_autopilot_run)

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
