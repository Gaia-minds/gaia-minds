#!/usr/bin/env python3
"""Evaluate reliability drift against baseline thresholds and recent checkpoint history."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_CONFIG = REPO_ROOT / "assistant" / "reliability-baseline-phase3.json"
DEFAULT_CHECKPOINT_ROOT = Path("/tmp/gaia-reliability-checkpoints")
DEFAULT_RUN_ID = "latest"


METRIC_THRESHOLD_SPECS: Tuple[Tuple[str, str, str], ...] = (
    ("benchmark_pass_rate", "benchmark_pass_rate_min", ">="),
    ("benchmark_failure_rate", "benchmark_failure_rate_max", "<="),
    ("uat_pass_rate", "uat_pass_rate_min", ">="),
    ("uat_failure_rate", "uat_failure_rate_max", "<="),
    ("memory_quality_pass_rate", "memory_quality_pass_rate_min", ">="),
    ("memory_quality_p95_latency_ms", "memory_quality_p95_latency_ms_max", "<="),
    ("consolidated_failure_rate", "consolidated_failure_rate_max", "<="),
    ("mttr_proxy_hours", "mttr_proxy_hours_max", "<="),
)

TRIAGE_LINKS = [
    "infrastructure/reliability-triage-workflow.md",
    "docs/incidents/README.md",
    "docs/incidents/postmortem-template.md",
]

SEVERITY_ORDER = {"sev1": 1, "sev2": 2, "sev3": 3}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(raw: str) -> datetime:
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _load_json(path: Path) -> Dict[str, Any]:
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


def _validate_baseline(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    thresholds = payload.get("thresholds")
    if not isinstance(thresholds, dict):
        errors.append("thresholds must be an object")
    else:
        for metric_id, threshold_key, _ in METRIC_THRESHOLD_SPECS:
            if threshold_key not in thresholds:
                errors.append(f"thresholds.{threshold_key} is required for {metric_id}")
                continue
            value = thresholds.get(threshold_key)
            if not isinstance(value, (int, float)):
                errors.append(f"thresholds.{threshold_key} must be numeric")

    triage = payload.get("triage")
    if not isinstance(triage, dict):
        errors.append("triage must be an object")
    else:
        if not isinstance(triage.get("severity_by_metric"), dict):
            errors.append("triage.severity_by_metric must be an object")
        if not isinstance(triage.get("owner_by_severity"), dict):
            errors.append("triage.owner_by_severity must be an object")

    return errors


def _evaluate_gate(value: float, comparator: str, threshold: float) -> bool:
    if comparator == ">=":
        return value >= threshold
    if comparator == "<=":
        return value <= threshold
    raise ValueError(f"unsupported comparator: {comparator}")


def _severity_for_metric(metric_id: str, severity_map: Dict[str, str]) -> str:
    configured = str(severity_map.get(metric_id, "")).strip().lower()
    if configured in SEVERITY_ORDER:
        return configured
    if metric_id in {
        "benchmark_pass_rate",
        "benchmark_failure_rate",
        "uat_pass_rate",
        "uat_failure_rate",
        "consolidated_failure_rate",
    }:
        return "sev1"
    if metric_id in {"memory_quality_pass_rate", "memory_quality_p95_latency_ms", "mttr_proxy_hours"}:
        return "sev2"
    return "sev3"


def _downgrade_severity(severity: str) -> str:
    if severity == "sev1":
        return "sev2"
    if severity == "sev2":
        return "sev3"
    return "sev3"


def _severity_action_required(severity: str, fail_on_severity: str) -> bool:
    return SEVERITY_ORDER.get(severity, 3) <= SEVERITY_ORDER.get(fail_on_severity, 2)


def _load_checkpoint_reports(checkpoint_root: Path) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    for report_path in checkpoint_root.glob("*/reliability-checkpoint.json"):
        if not report_path.is_file():
            continue
        try:
            payload = _load_json(report_path)
        except Exception:
            continue

        raw_ts = str(payload.get("generated_at", "")).strip()
        if raw_ts:
            try:
                generated_at = _parse_iso(raw_ts)
            except ValueError:
                generated_at = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)
        else:
            generated_at = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)

        reports.append(
            {
                "run_id": str(payload.get("checkpoint_id", report_path.parent.name)).strip() or report_path.parent.name,
                "generated_at": generated_at,
                "path": str(report_path.resolve()),
                "payload": payload,
            }
        )

    reports.sort(key=lambda item: (item["generated_at"], item["run_id"]))
    return reports


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Reliability Drift Report")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{payload.get('generated_at', '')}`")
    lines.append(f"- Source checkpoint run: `{payload.get('source_checkpoint_run_id', '')}`")
    lines.append(f"- Status: `{payload.get('status', 'unknown')}`")
    lines.append("")
    lines.append("## Metric Evaluation")
    lines.append("")
    lines.append("| Metric | Latest | Threshold | Comparator | History Avg | Samples | Adverse Shift | Tolerance | Status |")
    lines.append("| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |")

    for item in payload.get("evaluations", []):
        if not isinstance(item, dict):
            continue
        history_avg = item.get("history_average")
        history_avg_str = "-" if history_avg is None else f"{float(history_avg):.6f}"
        adverse_shift = item.get("adverse_shift")
        adverse_shift_str = "-" if adverse_shift is None else f"{float(adverse_shift):.6f}"
        status = "pass"
        reasons = item.get("breach_reasons", [])
        if isinstance(reasons, list) and reasons:
            status = "+".join(str(part) for part in reasons)
        lines.append(
            f"| `{item.get('metric_id', '')}` | {float(item.get('latest_value', 0.0)):.6f} | "
            f"{float(item.get('threshold', 0.0)):.6f} | `{item.get('comparator', '')}` | {history_avg_str} | "
            f"{int(item.get('history_samples', 0))} | {adverse_shift_str} | "
            f"{float(item.get('drift_tolerance', 0.0)):.6f} | `{status}` |"
        )

    lines.append("")
    lines.append("## Breaches")
    lines.append("")

    breaches = payload.get("breaches", [])
    if isinstance(breaches, list) and breaches:
        lines.append("| Metric | Severity | Owner | Action Required | Reasons |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in breaches:
            if not isinstance(item, dict):
                continue
            reasons = item.get("reasons", [])
            reason_text = ", ".join(str(part) for part in reasons) if isinstance(reasons, list) else ""
            lines.append(
                f"| `{item.get('metric_id', '')}` | `{item.get('severity', '')}` | `{item.get('owner', '')}` | "
                f"`{str(bool(item.get('action_required', False))).lower()}` | {reason_text} |"
            )
    else:
        lines.append("No drift breaches detected.")

    lines.append("")
    lines.append("## Triage Links")
    lines.append("")
    for link in TRIAGE_LINKS:
        lines.append(f"- `{link}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate reliability drift report artifacts")
    parser.add_argument("--baseline-config", default=str(DEFAULT_BASELINE_CONFIG), help="Baseline threshold config JSON")
    parser.add_argument("--checkpoint-root", default=str(DEFAULT_CHECKPOINT_ROOT), help="Checkpoint root directory")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID, help="Checkpoint run id to evaluate")
    parser.add_argument("--history-window", type=int, default=5, help="Number of recent historical checkpoints to compare")
    parser.add_argument("--history-min-samples", type=int, default=2, help="Minimum history samples for drift detection")
    parser.add_argument("--relative-drift-threshold", type=float, default=0.05, help="Drift threshold as ratio of absolute threshold")
    parser.add_argument("--absolute-drift-threshold", type=float, default=0.01, help="Minimum absolute drift threshold")
    parser.add_argument("--fail-on-severity", choices=["sev1", "sev2", "sev3"], default="sev2", help="Minimum severity that returns non-zero with --check")
    parser.add_argument("--check", action="store_true", help="Return non-zero when actionable drift is detected")
    parser.add_argument("--simulate-drift", default="", help="Force one metric into drift breach state")
    args = parser.parse_args()

    if args.history_window < 1:
        print("error: --history-window must be >= 1")
        return 1
    if args.history_min_samples < 0:
        print("error: --history-min-samples must be >= 0")
        return 1

    baseline_path = Path(args.baseline_config).expanduser().resolve()
    checkpoint_root = Path(args.checkpoint_root).expanduser().resolve()
    run_id = args.run_id.strip() or DEFAULT_RUN_ID

    baseline = _load_json(baseline_path)
    baseline_errors = _validate_baseline(baseline)
    if baseline_errors:
        print("Reliability baseline config invalid:")
        for item in baseline_errors:
            print(f"- {item}")
        return 1

    reports = _load_checkpoint_reports(checkpoint_root)
    if not reports:
        print(f"error: no reliability checkpoint reports found under {checkpoint_root}")
        return 1

    target_report_path = checkpoint_root / run_id / "reliability-checkpoint.json"
    target_payload: Dict[str, Any] | None = None
    target_generated_at: datetime | None = None
    target_run_id = run_id

    if target_report_path.exists():
        target_payload = _load_json(target_report_path)
        raw_ts = str(target_payload.get("generated_at", "")).strip()
        if raw_ts:
            try:
                target_generated_at = _parse_iso(raw_ts)
            except ValueError:
                target_generated_at = None
        if target_generated_at is None:
            target_generated_at = datetime.fromtimestamp(target_report_path.stat().st_mtime, tz=timezone.utc)
        target_run_id = str(target_payload.get("checkpoint_id", run_id)).strip() or run_id
    elif run_id == DEFAULT_RUN_ID:
        latest = reports[-1]
        target_payload = latest["payload"]
        target_generated_at = latest["generated_at"]
        target_report_path = Path(str(latest["path"]))
        target_run_id = str(latest["run_id"])
    else:
        print(f"error: checkpoint report not found for run-id '{run_id}' at {target_report_path}")
        return 1

    assert target_payload is not None
    assert target_generated_at is not None

    metrics = target_payload.get("metrics", {})
    if not isinstance(metrics, dict):
        print(f"error: checkpoint metrics missing/invalid in {target_report_path}")
        return 1

    evaluation_lookup: Dict[str, Dict[str, Any]] = {}
    evaluations = target_payload.get("evaluations", [])
    if isinstance(evaluations, list):
        for item in evaluations:
            if not isinstance(item, dict):
                continue
            metric_id = str(item.get("metric_id", "")).strip()
            if not metric_id:
                continue
            evaluation_lookup[metric_id] = item

    thresholds = baseline.get("thresholds", {})
    assert isinstance(thresholds, dict)

    triage = baseline.get("triage", {})
    triage = triage if isinstance(triage, dict) else {}
    severity_map = triage.get("severity_by_metric", {})
    owner_by_severity = triage.get("owner_by_severity", {})
    severity_map = severity_map if isinstance(severity_map, dict) else {}
    owner_by_severity = owner_by_severity if isinstance(owner_by_severity, dict) else {}

    historical_reports = [
        item for item in reports if Path(str(item.get("path", ""))).resolve() != target_report_path.resolve()
    ]
    historical_reports = historical_reports[-args.history_window :]

    simulated_metric = str(args.simulate_drift).strip()
    metric_ids = {spec[0] for spec in METRIC_THRESHOLD_SPECS}
    if simulated_metric and simulated_metric not in metric_ids:
        print(f"error: unknown --simulate-drift metric id '{simulated_metric}'")
        return 1

    evaluation_rows: List[Dict[str, Any]] = []
    breach_rows: List[Dict[str, Any]] = []

    for metric_id, threshold_key, default_comparator in METRIC_THRESHOLD_SPECS:
        threshold = float(thresholds[threshold_key])
        latest_value = float(metrics.get(metric_id, 0.0))

        checkpoint_eval = evaluation_lookup.get(metric_id, {})
        comparator = str(checkpoint_eval.get("comparator", default_comparator)).strip() or default_comparator

        history_values: List[float] = []
        for item in historical_reports:
            payload = item.get("payload", {})
            if not isinstance(payload, dict):
                continue
            history_metrics = payload.get("metrics", {})
            if not isinstance(history_metrics, dict):
                continue
            if metric_id not in history_metrics:
                continue
            history_values.append(float(history_metrics.get(metric_id, 0.0)))

        history_samples = len(history_values)
        history_average = (sum(history_values) / history_samples) if history_samples > 0 else None

        drift_tolerance = max(abs(threshold) * args.relative_drift_threshold, args.absolute_drift_threshold)

        if simulated_metric and metric_id == simulated_metric:
            bump = max(abs(threshold) * 0.2, drift_tolerance * 2.0, 0.01)
            if comparator == ">=":
                latest_value -= bump
            elif comparator == "<=":
                latest_value += bump

        threshold_breach = not _evaluate_gate(latest_value, comparator, threshold)

        adverse_shift: float | None = None
        history_drift_breach = False
        if history_average is not None and history_samples >= args.history_min_samples:
            if comparator == ">=":
                adverse_shift = history_average - latest_value
            else:
                adverse_shift = latest_value - history_average
            history_drift_breach = adverse_shift > drift_tolerance

        breach_reasons: List[str] = []
        if threshold_breach:
            breach_reasons.append("threshold_breach")
        if history_drift_breach:
            breach_reasons.append("history_drift")

        base_severity = _severity_for_metric(metric_id, severity_map)
        if threshold_breach:
            severity = base_severity
        elif history_drift_breach:
            severity = _downgrade_severity(base_severity)
        else:
            severity = ""

        owner = ""
        action_required = False
        recommended_action = ""

        if severity:
            owner = str(owner_by_severity.get(severity, "gaia-qa-evaluator")).strip() or "gaia-qa-evaluator"
            action_required = _severity_action_required(severity, args.fail_on_severity)
            if action_required:
                recommended_action = "Open/update incident record and follow infrastructure/reliability-triage-workflow.md"
            else:
                recommended_action = "Record drift and monitor next reliability checkpoint"

        row = {
            "metric_id": metric_id,
            "latest_value": latest_value,
            "comparator": comparator,
            "threshold": threshold,
            "history_samples": history_samples,
            "history_average": history_average,
            "adverse_shift": adverse_shift,
            "drift_tolerance": drift_tolerance,
            "threshold_breach": threshold_breach,
            "history_drift_breach": history_drift_breach,
            "breach_reasons": breach_reasons,
            "severity": severity,
            "owner": owner,
            "action_required": action_required,
            "recommended_action": recommended_action,
        }
        evaluation_rows.append(row)

        if breach_reasons:
            breach_rows.append(
                {
                    "metric_id": metric_id,
                    "severity": severity,
                    "owner": owner,
                    "action_required": action_required,
                    "reasons": breach_reasons,
                    "latest_value": latest_value,
                    "threshold": threshold,
                    "comparator": comparator,
                    "history_average": history_average,
                    "adverse_shift": adverse_shift,
                    "drift_tolerance": drift_tolerance,
                    "recommended_action": recommended_action,
                }
            )

    actionable_breaches = [item for item in breach_rows if bool(item.get("action_required", False))]

    if actionable_breaches:
        status = "fail"
    elif breach_rows:
        status = "warn"
    else:
        status = "pass"

    output_dir = checkpoint_root / run_id
    report_json = output_dir / "reliability-drift-report.json"
    report_md = output_dir / "reliability-drift-report.md"

    payload: Dict[str, Any] = {
        "schema_version": 1,
        "generated_at": _iso_now(),
        "status": status,
        "baseline_date_utc": str(baseline.get("baseline_date_utc", "")),
        "baseline_commit": str(baseline.get("baseline_commit", "")),
        "source_checkpoint_run_id": target_run_id,
        "source_checkpoint_generated_at": target_generated_at.isoformat(),
        "source_checkpoint_path": str(target_report_path),
        "history_window": args.history_window,
        "history_min_samples": args.history_min_samples,
        "relative_drift_threshold": args.relative_drift_threshold,
        "absolute_drift_threshold": args.absolute_drift_threshold,
        "fail_on_severity": args.fail_on_severity,
        "history_checkpoint_paths": [str(item.get("path", "")) for item in historical_reports],
        "evaluations": evaluation_rows,
        "breaches": breach_rows,
        "breach_count": len(breach_rows),
        "actionable_breach_count": len(actionable_breaches),
        "triage_links": TRIAGE_LINKS,
    }
    if simulated_metric:
        payload["simulated_drift_metric"] = simulated_metric

    _write_json(report_json, payload)
    _write_text(report_md, _render_markdown(payload))

    print(
        json.dumps(
            {
                "status": status,
                "report_json": str(report_json),
                "report_md": str(report_md),
                "breach_count": len(breach_rows),
                "actionable_breach_count": len(actionable_breaches),
            },
            indent=2,
            sort_keys=True,
        )
    )

    if args.check and actionable_breaches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
