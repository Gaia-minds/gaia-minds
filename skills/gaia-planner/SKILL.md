---
name: gaia-planner
description: Plan Gaia roadmap and backlog work with consistent quality. Use this skill when decomposing roadmap phases into actionable lanes, running backlog reassessment rounds, defining implementation plans, or deciding sequencing and dependencies across parallel agent work.
---

# Gaia Planner Skill

Use this skill for planning rounds, backlog reassessment, and roadmap
decomposition tasks.

## Required Context

Read these first:

1. `ROADMAP.md`
2. `STATUS.md`
3. `CHANGELOG.md`
4. `infrastructure/phase2-lane-implementation-plans.md`
5. `infrastructure/planning-round-template.md`

Then inspect relevant open issues/PRs for the scope being planned.

## Planning Workflow

1. Define the planning question and decision deadline.
2. Gather current-state evidence:
   - shipped items
   - in-progress items
   - blockers and risks
   - open dependency contracts
3. Draft the plan using `infrastructure/planning-round-template.md`.
4. Decompose work into independently reviewable items.
5. For each item, specify:
   - scope and non-goals
   - architecture deltas
   - validation plan
   - rollback/fallback
   - acceptance criteria
6. Mark dependencies and integration order explicitly.
7. Create a `needs research` list for unknowns.
8. Run state-sync checks and update (or record no-change reason):
   - `STATUS.md`
   - `ROADMAP.md`
   - `CHANGELOG.md`
   - lane/coordination issue comments

## Required Deliverables

- Planning artifact (issue comment or committed doc) using template sections.
- Clear execution queue with priorities and dependency notes.
- Explicit owner recommendation per item/lane.
- List of unclear items requiring research before implementation.

## Quality Gates

- Every item can be implemented and validated independently.
- Every high-risk item includes rollback and safety/policy impact notes.
- Shared contracts are identified before parallel implementation starts.
- Parallel lanes do not overlap in ownership or scope boundaries.
- State-sync checklist is complete (`updated` or `no change + reason`).

## Closeout

Before ending the planning round:

1. Link planning artifact in the relevant issue/PR.
2. Confirm state files are updated or explicitly unchanged with reason.
3. Add follow-up research tasks for unresolved unknowns.
