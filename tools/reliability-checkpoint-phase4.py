#!/usr/bin/env python3
"""Phase 4 delegation reliability checkpoint.

Runs the delegation QA matrix, compares against the Phase 4 baseline
thresholds, and reports pass/fail with metrics.

Usage:
    python3 tools/reliability-checkpoint-phase4.py [--check] [--json]

Options:
    --check   Exit non-zero if any threshold is breached.
    --json    Emit only JSON output (no human-readable prefix).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = REPO_ROOT / "assistant" / "reliability-baseline-phase4.json"
DEFAULT_FIXTURES = REPO_ROOT / "assistant" / "delegation-qa-matrix.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_runtime() -> Any:
    module_path = REPO_ROOT / "tools" / "gaia-assistant.py"
    spec = importlib.util.spec_from_file_location("gaia_assistant_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load gaia-assistant runtime module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_delegation_qa(module: Any, fixtures: Dict[str, Any]) -> Dict[str, Any]:
    """Run all QA matrix cases and aggregate metrics."""
    cases: List[Dict[str, Any]] = fixtures.get("cases", [])
    required_trace_types: List[str] = [
        str(t).strip() for t in fixtures.get("required_trace_types", [])
    ]

    passed_cases = 0
    agg_eligible_dispatch_tasks = 0
    agg_dispatched_tasks = 0
    seen_trace_types: set[str] = set()
    case_summaries: List[Dict[str, Any]] = []
    positive_path_fallback_count = 0
    positive_path_deferred_count = 0
    positive_path_task_count = 0

    with tempfile.TemporaryDirectory() as tmp:
        trace_root = Path(tmp) / "traces"

        for case in cases:
            if not isinstance(case, dict):
                continue
            case_id = str(case.get("id", "unknown")).strip()
            cfg = case.get("cfg", {})
            case_input = case.get("input", {})
            expect = case.get("expect", {})
            correlation_id = str(case_input.get("correlation_id", f"qa:{case_id}")).strip()
            trace_dir = trace_root / case_id

            result = module.execute_coordinator_delegation_v1(
                cfg, case_input, trace_dir=trace_dir, correlation_id=correlation_id
            )

            runtime_gate = result.get("runtime_gate", {})
            actual_runtime_enabled = bool(
                runtime_gate.get("enabled", False) if isinstance(runtime_gate, dict) else False
            )
            tasks: List[Dict[str, Any]] = result.get("tasks", [])
            tasks = tasks if isinstance(tasks, list) else []

            synthesis = result.get("synthesis", {})
            synthesis = synthesis if isinstance(synthesis, dict) else {}

            # Collect traces
            traces = module._read_action_traces(trace_dir)
            filtered = [
                item for item in traces
                if isinstance(item, dict)
                and str(item.get("metadata", {}).get("correlation_id", "")).strip() == correlation_id
            ]
            trace_counts: Dict[str, int] = {}
            for item in filtered:
                action_type = str(item.get("action_type", "")).strip()
                trace_counts[action_type] = trace_counts.get(action_type, 0) + 1
                seen_trace_types.add(action_type)

            # Case pass/fail based on expected vs actual
            case_ok = True
            if bool(expect.get("runtime_enabled", False)) != actual_runtime_enabled:
                case_ok = False
            actual_modes = [str(t.get("execution_mode", "")).strip().lower() for t in tasks if isinstance(t, dict)]
            expected_modes = [str(m).strip().lower() for m in expect.get("execution_modes", [])]
            if expected_modes and actual_modes != expected_modes:
                case_ok = False
            actual_decisions = [str(t.get("decision", "")).strip().lower() for t in tasks if isinstance(t, dict)]
            expected_decisions = [str(d).strip().lower() for d in expect.get("decisions", [])]
            if expected_decisions and actual_decisions != expected_decisions:
                case_ok = False
            expected_synthesis = str(expect.get("synthesis_status", "")).strip().lower()
            actual_synthesis = str(synthesis.get("status", "")).strip().lower()
            if expected_synthesis and actual_synthesis != expected_synthesis:
                case_ok = False
            for req_trace in expect.get("required_traces", []):
                if trace_counts.get(str(req_trace).strip(), 0) == 0:
                    case_ok = False
            for absent_trace in expect.get("absent_traces", []):
                if trace_counts.get(str(absent_trace).strip(), 0) > 0:
                    case_ok = False

            if case_ok:
                passed_cases += 1

            # Aggregate dispatch metrics (positive-path only)
            for t in tasks:
                if not isinstance(t, dict):
                    continue
                decision = str(t.get("decision", "")).strip().lower()
                mode = str(t.get("execution_mode", "")).strip().lower()
                if actual_runtime_enabled and decision == "delegate":
                    agg_eligible_dispatch_tasks += 1
                    if mode == "delegated":
                        agg_dispatched_tasks += 1
                    else:
                        positive_path_fallback_count += 1
                    positive_path_task_count += 1
                    if mode == "defer":
                        positive_path_deferred_count += 1

            case_summaries.append({
                "case_id": case_id,
                "ok": case_ok,
                "runtime_enabled": actual_runtime_enabled,
                "execution_modes": actual_modes,
                "decisions": actual_decisions,
                "synthesis_status": actual_synthesis,
            })

    total_cases = len(cases)
    qa_pass_rate = passed_cases / total_cases if total_cases > 0 else 0.0
    dispatch_success_rate = (
        agg_dispatched_tasks / agg_eligible_dispatch_tasks
        if agg_eligible_dispatch_tasks > 0
        else 1.0
    )
    trace_complete = all(t in seen_trace_types for t in required_trace_types)
    positive_path_fallback_rate = (
        positive_path_fallback_count / positive_path_task_count
        if positive_path_task_count > 0 else 0.0
    )
    positive_path_deferred_rate = (
        positive_path_deferred_count / positive_path_task_count
        if positive_path_task_count > 0 else 0.0
    )

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": total_cases - passed_cases,
        "qa_pass_rate": round(qa_pass_rate, 4),
        "eligible_dispatch_tasks": agg_eligible_dispatch_tasks,
        "dispatched_tasks": agg_dispatched_tasks,
        "dispatch_success_rate": round(dispatch_success_rate, 4),
        "trace_complete": trace_complete,
        "positive_path_fallback_rate": round(positive_path_fallback_rate, 4),
        "positive_path_deferred_rate": round(positive_path_deferred_rate, 4),
        "case_summaries": case_summaries,
    }


def _evaluate(metrics: Dict[str, Any], thresholds: Dict[str, Any]) -> List[Dict[str, Any]]:
    breaches: List[Dict[str, Any]] = []

    checks = [
        ("qa_pass_rate", ">=", float(thresholds.get("qa_pass_rate_min", 0.95))),
        ("dispatch_success_rate", ">=", float(thresholds.get("dispatch_success_rate_min", 0.90))),
        ("positive_path_fallback_rate", "<=", float(thresholds.get("fallback_rate_positive_path_max", 0.10))),
        ("positive_path_deferred_rate", "<=", float(thresholds.get("deferred_rate_positive_path_max", 0.10))),
    ]
    for metric_id, comparator, threshold in checks:
        value = float(metrics.get(metric_id, 0.0))
        if comparator == ">=" and value < threshold:
            breaches.append({"metric_id": metric_id, "required": threshold, "observed": value, "comparator": comparator})
        elif comparator == "<=" and value > threshold:
            breaches.append({"metric_id": metric_id, "required": threshold, "observed": value, "comparator": comparator})

    if not bool(metrics.get("trace_complete", False)):
        breaches.append({"metric_id": "trace_complete", "required": True, "observed": False, "comparator": "=="})

    return breaches


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 delegation reliability checkpoint")
    parser.add_argument("--check", action="store_true", help="Exit non-zero on any threshold breach")
    parser.add_argument("--json", action="store_true", dest="json_only", help="JSON-only output")
    parser.add_argument(
        "--baseline", default=str(DEFAULT_BASELINE), help="Path to reliability-baseline-phase4.json"
    )
    parser.add_argument(
        "--fixtures", default=str(DEFAULT_FIXTURES), help="Path to delegation-qa-matrix.json"
    )
    args = parser.parse_args()

    baseline = _load_json(Path(args.baseline))
    fixtures = _load_json(Path(args.fixtures))
    thresholds = baseline.get("thresholds", {})

    module = _load_runtime()
    metrics = _run_delegation_qa(module, fixtures)

    breaches = _evaluate(metrics, thresholds)
    gate_status = "pass" if not breaches else "fail"

    report = {
        "schema_version": 1,
        "generated_at": _iso_now(),
        "suite": "delegation-reliability-checkpoint-phase4",
        "baseline_date_utc": baseline.get("baseline_date_utc", ""),
        "baseline_commit": baseline.get("baseline_commit", ""),
        "gate_status": gate_status,
        "metrics": {k: v for k, v in metrics.items() if k != "case_summaries"},
        "breaches": breaches,
        "case_summaries": metrics.get("case_summaries", []),
    }

    if args.json_only:
        print(json.dumps(report, indent=2))
    else:
        status_label = "PASS" if gate_status == "pass" else "FAIL"
        print(f"delegation reliability checkpoint: {status_label}")
        print(f"  qa_pass_rate:            {metrics['qa_pass_rate']:.2%}")
        print(f"  dispatch_success_rate:   {metrics['dispatch_success_rate']:.2%}")
        print(f"  trace_complete:          {metrics['trace_complete']}")
        print(f"  positive_path_fallback:  {metrics['positive_path_fallback_rate']:.2%}")
        print(f"  positive_path_deferred:  {metrics['positive_path_deferred_rate']:.2%}")
        if breaches:
            print("  breaches:")
            for b in breaches:
                print(f"    - {b['metric_id']}: observed={b['observed']} {b['comparator']} required={b['required']}")

    if args.check and breaches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
