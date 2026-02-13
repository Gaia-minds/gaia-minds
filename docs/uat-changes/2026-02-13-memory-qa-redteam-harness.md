# Memory QA + Red-Team Harness UAT Update (2026-02-13)

## Why this change

Issue `#78` introduces a deterministic memory QA/red-team harness for poisoning
and leakage regressions, plus new retrieval/safety/latency gate metrics.

Because this adds a new memory quality enforcement surface used by smoke/UAT,
feature-to-scenario mapping and deterministic UAT coverage were updated.

## Risk

- High.
- Regressions could allow memory poisoning to outrank trusted memories or leak
  scoped secret records.

## Confidence and Safeguards

- Added deterministic `memory_qa_redteam_harness` scenario validating:
  - poisoning resistance
  - leakage block guarantees
  - retrieval quality and latency threshold enforcement
- Added matching smoke coverage:
  - `memory_qa_redteam_harness`
- Updated feature catalog mapping for memory command paths to include QA harness
  scenario coverage.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
