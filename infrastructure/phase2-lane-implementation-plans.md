# Phase 2 Lane Implementation Plans

Updated: February 8, 2026

## Purpose

This document provides execution-ready implementation plans for the Phase 2
parallel lanes. It exists to make agent offloading reliable: every lane has a
clear scope, architecture delta, validation plan, and done criteria.

## Required Plan Packet (Per Lane Issue)

Before coding starts, each lane issue must include an implementation-plan
comment with:

1. Scope and non-goals
2. Architecture deltas (modules, interfaces, data/config schema)
3. CLI/API surfaces added or changed
4. Validation commands and test coverage
5. Rollback/fallback plan
6. Dependencies on other lanes/contracts
7. Open risks and unresolved questions
8. State sync impact (`STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`)

## Architecture Update Rule

Any PR that changes runtime architecture must update `infrastructure/architecture.md`
with a `Phase 2 delta` section for that lane. If no architecture change is made,
the PR notes must state `No architecture delta`.

## Shared Contracts (Freeze First)

- Skill contract: skill metadata, capability declarations, trace identifiers
- Sandbox contract: profile names, escalation rules, approval event schema

## Lane Plans

### P2-A Scheduler (`#51`)

- Objective: recurring/scheduled execution runtime with durable state.
- Architecture changes:
  - Add scheduler service (`assistant` runtime loop + trigger dispatcher).
  - Add persisted schedule store (local DB/file-backed registry).
  - Add schedule event model with deterministic next-run calculation.
- CLI surface:
  - `gaia schedule create/list/update/cancel`.
- Validation:
  - Unit tests for recurrence math/timezone handling.
  - Restart/recovery test proving schedules survive process restarts.
  - Smoke test for one-shot + recurring task execution.
- Done criteria:
  - Schedules execute at expected times with persisted state and traces.

### P2-B Reminders (`#52`)

- Objective: proactive reminders with user-controlled cadence.
- Architecture changes:
  - Add reminder domain model and reminder executor.
  - Integrate reminder triggers with scheduler events from `P2-A`.
  - Add user preference fields for cadence/quiet-hours defaults.
- CLI surface:
  - `gaia reminders add/list/snooze/dismiss`.
- Validation:
  - Reminder scheduling tests (including snooze and quiet-hours).
  - End-to-end reminder flow in smoke/UAT suite.
- Done criteria:
  - Reminders trigger, respect user cadence controls, and are auditable.

### P2-C Skills Runtime (`#53`)

- Objective: first-class skill discovery/loading (`list`, `inspect`).
- Architecture changes:
  - Add skill registry/index model for local/project skill sources.
  - Add loader that reads metadata eagerly and instructions lazily.
  - Define compatibility checks for supported skill schema versions.
- CLI surface:
  - `gaia skills list`
  - `gaia skills inspect <skill-id>`
- Validation:
  - Fixture-based loading tests across valid/invalid skill packages.
  - CLI output contract tests.
- Done criteria:
  - Skills are discoverable, inspectable, and source/provenance visible.

### P2-D Skill Validation (`#54`)

- Objective: security and compatibility gate before skill activation.
- Architecture changes:
  - Add validator pipeline (schema, metadata, static checks, policy fit).
  - Add finding severity model (`info/warn/high/critical`).
  - Store validation artifacts for audit/reporting.
- CLI surface:
  - `gaia skills validate <path-or-skill-id>`.
- Validation:
  - Malicious/edge fixture corpus with expected findings.
  - Blocking behavior tests for high-severity failures.
- Done criteria:
  - Skills that fail high-severity checks cannot be onboarded.

### P2-E Sandbox (`#55`)

- Objective: safe code execution profiles with explicit escalation approvals.
- Architecture changes:
  - Add sandbox runner abstraction with `read-only` and `workspace-write`.
  - Add approval-event workflow for escalations.
  - Enforce default network-deny policy unless explicitly enabled.
- CLI/API surface:
  - Sandbox profile selection exposed in execution path.
- Validation:
  - Tests for filesystem/network policy enforcement.
  - Escalation prompt + decision logging tests.
- Done criteria:
  - No unapproved escalations; sandbox profile always traceable.

### P2-F Policy Engine (`#56`)

- Objective: centralized action gating by risk/source/scope + per-skill allowlists.
- Architecture changes:
  - Add policy evaluation layer executed before tool invocation.
  - Add policy schema for capability risk levels and skill allowlists.
  - Integrate user scope and approval requirements into decisions.
- CLI/API surface:
  - Policy decision traces visible through trace tooling.
- Validation:
  - Decision-table tests for allow/confirm/deny paths.
  - Regression tests for bypass attempts and conflicting rules.
- Done criteria:
  - All automated actions route through policy engine with explicit decisions.

### P2-G Audit and Traces (`#57`)

- Objective: unify trace schema for skills, policy, sandbox, and incidents.
- Architecture changes:
  - Extend trace schema with skill/source/hash/policy/sandbox fields.
  - Add correlation IDs linking runs, approvals, and incident reports.
  - Add trace query/report helpers for incident triage.
- CLI surface:
  - `gaia traces` enhancements for filtering by skill/sandbox/policy outcome.
- Validation:
  - Schema compatibility tests and migration checks.
  - UAT assertions that every skill-triggered run includes required metadata.
- Done criteria:
  - 100% of skill-triggered runs emit complete trace metadata.

### P2-H Quality (`#58`)

- Objective: harden system quality against malicious or incompatible skills.
- Architecture changes:
  - Add malicious-skill fixture set and compatibility matrix test data.
  - Expand UAT and benchmark harness for skill/sandbox/policy flows.
  - Add regression gates for validation/sandbox escape scenarios.
- Validation:
  - CI matrix across fixture classes and supported skill bundles.
  - Failure triage output suitable for issue automation.
- Done criteria:
  - Quality suite reliably blocks regressions in validation/policy/sandbox.

### P2-I Memory Research (`#60`)

- Objective: produce a research-backed memory-management recommendation before
  implementation.
- Architecture research scope:
  - Memory taxonomy (session, long-term user, project, safety/audit memory).
  - Storage/retrieval alternatives and migration paths.
  - Security/privacy controls (retention, consent, deletion guarantees).
  - Failure modes (poisoning, stale recall, privacy leakage).
- Deliverables:
  - Synthesis report in `research/synthesis/` with option matrix.
  - Proposed architecture deltas and follow-on implementation issues.
  - Benchmark approach for memory quality and safety.
- Done criteria:
  - One recommended architecture with explicit tradeoffs and rollback path.

## Dependency Summary

- `P2-A`: independent
- `P2-B`: depends on `P2-A` event contracts
- `P2-C`: independent (must publish skill contract)
- `P2-D`: depends on `P2-C` contract
- `P2-E`: independent (must publish sandbox contract)
- `P2-F`: depends on `P2-C` + `P2-E` contracts
- `P2-G`: depends on `P2-C` + `P2-E` + `P2-F` outputs
- `P2-H`: validates all lanes continuously
- `P2-I`: independent research lane; feeds later memory implementation lanes
