# UAT Change Record: Skills Provenance Admission Coverage

Date: 2026-02-14
Issue: `#122`
PR: pending

## Summary

Extended deterministic UAT/smoke governance coverage for the `gaia skills validate`
provenance admission gate.

Changes:

- Added UAT scenario:
  - `skills_provenance_admission_modes`
- Added smoke scenario:
  - `skills_provenance_admission_modes`
- Added reusable deterministic check script:
  - `tools/skill-provenance-check.sh`
- Updated feature mapping:
  - `assistant/feature-catalog.json` entries for `config set`, `skills`,
    `skills validate`.

## Why This Change

`#122` adds provenance policy modes and threshold behavior that materially change
`skills validate` outcomes (`pass|warn|fail`). Existing UAT coverage validated
malicious-pattern blocking but did not validate provenance admission decisions.

## Risk

Without this update, regressions in provenance mode handling (for example,
`warn` accidentally blocking or `enforce` silently passing) could ship undetected.

## Confidence Plan

- Deterministic fixtures verify all three expected outcomes:
  - `warn` mode: pass with non-blocking provenance findings
  - `enforce` mode: fail with blocking provenance findings
  - complete provenance metadata: pass in enforce mode
- Coverage is enforced in both terminal smoke and UAT suites.
- `make uat-policy` validates command-to-scenario mapping after this change.
