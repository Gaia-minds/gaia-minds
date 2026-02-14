#!/usr/bin/env python3
"""Deterministic hypothesis pipeline v1: proposal -> eval -> evidence package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HYPOTHESIS = REPO_ROOT / "assistant" / "hypotheses" / "phase3-hypothesis-pipeline-v1.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "assistant" / "hypothesis-evals"
DEFAULT_CONFIG = Path.home() / ".gaia-assistant" / "config.json"
DEFAULT_SIGNALS_LEDGER = Path.home() / ".gaia-assistant" / "data" / "unmet-intent-signals.json"
DEFAULT_SIGNALS_TRIAGE_LEDGER = Path.home() / ".gaia-assistant" / "data" / "unmet-intent-signal-triage.json"
DEFAULT_SIGNAL_CANDIDATE_OUTPUT = REPO_ROOT / "assistant" / "hypotheses" / "signal-candidates.json"
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_COMPARATORS = {">", ">=", "<", "<=", "==", "!="}
SIGNAL_CANDIDATE_SCHEMA_VERSION = 1
SIGNAL_CANDIDATE_CLASS_CHOICES: Sequence[str] = (
    "existing-skill-enable",
    "skill-import-candidate",
    "core-feature-gap",
    "out-of-scope-or-rejected",
)
SIGNAL_CANDIDATE_ALLOWED_PROMOTION_CLASSES: Set[str] = {
    "existing-skill-enable",
    "skill-import-candidate",
    "core-feature-gap",
}
SIGNAL_CANDIDATE_FORBIDDEN_KEYS: Set[str] = {
    "raw_text",
    "transcript",
    "conversation",
    "messages",
    "correction",
    "content",
    "user_text",
    "prompt_text",
}


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    return cleaned or "step"


def _normalize_number(value: Any, context: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be numeric, got bool")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise ValueError(f"{context} must be numeric, got {value!r}") from exc
    raise ValueError(f"{context} must be numeric, got {type(value).__name__}")


def _extract_json_path(payload: Dict[str, Any], json_path: str) -> Any:
    cursor: Any = payload
    for segment in json_path.split("."):
        part = segment.strip()
        if not part:
            continue
        if isinstance(cursor, list):
            try:
                idx = int(part)
            except ValueError as exc:
                raise KeyError(f"list index expected at '{part}' in json_path '{json_path}'") from exc
            if idx < 0 or idx >= len(cursor):
                raise KeyError(f"list index out of range at '{part}' in json_path '{json_path}'")
            cursor = cursor[idx]
            continue
        if not isinstance(cursor, dict):
            raise KeyError(f"cannot access '{part}' in json_path '{json_path}'")
        if part not in cursor:
            raise KeyError(f"missing key '{part}' in json_path '{json_path}'")
        cursor = cursor[part]
    return cursor


def _read_json_optional(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _normalize_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _normalize_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        normalized = int(value)
    except Exception:
        normalized = default
    if normalized < minimum:
        return minimum
    if normalized > maximum:
        return maximum
    return normalized


def _safe_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        normalized = float(value)
    except Exception:
        normalized = default
    if normalized < minimum:
        return minimum
    if normalized > maximum:
        return maximum
    return normalized


def _parse_iso8601(value: str) -> Optional[datetime]:
    raw = str(value).strip()
    if not raw:
        return None
    candidate = raw
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _contains_forbidden_keys(payload: Any, forbidden_keys: Set[str]) -> Optional[str]:
    def walk(value: Any, prefix: str) -> Optional[str]:
        if isinstance(value, dict):
            for key, nested in value.items():
                label = str(key).strip().lower()
                current = f"{prefix}.{key}" if prefix else str(key)
                if label in forbidden_keys:
                    return current
                found = walk(nested, current)
                if found:
                    return found
        elif isinstance(value, list):
            for idx, nested in enumerate(value):
                current = f"{prefix}[{idx}]"
                found = walk(nested, current)
                if found:
                    return found
        return None

    return walk(payload, "")


def _signal_hypothesis_stub(
    *,
    base_hypothesis: Dict[str, Any],
    signal_evidence: Dict[str, Any],
    triage_class: str,
) -> Dict[str, Any]:
    signal_id = str(signal_evidence.get("signal_id", "")).strip() or "signal"
    intent_tag = str(signal_evidence.get("intent_tag", "")).strip() or "unknown-intent"
    count = int(signal_evidence.get("count", 0))
    confidence = float(signal_evidence.get("confidence", 0.0))
    hypothesis_id = f"phase3-signal-{_slug(intent_tag)}-{_slug(signal_id[-8:])}"

    if triage_class == "core-feature-gap":
        title_prefix = "Core Feature Gap"
    elif triage_class == "skill-import-candidate":
        title_prefix = "Skill Import Candidate"
    else:
        title_prefix = "Skill Activation Candidate"

    stub = deepcopy(base_hypothesis)
    stub["schema_version"] = 1
    stub["hypothesis_id"] = hypothesis_id
    stub["title"] = f"{title_prefix}: {intent_tag}"
    stub["summary"] = (
        f"Signal-derived candidate from unmet-intent evidence "
        f"(signal_id={signal_id}, triage_class={triage_class}, count={count}, confidence={confidence:.3f})."
    )
    stub["owner"] = "framework-track"
    if str(stub.get("risk_level", "")).strip().lower() not in ALLOWED_RISK_LEVELS:
        stub["risk_level"] = "medium"
    stub["signal_evidence"] = {
        "source": "derived-signals-only",
        "signal_id": signal_id,
        "intent_tag": intent_tag,
        "triage_class": triage_class,
        "count": count,
        "confidence": confidence,
        "first_seen_at": str(signal_evidence.get("first_seen_at", "")).strip(),
        "last_seen_at": str(signal_evidence.get("last_seen_at", "")).strip(),
        "source_event_count": int(signal_evidence.get("source_event_count", 0)),
    }
    return stub


def _resolve_template(value: str, hypothesis_id: str, output_dir: Path) -> str:
    return (
        value.replace("{hypothesis_id}", hypothesis_id)
        .replace("{output_dir}", str(output_dir))
        .replace("{repo_root}", str(REPO_ROOT))
    )


def _resolve_repo_path(path_value: str, hypothesis_id: str, output_dir: Path) -> Path:
    resolved = Path(_resolve_template(path_value, hypothesis_id, output_dir)).expanduser()
    if not resolved.is_absolute():
        resolved = (REPO_ROOT / resolved).resolve()
    return resolved


def _compare(lhs: float, comparator: str, rhs: float) -> bool:
    if comparator == ">":
        return lhs > rhs
    if comparator == ">=":
        return lhs >= rhs
    if comparator == "<":
        return lhs < rhs
    if comparator == "<=":
        return lhs <= rhs
    if comparator == "==":
        return lhs == rhs
    if comparator == "!=":
        return lhs != rhs
    raise ValueError(f"unsupported comparator: {comparator}")


def _validate_hypothesis(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    schema_version = payload.get("schema_version")
    if schema_version != 1:
        errors.append("schema_version must be 1")

    hypothesis_id = str(payload.get("hypothesis_id", "")).strip()
    if not hypothesis_id:
        errors.append("hypothesis_id is required")

    for key in ("title", "summary", "owner"):
        value = str(payload.get(key, "")).strip()
        if not value:
            errors.append(f"{key} is required")

    risk_level = str(payload.get("risk_level", "")).strip().lower()
    if risk_level not in ALLOWED_RISK_LEVELS:
        errors.append("risk_level must be one of: low, medium, high")

    rollback = payload.get("rollback_criteria")
    if not isinstance(rollback, dict):
        errors.append("rollback_criteria must be an object")
    else:
        recommended_action = str(rollback.get("recommended_action", "")).strip()
        if not recommended_action:
            errors.append("rollback_criteria.recommended_action is required")
        commands = rollback.get("commands", [])
        if commands and not isinstance(commands, list):
            errors.append("rollback_criteria.commands must be an array when provided")

    evaluation = payload.get("evaluation")
    if not isinstance(evaluation, dict):
        errors.append("evaluation must be an object")
    else:
        commands = evaluation.get("commands", [])
        if not isinstance(commands, list):
            errors.append("evaluation.commands must be an array")
            commands = []
        for idx, item in enumerate(commands):
            if not isinstance(item, dict):
                errors.append(f"evaluation.commands[{idx}] must be an object")
                continue
            cid = str(item.get("id", "")).strip()
            run = str(item.get("run", "")).strip()
            if not cid:
                errors.append(f"evaluation.commands[{idx}].id is required")
            if not run:
                errors.append(f"evaluation.commands[{idx}].run is required")

        required_artifacts = evaluation.get("required_artifacts", [])
        if required_artifacts and not isinstance(required_artifacts, list):
            errors.append("evaluation.required_artifacts must be an array when provided")

    metrics = payload.get("expected_metric_movement", [])
    if not isinstance(metrics, list) or not metrics:
        errors.append("expected_metric_movement must be a non-empty array")
    else:
        for idx, item in enumerate(metrics):
            if not isinstance(item, dict):
                errors.append(f"expected_metric_movement[{idx}] must be an object")
                continue

            metric_id = str(item.get("id", "")).strip()
            metric_name = str(item.get("name", "")).strip()
            comparator = str(item.get("comparator", "")).strip()
            if not metric_id:
                errors.append(f"expected_metric_movement[{idx}].id is required")
            if not metric_name:
                errors.append(f"expected_metric_movement[{idx}].name is required")
            if comparator not in ALLOWED_COMPARATORS:
                errors.append(
                    f"expected_metric_movement[{idx}].comparator must be one of {sorted(ALLOWED_COMPARATORS)}"
                )

            if "target_delta" not in item:
                errors.append(f"expected_metric_movement[{idx}].target_delta is required")
            else:
                try:
                    _normalize_number(item.get("target_delta"), f"expected_metric_movement[{idx}].target_delta")
                except ValueError as exc:
                    errors.append(str(exc))

            for side in ("baseline", "current"):
                side_obj = item.get(side)
                if not isinstance(side_obj, dict):
                    errors.append(f"expected_metric_movement[{idx}].{side} must be an object")
                    continue
                path = str(side_obj.get("path", "")).strip()
                json_path = str(side_obj.get("json_path", "")).strip()
                if not path:
                    errors.append(f"expected_metric_movement[{idx}].{side}.path is required")
                if not json_path:
                    errors.append(f"expected_metric_movement[{idx}].{side}.json_path is required")

    canary_gate = payload.get("canary_gate")
    if canary_gate is not None:
        if not isinstance(canary_gate, dict):
            errors.append("canary_gate must be an object when provided")
        else:
            window = str(canary_gate.get("window", "")).strip()
            if not window:
                errors.append("canary_gate.window is required when canary_gate is provided")

            try:
                sample_size = int(canary_gate.get("sample_size", 0))
            except Exception:
                sample_size = 0
            if sample_size < 1:
                errors.append("canary_gate.sample_size must be a positive integer")

            try:
                pass_threshold = _normalize_number(
                    canary_gate.get("pass_threshold"),
                    "canary_gate.pass_threshold",
                )
            except ValueError as exc:
                errors.append(str(exc))
                pass_threshold = -1.0

            try:
                rollback_threshold = _normalize_number(
                    canary_gate.get("rollback_threshold"),
                    "canary_gate.rollback_threshold",
                )
            except ValueError as exc:
                errors.append(str(exc))
                rollback_threshold = -1.0

            if pass_threshold < 0 or pass_threshold > 1:
                errors.append("canary_gate.pass_threshold must be between 0 and 1")
            if rollback_threshold < 0 or rollback_threshold > 1:
                errors.append("canary_gate.rollback_threshold must be between 0 and 1")
            if (
                pass_threshold >= 0
                and rollback_threshold >= 0
                and pass_threshold < rollback_threshold
            ):
                errors.append(
                    "canary_gate.pass_threshold must be >= canary_gate.rollback_threshold"
                )

            fallback_owner = str(canary_gate.get("fallback_owner", "")).strip()
            if not fallback_owner:
                errors.append(
                    "canary_gate.fallback_owner is required when canary_gate is provided"
                )

    return errors


def _run_command(command: str, dry_run: bool) -> Tuple[int, str, str, float]:
    started = time.monotonic()
    if dry_run:
        elapsed = (time.monotonic() - started) * 1000.0
        return 0, f"dry-run: skipped command: {command}\n", "", elapsed

    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        shell=True,
        capture_output=True,
        text=True,
    )
    elapsed = (time.monotonic() - started) * 1000.0
    return proc.returncode, proc.stdout, proc.stderr, elapsed


def _evaluate_metric(item: Dict[str, Any], hypothesis_id: str, output_dir: Path) -> Dict[str, Any]:
    metric_id = str(item.get("id", "")).strip()
    metric_name = str(item.get("name", "")).strip()
    comparator = str(item.get("comparator", "")).strip()
    target_delta = _normalize_number(item.get("target_delta"), f"metric '{metric_id}' target_delta")
    required = bool(item.get("required", True))

    baseline_obj = item.get("baseline", {})
    current_obj = item.get("current", {})
    assert isinstance(baseline_obj, dict)
    assert isinstance(current_obj, dict)

    baseline_path = _resolve_repo_path(str(baseline_obj.get("path", "")), hypothesis_id, output_dir)
    current_path = _resolve_repo_path(str(current_obj.get("path", "")), hypothesis_id, output_dir)
    baseline_json_path = str(baseline_obj.get("json_path", "")).strip()
    current_json_path = str(current_obj.get("json_path", "")).strip()

    result: Dict[str, Any] = {
        "id": metric_id,
        "name": metric_name,
        "required": required,
        "comparator": comparator,
        "target_delta": target_delta,
        "baseline": None,
        "current": None,
        "delta": None,
        "passed": False,
        "error": "",
        "sources": {
            "baseline_path": str(baseline_path),
            "baseline_json_path": baseline_json_path,
            "current_path": str(current_path),
            "current_json_path": current_json_path,
        },
    }

    try:
        baseline_payload = _read_json(baseline_path)
        current_payload = _read_json(current_path)
        baseline_value = _normalize_number(
            _extract_json_path(baseline_payload, baseline_json_path),
            f"metric '{metric_id}' baseline value",
        )
        current_value = _normalize_number(
            _extract_json_path(current_payload, current_json_path),
            f"metric '{metric_id}' current value",
        )
        delta = current_value - baseline_value
        passed = _compare(delta, comparator, target_delta)
        result.update(
            {
                "baseline": baseline_value,
                "current": current_value,
                "delta": delta,
                "passed": passed,
            }
        )
    except Exception as exc:
        result["error"] = str(exc)
        result["passed"] = False

    return result


def _evaluate_canary_gate(
    hypothesis: Dict[str, Any],
    command_results: List[Dict[str, Any]],
    metric_results: List[Dict[str, Any]],
    rollback_required: bool,
) -> Dict[str, Any]:
    canary_gate = hypothesis.get("canary_gate")
    if not isinstance(canary_gate, dict):
        return {
            "configured": False,
            "decision": "hold",
            "reason": "canary_gate config missing; default hold decision.",
            "window": "",
            "sample_size_required": 0,
            "sample_size_observed": 0,
            "sample_sufficient": False,
            "thresholds": {
                "pass_threshold": 1.0,
                "rollback_threshold": 1.0,
            },
            "pass_rate": 0.0,
            "checks_total": 0,
            "checks_passed": 0,
            "fallback_owner": "",
            "rollback_required": rollback_required,
        }

    window = str(canary_gate.get("window", "")).strip()
    sample_size_required = max(1, int(canary_gate.get("sample_size", 1)))
    pass_threshold = float(canary_gate.get("pass_threshold", 1.0))
    rollback_threshold = float(canary_gate.get("rollback_threshold", 1.0))
    fallback_owner = str(canary_gate.get("fallback_owner", "")).strip()

    checks_total = len(command_results) + len(metric_results)
    checks_passed = sum(
        1
        for item in command_results
        if str(item.get("status", "")) in {"pass", "skipped-dry-run"}
    )
    checks_passed += sum(1 for item in metric_results if bool(item.get("passed", False)))
    pass_rate = checks_passed / checks_total if checks_total > 0 else 0.0
    sample_sufficient = checks_total >= sample_size_required

    if rollback_required or pass_rate < rollback_threshold:
        decision = "rollback-required"
        reason = (
            "Canary decision is rollback-required due to failing required gates or "
            f"pass_rate={pass_rate:.4f} below rollback_threshold={rollback_threshold:.4f}."
        )
    elif not sample_sufficient:
        decision = "hold"
        reason = (
            f"Canary sample insufficient ({checks_total}/{sample_size_required}); "
            "holding rollout for more evidence."
        )
    elif pass_rate >= pass_threshold:
        decision = "go"
        reason = (
            f"Canary pass_rate={pass_rate:.4f} meets pass_threshold={pass_threshold:.4f} "
            "with sufficient sample."
        )
    else:
        decision = "hold"
        reason = (
            f"Canary pass_rate={pass_rate:.4f} is between rollback_threshold={rollback_threshold:.4f} "
            f"and pass_threshold={pass_threshold:.4f}; holding rollout."
        )

    return {
        "configured": True,
        "decision": decision,
        "reason": reason,
        "window": window,
        "sample_size_required": sample_size_required,
        "sample_size_observed": checks_total,
        "sample_sufficient": sample_sufficient,
        "thresholds": {
            "pass_threshold": pass_threshold,
            "rollback_threshold": rollback_threshold,
        },
        "pass_rate": pass_rate,
        "checks_total": checks_total,
        "checks_passed": checks_passed,
        "fallback_owner": fallback_owner,
        "rollback_required": rollback_required,
    }


def _build_bundle_markdown(hypothesis: Dict[str, Any], report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Hypothesis Evidence Bundle: {hypothesis.get('title', 'Untitled')}")
    lines.append("")
    lines.append(f"- Hypothesis ID: `{hypothesis.get('hypothesis_id', '')}`")
    lines.append(f"- Risk level: `{hypothesis.get('risk_level', '')}`")
    lines.append(f"- Status: `{report.get('status', 'unknown')}`")
    lines.append(f"- Generated at: `{report.get('generated_at', '')}`")
    lines.append(f"- Dry run: `{report.get('dry_run', False)}`")
    lines.append("")
    lines.append("## Proposal")
    lines.append("")
    lines.append(str(hypothesis.get("summary", "")).strip())
    lines.append("")
    lines.append("## Command Execution")
    lines.append("")
    lines.append("| Command | Status | Exit | Duration (ms) |")
    lines.append("| --- | --- | --- | --- |")
    for item in report.get("command_results", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"| `{item.get('id', '')}` | `{item.get('status', '')}` | `{item.get('exit_code', '')}` | "
            f"{item.get('duration_ms', 0.0)} |"
        )
    lines.append("")
    lines.append("## Metric Movement")
    lines.append("")
    lines.append("| Metric | Baseline | Current | Delta | Comparator | Target | Status |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for item in report.get("metric_results", []):
        if not isinstance(item, dict):
            continue
        status = "pass" if bool(item.get("passed", False)) else "fail"
        lines.append(
            f"| `{item.get('name', '')}` | {item.get('baseline', 'n/a')} | {item.get('current', 'n/a')} | "
            f"{item.get('delta', 'n/a')} | `{item.get('comparator', '')}` | {item.get('target_delta', '')} | `{status}` |"
        )
        error = str(item.get("error", "")).strip()
        if error:
            lines.append(f"| `{item.get('name', '')}` error | n/a | n/a | n/a | n/a | n/a | `{error}` |")
    lines.append("")
    lines.append("## Canary Decision")
    lines.append("")
    canary = report.get("canary_decision", {})
    if isinstance(canary, dict):
        lines.append(f"- Decision: `{canary.get('decision', '')}`")
        lines.append(f"- Reason: {canary.get('reason', '')}")
        lines.append(f"- Window: `{canary.get('window', '')}`")
        lines.append(
            "- Sample size: observed `{observed}` / required `{required}` (sufficient={sufficient})".format(
                observed=canary.get("sample_size_observed", 0),
                required=canary.get("sample_size_required", 0),
                sufficient=canary.get("sample_sufficient", False),
            )
        )
        thresholds = canary.get("thresholds", {})
        if isinstance(thresholds, dict):
            lines.append(
                "- Thresholds: pass `>= {pass_t}` / rollback `< {rollback_t}`".format(
                    pass_t=thresholds.get("pass_threshold", ""),
                    rollback_t=thresholds.get("rollback_threshold", ""),
                )
            )
        lines.append(f"- Pass rate: `{float(canary.get('pass_rate', 0.0)):.4f}`")
        fallback_owner = str(canary.get("fallback_owner", "")).strip()
        if fallback_owner:
            lines.append(f"- Fallback owner: `{fallback_owner}`")
    else:
        lines.append("- Decision: `hold`")
        lines.append("- Reason: canary decision data unavailable")
    lines.append("")
    lines.append("## Rollback Recommendation")
    lines.append("")
    rollback = report.get("rollback_recommendation", {})
    if isinstance(rollback, dict):
        lines.append(f"- Required: `{rollback.get('required', False)}`")
        lines.append(f"- Reason: {rollback.get('reason', '')}")
        lines.append(f"- Recommended action: {rollback.get('recommended_action', '')}")
        commands = rollback.get("commands", [])
        if isinstance(commands, list) and commands:
            lines.append("- Suggested commands:")
            for command in commands:
                lines.append(f"  - `{command}`")
    lines.append("")
    lines.append("## Evidence Paths")
    lines.append("")
    for path_str in report.get("evidence_paths", []):
        lines.append(f"- `{path_str}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def _run_pipeline(hypothesis_path: Path, output_root: Path, run_id: str, dry_run: bool) -> Tuple[int, Dict[str, Any], Path]:
    hypothesis = _read_json(hypothesis_path)
    errors = _validate_hypothesis(hypothesis)
    if errors:
        print("Hypothesis contract validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1, {}, output_root

    hypothesis_id = str(hypothesis.get("hypothesis_id", "")).strip()
    output_dir = output_root / _slug(hypothesis_id) / _slug(run_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "hypothesis.json", hypothesis)

    evaluation = hypothesis.get("evaluation", {})
    assert isinstance(evaluation, dict)
    commands = evaluation.get("commands", [])
    commands = commands if isinstance(commands, list) else []
    required_artifacts = evaluation.get("required_artifacts", [])
    required_artifacts = required_artifacts if isinstance(required_artifacts, list) else []

    command_results: List[Dict[str, Any]] = []
    required_command_failures: List[str] = []

    commands_dir = output_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    for idx, item in enumerate(commands):
        if not isinstance(item, dict):
            continue
        command_id = _slug(str(item.get("id", f"command-{idx + 1}")))
        run_template = str(item.get("run", "")).strip()
        required = bool(item.get("required", True))
        command = _resolve_template(run_template, hypothesis_id, output_dir)
        exit_code, stdout, stderr, duration_ms = _run_command(command, dry_run=dry_run)

        stdout_path = commands_dir / f"{idx + 1:02d}-{command_id}.stdout.log"
        stderr_path = commands_dir / f"{idx + 1:02d}-{command_id}.stderr.log"
        _write_text(stdout_path, stdout)
        _write_text(stderr_path, stderr)

        status = "pass" if exit_code == 0 else "fail"
        if dry_run:
            status = "skipped-dry-run"
        if required and exit_code != 0:
            required_command_failures.append(command_id)

        command_results.append(
            {
                "id": command_id,
                "required": required,
                "command": command,
                "status": status,
                "exit_code": exit_code,
                "duration_ms": round(duration_ms, 3),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )

    artifact_checks: List[Dict[str, Any]] = []
    missing_required_artifacts: List[str] = []
    for path_item in required_artifacts:
        artifact_template = str(path_item).strip()
        if not artifact_template:
            continue
        artifact_path = _resolve_repo_path(artifact_template, hypothesis_id, output_dir)
        exists = artifact_path.exists()
        artifact_checks.append({"path": str(artifact_path), "exists": exists})
        if not exists:
            missing_required_artifacts.append(str(artifact_path))

    metrics = hypothesis.get("expected_metric_movement", [])
    metrics = metrics if isinstance(metrics, list) else []
    metric_results: List[Dict[str, Any]] = []
    required_metric_failures: List[str] = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        metric_result = _evaluate_metric(item, hypothesis_id=hypothesis_id, output_dir=output_dir)
        metric_results.append(metric_result)
        metric_id = str(metric_result.get("id", "")).strip()
        required = bool(metric_result.get("required", True))
        passed = bool(metric_result.get("passed", False))
        if required and not passed:
            required_metric_failures.append(metric_id or "unknown-metric")

    rollback = hypothesis.get("rollback_criteria", {})
    rollback = rollback if isinstance(rollback, dict) else {}

    rollback_required = bool(required_command_failures or required_metric_failures or missing_required_artifacts)
    rollback_reasons: List[str] = []
    if required_command_failures:
        rollback_reasons.append("required command failures: " + ", ".join(required_command_failures))
    if required_metric_failures:
        rollback_reasons.append("required metric gate failures: " + ", ".join(required_metric_failures))
    if missing_required_artifacts:
        rollback_reasons.append("missing required artifacts: " + ", ".join(missing_required_artifacts))

    report_status = "pass"
    if rollback_required:
        report_status = "fail"

    canary_decision = _evaluate_canary_gate(
        hypothesis=hypothesis,
        command_results=command_results,
        metric_results=metric_results,
        rollback_required=rollback_required,
    )
    if canary_decision.get("decision") == "rollback-required":
        rollback_required = True
        if report_status != "fail":
            report_status = "fail"
        reason = str(canary_decision.get("reason", "")).strip()
        if reason:
            rollback_reasons.append(reason)

    report: Dict[str, Any] = {
        "schema_version": 1,
        "pipeline_version": "hypothesis-pipeline-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis_id": hypothesis_id,
        "title": hypothesis.get("title", ""),
        "risk_level": hypothesis.get("risk_level", ""),
        "status": report_status,
        "dry_run": dry_run,
        "run_id": run_id,
        "hypothesis_path": str(hypothesis_path),
        "output_dir": str(output_dir),
        "command_results": command_results,
        "artifact_checks": artifact_checks,
        "metric_results": metric_results,
        "summary": {
            "commands_total": len(command_results),
            "required_command_failures": len(required_command_failures),
            "metrics_total": len(metric_results),
            "required_metric_failures": len(required_metric_failures),
            "missing_required_artifacts": len(missing_required_artifacts),
        },
        "rollback_recommendation": {
            "required": rollback_required,
            "reason": "; ".join(rollback_reasons) if rollback_reasons else "No rollback required.",
            "recommended_action": str(rollback.get("recommended_action", "")).strip(),
            "commands": rollback.get("commands", []),
        },
        "canary_decision": canary_decision,
    }

    report_path = output_dir / "evaluation-report.json"
    _write_json(report_path, report)

    bundle_markdown = _build_bundle_markdown(hypothesis, report)
    bundle_path = output_dir / "evidence-bundle.md"
    _write_text(bundle_path, bundle_markdown)

    evidence_paths: List[str] = [
        str(output_dir / "hypothesis.json"),
        str(report_path),
        str(bundle_path),
    ]
    for item in command_results:
        if not isinstance(item, dict):
            continue
        evidence_paths.append(str(item.get("stdout_path", "")))
        evidence_paths.append(str(item.get("stderr_path", "")))

    report["evidence_paths"] = evidence_paths
    _write_json(report_path, report)

    if report_status == "pass":
        print(f"Hypothesis pipeline PASS: {hypothesis_id}")
    else:
        print(f"Hypothesis pipeline FAIL: {hypothesis_id}")
    print(f"canary_decision={canary_decision.get('decision', '')}")
    print(f"report: {report_path}")
    print(f"bundle: {bundle_path}")

    exit_code = 0 if report_status == "pass" else 1
    return exit_code, report, output_dir


def _package_only(hypothesis_path: Path, report_path: Path, output_path: Path) -> int:
    hypothesis = _read_json(hypothesis_path)
    report = _read_json(report_path)
    bundle_markdown = _build_bundle_markdown(hypothesis, report)
    _write_text(output_path, bundle_markdown)
    print(f"wrote evidence bundle: {output_path}")
    return 0


def _generate_signal_candidates(
    *,
    signals_ledger_path: Path,
    triage_ledger_path: Path,
    config_path: Path,
    output_path: Path,
    base_hypothesis_path: Path,
    emit_hypotheses_dir: Optional[Path],
    min_count: int,
    min_confidence: float,
    max_age_days: int,
    max_candidates: int,
    now_value: str,
) -> Dict[str, Any]:
    now = _parse_iso8601(now_value) if now_value else datetime.now(timezone.utc)
    assert now is not None

    signals_payload = _read_json_optional(signals_ledger_path)
    triage_payload = _read_json_optional(triage_ledger_path)
    config_payload = _read_json_optional(config_path)
    base_hypothesis = _read_json(base_hypothesis_path)

    config_signals = config_payload.get("signals", {})
    config_signals = config_signals if isinstance(config_signals, dict) else {}
    config_enabled = _normalize_bool(config_signals.get("enabled", True), True)

    ledger_enabled = _normalize_bool(signals_payload.get("collection_enabled", True), True)
    effective_collection_enabled = config_enabled and ledger_enabled

    ledger_retention_days = _normalize_int(signals_payload.get("retention_days", 90), default=90, minimum=1, maximum=365)
    config_retention_days = _normalize_int(config_signals.get("retention_days", 90), default=90, minimum=1, maximum=365)
    effective_window_days = min(max_age_days, ledger_retention_days, config_retention_days)

    triage_items = triage_payload.get("items", [])
    triage_items = triage_items if isinstance(triage_items, list) else []
    triage_index: Dict[str, Dict[str, Any]] = {}
    for item in triage_items:
        if not isinstance(item, dict):
            continue
        signal_id = str(item.get("signal_id", "")).strip()
        if not signal_id:
            continue
        triage_index[signal_id] = item

    signals = signals_payload.get("signals", [])
    signals = signals if isinstance(signals, list) else []
    candidates: List[Dict[str, Any]] = []
    promoted_hypotheses: List[str] = []

    for raw_signal in signals:
        if not isinstance(raw_signal, dict):
            continue
        signal_id = str(raw_signal.get("signal_id", "")).strip()
        if not signal_id:
            continue

        triage_item = triage_index.get(signal_id, {})
        triage_class = str(triage_item.get("triage_class", "")).strip().lower()
        if triage_class not in SIGNAL_CANDIDATE_CLASS_CHOICES:
            triage_class = "out-of-scope-or-rejected"

        signal_evidence = {
            "signal_id": signal_id,
            "signal_type": str(raw_signal.get("signal_type", "")).strip().lower(),
            "intent_tag": str(raw_signal.get("intent_tag", "")).strip(),
            "count": _normalize_int(raw_signal.get("count", 0), default=0, minimum=0, maximum=1_000_000),
            "confidence": round(
                _safe_float(raw_signal.get("confidence", 0.0), default=0.0, minimum=0.0, maximum=1.0),
                3,
            ),
            "first_seen_at": str(raw_signal.get("first_seen_at", "")).strip(),
            "last_seen_at": str(raw_signal.get("last_seen_at", "")).strip(),
            "source_event_count": _normalize_int(
                raw_signal.get("source_event_count", 0),
                default=0,
                minimum=0,
                maximum=1_000_000,
            ),
            "triage_class": triage_class,
            "triage_confidence": round(
                _safe_float(triage_item.get("triage_confidence", 0.0), default=0.0, minimum=0.0, maximum=1.0),
                3,
            ),
            "follow_up_action": str(triage_item.get("follow_up_action", "")).strip(),
        }

        forbidden_in_signal = _contains_forbidden_keys(raw_signal, SIGNAL_CANDIDATE_FORBIDDEN_KEYS)
        forbidden_in_triage = _contains_forbidden_keys(triage_item, SIGNAL_CANDIDATE_FORBIDDEN_KEYS)
        forbidden_path = forbidden_in_signal or forbidden_in_triage

        parsed_last_seen = _parse_iso8601(signal_evidence["last_seen_at"])
        age_days = 99999.0
        if parsed_last_seen is not None:
            age_days = max(0.0, (now - parsed_last_seen).total_seconds() / 86400.0)

        pass_count = int(signal_evidence["count"]) >= min_count
        pass_confidence = float(signal_evidence["confidence"]) >= min_confidence
        pass_recency = age_days <= float(effective_window_days)
        pass_class = triage_class in SIGNAL_CANDIDATE_ALLOWED_PROMOTION_CLASSES

        status = "hold"
        reason = "thresholds_not_met"
        if forbidden_path:
            status = "reject"
            reason = f"forbidden_key_detected:{forbidden_path}"
        elif not effective_collection_enabled:
            status = "hold"
            reason = "signals_opt_out_enabled"
        elif not pass_class:
            status = "reject"
            reason = f"triage_class_not_promotable:{triage_class}"
        elif pass_count and pass_confidence and pass_recency:
            status = "promote"
            reason = "thresholds_met"
        else:
            hold_reasons: List[str] = []
            if not pass_count:
                hold_reasons.append("count")
            if not pass_confidence:
                hold_reasons.append("confidence")
            if not pass_recency:
                hold_reasons.append("recency")
            reason = "thresholds_not_met:" + ",".join(hold_reasons)

        score = float(signal_evidence["count"]) * float(signal_evidence["confidence"])
        score *= 1.0 + float(signal_evidence["triage_confidence"])
        score = round(score, 4)

        candidate: Dict[str, Any] = {
            "candidate_id": f"sigcand-{_slug(signal_id)}",
            "status": status,
            "reason": reason,
            "priority_score": score,
            "signal_evidence": signal_evidence,
            "promotion_gate": {
                "min_count": min_count,
                "min_confidence": min_confidence,
                "max_age_days": effective_window_days,
                "observed_age_days": round(age_days, 3),
                "pass_count": pass_count,
                "pass_confidence": pass_confidence,
                "pass_recency": pass_recency,
                "pass_class": pass_class,
            },
            "hypothesis": {},
        }

        if status == "promote":
            hypothesis_stub = _signal_hypothesis_stub(
                base_hypothesis=base_hypothesis,
                signal_evidence=signal_evidence,
                triage_class=triage_class,
            )
            hypothesis_entry: Dict[str, Any] = {
                "hypothesis_id": str(hypothesis_stub.get("hypothesis_id", "")).strip(),
                "title": str(hypothesis_stub.get("title", "")).strip(),
                "path": "",
            }
            if emit_hypotheses_dir is not None:
                emit_hypotheses_dir.mkdir(parents=True, exist_ok=True)
                hypothesis_path = emit_hypotheses_dir / f"{hypothesis_entry['hypothesis_id']}.json"
                _write_json(hypothesis_path, hypothesis_stub)
                hypothesis_entry["path"] = str(hypothesis_path)
                promoted_hypotheses.append(str(hypothesis_path))
            candidate["hypothesis"] = hypothesis_entry

        candidates.append(candidate)

    status_rank = {"promote": 0, "hold": 1, "reject": 2}
    candidates.sort(
        key=lambda item: (
            status_rank.get(str(item.get("status", "")).strip().lower(), 9),
            -float(item.get("priority_score", 0.0)),
            str(item.get("candidate_id", "")),
        )
    )
    candidates = candidates[:max_candidates]

    summary = {
        "signals_total": len([item for item in signals if isinstance(item, dict)]),
        "triage_items_total": len(triage_index),
        "candidates_total": len(candidates),
        "promoted_count": len([item for item in candidates if str(item.get("status", "")) == "promote"]),
        "held_count": len([item for item in candidates if str(item.get("status", "")) == "hold"]),
        "rejected_count": len([item for item in candidates if str(item.get("status", "")) == "reject"]),
        "opt_out_respected": not effective_collection_enabled,
    }

    output_payload: Dict[str, Any] = {
        "schema_version": SIGNAL_CANDIDATE_SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "source": {
            "signals_ledger_path": str(signals_ledger_path),
            "triage_ledger_path": str(triage_ledger_path),
            "config_path": str(config_path),
            "collection_enabled": effective_collection_enabled,
            "collection_enabled_config": config_enabled,
            "collection_enabled_ledger": ledger_enabled,
            "retention_days_ledger": ledger_retention_days,
            "retention_days_config": config_retention_days,
            "retention_window_days_effective": effective_window_days,
        },
        "thresholds": {
            "min_count": min_count,
            "min_confidence": min_confidence,
            "max_age_days": effective_window_days,
            "max_candidates": max_candidates,
        },
        "summary": summary,
        "class_summary": triage_payload.get("class_summary", {}),
        "promoted_hypotheses": promoted_hypotheses,
        "candidates": candidates,
    }

    _write_json(output_path, output_payload)
    return output_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic hypothesis pipeline v1")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="Validate hypothesis artifact contract")
    validate_parser.add_argument("--hypothesis", default=str(DEFAULT_HYPOTHESIS), help="Path to hypothesis JSON")

    run_parser = sub.add_parser("run", help="Run proposal -> eval -> evidence pipeline")
    run_parser.add_argument("--hypothesis", default=str(DEFAULT_HYPOTHESIS), help="Path to hypothesis JSON")
    run_parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output root directory")
    run_parser.add_argument("--run-id", default="latest", help="Run id subdirectory (default: latest)")
    run_parser.add_argument("--dry-run", action="store_true", help="Skip command execution and package from available artifacts")

    package_parser = sub.add_parser("package", help="Generate evidence bundle markdown from existing report")
    package_parser.add_argument("--hypothesis", default=str(DEFAULT_HYPOTHESIS), help="Path to hypothesis JSON")
    package_parser.add_argument("--report", required=True, help="Path to evaluation-report.json")
    package_parser.add_argument("--output", required=True, help="Path for evidence bundle markdown")

    candidates_parser = sub.add_parser(
        "signals-candidates",
        help="Generate deterministic hypothesis candidates from derived unmet-intent signal + triage ledgers",
    )
    candidates_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Assistant config path")
    candidates_parser.add_argument(
        "--signals-ledger",
        default=str(DEFAULT_SIGNALS_LEDGER),
        help="Path to unmet-intent signal ledger JSON",
    )
    candidates_parser.add_argument(
        "--triage-ledger",
        default=str(DEFAULT_SIGNALS_TRIAGE_LEDGER),
        help="Path to unmet-intent signal triage ledger JSON",
    )
    candidates_parser.add_argument(
        "--output",
        default=str(DEFAULT_SIGNAL_CANDIDATE_OUTPUT),
        help="Path to generated signal-candidate artifact JSON",
    )
    candidates_parser.add_argument(
        "--base-hypothesis",
        default=str(DEFAULT_HYPOTHESIS),
        help="Base hypothesis artifact used to materialize promoted candidate stubs",
    )
    candidates_parser.add_argument(
        "--emit-hypotheses-dir",
        default=None,
        help="Optional directory where promoted candidate hypothesis stubs are written",
    )
    candidates_parser.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum signal count required for candidate promotion",
    )
    candidates_parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.65,
        help="Minimum signal confidence required for candidate promotion",
    )
    candidates_parser.add_argument(
        "--max-age-days",
        type=int,
        default=90,
        help="Maximum signal age window (days) before candidate is held",
    )
    candidates_parser.add_argument(
        "--max-candidates",
        type=int,
        default=25,
        help="Maximum number of candidates to return",
    )
    candidates_parser.add_argument(
        "--now",
        default="",
        help="Optional ISO timestamp override for deterministic recency checks",
    )
    candidates_parser.add_argument("--json", dest="as_json", action="store_true", help="Emit candidate payload JSON")

    args = parser.parse_args()

    if args.command == "validate":
        hypothesis_path = Path(args.hypothesis).expanduser().resolve()
        try:
            payload = _read_json(hypothesis_path)
        except Exception as exc:
            print(f"error: unable to read hypothesis: {exc}")
            return 1
        errors = _validate_hypothesis(payload)
        if errors:
            print("Hypothesis contract invalid:")
            for item in errors:
                print(f"- {item}")
            return 1
        print("Hypothesis contract valid.")
        print(f"hypothesis_id={payload.get('hypothesis_id', '')}")
        print(f"risk_level={payload.get('risk_level', '')}")
        print(f"metrics={len(payload.get('expected_metric_movement', []))}")
        return 0

    if args.command == "run":
        hypothesis_path = Path(args.hypothesis).expanduser().resolve()
        output_root = Path(args.output_root).expanduser().resolve()
        try:
            exit_code, report, _ = _run_pipeline(
                hypothesis_path=hypothesis_path,
                output_root=output_root,
                run_id=args.run_id,
                dry_run=bool(args.dry_run),
            )
        except Exception as exc:
            print(f"error: hypothesis pipeline execution failed: {exc}")
            return 1

        rollback = report.get("rollback_recommendation", {})
        if isinstance(rollback, dict):
            print(f"rollback_required={rollback.get('required', False)}")
            print(f"rollback_reason={rollback.get('reason', '')}")
        return exit_code

    if args.command == "package":
        try:
            return _package_only(
                hypothesis_path=Path(args.hypothesis).expanduser().resolve(),
                report_path=Path(args.report).expanduser().resolve(),
                output_path=Path(args.output).expanduser().resolve(),
            )
        except Exception as exc:
            print(f"error: unable to package evidence bundle: {exc}")
            return 1

    if args.command == "signals-candidates":
        min_count = _normalize_int(args.min_count, default=2, minimum=1, maximum=1_000_000)
        min_confidence = _safe_float(args.min_confidence, default=0.65, minimum=0.0, maximum=1.0)
        max_age_days = _normalize_int(args.max_age_days, default=90, minimum=1, maximum=365)
        max_candidates = _normalize_int(args.max_candidates, default=25, minimum=1, maximum=500)
        emit_hypotheses_dir = (
            Path(args.emit_hypotheses_dir).expanduser().resolve()
            if str(args.emit_hypotheses_dir or "").strip()
            else None
        )
        try:
            payload = _generate_signal_candidates(
                signals_ledger_path=Path(args.signals_ledger).expanduser().resolve(),
                triage_ledger_path=Path(args.triage_ledger).expanduser().resolve(),
                config_path=Path(args.config).expanduser().resolve(),
                output_path=Path(args.output).expanduser().resolve(),
                base_hypothesis_path=Path(args.base_hypothesis).expanduser().resolve(),
                emit_hypotheses_dir=emit_hypotheses_dir,
                min_count=min_count,
                min_confidence=min_confidence,
                max_age_days=max_age_days,
                max_candidates=max_candidates,
                now_value=str(args.now or "").strip(),
            )
        except Exception as exc:
            print(f"error: signal candidate generation failed: {exc}")
            return 1

        if args.as_json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            summary = payload.get("summary", {})
            print(f"candidates={summary.get('candidates_total', 0)}")
            print(f"promoted={summary.get('promoted_count', 0)}")
            print(f"held={summary.get('held_count', 0)}")
            print(f"rejected={summary.get('rejected_count', 0)}")
            print(f"output={Path(args.output).expanduser().resolve()}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
