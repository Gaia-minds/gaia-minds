# Phase 4 Kickoff: Delegation Contract v1 and Coordinator Design

Updated: February 15, 2026
Main role: `contributor`
Activated sub-roles: `gaia-researcher`, `gaia-integration-coordinator`, `gaia-technical-writer`
Source issue: `#157`

## 1. Research Question

- Question: What delegation contract and coordinator runtime design can safely unlock
  Phase 4 multi-agent execution without regressing current single-agent guarantees?
- Decision this supports: execution-ready Phase 4 kickoff decomposition.
- Constraints:
  - no runtime implementation in this lane
  - preserve constitutional/safety guardrails and existing policy/sandbox contracts
  - keep deterministic operator-facing behavior and fallback-to-single-agent defaults

## 2. Scope and Method

- In scope:
  - delegation contract v1 (`confidence`, `risk_routing`, `fallback`)
  - coordinator runtime architecture (decompose -> delegate -> synthesize)
  - implementation-ready issue decomposition with explicit dependencies
- Out of scope:
  - code implementation of multi-agent runtime
  - provider/tooling expansion beyond current contracts
- Research method:
  - repository-first synthesis from roadmap/protocol/architecture artifacts
  - option tradeoff matrix and risk-first narrowing
  - integration planning via dependency and merge-order analysis

## 3. Evidence Log

| Source | Date | Claim Supported | Notes |
| --- | --- | --- | --- |
| `ROADMAP.md` | 2026-02-15 | Phase 4 goals: delegation policy + coordinator behavior | Defines intended outcomes and exit criteria |
| `infrastructure/agent-execution-protocol.md` | 2026-02-13 | role gates, merge gates, and remote-first discipline | Constrains rollout safety and process |
| `infrastructure/planning-round-2026-02-15-post-effort-selector-queue.md` | 2026-02-15 | `#157` scope and dependency posture | Confirms this lane is design-only and parallel-safe |
| `infrastructure/architecture.md` | 2026-02-15 | current single-agent baseline and guardrail model | Establishes compatibility constraints for Phase 4 |
| `STATUS.md` | 2026-02-15 | active queue ordering and next-lane ownership | Used for decomposition sequencing |

## 4. Findings

### Facts

- Phase 4 is planned but not yet decomposed into implementation slices.
- Existing runtime safety controls are centralized in policy/sandbox/capability
  gates; Phase 4 must preserve these controls.
- Current queue already reserves `#157` for design and `#156` for release
  readiness.

### Inferences

- A contract-first rollout is required; implementing coordinator behavior before
  contract/risk routing is likely to create integration churn.
- A deterministic fallback path to single-agent execution is mandatory for safe
  initial multi-agent rollout.
- Coordinator runtime should be introduced through thin slices with explicit
  traceability to preserve diagnosability.

## 5. Options and Tradeoffs

| Option | Benefits | Risks | Cost/Complexity | Compatibility |
| --- | --- | --- | --- | --- |
| A. Minimal coordinator wrapper (no formal contract) | Fastest start | high ambiguity, inconsistent routing, weak safety evidence | Low initial / high rework | Poor |
| B. Contract-first coordinator v1 with deterministic thresholds (recommended) | clear safety envelope, testable behavior, reversible rollout | moderate upfront design overhead | Medium | Strong |
| C. Dynamic adaptive delegation (self-tuning thresholds from start) | potentially higher long-run optimization | high instability and weak interpretability in early phase | High | Low |

## 6. Recommendation

- Recommended option: **B. Contract-first coordinator v1 with deterministic thresholds**.
- Confidence level: **High**.
- Why this option:
  - balances delivery speed with explicit safety/routing guarantees
  - enables incremental implementation lanes and deterministic QA gates
  - preserves current single-agent fallback behavior as safety baseline
- Adoption criteria:
  - delegation contract evaluator exists with deterministic policy outcomes
  - coordinator execution emits complete correlation traces
  - fallback-to-single-agent path is covered in CI/UAT before default enablement
- Rollback path:
  - keep Phase 4 feature flag default-off until lanes pass quality gates
  - revert delegation routing to single-agent path without schema migration

## 7. Delegation Contract v1

### 7.1 Contract Goals

- Decide `delegate|confirm|fallback|deny` deterministically for each candidate
  delegation unit.
- Keep policy/capability/sandbox controls authoritative; delegation cannot bypass
  existing gates.
- Produce explainable, traceable decisions for every routed task.

### 7.2 Core Fields

```json
{
  "task_id": "string",
  "intent_class": "string",
  "risk_level": "low|medium|high|critical",
  "estimated_confidence": 0.0,
  "required_capabilities": ["file_read"],
  "candidate_specialists": ["research", "planning"],
  "decision": "delegate|confirm|fallback|deny",
  "decision_reason": "string",
  "fallback_strategy": "single_agent|defer"
}
```

### 7.3 Confidence Thresholds (v1)

- `low` risk:
  - `>= 0.70` -> `delegate`
  - `0.45..0.69` -> `confirm`
  - `< 0.45` -> `fallback`
- `medium` risk:
  - `>= 0.80` -> `delegate`
  - `0.60..0.79` -> `confirm`
  - `< 0.60` -> `fallback`
- `high` risk:
  - `>= 0.90` plus explicit human confirmation -> `delegate`
  - otherwise -> `confirm` or `fallback` (default `fallback`)
- `critical` risk:
  - always `deny` in v1.

### 7.4 Risk Routing and Safety Rules

- Any missing required capability -> `deny`.
- Any policy decision of `deny` -> `deny`.
- Any sandbox escalation requirement without approval -> `confirm` or `fallback`
  (default `fallback`).
- Cross-domain tasks with unresolved specialist ambiguity -> `fallback` to
  single-agent synthesis.

### 7.5 Fallback Policy

- Primary fallback: execute via current single-agent runtime path.
- Secondary fallback: defer with actionable explanation when no safe execution
  path exists.
- Failure fallback: on specialist execution failure, retry once with same
  specialist; then fallback to single-agent.

## 8. Coordinator Runtime Design (v1)

### 8.1 Control Flow

1. **Normalize request**: derive intent/risk metadata.
2. **Plan decomposition**: split into bounded sub-tasks.
3. **Rank specialists**: deterministic scoring over capability fit + confidence.
4. **Run contract evaluator**: produce `delegate|confirm|fallback|deny`.
5. **Dispatch execution**: delegate approved sub-tasks with correlation id.
6. **Synthesize outputs**: combine specialist outputs into user-facing response.
7. **Postflight scoring**: record quality/fallback reasons for future tuning.

### 8.2 Runtime Constraints

- Coordinator cannot grant capabilities; it consumes existing policy decisions.
- Coordinator must emit per-subtask and aggregate traces using shared
  correlation ids.
- Default runtime mode remains single-agent unless multi-agent mode is explicitly
  enabled by configuration.

### 8.3 Trace Requirements

- `delegation_plan_created`
- `delegation_decision`
- `specialist_dispatch`
- `specialist_result`
- `delegation_fallback`
- `delegation_synthesis`

Each event must include `correlation_id`, `task_id`, `risk_level`, `decision`,
`decision_reason`, and `fallback_strategy` where applicable.

## 9. Integration Sync Report

### 9.1 Lanes in Scope

- Lanes/issues:
  - `#157` (this design lane)
  - Phase 4 follow-on implementation lanes (`#161`, `#162`, `#163`, `#164`)
- Coordinator: @nunopratas

### 9.2 Contract Compatibility

| Contract | Producers | Consumers | Status | Notes |
| --- | --- | --- | --- | --- |
| Policy/capability gates | existing assistant runtime | coordinator + specialists | Compatible | delegation must call existing evaluator, no bypass |
| Sandbox escalation contract | existing assistant runtime | specialist execution path | Compatible | escalation still requires explicit approval |
| Trace correlation schema | existing assistant runtime | coordinator telemetry | Extend | add delegation event types while preserving schema envelope |

### 9.3 Merge Order

- Proposed order:
  1. delegation contract evaluator lane
  2. coordinator planner/registry lane
  3. execution+synthesis lane
  4. safety/QA gating lane
- Rationale:
  - lock routing contract first
  - add orchestration primitives second
  - integrate execution after interfaces stabilize
  - enforce reliability/safety regression gates before defaulting on

### 9.4 Integration Risks

- Risk: contract and runtime drift across lanes.
  - Impact: inconsistent delegation outcomes and difficult debugging.
  - Mitigation: shared fixture contract + required cross-lane check in every PR.
- Risk: specialist execution bypassing safety gates.
  - Impact: policy/sandbox regressions.
  - Mitigation: enforce centralized pre-dispatch gate and negative-path tests.

### 9.5 Sync Actions

- Required PR updates:
  - every Phase 4 implementation PR references this contract doc and declares
    compatibility/no-delta.
- Cross-lane tests:
  - contract decision table fixtures
  - fallback regression harness
  - trace correlation completeness checks
- Next sync date: February 18, 2026 (or earlier if contract assumptions change).

## 10. Implementation-Ready Decomposition

Planned follow-on issues (created from this lane):

1. `#161` Phase 4 lane A: delegation contract evaluator + fixture harness
2. `#162` Phase 4 lane B: coordinator planner + specialist registry
3. `#163` Phase 4 lane C: delegated execution and synthesis runtime path
4. `#164` Phase 4 lane D: delegation safety/QA matrix and rollout gate

Dependency order:

- `#161` -> `#162` -> `#163` -> `#164`
- D is required before enabling multi-agent mode by default.

## 11. Unknowns and Follow-Up Research

- Unknown: optimal confidence thresholds per intent class.
  - Impact: over- or under-delegation risk in early rollout.
  - Follow-up: collect bounded offline replay data before threshold tuning.
- Unknown: specialist latency/cost tradeoff for decomposition granularity.
  - Impact: degraded user latency/cost without quality gain.
  - Follow-up: add benchmark lane after C with latency/cost scorecards.

## 12. State Sync Checklist

- [x] `STATUS.md` updated
- [x] `ROADMAP.md` updated
- [x] `CHANGELOG.md` updated

## 13. Documentation Freshness Report

### 13.1 Audit Scope

- Folders/files audited:
  - `ROADMAP.md`
  - `STATUS.md`
  - `CHANGELOG.md`
  - `infrastructure/INDEX.md`
  - `infrastructure/phase4-kickoff-delegation-contract-v1.md`
- Audit date: February 15, 2026
- Reviewer: @nunopratas

### 13.2 Source-of-Truth Map

| Doc | Source of Truth | Last Checked |
| --- | --- | --- |
| `STATUS.md` | remote issue queue + current claim state | 2026-02-15 |
| `ROADMAP.md` | active execution queues and dependency order | 2026-02-15 |
| `CHANGELOG.md` | shipped/planned behavior deltas from this lane | 2026-02-15 |
| `infrastructure/INDEX.md` | generated from infrastructure docs tree | 2026-02-15 |

### 13.3 Drift Findings

| Severity | File | Drift Description | Required Fix |
| --- | --- | --- | --- |
| Medium | `ROADMAP.md` | queue did not include Phase 4 implementation issue split from `#157` | add seeded lane list + merge order |
| Medium | `STATUS.md` | active queue did not reflect `#157` execution and new Phase 4 follow-ons | update shipped/in-progress/next-up ordering |

### 13.4 Updates Applied

- File: `ROADMAP.md`
  - Change summary: marked `#157` delivered; added seeded Phase 4 implementation queue (`#161`-`#164`) and dependency order.
  - Validation run: `make generate-indexes`; `make check-all`.
- File: `STATUS.md`
  - Change summary: synced sprint status for `#157` delivery and next queue ordering.
  - Validation run: `make generate-indexes`; `make check-all`.
- File: `CHANGELOG.md`
  - Change summary: documented Phase 4 kickoff design artifact and decomposed follow-on issue set.
  - Validation run: `make check-all`.

### 13.5 Remaining Docs Debt

- Item: Phase 4 runtime user-facing docs in `assistant/README.md`.
  - Why not fixed now: no runtime implementation merged yet.
  - Follow-up issue: `#163` and `#164`.
