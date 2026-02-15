# Planning Round: Post-Effort-Selector Queue Reset (2026-02-15)

Updated: February 15, 2026
Main role: `planner`
Activated sub-roles: `gaia-planner`, `gaia-researcher`, `gaia-technical-writer`, `gaia-integration-coordinator`

## 1. Planning Question

- Decision to make: What is the next executable queue now that `#144`-`#147` are delivered and merged?
- Decision deadline: February 15, 2026 (planning round close)
- Scope boundary: planning/decomposition/state sync only (no runtime implementation in this lane)

## 2. Inputs Reviewed

- `ROADMAP.md`: Phase 3 queue status and transition point after selector/failover/effort lanes
- `STATUS.md`: sprint queue was empty after `#147` merge and required reseeding
- `CHANGELOG.md`: unreleased stream already includes delivered behavior deltas from recent lanes
- `infrastructure/planning-round-template.md`
- `skills/gaia-planner/SKILL.md`
- Open issues:
  - `#153` planning round coordinator issue
  - `#154` model capability metadata lane
  - `#155` onboarding/model-effort compatibility guardrails lane
  - `#156` npm `0.5.0` release readiness lane
  - `#157` Phase 4 kickoff design lane
- Open PRs:
  - PR `#148` planning queue PR targeting already-delivered `#144`-`#147` sequence (now stale/superseded)

## 3. Current State Snapshot

- Shipped:
  - provider discovery research, model catalog command, runtime failover, and effort selector lanes (`#144`-`#147`)
  - corresponding state/doc/UAT governance updates merged on `main`
- In progress:
  - none
- Blocked:
  - no implementation lane blocked; only stale planning PR (`#148`) requires supersession handling
- Risk hotspots:
  - model capability support remains partially heuristic in UX/runtime surfaces
  - onboarding guidance still allows invalid model+effort combinations until runtime no-op logs
  - release cadence needs explicit post-selector package checkpoint (`0.5.0`)

## 4. Proposed Work Items

### Item `#154`

- Title: Expose model capability metadata in `gaia models list`
- Scope and non-goals:
  - scope: publish normalized capability fields (`supports_effort`, `effort_levels`) with deterministic derivation/fallback provenance
  - non-goal: runtime request-path changes
- Architecture deltas:
  - model catalog payload/output contract updates in launcher command surfaces
- Validation plan:
  - `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/gaia_assistant_onboarding.py`
  - `make test-smoke`
  - `make test-uat`
  - `make check-all`
- Rollback/fallback:
  - additive metadata fields can be reverted without runtime behavior impact
- Acceptance criteria:
  - JSON + text model list outputs include capability metadata with source clarity
- Owner recommendation:
  - contributor with `gaia-researcher`, `gaia-qa-evaluator`, `gaia-technical-writer`

### Item `#155`

- Title: Add onboarding compatibility guardrails for model+effort
- Scope and non-goals:
  - scope: pre-runtime warnings/remediation for unsupported provider/model/effort combinations
  - non-goal: provider API expansion
- Architecture deltas:
  - onboarding/run startup validation and compatibility-reporting layer
- Validation plan:
  - `python3 -m py_compile tools/gaia-assistant.py tools/agent-loop.py`
  - `make test-smoke`
  - `make test-uat`
  - `make check-all`
- Rollback/fallback:
  - guardrails are additive warnings and can be disabled/reverted without API contract break
- Acceptance criteria:
  - unsupported combinations are surfaced before execution with deterministic operator guidance
- Owner recommendation:
  - contributor with `gaia-qa-evaluator`, `gaia-technical-writer`

### Item `#156`

- Title: Prepare npm release `@gaia-minds/assistant-cli@0.5.0`
- Scope and non-goals:
  - scope: readiness evidence, QA go/no-go, tag/version publish flow
  - non-goal: new feature implementation
- Architecture deltas:
  - none (release/process artifacts only)
- Validation plan:
  - `make check-all`
  - `make test-smoke`
  - `make test-uat`
  - release workflow proof commands in PR notes
- Rollback/fallback:
  - version/tag rollback path documented in readiness report before publish
- Acceptance criteria:
  - release artifacts committed and publish workflow succeeds with verified package installability
- Owner recommendation:
  - contributor with required gates `gaia-release-manager`, `gaia-qa-evaluator`

### Item `#157`

- Title: Phase 4 kickoff delegation contract and coordinator design
- Scope and non-goals:
  - scope: architecture/design package for delegation policy contract + coordinator runtime decomposition
  - non-goal: runtime implementation
- Architecture deltas:
  - design artifact only; no runtime code deltas in this lane
- Validation plan:
  - `make generate-indexes`
  - `make check-all`
- Rollback/fallback:
  - planning artifact can be superseded by later planning rounds if constraints change
- Acceptance criteria:
  - implementation-ready decomposition issues with dependency ordering and safety constraints
- Owner recommendation:
  - contributor with `gaia-researcher`, `gaia-integration-coordinator`, `gaia-technical-writer`

## 5. Dependencies and Merge Order

- Shared contracts:
  - capability metadata contract from `#154` should feed UX guardrails in `#155`
  - release lane `#156` depends on post-selector stabilization lanes (`#154`, `#155`) reaching merge-ready state
- Item dependencies:
  - `#154` -> `#155` (contract reuse)
  - `#156` after `#154` + `#155`
  - `#157` can run in parallel (design lane)
- Parallelization notes:
  - `#157` is independent and can execute while `#154`/`#155` implement

Recommended merge order:

1. `#154`
2. `#155`
3. `#157` (parallel-safe; merge when ready)
4. `#156`

## 6. Unclear Items Requiring Research

- Unknown:
  - canonical provider/model capability source for effort support remains partly heuristic
- Why blocked:
  - provider APIs do not expose a uniform capabilities contract across all runtimes
- Required research output:
  - update capability derivation rationale in `#154` with explicit source/fallback mapping and maintenance notes

## 7. State Sync Checklist

- [x] `STATUS.md` updated
- [x] `ROADMAP.md` updated
- [x] `CHANGELOG.md` unchanged with reason (planning-only lane; no shipped behavior delta)
- [x] Coordination issue comment posted

No `CHANGELOG.md` update in this planning lane: no shipped runtime behavior change.

## 8. Exit

- Final decision:
  - seed a post-selector queue focused on capability metadata, compatibility guardrails, release readiness, and Phase 4 kickoff design
- Next review date:
  - February 18, 2026
- Open follow-ups:
  - close/supersede stale planning PR `#148` once this planning round lands
  - if `#154` discovers incompatible provider capability assumptions, run a micro-planning update before `#155`
