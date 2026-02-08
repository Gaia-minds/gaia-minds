# Benchmark Methodology (Phase 1)

This benchmark tracks quality on the 20 canonical Phase 1 assistant tasks.

## Command Surface

Run benchmark:

```bash
make benchmark
```

The command writes structured JSON results to:

- `assistant/benchmark-results.json`
- `assistant/benchmark-trend-history.json` (when running `make benchmark-trend`)
- `assistant/benchmark-trend-summary.md` (when running `make benchmark-trend`)

Baseline artifact:

- `assistant/benchmark-baseline.json`

## Scoring

- Task source: `assistant/canonical-tasks.md`
- Runner source: `tools/phase1-hardening.py`
- Benchmark wrapper: `tools/benchmark.py`
- Score: `passed / total * 100`
- Phase 1 success target: `>=80%`

Each task emits:

- task id (`T01`...`T20`)
- title
- pass/fail status
- deterministic details string

## Determinism Rules

- Benchmark compares current run against `assistant/benchmark-baseline.json`.
- Baseline is read-only during normal runs.
- Benchmark fails on drift (task pass/fail or summary changes).
- Baseline updates only when explicitly requested.

## Updating Baseline

Only update baseline after intentional behavior changes that should redefine
expected quality:

```bash
python3 tools/benchmark.py --update-baseline
```

Review the resulting diff in `assistant/benchmark-baseline.json` before merge.

## CI Integration

`.github/workflows/benchmark.yml` runs `make benchmark` on PRs and main,
and uploads `assistant/benchmark-results.json` as an artifact.

Nightly trend workflow:

- `.github/workflows/benchmark-nightly.yml` runs on a nightly UTC schedule and on manual dispatch.
- It runs `make benchmark`, appends a new trend record, and updates:
  - `assistant/benchmark-trend-history.json`
  - `assistant/benchmark-trend-summary.md`
- It uploads nightly artifacts for triage and long-term comparison.

## Local Trend Updates

```bash
make benchmark
make benchmark-trend
```

Use the summary to quickly inspect:

- current benchmark status
- score delta versus previous run
- pass streak and recent run table

## Incident and Postmortem Integration

When nightly benchmarks fail or regressions are detected, open a postmortem
using:

- `docs/incidents/postmortem-template.md`
- `docs/incidents/README.md`
