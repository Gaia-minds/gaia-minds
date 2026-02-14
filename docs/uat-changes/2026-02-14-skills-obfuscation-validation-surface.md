# UAT Change Record: Skills Obfuscation Validation Coverage

Date: 2026-02-14
Issue: `#123`
PR: pending

## Summary

Extended deterministic UAT/smoke governance coverage for obfuscation-aware
`gaia skills validate` checks.

Changes:

- Added UAT scenario:
  - `skills_obfuscation_validation_hardening`
- Added smoke scenario:
  - `skills_obfuscation_validation_hardening`
- Added reusable deterministic check script:
  - `tools/skill-obfuscation-check.sh`
- Updated feature mapping:
  - `assistant/feature-catalog.json` entries for `config set`, `skills`,
    `skills validate`.

## Why This Change

`#123` introduces canonicalization-aware scanning for obfuscated
prompt-injection/exfiltration payloads and adds detection-stage metadata.
Existing quality/UAT checks covered straightforward malicious patterns but did
not assert encoded/hidden/split-token bypass handling or benign obfuscation
non-regression.

## Risk

Without this update, regressions could allow obfuscated payload bypasses (false
negatives) or over-block benign instructional content (false positives).

## Confidence Plan

- Deterministic fixtures verify both bypass and non-bypass behavior:
  - obfuscated prompt-injection fixture must fail with canonicalized detection
  - obfuscated exfiltration fixture must fail with canonicalized detection
  - benign obfuscation control must pass with zero blocking findings
- Coverage is enforced in both smoke and UAT suites.
- `make uat-policy` validates command-to-scenario mapping after this change.
