#!/usr/bin/env python3
"""Gaia Minds Self-Evolving Agent -- Main Loop.

This is the reasoning core of an autonomous agent that:
1. Gathers state from the repository and GitHub
2. Asks the configured reasoning provider what to do
3. Checks alignment of proposed actions
4. Executes approved actions
5. Writes memory (decisions, lessons, state)
6. Evolves by learning from outcomes

All reasoning traces are logged to tools/agent-memory/ for transparency.

Run locally:
    python3 tools/agent-loop.py                    # single cycle
    python3 tools/agent-loop.py --mode continuous   # loop with interval
    python3 tools/agent-loop.py --dry-run           # plan but don't execute
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Resolve paths and add tools/ to sys.path for sibling imports
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

# Sibling modules -- imported after path setup
from agent_alignment import (  # noqa: E402
    AlignmentResult,
    check_alignment,
    load_constitution,
)
from agent_actions import (  # noqa: E402
    ActionResult,
    RepoState,
    execute_action,
    gather_state,
)

# ---------------------------------------------------------------------------
# Optional: Anthropic SDK
# ---------------------------------------------------------------------------

try:
    import anthropic

    _HAS_ANTHROPIC = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _HAS_ANTHROPIC = False

# Optional: PyYAML
try:
    import yaml

    _HAS_YAML = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    _HAS_YAML = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

log = logging.getLogger("gaia-agent")

# Defaults for dual-track evolution behavior.
DEFAULT_TRACKS: Dict[str, Dict[str, Any]] = {
    "assistant": {
        "weight": 7,
        "description": "Improve user-facing personal assistant behavior and reliability",
        "allowed_actions": [
            "verify_resources",
            "generate_indexes",
            "add_research",
            "add_resource",
            "update_skill",
            "open_issue",
            "comment_on_pr",
            "check_pr_status",
        ],
    },
    "framework": {
        "weight": 3,
        "description": "Improve Gaia self-evolving framework and governance tooling",
        "allowed_actions": [
            "verify_resources",
            "generate_indexes",
            "create_tool",
            "update_skill",
            "open_issue",
            "comment_on_pr",
            "check_pr_status",
        ],
    },
}

DEFAULT_BUDGET_POLICY: Dict[str, Any] = {
    "user_service_pct": 80,
    "self_improvement_pct": 20,
    "hard_cycle_token_cap": 12000,
    "hard_window_token_cap": 60000,
    "window": "daily_utc",
    "warning_threshold_pct": 80,
    "breach_action": "block",
    "estimated_tokens_per_action": 400,
}
SUPPORTED_BUDGET_WINDOWS = {"hourly_utc", "daily_utc", "weekly_utc"}
SUPPORTED_BREACH_ACTIONS = {"warn", "defer", "block"}

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"
SUPPORTED_REASONING_PROVIDERS = {"anthropic", "openai", "openrouter"}
DEFAULT_REASONING_FAILOVER_ORDER = ("openai", "openrouter", "anthropic")
DEFAULT_REASONING_FAILOVER_ERROR_CLASSES = ("quota", "auth")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = SCRIPT_DIR / "agent-config.yml"
MEMORY_DIR = Path(
    os.environ.get("GAIA_AGENT_MEMORY_DIR", str(SCRIPT_DIR / "agent-memory"))
).expanduser()
DECISIONS_PATH = MEMORY_DIR / "decisions.jsonl"
LESSONS_PATH = MEMORY_DIR / "lessons.jsonl"
STATE_PATH = MEMORY_DIR / "state.json"
BUDGET_DECISIONS_PATH = MEMORY_DIR / "budget-decisions.jsonl"


def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Load agent-config.yml."""
    text = path.read_text(encoding="utf-8")
    if _HAS_YAML:
        return yaml.safe_load(text)
    # Minimal fallback -- parse enough to run
    import re

    config: Dict[str, Any] = {}
    # Extract key top-level scalars
    for match in re.finditer(r"^  (\w+):\s*\"?([^\"#\n]+)\"?", text, re.MULTILINE):
        key, val = match.group(1).strip(), match.group(2).strip()
        config[key] = val
    return config


def _resolve_reasoning_provider(config: Dict[str, Any]) -> str:
    """Resolve reasoning provider from env override or config."""
    override = os.environ.get("GAIA_REASONING_PROVIDER", "").strip().lower()
    if override:
        if override in SUPPORTED_REASONING_PROVIDERS:
            return override
        log.warning(
            "Unsupported GAIA_REASONING_PROVIDER=%s; falling back to config/default",
            override,
        )

    reasoning_cfg = config.get("reasoning", {})
    if not isinstance(reasoning_cfg, dict):
        reasoning_cfg = {}
    configured = str(reasoning_cfg.get("provider", "anthropic")).strip().lower()
    if configured in SUPPORTED_REASONING_PROVIDERS:
        return configured
    return "anthropic"


def _resolve_reasoning_model(config: Dict[str, Any], provider: str) -> str:
    """Resolve reasoning model from env overrides and config."""
    direct_override = os.environ.get("GAIA_REASONING_MODEL", "").strip()
    if direct_override:
        return direct_override

    reasoning = config.get("reasoning", {})
    reasoning = reasoning if isinstance(reasoning, dict) else {}
    models_cfg = reasoning.get("models", {})
    models_cfg = models_cfg if isinstance(models_cfg, dict) else {}

    if provider == "openai":
        env_model = os.environ.get("OPENAI_MODEL", "").strip()
        if env_model:
            return env_model

        configured_openai_model = str(models_cfg.get("openai", "")).strip()
        if configured_openai_model:
            return configured_openai_model

        openai_cfg = reasoning.get("openai", {})
        if isinstance(openai_cfg, dict):
            openai_model = str(openai_cfg.get("model", "")).strip()
            if openai_model:
                return openai_model

        legacy_model = str(reasoning.get("model", "")).strip()
        if legacy_model and legacy_model != DEFAULT_ANTHROPIC_MODEL:
            return legacy_model

        return DEFAULT_OPENAI_MODEL

    if provider == "openrouter":
        env_model = os.environ.get("OPENROUTER_MODEL", "").strip()
        if env_model:
            return env_model

        configured_openrouter_model = str(models_cfg.get("openrouter", "")).strip()
        if configured_openrouter_model:
            return configured_openrouter_model

        openrouter_cfg = reasoning.get("openrouter", {})
        if isinstance(openrouter_cfg, dict):
            openrouter_model = str(openrouter_cfg.get("model", "")).strip()
            if openrouter_model:
                return openrouter_model

        legacy_model = str(reasoning.get("model", "")).strip()
        if legacy_model and legacy_model != DEFAULT_ANTHROPIC_MODEL:
            return legacy_model

        return DEFAULT_OPENROUTER_MODEL

    env_model = os.environ.get("ANTHROPIC_MODEL", "").strip()
    if env_model:
        return env_model

    configured_anthropic_model = str(models_cfg.get("anthropic", "")).strip()
    if configured_anthropic_model:
        return configured_anthropic_model

    legacy_model = str(reasoning.get("model", "")).strip()
    return legacy_model or DEFAULT_ANTHROPIC_MODEL


def _resolve_openai_runtime(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve OpenAI runtime settings from config and env."""
    reasoning = config.get("reasoning", {})
    reasoning = reasoning if isinstance(reasoning, dict) else {}
    openai_cfg = reasoning.get("openai", {})
    openai_cfg = openai_cfg if isinstance(openai_cfg, dict) else {}

    base_url = str(
        os.environ.get(
            "OPENAI_BASE_URL",
            openai_cfg.get("base_url", "https://api.openai.com/v1"),
        )
    ).strip()
    if not base_url:
        base_url = "https://api.openai.com/v1"
    base_url = base_url.rstrip("/")

    timeout_raw = os.environ.get(
        "OPENAI_TIMEOUT_SECONDS",
        str(openai_cfg.get("timeout_seconds", 120)),
    )
    try:
        timeout_seconds = int(str(timeout_raw).strip())
    except ValueError:
        timeout_seconds = 120
    if timeout_seconds < 1:
        timeout_seconds = 120

    return {
        "api_key": os.environ.get("OPENAI_API_KEY", "").strip(),
        "base_url": base_url,
        "timeout_seconds": timeout_seconds,
    }


def _resolve_openrouter_runtime(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve OpenRouter runtime settings from config and env."""
    reasoning = config.get("reasoning", {})
    reasoning = reasoning if isinstance(reasoning, dict) else {}
    openrouter_cfg = reasoning.get("openrouter", {})
    openrouter_cfg = openrouter_cfg if isinstance(openrouter_cfg, dict) else {}

    base_url = str(
        os.environ.get(
            "OPENROUTER_BASE_URL",
            openrouter_cfg.get("base_url", "https://openrouter.ai/api/v1"),
        )
    ).strip()
    if not base_url:
        base_url = "https://openrouter.ai/api/v1"
    base_url = base_url.rstrip("/")

    app_name = str(
        os.environ.get(
            "OPENROUTER_APP_NAME",
            openrouter_cfg.get("app_name", "gaia-minds-agent"),
        )
    ).strip()
    if not app_name:
        app_name = "gaia-minds-agent"

    app_url = str(
        os.environ.get(
            "OPENROUTER_APP_URL",
            openrouter_cfg.get("app_url", "https://github.com/Gaia-minds/gaia-minds"),
        )
    ).strip()
    if not app_url:
        app_url = "https://github.com/Gaia-minds/gaia-minds"

    timeout_raw = os.environ.get(
        "OPENROUTER_TIMEOUT_SECONDS",
        str(openrouter_cfg.get("timeout_seconds", 120)),
    )
    try:
        timeout_seconds = int(str(timeout_raw).strip())
    except ValueError:
        timeout_seconds = 120
    if timeout_seconds < 1:
        timeout_seconds = 120

    return {
        "api_key": os.environ.get("OPENROUTER_API_KEY", "").strip(),
        "base_url": base_url,
        "app_name": app_name,
        "app_url": app_url,
        "timeout_seconds": timeout_seconds,
    }


def _parse_bool_default(value: Any, default_value: bool) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "on", "enabled"}:
        return True
    if token in {"0", "false", "no", "off", "disabled"}:
        return False
    return default_value


def _resolve_reasoning_failover_policy(config: Dict[str, Any], primary_provider: str) -> Dict[str, Any]:
    reasoning = config.get("reasoning", {})
    reasoning = reasoning if isinstance(reasoning, dict) else {}
    failover_cfg = reasoning.get("failover", {})
    failover_cfg = failover_cfg if isinstance(failover_cfg, dict) else {}

    enabled_default = _parse_bool_default(failover_cfg.get("enabled", True), True)
    enabled = _parse_bool_default(os.environ.get("GAIA_REASONING_FAILOVER_ENABLED", ""), enabled_default)

    classes_override = os.environ.get("GAIA_REASONING_FAILOVER_HARD_ERRORS", "").strip()
    classes_raw: Any = classes_override if classes_override else failover_cfg.get(
        "hard_error_classes",
        list(DEFAULT_REASONING_FAILOVER_ERROR_CLASSES),
    )
    if isinstance(classes_raw, str):
        class_tokens = [token.strip().lower() for token in classes_raw.split(",")]
    elif isinstance(classes_raw, list):
        class_tokens = [str(token).strip().lower() for token in classes_raw]
    else:
        class_tokens = list(DEFAULT_REASONING_FAILOVER_ERROR_CLASSES)
    hard_error_classes: List[str] = []
    for token in class_tokens:
        if token in DEFAULT_REASONING_FAILOVER_ERROR_CLASSES and token not in hard_error_classes:
            hard_error_classes.append(token)
    if not hard_error_classes:
        hard_error_classes = list(DEFAULT_REASONING_FAILOVER_ERROR_CLASSES)

    order_override = os.environ.get("GAIA_REASONING_FAILOVER_ORDER", "").strip()
    order_raw: Any = order_override if order_override else failover_cfg.get("order", list(DEFAULT_REASONING_FAILOVER_ORDER))
    if isinstance(order_raw, str):
        order_tokens = [token.strip().lower() for token in order_raw.split(",")]
    elif isinstance(order_raw, list):
        order_tokens = [str(token).strip().lower() for token in order_raw]
    else:
        order_tokens = list(DEFAULT_REASONING_FAILOVER_ORDER)
    order: List[str] = []
    for token in order_tokens:
        if token in SUPPORTED_REASONING_PROVIDERS and token != primary_provider and token not in order:
            order.append(token)

    models_raw = failover_cfg.get("models", {})
    models_raw = models_raw if isinstance(models_raw, dict) else {}
    models: Dict[str, str] = {}
    for provider in SUPPORTED_REASONING_PROVIDERS:
        value = str(models_raw.get(provider, "")).strip()
        if value:
            models[provider] = value
    models_override = os.environ.get("GAIA_REASONING_FAILOVER_MODELS", "").strip()
    if models_override:
        for token in models_override.split(","):
            item = token.strip()
            if not item or "=" not in item:
                continue
            provider, model = item.split("=", 1)
            provider = provider.strip().lower()
            model = model.strip()
            if provider in SUPPORTED_REASONING_PROVIDERS and model:
                models[provider] = model

    return {
        "enabled": enabled,
        "hard_error_classes": hard_error_classes,
        "order": order,
        "models": models,
    }


def _classify_reasoning_error(error_text: str) -> str:
    normalized = str(error_text).strip().lower()
    if not normalized:
        return "other"
    quota_markers = (
        "insufficient_quota",
        "rate limit",
        "quota",
        "billing",
        "http 429",
    )
    if any(marker in normalized for marker in quota_markers):
        return "quota"
    auth_markers = (
        "http 401",
        "http 403",
        "unauthorized",
        "forbidden",
        "authentication",
        "invalid api key",
        "api key is not set",
        "permission denied",
    )
    if any(marker in normalized for marker in auth_markers):
        return "auth"
    return "other"


def _initialize_reasoning_client(
    config: Dict[str, Any],
    provider: str,
    *,
    model_override: str = "",
) -> Tuple[Any, str, str]:
    model = model_override.strip() or _resolve_reasoning_model(config, provider)
    if provider == "anthropic":
        if not _HAS_ANTHROPIC:
            return None, model, "anthropic-package"
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return None, model, "anthropic-key"
        return anthropic.Anthropic(api_key=api_key), model, ""
    if provider == "openai":
        runtime = _resolve_openai_runtime(config)
        if not runtime.get("api_key"):
            return None, model, "openai-key"
        return runtime, model, ""
    if provider == "openrouter":
        runtime = _resolve_openrouter_runtime(config)
        if not runtime.get("api_key"):
            return None, model, "openrouter-key"
        return runtime, model, ""
    return None, model, "unsupported-provider"


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


def load_memory(
    n_decisions: int = 10,
    n_lessons: int = 10,
    n_budget_decisions: int = 10,
) -> Dict[str, Any]:
    """Load recent decisions, lessons, and state from agent-memory/."""
    memory: Dict[str, Any] = {
        "recent_decisions": [],
        "recent_budget_decisions": [],
        "lessons": [],
        "state": {},
    }

    # Decisions (last N lines)
    if DECISIONS_PATH.exists():
        lines = DECISIONS_PATH.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-n_decisions:]:
            line = line.strip()
            if line:
                try:
                    memory["recent_decisions"].append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # Lessons (last N lines)
    if LESSONS_PATH.exists():
        lines = LESSONS_PATH.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-n_lessons:]:
            line = line.strip()
            if line:
                try:
                    memory["lessons"].append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # Budget decisions (last N lines)
    if BUDGET_DECISIONS_PATH.exists():
        lines = BUDGET_DECISIONS_PATH.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-n_budget_decisions:]:
            line = line.strip()
            if line:
                try:
                    memory["recent_budget_decisions"].append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # State
    if STATE_PATH.exists():
        try:
            memory["state"] = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return memory


def log_decision(
    cycle: int,
    action: Dict[str, Any],
    alignment: AlignmentResult,
    outcome: str,
    details: str = "",
    active_track: str = "unknown",
) -> None:
    """Append a decision record to decisions.jsonl."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": cycle,
        "track": active_track,
        "action": action.get("type", "unknown"),
        "action_params": action.get("params", {}),
        "reasoning": alignment.reasoning[:500],
        "alignment_check": "allowed" if alignment.allowed else "denied",
        "risk_level": alignment.risk_level,
        "outcome": outcome,
        "details": details[:500],
    }
    with open(DECISIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_budget_decision(cycle: int, payload: Dict[str, Any]) -> None:
    """Append a structured budget-decision record to budget-decisions.jsonl."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": cycle,
    }
    record.update(payload)
    with open(BUDGET_DECISIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_lesson(cycle: int, lesson: str, source: str, context: str = "") -> None:
    """Append a lesson to lessons.jsonl."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": cycle,
        "lesson": lesson,
        "source": source,
        "context": context[:300],
    }
    with open(LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def update_state(
    cycle: int,
    results: List[ActionResult],
    active_track: str = "unknown",
    budget_policy: Optional[Dict[str, Any]] = None,
    budget_runtime: Optional[Dict[str, Any]] = None,
    budget_decision: Optional[Dict[str, Any]] = None,
) -> None:
    """Update state.json with cycle results."""
    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    state["last_cycle"] = cycle
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["last_track"] = active_track
    state["total_actions"] = state.get("total_actions", 0) + len(results)
    track_counts = state.get("track_counts", {})
    track_counts[active_track] = track_counts.get(active_track, 0) + 1
    state["track_counts"] = track_counts
    if budget_policy:
        state["budget_policy"] = budget_policy
    if budget_runtime:
        state["budget_runtime"] = budget_runtime
    if budget_decision:
        state["last_budget_decision"] = budget_decision

    for r in results:
        if r.artifacts.get("pr_url"):
            state["total_prs_created"] = state.get("total_prs_created", 0) + 1

    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def commit_memory(cycle: int) -> None:
    """Commit memory changes to git."""
    import subprocess

    try:
        subprocess.run(
            ["git", "add", str(MEMORY_DIR)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=30,
        )
        # Check if there are staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet", str(MEMORY_DIR)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:  # there are changes
            subprocess.run(
                ["git", "commit", "-m", f"agent: memory update cycle {cycle}"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                timeout=30,
            )
            log.info("Memory committed to git (cycle %d)", cycle)
        else:
            log.debug("No memory changes to commit")
    except Exception as exc:
        log.warning("Could not commit memory: %s", exc)


def rotate_logs(config: Dict[str, Any]) -> None:
    """Rotate decision and lesson logs if they exceed configured limits."""
    max_decisions = config.get("memory", {}).get("max_decisions_log_entries", 500)
    max_budget_decisions = config.get("memory", {}).get("max_budget_decision_entries", 500)
    max_lessons = config.get("memory", {}).get("max_lessons_entries", 100)

    for path, limit in [
        (DECISIONS_PATH, max_decisions),
        (BUDGET_DECISIONS_PATH, max_budget_decisions),
        (LESSONS_PATH, max_lessons),
    ]:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > limit:
            # Keep the most recent entries
            path.write_text("\n".join(lines[-limit:]) + "\n", encoding="utf-8")
            log.info("Rotated %s: kept last %d of %d entries", path.name, limit, len(lines))


def normalized_track_config(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return normalized track configuration with safe defaults."""
    tracks_cfg = config.get("evolution", {}).get("tracks", {})
    out: Dict[str, Dict[str, Any]] = {}
    for name, defaults in DEFAULT_TRACKS.items():
        configured = tracks_cfg.get(name, {})
        weight = configured.get("weight", defaults["weight"])
        try:
            weight_int = int(weight)
        except (TypeError, ValueError):
            weight_int = int(defaults["weight"])
        if weight_int < 1:
            weight_int = 1
        allowed_actions = configured.get("allowed_actions", defaults["allowed_actions"])
        if not isinstance(allowed_actions, list):
            allowed_actions = defaults["allowed_actions"]
        out[name] = {
            "weight": weight_int,
            "description": configured.get("description", defaults["description"]),
            "allowed_actions": allowed_actions,
        }
    return out


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _non_negative_int(value: Any, default: int = 0) -> int:
    parsed = _parse_int(value, default)
    return parsed if parsed >= 0 else default


def validate_budget_policy_config(config: Dict[str, Any]) -> List[str]:
    """Validate budget contract fields and return blocking startup errors."""
    budget_cfg = config.get("budget", {})
    if budget_cfg is None:
        budget_cfg = {}
    if not isinstance(budget_cfg, dict):
        return ["budget must be a mapping in tools/agent-config.yml"]

    errors: List[str] = []

    def read_int(
        field: str,
        *,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
    ) -> Optional[int]:
        if field not in budget_cfg:
            return None
        raw = budget_cfg.get(field)
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            errors.append(f"budget.{field} must be an integer")
            return None
        if min_value is not None and parsed < min_value:
            errors.append(f"budget.{field} must be >= {min_value}")
        if max_value is not None and parsed > max_value:
            errors.append(f"budget.{field} must be <= {max_value}")
        return parsed

    user_pct = read_int("user_service_pct", min_value=0)
    self_pct = read_int("self_improvement_pct", min_value=0)
    if user_pct is not None and self_pct is not None and (user_pct + self_pct) <= 0:
        errors.append("budget.user_service_pct + budget.self_improvement_pct must be > 0")

    hard_cycle = read_int("hard_cycle_token_cap", min_value=1)
    hard_window = read_int("hard_window_token_cap", min_value=1)
    if hard_cycle is not None and hard_window is not None and hard_window < hard_cycle:
        errors.append("budget.hard_window_token_cap must be >= budget.hard_cycle_token_cap")

    read_int("warning_threshold_pct", min_value=1, max_value=100)
    read_int("estimated_tokens_per_action", min_value=0)

    window = budget_cfg.get("window")
    if window is not None:
        window_value = str(window).strip().lower()
        if window_value not in SUPPORTED_BUDGET_WINDOWS:
            allowed = ", ".join(sorted(SUPPORTED_BUDGET_WINDOWS))
            errors.append(f"budget.window must be one of: {allowed}")

    breach_action = budget_cfg.get("breach_action")
    if breach_action is not None:
        breach_value = str(breach_action).strip().lower()
        if breach_value not in SUPPORTED_BREACH_ACTIONS:
            allowed = ", ".join(sorted(SUPPORTED_BREACH_ACTIONS))
            errors.append(f"budget.breach_action must be one of: {allowed}")

    cycle_cap_limit = (
        hard_cycle
        if hard_cycle is not None
        else int(DEFAULT_BUDGET_POLICY["hard_cycle_token_cap"])
    )
    window_cap_limit = (
        hard_window
        if hard_window is not None
        else int(DEFAULT_BUDGET_POLICY["hard_window_token_cap"])
    )

    for key, cap_limit in (
        ("track_cycle_token_cap", cycle_cap_limit),
        ("track_window_token_cap", window_cap_limit),
    ):
        caps = budget_cfg.get(key)
        if caps is None:
            continue
        if not isinstance(caps, dict):
            errors.append(f"budget.{key} must be a mapping with assistant/framework keys")
            continue
        for track in ("assistant", "framework"):
            if track not in caps:
                errors.append(f"budget.{key}.{track} is required when budget.{key} is set")
                continue
            try:
                track_cap = int(caps[track])
            except (TypeError, ValueError):
                errors.append(f"budget.{key}.{track} must be an integer")
                continue
            if track_cap < 1:
                errors.append(f"budget.{key}.{track} must be >= 1")
            if track_cap > cap_limit:
                errors.append(
                    f"budget.{key}.{track} must be <= budget."
                    f"{'hard_cycle_token_cap' if key == 'track_cycle_token_cap' else 'hard_window_token_cap'}"
                )

    return errors


def normalized_budget_policy(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return normalized budget policy with explicit global + track caps."""
    budget_cfg = config.get("budget", {})
    budget_cfg = budget_cfg if isinstance(budget_cfg, dict) else {}

    user_pct = _parse_int(
        budget_cfg.get("user_service_pct", DEFAULT_BUDGET_POLICY["user_service_pct"]),
        int(DEFAULT_BUDGET_POLICY["user_service_pct"]),
    )
    self_pct = _parse_int(
        budget_cfg.get(
            "self_improvement_pct",
            DEFAULT_BUDGET_POLICY["self_improvement_pct"],
        ),
        int(DEFAULT_BUDGET_POLICY["self_improvement_pct"]),
    )
    if user_pct < 0:
        user_pct = int(DEFAULT_BUDGET_POLICY["user_service_pct"])
    if self_pct < 0:
        self_pct = int(DEFAULT_BUDGET_POLICY["self_improvement_pct"])
    split_total = user_pct + self_pct
    if split_total <= 0:
        user_pct = int(DEFAULT_BUDGET_POLICY["user_service_pct"])
        self_pct = int(DEFAULT_BUDGET_POLICY["self_improvement_pct"])
        split_total = user_pct + self_pct

    hard_cycle = _parse_int(
        budget_cfg.get("hard_cycle_token_cap", DEFAULT_BUDGET_POLICY["hard_cycle_token_cap"]),
        int(DEFAULT_BUDGET_POLICY["hard_cycle_token_cap"]),
    )
    if hard_cycle < 1:
        hard_cycle = int(DEFAULT_BUDGET_POLICY["hard_cycle_token_cap"])

    hard_window = _parse_int(
        budget_cfg.get("hard_window_token_cap", DEFAULT_BUDGET_POLICY["hard_window_token_cap"]),
        int(DEFAULT_BUDGET_POLICY["hard_window_token_cap"]),
    )
    if hard_window < hard_cycle:
        hard_window = max(hard_cycle, int(DEFAULT_BUDGET_POLICY["hard_window_token_cap"]))

    warning_threshold_pct = _parse_int(
        budget_cfg.get("warning_threshold_pct", DEFAULT_BUDGET_POLICY["warning_threshold_pct"]),
        int(DEFAULT_BUDGET_POLICY["warning_threshold_pct"]),
    )
    if warning_threshold_pct < 1 or warning_threshold_pct > 100:
        warning_threshold_pct = int(DEFAULT_BUDGET_POLICY["warning_threshold_pct"])

    estimated_tokens_per_action = _parse_int(
        budget_cfg.get(
            "estimated_tokens_per_action",
            DEFAULT_BUDGET_POLICY["estimated_tokens_per_action"],
        ),
        int(DEFAULT_BUDGET_POLICY["estimated_tokens_per_action"]),
    )
    if estimated_tokens_per_action < 0:
        estimated_tokens_per_action = int(DEFAULT_BUDGET_POLICY["estimated_tokens_per_action"])

    window = str(budget_cfg.get("window", DEFAULT_BUDGET_POLICY["window"])).strip().lower()
    if window not in SUPPORTED_BUDGET_WINDOWS:
        window = str(DEFAULT_BUDGET_POLICY["window"])

    breach_action = str(
        budget_cfg.get("breach_action", DEFAULT_BUDGET_POLICY["breach_action"])
    ).strip().lower()
    if breach_action not in SUPPORTED_BREACH_ACTIONS:
        breach_action = str(DEFAULT_BUDGET_POLICY["breach_action"])

    assistant_ratio = user_pct / split_total
    framework_ratio = self_pct / split_total
    assistant_cycle_default = max(1, int(round(hard_cycle * assistant_ratio)))
    framework_cycle_default = max(1, hard_cycle - assistant_cycle_default)
    assistant_window_default = max(1, int(round(hard_window * assistant_ratio)))
    framework_window_default = max(1, hard_window - assistant_window_default)

    cycle_overrides = budget_cfg.get("track_cycle_token_cap", {})
    cycle_overrides = cycle_overrides if isinstance(cycle_overrides, dict) else {}
    window_overrides = budget_cfg.get("track_window_token_cap", {})
    window_overrides = window_overrides if isinstance(window_overrides, dict) else {}

    track_cycle_caps = {
        "assistant": min(
            hard_cycle,
            max(1, _parse_int(cycle_overrides.get("assistant"), assistant_cycle_default)),
        ),
        "framework": min(
            hard_cycle,
            max(1, _parse_int(cycle_overrides.get("framework"), framework_cycle_default)),
        ),
    }
    track_window_caps = {
        "assistant": min(
            hard_window,
            max(1, _parse_int(window_overrides.get("assistant"), assistant_window_default)),
        ),
        "framework": min(
            hard_window,
            max(1, _parse_int(window_overrides.get("framework"), framework_window_default)),
        ),
    }

    return {
        "user_service_pct": user_pct,
        "self_improvement_pct": self_pct,
        "hard_cycle_token_cap": hard_cycle,
        "hard_window_token_cap": hard_window,
        "window": window,
        "warning_threshold_pct": warning_threshold_pct,
        "breach_action": breach_action,
        "estimated_tokens_per_action": estimated_tokens_per_action,
        "track_cycle_token_cap": track_cycle_caps,
        "track_window_token_cap": track_window_caps,
    }


def _budget_window_key(now: datetime, window: str) -> str:
    if window == "hourly_utc":
        return now.strftime("%Y-%m-%dT%H")
    if window == "weekly_utc":
        year, week, _ = now.isocalendar()
        return f"{year}-W{week:02d}"
    return now.strftime("%Y-%m-%d")


def _normalize_budget_runtime(
    state: Dict[str, Any],
    budget_policy: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    runtime = state.get("budget_runtime", {})
    runtime = runtime if isinstance(runtime, dict) else {}
    window = str(budget_policy.get("window", "daily_utc"))
    window_key = _budget_window_key(now, window)

    totals = runtime.get("totals", {})
    totals = totals if isinstance(totals, dict) else {}
    normalized_totals = {
        "overall": _non_negative_int(totals.get("overall", 0), 0),
        "assistant": _non_negative_int(totals.get("assistant", 0), 0),
        "framework": _non_negative_int(totals.get("framework", 0), 0),
    }

    same_window = (
        str(runtime.get("window", "")).strip() == window
        and str(runtime.get("window_key", "")).strip() == window_key
    )

    if not same_window:
        normalized_totals = {"overall": 0, "assistant": 0, "framework": 0}

    window_started_at = str(runtime.get("window_started_at", "")).strip()
    if not same_window or not window_started_at:
        window_started_at = now.isoformat()

    return {
        "window": window,
        "window_key": window_key,
        "window_started_at": window_started_at,
        "totals": normalized_totals,
    }


def estimate_cycle_tokens(
    config: Dict[str, Any],
    budget_policy: Dict[str, Any],
    actions: List[Dict[str, Any]],
) -> int:
    """Estimate token usage for this cycle deterministically."""
    if not actions:
        return 0

    reasoning_cfg = config.get("reasoning", {})
    reasoning_cfg = reasoning_cfg if isinstance(reasoning_cfg, dict) else {}
    max_tokens = _parse_int(reasoning_cfg.get("max_tokens", 4096), 4096)
    if max_tokens < 1:
        max_tokens = 4096

    per_action = _parse_int(
        budget_policy.get("estimated_tokens_per_action", 0),
        int(DEFAULT_BUDGET_POLICY["estimated_tokens_per_action"]),
    )
    if per_action < 0:
        per_action = int(DEFAULT_BUDGET_POLICY["estimated_tokens_per_action"])

    return max_tokens + (len(actions) * per_action)


def evaluate_budget_decision(
    *,
    budget_policy: Dict[str, Any],
    state: Dict[str, Any],
    active_track: str,
    estimated_cycle_tokens: int,
    now: Optional[datetime] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Evaluate deterministic budget decision before action execution."""
    now_utc = now if now is not None else datetime.now(timezone.utc)
    runtime = _normalize_budget_runtime(state, budget_policy, now_utc)
    totals = runtime["totals"]

    track = active_track if active_track in {"assistant", "framework"} else "assistant"
    estimated = max(0, _parse_int(estimated_cycle_tokens, 0))
    warning_threshold_pct = _parse_int(
        budget_policy.get("warning_threshold_pct", DEFAULT_BUDGET_POLICY["warning_threshold_pct"]),
        int(DEFAULT_BUDGET_POLICY["warning_threshold_pct"]),
    )
    if warning_threshold_pct < 1 or warning_threshold_pct > 100:
        warning_threshold_pct = int(DEFAULT_BUDGET_POLICY["warning_threshold_pct"])

    cycle_caps = budget_policy.get("track_cycle_token_cap", {})
    cycle_caps = cycle_caps if isinstance(cycle_caps, dict) else {}
    window_caps = budget_policy.get("track_window_token_cap", {})
    window_caps = window_caps if isinstance(window_caps, dict) else {}

    limits = {
        "cycle": {
            "overall": _parse_int(
                budget_policy.get("hard_cycle_token_cap", DEFAULT_BUDGET_POLICY["hard_cycle_token_cap"]),
                int(DEFAULT_BUDGET_POLICY["hard_cycle_token_cap"]),
            ),
            "assistant": _parse_int(cycle_caps.get("assistant", 0), 0),
            "framework": _parse_int(cycle_caps.get("framework", 0), 0),
        },
        "window": {
            "overall": _parse_int(
                budget_policy.get(
                    "hard_window_token_cap",
                    DEFAULT_BUDGET_POLICY["hard_window_token_cap"],
                ),
                int(DEFAULT_BUDGET_POLICY["hard_window_token_cap"]),
            ),
            "assistant": _parse_int(window_caps.get("assistant", 0), 0),
            "framework": _parse_int(window_caps.get("framework", 0), 0),
        },
    }

    projected = {
        "overall": totals["overall"] + estimated,
        "assistant": totals["assistant"] + (estimated if track == "assistant" else 0),
        "framework": totals["framework"] + (estimated if track == "framework" else 0),
    }

    breaches: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    def evaluate_limit(metric_id: str, actual: int, limit: int) -> None:
        if limit < 1:
            return
        if actual > limit:
            breaches.append({"id": metric_id, "actual": actual, "limit": limit})
            return
        threshold = max(1, int(limit * warning_threshold_pct / 100))
        if actual >= threshold:
            warnings.append({"id": metric_id, "actual": actual, "threshold": threshold, "limit": limit})

    evaluate_limit("cycle.overall", estimated, limits["cycle"]["overall"])
    evaluate_limit(f"cycle.{track}", estimated, limits["cycle"][track])
    evaluate_limit("window.overall", projected["overall"], limits["window"]["overall"])
    evaluate_limit(f"window.{track}", projected[track], limits["window"][track])

    breach_action = str(budget_policy.get("breach_action", "block")).strip().lower()
    if breach_action not in SUPPORTED_BREACH_ACTIONS:
        breach_action = "block"

    if breaches:
        decision = "warn" if breach_action == "warn" else breach_action
        reason = "budget cap breached: " + ", ".join(item["id"] for item in breaches)
    elif warnings:
        decision = "warn"
        reason = "budget near threshold: " + ", ".join(item["id"] for item in warnings)
    else:
        decision = "allow"
        reason = "budget within thresholds"

    apply_usage = decision in {"allow", "warn"}
    applied_usage = (
        projected
        if apply_usage
        else {
            "overall": totals["overall"],
            "assistant": totals["assistant"],
            "framework": totals["framework"],
        }
    )
    runtime["totals"] = dict(applied_usage)

    payload: Dict[str, Any] = {
        "decision": decision,
        "reason": reason,
        "breach_action": breach_action,
        "window": runtime["window"],
        "window_key": runtime["window_key"],
        "track": track,
        "estimated_cycle_tokens": estimated,
        "warning_threshold_pct": warning_threshold_pct,
        "limits": limits,
        "usage": {
            "current": {
                "overall": totals["overall"],
                "assistant": totals["assistant"],
                "framework": totals["framework"],
            },
            "projected": projected,
            "applied": applied_usage,
        },
        "breaches": breaches,
        "warnings": warnings,
        "enforced": decision in {"block", "defer"},
        "applied_usage": apply_usage,
    }
    return payload, runtime


def select_active_track(
    config: Dict[str, Any],
    cycle_number: int,
) -> str:
    """Choose active track for this cycle.

    Override via GAIA_ACTIVE_TRACK_OVERRIDE=assistant|framework.
    """
    tracks = normalized_track_config(config)
    override = os.environ.get("GAIA_ACTIVE_TRACK_OVERRIDE", "").strip().lower()
    if override in tracks:
        return override

    scheduler = config.get("evolution", {}).get("scheduler", "weighted_round_robin")
    if scheduler == "round_robin":
        order = sorted(tracks.keys())
        return order[(cycle_number - 1) % len(order)]

    # weighted_round_robin
    weighted_order: List[str] = []
    for name in sorted(tracks.keys()):
        weighted_order.extend([name] * int(tracks[name]["weight"]))
    if not weighted_order:
        return "assistant"
    return weighted_order[(cycle_number - 1) % len(weighted_order)]


def action_allowed_in_track(action_type: str, active_track: str, config: Dict[str, Any]) -> bool:
    """Return whether action_type is allowed in the active track policy."""
    tracks = normalized_track_config(config)
    track_cfg = tracks.get(active_track)
    if not track_cfg:
        return False
    allowed_actions = track_cfg.get("allowed_actions", [])
    return action_type in allowed_actions


# ---------------------------------------------------------------------------
# Reasoning
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are the reasoning core of Gaia Agent, a self-evolving autonomous agent for \
the Gaia Minds project. Every action you propose must align with the Constitution below.

<constitution>
{constitution}
</constitution>

You have access to these action types:
- verify_resources: Check if resource URLs are still live
- generate_indexes: Regenerate INDEX.md files
- add_research: Create a new research file (params: topic, subcategory, content)
- add_resource: Document a new resource (params: name, subcategory, content)
- create_tool: Create a new tool script (params: name, content, description)
- update_skill: Modify a skill file (params: skill_name, changes)
- open_issue: Open a GitHub issue (params: title, body, labels)
- comment_on_pr: Comment on a PR (params: pr_number, body)
- check_pr_status: Check PR status (params: pr_number)

Risk levels:
- auto_execute: verify_resources, generate_indexes (done immediately)
- auto_pr: add_research, add_resource, create_tool, update_skill (creates PR)
- require_review: anything modifying the agent itself (creates issue for human)
- forbidden: delete_constitution, disable_hooks, merge_own_pr, modify_git_history, bypass_review

IMPORTANT RULES:
- Never propose forbidden actions.
- For research/resource content, write COMPLETE, substantive content — not placeholders.
- Prioritize: stale resources > open issues > stale indexes > research gaps > tool improvements.
- If nothing needs doing, return an empty actions list. Don't invent busywork.
- Learn from past mistakes shown in the memory context.
- Be specific in your reasoning — reference what you observed in the state.
- Respect the active evolution track and only propose actions allowed for that track.
"""

USER_PROMPT_TEMPLATE = """\
Current repository state:
{state_json}

Recent memory (last {n_decisions} decisions):
{decisions_json}

Recent budget decisions:
{budget_decisions_json}

Lessons learned:
{lessons_json}

Agent state:
{agent_state_json}

Active evolution track for this cycle:
{active_track}

Track policy:
{track_policy_json}

Budget policy:
{budget_policy_json}

Based on the current state, what actions should I take this cycle?

Respond with valid JSON only (no markdown, no code fences):
{{
  "reasoning": "Step-by-step reasoning about what needs to be done and why",
  "actions": [
    {{"type": "action_type", "params": {{}}, "reasoning": "why this specific action"}}
  ]
}}

If nothing needs doing, return: {{"reasoning": "explanation", "actions": []}}
"""


def state_to_summary(state: RepoState) -> Dict[str, Any]:
    """Convert RepoState to a JSON-serializable summary for the prompt."""
    return {
        "open_issues_count": len(state.open_issues),
        "open_issues": state.open_issues[:10],
        "open_prs_count": len(state.open_prs),
        "open_prs": state.open_prs[:5],
        "recent_commits": state.recent_commits[:10],
        "stale_resources": state.stale_resources[:10],
        "stale_indexes": state.stale_indexes,
        "pending_reviews": state.pending_reviews[:5],
        "agent_pr_history": state.agent_pr_history[:10],
        "research_topics": state.research_topics,
        "resource_files_count": len(state.resource_files),
        "tool_files": state.tool_files,
    }


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM text responses."""
    out = text.strip()
    if out.startswith("```"):
        lines = out.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        out = "\n".join(lines)
    return out.strip()


def _extract_anthropic_text(response: Any) -> str:
    """Extract plain text from an Anthropic response object."""
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text
    return text


def _extract_chat_completion_text(payload: Dict[str, Any], provider_name: str) -> str:
    """Extract assistant message text from chat completion payload."""
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"{provider_name} response missing choices")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    if not isinstance(message, dict):
        raise ValueError(f"{provider_name} response has invalid message payload")
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "".join(parts)
    raise ValueError(f"{provider_name} response content is not text")


def _openai_chat_completion(
    client: Dict[str, Any],
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call OpenAI chat completions API and return text response."""
    endpoint = f"{client['base_url']}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {client['api_key']}",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=int(client["timeout_seconds"])) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {details[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI API returned non-JSON response") from exc

    return _extract_chat_completion_text(parsed, "OpenAI")


def _openrouter_chat_completion(
    client: Dict[str, Any],
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Call OpenRouter chat completions API and return text response."""
    endpoint = f"{client['base_url']}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {client['api_key']}",
        "Content-Type": "application/json",
        "HTTP-Referer": client["app_url"],
        "X-Title": client["app_name"],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=int(client["timeout_seconds"])) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter API returned HTTP {exc.code}: {details[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenRouter API returned non-JSON response") from exc

    return _extract_chat_completion_text(parsed, "OpenRouter")


def ask_model_for_plan(
    client: Any,
    config: Dict[str, Any],
    state: RepoState,
    memory: Dict[str, Any],
    constitution: str,
    active_track: str,
    provider: str,
    model: str,
) -> Dict[str, Any]:
    """Ask the configured reasoning provider to analyze state and propose actions."""
    reasoning_config = config.get("reasoning", {})
    reasoning_config = reasoning_config if isinstance(reasoning_config, dict) else {}
    max_tokens = reasoning_config.get("max_tokens", 4096)
    temperature = reasoning_config.get("temperature", 0.3)
    try:
        max_tokens_int = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens_int = 4096
    if max_tokens_int < 1:
        max_tokens_int = 4096
    try:
        temperature_float = float(temperature)
    except (TypeError, ValueError):
        temperature_float = 0.3

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(constitution=constitution)

    n_decisions = 10
    n_lessons = 10
    track_policy = normalized_track_config(config).get(active_track, {})
    budget_policy = normalized_budget_policy(config)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        state_json=json.dumps(state_to_summary(state), indent=2),
        n_decisions=n_decisions,
        decisions_json=json.dumps(memory.get("recent_decisions", []), indent=2),
        budget_decisions_json=json.dumps(memory.get("recent_budget_decisions", []), indent=2),
        lessons_json=json.dumps(memory.get("lessons", []), indent=2),
        agent_state_json=json.dumps(memory.get("state", {}), indent=2),
        active_track=active_track,
        track_policy_json=json.dumps(track_policy, indent=2),
        budget_policy_json=json.dumps(budget_policy, indent=2),
    )

    log.info("Asking reasoning provider '%s' (%s) for a plan...", provider, model)
    log.debug("System prompt: %d chars, User prompt: %d chars", len(system_prompt), len(user_prompt))

    text: str
    try:
        if provider == "anthropic":
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens_int,
                temperature=temperature_float,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = _extract_anthropic_text(response)
        elif provider == "openai":
            if not isinstance(client, dict):
                raise RuntimeError("OpenAI client is misconfigured")
            text = _openai_chat_completion(
                client=client,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens_int,
                temperature=temperature_float,
            )
        elif provider == "openrouter":
            if not isinstance(client, dict):
                raise RuntimeError("OpenRouter client is misconfigured")
            text = _openrouter_chat_completion(
                client=client,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens_int,
                temperature=temperature_float,
            )
        else:
            raise RuntimeError(f"Unsupported reasoning provider: {provider}")
    except Exception as exc:
        error_text = str(exc)
        error_class = _classify_reasoning_error(error_text)
        log.error("Reasoning request failed (%s/%s): %s", provider, model, exc)
        return {
            "reasoning": f"Reasoning request failed: {exc}",
            "actions": [],
            "_reasoning_error": error_text,
            "_reasoning_error_class": error_class,
        }

    # Parse JSON from response text.
    text = _strip_markdown_fences(text)

    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse reasoning response as JSON: %s", exc)
        log.error("Raw response: %s", text[:500])
        plan = {"reasoning": f"Failed to parse response: {exc}", "actions": []}

    actions = plan.get("actions", [])
    log.info(
        "Reasoning provider '%s' proposed %d action(s): %s",
        provider,
        len(actions),
        ", ".join(a.get("type", "?") for a in actions) or "(none)",
    )
    log.info("Reasoning: %s", plan.get("reasoning", "")[:200])

    return plan


# ---------------------------------------------------------------------------
# Main cycle
# ---------------------------------------------------------------------------


def run_cycle(
    config: Dict[str, Any],
    client: Any,
    cycle_number: int,
    reasoning_provider: str,
    reasoning_model: str,
    dry_run: bool = False,
) -> List[ActionResult]:
    """Run one complete agent cycle."""
    repo_root = str(REPO_ROOT)
    budget_policy = normalized_budget_policy(config)

    # 1. Gather state
    log.info("=== Cycle %d: Gathering state ===", cycle_number)
    state = gather_state(config, repo_root)

    # 2. Load memory
    memory = load_memory()
    active_track = select_active_track(config, cycle_number)
    log.info(
        (
            "Active track: %s (budget split: service=%s%%, self_improvement=%s%%, "
            "hard_cycle_token_cap=%s, hard_window_token_cap=%s, window=%s, breach_action=%s)"
        ),
        active_track,
        budget_policy["user_service_pct"],
        budget_policy["self_improvement_pct"],
        budget_policy["hard_cycle_token_cap"],
        budget_policy["hard_window_token_cap"],
        budget_policy["window"],
        budget_policy["breach_action"],
    )

    # 3. Load constitution
    constitution = load_constitution(repo_root)

    # 4. Ask reasoning provider for a plan
    failover_policy = _resolve_reasoning_failover_policy(config, reasoning_provider)
    hard_error_classes = set(failover_policy.get("hard_error_classes", []))
    failover_order = list(failover_policy.get("order", []))
    failover_models = failover_policy.get("models", {})
    failover_models = failover_models if isinstance(failover_models, dict) else {}
    log.info(
        "Reasoning failover policy: enabled=%s hard_errors=%s order=%s",
        bool(failover_policy.get("enabled", False)),
        ",".join(sorted(hard_error_classes)) or "(none)",
        ",".join(failover_order) or "(none)",
    )

    failover_attempts: List[Dict[str, str]] = []
    selected_provider = reasoning_provider
    selected_model = reasoning_model

    if client is None:
        log.info(
            "No API client available for provider '%s' -- proceeding with failover policy evaluation",
            reasoning_provider,
        )
        primary_error = f"No API client available for provider '{reasoning_provider}'"
        plan = {
            "reasoning": f"Reasoning request failed: {primary_error}",
            "actions": [],
            "_reasoning_error": primary_error,
            "_reasoning_error_class": "auth",
        }
    else:
        plan = ask_model_for_plan(
            client=client,
            config=config,
            state=state,
            memory=memory,
            constitution=constitution,
            active_track=active_track,
            provider=reasoning_provider,
            model=reasoning_model,
        )

    primary_error = str(plan.get("_reasoning_error", "")).strip()
    primary_error_class = str(plan.get("_reasoning_error_class", "other")).strip().lower()
    if primary_error:
        if dry_run:
            log.info("Dry-run mode: skipping runtime failover after error class=%s", primary_error_class)
        elif bool(failover_policy.get("enabled", False)) and primary_error_class in hard_error_classes:
            log.warning(
                "Reasoning failover triggered: provider=%s model=%s class=%s error=%s",
                reasoning_provider,
                reasoning_model,
                primary_error_class,
                primary_error,
            )
            for fallback_provider in failover_order:
                model_override = str(failover_models.get(fallback_provider, "")).strip()
                fallback_client, fallback_model, init_issue = _initialize_reasoning_client(
                    config,
                    fallback_provider,
                    model_override=model_override,
                )
                attempt: Dict[str, str] = {
                    "provider": fallback_provider,
                    "model": fallback_model,
                }
                if fallback_client is None:
                    attempt["outcome"] = "skipped"
                    attempt["reason"] = init_issue or "client-unavailable"
                    failover_attempts.append(attempt)
                    log.warning(
                        "Reasoning failover skipped %s/%s: %s",
                        fallback_provider,
                        fallback_model,
                        init_issue or "client-unavailable",
                    )
                    continue

                fallback_plan = ask_model_for_plan(
                    client=fallback_client,
                    config=config,
                    state=state,
                    memory=memory,
                    constitution=constitution,
                    active_track=active_track,
                    provider=fallback_provider,
                    model=fallback_model,
                )
                fallback_error = str(fallback_plan.get("_reasoning_error", "")).strip()
                fallback_error_class = str(fallback_plan.get("_reasoning_error_class", "other")).strip().lower()
                if fallback_error:
                    attempt["outcome"] = "failed"
                    attempt["reason"] = fallback_error_class or "other"
                    failover_attempts.append(attempt)
                    log.warning(
                        "Reasoning failover attempt failed: %s/%s class=%s error=%s",
                        fallback_provider,
                        fallback_model,
                        fallback_error_class or "other",
                        fallback_error,
                    )
                    continue

                attempt["outcome"] = "success"
                attempt["reason"] = "ok"
                failover_attempts.append(attempt)
                plan = fallback_plan
                selected_provider = fallback_provider
                selected_model = fallback_model
                log.info(
                    "Reasoning failover succeeded: %s/%s -> %s/%s",
                    reasoning_provider,
                    reasoning_model,
                    selected_provider,
                    selected_model,
                )
                break

            if failover_attempts and not any(item.get("outcome") == "success" for item in failover_attempts):
                log.error(
                    "Reasoning failover exhausted with no successful provider. "
                    "Attempts=%s",
                    failover_attempts,
                )
        elif not bool(failover_policy.get("enabled", False)):
            log.info("Reasoning failover disabled; not attempting fallback after error class=%s", primary_error_class)
        else:
            log.info(
                "Reasoning failover not applied for error class=%s (configured=%s)",
                primary_error_class,
                ",".join(sorted(hard_error_classes)) or "(none)",
            )

    if failover_attempts:
        log_lesson(
            cycle_number,
            "Reasoning failover attempted",
            "reasoning_failover",
            json.dumps(
                {
                    "from_provider": reasoning_provider,
                    "from_model": reasoning_model,
                    "to_provider": selected_provider,
                    "to_model": selected_model,
                    "attempts": failover_attempts,
                },
                separators=(",", ":"),
            ),
        )

    actions = plan.get("actions", [])
    actions = actions if isinstance(actions, list) else []

    memory_state = memory.get("state", {})
    memory_state = memory_state if isinstance(memory_state, dict) else {}
    estimated_cycle_tokens = estimate_cycle_tokens(config, budget_policy, actions)
    budget_decision, budget_runtime = evaluate_budget_decision(
        budget_policy=budget_policy,
        state=memory_state,
        active_track=active_track,
        estimated_cycle_tokens=estimated_cycle_tokens,
    )
    log_budget_decision(cycle_number, budget_decision)
    log.info(
        "Budget decision: %s (estimated_cycle_tokens=%d, reason=%s)",
        budget_decision.get("decision", "allow"),
        estimated_cycle_tokens,
        budget_decision.get("reason", ""),
    )

    if not actions:
        log.info("No actions proposed this cycle.")
        update_state(
            cycle_number,
            [],
            active_track,
            budget_policy,
            budget_runtime=budget_runtime,
            budget_decision=budget_decision,
        )
        return []

    if budget_decision.get("decision") in {"block", "defer"}:
        decision = str(budget_decision.get("decision", "block"))
        outcome = "blocked_by_budget" if decision == "block" else "deferred_by_budget"
        reason = str(budget_decision.get("reason", "")).strip()
        log.warning(
            "Budget gate enforced (%s): %s. Skipping %d action(s).",
            decision,
            reason or "no reason provided",
            len(actions),
        )
        budget_alignment = AlignmentResult(
            allowed=False,
            risk_level="high" if decision == "block" else "medium",
            reasoning=reason or "Budget gate enforced.",
        )
        log_decision(
            cycle_number,
            {
                "type": "budget_gate",
                "params": {
                    "decision": decision,
                    "estimated_cycle_tokens": estimated_cycle_tokens,
                    "track": active_track,
                },
            },
            budget_alignment,
            outcome,
            reason,
            active_track=active_track,
        )
        log_lesson(
            cycle_number,
            (
                f"Budget gate enforced decision='{decision}' for track '{active_track}' "
                f"(estimated_cycle_tokens={estimated_cycle_tokens})"
            ),
            "budget_gate",
            reason[:300],
        )
        update_state(
            cycle_number,
            [],
            active_track,
            budget_policy,
            budget_runtime=budget_runtime,
            budget_decision=budget_decision,
        )
        return []

    # 5. Process each action
    results: List[ActionResult] = []
    for i, action in enumerate(actions):
        action_type = action.get("type", "unknown")
        log.info("--- Action %d/%d: %s ---", i + 1, len(actions), action_type)

        if not action_allowed_in_track(action_type, active_track, config):
            reason = f"Action '{action_type}' blocked by track policy for '{active_track}'"
            log.warning(reason)
            track_policy_alignment = AlignmentResult(
                allowed=False,
                risk_level="high",
                reasoning=reason,
            )
            log_decision(
                cycle_number,
                action,
                track_policy_alignment,
                "blocked_by_track_policy",
                reason,
                active_track=active_track,
            )
            continue

        # 5a. Check alignment
        alignment = check_alignment(
            action,
            constitution,
            json.dumps(memory.get("recent_decisions", [])[-5:]),
            client=client if reasoning_provider == "anthropic" and _HAS_ANTHROPIC else None,
            model=reasoning_model,
        )

        log.info(
            "Alignment: %s (risk=%s) - %s",
            "ALLOWED" if alignment.allowed else "DENIED",
            alignment.risk_level,
            alignment.reasoning[:150],
        )

        # 5b. Route based on alignment + risk
        if not alignment.allowed:
            log.warning("Action BLOCKED by alignment checker")
            log_decision(cycle_number, action, alignment, "blocked", active_track=active_track)
            continue

        if alignment.risk_level == "forbidden":
            log.warning("Action FORBIDDEN")
            log_decision(cycle_number, action, alignment, "forbidden", active_track=active_track)
            continue

        if alignment.risk_level == "high":
            log.info("High-risk action -> creating issue for human review")
            if not dry_run:
                issue_action = {
                    "type": "open_issue",
                    "params": {
                        "title": f"[Agent] Review request: {action_type}",
                        "body": (
                            f"## Proposed Action\n\n"
                            f"**Type:** `{action_type}`\n\n"
                            f"**Params:**\n```json\n{json.dumps(action.get('params', {}), indent=2)}\n```\n\n"
                            f"**Agent reasoning:** {action.get('reasoning', 'N/A')}\n\n"
                            f"## Alignment Check\n\n"
                            f"**Risk level:** {alignment.risk_level}\n"
                            f"**Reasoning:** {alignment.reasoning}\n\n"
                            f"---\n"
                            f"*This issue was created by gaia-agent cycle {cycle_number}. "
                            f"Please review and provide guidance.*"
                        ),
                        "labels": ["human-input", "agent-contribution"],
                    },
                }
                result = execute_action(issue_action, config, repo_root)
                results.append(result)
            log_decision(
                cycle_number,
                action,
                alignment,
                "deferred_to_human",
                active_track=active_track,
            )
            continue

        # 5c. Execute (low or medium risk)
        if dry_run:
            log.info("[DRY RUN] Would execute: %s", action_type)
            log_decision(cycle_number, action, alignment, "dry_run", active_track=active_track)
            continue

        log.info("Executing action...")
        result = execute_action(action, config, repo_root)
        results.append(result)

        outcome = "success" if result.success else "failed"
        log.info("Result: %s - %s", outcome, result.output[:200] if result.output else result.error[:200])

        log_decision(
            cycle_number,
            action,
            alignment,
            outcome,
            result.output or result.error,
            active_track=active_track,
        )

        # Learn from failures
        if not result.success:
            log_lesson(
                cycle_number,
                f"Action '{action_type}' failed: {result.error[:200]}",
                "error",
                json.dumps(action.get("params", {})),
            )

    # 6. Update state
    update_state(
        cycle_number,
        results,
        active_track,
        budget_policy,
        budget_runtime=budget_runtime,
        budget_decision=budget_decision,
    )

    # 7. Rotate logs if needed
    rotate_logs(config)

    # 8. Commit memory
    if not dry_run:
        commit_memory(cycle_number)

    return results


# ---------------------------------------------------------------------------
# Learn from PR feedback
# ---------------------------------------------------------------------------


def check_pr_feedback(config: Dict[str, Any], cycle_number: int) -> None:
    """Check if any of our past PRs got merged or rejected, and learn."""
    repo_root = str(REPO_ROOT)
    state = gather_state(config, repo_root)

    for pr in state.agent_pr_history:
        pr_state = pr.get("state", "").upper()
        pr_title = pr.get("title", "")
        pr_number = pr.get("number", "?")

        # Check if we already have a lesson about this PR
        memory = load_memory(n_decisions=0, n_lessons=100)
        already_logged = any(
            f"PR #{pr_number}" in lesson.get("context", "")
            for lesson in memory.get("lessons", [])
        )
        if already_logged:
            continue

        if pr_state == "MERGED":
            log_lesson(
                cycle_number,
                f"PR #{pr_number} '{pr_title}' was merged successfully",
                "pr_merged",
                f"PR #{pr_number}",
            )
            log.info("Learned: PR #%s was merged", pr_number)

        elif pr_state == "CLOSED":
            log_lesson(
                cycle_number,
                f"PR #{pr_number} '{pr_title}' was closed without merge -- review why",
                "pr_rejected",
                f"PR #{pr_number}",
            )
            log.info("Learned: PR #%s was rejected", pr_number)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gaia Minds Self-Evolving Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 tools/agent-loop.py                     # single cycle\n"
            "  python3 tools/agent-loop.py --mode continuous    # loop every hour\n"
            "  python3 tools/agent-loop.py --dry-run -v         # plan without executing\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_PATH),
        help="Path to agent-config.yml (default: tools/agent-config.yml)",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "continuous"],
        default=None,
        help="Override cycle mode from config",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gather state and plan, but don't execute actions",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, stream=sys.stderr)

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    config = load_config(config_path)
    if not isinstance(config, dict):
        log.error("Config file is invalid: expected a YAML mapping at %s", config_path)
        return 1

    budget_errors = validate_budget_policy_config(config)
    if budget_errors:
        log.error("Budget configuration validation failed:")
        for item in budget_errors:
            log.error("- %s", item)
        return 1

    reasoning_provider = _resolve_reasoning_provider(config)
    reasoning_model = _resolve_reasoning_model(config, reasoning_provider)
    openai_runtime: Optional[Dict[str, Any]] = None
    openrouter_runtime: Optional[Dict[str, Any]] = None
    if reasoning_provider == "openai":
        openai_runtime = _resolve_openai_runtime(config)
    if reasoning_provider == "openrouter":
        openrouter_runtime = _resolve_openrouter_runtime(config)
    log.info("Reasoning provider selected: %s (model: %s)", reasoning_provider, reasoning_model)
    failover_policy = _resolve_reasoning_failover_policy(config, reasoning_provider)
    log.info(
        "Failover configured: enabled=%s hard_errors=%s order=%s",
        bool(failover_policy.get("enabled", False)),
        ",".join(failover_policy.get("hard_error_classes", [])) or "(none)",
        ",".join(failover_policy.get("order", [])) or "(none)",
    )

    # Validate provider runtime requirements (except in dry-run).
    if not args.dry_run:
        preflight_issue = ""
        if reasoning_provider == "anthropic":
            if not _HAS_ANTHROPIC:
                preflight_issue = "anthropic-package"
            elif not os.environ.get("ANTHROPIC_API_KEY", "").strip():
                preflight_issue = "anthropic-key"
        elif reasoning_provider == "openrouter":
            if not openrouter_runtime or not openrouter_runtime.get("api_key"):
                preflight_issue = "openrouter-key"
        elif reasoning_provider == "openai":
            if not openai_runtime or not openai_runtime.get("api_key"):
                preflight_issue = "openai-key"
        else:
            preflight_issue = "unsupported-provider"

        if preflight_issue:
            if bool(failover_policy.get("enabled", False)):
                log.warning(
                    "Primary reasoning provider preflight failed (%s); continuing because failover is enabled.",
                    preflight_issue,
                )
            else:
                if preflight_issue == "anthropic-package":
                    log.error(
                        "Reasoning provider is 'anthropic' but the 'anthropic' package is missing.\n"
                        "Install it:\n"
                        "  pip install anthropic\n"
                        "Or: pip install -r requirements.txt"
                    )
                elif preflight_issue == "anthropic-key":
                    log.error(
                        "Reasoning provider is 'anthropic' but ANTHROPIC_API_KEY is not set.\n"
                        "  export ANTHROPIC_API_KEY='your-key-here'"
                    )
                elif preflight_issue == "openrouter-key":
                    log.error(
                        "Reasoning provider is 'openrouter' but OPENROUTER_API_KEY is not set.\n"
                        "  export OPENROUTER_API_KEY='your-key-here'"
                    )
                elif preflight_issue == "openai-key":
                    log.error(
                        "Reasoning provider is 'openai' but OPENAI_API_KEY is not set.\n"
                        "  export OPENAI_API_KEY='your-key-here'"
                    )
                else:
                    log.error(
                        "Unsupported reasoning provider '%s'. Supported: anthropic, openai, openrouter",
                        reasoning_provider,
                    )
                return 1

    log.info("Loaded config: %s v%s", config.get("agent", {}).get("name", "?"), config.get("agent", {}).get("version", "?"))

    # Determine mode
    mode = args.mode or config.get("cycle", {}).get("mode", "single")

    # Initialize provider client.
    client: Any = None
    if reasoning_provider == "anthropic" and _HAS_ANTHROPIC and os.environ.get("ANTHROPIC_API_KEY", "").strip():
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip())
        log.info("Anthropic client initialized (model: %s)", reasoning_model)
    elif reasoning_provider == "openai" and openai_runtime and openai_runtime.get("api_key"):
        client = openai_runtime
        log.info(
            "OpenAI client initialized (model: %s, base_url: %s)",
            reasoning_model,
            openai_runtime.get("base_url"),
        )
    elif reasoning_provider == "openrouter" and openrouter_runtime and openrouter_runtime.get("api_key"):
        client = openrouter_runtime
        log.info(
            "OpenRouter client initialized (model: %s, base_url: %s)",
            reasoning_model,
            openrouter_runtime.get("base_url"),
        )
    else:
        log.info(
            "No provider client initialized (provider=%s, likely dry-run or missing credentials)",
            reasoning_provider,
        )

    # Ensure memory directory exists
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for path in [DECISIONS_PATH, LESSONS_PATH]:
        if not path.exists():
            path.touch()
    if not STATE_PATH.exists():
        STATE_PATH.write_text("{}\n", encoding="utf-8")

    # Load current state to get cycle number
    try:
        state_data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        state_data = {}
    cycle_number = state_data.get("last_cycle", 0) + 1

    if mode == "single":
        log.info("Running single cycle (#%d)...", cycle_number)
        # Check PR feedback before planning
        check_pr_feedback(config, cycle_number)
        results = run_cycle(
            config=config,
            client=client,
            cycle_number=cycle_number,
            reasoning_provider=reasoning_provider,
            reasoning_model=reasoning_model,
            dry_run=args.dry_run,
        )
        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        log.info("Cycle %d complete: %d succeeded, %d failed", cycle_number, succeeded, failed)
        return 1 if failed > 0 else 0

    elif mode == "continuous":
        interval = config.get("cycle", {}).get("interval_minutes", 60)
        max_cycles = config.get("cycle", {}).get("max_cycles", 0)
        log.info("Running continuously (interval=%dm, max_cycles=%s)...", interval, max_cycles or "unlimited")

        try:
            cycles_run = 0
            while True:
                check_pr_feedback(config, cycle_number)
                results = run_cycle(
                    config=config,
                    client=client,
                    cycle_number=cycle_number,
                    reasoning_provider=reasoning_provider,
                    reasoning_model=reasoning_model,
                    dry_run=args.dry_run,
                )
                succeeded = sum(1 for r in results if r.success)
                failed = sum(1 for r in results if not r.success)
                log.info("Cycle %d complete: %d succeeded, %d failed", cycle_number, succeeded, failed)

                cycle_number += 1
                cycles_run += 1

                if max_cycles and cycles_run >= max_cycles:
                    log.info("Reached max_cycles (%d). Stopping.", max_cycles)
                    break

                log.info("Sleeping %d minutes until next cycle...", interval)
                time.sleep(interval * 60)

        except KeyboardInterrupt:
            log.info("\nInterrupted by user. Exiting gracefully.")
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
