# Model Capability Metadata Coverage UAT Update (2026-02-15)

## Why this change

Issue `#154` extends `gaia models list` output contract with capability metadata
(`supports_effort`, `effort_levels`) and capability provenance reporting. This
lane updates protected UAT governance files so the command-surface contract is
deterministically covered.

Updated mapping:

- `models list` now includes `models_list_capability_metadata` in addition to
  existing source-disclosure coverage.

New scenario:

- `models_list_capability_metadata`

The new scenario validates JSON schema presence/type for capability metadata and
text output disclosure (`capability source`, `effort:` markers).

## Risk

- Medium.
- Contract drift in model-catalog output could break downstream selectors or
  hide capability assumptions if untested.

## Confidence and Safeguards

- Coverage is deterministic/local and reuses existing command path.
- Assertions verify both machine-readable and human-readable output contracts.
- Existing source-disclosure scenario remains active for backward contract
  confidence.

## Validation

- `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/gaia_assistant_onboarding.py`
- `make test-smoke`
- `make test-uat`
- `make check-all`
- `python3 tools/check-uat-policy.py --base-ref origin/main --reviewer TonyThePredictor`
