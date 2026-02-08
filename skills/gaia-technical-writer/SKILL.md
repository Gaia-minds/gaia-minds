---
name: gaia-technical-writer
description: Keep Gaia documentation accurate and current across roadmap, status, skills, infrastructure, and assistant docs. Use this skill for repo-wide docs freshness audits, drift correction, and documentation quality gates.
---

# Gaia Technical Writer Skill

Use this skill for documentation freshness and consistency work.

## Required Context

Read these first:

1. `README.md`
2. `ROADMAP.md`
3. `STATUS.md`
4. `CHANGELOG.md`
5. `infrastructure/docs-freshness-template.md`

## Workflow

1. Define audit scope (full repo or targeted area).
2. Build source-of-truth mapping for audited docs.
3. Detect drift:
   - outdated dates/versions/releases
   - stale issue/PR references
   - commands that no longer match runtime
   - inconsistency between `ROADMAP.md`, `STATUS.md`, and `CHANGELOG.md`
4. Apply fixes in small, reviewable commits.
5. Regenerate indexes when content trees changed.
6. Run `make check-all`.
7. Publish docs freshness report using template.

## Deliverables

- Updated documentation files.
- Freshness report artifact (issue comment or committed doc).
- Follow-up list for unresolved docs debt.

## Quality Gates

- Every changed doc has an identifiable source of truth.
- Status/roadmap/changelog alignment is checked every round.
- No known stale dates/version references remain in scoped docs.
- Indexes are regenerated when required.
