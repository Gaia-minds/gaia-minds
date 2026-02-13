# Reliability Drift Report v1

Updated: February 13, 2026

Issue: `#93`
Track: `framework-track`
Risk: `high`

## Purpose

Define the deterministic drift-detection artifact generated after reliability
checkpoint runs.

The drift report compares:

1. latest reliability checkpoint metrics vs baseline thresholds
2. latest metrics vs recent checkpoint history window

and produces severity/owner recommendations for triage.

## Tooling

- Generator: `tools/reliability-drift.py`
- Default output root: `/tmp/gaia-reliability-checkpoints`
- Default output path:
  - `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-drift-report.json`
  - `/tmp/gaia-reliability-checkpoints/<run-id>/reliability-drift-report.md`

## Core Detection Rules

For each baseline metric:

- `threshold_breach`:
  - latest value fails configured threshold comparator from
    `assistant/reliability-baseline-phase3.json`
- `history_drift`:
  - latest value moves in the adverse direction relative to recent history
  - adverse shift must exceed drift tolerance

Default drift tolerance:

- `max(abs(threshold) * 0.05, 0.01)`

History requirement:

- at least `history_min_samples` values (default: `2`)

## JSON Schema (v1)

Top-level fields:

- `schema_version` (`1`)
- `generated_at`
- `status` (`pass` | `warn` | `fail`)
- `baseline_date_utc`
- `baseline_commit`
- `source_checkpoint_run_id`
- `source_checkpoint_generated_at`
- `source_checkpoint_path`
- `history_window`
- `history_min_samples`
- `relative_drift_threshold`
- `absolute_drift_threshold`
- `fail_on_severity`
- `history_checkpoint_paths` (array)
- `evaluations` (array)
- `breaches` (array)
- `breach_count`
- `actionable_breach_count`
- `triage_links` (array)
- `simulated_drift_metric` (optional, test mode only)

`evaluations[]` fields:

- `metric_id`
- `latest_value`
- `comparator`
- `threshold`
- `history_samples`
- `history_average` (nullable)
- `adverse_shift` (nullable)
- `drift_tolerance`
- `threshold_breach` (bool)
- `history_drift_breach` (bool)
- `breach_reasons` (array)
- `severity` (empty when no breach)
- `owner` (empty when no breach)
- `action_required` (bool)
- `recommended_action`

`breaches[]` fields:

- `metric_id`
- `severity`
- `owner`
- `action_required`
- `reasons`
- `latest_value`
- `threshold`
- `comparator`
- `history_average`
- `adverse_shift`
- `drift_tolerance`
- `recommended_action`

## Status Semantics

- `pass`: no drift breaches
- `warn`: drift breaches exist, but none are actionable at configured
  `fail_on_severity`
- `fail`: at least one actionable breach exists

`--check` exits non-zero when status is `fail`.

## Triage Linkage

Actionable drift (`sev1`/`sev2` by default) should open or update incidents using:

- `infrastructure/reliability-triage-workflow.md`
- `docs/incidents/postmortem-template.md`
