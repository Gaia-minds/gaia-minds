# Self-Evolution PR Evidence Rubric

Updated: February 13, 2026

## Purpose

Define the minimum evidence required for self-evolution pull requests so rollout
decisions are deterministic, reviewable, and reversible.

Scope:

- framework-track PRs that change self-evolution behavior or governance
- cross-track PRs that include self-evolution behavior/governance deltas

## Required Evidence Fields

When self-evolution applicability is marked as `Applies` in the PR template, all
fields below are mandatory and must be substantive.

1. Baseline evidence
   - Current/reference metrics or behavior before the change.
   - Include artifact links/paths (benchmark, UAT, matrix, logs, or reports).
2. Delta observed
   - What changed versus baseline and by how much.
   - Include exact metrics or deterministic pass/fail outcomes.
3. Thresholds and guardrails
   - Acceptance thresholds used for go/no-go decisions.
   - Include breach behavior (block, rollback, follow-up issue).
4. Rollback/fallback
   - Exact rollback path if post-merge behavior regresses.
   - Include commands, refs, or procedure owner.
5. Risk notes
   - Primary risks, blast radius, and unresolved follow-ups.

## Applicability Gate

PR authors must choose exactly one option in `.github/pull_request_template.md`:

- `Applies: this PR changes self-evolution behavior/governance.`
- `Not applicable: no self-evolution behavior/governance changes.`

If `Applies` is selected, all required evidence fields are enforced by CI.

## Deterministic CI Enforcement

- Checker: `tools/check-self-evolution-evidence.py`
- Workflow: `.github/workflows/self-evolution-evidence.yml`

The check fails when:

- applicability is missing or contradictory
- required evidence fields are missing
- required evidence fields are placeholder-only content

## Planning and Release Workflow Linkage

- Planning rounds:
  `infrastructure/planning-round-template.md` requires evidence-contract planning
  for self-evolution items.
- Release readiness:
  `infrastructure/release-readiness-template.md` requires explicit rubric gate
  confirmation for releases including self-evolution PRs.

## Reviewer Notes

- This rubric is an enforcement baseline, not the maximum bar.
- Reviewers can require deeper evidence for higher-risk changes.
