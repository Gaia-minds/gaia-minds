# Assistant vs Framework Contributor Playbook

## Purpose

Use this playbook to decide where changes belong, validate them consistently,
and hand off work safely during parallel multi-worktree execution.

This document is the canonical `assistant vs framework` decision guide.
For onboarding and autonomous issue selection rules, see
`infrastructure/agent-execution-protocol.md`.
Use its strict main-role/sub-role matrix and mandatory merge gates.
Always perform remote-first sync before planning/claiming work.

## Track Decision Tree

1. Does the change primarily affect end-user assistant behavior or UX?
   - Yes: `assistant-track`
   - No: continue
2. Does the change primarily affect governance, policies, workflows,
   release process, CI, or contributor coordination?
   - Yes: `framework-track`
   - No: continue
3. Does the change modify both runtime behavior and framework/process surfaces?
   - Yes: mark as cross-track (`assistant-track` + `framework-track`)
   - No: choose the dominant track and explain why in PR notes

When uncertain, default to the narrower scope and open a follow-up issue for the
other track.

## Validation Matrix

| Change Type | Track Declaration | Required Validation | Required Notes |
| --- | --- | --- | --- |
| Assistant feature/runtime behavior | `assistant-track` | `make test-smoke`; relevant `gaia ...` command checks for changed surfaces | Include before/after behavior and capability policy impact |
| Framework policy/process/docs | `framework-track` | `make check-all`; run file-specific checks when applicable (for example `python3 tools/verify-resources.py` for resources) | Include governance/process rationale and migration notes |
| Self-evolution behavior/governance PR | `framework-track` or cross-track | `make check-all`; `self-evolution-evidence` workflow must pass | Include rubric evidence (`baseline`, `delta`, `thresholds`, `rollback`, `risk notes`) per `infrastructure/self-evolution-evidence-rubric.md` |
| CI/tooling/release workflow | `framework-track` | `make check-all`; dry-run or targeted command proving workflow/tool behavior | Include rollback/fallback path if automation fails |
| Cross-track change | `assistant-track` + `framework-track` | All relevant checks above in one PR, or split into two PRs | Explicitly call out coupling and merge order |

Every PR should include explicit `track declaration` and risk level.

## Risk Levels

- Low: docs-only or non-breaking internal changes with local validation.
- Medium: behavior or tooling changes with bounded blast radius.
- High: auth, permissions, release, safety/policy, or cross-track migrations.

High-risk changes should not merge without explicit maintainer review.

## Role Skill Matrix

Use the specialized skill matching your task type:

- Main roles:
  - `planner` (primary planning/backlog role)
  - `contributor` (primary execution role)
- Planning: `skills/gaia-planner/SKILL.md`
- Research: `skills/gaia-researcher/SKILL.md`
- Documentation freshness: `skills/gaia-technical-writer/SKILL.md`
- Security review: `skills/gaia-security-reviewer/SKILL.md`
- QA evaluation: `skills/gaia-qa-evaluator/SKILL.md`
- Release management: `skills/gaia-release-manager/SKILL.md`
- Incident response: `skills/gaia-incident-responder/SKILL.md`
- Integration coordination: `skills/gaia-integration-coordinator/SKILL.md`
- Memory privacy review: `skills/gaia-privacy-memory-steward/SKILL.md`

## Multi-Worktree / Multi-Agent Handoff Protocol

1. Claim issue and post implementation plan before coding.
   - Include scope/non-goals, architecture deltas, CLI/API changes, validation,
     rollback, and dependencies.
   - Use `infrastructure/phase2-lane-implementation-plans.md` as the template.
2. Create isolated worktree per issue (`/tmp/...`) and branch from latest
   `origin/main`.
3. Keep PR scope single-purpose; avoid mixing unrelated tracks.
4. Before push, run required validation from matrix and capture outputs.
5. Post handoff comment with:
   - changed files
   - validation commands + results
   - known risks and follow-ups
6. Rebase worktree branch on latest main before merge if parallel PRs merged.
7. After merge, close/refresh issue state with links to PR and remaining work.
8. Confirm state docs are updated (or no-change reason recorded):
   - `STATUS.md`
   - `ROADMAP.md`
   - `CHANGELOG.md`

If runtime architecture changed, update `infrastructure/architecture.md`. If it
did not, say `No architecture delta` in PR notes.

## Phase 4: Delegation Framework Contributor Guide

This section covers how to extend the Phase 4 multi-agent delegation framework
introduced in issues `#161`–`#164`. The framework lives in three main surfaces:

- **Contract rules** — `assistant/delegation-contract-v1-fixtures.json`
- **QA matrix** — `assistant/delegation-qa-matrix.json`
- **Specialists** — registered in `assistant/coordinator-planner-fixtures.json`
  and dispatched by `tools/gaia-assistant.py:execute_coordinator_delegation_v1`

### Adding or Modifying Contract Rules

1. Read `infrastructure/specialist-registry-contract-v1.md` and
   `infrastructure/phase4-kickoff-delegation-contract-v1.md` to understand the
   current contract model (`confidence`, `risk_routing`, `fallback`).
2. Edit `assistant/delegation-contract-v1-fixtures.json` — add a new fixture
   case for the rule. Each fixture has:
   - `id`, `description`, `input` (delegation request shape), `expect` (decision + reason pattern)
3. Run the contract check to validate:
   ```
   make delegation-contract-check
   ```
4. If the rule requires a corresponding coordinator planner change, add a fixture
   to `assistant/coordinator-planner-fixtures.json` and run:
   ```
   make delegation-planner-check
   ```
5. Add an end-to-end case to `assistant/delegation-qa-matrix.json` covering the
   new rule path, then run:
   ```
   make delegation-qa
   ```
   The gate must remain `gate_status=pass`.

Do not merge if `make delegation-qa` shows `gate_status=fail`.

### Extending the QA Matrix

The QA matrix (`assistant/delegation-qa-matrix.json`) is the rollout gate for
`delegation_enabled=true` by default. Each case covers a specific pipeline path.

Case structure:

```json
{
  "id": "qa_e2e_<your_case>",
  "description": "...",
  "cfg": { "runtime": { "delegation_enabled": true, "delegation_mode": "coordinator_v1" } },
  "input": {
    "plan_id": "...", "correlation_id": "...",
    "user_request": "...", "subtasks": [...]
  },
  "expect": {
    "runtime_enabled": true,
    "task_count": 1,
    "execution_modes": ["delegated"],
    "decisions": ["delegate"],
    "result_statuses": ["ok"],
    "synthesis_status": "ok",
    "fallback_count": 0,
    "deferred_count": 0,
    "required_traces": [
      "delegation_plan_created", "delegation_decision",
      "specialist_dispatch", "specialist_result", "delegation_synthesis"
    ],
    "absent_traces": []
  }
}
```

Key rules:
- `risk_level: "critical"` tasks must produce `decision: "deny"` and `execution_mode: "defer"`.
- `policy_decision: "deny"` tasks must produce `decision: "deny"` regardless of confidence.
- Cases with `delegation_enabled: false` must produce `execution_modes: ["single_agent", ...]`.
- All 6 required trace types must appear across the full suite to satisfy `trace_complete=true`.

After adding a case, run `make delegation-qa` and confirm `gate_status=pass`.

### Adding a New Specialist Type

1. Identify the specialist's `specialist_id`, `capabilities`, `risk_envelope`,
   and `cost_hint`/`latency_hint` from `infrastructure/specialist-registry-contract-v1.md`.
2. Add the specialist to the relevant coordinator planner fixture in
   `assistant/coordinator-planner-fixtures.json`.
3. Add a QA matrix case dispatching to the new specialist (set `intent_class` and
   `required_capabilities` to match the specialist's profile).
4. Run all Phase 4 checks:
   ```
   make delegation-contract-check
   make delegation-planner-check
   make delegation-execution-check
   make delegation-qa
   make delegation-checkpoint-check
   ```
   All must pass.

### Running Targeted Phase 4 Checks

| Target | What it checks |
| --- | --- |
| `make delegation-contract-check` | Contract evaluator fixtures (deny/delegate/fallback decisions) |
| `make delegation-planner-check` | Coordinator planner fixtures (task decomposition, specialist assignment) |
| `make delegation-execution-check` | Delegated execution + synthesis fixtures (dispatch, result, synthesis) |
| `make delegation-qa` | Full end-to-end QA matrix (all 6 cases, rollout gate evaluation) |
| `make delegation-checkpoint-check` | Phase 4 reliability baseline comparison (exits non-zero on breach) |
| `make delegation-trend` | Run checkpoint and append to `assistant/delegation-trend-history.json` |

For a single-command check covering QA + baseline:

```
make delegation-qa && make delegation-checkpoint-check
```

### Reading Gate Output

`make delegation-qa` prints the full JSON gate result. Look for:

```json
"gate_result": {
  "gate_status": "pass",
  "reason": "all rollout gate thresholds satisfied: qa_pass_rate=100.00% ..."
}
```

`make delegation-checkpoint-check` prints a human-readable summary:

```
delegation reliability checkpoint: PASS
  qa_pass_rate:            100.00%
  dispatch_success_rate:   100.00%
  trace_complete:          True
  positive_path_fallback:  0.00%
  positive_path_deferred:  0.00%
```

If the gate fails, the script exits non-zero and lists breached thresholds. Do
not merge a PR that breaks the gate.

### Delegation Track: Self-Evolution Evidence

Any change that modifies default delegation behavior (`delegation_enabled`,
`delegation_mode`, risk routing, or fallback strategy) is a **self-evolution
item** on the framework track. The PR body must include the full evidence
contract from `infrastructure/self-evolution-evidence-rubric.md`:

- Baseline evidence: current `make delegation-checkpoint-check` output
- Delta observed: measured change in `qa_pass_rate`, `dispatch_success_rate`, fallback/deferred rates
- Thresholds and guardrails: `qa_pass_rate >= 95%`, `dispatch_success_rate >= 90%`, `trace_complete=true`
- Rollback/fallback: revert default config; single-agent path always preserved
- Risk notes: confirm no behavioral regression in negative-path cases (deny, defer, gate-off)

The nightly CI (`benchmark-nightly.yml`) runs the delegation checkpoint automatically
and appends results to `assistant/delegation-trend-history.json`. Check recent trend
entries if the nightly gate shows a regression before your PR merges.

## PR Author Checklist

- Declare track: assistant/framework/cross-track.
- Declare risk: low/medium/high.
- Declare self-evolution applicability and complete rubric fields when required.
- List validations run.
- Confirm state-doc sync (`STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`) or no-change reason.
- Document follow-up items for the next contributor.
