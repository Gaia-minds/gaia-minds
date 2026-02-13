# Reliability Triage Workflow

Updated: February 13, 2026

This workflow defines owner/severity routing for reliability checkpoint
threshold breaches and reliability drift breaches.

Baseline thresholds:

- `assistant/reliability-baseline-phase3.json`

Checkpoint artifacts:

- `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-checkpoint.json`
- `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-checkpoint.md`
- `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-drift-report.json`
- `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-drift-report.md`

Drift report schema:

- `infrastructure/reliability-drift-report-v1.md`

## Severity Routing

| Severity | Default Owner | Trigger Pattern |
| --- | --- | --- |
| `sev1` | `gaia-incident-responder` | Benchmark/UAT pass-rate regression, any benchmark/UAT failure-rate breach, consolidated failure-rate breach |
| `sev2` | `gaia-qa-evaluator` | Memory quality pass-rate or latency budget breach, MTTR proxy breach |
| `sev3` | `gaia-technical-writer` | Documentation/process mismatch without runtime reliability breach |

## Response Steps

1. Run `make reliability-checkpoint-check` and capture artifact paths.
2. Run `make reliability-drift-check` and capture drift report paths.
3. For each checkpoint/drift breach, route by severity table above.
4. Open or update an incident record under `docs/incidents/` using
   `docs/incidents/postmortem-template.md`.
5. Link checkpoint/drift artifacts, relevant CI runs, and remediation owner in
   the
   incident file.
6. Add remediation issue(s) with due dates; reference them in sprint status.
7. Re-run checkpoint + drift checks after mitigation and update incident status.

## Minimum Incident Fields

- breached metric ids and observed values
- threshold values from baseline config
- assigned severity and owner
- mitigation/rollback action
- verification command evidence

## Release Gate Linkage

Release readiness must include reliability checkpoint evidence:

- `infrastructure/release-readiness-template.md`
