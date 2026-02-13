# Hypothesis Artifacts

This folder stores versioned Phase 3 hypothesis proposal artifacts consumed by
`tools/hypothesis-pipeline.py`.

## Files

- `phase3-hypothesis-pipeline-v1.json`:
  passing reference hypothesis contract for proposal -> eval -> evidence flow.
- `phase3-hypothesis-pipeline-v1-failure-fixture.json`:
  deterministic failure fixture for rollback recommendation validation.

## Commands

Validate contract:

```bash
python3 tools/hypothesis-pipeline.py validate \
  --hypothesis assistant/hypotheses/phase3-hypothesis-pipeline-v1.json
```

Run deterministic dry-run packaging:

```bash
python3 tools/hypothesis-pipeline.py run \
  --hypothesis assistant/hypotheses/phase3-hypothesis-pipeline-v1.json \
  --run-id dry-run \
  --dry-run
```

Run deterministic failure fixture (expected non-zero):

```bash
python3 tools/hypothesis-pipeline.py run \
  --hypothesis assistant/hypotheses/phase3-hypothesis-pipeline-v1-failure-fixture.json \
  --run-id failure-fixture \
  --dry-run
```

Generated evidence artifacts are written under:
`assistant/hypothesis-evals/<hypothesis-id>/<run-id>/`.

`make hypothesis-*` targets default to `/tmp/gaia-hypothesis-evals` and can be
overridden via `HYPOTHESIS_OUTPUT_ROOT`.
