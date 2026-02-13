# Memory Policy + Privacy Surface UAT Update (2026-02-13)

## Why this change

Issue `#77` adds new memory policy/privacy command and governance surfaces:

- `gaia memory export`
- capability/policy tool support for `memory_export`
- consent/retention contract enforcement across memory classes
- delete/export evidence artifacts (`memory-tombstones.jsonl`,
  `memory-export-events.jsonl`, export JSON payloads)

Because this introduces a new command path and materially changes memory safety
behavior, UAT mapping and deterministic scenario coverage were required.

## Risk

- High.
- Regressions could allow unsafe memory export, invalid consent/retention
  combinations, or missing delete/export evidence guarantees.

## Confidence and Safeguards

- Added deterministic `memory_policy_privacy_controls` scenario that validates:
  - policy-engine confirm/deny behavior for `memory_export`
  - export capability deny gate (`memory_export forbidden`)
  - consent boundary enforcement by memory class
  - successful export artifact generation and trace metadata
  - delete tombstone evidence emission
- Added matching smoke coverage:
  - `memory_policy_privacy_controls`
- Added UAT feature catalog coverage for new command path:
  - `memory export`

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
