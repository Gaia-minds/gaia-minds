#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_PATH="${ROOT_DIR}/assistant/delegated-execution-fixtures.json"
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
    raise SystemExit("delegated execution fixtures missing cases")

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
summary: list[dict[str, object]] = []


def stable_result(payload: dict[str, object]) -> dict[str, object]:
    clone = copy.deepcopy(payload)
    if isinstance(clone, dict):
        clone.pop("duration_ms", None)
    return clone


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

    correlation_id = str(case_input.get("correlation_id", "")).strip() or f"fixture:{case_id}"

    trace_dir_a = trace_root / f"{case_id}-a"
    trace_dir_b = trace_root / f"{case_id}-b"

    result_a = module.execute_coordinator_delegation_v1(
        cfg,
        case_input,
        trace_dir=trace_dir_a,
        correlation_id=correlation_id,
    )
    result_b = module.execute_coordinator_delegation_v1(
        cfg,
        case_input,
        trace_dir=trace_dir_b,
        correlation_id=correlation_id,
    )

    if json.dumps(stable_result(result_a), sort_keys=True) != json.dumps(stable_result(result_b), sort_keys=True):
        failures.append(f"{case_id}: execution output is not deterministic")

    runtime_gate = result_a.get("runtime_gate", {})
    if not isinstance(runtime_gate, dict):
        failures.append(f"{case_id}: runtime_gate payload missing")
        runtime_gate = {}

    expected_runtime_enabled = bool(expect.get("runtime_enabled", False))
    actual_runtime_enabled = bool(runtime_gate.get("enabled", False))
    if actual_runtime_enabled != expected_runtime_enabled:
        failures.append(
            f"{case_id}: runtime_enabled mismatch expected={expected_runtime_enabled} actual={actual_runtime_enabled}"
        )

    expected_task_count = int(expect.get("task_count", 0) or 0)
    actual_task_count = int(result_a.get("task_count", -1) or -1)
    if actual_task_count != expected_task_count:
        failures.append(
            f"{case_id}: task_count mismatch expected={expected_task_count} actual={actual_task_count}"
        )

    tasks = result_a.get("tasks", [])
    if not isinstance(tasks, list):
        failures.append(f"{case_id}: tasks payload is not a list")
        continue

    actual_modes = [str(item.get("execution_mode", "")).strip().lower() for item in tasks if isinstance(item, dict)]
    expected_modes = [str(item).strip().lower() for item in expect.get("execution_modes", [])]
    if expected_modes and actual_modes != expected_modes:
        failures.append(f"{case_id}: execution_modes mismatch expected={expected_modes} actual={actual_modes}")

    actual_decisions = [str(item.get("decision", "")).strip().lower() for item in tasks if isinstance(item, dict)]
    expected_decisions = [str(item).strip().lower() for item in expect.get("decisions", [])]
    if expected_decisions and actual_decisions != expected_decisions:
        failures.append(f"{case_id}: decisions mismatch expected={expected_decisions} actual={actual_decisions}")

    actual_statuses: list[str] = []
    for item in tasks:
        if not isinstance(item, dict):
            actual_statuses.append("")
            continue
        envelope = item.get("result_envelope", {})
        if not isinstance(envelope, dict):
            actual_statuses.append("")
            continue
        actual_statuses.append(str(envelope.get("status", "")).strip().lower())
    expected_statuses = [str(item).strip().lower() for item in expect.get("result_statuses", [])]
    if expected_statuses and actual_statuses != expected_statuses:
        failures.append(
            f"{case_id}: result status mismatch expected={expected_statuses} actual={actual_statuses}"
        )

    synthesis = result_a.get("synthesis", {})
    synthesis = synthesis if isinstance(synthesis, dict) else {}
    expected_synthesis_status = str(expect.get("synthesis_status", "")).strip().lower()
    actual_synthesis_status = str(synthesis.get("status", "")).strip().lower()
    if expected_synthesis_status and actual_synthesis_status != expected_synthesis_status:
        failures.append(
            f"{case_id}: synthesis status mismatch expected={expected_synthesis_status} actual={actual_synthesis_status}"
        )

    expected_fallback_count = int(expect.get("fallback_count", -1))
    if expected_fallback_count >= 0:
        actual_fallback_count = int(synthesis.get("fallback_count", -1))
        if actual_fallback_count != expected_fallback_count:
            failures.append(
                f"{case_id}: fallback_count mismatch expected={expected_fallback_count} actual={actual_fallback_count}"
            )

    expected_deferred_count = int(expect.get("deferred_count", -1))
    if expected_deferred_count >= 0:
        actual_deferred_count = int(synthesis.get("deferred_count", -1))
        if actual_deferred_count != expected_deferred_count:
            failures.append(
                f"{case_id}: deferred_count mismatch expected={expected_deferred_count} actual={actual_deferred_count}"
            )

    traces = module._read_action_traces(trace_dir_a)
    filtered = [
        item
        for item in traces
        if isinstance(item, dict)
        and str(item.get("metadata", {}).get("correlation_id", "")).strip() == correlation_id
    ]
    trace_counts: dict[str, int] = {}
    for item in filtered:
        action_type = str(item.get("action_type", "")).strip()
        trace_counts[action_type] = trace_counts.get(action_type, 0) + 1

    expected_trace_counts = expect.get("trace_counts", {})
    if isinstance(expected_trace_counts, dict):
        for action_type, expected_count_raw in expected_trace_counts.items():
            action_token = str(action_type).strip()
            expected_count = int(expected_count_raw)
            actual_count = int(trace_counts.get(action_token, 0))
            if actual_count != expected_count:
                failures.append(
                    f"{case_id}: trace count mismatch for {action_token} expected={expected_count} actual={actual_count}"
                )

    expected_trace_absent = expect.get("trace_absent", [])
    if isinstance(expected_trace_absent, list):
        for action_type in expected_trace_absent:
            action_token = str(action_type).strip()
            if trace_counts.get(action_token, 0) != 0:
                failures.append(
                    f"{case_id}: expected no traces for action_type={action_token}"
                )

    summary.append(
        {
            "case_id": case_id,
            "runtime_enabled": actual_runtime_enabled,
            "execution_modes": actual_modes,
            "decisions": actual_decisions,
            "synthesis_status": actual_synthesis_status,
            "trace_counts": trace_counts,
        }
    )

if failures:
    print("delegated execution fixture failures:")
    for item in failures:
        print(f"- {item}")
    raise SystemExit(1)

print(
    json.dumps(
        {
            "suite": "delegated-execution-v1",
            "status": "pass",
            "total": len(cases),
            "summary": summary,
        },
        indent=2,
    )
)
PY
