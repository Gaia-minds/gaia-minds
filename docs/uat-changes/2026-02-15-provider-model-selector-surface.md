# Provider Model Selector UAT Update (2026-02-15)

## Why this change

Issue `#142` adds provider-aware model catalog selection and changes Codex OAuth
runtime default alignment to `gpt-5.3-codex`. Protected UAT files were updated
to ensure this behavior remains deterministic and validated in CI.

Updated scenario:

- `auth_link_codex_aligns_run_provider`

Updated assertions:

- verify aligned runtime provider is `openai`
- verify aligned runtime model is `gpt-5.3-codex`
- verify dry-run output includes the aligned model string

## Risk

- Medium.
- Regression risk is concentrated in OAuth-linked runtime-default alignment and
  run preflight rendering for provider/model selection.

## Confidence and Safeguards

- Deterministic token fixture path still drives Codex auth-link behavior without
  external network dependencies.
- Assertions now cover both provider and model alignment so fallback regressions
  are caught earlier.
- Existing onboarding and run command-path coverage remains unchanged.

## Validation

- `python3 tools/uat-runner.py --run auth_link_codex_aligns_run_provider`
- `python3 tools/uat-runner.py --run onboard_openai_nostore`
- `make test-smoke`
- `make check-all`
