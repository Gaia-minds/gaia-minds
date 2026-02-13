# Skills Runtime Surface UAT Update (2026-02-13)

## Why this change

`P2-C` introduces a new top-level command surface in `tools/gaia-assistant.py`:

- `skills list`
- `skills inspect`

UAT coverage and command mappings were extended so deterministic policy checks
continue to enforce command-surface completeness.

## Risk

- Medium.
- New registry/inspection output could drift if source filtering or skill-id
  resolution changes without scenario updates.

## Confidence and Safeguards

- Added deterministic scenario `skills_runtime_list_and_inspect` that validates:
  - project-source listing includes expected skills
  - inspect lookup from list output
  - contract schema marker (`schema_version: 1`)
  - source provenance (`source: project`)
- Registered command mappings in `assistant/feature-catalog.json` for:
  - `skills`
  - `skills list`
  - `skills inspect`

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
