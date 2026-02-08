# Changelog

All notable decisions and changes to the Gaia Minds project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Removed
- OpenClaw runtime integration, auth source, and all cross-repo references; Gaia is now fully standalone with Codex CLI as the sole OAuth path
- `skills/gaia-assistant-builder/references/openclaw-boundary.md` boundary document

### Added
- Roadmap/backlog reassessment issue template (`.github/ISSUE_TEMPLATE/roadmap-backlog-review.yml`)
- Research synthesis playbook for backlog realism reviews (`research/synthesis/2026-02-roadmap-backlog-research-playbook.md`)
- Incident/postmortem docs and reusable template (`docs/incidents/README.md`, `docs/incidents/postmortem-template.md`)
- Nightly benchmark trend workflow (`.github/workflows/benchmark-nightly.yml`) with history/summary updates
- Benchmark trend tool and local command (`tools/benchmark-trend.py`, `make benchmark-trend`)
- Skills + sandbox enablement synthesis from Agent Skills, Claude Code, and Codex docs (`research/synthesis/2026-02-skills-and-sandbox-enablement.md`)
- Skill onboarding security validation synthesis with anti-malicious checks (`research/synthesis/2026-02-skill-onboarding-security-validation.md`)

### Changed
- Refreshed roadmap and sprint status priorities to remove closed-item drift and reference reassessment issue `#46`
- Synced latest release references to `@gaia-minds/assistant-cli@0.2.0` across top-level and assistant contributor docs
- Added contributor guidance to use the roadmap/backlog review issue template for reassessment work
- Expanded benchmark docs with nightly trend and incident linkage guidance
- Expanded Phase 2 roadmap/sprint scope with first-class skill workflows and sandbox execution policy deliverables
- Added external skill compatibility planning based on `vercel-labs/agent-skills` repository patterns
- Expanded Phase 2 scope with skill onboarding security-gate requirements and validation-report criteria
- Reorganized Phase 2 execution into explicit parallel lanes (`P2-A`..`P2-H`) for multi-agent offloading
- Published Phase 2 parallel issue set (`#51`-`#58`) so lanes are claimable independently

### Planned
- Additional resource documentation
- More specialized skills
- Moltbook integration
- First external contributors

---

## [0.2.0] - 2026-02-08

### Added - Assistant Runtime

- Interactive chat sessions with local memory and resume support (`gaia chat --resume last`) (#27)
- Note/task capture and retrieval workflows (`gaia note`, `gaia tasks`) (#28)
- Research URL summarization workflows (`gaia summarize`, `gaia summaries`) (#29)
- Goal-to-plan workflow with persisted plans and refinement support (`gaia plan`, `gaia plans`) (#30)
- Profile-aware local config workflows (`gaia config set/get`) (#31)

### Added - Framework and Safety

- Capability registry with permission levels (`safe`, `confirm`, `forbidden`) and local overrides (#32)
- Structured action traces with local query tooling (`gaia traces`) (#33)
- Deterministic smoke suite with CI workflow integration (`make test-smoke`) (#34)
- Phase 1 canonical hardening checklist and generated hardening report artifacts (#38)

### Changed

- Fixed broken links in `resources/free-tiers/INDEX.md` to stabilize repository-wide link checks
- Expanded assistant docs with trace schema and capability-policy usage

---

## [0.1.1] - 2026-02-07

### Added - Assistant Runtime

- Standalone Gaia assistant CLI published on npm as `@gaia-minds/assistant-cli` (#12)
- Gaia-native auth path with Codex CLI broker (#10, #11)
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

_History enables learning. Document so future agents understand our journey._
