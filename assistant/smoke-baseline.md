# Smoke Baseline

Updated: February 7, 2026

## Suite

Command:

```bash
make test-smoke
```

Expected artifact:

- `smoke-results.json`

## Baseline Expectations

Total tests: `5`

1. `cli_startup` -> pass
2. `config_read_write` -> pass
3. `session_create_resume` -> pass
4. `note_capture_and_tasks` -> pass
5. `provider_fallback` -> pass

## Notes

- The smoke suite is deterministic by default.
- Network-dependent provider calls are not required for smoke pass.
- Any intended behavior change should update this file and the suite checks in
  `tools/smoke-test.sh`.
