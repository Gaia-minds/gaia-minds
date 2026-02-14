# Unmet-Intent Signals Surface UAT Update (2026-02-14)

## Why this change

Issue `#111` adds a new privacy-preserving unmet-intent signal command surface:

- `gaia signals extract`
- `gaia signals list`
- `gaia signals export`
- `gaia signals clear`

The lane also extends `gaia config set` usage with explicit signal controls:

- `signals_enabled` (default-on collection with opt-out)
- `signals_retention_days`
- `signals_max_records`

Because this introduces new command paths plus privacy/retention behavior, UAT
mapping and deterministic scenario coverage were updated in the same change set.

## Risk

- High.
- Regressions could leak raw transcript content into derived signal artifacts,
  ignore opt-out behavior, or bypass retention/cap controls.

## Confidence and Safeguards

- Added deterministic scenario `signals_extraction_privacy_controls` validating:
  - derived signal extraction from local feedback + trace artifacts
  - raw transcript token is absent from signal ledger artifacts
  - explicit opt-out (`signals_enabled=false`) blocks new signal writes
  - retention window and deterministic record cap enforcement
  - export + clear command behavior and artifact handling
- Added matching smoke coverage:
  - `signals_extraction_privacy_controls`
- Added feature catalog mappings for all new `signals` command paths and config
  set usage tied to this scenario.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
- `make check-all`
