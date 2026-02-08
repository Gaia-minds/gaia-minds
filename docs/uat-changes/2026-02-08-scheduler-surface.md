# Scheduler Surface UAT Update (2026-02-08)

## Why this change

`P2-A` introduces a new scheduler command surface:
`gaia schedule create/list/update/cancel/run-due`.
UAT coverage and command-to-scenario mapping must be updated in the same change
set to keep policy checks deterministic and prevent uncovered CLI drift.

## Risk

- Medium: scheduler introduces persistent state transitions and due-window
  behavior, so regressions could create duplicate runs or missed executions if
  command behavior changes without coverage.

## Confidence and Safeguards

- Added explicit feature-catalog mappings for all `schedule` command paths.
- Added deterministic UAT scenario for schedule lifecycle and duplicate-run-key
  skip behavior.
- Added smoke coverage for schedule lifecycle and due-run execution flow.

## Validation

- `make check-all`
- `make test-smoke`
- `python3 tools/uat-runner.py --manifest assistant/uat-scenarios.json --run schedule_lifecycle_and_run_due --json-out assistant/uat-results.json`
- `python3 tools/check-uat-policy.py --base-ref origin/main --reviewer TonyThePredictor`
