#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GAIA=(node "${ROOT_DIR}/bin/gaia.js")

if [[ -z "${GAIA_ASSISTANT_HOME:-}" ]]; then
  echo "GAIA_ASSISTANT_HOME must be set for provenance check." >&2
  exit 1
fi

base_dir="${GAIA_ASSISTANT_HOME}/provenance-check"
missing_dir="${base_dir}/missing"
complete_dir="${base_dir}/complete"
mkdir -p "${missing_dir}" "${complete_dir}"

cat > "${missing_dir}/SKILL.md" <<'SKILL_MISSING'
---
name: runtime-provenance-missing
description: Deterministic fixture missing provenance metadata for warn/enforce checks.
capabilities:
  - file_read
---

This fixture intentionally omits source pinning and attestation metadata.
SKILL_MISSING

cat > "${complete_dir}/provenance.intoto.jsonl" <<'ATTESTATION'
{"_type":"https://in-toto.io/Statement/v1","predicateType":"https://slsa.dev/provenance/v1","subject":[{"name":"runtime-provenance-complete","digest":{"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}],"predicate":{"buildType":"gaia-fixture","builder":{"id":"gaia-ci"}}}
ATTESTATION

att_sha="$(sha256sum "${complete_dir}/provenance.intoto.jsonl" | awk '{print $1}')"
cat > "${complete_dir}/SKILL.md" <<SKILL_COMPLETE
---
name: runtime-provenance-complete
description: Deterministic fixture with complete provenance metadata.
capabilities:
  - file_read
source_repo: https://github.com/example/runtime-provenance-complete
source_commit: 0123456789abcdef0123456789abcdef01234567
source_tree: fedcba9876543210fedcba9876543210fedcba98
attestation_ref: provenance.intoto.jsonl
attestation_sha256: ${att_sha}
source_health_score: 9
source_health_provider: openssf-scorecard
---

This fixture includes complete provenance metadata.
SKILL_COMPLETE

"${GAIA[0]}" "${GAIA[1]}" config set skills_provenance_mode warn >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_attestation_mode warn >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_source_health_mode warn >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_source_health_min_score 7 >/dev/null

warn_json="$("${GAIA[0]}" "${GAIA[1]}" skills validate "${missing_dir}" --json)"
warn_status="$(printf '%s' "${warn_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('status', ''))")"
warn_blocking="$(printf '%s' "${warn_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('summary', {}).get('blocking_count', 0))")"
warn_decision="$(printf '%s' "${warn_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('provenance_admission', {}).get('overall_decision', ''))")"
[[ "${warn_status}" == "pass" ]]
[[ "${warn_blocking}" -eq 0 ]]
[[ "${warn_decision}" == "warn" ]]
[[ "${warn_json}" == *"provenance_source_pin_missing"* ]]
[[ "${warn_json}" == *"provenance_attestation_missing"* ]]
[[ "${warn_json}" == *"provenance_source_health_missing"* ]]

"${GAIA[0]}" "${GAIA[1]}" config set skills_provenance_mode enforce >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_attestation_mode enforce >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_source_health_mode enforce >/dev/null
set +e
"${GAIA[0]}" "${GAIA[1]}" skills validate "${missing_dir}" >/tmp/skills-provenance-enforce-runtime.out 2>&1
enforce_rc=$?
set -e
[[ ${enforce_rc} -ne 0 ]]
enforce_out="$(cat /tmp/skills-provenance-enforce-runtime.out)"
[[ "${enforce_out}" == *"Validation status: FAIL"* ]]
[[ "${enforce_out}" == *"provenance_source_pin_missing"* ]]

complete_json="$("${GAIA[0]}" "${GAIA[1]}" skills validate "${complete_dir}" --json)"
complete_status="$(printf '%s' "${complete_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('status',''))")"
complete_blocking="$(printf '%s' "${complete_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('summary', {}).get('blocking_count', 0))")"
complete_decision="$(printf '%s' "${complete_json}" | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload.get('provenance_admission', {}).get('overall_decision', ''))")"
[[ "${complete_status}" == "pass" ]]
[[ "${complete_blocking}" -eq 0 ]]
[[ "${complete_decision}" == "pass" ]]

"${GAIA[0]}" "${GAIA[1]}" config set skills_provenance_mode warn >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_attestation_mode warn >/dev/null
"${GAIA[0]}" "${GAIA[1]}" config set skills_source_health_mode warn >/dev/null
