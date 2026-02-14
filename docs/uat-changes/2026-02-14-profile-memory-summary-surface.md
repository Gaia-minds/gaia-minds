# Response Profile + Memory Summarize Surface UAT Update (2026-02-14)

## Why this change

Issue `#97` adds new deterministic behavior and command surfaces:

- response-profile selection for chat (`gaia chat --response-profile ...`)
- profile preference persistence via config (`response_profile`)
- memory summarization workflow with traceability (`gaia memory summarize`)

This lane also introduces a new thresholded benchmark gate for summarize quality
and traceability (`tools/memory-summary-benchmark.py`).

Because this changes command paths and profile-driven runtime behavior, UAT
mapping and deterministic scenario coverage were required by policy.

## Risk

- Medium.
- Regressions could silently collapse profile differentiation, mis-resolve
  `auto` profile from feedback, or generate untraceable summary artifacts.

## Confidence and Safeguards

- Added deterministic `chat_response_profiles_deterministic` scenario that
  validates:
  - explicit concise/detailed override behavior and output markers
  - `auto` profile resolution from feedback correction records
  - config-driven default profile resolution
- Added deterministic `memory_summarize_traceability_benchmark` scenario that
  validates:
  - summary persistence via `gaia memory summarize`
  - source linkage ledger emission (`memory-summary-events.jsonl`)
  - trace metadata for `memory_summarize`
  - benchmark threshold enforcement for profile-match and traceability rates
- Added matching smoke coverage:
  - `chat_response_profiles_deterministic`
  - `memory_summarize_traceability_and_benchmark`
- Added UAT feature catalog mapping for new command path:
  - `memory summarize`

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
- `make memory-summary-benchmark`
