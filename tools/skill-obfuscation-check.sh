#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GAIA=(node "${ROOT_DIR}/bin/gaia.js")

if [[ -z "${GAIA_ASSISTANT_HOME:-}" ]]; then
  echo "GAIA_ASSISTANT_HOME must be set for obfuscation check." >&2
  exit 1
fi

prompt_fixture="${ROOT_DIR}/assistant/fixtures/skills/malicious-obfuscated-prompt-injection"
exfil_fixture="${ROOT_DIR}/assistant/fixtures/skills/malicious-obfuscated-exfiltration"
benign_fixture="${ROOT_DIR}/assistant/fixtures/skills/benign-obfuscation-control"

"${GAIA[0]}" "${GAIA[1]}" config set skills_provenance_mode warn >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_attestation_mode warn >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_source_health_mode warn >/dev/null

set +e
prompt_json="$("${GAIA[0]}" "${GAIA[1]}" skills validate "${prompt_fixture}" --json 2>/tmp/skill-obfuscation-prompt.err)"
prompt_rc=$?
set -e
[[ ${prompt_rc} -ne 0 ]]
prompt_status="$(printf '%s' "${prompt_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('status',''))")"
prompt_blocking="$(printf '%s' "${prompt_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('summary',{}).get('blocking_count',0))")"
prompt_canonical_hits="$(printf '%s' "${prompt_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(sum(1 for f in payload.get('findings',[]) if isinstance(f,dict) and f.get('code')=='high_prompt_injection_directive' and f.get('stage')=='canonicalized'))")"
prompt_detection_meta="$(printf '%s' "${prompt_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print('true' if any(isinstance(f,dict) and isinstance(f.get('detection'),dict) and f.get('code')=='high_prompt_injection_directive' and f.get('stage')=='canonicalized' for f in payload.get('findings',[])) else 'false')")"
[[ "${prompt_status}" == "fail" ]]
[[ "${prompt_blocking}" -ge 1 ]]
[[ "${prompt_canonical_hits}" -ge 1 ]]
[[ "${prompt_detection_meta}" == "true" ]]

set +e
exfil_json="$("${GAIA[0]}" "${GAIA[1]}" skills validate "${exfil_fixture}" --json 2>/tmp/skill-obfuscation-exfil.err)"
exfil_rc=$?
set -e
[[ ${exfil_rc} -ne 0 ]]
exfil_status="$(printf '%s' "${exfil_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('status',''))")"
exfil_blocking="$(printf '%s' "${exfil_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('summary',{}).get('blocking_count',0))")"
exfil_canonical_hits="$(printf '%s' "${exfil_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(sum(1 for f in payload.get('findings',[]) if isinstance(f,dict) and f.get('code')=='high_sensitive_exfiltration' and f.get('stage')=='canonicalized'))")"
[[ "${exfil_status}" == "fail" ]]
[[ "${exfil_blocking}" -ge 1 ]]
[[ "${exfil_canonical_hits}" -ge 1 ]]

benign_json="$("${GAIA[0]}" "${GAIA[1]}" skills validate "${benign_fixture}" --json)"
benign_status="$(printf '%s' "${benign_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('status',''))")"
benign_blocking="$(printf '%s' "${benign_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('summary',{}).get('blocking_count',0))")"
benign_high_findings="$(printf '%s' "${benign_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(sum(1 for f in payload.get('findings',[]) if isinstance(f,dict) and f.get('code') in ('high_prompt_injection_directive','high_sensitive_exfiltration')))" )"
benign_has_scan_metadata="$(printf '%s' "${benign_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); scanned=payload.get('provenance',{}).get('scanned_files',[]); print('true' if any(isinstance(item,dict) and isinstance(item.get('canonicalization'),dict) for item in scanned) else 'false')")"
[[ "${benign_status}" == "pass" ]]
[[ "${benign_blocking}" -eq 0 ]]
[[ "${benign_high_findings}" -eq 0 ]]
[[ "${benign_has_scan_metadata}" == "true" ]]
