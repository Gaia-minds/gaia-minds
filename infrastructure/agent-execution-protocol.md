# Agent Execution Protocol

Updated: February 8, 2026

## Purpose

Define a consistent operating protocol for agents working in this repository:

- main-role selection (`planner` or `contributor`)
- autonomous issue selection
- sub-role skill triggering rules
- required deliverables and quality checks
- operator prompt templates

## Role Hierarchy (Required)

Two main roles exist:

1. `planner` (main role)
   - owns planning rounds, backlog decomposition, sequencing, and dependency clarity
2. `contributor` (main role)
   - owns implementation/research/docs/review execution for a selected issue/lane

All other skills are sub-roles and must be used under one of the two main roles:

- `gaia-researcher`
- `gaia-technical-writer`
- `gaia-security-reviewer`
- `gaia-qa-evaluator`
- `gaia-release-manager`
- `gaia-incident-responder`
- `gaia-integration-coordinator`
- `gaia-privacy-memory-steward`

## Startup Handshake (Required)

After reading repo context, the agent must ask:

`Which main role should I take: planner or contributor?`

Rules:

1. Do not start work before main-role confirmation (unless human explicitly requests unattended/autonomous mode).
2. Declare chosen main role in first issue/PR comment.
3. Trigger sub-role skills only when task conditions require them.

## Contributor Main Role: Autonomous Issue Selection

Contributor-role agents should self-select work by default.

1. Load required baseline context:
   - `CONSTITUTION.md`
   - `skills/gaia-contributor/SKILL.md`
   - `infrastructure/contributor-playbook.md`
2. Scan open queue:
   - `gh issue list --repo Gaia-minds/gaia-minds --state open --limit 100 | rg '\[Phase 2\]\[P2-'`
3. Filter to ready items:
   - no active owner claim
   - dependencies unblocked
   - scope matches current skill set
4. Pick highest-priority ready issue (priority from `STATUS.md`).
5. Post claim comment before coding:
   - owner
   - scope
   - ETA
   - role skill(s) to be used
6. Post required plan packet before implementation.
7. Move lane status to `In Progress` in `STATUS.md`.
8. If blocked for >24h, post blocker details and unclaim.

## Planner Main Role: Planning Flow

Planner-role agents should:

1. Define planning scope and decision deadline.
2. Use `infrastructure/planning-round-template.md`.
3. Produce an execution-ready plan:
   - decomposed items/lanes
   - dependency and merge-order notes
   - unclear items requiring research
4. Recommend owners and next actions.
5. Sync state docs (`STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`) or record no-change reason.

## Sub-Role Trigger Matrix

`gaia-contributor` is always active as baseline workflow.

- Trigger `gaia-planner`:
  - at planning/reprioritization rounds
  - when issue readiness/dependencies are unclear
  - when work must be decomposed into parallel lanes
- Trigger `gaia-researcher`:
  - when decisions depend on external evidence/tradeoffs
  - when implementation path is unclear or controversial
- Trigger `gaia-technical-writer`:
  - after merge batches
  - before release
  - when roadmap/status/changelog drift is suspected
- Trigger `gaia-security-reviewer`:
  - for auth, permissions, sandbox, policy, skill onboarding, or high-risk changes
- Trigger `gaia-qa-evaluator`:
  - before merge on feature lanes
  - before release go/no-go
- Trigger `gaia-release-manager`:
  - when preparing or executing a release
- Trigger `gaia-incident-responder`:
  - on regressions, failed automation, or reliability/safety incidents
- Trigger `gaia-integration-coordinator`:
  - when two or more lanes are active and contract compatibility needs coordination
- Trigger `gaia-privacy-memory-steward`:
  - for memory-related research, design, or implementation

## Required Output Contract

Every active issue should include:

1. Main role declaration (`planner` or `contributor`).
2. Claim comment (owner/scope/ETA/sub-roles) for contributor work.
3. Plan packet or research/design packet (per relevant template).
4. Validation evidence in PR notes.
5. State sync update (or no-change reason):
   - `STATUS.md`
   - `ROADMAP.md`
   - `CHANGELOG.md`

## Standard Validation

Run before PR:

- `make generate-indexes` (if indexed folders changed)
- `make check-all`
- lane-specific checks from the selected role skill

## Operator Prompt Template

Use this when onboarding an agent:

```text
Work autonomously on Gaia Minds using the agent execution protocol.

Required startup:
1) Read CONSTITUTION.md
2) Read skills/gaia-contributor/SKILL.md
3) Read infrastructure/agent-execution-protocol.md
4) Ask me which main role to take: planner or contributor

Do not start work until I answer with the main role.

Then:
- If planner: run a planning round and publish the planning artifact.
- If contributor: select your own issue from the open Phase 2 queue, post claim + plan packet, then execute in a focused branch and open a PR.

Mandatory before PR:
- run make generate-indexes (if needed)
- run make check-all
- sync STATUS.md, ROADMAP.md, CHANGELOG.md (or state no-change reasons)

PR notes must include:
- summary of changes
- validations run
- risks/follow-ups
- issue link
```

## Role-Specific Prompt Add-on

Add one line to force a sub-role skill:

```text
Primary sub-role skill for this task: skills/<role-skill>/SKILL.md
```
