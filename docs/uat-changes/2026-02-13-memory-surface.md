# Memory Surface UAT Update (2026-02-13)

## Why this change

Issue `#75` adds a new `gaia memory` command surface backed by local SQLite
storage (`memory.db`) with deterministic CRUD flows.

New command paths:
- `gaia memory add`
- `gaia memory get`
- `gaia memory list`
- `gaia memory update`
- `gaia memory delete`

Because this introduces new top-level CLI paths and persistent state semantics,
UAT mapping and deterministic scenario coverage were required by policy.

## Risk

- High.
- Regressions could corrupt long-term memory records or silently bypass memory
  read/write/delete permission checks and trace coverage.

## Confidence and Safeguards

- Added a deterministic `memory_crud_and_filters` UAT scenario that validates:
  - create -> retrieve -> update -> list/filter -> delete lifecycle
  - stable record ids and JSON contract output
  - soft-delete behavior (`get` fails without `--include-deleted`)
- Added matching smoke coverage for memory CRUD/filter behavior.
- Memory operations emit dedicated trace types:
  - `memory_capture`
  - `memory_retrieve`
  - `memory_update`
  - `memory_delete`

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
