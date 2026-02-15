# Claude OAuth Onboarding/Auth UAT Update (2026-02-15)

## Why this change

Issue `#130` adds Claude Code OAuth onboarding/auth support. Protected UAT files
were updated so this new command surface is verified deterministically without
requiring live external login.

Added scenarios:

- `onboard_claude_code_oauth`
- `auth_login_claude_cli_source`

Updated mappings:

- `assistant/feature-catalog.json` command-path mappings for `onboard`,
  `auth login`, and `auth status`
- `assistant/uat-policy.md` OAuth command-surface policy notes

## Risk

- Medium.
- Regression risk centers on parser/command wiring and metadata-link handling
  for `claude-code` / `claude-cli`.

## Confidence and Safeguards

- Deterministic local `claude` CLI stub validates:
  - `gaia onboard --provider claude-code` path
  - `gaia auth login --provider claude-code --source claude-cli` path
  - `gaia auth status` metadata rendering for linked Claude profile
- Existing auth/codex scenarios remain unchanged and still run.
- `uat-policy` stays enforced with this change record.

## Validation

- `make check-all`
- `make test-smoke`
- `make test-uat`
- `make uat-policy`
