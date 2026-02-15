#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_PATH="${ROOT_DIR}/assistant/delegation-contract-v1-fixtures.json"
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
    raise SystemExit("delegation fixtures missing cases")

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
decision_counts: dict[str, int] = {}

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

    decision = module.evaluate_delegation_contract_v1(case_input)

    expected_decision = str(expect.get("decision", "")).strip().lower()
    actual_decision = str(decision.get("decision", "")).strip().lower()
    if actual_decision != expected_decision:
        failures.append(
            f"{case_id}: decision mismatch expected={expected_decision} actual={actual_decision}"
        )

    expected_fallback = str(expect.get("fallback_strategy", "")).strip().lower()
    actual_fallback = str(decision.get("fallback_strategy", "")).strip().lower()
    if expected_fallback and actual_fallback != expected_fallback:
        failures.append(
            f"{case_id}: fallback mismatch expected={expected_fallback} actual={actual_fallback}"
        )

    expected_reason = expect.get("reason_contains", "")
    actual_reason = str(decision.get("decision_reason", "")).strip().lower()
    if isinstance(expected_reason, list):
        for token in expected_reason:
            probe = str(token).strip().lower()
            if probe and probe not in actual_reason:
                failures.append(
                    f"{case_id}: decision_reason missing token '{probe}'"
                )
    else:
        probe = str(expected_reason).strip().lower()
        if probe and probe not in actual_reason:
            failures.append(
                f"{case_id}: decision_reason missing token '{probe}'"
            )

    trace = module.emit_delegation_decision_trace(
        trace_dir,
        decision,
        correlation_id=f"fixture:{case_id}",
        input_summary=f"fixture {case_id}",
        duration_ms=0.1,
    )
    metadata = trace.get("metadata", {})
    if not isinstance(metadata, dict):
        failures.append(f"{case_id}: trace metadata missing")
        continue

    for field in ("decision_reason", "fallback_strategy", "task_id", "risk_level", "decision", "correlation_id"):
        value = metadata.get(field)
        if str(value).strip() == "":
            failures.append(f"{case_id}: trace metadata missing field '{field}'")

    if str(trace.get("action_type", "")).strip() != "delegation_decision":
        failures.append(f"{case_id}: unexpected trace action_type={trace.get('action_type')}")

    decision_counts[actual_decision] = decision_counts.get(actual_decision, 0) + 1

trace_entries = module._read_action_traces(trace_dir)
delegation_traces = [
    item for item in trace_entries
    if isinstance(item, dict) and str(item.get("action_type", "")).strip() == "delegation_decision"
]
if len(delegation_traces) != len(cases):
    failures.append(
        "delegation trace count mismatch: "
        f"expected={len(cases)} actual={len(delegation_traces)}"
    )

if failures:
    print("delegation contract fixture failures:")
    for item in failures:
        print(f"- {item}")
    raise SystemExit(1)

print(
    json.dumps(
        {
            "suite": "delegation-contract-v1",
            "status": "pass",
            "total": len(cases),
            "decision_counts": decision_counts,
            "trace_dir": str(trace_dir),
        },
        indent=2,
    )
)
PY
