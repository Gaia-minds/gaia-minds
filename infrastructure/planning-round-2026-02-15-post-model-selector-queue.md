# Planning Round: Post-Model-Selector Queue Reset (2026-02-15)

Updated: February 15, 2026
Main role: `planner`
Activated sub-roles: `gaia-planner`, `gaia-researcher`, `gaia-technical-writer`, `gaia-integration-coordinator`

## 1. Planning Question

- Decision to make: What is the next executable queue after the model-selector delivery lane, including immediate merge unblock work and follow-on assistant priorities?
- Decision deadline: February 15, 2026 (planning round close)
- Scope boundary: planning/decomposition/state sync only (no implementation in this lane)

## 2. Inputs Reviewed

- `ROADMAP.md`: Phase 3 status, delivered queue, and pending next-wave gap
- `STATUS.md`: sprint queue currently empty, planning round requested
- `CHANGELOG.md`: release history and unreleased section baseline
- `infrastructure/planning-round-template.md`
- `skills/gaia-planner/SKILL.md`
- Open issues/PRs:
  - issue `#142`
  - PR `#143` (open; failing `self-evolution-evidence` and `uat-policy`)
- CI failure evidence for PR `#143`:
  - `self-evolution-evidence`: missing required applicability checklist lines in PR body
  - `uat-policy`: missing `docs/uat-changes/*` record and missing substantial `## UAT Change Justification` section

## 3. Current State Snapshot

- Shipped:
  - governance/onboarding stabilization queue and npm `v0.4.0` release are delivered
  - provider model selector implementation is complete in PR `#143` pending merge gates
- In progress:
  - `#142` via PR `#143`
- Blocked:
  - PR `#143` merge blocked by policy checks (`self-evolution-evidence`, `uat-policy`)
- Risk hotspots:
  - runtime failure path on provider quota exhaustion remains unmitigated
  - provider model discovery behavior differs by auth path (live vs curated) and needs explicit contract
  - no first-class model-catalog inspection command for operators

## 4. Proposed Work Items

### Item `#142` closeout - merge gate remediation for PR `#143`

- Title: Close CI policy gates and merge provider model selector lane
- Scope and non-goals:
  - scope: satisfy failing CI requirements (PR body checklist + UAT change record/justification), rerun checks, merge
  - non-goal: feature expansion beyond merged PR scope
- Architecture deltas:
  - none expected beyond policy-doc/compliance metadata updates
- Validation plan:
  - CI green on PR `#143`
  - `make check-all`
- Rollback/fallback:
  - amend policy/docs metadata only; no runtime rollback expected
- Acceptance criteria:
  - PR `#143` merged and issue `#142` closed
- Owner recommendation:
  - contributor with `gaia-technical-writer` and `gaia-qa-evaluator`

### Item `#144` - provider model discovery contract research

- Title: Research provider model discovery contracts (Codex/Claude/OpenAI/Anthropic/OpenRouter)
- Scope and non-goals:
  - scope: define authoritative discovery contract and fallback policy
  - non-goal: command/runtime implementation
- Architecture deltas:
  - research artifact only
- Validation plan:
  - source-backed synthesis doc in `research/synthesis/`
  - `make check-all` if docs/indexes changed
- Rollback/fallback:
  - not applicable (research lane)
- Acceptance criteria:
  - implementation-ready contract for follow-on lanes with explicit unknowns
- Owner recommendation:
  - contributor with `gaia-researcher`

### Item `#145` - provider model catalog inspection command

- Title: Add provider model catalog inspection command
- Scope and non-goals:
  - scope: expose `gaia models list`-style command with provider filter, source transparency, and JSON output
  - non-goal: runtime failover logic
- Architecture deltas:
  - parser/runtime command extension and catalog-helper reuse
- Validation plan:
  - `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/gaia_assistant_onboarding.py`
  - `make test-smoke`
  - `make check-all`
  - UAT additions for command output contract
- Rollback/fallback:
  - command is additive and can be removed without affecting onboarding flow
- Acceptance criteria:
  - operators can inspect model options and source tags (`live` vs `curated`) deterministically
- Owner recommendation:
  - contributor with `gaia-qa-evaluator` and `gaia-technical-writer`

### Item `#146` - runtime failover for quota/auth hard failures

- Title: Add runtime failover for provider quota/auth hard failures
- Scope and non-goals:
  - scope: deterministic fallback on selected hard-error classes (for example quota exhaustion)
  - non-goal: opaque or unbounded retry loops
- Architecture deltas:
  - runtime provider-selection/failure path + fallback policy config
- Validation plan:
  - deterministic failure fixture coverage
  - `make test-smoke`
  - `make check-all`
  - UAT evidence for fallback visibility
- Rollback/fallback:
  - config-gated disable switch to return to strict single-provider mode
- Acceptance criteria:
  - fallback attempts are policy-bounded, logged, and traceable
- Owner recommendation:
  - contributor with required gates `gaia-security-reviewer`, `gaia-qa-evaluator`

### Item `#147` - model effort selector

- Title: Add model effort selector across onboarding/config/runtime
- Scope and non-goals:
  - scope: normalized effort preference contract and propagation where supported
  - non-goal: provider-specific tuning beyond normalized effort surface
- Architecture deltas:
  - config schema + parser flags + runtime request wiring
- Validation plan:
  - targeted compile checks
  - smoke/UAT coverage for effort selection/propagation
  - `make check-all`
- Rollback/fallback:
  - effort remains optional; unsupported providers no-op with explicit info output
- Acceptance criteria:
  - user can set effort and runtime behavior is deterministic across providers
- Owner recommendation:
  - contributor with `gaia-qa-evaluator` and `gaia-integration-coordinator`

## 5. Dependencies and Merge Order

- Shared contracts:
  - model catalog/discovery contract from `#144` feeds `#145` and `#147`
  - fallback/error taxonomy from `#146` should align with model/provider contract language used in docs
- Item dependencies:
  - `#142` closeout is first priority (unblocks current sprint carry-over)
  - `#145` depends on `#144` output for provider contract correctness
  - `#147` depends on `#144` and should reuse command/schema work from `#145`
  - `#146` can run in parallel after `#142` closeout
- Parallelization notes:
  - `#145` and `#146` can execute in parallel once `#144` recommendations are published

Recommended merge order:

1. `#142` closeout (PR `#143` merge)
2. `#144` research contract
3. `#145` model catalog command
4. `#146` runtime failover
5. `#147` model effort selector

## 6. Unclear Items Requiring Research

- Unknown:
  - whether Codex CLI and Claude Code CLI expose stable machine-readable model catalogs for direct Gaia ingestion
  - normalized effort semantics that can be mapped safely across providers/models
- Why blocked:
  - CLI/provider capabilities differ by auth mode and may not expose equivalent metadata surfaces
- Required research output:
  - explicit capability matrix with recommended Gaia fallback/normalization rules (`#144`)

## 7. State Sync Checklist

- [x] `STATUS.md` updated
- [x] `ROADMAP.md` updated
- [x] `CHANGELOG.md` unchanged with reason (planning-only round; no shipped behavior delta)
- [x] Coordination issue comment posted

## 8. Exit

- Final decision:
  - execute an assistant-focused queue that closes `#142`, then lands model-discovery contract, catalog inspection, runtime failover, and effort-selection layers in sequence
- Next review date:
  - February 18, 2026
- Open follow-ups:
  - verify PR-template/policy compliance completion on `#143` before new feature lanes begin
  - reopen planning if `#144` reveals hard constraints that materially change lane sequencing
