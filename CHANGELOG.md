# Changelog

All notable decisions and changes to the Gaia Minds project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added
- Planning-round artifact for governance/onboarding stabilization sequencing with issue queue `#129`-`#134`, dependency order, and gate expectations (`infrastructure/planning-round-2026-02-14-governance-onboarding-release-reset.md`)
- Obfuscation-aware canonicalization checks in `gaia skills validate` for encoded/hidden/split-token prompt-injection and sensitive-exfiltration directives, with bounded deterministic candidate scanning (`tools/gaia-assistant.py`, `#123`)
- Detection-stage metadata on skill validation findings (`detection.mode/source/candidate_stage`) and per-file canonicalization scan summaries in report provenance (`tools/gaia-assistant.py`, `#123`)
- Obfuscation fixture set for malicious bypass and benign false-positive guard coverage (`assistant/fixtures/skills/malicious-obfuscated-prompt-injection/SKILL.md`, `assistant/fixtures/skills/malicious-obfuscated-exfiltration/SKILL.md`, `assistant/fixtures/skills/benign-obfuscation-control/SKILL.md`, `assistant/fixtures/skills/manifest.json`, `#123`)
- Reusable obfuscation hardening regression script and smoke/UAT scenario coverage (`tools/skill-obfuscation-check.sh`, `tools/smoke-test.sh`, `assistant/uat-scenarios.json`, `assistant/feature-catalog.json`, `#123`)
- Skill-first unmet-intent triage command surface (`gaia signals triage`) with deterministic class routing (`existing-skill-enable`, `skill-import-candidate`, `core-feature-gap`, `out-of-scope-or-rejected`) and persisted triage ledger output (`tools/gaia-assistant.py`, `tools/gaia_assistant_parser.py`, `#112`)
- Validation-aware skill matching and security-gate evidence in triage output (`rationale`, `follow_up_action`, `security_gate`, `matched_skill`, `class_summary`) with blocked paths for dangerous intents, forbidden capabilities, or failed validation evidence (`tools/gaia-assistant.py`, `#112`)
- Deterministic triage fixture matrix + reusable check harness (`assistant/signal-triage-fixtures.json`, `tools/signal-triage-check.sh`) with smoke/UAT coverage and feature-governance mappings (`tools/smoke-test.sh`, `assistant/uat-scenarios.json`, `assistant/feature-catalog.json`, `#112`)
- UAT governance change record for unmet-intent triage command-surface coverage (`docs/uat-changes/2026-02-14-signals-triage-surface.md`, `#112`)
- Signal-derived hypothesis candidate generation flow in hypothesis pipeline (`tools/hypothesis-pipeline.py` `signals-candidates`) with deterministic threshold routing (`promote|hold|reject`) and triage-aware promotion classes (`#113`)
- Opt-out and retention-window candidate controls honoring `signals.enabled` plus effective retention bounds, with derived-signal-only rejection for forbidden raw-text key classes (`#113`)
- Optional promoted candidate hypothesis stub emission for downstream canary-gated pipeline use (`assistant/hypotheses/generated/*.json` via `--emit-hypotheses-dir`) (`#113`)
- Deterministic signal-candidate fixture matrix + reusable check harness (`assistant/hypothesis-signal-candidate-fixtures.json`, `tools/hypothesis-signal-candidate-check.sh`, `make hypothesis-signals-candidate-fixture`) (`#113`)
- Hypothesis pipeline CI coverage extension for signal-derived candidate generation fixture (`.github/workflows/hypothesis-pipeline.yml`, `#113`)
- Skill provenance admission policy controls for validation workflow (`skills_provenance_mode`, `skills_attestation_mode`, `skills_source_health_mode`, `skills_source_health_min_score`) (`tools/gaia-assistant.py`, `#122`)
- Deterministic provenance admission evidence in skill validation reports (`provenance_admission`) and `skills_validate` trace metadata (`tools/gaia-assistant.py`, `#122`)
- Provenance fixture set for skill validation quality checks (`assistant/fixtures/skills/provenance-complete/*`, `assistant/fixtures/skills/provenance-missing/SKILL.md`, `assistant/fixtures/skills/manifest.json`, `#122`)
- Reusable provenance admission regression script and smoke/UAT coverage for pass/warn/fail policy modes (`tools/skill-provenance-check.sh`, `tools/smoke-test.sh`, `assistant/uat-scenarios.json`, `assistant/feature-catalog.json`, `#122`)
- UAT governance change record for skills provenance admission coverage (`docs/uat-changes/2026-02-14-skills-provenance-admission-surface.md`, `#122`)
- Privacy-preserving unmet-intent signal command surface (`gaia signals extract/list/export/clear`) with deterministic derived-signal schema and local inspection/export/clear controls (`tools/gaia-assistant.py`, `tools/gaia_assistant_parser.py`, `#111`)
- Default-on signal collection controls with explicit opt-out and bounded retention/cap settings via config keys (`signals_enabled`, `signals_retention_days`, `signals_max_records`) (`tools/gaia-assistant.py`, `#111`)
- Local unmet-intent signal artifacts:
  - `~/.gaia-assistant/data/unmet-intent-signals.json`
  - `~/.gaia-assistant/data/unmet-intent-signal-exports.jsonl`
- Deterministic smoke/UAT coverage for signal extraction privacy controls, opt-out behavior, retention-window enforcement, bounded storage cap, and export/clear flows (`tools/smoke-test.sh`, `assistant/uat-scenarios.json`, `assistant/feature-catalog.json`, `#111`)
- UAT governance change record for unmet-intent signal command-surface coverage (`docs/uat-changes/2026-02-14-signals-surface.md`)
- Continuous security-validation research synthesis for broad-source skill imports with issue-linked implementation recommendations (`research/synthesis/2026-02-broad-source-skill-import-security-validation-loop.md`, `#115`)
- Follow-on hardening issue set seeded from `#115`: provenance admission gate (`#122`) and obfuscation-aware validator/fixture expansion (`#123`)

### Changed
- Sprint state docs now track only active queue lanes and include the user-reported OAuth onboarding continuity fix lane (`#134`) before onboarding expansion/release work (`STATUS.md`, `ROADMAP.md`)
- Phase 3 immediate priorities were reset from stale completed items to the active stabilization queue (`#129`-`#134`) with explicit merge order and release dependency gating (`ROADMAP.md`)
- Top-level roadmap/status state now marks `#113` delivered and the signal-driven follow-on queue complete pending next planning round (`STATUS.md`, `ROADMAP.md`)
- Top-level roadmap/status state now marks `#123` delivered and advances signal-driven queue sequencing with `#112` triage delivery evidence (`STATUS.md`, `ROADMAP.md`)
- Top-level roadmap/status state now marks `#122` delivered and advances active queue ownership to `#123` (`STATUS.md`, `ROADMAP.md`)
- UAT policy checker now enforces command-path coverage across both assistant CLI sources after parser modularization (`tools/gaia-assistant.py` + `tools/gaia_assistant_parser.py`) (`tools/check-uat-policy.py`, `assistant/uat-policy.md`)
- Assistant/runtime architecture docs now include unmet-intent skill-first triage behavior, triage artifact paths, and command usage updates (`README.md`, `assistant/README.md`, `infrastructure/architecture.md`, `#112`)
- Hypothesis pipeline contract/docs now include signal-derived candidate integration, threshold semantics, and derived-signal-only guardrails (`assistant/README.md`, `assistant/hypotheses/README.md`, `infrastructure/hypothesis-pipeline-v1.md`, `infrastructure/architecture.md`, `#113`)

### Removed
- _Nothing yet._

## [0.3.0] - 2026-02-14

### Removed
- OpenClaw runtime integration, auth source, and all cross-repo references; Gaia is now fully standalone with Codex CLI as the sole OAuth path
- `skills/gaia-assistant-builder/references/openclaw-boundary.md` boundary document
- Unused auth-profile helper functions from assistant runtime (`_collect_provider_profiles`, `_pick_profile_id`) after dead-code audit lane cleanup (`tools/gaia-assistant.py`, `#105`)

### Added
- Self-evolution PR evidence rubric contract with required fields (`baseline`, `delta`, `thresholds/guardrails`, `rollback/fallback`, `risk notes`) and applicability rules (`infrastructure/self-evolution-evidence-rubric.md`, `#85`)
- Deterministic self-evolution PR evidence enforcement in CI (`tools/check-self-evolution-evidence.py`, `.github/workflows/self-evolution-evidence.yml`)
- UAT governance change record for self-evolution PR evidence rubric enforcement (`docs/uat-changes/2026-02-13-self-evolution-evidence-rubric.md`)
- Hypothesis pipeline v1 deterministic tooling (`tools/hypothesis-pipeline.py`) with proposal validation, eval execution, and PR-ready evidence bundle generation (`#86`)
- Deterministic canary rollout decision gate for hypothesis evidence with explicit `go|hold|rollback-required` outcomes and fallback-owner metadata (`tools/hypothesis-pipeline.py`, `#94`)
- Deterministic hard token-budget enforcement gate for agent cycles with explicit `allow|warn|defer|block` decisions across assistant/framework tracks (`tools/agent-loop.py`, `tools/agent-config.yml`, `#95`)
- Assistant feedback command surface for deterministic response-quality capture (`gaia feedback record/list`) with `helpful` / `not-helpful` labels, optional correction text, and session/trace linkage (`tools/gaia-assistant.py`, `#96`)
- Local feedback persistence contract (`~/.gaia-assistant/data/feedback.json`) with deterministic retention cap (latest 500 records, local-only)
- Deterministic smoke/UAT coverage for feedback capture and invalid-label rejection (`tools/smoke-test.sh`, `assistant/uat-scenarios.json`, `assistant/feature-catalog.json`)
- UAT governance change record for feedback command-surface coverage (`docs/uat-changes/2026-02-14-feedback-surface.md`)
- Response profile preference contract for chat/summarization (`auto|concise|balanced|detailed`) with config aliases (`response_profile`, `response-style`, `style`) and per-chat override (`gaia chat --response-profile ...`) (`tools/gaia-assistant.py`, `#97`)
- Memory summarization command surface with profile-aware deterministic compaction and source-traceable persistence (`gaia memory summarize`, `memory-summary-events.jsonl`) (`tools/gaia-assistant.py`, `#97`)
- Deterministic memory summarize benchmark harness and fixtures with profile-selection + source-traceability thresholds (`tools/memory-summary-benchmark.py`, `assistant/memory-summary-fixtures.json`, `make memory-summary-benchmark`)
- Deterministic smoke/UAT coverage for response-profile selection and memory summarize traceability thresholds (`tools/smoke-test.sh`, `assistant/uat-scenarios.json`, `assistant/feature-catalog.json`)
- UAT governance change record for profile + memory summarize command-surface coverage (`docs/uat-changes/2026-02-14-profile-memory-summary-surface.md`)
- Token-budget fixture contract and deterministic checker for pass/warn/block/defer + threshold-edge coverage (`assistant/token-budget-fixtures.json`, `tools/token-budget-fixtures.py`)
- Token-budget CI workflow and make target for regression gating (`.github/workflows/token-budget-enforcement.yml`, `make token-budget-fixtures`)
- Hypothesis artifact contract documentation and reference proposal/failure fixtures (`infrastructure/hypothesis-pipeline-v1.md`, `assistant/hypotheses/*.json`, `assistant/hypotheses/README.md`)
- Hold-decision hypothesis fixture and CI assertions for pass/hold/rollback decision coverage (`assistant/hypotheses/phase3-hypothesis-pipeline-v1-hold-fixture.json`, `.github/workflows/hypothesis-pipeline.yml`)
- Hypothesis pipeline CI workflow for pass-path packaging and rollback-required failure-fixture checks (`.github/workflows/hypothesis-pipeline.yml`)
- Phase 3 reliability baseline threshold contract with absolute date + baseline commit (`assistant/reliability-baseline-phase3.json`, `assistant/reliability-baseline-phase3.md`, `#87`)
- Deterministic reliability checkpoint tool for benchmark/UAT/memory-quality gate aggregation and threshold enforcement (`tools/reliability-checkpoint.py`, `make reliability-checkpoint*`)
- Reliability breach triage routing workflow with severity/owner mapping (`infrastructure/reliability-triage-workflow.md`)
- Deterministic reliability drift detector against baseline + checkpoint history with actionable severity/owner recommendations (`tools/reliability-drift.py`, `make reliability-drift*`, `#93`)
- Reliability drift report contract documentation and artifact schema (`infrastructure/reliability-drift-report-v1.md`)
- Reliability drift CI workflow with deterministic pass path and simulated drift-breach failure fixture (`.github/workflows/reliability-drift.yml`)
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
- Quality matrix harness for malicious fixtures + runtime guardrails (`make quality-matrix`, `tools/quality-matrix.py`) for lane `P2-H` (`#58`)
- Compatibility matrix baseline + reproducible renderer/checker against `vercel-labs/agent-skills` (`assistant/compatibility-matrix-baseline.json`, `assistant/compatibility-matrix.md`, `tools/compatibility-matrix.py`)
- Memory strategy/tradeoff synthesis with architecture recommendation and benchmark plan for lane `P2-I` (`research/synthesis/2026-02-gaia-memory-strategy-and-tradeoffs.md`, `#60`)
- Follow-on memory implementation issue set split into parallel lanes (`#75`, `#76`, `#77`, `#78`)
- Memory runtime command surface with local SQLite-backed CRUD store (`gaia memory add/get/list/update/delete`) for lane `#75`
- Memory retrieval command surface with deterministic ranking pipeline (`gaia memory retrieve`) for lane `#76`
- Memory policy/privacy command surface with deterministic export and capability gating (`gaia memory export`, `memory_export`) for lane `#77`
- Memory consent/retention contract enforcement matrix by memory class (`session_short`, `user_long`, `project`, `safety_audit`) for lane `#77`
- Memory delete/export evidence artifacts (`memory-tombstones.jsonl`, `memory-export-events.jsonl`, `memory-exports/*.json`) for lane `#77`
- Memory QA/red-team harness with deterministic poisoning/leakage fixture suite and threshold gate (`assistant/memory-quality-fixtures.json`, `tools/memory-quality-matrix.py`, `make memory-quality`) for lane `#78`
- Memory retrieval benchmark fixture set + threshold gate (`assistant/memory-retrieval-fixtures.json`, `tools/memory-benchmark.py`, `make memory-benchmark`)
- Deterministic smoke/UAT coverage for retrieval ranking and benchmark threshold enforcement (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- UAT change record for memory retrieval/ranking coverage governance (`docs/uat-changes/2026-02-13-memory-retrieval-surface.md`)
- Deterministic smoke/UAT coverage for memory policy/privacy controls and export/delete evidence guarantees (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- UAT change record for memory policy/privacy surface governance (`docs/uat-changes/2026-02-13-memory-policy-privacy-surface.md`)
- Deterministic smoke/UAT coverage for memory QA/red-team harness regressions (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- UAT change record for memory QA/red-team harness governance (`docs/uat-changes/2026-02-13-memory-qa-redteam-harness.md`)
- Memory UAT/smoke coverage and governance change record (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`, `docs/uat-changes/2026-02-13-memory-surface.md`)
- Versioned skill metadata contract publication (`infrastructure/skill-contract-v1.md`)
- Versioned sandbox contract publication (`infrastructure/sandbox-contract-v1.md`)
- Deterministic UAT + smoke coverage for the new scheduler command paths (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for reminder lifecycle controls (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for skills runtime list/inspect command paths (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for skills validation pass/block flows (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for sandbox profile/escalation command paths (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for policy decision/allowlist command paths and sandbox bypass checks (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for trace filtering and correlation-id audit flows (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- Deterministic UAT + smoke coverage for quality-matrix guardrails (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/smoke-test.sh`)
- UAT change record for scheduler CLI coverage governance (`docs/uat-changes/2026-02-08-scheduler-surface.md`)
- UAT change record for reminder CLI coverage governance (`docs/uat-changes/2026-02-13-reminder-surface.md`)
- UAT change record for skills runtime CLI coverage governance (`docs/uat-changes/2026-02-13-skills-runtime-surface.md`)
- UAT change record for skills validation CLI coverage governance (`docs/uat-changes/2026-02-13-skills-validation-surface.md`)
- UAT change record for sandbox CLI coverage governance (`docs/uat-changes/2026-02-13-sandbox-surface.md`)
- UAT change record for policy engine CLI coverage governance (`docs/uat-changes/2026-02-13-policy-surface.md`)
- UAT change record for trace schema/filter coverage governance (`docs/uat-changes/2026-02-13-traces-surface.md`)
- UAT change record for quality-matrix guardrail coverage governance (`docs/uat-changes/2026-02-13-quality-matrix-surface.md`)
- Roadmap/backlog reassessment issue template (`.github/ISSUE_TEMPLATE/roadmap-backlog-review.yml`)
- Research synthesis playbook for backlog realism reviews (`research/synthesis/2026-02-roadmap-backlog-research-playbook.md`)
- Incident/postmortem docs and reusable template (`docs/incidents/README.md`, `docs/incidents/postmortem-template.md`)
- Nightly benchmark trend workflow (`.github/workflows/benchmark-nightly.yml`) with history/summary updates
- Dedicated quality-matrix CI workflow (`.github/workflows/quality-matrix.yml`) for malicious-fixture regressions
- Benchmark trend tool and local command (`tools/benchmark-trend.py`, `make benchmark-trend`)
- Skills + sandbox enablement synthesis from Agent Skills, Claude Code, and Codex docs (`research/synthesis/2026-02-skills-and-sandbox-enablement.md`)
- Skill onboarding security validation synthesis with anti-malicious checks (`research/synthesis/2026-02-skill-onboarding-security-validation.md`)
- Phase 2 lane implementation plan packets with architecture-delta requirements (`infrastructure/phase2-lane-implementation-plans.md`)
- Memory-management research lane issue (`#60`) for options/tradeoffs before implementation
- Phase 2 planner-round execution artifact with merge order, integration sync report, and docs freshness evidence (`infrastructure/planning-round-2026-02-08-phase2.md`)
- Planning/research/doc/review templates for consistent role execution quality (`infrastructure/*-template.md`)
- New role skills: planner, researcher, technical writer, security reviewer, QA evaluator, release manager, incident responder, integration coordinator, privacy-memory steward
- Agent execution protocol with autonomous issue selection, skill-trigger matrix, output contract, and operator prompt templates (`infrastructure/agent-execution-protocol.md`)
- Post-Phase-2 reassessment planning-round artifact and kickoff queue decomposition for Phase 3 (`infrastructure/planning-round-2026-02-13-post-phase2-reassessment.md`, `#84`)
- Phase 3 kickoff issue set for evidence rubric, hypothesis pipeline v1, and reliability baseline checkpoint (`#85`, `#86`, `#87`)
- Post-Phase-3-kickoff reassessment planning-round artifact and two-wave execution queue (`infrastructure/planning-round-2026-02-13-post-phase3-kickoff-reassessment.md`, `#92`)
- Next Phase 3 execution queue issue set for drift detection, canary gate, token-budget enforcement, feedback capture, and profile/summarization follow-on (`#93`, `#94`, `#95`, `#96`, `#97`)
- Post-Phase-3-delivery stabilization planning-round artifact with refactor/docs/release sequencing and dead-artifact triage scope (`infrastructure/planning-round-2026-02-14-post-phase3-delivery-stabilization.md`, `#104`)
- Post-Phase-3-delivery issue set for dead-code audit, assistant modular refactor, live-preview refresh, and npm release `0.3.0` (`#105`, `#106`, `#107`, `#108`)
- User-intent signal architecture planning-round artifact for privacy-preserving self-evolution inputs and skill-first gap routing (`infrastructure/planning-round-2026-02-14-user-intent-signal-architecture.md`, `#110`)
- Signal-driven self-evolution follow-on issue set for unmet-intent extraction, skill-first triage, and hypothesis integration (`#111`, `#112`, `#113`)
- Continuous security-validation research lane for broad-source skill import hardening against prompt-injection and malicious instruction attacks (`#115`)
- Dead-code/dead-artifact audit report with keep/remove/defer classification and follow-up mapping (`infrastructure/dead-code-artifact-audit-2026-02-14.md`, `#105`)
- Assistant CLI parser modularization via extracted parser builder module (`tools/gaia_assistant_parser.py`) while preserving stable runtime entrypoint (`tools/gaia-assistant.py`) (`#106`)
- Refreshed live-preview terminal/animated assets for current assistant command surfaces (response profiles, feedback capture, memory summarize, traces) (`assistant/assets/gaia-assistant-terminal.svg`, `assistant/assets/gaia-assistant-demo-animated.svg`, `#107`)
- Release-readiness and QA evaluation evidence reports for npm `0.3.0` go/no-go and rollback-safe publish gating (`infrastructure/release-readiness-2026-02-14-v0.3.0.md`, `infrastructure/qa-evaluation-2026-02-14-v0.3.0.md`, `#108`)

### Changed
- PR template now includes explicit self-evolution applicability gating and required evidence fields (`.github/pull_request_template.md`)
- Planning/release/contributor/protocol workflow docs now reference the self-evolution evidence rubric gate (`infrastructure/planning-round-template.md`, `infrastructure/release-readiness-template.md`, `infrastructure/contributor-playbook.md`, `infrastructure/agent-execution-protocol.md`)
- Assistant docs now include Phase 3 hypothesis pipeline usage and artifact paths (`assistant/README.md`)
- Roadmap/status priorities now reflect `#85` shipped and `#86` in progress (`ROADMAP.md`, `STATUS.md`)
- Planning/release templates now reference Phase 3 reliability thresholds and checkpoint triage requirements (`infrastructure/planning-round-template.md`, `infrastructure/release-readiness-template.md`)
- Incident workflow docs now reference reliability checkpoint artifacts for regression triage (`docs/incidents/README.md`)
- Reliability triage workflow now includes drift-report artifacts and dual-step checkpoint+drift routing guidance (`infrastructure/reliability-triage-workflow.md`, `assistant/reliability-baseline-phase3.md`, `assistant/README.md`)
- Assistant architecture docs now include Phase 2 scheduler delta details (`infrastructure/architecture.md`)
- Assistant architecture/docs now include Phase 2 reminder delta details and CLI usage (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 skills runtime delta details and contract reference (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 skill validation delta details, artifact paths, and blocking semantics (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 sandbox profile/escalation delta details and contract reference (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 policy engine delta details, command usage, and trace semantics (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 audit+trace delta details with normalized metadata and correlation filtering (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include Phase 2 quality matrix delta details, compatibility baseline, and benchmark methodology updates (`infrastructure/architecture.md`, `assistant/README.md`, `assistant/benchmarking.md`)
- Assistant architecture/docs now include memory runtime SQLite adapter contract, persistence path, and trace semantics (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include memory retrieval stage/ranking contract and benchmark enforcement details (`infrastructure/architecture.md`, `assistant/README.md`, `assistant/benchmarking.md`)
- Assistant architecture/docs now include memory policy/privacy capability model, consent/retention matrix, and delete/export evidence paths (`infrastructure/architecture.md`, `assistant/README.md`)
- Assistant architecture/docs now include memory QA/red-team harness metrics, triage workflow, and failure-gate guidance (`infrastructure/architecture.md`, `assistant/README.md`, `assistant/benchmarking.md`, `assistant/uat-policy.md`)
- Assistant architecture/docs now include Phase 3 feedback loop capture contract, persistence boundaries, and trace semantics (`infrastructure/architecture.md`, `assistant/README.md`, `README.md`)
- Assistant architecture/docs now include Phase 3 response-profile resolution and memory summarize traceability contract + benchmark gate (`infrastructure/architecture.md`, `assistant/README.md`, `assistant/uat-policy.md`)
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
- Refreshed roadmap/status to reflect completed Phase 2 delivery and queued Phase 3 kickoff priorities (`ROADMAP.md`, `STATUS.md`)
- Refreshed roadmap/status to reflect Phase 3 kickoff completion (`#87` / PR `#91`) and the newly published post-kickoff queue (`#93`-`#97`) (`ROADMAP.md`, `STATUS.md`)
- Refreshed roadmap/status to reflect the post-delivery stabilization queue and merge order (`#105`-`#108`) (`ROADMAP.md`, `STATUS.md`)
- Refreshed roadmap/status with a post-release signal-driven evolution queue (`#111`-`#113`) and privacy rule for derived user-intent signals only (`ROADMAP.md`, `STATUS.md`)
- Locked signal-driven queue decisions: broad-source skill candidates with security validation gates, default-on signal capture with opt-out, and 90-day derived-signal retention (`ROADMAP.md`, `STATUS.md`, `#111`, `#112`, `#113`)
- Refreshed roadmap/status to reflect dead-code/dead-artifact audit delivery and remaining stabilization merge order (`ROADMAP.md`, `STATUS.md`, `#105`)
- Assistant architecture/docs and package payload now declare parser module boundaries and npm compatibility for modular CLI parser construction (`infrastructure/architecture.md`, `assistant/README.md`, `package.json`, `#106`)
- Refreshed root/assistant README live-preview references with explicit source-of-truth asset mapping for docs freshness (`README.md`, `assistant/README.md`, `#107`)

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
