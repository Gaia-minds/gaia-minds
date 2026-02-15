# Model Catalog Inspection Command UAT Update (2026-02-15)

## Why this change

Issue `#145` introduces a new assistant command surface:

- `gaia models list`

Because this adds a new CLI command path, protected UAT policy files were
updated to register deterministic coverage for:

- `models`
- `models list`

New scenario:

- `models_list_source_disclosure`

This scenario validates both text and JSON output contracts, including
provider/source disclosure and deterministic default ordering for the
`openai-codex` provider path.

## Risk

- Medium.
- Main risk is command-surface drift: parser path additions without UAT mapping
  can silently regress policy coverage and break downstream command contracts.

## Confidence and Safeguards

- The UAT scenario is deterministic and does not require external credentials.
- Assertions validate source disclosure (`live` or `curated`) rather than
  brittle provider-network assumptions.
- JSON output is parsed with Python to ensure schema-level correctness instead
  of substring-only checks.

## Validation

- `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/gaia_assistant_onboarding.py`
- `make test-smoke`
- `make test-uat`
- `make check-all`
- `python3 tools/check-uat-policy.py --base-ref origin/main --reviewer TonyThePredictor`
