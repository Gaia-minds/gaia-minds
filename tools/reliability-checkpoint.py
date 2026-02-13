#!/usr/bin/env python3
"""Generate a reproducible Phase 3 reliability checkpoint report."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_CONFIG = REPO_ROOT / "assistant" / "reliability-baseline-phase3.json"
DEFAULT_BENCHMARK_RESULTS = REPO_ROOT / "assistant" / "benchmark-results.json"
DEFAULT_BENCHMARK_HISTORY = REPO_ROOT / "assistant" / "benchmark-trend-history.json"
DEFAULT_OUTPUT_ROOT = Path("/tmp/gaia-reliability-checkpoints")
DEFAULT_UAT_MANIFEST = REPO_ROOT / "assistant" / "uat-scenarios.json"
DEFAULT_MEMORY_FIXTURES = REPO_ROOT / "assistant" / "memory-quality-fixtures.json"


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


def _run_command(label: str, command: List[str]) -> None:
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"{label} failed (exit={proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def _validate_baseline(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not str(payload.get("baseline_date_utc", "")).strip():
        errors.append("baseline_date_utc is required")
    if not str(payload.get("baseline_commit", "")).strip():
        errors.append("baseline_commit is required")

    thresholds = payload.get("thresholds")
    if not isinstance(thresholds, dict):
        errors.append("thresholds must be an object")
        return errors

    required_threshold_keys = (
        "benchmark_pass_rate_min",
        "benchmark_failure_rate_max",
        "uat_pass_rate_min",
        "uat_failure_rate_max",
        "memory_quality_pass_rate_min",
        "memory_quality_p95_latency_ms_max",
        "consolidated_failure_rate_max",
        "mttr_proxy_hours_max",
    )
    for key in required_threshold_keys:
        if key not in thresholds:
            errors.append(f"thresholds.{key} is required")
            continue
        value = thresholds.get(key)
        if not isinstance(value, (int, float)):
            errors.append(f"thresholds.{key} must be numeric")

    triage = payload.get("triage")
    if not isinstance(triage, dict):
        errors.append("triage must be an object")
    else:
        owners = triage.get("owner_by_severity")
        if not isinstance(owners, dict):
            errors.append("triage.owner_by_severity must be an object")

    return errors


def _safe_rate(passed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return passed / total


def _collect_benchmark_metrics(payload: Dict[str, Any]) -> Dict[str, float]:
    total = int(payload.get("total", 0))
    passed = int(payload.get("passed", 0))
    failed = int(payload.get("failed", 0))
    return {
        "benchmark_total": float(total),
        "benchmark_passed": float(passed),
        "benchmark_failed": float(failed),
        "benchmark_pass_rate": _safe_rate(passed, total),
        "benchmark_failure_rate": _safe_rate(failed, total),
    }


def _collect_uat_metrics(payload: Dict[str, Any]) -> Dict[str, float]:
    total = int(payload.get("total", 0))
    passed = int(payload.get("passed", 0))
    failed = int(payload.get("failed", 0))
    duration_ms = float(payload.get("duration_ms", 0.0))
    return {
        "uat_total": float(total),
        "uat_passed": float(passed),
        "uat_failed": float(failed),
        "uat_pass_rate": _safe_rate(passed, total),
        "uat_failure_rate": _safe_rate(failed, total),
        "uat_duration_ms": duration_ms,
    }


def _collect_memory_quality_metrics(payload: Dict[str, Any]) -> Dict[str, float]:
    thresholds = payload.get("thresholds", {})
    summary = payload.get("summary", {})
    retrieval_cases = payload.get("retrieval_cases", [])
    poisoning_cases = payload.get("poisoning_cases", [])
    leakage_cases = payload.get("leakage_cases", [])

    retrieval_cases = retrieval_cases if isinstance(retrieval_cases, list) else []
    poisoning_cases = poisoning_cases if isinstance(poisoning_cases, list) else []
    leakage_cases = leakage_cases if isinstance(leakage_cases, list) else []

    recall_min = float(thresholds.get("recall_at_k_min", 0.0)) if isinstance(thresholds, dict) else 0.0
    precision_min = float(thresholds.get("precision_at_k_min", 0.0)) if isinstance(thresholds, dict) else 0.0
    faithfulness_min = float(thresholds.get("faithfulness_at_1_min", 0.0)) if isinstance(thresholds, dict) else 0.0

    retrieval_passed = 0
    for item in retrieval_cases:
        if not isinstance(item, dict):
            continue
        recall = float(item.get("recall_at_k", 0.0))
        precision = float(item.get("precision_at_k", 0.0))
        faithfulness = float(item.get("faithfulness_at_1", 0.0))
        if recall >= recall_min and precision >= precision_min and faithfulness >= faithfulness_min:
            retrieval_passed += 1

    poisoning_passed = sum(1 for item in poisoning_cases if isinstance(item, dict) and bool(item.get("pass", False)))
    leakage_passed = sum(1 for item in leakage_cases if isinstance(item, dict) and bool(item.get("pass", False)))

    total_cases = len(retrieval_cases) + len(poisoning_cases) + len(leakage_cases)
    passed_cases = retrieval_passed + poisoning_passed + leakage_passed
    failed_cases = total_cases - passed_cases

    return {
        "memory_quality_total_cases": float(total_cases),
        "memory_quality_passed_cases": float(passed_cases),
        "memory_quality_failed_cases": float(failed_cases),
        "memory_quality_pass_rate": _safe_rate(passed_cases, total_cases),
        "memory_quality_p95_latency_ms": float(summary.get("p95_latency_ms", 0.0))
        if isinstance(summary, dict)
        else 0.0,
        "memory_quality_status_pass": 1.0 if str(payload.get("status", "")).strip().lower() == "pass" else 0.0,
    }


def _compute_mttr_proxy_hours(history_payload: Dict[str, Any]) -> float:
    entries = history_payload.get("entries", [])
    if not isinstance(entries, list):
        return 0.0

    parsed: List[Tuple[datetime, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        ts_raw = str(item.get("timestamp_utc", "")).strip()
        status = str(item.get("status", "")).strip().lower()
        if not ts_raw or not status:
            continue
        try:
            ts = _parse_iso(ts_raw)
        except ValueError:
            continue
        parsed.append((ts, status))
    parsed.sort(key=lambda pair: pair[0])

    open_failure: datetime | None = None
    recoveries_hours: List[float] = []
    for ts, status in parsed:
        if status == "fail":
            open_failure = ts
            continue
        if status == "pass" and open_failure is not None:
            delta = ts - open_failure
            recoveries_hours.append(delta.total_seconds() / 3600.0)
            open_failure = None

    if recoveries_hours:
        return round(recoveries_hours[-1], 3)
    if open_failure is not None:
        # Open unresolved failure in trend history => max-risk proxy.
        return 9999.0
    return 0.0


def _severity_for_metric(metric_id: str, severity_map: Dict[str, str]) -> str:
    configured = str(severity_map.get(metric_id, "")).strip().lower()
    if configured in {"sev1", "sev2", "sev3"}:
        return configured
    if metric_id in {"benchmark_pass_rate", "uat_pass_rate", "consolidated_failure_rate"}:
        return "sev1"
    if metric_id in {"benchmark_failure_rate", "uat_failure_rate", "memory_quality_p95_latency_ms", "mttr_proxy_hours"}:
        return "sev2"
    return "sev3"


def _evaluate_gate(metric_id: str, value: float, comparator: str, threshold: float) -> bool:
    if comparator == ">=":
        return value >= threshold
    if comparator == "<=":
        return value <= threshold
    raise ValueError(f"unsupported comparator: {comparator}")


def _render_summary_markdown(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Reliability Checkpoint")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{payload.get('generated_at', '')}`")
    lines.append(f"- Baseline date (UTC): `{payload.get('baseline_date_utc', '')}`")
    lines.append(f"- Baseline commit: `{payload.get('baseline_commit', '')}`")
    lines.append(f"- Status: `{payload.get('status', 'unknown')}`")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | Value | Threshold | Comparator | Status |")
    lines.append("| --- | ---: | ---: | --- | --- |")
    for item in payload.get("evaluations", []):
        if not isinstance(item, dict):
            continue
        status = "pass" if bool(item.get("passed", False)) else "fail"
        lines.append(
            f"| `{item.get('metric_id', '')}` | {float(item.get('value', 0.0)):.6f} | "
            f"{float(item.get('threshold', 0.0)):.6f} | `{item.get('comparator', '')}` | `{status}` |"
        )
    lines.append("")

    breaches = payload.get("breaches", [])
    if isinstance(breaches, list) and breaches:
        lines.append("## Threshold Breaches")
        lines.append("")
        lines.append("| Metric | Severity | Owner | Reason |")
        lines.append("| --- | --- | --- | --- |")
        for item in breaches:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"| `{item.get('metric_id', '')}` | `{item.get('severity', '')}` | "
                f"`{item.get('owner', '')}` | {item.get('reason', '')} |"
            )
    else:
        lines.append("## Threshold Breaches")
        lines.append("")
        lines.append("No threshold breaches detected.")

    lines.append("")
    lines.append("## Triage Links")
    lines.append("")
    lines.append("- `infrastructure/reliability-triage-workflow.md`")
    lines.append("- `docs/incidents/README.md`")
    lines.append("- `docs/incidents/postmortem-template.md`")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 3 reliability checkpoint artifacts")
    parser.add_argument("--baseline-config", default=str(DEFAULT_BASELINE_CONFIG), help="Baseline threshold config JSON")
    parser.add_argument("--benchmark-results", default=str(DEFAULT_BENCHMARK_RESULTS), help="Benchmark results JSON")
    parser.add_argument("--benchmark-history", default=str(DEFAULT_BENCHMARK_HISTORY), help="Benchmark trend history JSON")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Checkpoint output root directory")
    parser.add_argument("--run-id", default="latest", help="Checkpoint run id directory")
    parser.add_argument("--uat-results", default="", help="UAT results JSON path override")
    parser.add_argument("--memory-quality-results", default="", help="Memory quality results JSON path override")
    parser.add_argument("--skip-uat", action="store_true", help="Skip running UAT runner command")
    parser.add_argument("--skip-memory-quality", action="store_true", help="Skip running memory quality command")
    parser.add_argument("--check", action="store_true", help="Return non-zero when any threshold breaches occur")
    parser.add_argument("--simulate-breach", default="", help="Force one metric id into breach state for triage validation")
    args = parser.parse_args()

    baseline_path = Path(args.baseline_config).expanduser().resolve()
    benchmark_results_path = Path(args.benchmark_results).expanduser().resolve()
    benchmark_history_path = Path(args.benchmark_history).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    checkpoint_dir = output_root / args.run_id.strip()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    uat_results_path = (
        Path(args.uat_results).expanduser().resolve()
        if args.uat_results
        else checkpoint_dir / "uat-results.json"
    )
    memory_quality_results_path = (
        Path(args.memory_quality_results).expanduser().resolve()
        if args.memory_quality_results
        else checkpoint_dir / "memory-quality-results.json"
    )

    baseline = _load_json(baseline_path)
    baseline_errors = _validate_baseline(baseline)
    if baseline_errors:
        print("Reliability baseline config invalid:")
        for item in baseline_errors:
            print(f"- {item}")
        return 1

    if not args.skip_uat:
        _run_command(
            "uat-runner",
            [
                "python3",
                "./tools/uat-runner.py",
                "--manifest",
                str(DEFAULT_UAT_MANIFEST),
                "--json-out",
                str(uat_results_path),
                "--artifacts-dir",
                str(checkpoint_dir / "uat-artifacts"),
            ],
        )
    elif not uat_results_path.exists():
        print(f"error: --skip-uat set but results path does not exist: {uat_results_path}")
        return 1

    if not args.skip_memory_quality:
        _run_command(
            "memory-quality-matrix",
            [
                "python3",
                "./tools/memory-quality-matrix.py",
                "--fixtures",
                str(DEFAULT_MEMORY_FIXTURES),
                "--json-out",
                str(memory_quality_results_path),
            ],
        )
    elif not memory_quality_results_path.exists():
        print(f"error: --skip-memory-quality set but results path does not exist: {memory_quality_results_path}")
        return 1

    benchmark_results = _load_json(benchmark_results_path)
    benchmark_history = _load_json(benchmark_history_path)
    uat_results = _load_json(uat_results_path)
    memory_quality_results = _load_json(memory_quality_results_path)

    metrics: Dict[str, float] = {}
    metrics.update(_collect_benchmark_metrics(benchmark_results))
    metrics.update(_collect_uat_metrics(uat_results))
    metrics.update(_collect_memory_quality_metrics(memory_quality_results))

    total_checks = int(metrics["benchmark_total"] + metrics["uat_total"] + metrics["memory_quality_total_cases"])
    total_failed = int(metrics["benchmark_failed"] + metrics["uat_failed"] + metrics["memory_quality_failed_cases"])
    metrics["consolidated_failure_rate"] = _safe_rate(total_failed, total_checks)
    metrics["mttr_proxy_hours"] = _compute_mttr_proxy_hours(benchmark_history)

    thresholds = baseline["thresholds"]
    assert isinstance(thresholds, dict)
    gate_specs = [
        ("benchmark_pass_rate", ">=", float(thresholds["benchmark_pass_rate_min"])),
        ("benchmark_failure_rate", "<=", float(thresholds["benchmark_failure_rate_max"])),
        ("uat_pass_rate", ">=", float(thresholds["uat_pass_rate_min"])),
        ("uat_failure_rate", "<=", float(thresholds["uat_failure_rate_max"])),
        ("memory_quality_pass_rate", ">=", float(thresholds["memory_quality_pass_rate_min"])),
        ("memory_quality_p95_latency_ms", "<=", float(thresholds["memory_quality_p95_latency_ms_max"])),
        ("consolidated_failure_rate", "<=", float(thresholds["consolidated_failure_rate_max"])),
        ("mttr_proxy_hours", "<=", float(thresholds["mttr_proxy_hours_max"])),
    ]

    simulated = str(args.simulate_breach).strip()
    if simulated:
        metric_ids = {item[0] for item in gate_specs}
        if simulated not in metric_ids:
            print(f"error: unknown --simulate-breach metric id '{simulated}'")
            return 1

    triage = baseline.get("triage", {})
    triage = triage if isinstance(triage, dict) else {}
    severity_map = triage.get("severity_by_metric", {})
    owner_by_severity = triage.get("owner_by_severity", {})
    severity_map = severity_map if isinstance(severity_map, dict) else {}
    owner_by_severity = owner_by_severity if isinstance(owner_by_severity, dict) else {}

    evaluations: List[Dict[str, Any]] = []
    breaches: List[Dict[str, Any]] = []
    for metric_id, comparator, threshold in gate_specs:
        value = float(metrics.get(metric_id, 0.0))

        if simulated and metric_id == simulated:
            bump = max(abs(threshold) * 0.2, 0.01)
            if comparator == "<=":
                value = threshold + bump
            else:
                value = threshold - bump
            metrics[metric_id] = value

        passed = _evaluate_gate(metric_id, value, comparator, threshold)
        evaluation = {
            "metric_id": metric_id,
            "value": value,
            "comparator": comparator,
            "threshold": threshold,
            "passed": passed,
        }
        evaluations.append(evaluation)

        if not passed:
            severity = _severity_for_metric(metric_id, severity_map)
            owner = str(owner_by_severity.get(severity, "gaia-qa-evaluator")).strip() or "gaia-qa-evaluator"
            breaches.append(
                {
                    "metric_id": metric_id,
                    "severity": severity,
                    "owner": owner,
                    "reason": f"{metric_id} value={value:.6f} {comparator} threshold={threshold:.6f} failed",
                    "recommended_action": "Open/update incident issue and follow reliability triage workflow",
                }
            )

    status = "pass" if not breaches else "fail"
    checkpoint_payload: Dict[str, Any] = {
        "schema_version": 1,
        "generated_at": _iso_now(),
        "checkpoint_id": args.run_id.strip(),
        "status": status,
        "baseline_date_utc": str(baseline.get("baseline_date_utc", "")),
        "baseline_commit": str(baseline.get("baseline_commit", "")),
        "thresholds": thresholds,
        "metrics": metrics,
        "evaluations": evaluations,
        "breaches": breaches,
        "sources": {
            "baseline_config": str(baseline_path),
            "benchmark_results": str(benchmark_results_path),
            "benchmark_history": str(benchmark_history_path),
            "uat_results": str(uat_results_path),
            "memory_quality_results": str(memory_quality_results_path),
        },
        "triage_links": [
            "infrastructure/reliability-triage-workflow.md",
            "docs/incidents/README.md",
            "docs/incidents/postmortem-template.md",
        ],
    }
    if simulated:
        checkpoint_payload["simulated_breach_metric"] = simulated

    report_json = checkpoint_dir / "reliability-checkpoint.json"
    report_md = checkpoint_dir / "reliability-checkpoint.md"
    _write_json(report_json, checkpoint_payload)
    _write_text(report_md, _render_summary_markdown(checkpoint_payload))

    summary = {
        "status": status,
        "breach_count": len(breaches),
        "report_json": str(report_json),
        "report_md": str(report_md),
        "checkpoint_id": args.run_id.strip(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if args.check and breaches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
