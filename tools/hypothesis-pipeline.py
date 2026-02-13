#!/usr/bin/env python3
"""Deterministic hypothesis pipeline v1: proposal -> eval -> evidence package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HYPOTHESIS = REPO_ROOT / "assistant" / "hypotheses" / "phase3-hypothesis-pipeline-v1.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "assistant" / "hypothesis-evals"
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_COMPARATORS = {">", ">=", "<", "<=", "==", "!="}


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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
