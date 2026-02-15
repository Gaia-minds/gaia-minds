# Reasoning Effort Selector UAT Coverage Update (2026-02-15)

## Why this change

Issue `#147` adds a provider-aware model effort selector across onboarding,
config, and runtime paths. This lane updates protected UAT governance files so
the `run` command path and onboarding contract stay covered by deterministic
scenarios.

Updated mapping:

- `run` now includes `run_reasoning_effort_selector`.

Updated scenarios:

- `onboard_openai_nostore` now verifies onboarding `--effort` persistence.
- `run_reasoning_effort_selector` validates:
  - effort propagation for supported provider/model combinations
  - deterministic no-op logging for unsupported provider/model combinations

## Risk

- High.
- Effort wiring changes runtime request payload behavior and startup contract
  output; missing UAT coverage could allow silent regressions.

## Confidence and Safeguards

- Scenario `run_reasoning_effort_selector` uses local deterministic mock
  endpoints only (`tools/runtime-effort-check.sh`), with explicit payload
  assertions.
- The unsupported-model lane fails if effort is sent when it should be omitted.
- Existing baseline run coverage (`run_single_dry`,
  `run_failover_quota_hard_error`) remains unchanged.

## Validation

- `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/gaia_assistant_onboarding.py tools/agent-loop.py`
- `bash ./tools/runtime-effort-check.sh`
- `make test-smoke`
- `make test-uat`
- `make check-all`
- `python3 tools/check-uat-policy.py --base-ref origin/main --reviewer TonyThePredictor`
