# Hypothesis Pipeline v1 Contract

Updated: February 13, 2026

Issue: `#86`  
Track: `framework-track`  
Risk: `high`

## Purpose

Define the first operational self-evolution hypothesis pipeline:

1. proposal artifact
2. deterministic evaluation run
3. PR-ready evidence package

This contract is rollout-focused governance tooling only. It does not perform
automatic merge or deployment.

## Artifact Schema (`schema_version: 1`)

Hypothesis artifacts are JSON files under `assistant/hypotheses/`.

Required top-level fields:

- `schema_version` (`1`)
- `hypothesis_id` (stable slug)
- `title`
- `summary`
- `owner`
- `risk_level` (`low` | `medium` | `high`)
- `rollback_criteria`
- `evaluation`
- `expected_metric_movement` (non-empty array)

### `rollback_criteria`

- `recommended_action` (required string)
- `commands` (optional array of rollback commands)
- `reason_on_failure` (optional string)

### `evaluation`

- `commands` (array; each command has `id`, `run`, optional `required`)
- `required_artifacts` (optional array of file paths to assert existence)

Path templates may use:

- `{hypothesis_id}`
- `{output_dir}`
- `{repo_root}`

### `expected_metric_movement[]`

Each metric gate includes:

- `id`
- `name`
- `description`
- `baseline.path`
- `baseline.json_path`
- `current.path`
- `current.json_path`
- `comparator` (`>`, `>=`, `<`, `<=`, `==`, `!=`)
- `target_delta` (numeric)
- `required` (optional, default `true`)

Metric evaluation uses:

`delta = current - baseline`

Gate condition:

`delta <comparator> target_delta`

## Tooling Contract

Tool: `tools/hypothesis-pipeline.py`

Subcommands:

- `validate`: validate hypothesis contract
- `run`: execute deterministic evaluation and generate evidence package
- `package`: regenerate evidence markdown from an existing report

Default output root:

- `assistant/hypothesis-evals/<hypothesis-id>/<run-id>/`

Generated artifacts:

- `hypothesis.json`
- `commands/*.stdout.log`
- `commands/*.stderr.log`
- `evaluation-report.json`
- `evidence-bundle.md`

## Determinism + Failure Behavior

- Command execution and metric gates are explicit and file-backed.
- Evidence bundle format is stable and PR-review friendly.
- Any required command failure, required artifact miss, or required metric gate
  failure sets report status to `fail`.
- `evaluation-report.json` always includes explicit rollback recommendation:
  - `rollback_recommendation.required`
  - `rollback_recommendation.reason`
  - `rollback_recommendation.recommended_action`
  - `rollback_recommendation.commands`

## Reference Artifacts

- Passing reference hypothesis:
  `assistant/hypotheses/phase3-hypothesis-pipeline-v1.json`
- Failure fixture:
  `assistant/hypotheses/phase3-hypothesis-pipeline-v1-failure-fixture.json`
- Usage notes:
  `assistant/hypotheses/README.md`
