# Gaia Standalone Assistant

This is the standalone Gaia personal assistant runtime path.

It runs independently from OpenClaw, while staying compatible with the same
provider auth patterns:

1. Subscription OAuth flows (for providers that support it in your environment)
2. Direct API key access

Current npm release: `@gaia-minds/assistant-cli@0.1.1`

## Quick Start

```bash
# Install from npm (recommended)
npm install -g @gaia-minds/assistant-cli
gaia onboard
gaia auth status
gaia doctor

# Local development from this repository
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

## Provider Onboarding

Run the guided onboarding wizard:

```bash
gaia onboard
```

The wizard lets you choose provider and connection style:

1. `openrouter` -> API key + model selection
2. `openai` -> API key
3. `anthropic` -> API key
4. `openai-codex` -> OAuth via Codex CLI

Direct non-interactive examples:

```bash
# OpenRouter
gaia onboard --provider openrouter --api-key "$OPENROUTER_API_KEY" --model openrouter/auto --yes

# Anthropic
gaia onboard --provider anthropic --api-key "$ANTHROPIC_API_KEY" --yes

# OpenAI API key
gaia onboard --provider openai --api-key "$OPENAI_API_KEY" --model gpt-4.1-mini --yes

# OpenAI Codex OAuth
gaia onboard --provider openai-codex --yes
```

Gaia still supports explicit auth commands if you prefer manual control.
For Codex OAuth:

```bash
npm run gaia -- auth login --source codex-cli --provider openai-codex
npm run gaia -- auth status
```

Optional compatibility path (legacy): link from OpenClaw profile store.
Use `--source openclaw`.

## Token Safety

- OAuth tokens are stored in Gaia local state:
  `~/.gaia-assistant/auth-profiles.json` (or `$GAIA_ASSISTANT_HOME/auth-profiles.json`)
- API keys can be stored in Gaia local secret store:
  `~/.gaia-assistant/secrets.json` (or `$GAIA_ASSISTANT_HOME/secrets.json`)
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
- `OPENROUTER_API_KEY`

Reasoning provider selection is configured by onboarding in launcher config,
and can be overridden per run:

```bash
# one-off override from Gaia launcher
gaia run --mode single --reasoning-provider openai --reasoning-model gpt-4.1-mini
gaia run --mode single --reasoning-provider openrouter --reasoning-model openrouter/auto

# npm/local clone equivalent
npm run gaia -- run --mode single --reasoning-provider openai --reasoning-model gpt-4.1-mini
npm run gaia -- run --mode single --reasoning-provider openrouter --reasoning-model openrouter/auto
```

OpenRouter quick setup:

```bash
export OPENROUTER_API_KEY="your-openrouter-key"
gaia onboard --provider openrouter
gaia run --mode single --reasoning-provider openrouter --reasoning-model openrouter/auto
```

OpenAI quick setup:

```bash
export OPENAI_API_KEY="your-openai-key"
gaia onboard --provider openai --model gpt-4.1-mini
gaia run --mode single --reasoning-provider openai --reasoning-model gpt-4.1-mini
```

Provider OAuth profile support is exposed through Gaia-native commands:

- `gaia onboard`
- `gaia auth login --source codex-cli --provider openai-codex`
- `npm run gaia -- onboard`
- `npm run gaia -- auth login --source codex-cli --provider openai-codex`

Direct Python fallback (if preferred):
- `python3 tools/gaia-assistant.py onboard`
- `python3 tools/gaia-assistant.py auth login --source codex-cli --provider openai-codex`

OpenClaw linking remains available as an optional compatibility source.

The self-evolution loop planner supports Anthropic, OpenAI, and OpenRouter in
non-dry runs. Tier-2 LLM alignment checks currently run only with Anthropic;
when using OpenAI or OpenRouter, Tier-1 deterministic alignment checks still apply.

## Agent Follow-Up

For agents continuing this track, use contributor workflow from:

- `skills/gaia-contributor/SKILL.md`
- `skills/gaia-assistant-builder/SKILL.md`

Recommended handoff protocol:

1. Pull latest main and read this file + `tools/agent-config.yml`.
2. Check open work first:
   - `gh issue list --state open`
   - `gh pr list --state open`
3. Avoid duplication:
   - `rg -n "<topic>" assistant tools infrastructure skills`
4. Prefer small, reviewable PRs for runtime changes.
5. Before pushing, run:
   - `make check-all`
   - `python3 -m py_compile tools/gaia-assistant.py tools/agent-loop.py tools/agent-alignment.py`
6. Update `CHANGELOG.md` with meaningful behavior changes.
7. If this is your first PR to Gaia, include Constitutional acknowledgment from
   `skills/gaia-contributor/SKILL.md` in PR description.

## Maintainer Release Flow

`@gaia-minds/assistant-cli` is publish-ready via GitHub Actions.

1. Ensure npm auth is configured in repository settings:
   - preferred: npm Trusted Publisher for this repo/workflow
   - fallback: repository secret `NPM_TOKEN`
2. Bump version in `package.json` and create a tag like `v0.1.1`.
3. Push the version commit and tag.
4. GitHub Action `.github/workflows/npm-publish.yml` validates and publishes.
5. For rehearsal, run workflow manually with `dry_run=true`.
