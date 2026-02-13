# Release Readiness Template

Updated: February 13, 2026

## 1. Release Scope

- Version/tag:
- Included PRs:
- Release manager:

## 2. Readiness Checklist

- [ ] Required checks green
- [ ] Changelog entries complete
- [ ] Upgrade notes included (if needed)
- [ ] Rollback plan confirmed

## 3. Self-Evolution Evidence Gate (Required when release includes self-evolution PRs)

- [ ] Applicability reviewed for each included PR (`Applies` vs `Not applicable`)
- [ ] Baseline evidence linked
- [ ] Delta evidence linked
- [ ] Thresholds and guardrails documented
- [ ] Rollback/fallback evidence documented
- [ ] Risk notes reviewed and accepted

Reference rubric: `infrastructure/self-evolution-evidence-rubric.md`

## 4. Reliability Checkpoint Gate (Required for Phase 3 framework releases)

- [ ] Reliability checkpoint artifact linked
- [ ] Thresholds from `assistant/reliability-baseline-phase3.json` are satisfied
- [ ] Any threshold breach has severity + owner triage record
- [ ] Incident/postmortem links added for unresolved reliability regressions

Reference workflow: `infrastructure/reliability-triage-workflow.md`

## 5. Risk Review

- High-risk changes:
- Mitigations:

## 6. Publish Plan

- Build/publish commands:
- Verification steps:
- Communication targets:

## 7. Decision

- Go/no-go:
- Reason:
