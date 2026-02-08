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

## Segregation Rules (Mandatory)

1. Exactly one main role is active per issue at a time: `planner` or
   `contributor`.
2. Sub-roles are selected from the allowed set for that main role only.
3. `gaia-planner` is a planner-role sub-role; contributor-role tasks do not use
   it unless a human explicitly overrides.
4. If required sub-role gates are not satisfied, the PR is not merge-ready.
5. Maximum active sub-roles per issue:
   - default: 3
   - incident/release workflows: 4

### Allowed Sub-Roles by Main Role

| Main Role | Allowed Sub-Roles |
| --- | --- |
| `planner` | `gaia-planner`, `gaia-researcher`, `gaia-integration-coordinator`, `gaia-technical-writer`, `gaia-privacy-memory-steward` |
| `contributor` | `gaia-researcher`, `gaia-technical-writer`, `gaia-security-reviewer`, `gaia-qa-evaluator`, `gaia-release-manager`, `gaia-incident-responder`, `gaia-integration-coordinator`, `gaia-privacy-memory-steward` |

## Startup Handshake (Required)

After completing remote-first sync and reading repo context, the agent must ask:

`Which main role should I take: planner or contributor?`

Rules:

1. Do not start work before main-role confirmation (unless human explicitly requests unattended/autonomous mode).
2. Declare chosen main role in first issue/PR comment.
3. Trigger sub-role skills only when task conditions require them.

## Remote-First State Sync (Mandatory)

Never decide work from local state alone. Sync with `origin` first.

Required sequence before selecting/claiming work:

1. Validate remote access:
   - `git remote get-url origin` (must point to `Gaia-minds/gaia-minds`, HTTPS or SSH)
   - `git remote -v`
   - `git fetch origin`
2. Update local `main` from remote:
   - `git checkout main`
   - `git pull --ff-only origin main`
3. If continuing from a feature branch:
   - `git checkout <branch>`
   - `git fetch origin`
   - `git rebase origin/main` (or document why rebase is deferred)
4. Verify remote collaboration state:
   - `gh issue list --repo Gaia-minds/gaia-minds --state open --limit 100`
   - `gh pr list --repo Gaia-minds/gaia-minds --state open`

If remote checks fail (GitHub/API connectivity), stop autonomous selection and
report a blocker instead of using stale local assumptions.

## Contributor Main Role: Autonomous Issue Selection

Contributor-role agents should self-select work by default.

1. Complete `Remote-First State Sync (Mandatory)`.
2. Load required baseline context:
   - `CONSTITUTION.md`
   - `skills/gaia-contributor/SKILL.md`
   - `infrastructure/contributor-playbook.md`
3. Scan open queue:
   - `gh issue list --repo Gaia-minds/gaia-minds --state open --limit 100 | rg '\[Phase 2\]\[P2-'`
4. Filter to ready items:
   - no active owner claim
   - dependencies unblocked
   - scope matches current skill set
5. Pick highest-priority ready issue (priority from `STATUS.md`).
6. Post claim comment before coding:
   - owner
   - scope
   - ETA
   - role skill(s) to be used
7. Post required plan packet before implementation.
8. Move lane status to `In Progress` in `STATUS.md`.
9. If blocked for >24h, post blocker details and unclaim.

## Planner Main Role: Planning Flow

Planner-role agents should:

1. Complete `Remote-First State Sync (Mandatory)`.
2. Define planning scope and decision deadline.
3. Use `infrastructure/planning-round-template.md`.
4. Produce an execution-ready plan:
   - decomposed items/lanes
   - dependency and merge-order notes
   - unclear items requiring research
5. Recommend owners and next actions.
6. Sync state docs (`STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`) or record no-change reason.

## Sub-Role Trigger Matrix (Strict)

`gaia-contributor` is always active as baseline workflow.

| Condition | Main Role | Required Sub-Roles | Optional Sub-Roles |
| --- | --- | --- | --- |
| Planning/reprioritization round | `planner` | `gaia-planner` | `gaia-researcher`, `gaia-integration-coordinator`, `gaia-technical-writer` |
| Decision unclear or tradeoff-heavy | `planner` or `contributor` | `gaia-researcher` | `gaia-technical-writer` |
| 2+ active lanes with contract coupling | `planner` or `contributor` | `gaia-integration-coordinator` | `gaia-researcher`, `gaia-technical-writer` |
| Docs drift risk / post-merge docs pass | `planner` or `contributor` | `gaia-technical-writer` | none |
| High-risk implementation (auth/policy/sandbox/skills validation) | `contributor` | `gaia-security-reviewer`, `gaia-qa-evaluator` | `gaia-technical-writer` |
| Memory-related design/implementation | `planner` or `contributor` | `gaia-privacy-memory-steward`, `gaia-qa-evaluator` | `gaia-researcher`, `gaia-security-reviewer` |
| Release preparation/execution | `contributor` | `gaia-release-manager`, `gaia-qa-evaluator` | `gaia-technical-writer`, `gaia-security-reviewer` |
| Incident response or reliability regression | `contributor` | `gaia-incident-responder` | `gaia-qa-evaluator`, `gaia-security-reviewer`, `gaia-technical-writer` |

## Mandatory Merge Gates

Before merge, enforce these gates:

1. High-risk change:
   - `gaia-security-reviewer` findings resolved or accepted with rationale
   - `gaia-qa-evaluator` pass/go decision
2. Memory-related change:
   - `gaia-privacy-memory-steward` review complete
   - `gaia-qa-evaluator` pass/go decision
3. Release PR:
   - `gaia-release-manager` go/no-go documented
   - `gaia-qa-evaluator` pass/go decision
4. Incident fix PR:
   - `gaia-incident-responder` report/postmortem link
   - `gaia-qa-evaluator` regression verification

## Required Output Contract

Every active issue should include:

1. Main role declaration (`planner` or `contributor`).
2. Claim comment (owner/scope/ETA/sub-roles) for contributor work.
3. Plan packet or research/design packet (per relevant template).
4. Validation evidence in PR notes.
5. Required sub-role gate evidence for the selected work type.
6. State sync update (or no-change reason):
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
1) Confirm repository target is https://github.com/Gaia-minds/gaia-minds.git (or SSH equivalent) using `git remote get-url origin`
2) Run remote-first sync (`git fetch origin`, `git pull --ff-only origin main`, and check open issues/PRs on remote)
3) Read CONSTITUTION.md
4) Read skills/gaia-contributor/SKILL.md
5) Read infrastructure/agent-execution-protocol.md and follow it as the operating protocol
6) Ask me which main role to take: planner or contributor

Do not start work until I answer with the main role.

Then:
- If planner: run a planning round and publish the planning artifact.
- If contributor: read infrastructure/contributor-playbook.md, then select your own issue from the open Phase 2 queue, post claim + plan packet, then execute in a focused branch and open a PR.
- Use only sub-roles allowed by the protocol matrix for your chosen main role.
- Satisfy mandatory merge gates for your work type before requesting merge.

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

To constrain to mandatory gates, add:

```text
Enforce protocol mandatory gates for this work type and include evidence in PR notes.
```
