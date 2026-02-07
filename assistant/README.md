# Gaia Standalone Assistant

This is the standalone Gaia personal assistant runtime path.

It runs independently from OpenClaw, while staying compatible with the same
provider auth patterns:

1. Subscription OAuth flows (for providers that support it in your environment)
2. Direct API key access

## Quick Start

```bash
# From this repository
npm install
npm run gaia -- onboard
npm run gaia -- auth status
npm run gaia -- doctor

# Single dry-run cycle
npm run gaia -- run --mode single --dry-run

# Continuous assistant track
npm run gaia -- run --mode continuous --track assistant

# Optional global command from this clone
npm install -g .
gaia doctor
```

## OAuth Onboarding

Gaia uses its own local auth store for ChatGPT/Codex-style profiles.
The default OAuth broker is Codex CLI (web/device flow):

```bash
npm run gaia -- auth login --source codex-cli --provider openai-codex
npm run gaia -- auth status
```

If you already authenticated with Codex CLI, import/link without re-running login:

```bash
npm run gaia -- auth link --source codex-cli --provider openai-codex
```

Optional compatibility path (legacy): link from OpenClaw profile store.
Use `--source openclaw`.

## Token Safety

- OAuth tokens are stored in Gaia local state:
  `~/.gaia-assistant/auth-profiles.json` (or `$GAIA_ASSISTANT_HOME/auth-profiles.json`)
- Launcher config stores profile selection metadata in:
  `~/.gaia-assistant/config.json` (or `$GAIA_ASSISTANT_HOME/config.json`)
- Never commit auth stores or local runtime state to git.
- If you want strict separation, keep `GAIA_ASSISTANT_HOME` outside this repo.

## Tracks

The evolution loop runs with two tracks:

1. `assistant` — user-facing personal assistant improvements
2. `framework` — evolution framework and governance improvements

Default scheduling and policy live in `tools/agent-config.yml`.

## Budget Policy

Default budget split:

- User service: `80%`
- Self-improvement: `20%`

Adjust in `tools/agent-config.yml` under `budget`.

## Auth Notes

Expected environment variables for direct API mode:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

Provider OAuth profile support is exposed through Gaia-native commands:

- `npm run gaia -- onboard`
- `npm run gaia -- auth login --source codex-cli --provider openai-codex`

Direct Python fallback (if preferred):
- `python3 tools/gaia-assistant.py onboard`
- `python3 tools/gaia-assistant.py auth login --source codex-cli --provider openai-codex`

OpenClaw linking remains available as an optional compatibility source.

Current limitation: the self-evolution loop planner currently uses Anthropic SDK
for non-dry cycles. OAuth onboarding is in place so contributors can securely
connect web auth profiles now while provider backends continue to evolve.
