---
name: gaia-assistant-builder
description: Build and evolve the Gaia personal assistant track powered by OpenClaw while preserving constitutional safety, explicit user direction, and a token budget split between user service work and self-improvement. Use when contributing assistant architecture, workflows, governance, or implementation tasks for this track.
---

# Gaia Assistant Builder Skill

Use this skill when the task is about the Gaia personal assistant program.

This program is not a replacement for OpenClaw. It is Gaia's constitutional
layer on top of OpenClaw capabilities, with transparent governance and a
user-direction workflow.

## Required Context

Read these first:

1. `CONSTITUTION.md`
2. `infrastructure/personal-assistant-program.md`
3. `assistant/README.md` for standalone runtime bootstrap
4. `tools/agent-config.yml` and `tools/agent-loop.py` for self-evolving loop behavior

Then load references from this skill as needed:

- `references/direction-contract.md` for user-direction issue handling
- `references/openclaw-boundary.md` for what belongs in Gaia vs OpenClaw

## Core Rules

1. Keep the assistant user-useful first and self-improving second.
2. Preserve transparent review paths. No hidden behavior.
3. Treat user direction as a first-class input with explicit scope and success criteria.
4. Keep OpenClaw-specific generic improvements upstreamable.
5. Keep Gaia-specific constitutional and governance logic in Gaia.

## Contribution Workflow

1. Sync and inspect current state.
2. Check open assistant-direction issues and active PRs.
3. Select one scoped contribution that can be reviewed independently.
4. Implement with tests/checks where applicable.
5. Regenerate indexes with `make generate-indexes` when docs/skills/infrastructure changed.
6. Run `make check-all`.
7. Open PR with clear "what changed / why / validation" sections.

## Scope Boundaries

Contribute to Gaia when work is:

- Constitutional guardrails
- User-direction protocol
- Token budget policy and governance
- Gaia-specific skills and contributor workflows

Contribute to OpenClaw when work is:

- Generic runtime capability
- Generic onboarding/CLI/docs improvements
- Generic skill loading or platform behavior

For cross-repo work:

1. Land canonical policy and contract changes in Gaia first.
2. Open OpenClaw PR for generic integration or docs linkage.
3. Link both PRs to keep a clear audit trail.

## Minimum PR Checklist

- [ ] Aligns with `CONSTITUTION.md`
- [ ] References the assistant program docs if behavior changes
- [ ] Uses the user-direction contract when task is human-directed
- [ ] Includes validation output (`make check-all` at minimum)
- [ ] Regenerates indexes if needed
