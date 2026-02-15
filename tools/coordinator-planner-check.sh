#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_PATH="${ROOT_DIR}/assistant/coordinator-planner-fixtures.json"
TMP_ROOT="$(mktemp -d)"
TRACE_DIR="${TMP_ROOT}/traces"

cleanup() {
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

export ROOT_DIR
export FIXTURES_PATH
export TRACE_DIR

python3 - <<'PY'
import importlib.util
import json
import os
import sys
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
fixtures_path = Path(os.environ["FIXTURES_PATH"])
trace_dir = Path(os.environ["TRACE_DIR"])

fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
cases = fixtures.get("cases", [])
if not isinstance(cases, list) or not cases:
    raise SystemExit("coordinator planner fixtures missing cases")

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

for case in cases:
    if not isinstance(case, dict):
        failures.append("fixture entry is not an object")
        continue
    case_id = str(case.get("id", "")).strip() or "unknown"
    case_input = case.get("input", {})
    expect = case.get("expect", {})
    if not isinstance(case_input, dict) or not isinstance(expect, dict):
        failures.append(f"{case_id}: fixture input/expect must be objects")
        continue

    plan_first = module.plan_coordinator_delegation_v1(case_input)
    plan_second = module.plan_coordinator_delegation_v1(case_input)

    stable_a = json.dumps(plan_first, sort_keys=True)
    stable_b = json.dumps(plan_second, sort_keys=True)
    if stable_a != stable_b:
        failures.append(f"{case_id}: planner output is not deterministic")

    expected_task_count = int(expect.get("task_count", 0) or 0)
    actual_task_count = int(plan_first.get("task_count", -1) or -1)
    if actual_task_count != expected_task_count:
        failures.append(
            f"{case_id}: task_count mismatch expected={expected_task_count} actual={actual_task_count}"
        )

    tasks = plan_first.get("tasks", [])
    if not isinstance(tasks, list):
        failures.append(f"{case_id}: tasks payload is not a list")
        continue

    expected_task_ids = [str(item).strip() for item in expect.get("task_ids", [])]
    actual_task_ids = [str(item.get("task_id", "")).strip() for item in tasks if isinstance(item, dict)]
    if expected_task_ids and actual_task_ids != expected_task_ids:
        failures.append(
            f"{case_id}: task id mismatch expected={expected_task_ids} actual={actual_task_ids}"
        )

    expected_top = [str(item).strip().lower() for item in expect.get("top_specialists", [])]
    actual_top: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            actual_top.append("")
            continue
        ranked = task.get("ranked_specialists", [])
        if isinstance(ranked, list) and ranked and isinstance(ranked[0], dict):
            actual_top.append(str(ranked[0].get("specialist_id", "")).strip().lower())
        else:
            actual_top.append("")
    if expected_top and actual_top != expected_top:
        failures.append(
            f"{case_id}: top specialist mismatch expected={expected_top} actual={actual_top}"
        )

    expected_decisions = [str(item).strip().lower() for item in expect.get("decisions", [])]
    actual_decisions: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            actual_decisions.append("")
            continue
        decision = task.get("delegation_decision", {})
        if not isinstance(decision, dict):
            actual_decisions.append("")
            continue
        contract_id = str(decision.get("contract_id", "")).strip()
        if contract_id != "delegation.contract.v1":
            failures.append(
                f"{case_id}: evaluator contract mismatch for task {task.get('task_id')}: {contract_id}"
            )
        actual_decisions.append(str(decision.get("decision", "")).strip().lower())
    if expected_decisions and actual_decisions != expected_decisions:
        failures.append(
            f"{case_id}: decision mismatch expected={expected_decisions} actual={actual_decisions}"
        )

    for task in tasks:
        if not isinstance(task, dict):
            continue
        candidates = task.get("candidate_specialists", [])
        if not isinstance(candidates, list) or not candidates:
            failures.append(f"{case_id}: missing candidate_specialists for task {task.get('task_id')}")

    trace = module.emit_coordinator_plan_trace(
        trace_dir,
        plan_first,
        correlation_id=f"fixture:{case_id}",
        duration_ms=0.1,
    )
    metadata = trace.get("metadata", {})
    if not isinstance(metadata, dict):
        failures.append(f"{case_id}: plan trace metadata missing")
    else:
        for field in ("plan_id", "task_count", "correlation_id"):
            if str(metadata.get(field, "")).strip() == "":
                failures.append(f"{case_id}: plan trace missing '{field}'")

    summary.append(
        {
            "case_id": case_id,
            "task_count": actual_task_count,
            "top_specialists": actual_top,
            "decisions": actual_decisions,
        }
    )

trace_entries = module._read_action_traces(trace_dir)
plan_traces = [
    item for item in trace_entries
    if isinstance(item, dict) and str(item.get("action_type", "")).strip() == "delegation_plan_created"
]
if len(plan_traces) != len(cases):
    failures.append(
        "plan trace count mismatch: "
        f"expected={len(cases)} actual={len(plan_traces)}"
    )

if failures:
    print("coordinator planner fixture failures:")
    for item in failures:
        print(f"- {item}")
    raise SystemExit(1)

print(
    json.dumps(
        {
            "suite": "coordinator-planner-v1",
            "status": "pass",
            "total": len(cases),
            "summary": summary,
            "trace_dir": str(trace_dir),
        },
        indent=2,
    )
)
PY
