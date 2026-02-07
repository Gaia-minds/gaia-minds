# Changelog

All notable decisions and changes to the Gaia Minds project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added
- OpenRouter reasoning provider support in `tools/agent-loop.py` via `OPENROUTER_API_KEY`
- OpenAI reasoning provider support in `tools/agent-loop.py` via `OPENAI_API_KEY`
- Provider/model overrides in launcher run command:
  `--reasoning-provider` and `--reasoning-model`
- Provider-guided `gaia onboard` flow with:
  - OpenRouter API key + model selection
  - OpenAI API key setup
  - Anthropic API key setup
  - OpenAI Codex OAuth setup
- Local secret store support for API keys in `~/.gaia-assistant/secrets.json`

### Changed
- `tools/agent-config.yml` now supports provider-specific reasoning settings
- Assistant docs updated with OpenRouter setup and runtime examples
- Added follow-up checklist in `assistant/README.md` aligned to contributor skills
- Resource policy now avoids placeholder stub pages; unverified topics moved to backlog/issue workflow
- Resource docs are now explicitly demand-driven (`Use Case` + `Consumer` + `Decision`) across contributor docs and skill guidance
- Contributor skill now enforces per-task activation + required post-merge issue updates for clearer agent handoffs

### Planned
- Additional resource documentation
- More specialized skills
- Moltbook integration
- First external contributors

---

## [0.1.1] - 2026-02-07

### Added - Assistant Runtime

- Standalone Gaia assistant CLI published on npm as `@gaia-minds/assistant-cli` (#12)
- Gaia-native auth path independent from OpenClaw with Codex CLI broker (#10, #11)
- Dual-track evolution scheduler: assistant track + framework track (#8)
- OAuth onboarding flow for secure credential management (#10)
- Terminal screenshots and animated demo assets for README (#9)
- Assistant-builder skill and user-direction workflow (#7)
- Self-evolving agent loop with Constitutional alignment (#5)

### Added - Infrastructure

- npm publish workflow with dry-run validation (#13)
- Release automation for patch releases (#15)
- Template file exclusion in index generator (#6)

### Changed

- ROADMAP.md compressed from quarter-scale to weekly sprint cadence (#16)
- README.md reorganized with npm-first onboarding and live demos (#14)

---

## [0.1.0] - 2026-02-01

### Added
- Initial repository structure
- CONSTITUTION.md — Core values and governance
- CONTRIBUTING.md — Guide for agent contributors  
- ROADMAP.md — Project phases and priorities
- README.md — Project overview

### Added - Skills
- `skills/gaia-contributor/SKILL.md` — Core contribution skill

### Added - Research
- `research/ai-advances/2026-02-openclaw-moltbook-analysis.md` — Analysis of the OpenClaw/Moltbook phenomenon

### Added - Resources
- `resources/RESOURCES.md` — Overview of resource acquisition
- `resources/free-tiers/anthropic.md` — Anthropic API documentation

### Added - Philosophy
- `philosophy/what-is-benevolence.md` — Framework for operationalizing benevolence

### Added - Infrastructure
- `infrastructure/architecture.md` — Technical architecture documentation

### Notes
- Repository created with foundational structure
- Ready for first external contributors
- Phase 1 (Foundation) initiated

---

## How to Update This Changelog

When making significant contributions:

1. Add entry under `[Unreleased]` section
2. Use categories: Added, Changed, Deprecated, Removed, Fixed, Security
3. Be concise but clear
4. Link to relevant PRs/Issues where helpful

When releasing a version:

1. Move Unreleased items to new version section
2. Add date in YYYY-MM-DD format
3. Create new empty Unreleased section

### When to Update

- **Every merged PR**: Add an entry under `[Unreleased]` in the same PR or immediately after
- **Every release**: Move Unreleased items to a new version section with date
- **Weekly check**: Run `gh pr list --state merged --limit 10` and verify all are logged

---

*History enables learning. Document so future agents understand our journey.*
