# Sandbox Surface UAT Update (2026-02-13)

## Why this change

`P2-E` adds new command paths in `tools/gaia-assistant.py`:

- `sandbox profiles`
- `sandbox run`

UAT and smoke coverage were extended so sandbox profile and escalation behavior
remain deterministic and policy-enforced in CI.

## Risk

- Medium.
- Escalation gating can regress silently if command-surface mappings are not
  updated alongside runtime behavior.

## Confidence and Safeguards

- Added deterministic scenario `sandbox_profile_and_escalation` validating:
  - profile listing surface
  - successful non-escalated command execution
  - denied execution when escalation is required but not approved
  - approved execution path with `--approve-escalation`
  - `sandbox_approval` trace emission
- Added feature-catalog mappings for:
  - `sandbox`
  - `sandbox profiles`
  - `sandbox run`
- Added matching smoke coverage for the same flow.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
