# Incident and Postmortem Workflow

Use this folder to document significant regressions and reliability incidents.

## When to Create a Postmortem

Create a postmortem when one of these occurs:

- benchmark regression or drift on `main`
- autopilot rollback or failed automation requiring manual intervention
- CI reliability incident that blocks contributor throughput
- policy/governance gate failure with user-facing or release impact

## File Naming

Create postmortems as:

- `docs/incidents/YYYY-MM-DD-<short-slug>.md`

Example:

- `docs/incidents/2026-02-10-nightly-benchmark-regression.md`

## Process

1. Copy `docs/incidents/postmortem-template.md` into a new incident file.
2. Fill in the timeline, impact, root cause, and corrective actions.
3. Link to evidence: CI runs, logs, traces, and related PRs/issues.
4. Add owners and due dates for remediation tasks.
5. Keep status current until all actions are closed.

## Required Evidence Sources

- benchmark artifacts (`assistant/benchmark-results.json`)
- benchmark trend summary (`assistant/benchmark-trend-summary.md`)
- benchmark trend history (`assistant/benchmark-trend-history.json`)
- reliability checkpoint artifacts (`/tmp/gaia-reliability-checkpoints/<run-id>/reliability-checkpoint.{json,md}`)
- relevant CI workflow run URLs
- traces/logs tied to the incident
