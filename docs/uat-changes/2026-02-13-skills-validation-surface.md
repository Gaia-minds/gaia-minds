# Skills Validation Surface UAT Update (2026-02-13)

## Why this change

`P2-D` adds a new command path in `tools/gaia-assistant.py`:

- `skills validate`

UAT coverage and feature-catalog mappings were extended so the new security
gate remains deterministic and policy-compliant in CI.

## Risk

- Medium.
- Validation gate behavior can drift if severity/blocking semantics or static
  risk checks change without deterministic scenario updates.

## Confidence and Safeguards

- Added deterministic scenario `skills_validation_pass_and_block` that checks:
  - known project skill passes validation
  - malicious fixture fails with non-zero exit
  - `skills_validate` trace event is emitted
- Registered command mappings in `assistant/feature-catalog.json` for:
  - `skills`
  - `skills validate`
- Added smoke coverage for the same pass/block behavior.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
