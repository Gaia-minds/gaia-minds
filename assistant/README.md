# Gaia Standalone Assistant

This is the standalone Gaia personal assistant runtime path.

It runs independently from OpenClaw, while staying compatible with the same
provider auth patterns:

1. Subscription OAuth flows (for providers that support it in your environment)
2. Direct API key access

## Quick Start

```bash
# From this repository
python3 tools/gaia-assistant.py init
python3 tools/gaia-assistant.py doctor

# Single dry-run cycle
python3 tools/gaia-assistant.py run --mode single --dry-run

# Continuous assistant track
python3 tools/gaia-assistant.py run --mode continuous --track assistant
```

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

Provider OAuth profile support depends on your operator environment.

