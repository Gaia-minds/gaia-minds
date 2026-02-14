# Hypothesis Pipeline v1 Contract

Updated: February 14, 2026

Issue: `#86`, `#94`  
Track: `framework-track`  
Risk: `high`

## Purpose

Define the first operational self-evolution hypothesis pipeline:

1. proposal artifact
2. deterministic evaluation run
3. PR-ready evidence package
4. derived-signal candidate generation (thresholded, suggestion-mode)

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
- `canary_gate` (optional; if omitted, rollout decision defaults to `hold`)
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

### `canary_gate`

Canary gate configuration controls rollout decision evidence:

- `window` (required string when provided; e.g., `24h`, `7d`)
- `sample_size` (required positive integer when provided)
- `pass_threshold` (required number in `[0,1]` when provided)
- `rollback_threshold` (required number in `[0,1]` when provided)
- `fallback_owner` (required string when provided)

Validation rule:

`pass_threshold >= rollback_threshold`

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
- `signals-candidates`: build thresholded hypothesis candidates from
  `unmet-intent-signals.json` + `unmet-intent-signal-triage.json` with
  derived-signal-only guardrails

Default output root:

- `assistant/hypothesis-evals/<hypothesis-id>/<run-id>/`

Generated artifacts:

- `hypothesis.json`
- `commands/*.stdout.log`
- `commands/*.stderr.log`
- `evaluation-report.json`
- `evidence-bundle.md`
- `assistant/hypotheses/signal-candidates.json` (generated candidate summary)
- optional promoted candidate hypothesis stubs under
  `assistant/hypotheses/generated/*.json`

## Determinism + Failure Behavior

- Command execution and metric gates are explicit and file-backed.
- Evidence bundle format is stable and PR-review friendly.
- Any required command failure, required artifact miss, or required metric gate
  failure sets report status to `fail`.
- Signal-derived candidate generation remains suggestion-only:
  - candidates are `promote|hold|reject`
  - opt-out state (`signals.enabled=false`) forces `hold` (no promotion)
  - only triage classes `existing-skill-enable`, `skill-import-candidate`, and
    `core-feature-gap` are promotable
  - `out-of-scope-or-rejected` remains non-promotable
- Candidate promotion thresholds are deterministic:
  - minimum signal `count`
  - minimum signal `confidence`
  - maximum `age_days` bounded by effective retention window (<= 90 days by
    default policy)
- Derived-signal-only policy guard:
  - payloads containing forbidden raw-text key classes (`raw_text`,
    `transcript`, `messages`, etc.) are rejected from promotion.
- `evaluation-report.json` always includes explicit rollback recommendation:
  - `rollback_recommendation.required`
  - `rollback_recommendation.reason`
  - `rollback_recommendation.recommended_action`
  - `rollback_recommendation.commands`
- `evaluation-report.json` now includes explicit canary decision evidence:
  - `canary_decision.decision` (`go` | `hold` | `rollback-required`)
  - `canary_decision.reason`
  - `canary_decision.window`
  - `canary_decision.sample_size_observed` / `sample_size_required`
  - `canary_decision.thresholds.pass_threshold` / `rollback_threshold`
  - `canary_decision.pass_rate`
  - `canary_decision.fallback_owner`
- Decision routing:
  - `rollback-required` when required gates fail or pass rate breaches rollback threshold
  - `hold` when sample is insufficient or pass rate does not clear `pass_threshold`
  - `go` when sample is sufficient and pass rate clears `pass_threshold`

## Reference Artifacts

- Passing reference hypothesis:
  `assistant/hypotheses/phase3-hypothesis-pipeline-v1.json`
- Failure fixture:
  `assistant/hypotheses/phase3-hypothesis-pipeline-v1-failure-fixture.json`
- Hold fixture:
  `assistant/hypotheses/phase3-hypothesis-pipeline-v1-hold-fixture.json`
- Signal-candidate fixture:
  `assistant/hypothesis-signal-candidate-fixtures.json`
- Usage notes:
  `assistant/hypotheses/README.md`
