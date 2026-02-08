# Phase 2 Planning Round - 2026-02-08

Updated: February 8, 2026
Coordinator: Codex (planner main role)
Activated sub-roles: `gaia-planner`, `gaia-integration-coordinator`,
`gaia-technical-writer`

## 1. Planning Question

- Decision to make: define execution order, ownership guidance, and integration
  boundaries for Phase 2 lanes `P2-A` to `P2-I`.
- Decision deadline: February 9, 2026 (before first lane implementation PRs).
- Scope boundary: planning and coordination only; no lane implementation in this
  round.

## 2. Inputs Reviewed

- `ROADMAP.md`: Phase 2 lane map, shared contract freeze requirement, dependency
  notes.
- `STATUS.md`: no lane claims yet; all Phase 2 lanes in `Next Up`.
- `CHANGELOG.md`: protocol, lane-plan packet requirements, and role matrix
  recently added.
- `infrastructure/phase2-lane-implementation-plans.md`: architecture deltas and
  done criteria per lane.
- Issues/PRs:
  - Open lane issues: `#51`, `#52`, `#53`, `#54`, `#55`, `#56`, `#57`, `#58`,
    `#60`
  - Open PRs: none

## 3. Current State Snapshot

- Shipped:
  - Phase 1 assistant/runtime hardening complete; npm release
    `@gaia-minds/assistant-cli@0.2.0` shipped on February 8, 2026.
- In progress:
  - No active lane claims.
- Blocked:
  - No explicit blockers, but no shared contract freeze PR exists yet.
- Risk hotspots:
  - Contract drift across `P2-C`, `P2-D`, `P2-F`, and `P2-G` if contract-first
    sequencing is skipped.
  - Sandbox behavior ambiguity across `P2-E`, `P2-F`, and `P2-H` without a
    published approval-event schema.
  - No active owner declarations in lane issues increases collision risk.

## 4. Proposed Work Items

### Lane `P2-C` (`#53`) - Skill Contract Freeze and Runtime Baseline

- Scope and non-goals:
  - Scope: publish the v1 skill metadata/capability/trace contract and ship
    `gaia skills list/inspect`.
  - Non-goal: security validation pipeline (belongs to `P2-D`).
- Architecture deltas:
  - Add registry/index and lazy instruction loading path.
  - Add contract version identifier to skill metadata model.
- Validation plan:
  - Fixture loading tests (valid/invalid skill packs).
  - CLI contract tests for deterministic list/inspect output.
- Rollback/fallback:
  - Keep current non-runtime skill behavior behind feature flag if contract
    regressions appear.
- Acceptance criteria:
  - Versioned skill contract docs merged and referenced by dependent lanes.
- Owner recommendation:
  - Contributor with CLI/runtime parsing experience.

### Lane `P2-E` (`#55`) - Sandbox Contract Freeze and Profile Enforcement

- Scope and non-goals:
  - Scope: publish sandbox profile names, escalation rules, and approval-event
    schema; enforce default least privilege.
  - Non-goal: policy decision model (belongs to `P2-F`).
- Architecture deltas:
  - Add runner abstraction for `read-only` and `workspace-write`.
  - Add escalation event model with explicit approval record.
- Validation plan:
  - Filesystem/network policy tests.
  - Escalation decision logging tests.
- Rollback/fallback:
  - Force `read-only` fallback profile if `workspace-write` checks fail.
- Acceptance criteria:
  - All execution paths carry explicit sandbox profile and escalation event data.
- Owner recommendation:
  - Contributor with sandbox/security implementation experience.

### Lane `P2-A` (`#51`) - Scheduler Core

- Scope and non-goals:
  - Scope: recurring scheduler primitives, durable schedule store, idempotent
    run keys.
  - Non-goal: reminder UX and user-facing reminder semantics (belongs to
    `P2-B`).
- Architecture deltas:
  - Scheduler service and persisted schedule registry.
- Validation plan:
  - Recurrence math tests and restart recovery tests.
- Rollback/fallback:
  - Disable recurring schedules and preserve one-shot execution if persistence
    path regresses.
- Acceptance criteria:
  - Jobs survive restart and skip duplicates via idempotency.
- Owner recommendation:
  - Contributor with time/recurrence and persistence experience.

### Lane `P2-D` (`#54`) - Skill Validation Security Gate

- Scope and non-goals:
  - Scope: `gaia skills validate`, static checks, provenance/hash artifacts,
    blocking on high-severity findings.
  - Non-goal: baseline skill browsing UX (belongs to `P2-C`).
- Architecture deltas:
  - Validator pipeline with severity model and report artifact storage.
- Validation plan:
  - Malicious fixture corpus tests and fail-closed behavior tests.
- Rollback/fallback:
  - Keep validation command optional but warn-only if blocker bug is found;
    preserve full report output.
- Acceptance criteria:
  - High-severity findings block onboarding with reproducible report artifacts.
- Owner recommendation:
  - Contributor with security validation and static analysis experience.

### Lane `P2-F` (`#56`) - Policy Engine v1

- Scope and non-goals:
  - Scope: centralized allow/confirm/deny decisions by risk/source/scope and
    per-skill tool allowlists.
  - Non-goal: sandbox runtime internals (belongs to `P2-E`).
- Architecture deltas:
  - Pre-tool policy evaluation layer and policy schema definitions.
- Validation plan:
  - Decision-table tests and policy bypass regression tests.
- Rollback/fallback:
  - Fail-safe fallback to `confirm` for ambiguous policy states.
- Acceptance criteria:
  - Every automated action emits explainable policy decision metadata.
- Owner recommendation:
  - Contributor with policy engine and authorization model experience.

### Lane `P2-B` (`#52`) - Reminders and Cadence

- Scope and non-goals:
  - Scope: reminder model, cadence settings, pause/resume/snooze controls.
  - Non-goal: scheduler core internals (belongs to `P2-A`).
- Architecture deltas:
  - Reminder domain model integrated with scheduler events.
- Validation plan:
  - Quiet-hours and snooze behavior tests.
- Rollback/fallback:
  - Disable proactive reminder delivery while preserving reminder CRUD data.
- Acceptance criteria:
  - Reminder behavior is policy-compliant and traceable.
- Owner recommendation:
  - Contributor with user workflow and runtime integration experience.

### Lane `P2-G` (`#57`) - Unified Audit and Traces

- Scope and non-goals:
  - Scope: unified trace schema for skill source/hash, policy decisions,
    sandbox profile, approval events, and incident linkage.
  - Non-goal: malicious fixture authoring (belongs to `P2-H`).
- Architecture deltas:
  - Extend trace schema, add correlation IDs, and query helpers.
- Validation plan:
  - Schema compatibility tests and UAT metadata completeness assertions.
- Rollback/fallback:
  - Backward-compatible trace writer with dual-field output during migration.
- Acceptance criteria:
  - All skill-triggered runs include complete trace metadata.
- Owner recommendation:
  - Contributor with observability/schema migration experience.

### Lane `P2-H` (`#58`) - Quality Harness and Compatibility Matrix

- Scope and non-goals:
  - Scope: malicious fixtures, UAT expansion, and compatibility matrix baselines
    (including external skill bundle patterns).
  - Non-goal: runtime feature implementation.
- Architecture deltas:
  - Add fixture corpus and CI matrix coverage for validation/policy/sandbox
    paths.
- Validation plan:
  - CI matrix verification and failure triage outputs.
- Rollback/fallback:
  - Keep strict fixture classes enabled; quarantine flaky fixture classes behind
    explicit skip list with owner + ETA.
- Acceptance criteria:
  - CI blocks regressions for malicious and incompatible skill scenarios.
- Owner recommendation:
  - Contributor with QA harness and CI matrix experience.

### Lane `P2-I` (`#60`) - Memory Research Gate

- Scope and non-goals:
  - Scope: produce options matrix and recommendation for memory architecture,
    privacy controls, and benchmark approach.
  - Non-goal: memory runtime implementation.
- Architecture deltas:
  - Research-only deltas: proposed architecture changes documented, not shipped.
- Validation plan:
  - Evidence quality review: at least three viable options and explicit
    migration/rollback strategy.
- Rollback/fallback:
  - Maintain current local session-memory-only runtime until follow-on design is
    approved.
- Acceptance criteria:
  - Recommended memory architecture with implementation backlog proposals.
- Owner recommendation:
  - Contributor with retrieval systems and privacy/safety analysis experience.

## 5. Dependencies and Merge Order

- Shared contracts:
  - Skill contract (`P2-C`) and sandbox contract (`P2-E`) must be merged first.
- Item dependencies:
  - `P2-D` depends on `P2-C` + `P2-E`.
  - `P2-F` depends on `P2-C` + `P2-E`.
  - `P2-G` depends on `P2-C` + `P2-E` + `P2-F`.
  - `P2-B` depends on `P2-A` scheduler event contracts.
  - `P2-H` runs continuously against all lane outputs.
  - `P2-I` is independent research, feeds follow-on implementation.
- Parallelization notes:
  - Wave 0 (contract freeze): `P2-C`, `P2-E`.
  - Wave 1 (parallel after contract freeze): `P2-A`, `P2-D`, `P2-F`, `P2-H`,
    `P2-I`.
  - Wave 2: `P2-B` (after `P2-A` event contract confirmation), `P2-G` (after
    policy and sandbox/skill contracts stabilize).
  - Final hardening: `P2-H` regression sweep across merged lane set.

## 6. Unclear Items Requiring Research

- Unknown: DST/timezone boundary policy for recurring schedule execution.
  - Why blocked: can cause duplicate or skipped runs around offset changes.
  - Required research output: timezone policy note + deterministic recurrence
    examples.
- Unknown: provenance/hash strategy for remote skill bundles.
  - Why blocked: affects `P2-D` artifact format and reproducibility.
  - Required research output: canonical source-hash schema with verification
    algorithm.
- Unknown: external compatibility matrix scope depth for `vercel-labs/agent-skills`.
  - Why blocked: fixture coverage breadth affects `P2-H` CI runtime/cost.
  - Required research output: minimum viable matrix tiers and sampling strategy.
- Unknown: privacy retention/deletion policy defaults for memory lane follow-up.
  - Why blocked: `P2-I` recommendation must align with policy/sandbox/audit
    controls.
  - Required research output: retention policy matrix mapped to policy engine
    controls.

## 7. State Sync Checklist

- [x] `STATUS.md` reviewed; no change because lane queue and claim state are
  still accurate (no lane claim started in this planner round).
- [x] `ROADMAP.md` reviewed; no change because Phase 2 lane decomposition and
  dependency order already match this planning decision.
- [x] `CHANGELOG.md` updated to record this planning artifact.
- [x] Coordination issue comment posted.

## 8. Exit

- Final decision:
  - Start Phase 2 execution with contract-first sequencing:
    - Merge `P2-C` and `P2-E` contract PRs first.
    - Start Wave 1 lanes immediately after contract freeze.
    - Gate Wave 2 and final hardening on dependency completion.
- Next review date: February 11, 2026.
- Open follow-ups:
  - Assign owners to each lane issue and attach per-lane implementation-plan
    packets before coding starts.
  - Re-run integration sync once first contract PRs are open.

## 9. Integration Sync Report (`gaia-integration-coordinator`)

### 9.1 Lanes in Scope

- Lanes/issues: `#51`, `#52`, `#53`, `#54`, `#55`, `#56`, `#57`, `#58`, `#60`
- Coordinator: Codex planner run (February 8, 2026)

### 9.2 Contract Compatibility

| Contract | Producers | Consumers | Status | Notes |
| --- | --- | --- | --- | --- |
| Skill metadata/capability/trace identifiers | `P2-C` | `P2-D`, `P2-F`, `P2-G`, `P2-H` | Pending freeze | Must version contract and publish test fixtures. |
| Sandbox profiles/escalation approval schema | `P2-E` | `P2-D`, `P2-F`, `P2-G`, `P2-H` | Pending freeze | Must lock profile names and approval event schema. |
| Policy decision schema | `P2-F` | `P2-G`, `P2-H` | Pending producer | Required before final trace schema lock in `P2-G`. |
| Scheduler event contract | `P2-A` | `P2-B` | Pending producer | Must define recurrence/idempotency fields for reminder triggers. |

### 9.3 Merge Order

- Proposed order:
  1. `P2-C` and `P2-E` (contract freeze PRs)
  2. `P2-A`, `P2-D`, `P2-F`, `P2-H`, `P2-I` (parallel wave)
  3. `P2-B` and `P2-G`
  4. `P2-H` final hardening sweep
- Rationale:
  - Consumers should not implement against unstable contracts.
  - Quality lane runs continuously and catches integration regressions early.

### 9.4 Integration Risks

- Risk: contract version mismatch between lane branches.
  - Impact: broken integration and rework in `P2-D`, `P2-F`, `P2-G`.
  - Mitigation: enforce versioned contract fixtures and PR notes with contract
    revision IDs.
- Risk: incomplete policy decision payload for trace unification.
  - Impact: `P2-G` may ship incompatible schema.
  - Mitigation: require `P2-F` decision payload examples before `P2-G` schema
    freeze.
- Risk: scheduler event schema drift during reminders integration.
  - Impact: reminder misfires or duplicate reminders.
  - Mitigation: freeze scheduler event fields before `P2-B` implementation PR
    merge.

### 9.5 Sync Actions

- Required PR updates:
  - Each lane PR must include contract version references in PR notes.
  - Dependent lanes must pin against the latest merged contract revision.
- Cross-lane tests:
  - `P2-D` + `P2-E` sandbox dry-run validation fixtures.
  - `P2-F` + `P2-G` policy decision trace schema checks.
  - `P2-A` + `P2-B` reminder trigger integration tests.
- Next sync date: February 11, 2026 (or earlier after first contract PR merges).

## 10. Docs Freshness Report (`gaia-technical-writer`)

### 10.1 Audit Scope

- Folders/files audited:
  - `README.md`
  - `ROADMAP.md`
  - `STATUS.md`
  - `CHANGELOG.md`
  - `infrastructure/agent-execution-protocol.md`
  - `infrastructure/phase2-lane-implementation-plans.md`
- Audit date: February 8, 2026
- Reviewer: Codex planner run

### 10.2 Source-of-Truth Map

| Doc | Source of Truth | Last Checked |
| --- | --- | --- |
| `README.md` | Runtime status + onboarding protocol docs | February 8, 2026 |
| `ROADMAP.md` | Phase sequencing and lane dependencies | February 8, 2026 |
| `STATUS.md` | Current sprint shipped/in-progress/next-up state | February 8, 2026 |
| `CHANGELOG.md` | Unreleased planning/protocol updates | February 8, 2026 |

### 10.3 Drift Findings

| Severity | File | Drift Description | Required Fix |
| --- | --- | --- | --- |
| Medium | `infrastructure/` | No committed planning-round artifact for current Phase 2 execution decision. | Add this planning-round artifact and link from coordination issue. |

### 10.4 Updates Applied

- File: `infrastructure/planning-round-2026-02-08-phase2.md`
- Change summary: added execution-ready planning packet, integration sync
  report, and docs freshness evidence for Phase 2 lanes.
- Validation run: `make generate-indexes` (if needed), `make check-all`.

### 10.5 Remaining Docs Debt

- Item: Add lane-owner attribution updates once contributor claims begin.
- Why not fixed now: no lane claim comments or assignees exist yet.
- Follow-up issue: lane issues `#51` to `#58`, `#60` (owner claim comments
  required before implementation).

### 10.6 State Sync Checklist

- [x] `STATUS.md` reviewed/updated
- [x] `ROADMAP.md` reviewed/updated
- [x] `CHANGELOG.md` reviewed/updated
- [x] `skills/INDEX.md` and `infrastructure/INDEX.md` regenerated when needed
