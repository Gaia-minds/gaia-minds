# Changelog

All notable decisions and changes to the Gaia Minds project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Removed
- OpenClaw runtime integration, auth source, and all cross-repo references; Gaia is now fully standalone with Codex CLI as the sole OAuth path
- `skills/gaia-assistant-builder/references/openclaw-boundary.md` boundary document

### Added
- Scheduler core command surface with durable schedule persistence and due-run execution (`gaia schedule create/list/update/cancel/run-due`) for lane `P2-A` (`#51`)
- Scheduler run ledger for idempotent execution keys (`~/.gaia-assistant/data/schedule-runs.jsonl`)
- Reminder command surface with cadence controls and lifecycle actions (`gaia reminder create/list/update/pause/resume/snooze/dismiss`) for lane `P2-B` (`#52`)
- Reminder delivery event log (`~/.gaia-assistant/data/reminder-events.jsonl`)
- Skills runtime command surface for deterministic discovery/inspection (`gaia skills list`, `gaia skills inspect`) for lane `P2-C` (`#53`)
- Skills validation security gate command surface (`gaia skills validate`) with severity-ranked findings and blocking behavior for lane `P2-D` (`#54`)
- Skill validation report artifacts (`~/.gaia-assistant/traces/skill-validation-reports/*.json`) with schema `gaia.skill-validation.v1`
- Sandbox command surface with profile contract and escalation approvals (`gaia sandbox profiles/run`) for lane `P2-E` (`#55`)
- Sandbox approval event log (`~/.gaia-assistant/traces/sandbox-approvals.jsonl`)
- Policy engine command surface with decision evaluation and per-skill allowlists (`gaia policy evaluate`, `gaia policy allowlist set/list/clear`) for lane `P2-F` (`#56`)
- Policy decision traces for sandbox execution gating (`policy_decision`)
- Unified trace metadata envelope with correlation ids across skills/policy/sandbox actions for lane `P2-G` (`#57`)
- Versioned skill metadata contract publication (`infrastructure/skill-contract-v1.md`)
- Versioned sandbox contract publication (`infrastructure/sandbox-contract-v1.md`)
- Deterministic UAT + smoke coverage for the new scheduler command paths (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for reminder lifecycle controls (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for skills runtime list/inspect command paths (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for skills validation pass/block flows (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for sandbox profile/escalation command paths (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for policy decision/allowlist command paths and sandbox bypass checks (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for trace filtering and correlation-id audit flows (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- UAT change record for scheduler CLI coverage governance (`docs/uat-changes/2026-02-08-scheduler-surface.md`)
- UAT change record for reminder CLI coverage governance (`docs/uat-changes/2026-02-13-reminder-surface.md`)
- UAT change record for skills runtime CLI coverage governance (`docs/uat-changes/2026-02-13-skills-runtime-surface.md`)
- UAT change record for skills validation CLI coverage governance (`docs/uat-changes/2026-02-13-skills-validation-surface.md`)
- UAT change record for sandbox CLI coverage governance (`docs/uat-changes/2026-02-13-sandbox-surface.md`)
- UAT change record for policy engine CLI coverage governance (`docs/uat-changes/2026-02-13-policy-surface.md`)
- UAT change record for trace schema/filter coverage governance (`docs/uat-changes/2026-02-13-traces-surface.md`)
- Roadmap/backlog reassessment issue template (`.github/ISSUE_TEMPLATE/roadmap-backlog-review.yml`)
- Research synthesis playbook for backlog realism reviews (`research/synthesis/2026-02-roadmap-backlog-research-playbook.md`)
- Incident/postmortem docs and reusable template (`docs/incidents/README.md`, `docs/incidents/postmortem-template.md`)
- Nightly benchmark trend workflow (`.github/workflows/benchmark-nightly.yml`) with history/summary updates
- Benchmark trend tool and local command (`tools/benchmark-trend.py`, `make benchmark-trend`)
- Skills + sandbox enablement synthesis from Agent Skills, Claude Code, and Codex docs (`research/synthesis/2026-02-skills-and-sandbox-enablement.md`)
- Skill onboarding security validation synthesis with anti-malicious checks (`research/synthesis/2026-02-skill-onboarding-security-validation.md`)
- Phase 2 lane implementation plan packets with architecture-delta requirements (`infrastructure/phase2-lane-implementation-plans.md`)
- Memory-management research lane issue (`#60`) for options/tradeoffs before implementation
- Phase 2 planner-round execution artifact with merge order, integration sync report, and docs freshness evidence (`infrastructure/planning-round-2026-02-08-phase2.md`)
- Planning/research/doc/review templates for consistent role execution quality (`infrastructure/*-template.md`)
- New role skills: planner, researcher, technical writer, security reviewer, QA evaluator, release manager, incident responder, integration coordinator, privacy-memory steward
- Agent execution protocol with autonomous issue selection, skill-trigger matrix, output contract, and operator prompt templates (`infrastructure/agent-execution-protocol.md`)

### Changed
- Assistant architecture docs now include Phase 2 scheduler delta details (`infrastructure/architecture.md`)
- Assistant architecture/docs now include Phase 2 reminder delta details and CLI usage (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 skills runtime delta details and contract reference (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 skill validation delta details, artifact paths, and blocking semantics (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 sandbox profile/escalation delta details and contract reference (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 policy engine delta details, command usage, and trace semantics (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 audit+trace delta details with normalized metadata and correlation filtering (`infrastructure/architecture.md`, `assistant/README.md`)
- Refreshed roadmap and sprint status priorities to remove closed-item drift and reference reassessment issue `#46`
- Synced latest release references to `@gaia-minds/assistant-cli@0.2.0` across top-level and assistant contributor docs
- Added contributor guidance to use the roadmap/backlog review issue template for reassessment work
- Expanded benchmark docs with nightly trend and incident linkage guidance
- Expanded Phase 2 roadmap/sprint scope with first-class skill workflows and sandbox execution policy deliverables
- Added external skill compatibility planning based on `vercel-labs/agent-skills` repository patterns
- Expanded Phase 2 scope with skill onboarding security-gate requirements and validation-report criteria
- Reorganized Phase 2 execution into explicit parallel lanes (`P2-A`..`P2-H`) for multi-agent offloading
- Published Phase 2 parallel issue set (`#51`-`#58`) so lanes are claimable independently
- Extended Phase 2 execution model to require per-lane implementation plans and include `P2-I` memory research
- Updated contributor skill/playbook workflows to require lane plan packets before coding
- Added role-based skill routing + state-doc sync reminders across contributor workflow docs
- Updated README/CONTRIBUTING/contributor docs to direct onboarding through the new execution protocol
- Clarified execution model to enforce two main roles (`planner`, `contributor`) with other skills treated as sub-roles
- Added strict main-role/sub-role matrix and mandatory merge gates to the execution protocol
- Added remote-first sync requirement so agents must refresh from `origin` before planning or issue selection

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
