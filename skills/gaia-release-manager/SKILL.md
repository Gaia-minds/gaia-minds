---
name: gaia-release-manager
description: Coordinate release readiness and execution for Gaia. Use this skill when preparing a release, verifying changelog/version integrity, checking gates, and managing rollback-safe publish decisions.
---

# Gaia Release Manager Skill

Use this skill for release preparation, go/no-go checks, and publish coordination.

## Required Context

1. `CHANGELOG.md`
2. `STATUS.md`
3. `ROADMAP.md`
4. `infrastructure/release-readiness-template.md`

## Workflow

1. Define release scope (version, included PRs).
2. Verify readiness:
   - required checks green
   - changelog complete
   - migration notes/known risks documented
3. Confirm rollback/fallback path.
4. Execute or coordinate release workflow.
5. Publish release summary and post-release verification.
6. Run state sync updates (`STATUS.md`, `CHANGELOG.md`) if needed.

## Deliverables

- Release readiness report using template.
- Go/no-go decision with rationale.
- Post-release verification note with follow-ups.

## Quality Gates

- No release with unresolved blocking defects.
- Changelog accurately reflects shipped scope.
- Rollback plan is documented before publish.
- Release decision is traceable to validation evidence.
