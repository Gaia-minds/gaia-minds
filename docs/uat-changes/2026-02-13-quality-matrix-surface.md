# Quality Matrix Surface UAT Update (2026-02-13)

## Why this change

`P2-H` adds deterministic quality hardening for skills/sandbox/policy
regressions with a reusable fixture suite and quality matrix harness:

- malicious skill fixtures (`assistant/fixtures/skills/*`)
- quality runner (`tools/quality-matrix.py`)
- compatibility matrix reproducibility check (`tools/compatibility-matrix.py`)

UAT and smoke coverage were extended with `quality_matrix_guardrails` so
malicious fixture drift and compatibility-matrix drift fail CI immediately.

## Risk

- High.
- Regression in malicious-pattern detection or runtime guardrails can silently
  weaken skill onboarding and sandbox/policy protections.

## Confidence and Safeguards

- Added deterministic fixture classes for:
  - prompt-injection directives
  - unsafe script execution
  - sensitive-data exfiltration patterns
  - reverse-shell behavior
- Added quality-matrix runtime checks for:
  - sandbox escalation required/approved paths
  - policy tool assertion mismatch block
  - allowlist deny enforcement
  - compatibility matrix check mode (`--check`)
- Added smoke and UAT coverage for `quality_matrix_guardrails`.
- Added dedicated CI workflow `quality-matrix` for PR and main branch runs.

## Validation

- `make quality-matrix`
- `make test-smoke`
- `make test-uat`
- `make uat-policy`
