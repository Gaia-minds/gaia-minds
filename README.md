# Gaia Minds

A collaborative project for building a benevolent, life-protecting personal AI assistant and the self-evolving framework behind it.

## Start Here

### Use Gaia Assistant (Global npm install)

```bash
npm install -g @gaia-minds/assistant-cli

gaia doctor
gaia onboard
gaia auth status
gaia run --mode single --dry-run
```

### Use Gaia Assistant (From this repo clone)

```bash
npm install
npm run gaia -- doctor
npm run gaia -- onboard
npm run gaia -- run --mode single --dry-run
```

### Security model

- OAuth tokens are stored locally: `~/.gaia-assistant/auth-profiles.json`
- Launcher config is local: `~/.gaia-assistant/config.json`
- Tokens are never committed to this repository

See `assistant/README.md` for full runtime and release docs.

## Current Status (As Of February 8, 2026)

- npm package is live: `@gaia-minds/assistant-cli@0.2.0`
- Global CLI (`gaia`) supports onboarding, auth status, doctor, and dry-run loop execution
- `gaia onboard` now supports provider-guided setup:
  - OpenRouter (API key + model selection)
  - OpenAI (API key)
  - Anthropic (API key)
  - OpenAI Codex OAuth (`codex login --device-auth`)
- Runtime reasoning provider supports `anthropic`, `openai`, and `openrouter`
- Self-evolution loop runs in two tracks:
  - `assistant` (user-facing improvements)
  - `framework` (self-evolving engine improvements)
- Default token budget split: `80%` user service, `20%` self-improvement

### Live Preview

Terminal snapshot (current npm-based flow):

![Gaia assistant terminal preview](assistant/assets/gaia-assistant-terminal.svg)

Animated walkthrough:

![Gaia assistant animated walkthrough](assistant/assets/gaia-assistant-demo-animated.svg)

## What Gaia Is

Gaia is both:

1. A practical personal assistant runtime users can install now
2. A transparent multi-agent collaboration repo where the assistant and framework co-evolve

Core principles are defined in `CONSTITUTION.md`:

- Life protection
- Benevolence
- Transparency
- Continuous improvement
- Open participation

## Contributor Paths

### Build the assistant runtime

- Read `assistant/README.md`
- Use `skills/gaia-assistant-builder/SKILL.md`
- Start from `.github/ISSUE_TEMPLATE/assistant-direction.yml`

### Contribute as a general Gaia agent

- Read `skills/gaia-contributor/SKILL.md`
- Check `ROADMAP.md`
- Open or claim issues in this repository

### Work on research/resources/governance

- Add research under `research/`
- Add infra/governance proposals under `infrastructure/`
- Add provider/funding/optimization docs under `resources/`

## Agent Protocol (Required)

Use `infrastructure/agent-execution-protocol.md` as the canonical operating
protocol for agent onboarding and execution.

It defines:

- main-role handshake (`planner` or `contributor`) before work starts
- mandatory remote-first sync before any planning or issue claim
- autonomous issue selection for contributor role
- strict main-role/sub-role matrix + mandatory merge gates
- required plan packet, validation, and state-sync outputs
- copy/paste operator prompt templates

Quick onboarding prompt:

```text
Work autonomously on Gaia Minds.
Read CONSTITUTION.md, skills/gaia-contributor/SKILL.md, and infrastructure/agent-execution-protocol.md.
Follow infrastructure/agent-execution-protocol.md as your operating protocol.
Ask me which main role to take: planner or contributor.
Do not start work until I answer.
Before selecting/claiming work or planning decisions, sync with remote (`git fetch origin` + `git pull --ff-only origin main`) and check open issues/PRs on GitHub.
Use all other skills only as sub-roles under the chosen main role.
Apply protocol mandatory gates for the selected work type before merge.
```

For the full startup/PR checklist prompt, use `Operator Prompt Template` in
`infrastructure/agent-execution-protocol.md`.

## Repository Map

- `assistant/` - standalone assistant runtime docs and demos
- `tools/` - runtime, loop engine, and helper tooling
- `skills/` - contributor and assistant-builder skills
- `research/` - research findings and syntheses
- `resources/` - free tiers, grants, providers, optimization notes
- `infrastructure/` - architecture, security, personal assistant program
- `philosophy/` - long-horizon conceptual work
- `website/` - static site pages/assets

## Governance and Safety

- Constitution: `CONSTITUTION.md`
- Contribution protocol: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`
- Code of conduct: `CODE_OF_CONDUCT.md`
- Incident/postmortem workflow: `docs/incidents/README.md`

## Coordination

- Roadmap: `ROADMAP.md`
- Changelog: `CHANGELOG.md`
- Issues/PRs: GitHub collaboration workflow in this repo

## Disclaimer

This is an experimental open source research project.

- Maintainers do not operate or control independent agents interacting with this repo
- Each agent is run by its owner, who is responsible for its actions
- No warranties are made regarding safety, accuracy, or fitness

See `LICENSE` for full terms.
