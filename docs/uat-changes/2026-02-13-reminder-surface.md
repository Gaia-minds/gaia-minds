# Reminder Surface UAT Update (2026-02-13)

## Why this change

`P2-B` adds a new reminder command surface in `tools/gaia-assistant.py`:

- `reminder create`
- `reminder list`
- `reminder update`
- `reminder pause`
- `reminder resume`
- `reminder snooze`
- `reminder dismiss`

UAT mappings were extended so reminder lifecycle coverage is deterministic and
policy-compliant alongside existing scheduler checks.

## Risk

- Medium.
- New command paths could drift from deterministic behavior if reminder due-time
  handling or trace assertions become non-reproducible.

## Confidence and Safeguards

- Added a single deterministic end-to-end scenario:
  `reminder_lifecycle_and_controls`.
- Scenario validates create/list controls, pause/resume/snooze transitions, due
  execution via `schedule run-due`, trace emission (`reminder_run`), and
  dismissal cleanup.
- Coverage is registered in both `assistant/uat-scenarios.json` and
  `assistant/feature-catalog.json` to satisfy policy checks.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
