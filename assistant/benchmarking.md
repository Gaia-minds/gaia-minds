# Benchmark Methodology (Phase 1 + Quality Matrix + Memory Retrieval + Memory QA)

This benchmark tracks:

1. quality on the 20 canonical Phase 1 assistant tasks
2. deterministic quality-matrix guardrails for skills/sandbox/policy compatibility
3. deterministic memory retrieval quality/latency/token-overhead thresholds
4. deterministic memory QA/red-team poisoning and leakage gates

## Command Surface

Run benchmark:

```bash
make benchmark
make memory-benchmark
make memory-quality
```

The command writes structured JSON results to:

- `assistant/benchmark-results.json`
- `assistant/memory-retrieval-benchmark-results.json` (when running `make memory-benchmark`)
- `assistant/memory-quality-results.json` (when running `make memory-quality`)
- `assistant/quality-matrix-results.json` (when running `make quality-matrix`)
- `assistant/benchmark-trend-history.json` (when running `make benchmark-trend`)
- `assistant/benchmark-trend-summary.md` (when running `make benchmark-trend`)

Baseline artifact:

- `assistant/benchmark-baseline.json`

## Scoring

- Task source: `assistant/canonical-tasks.md`
- Runner source: `tools/phase1-hardening.py`
- Quality runner source: `tools/quality-matrix.py`
- Memory retrieval runner source: `tools/memory-benchmark.py`
- Memory QA/red-team runner source: `tools/memory-quality-matrix.py`
- Benchmark wrapper: `tools/benchmark.py`
- Combined score: `(canonical_passed + quality_passed) / (canonical_total + quality_total) * 100`
- Success target: `>=80%`

Canonical tasks emit:

- task id (`T01`...`T20`)
- title
- pass/fail status
- deterministic details string

Quality matrix emits:

- fixture/runtime check id
- category (`prompt-injection`, `unsafe-script`, `exfiltration`, `sandbox`, `policy`, `compatibility`)
- pass/fail status

Memory retrieval benchmark emits:

- per-query returned ids vs expected ids
- Recall@k and nDCG@k
- retrieval latency (ms), including p95 threshold check
- token-overhead estimate and threshold check
- pass/fail status from fixture-defined thresholds

Memory QA/red-team harness emits:

- retrieval quality metrics: Recall@k, Precision@k, Faithfulness@1
- safety metrics: poisoning resistance rate and leakage block rate
- latency and token-overhead summaries with thresholds
- pass/fail status from fixture-defined thresholds

## Determinism Rules

- Benchmark compares current run against `assistant/benchmark-baseline.json`.
- Baseline is read-only during normal runs.
- Benchmark fails on drift (task pass/fail, quality-check pass/fail, or summary changes).
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

Memory retrieval thresholds are also enforced in CI via smoke/UAT suites:
- `make test-smoke` runs retrieval + `tools/memory-benchmark.py --check`
- `make test-uat` runs retrieval + `tools/memory-benchmark.py --check`

Memory QA/red-team thresholds are also enforced in CI via smoke/UAT suites:
- `make test-smoke` runs `tools/memory-quality-matrix.py --check`
- `make test-uat` runs `tools/memory-quality-matrix.py --check`

`.github/workflows/quality-matrix.yml` runs `make quality-matrix` on PRs and main,
and uploads `assistant/quality-matrix-results.json` as an artifact.

Nightly trend workflow:

- `.github/workflows/benchmark-nightly.yml` runs on a nightly UTC schedule and on manual dispatch.
- It runs `make benchmark`, appends a new trend record, and updates:
  - `assistant/benchmark-trend-history.json`
  - `assistant/benchmark-trend-summary.md`
- It uploads nightly artifacts for triage and long-term comparison.

## Local Trend Updates

```bash
make benchmark
make memory-benchmark
make memory-quality
make quality-matrix
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

## Memory Evaluation Failure Triage

When memory benchmarks or QA/red-team gates fail:

1. Re-run locally with isolated artifacts:
   - `make memory-benchmark`
   - `make memory-quality`
2. Inspect artifacts:
   - `assistant/memory-retrieval-benchmark-results.json`
   - `assistant/memory-quality-results.json`
3. Identify failure class:
   - retrieval ranking drift (`recall_at_k`, `ndcg_at_k`, `faithfulness_at_1`)
   - poisoning regression (`poisoning_resistance`)
   - leakage regression (`leakage_block_rate`)
   - latency regression (`p95_latency_ms`)
4. Validate command-level behavior with deterministic queries from fixture files.
5. Open/update an issue with failing metric names, expected thresholds, and artifact excerpts before changing thresholds.
