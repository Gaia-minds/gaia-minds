---
name: gaia-researcher
description: Run high-quality Gaia research tasks with explicit evidence, tradeoff analysis, and actionable recommendations. Use this skill for roadmap/backlog research, architecture option analysis, risk studies, and any task that must convert findings into implementation-ready decisions.
---

# Gaia Researcher Skill

Use this skill when the primary goal is to produce decision-grade research.

## Required Context

Read these first:

1. `ROADMAP.md`
2. `STATUS.md`
3. `infrastructure/research-task-template.md`
4. `infrastructure/contributor-playbook.md`

Then load lane-specific docs/issues/PRs for the research scope.

## Research Workflow

1. Define the decision question and constraints.
2. Capture baseline assumptions from current Gaia docs/issues.
3. Gather evidence:
   - use primary sources when possible
   - include publish/update dates
   - include contradictory evidence when relevant
4. Build options and tradeoff matrix:
   - safety/security impact
   - implementation complexity
   - operational cost/performance
   - compatibility with current roadmap/contracts
5. Make a recommendation with confidence level.
6. Convert findings into action:
   - implementation-ready backlog items, or
   - explicit `needs more research` list
7. Run state-sync checks and update (or record no-change reason):
   - `STATUS.md`
   - `ROADMAP.md`
   - `CHANGELOG.md`

## Required Deliverables

- Research artifact using `infrastructure/research-task-template.md`.
- Explicit fact-vs-inference separation.
- Recommendation section with adoption criteria and rollback notes.
- Clear next actions linked to issues/lanes.

## Quality Gates

- Claims are evidence-linked and date-stamped.
- Tradeoffs are explicit; at least 3 options when feasible.
- Unknowns and risks are listed with follow-up research tasks.
- Outcome is actionable by planner/contributor agents without extra interpretation.
- State-sync checklist is complete (`updated` or `no change + reason`).
