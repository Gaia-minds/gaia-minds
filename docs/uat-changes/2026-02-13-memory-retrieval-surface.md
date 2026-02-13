# Memory Retrieval Surface UAT Update (2026-02-13)

## Why this change

Issue `#76` adds a retrieval/ranking command surface over the memory runtime:

- `gaia memory retrieve`

This lane also introduces retrieval quality regression thresholds via
`tools/memory-benchmark.py` and fixture-driven checks.

Because this change adds a new command path and deterministic quality gate
semantics, UAT mapping and deterministic scenario coverage were required by
policy.

## Risk

- High.
- Regressions could silently degrade retrieval quality, bypass deterministic
  fallback behavior, or exceed latency/token-overhead budgets.

## Confidence and Safeguards

- Added deterministic `memory_retrieve_ranking_benchmark` UAT scenario that
  validates:
  - retrieval stage flow correctness for seeded fixtures
  - ranking output includes expected top result and stage diagnostics
  - benchmark threshold enforcement (`--check`) for Recall@k, nDCG@k, p95
    latency, and average token-overhead
- Added matching smoke coverage:
  - `memory_retrieve_ranking_and_benchmark`
- Added UAT catalog mapping for new command path:
  - `memory retrieve`

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
- `make memory-benchmark`
