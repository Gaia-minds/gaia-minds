# Auth Onboarding Run-Continuity UAT Update (2026-02-15)

## Why this change

Issue `#134` fixes an onboarding/runtime continuity regression where a successful
`openai-codex` OAuth link could still leave `gaia run` on an incompatible
provider path. The protected UAT manifest file (`assistant/uat-scenarios.json`)
was updated to lock in deterministic regression coverage.

Added scenario:

- `auth_link_codex_aligns_run_provider`

This validates Codex OAuth link behavior aligns runtime provider defaults and
prevents fallback to the historical anthropic-missing dependency failure path.

## Risk

- Medium.
- Regression risk centers on first-run onboarding continuity and auth/provider
  mismatch handling in `gaia run`.

## Confidence and Safeguards

- Added deterministic UAT scenario covering:
  - synthetic Codex credential fixture import
  - provider-default alignment to `openai`
  - `gaia run --dry-run` provider-path verification
  - negative assertion against the prior anthropic package mismatch failure text
- Full smoke and UAT suites pass with scenario included.
- `uat-policy` remains green with this change record present.

## Validation

- `make check-all`
- `make test-smoke`
- `make test-uat`
- `make uat-policy`
