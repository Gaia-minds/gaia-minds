# Runtime Failover Hard-Error Coverage UAT Update (2026-02-15)

## Why this change

Issue `#146` adds runtime failover behavior for reasoning-provider hard errors
(quota/auth classes). This lane updates protected UAT governance files to keep
command-to-scenario coverage deterministic for the `run` command path.

Updated mapping:

- `run` now includes `run_failover_quota_hard_error`.

New scenario:

- `run_failover_quota_hard_error`

The new scenario uses deterministic local mock provider endpoints to force an
OpenAI-style `insufficient_quota` failure and verify failover visibility and
successful fallback to OpenRouter behavior.

## Risk

- High.
- Runtime failover changes provider-selection behavior during live runs; missing
  UAT coverage could hide regressions in fallback ordering or failure handling.

## Confidence and Safeguards

- The failover scenario is fully local (no external network dependency) via
  `tools/runtime-failover-check.sh` mock servers.
- Assertions validate policy visibility (`Reasoning failover: enabled`),
  trigger detection, and deterministic fallback success logging.
- Existing `run_single_dry` coverage remains intact to preserve baseline run
  command-path confidence.

## Validation

- `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/gaia_assistant_onboarding.py tools/agent-loop.py`
- `bash ./tools/runtime-failover-check.sh`
- `make test-smoke`
- `make test-uat`
- `make check-all`
- `python3 tools/check-uat-policy.py --base-ref origin/main --reviewer TonyThePredictor`
