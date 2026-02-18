#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_PATH="${ROOT_DIR}/assistant/delegation-qa-matrix.json"
TMP_ROOT="$(mktemp -d)"
TRACE_ROOT="${TMP_ROOT}/traces"

cleanup() {
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

export ROOT_DIR
export FIXTURES_PATH
export TRACE_ROOT

python3 - <<'PY'
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
fixtures_path = Path(os.environ["FIXTURES_PATH"])
trace_root = Path(os.environ["TRACE_ROOT"])

fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
cases = fixtures.get("cases", [])
if not isinstance(cases, list) or not cases:
    raise SystemExit("delegation QA matrix fixtures missing cases")

required_trace_types = [
    str(t).strip() for t in fixtures.get("required_trace_types", [])
]

tools_dir = root / "tools"
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))
module_path = tools_dir / "gaia-assistant.py"
spec = importlib.util.spec_from_file_location("gaia_assistant_runtime", module_path)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load gaia-assistant runtime module")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

failures: list[str] = []
case_summaries: list[dict[str, object]] = []

# Aggregate metrics for rollout gate.
# eligible_dispatch_tasks: tasks where runtime was enabled AND contract decision=delegate.
# dispatched_tasks: tasks that were actually execution_mode=delegated.
# These metrics isolate positive-path performance from deliberate negative-path cases.
agg_eligible_dispatch_tasks = 0
agg_dispatched_tasks = 0
seen_trace_types: set[str] = set()
passed_cases = 0


for case in cases:
    if not isinstance(case, dict):
        failures.append("fixture entry is not an object")
        continue

    case_id = str(case.get("id", "")).strip() or "unknown"
    cfg = case.get("cfg", {})
    case_input = case.get("input", {})
    expect = case.get("expect", {})

    if not isinstance(cfg, dict) or not isinstance(case_input, dict) or not isinstance(expect, dict):
        failures.append(f"{case_id}: fixture cfg/input/expect must be objects")
        continue

    correlation_id = str(case_input.get("correlation_id", "")).strip() or f"qa:{case_id}"
    trace_dir = trace_root / case_id

    result = module.execute_coordinator_delegation_v1(
        cfg,
        case_input,
        trace_dir=trace_dir,
        correlation_id=correlation_id,
    )

    case_failures: list[str] = []

    runtime_gate = result.get("runtime_gate", {})
    expected_runtime_enabled = bool(expect.get("runtime_enabled", False))
    actual_runtime_enabled = bool(runtime_gate.get("enabled", False) if isinstance(runtime_gate, dict) else False)
    if actual_runtime_enabled != expected_runtime_enabled:
        case_failures.append(
            f"runtime_enabled mismatch expected={expected_runtime_enabled} actual={actual_runtime_enabled}"
        )

    expected_task_count = int(expect.get("task_count", 0) or 0)
    actual_task_count = int(result.get("task_count", -1) or -1)
    if actual_task_count != expected_task_count:
        case_failures.append(
            f"task_count mismatch expected={expected_task_count} actual={actual_task_count}"
        )

    tasks = result.get("tasks", [])
    if not isinstance(tasks, list):
        case_failures.append("tasks payload is not a list")
        tasks = []

    actual_modes = [str(t.get("execution_mode", "")).strip().lower() for t in tasks if isinstance(t, dict)]
    expected_modes = [str(m).strip().lower() for m in expect.get("execution_modes", [])]
    if expected_modes and actual_modes != expected_modes:
        case_failures.append(f"execution_modes mismatch expected={expected_modes} actual={actual_modes}")

    actual_decisions = [str(t.get("decision", "")).strip().lower() for t in tasks if isinstance(t, dict)]
    expected_decisions = [str(d).strip().lower() for d in expect.get("decisions", [])]
    if expected_decisions and actual_decisions != expected_decisions:
        case_failures.append(f"decisions mismatch expected={expected_decisions} actual={actual_decisions}")

    actual_statuses: list[str] = []
    for t in tasks:
        if not isinstance(t, dict):
            actual_statuses.append("")
            continue
        envelope = t.get("result_envelope", {})
        actual_statuses.append(str(envelope.get("status", "")).strip().lower() if isinstance(envelope, dict) else "")
    expected_statuses = [str(s).strip().lower() for s in expect.get("result_statuses", [])]
    if expected_statuses and actual_statuses != expected_statuses:
        case_failures.append(f"result_status mismatch expected={expected_statuses} actual={actual_statuses}")

    synthesis = result.get("synthesis", {})
    synthesis = synthesis if isinstance(synthesis, dict) else {}
    expected_synthesis = str(expect.get("synthesis_status", "")).strip().lower()
    actual_synthesis = str(synthesis.get("status", "")).strip().lower()
    if expected_synthesis and actual_synthesis != expected_synthesis:
        case_failures.append(f"synthesis_status mismatch expected={expected_synthesis} actual={actual_synthesis}")

    expected_fallback_count = int(expect.get("fallback_count", -1))
    if expected_fallback_count >= 0:
        actual_fallback_count = int(synthesis.get("fallback_count", -1))
        if actual_fallback_count != expected_fallback_count:
            case_failures.append(
                f"fallback_count mismatch expected={expected_fallback_count} actual={actual_fallback_count}"
            )

    expected_deferred_count = int(expect.get("deferred_count", -1))
    if expected_deferred_count >= 0:
        actual_deferred_count = int(synthesis.get("deferred_count", -1))
        if actual_deferred_count != expected_deferred_count:
            case_failures.append(
                f"deferred_count mismatch expected={expected_deferred_count} actual={actual_deferred_count}"
            )

    traces = module._read_action_traces(trace_dir)
    filtered = [
        item for item in traces
        if isinstance(item, dict)
        and str(item.get("metadata", {}).get("correlation_id", "")).strip() == correlation_id
    ]
    trace_counts: dict[str, int] = {}
    for item in filtered:
        action_type = str(item.get("action_type", "")).strip()
        trace_counts[action_type] = trace_counts.get(action_type, 0) + 1
        seen_trace_types.add(action_type)

    for required_trace in expect.get("required_traces", []):
        token = str(required_trace).strip()
        if trace_counts.get(token, 0) == 0:
            case_failures.append(f"required trace type missing: {token}")

    for absent_trace in expect.get("absent_traces", []):
        token = str(absent_trace).strip()
        if trace_counts.get(token, 0) > 0:
            case_failures.append(f"expected absent trace type was present: {token}")

    # Accumulate eligible dispatch metrics.
    # eligible: runtime enabled AND contract decision was delegate.
    # dispatched: execution_mode was actually delegated.
    for t in tasks:
        if not isinstance(t, dict):
            continue
        task_runtime_enabled = actual_runtime_enabled
        task_decision = str(t.get("decision", "")).strip().lower()
        task_mode = str(t.get("execution_mode", "")).strip().lower()
        if task_runtime_enabled and task_decision == "delegate":
            agg_eligible_dispatch_tasks += 1
            if task_mode == "delegated":
                agg_dispatched_tasks += 1

    case_ok = len(case_failures) == 0
    if case_ok:
        passed_cases += 1
    else:
        for f in case_failures:
            failures.append(f"{case_id}: {f}")

    case_summaries.append(
        {
            "case_id": case_id,
            "ok": case_ok,
            "runtime_enabled": actual_runtime_enabled,
            "execution_modes": actual_modes,
            "decisions": actual_decisions,
            "synthesis_status": actual_synthesis,
            "trace_counts": trace_counts,
        }
    )

total_cases = len(cases)

trace_complete = all(t in seen_trace_types for t in required_trace_types)
missing_trace_types = [t for t in required_trace_types if t not in seen_trace_types]

qa_run = {
    "total_cases": total_cases,
    "passed_cases": passed_cases,
    "failed_cases": total_cases - passed_cases,
    "eligible_dispatch_tasks": agg_eligible_dispatch_tasks,
    "dispatched_tasks": agg_dispatched_tasks,
    "trace_complete": trace_complete,
}

gate_result = module.evaluate_delegation_rollout_gate_v1(qa_run)

if failures:
    print("delegation QA matrix case failures:")
    for item in failures:
        print(f"- {item}")

if missing_trace_types:
    print(f"missing required trace types: {missing_trace_types}")

gate_status = str(gate_result.get("gate_status", "fail")).strip().lower()
print(
    json.dumps(
        {
            "suite": "delegation-qa-matrix-v1",
            "qa_run": qa_run,
            "gate_result": gate_result,
            "case_summaries": case_summaries,
        },
        indent=2,
    )
)

if failures or gate_status != "pass":
    raise SystemExit(1)
PY
