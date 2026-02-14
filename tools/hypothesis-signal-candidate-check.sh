#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR

tmp_root="$(mktemp -d)"
export TMP_ROOT="${tmp_root}"
trap 'rm -rf "${tmp_root}"' EXIT

fixtures_path="${ROOT_DIR}/assistant/hypothesis-signal-candidate-fixtures.json"
signals_path="${tmp_root}/data/unmet-intent-signals.json"
triage_path="${tmp_root}/data/unmet-intent-signal-triage.json"
config_path="${tmp_root}/config.json"
output_path="${tmp_root}/signal-candidates.json"
emit_dir="${tmp_root}/generated-hypotheses"

mkdir -p "${tmp_root}/data" "${emit_dir}"

python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
tmp_root = Path(os.environ["TMP_ROOT"])
fixtures = json.loads((root / "assistant" / "hypothesis-signal-candidate-fixtures.json").read_text(encoding="utf-8"))

signals_payload = fixtures["signals_ledger"]
triage_payload = fixtures["triage_ledger"]

signals_path = tmp_root / "data" / "unmet-intent-signals.json"
triage_path = tmp_root / "data" / "unmet-intent-signal-triage.json"
config_path = tmp_root / "config.json"

signals_path.write_text(json.dumps(signals_payload, indent=2) + "\n", encoding="utf-8")
triage_path.write_text(json.dumps(triage_payload, indent=2) + "\n", encoding="utf-8")
config_payload = {
    "schema_version": 1,
    "signals": {
        "enabled": True,
        "retention_days": int(signals_payload.get("retention_days", 90)),
        "max_records": int(signals_payload.get("max_records", 300)),
    },
}
config_path.write_text(json.dumps(config_payload, indent=2) + "\n", encoding="utf-8")
PY

export CONFIG_PATH="${config_path}"
threshold_args=()
while IFS= read -r line; do
  threshold_args+=("${line}")
done < <(python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
fixtures = json.loads((root / "assistant" / "hypothesis-signal-candidate-fixtures.json").read_text(encoding="utf-8"))
thresholds = fixtures.get("thresholds", {})
print("--min-count")
print(str(int(thresholds.get("min_count", 2))))
print("--min-confidence")
print(str(float(thresholds.get("min_confidence", 0.65))))
print("--max-age-days")
print(str(int(thresholds.get("max_age_days", 90))))
print("--max-candidates")
print(str(int(thresholds.get("max_candidates", 10))))
print("--now")
print(str(fixtures.get("now", "")))
PY
)

candidate_json="$(python3 "${ROOT_DIR}/tools/hypothesis-pipeline.py" signals-candidates \
  --config "${config_path}" \
  --signals-ledger "${signals_path}" \
  --triage-ledger "${triage_path}" \
  --output "${output_path}" \
  --base-hypothesis "${ROOT_DIR}/assistant/hypotheses/phase3-hypothesis-pipeline-v1.json" \
  --emit-hypotheses-dir "${emit_dir}" \
  "${threshold_args[@]}" \
  --json)"
export CANDIDATE_JSON="${candidate_json}"

python3 - <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
fixtures = json.loads((root / "assistant" / "hypothesis-signal-candidate-fixtures.json").read_text(encoding="utf-8"))
expectations = fixtures["expectations"]
payload = json.loads(os.environ["CANDIDATE_JSON"])

summary = payload.get("summary", {})
if int(summary.get("promoted_count", -1)) != int(expectations["promoted_count"]):
    raise SystemExit("promoted_count mismatch")
if int(summary.get("held_count", -1)) != int(expectations["held_count"]):
    raise SystemExit("held_count mismatch")
if int(summary.get("rejected_count", -1)) != int(expectations["rejected_count"]):
    raise SystemExit("rejected_count mismatch")

status_by_signal = expectations["status_by_signal"]
by_signal = {}
for item in payload.get("candidates", []):
    if not isinstance(item, dict):
        continue
    signal = item.get("signal_evidence", {})
    if not isinstance(signal, dict):
        continue
    signal_id = str(signal.get("signal_id", ""))
    if signal_id:
        by_signal[signal_id] = item

for signal_id, expected_status in status_by_signal.items():
    actual = str(by_signal.get(signal_id, {}).get("status", ""))
    if actual != expected_status:
        raise SystemExit(f"status mismatch for {signal_id}: expected {expected_status}, got {actual}")

promoted_expected = set(expectations["promoted_signal_ids"])
promoted_actual = {
    str(item.get("signal_evidence", {}).get("signal_id", ""))
    for item in payload.get("candidates", [])
    if isinstance(item, dict) and str(item.get("status", "")) == "promote"
}
if promoted_actual != promoted_expected:
    raise SystemExit(f"promoted signal ids mismatch: expected {sorted(promoted_expected)}, got {sorted(promoted_actual)}")

for item in payload.get("candidates", []):
    if not isinstance(item, dict):
        continue
    if str(item.get("status", "")) != "promote":
        continue
    hypothesis = item.get("hypothesis", {})
    if not isinstance(hypothesis, dict):
        raise SystemExit("promoted candidate missing hypothesis block")
    hypothesis_path = Path(str(hypothesis.get("path", "")).strip())
    if not hypothesis_path.exists():
        raise SystemExit(f"promoted hypothesis file missing: {hypothesis_path}")
    proc = subprocess.run(
        [
            "python3",
            str(root / "tools" / "hypothesis-pipeline.py"),
            "validate",
            "--hypothesis",
            str(hypothesis_path),
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"generated hypothesis contract invalid: {hypothesis_path}\n{proc.stdout}\n{proc.stderr}")

forbidden = {"raw_text", "transcript", "conversation", "messages", "content"}

def walk(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).strip().lower() in forbidden:
                return str(key)
            found = walk(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = walk(nested)
            if found:
                return found
    return ""

found = walk(payload)
if found:
    raise SystemExit(f"forbidden key leaked into candidate payload: {found}")
PY

python3 - <<'PY'
import json
import os
from pathlib import Path

config_path = Path(os.environ["CONFIG_PATH"])
cfg = json.loads(config_path.read_text(encoding="utf-8"))
signals = cfg.get("signals", {})
if not isinstance(signals, dict):
    signals = {}
signals["enabled"] = False
cfg["signals"] = signals
config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
PY

opt_out_json="$(python3 "${ROOT_DIR}/tools/hypothesis-pipeline.py" signals-candidates \
  --config "${config_path}" \
  --signals-ledger "${signals_path}" \
  --triage-ledger "${triage_path}" \
  --output "${tmp_root}/signal-candidates-opt-out.json" \
  --base-hypothesis "${ROOT_DIR}/assistant/hypotheses/phase3-hypothesis-pipeline-v1.json" \
  "${threshold_args[@]}" \
  --json)"
export OPT_OUT_JSON="${opt_out_json}"

python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["OPT_OUT_JSON"])
summary = payload.get("summary", {})
fixtures = json.loads(
    open(os.environ["ROOT_DIR"] + "/assistant/hypothesis-signal-candidate-fixtures.json", encoding="utf-8").read()
)
if int(summary.get("promoted_count", -1)) != int(fixtures["expectations"]["opt_out_promoted_count"]):
    raise SystemExit("opt-out promoted_count mismatch")
if not bool(summary.get("opt_out_respected", False)):
    raise SystemExit("opt-out signal was not respected")
PY
