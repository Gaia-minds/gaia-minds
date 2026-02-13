# Trace Surface UAT Update (2026-02-13)

## Why this change

`P2-G` extends trace behavior in `tools/gaia-assistant.py` with:

- normalized cross-lane metadata fields
- correlation identifiers linking policy/sandbox trace chains
- new `gaia traces` metadata filters (`--skill-id`, `--skill-source`,
  `--policy-decision`, `--sandbox-profile`, `--correlation-id`, `--json`)

UAT and smoke coverage were extended so trace filtering and correlation flows
remain deterministic and policy-enforced in CI.

## Risk

- High.
- Audit/schema drift can reduce incident triage reliability if trace filters and
  metadata contracts are not validated end-to-end.

## Confidence and Safeguards

- Added deterministic scenario `traces_filtering_and_correlation` validating:
  - filtered `policy_decision` traces by skill/policy/sandbox dimensions
  - non-empty `correlation_id` extraction from JSON output
  - correlation-linked retrieval includes both `policy_decision` and
    `sandbox_run` events
- Added matching smoke coverage for the same filter/correlation flow.
- Updated feature catalog mappings so trace/sandbox paths remain tied to
  scenario coverage.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
