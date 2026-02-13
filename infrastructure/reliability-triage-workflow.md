# Reliability Triage Workflow

Updated: February 13, 2026

This workflow defines owner/severity routing for reliability checkpoint
threshold breaches.

Baseline thresholds:

- `assistant/reliability-baseline-phase3.json`

Checkpoint artifacts:

- `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-checkpoint.json`
- `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-checkpoint.md`

## Severity Routing

| Severity | Default Owner | Trigger Pattern |
| --- | --- | --- |
| `sev1` | `gaia-incident-responder` | Benchmark/UAT pass-rate regression, any benchmark/UAT failure-rate breach, consolidated failure-rate breach |
| `sev2` | `gaia-qa-evaluator` | Memory quality pass-rate or latency budget breach, MTTR proxy breach |
| `sev3` | `gaia-technical-writer` | Documentation/process mismatch without runtime reliability breach |

## Response Steps

1. Run `make reliability-checkpoint-check` and capture artifact paths.
2. For each breach, route by severity table above.
3. Open or update an incident record under `docs/incidents/` using
   `docs/incidents/postmortem-template.md`.
4. Link checkpoint artifacts, relevant CI runs, and remediation owner in the
   incident file.
5. Add remediation issue(s) with due dates; reference them in sprint status.
6. Re-run checkpoint after mitigation and update incident status.

## Minimum Incident Fields

- breached metric ids and observed values
- threshold values from baseline config
- assigned severity and owner
- mitigation/rollback action
- verification command evidence

## Release Gate Linkage

Release readiness must include reliability checkpoint evidence:

- `infrastructure/release-readiness-template.md`
