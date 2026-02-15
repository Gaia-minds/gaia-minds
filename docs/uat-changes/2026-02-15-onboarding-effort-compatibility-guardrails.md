# Onboarding Effort Compatibility Guardrails UAT Update (2026-02-15)

## Why this change

Issue `#155` adds deterministic compatibility guardrails so onboarding and run
startup clearly disclose unsupported model+effort combinations before cycle
execution. Runtime behavior remains no-op for unsupported paths, but user
guidance is now explicit.

Updated mappings:

- `onboard` now includes `onboard_effort_compatibility_warning` coverage.
- Existing runtime selector scenario (`run_reasoning_effort_selector`) now
  asserts startup compatibility warning/remediation text for unsupported paths.

## Risk

- Medium.
- If warning text drifts or disappears, users may incorrectly assume effort is
  being applied for unsupported model/provider pairs.

## Confidence and Safeguards

- Coverage remains deterministic/local with no external API dependency.
- Assertions validate both onboarding and run startup warning contracts.
- Existing runtime selector checks still verify applied/no-op behavior in
  agent-loop logs.

## Validation

- `python3 -m py_compile tools/gaia-assistant.py tools/agent-loop.py`
- `make test-smoke`
- `make test-uat`
- `make check-all`
- `python3 tools/check-uat-policy.py --base-ref origin/main --reviewer TonyThePredictor`
