# Agent Execution Protocol

Updated: February 8, 2026

## Purpose

Define a consistent operating protocol for agents working in this repository:

- autonomous issue selection
- role-skill triggering rules
- required deliverables and quality checks
- operator prompt templates

## Default Mode: Autonomous Issue Selection

Agents should self-select work by default.

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

## Skill Trigger Matrix

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

1. Claim comment (owner/scope/ETA/skills).
2. Plan packet or research/design packet (per relevant template).
3. Validation evidence in PR notes.
4. State sync update (or no-change reason):
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

Then:
- Select your own issue from the open Phase 2 queue.
- Post a claim comment with owner/scope/ETA and chosen role skills.
- Before coding, post the required plan packet.
- Execute work in a focused branch and open a PR.

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

Add one line to force the role skill:

```text
Primary role skill for this task: skills/<role-skill>/SKILL.md
```
