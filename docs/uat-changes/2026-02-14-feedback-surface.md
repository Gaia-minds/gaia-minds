# Feedback Surface UAT Update (2026-02-14)

## Why this change

Issue `#96` adds a new feedback command surface for deterministic capture of
assistant response quality signals with correction notes and trace/session
linkage.

New command paths:

- `gaia feedback`
- `gaia feedback record`
- `gaia feedback list`

Because this introduces new persistent local records and new command routes, UAT
mapping and deterministic scenario coverage were required by policy.

## Risk

- Medium.
- Regressions could silently drop feedback records, break linkage integrity, or
  allow invalid labels that poison downstream quality analysis.

## Confidence and Safeguards

- Added deterministic `feedback_record_and_list` scenario that validates:
  - record creation with `not helpful` label normalization
  - required linkage to session + trace ids
  - persisted record retrieval via `feedback list`
  - trace evidence emission (`feedback_record`)
- Added deterministic `feedback_invalid_label_rejected` scenario that validates
  invalid input handling.
- Added matching smoke coverage for both positive and invalid-input paths.
- Updated feature-catalog coverage for all new feedback command paths.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
