# Release Readiness Report: v0.4.0

Date: February 15, 2026
Issue: `#133`
Main role: `contributor`
Sub-role gates: `gaia-release-manager`, `gaia-qa-evaluator`

## 1. Release Scope

- Version/tag: `0.4.0` / `v0.4.0`
- Included PRs: cumulative scope since `v0.3.0`, including signal-driven self-evolution follow-ons (`#111`, `#112`, `#113`, `#115`, `#122`, `#123`) and stabilization/release lanes (`#134`, `#129`, `#131`, `#130`, `#132` via PRs `#136`, `#139`, `#137`, `#138`, `#140`)
- Release manager: Codex (`@TonyThePredictor`)

## 2. Readiness Checklist

- [x] Required checks green
- [x] Changelog entries complete
- [x] Upgrade notes included (if needed)
- [x] Rollback plan confirmed

## 3. Self-Evolution Evidence Gate (Required when release includes self-evolution PRs)

- [x] Applicability reviewed for each included PR (`Applies` vs `Not applicable`)
- [x] Baseline evidence linked
- [x] Delta evidence linked
- [x] Thresholds and guardrails documented
- [x] Rollback/fallback evidence documented
- [x] Risk notes reviewed and accepted

Evidence references:

- Rubric contract: `infrastructure/self-evolution-evidence-rubric.md`
- CI enforcement gate: `.github/workflows/self-evolution-evidence.yml`
- Included self-evolution lanes in this release train: `#111`, `#112`, `#113`, `#122`, `#123`

## 4. Reliability Checkpoint Gate (Required for Phase 3 framework releases)

- [x] Reliability checkpoint artifact linked
- [x] Thresholds from `assistant/reliability-baseline-phase3.json` are satisfied
- [x] Any threshold breach has severity + owner triage record
- [x] Incident/postmortem links added for unresolved reliability regressions

Checkpoint evidence (reproducible):

- Command: `make reliability-checkpoint-check`
- Artifact JSON: `/tmp/gaia-reliability-checkpoints/latest/reliability-checkpoint.json`
- Artifact Markdown: `/tmp/gaia-reliability-checkpoints/latest/reliability-checkpoint.md`
- Result: `status=pass`, `breach_count=0`

## 5. Risk Review

- High-risk changes:
  - release train includes policy/sandbox/skill-validation/self-evolution deltas plus onboarding/auth and preview workflow updates merged after `v0.3.0`
  - npm publish correctness risk (version/tag mismatch, packaging drift, provenance publish failure)
- Mitigations:
  - full required gate matrix executed locally before release PR (`check-all`, smoke/UAT, quality-matrix, uat-policy, `npm pack --dry-run`, reliability checkpoint check)
  - tag-validation guard in publish workflow enforces `vX.Y.Z == package.json` version
  - rollback path documented below

## 6. Publish Plan

- Build/publish commands:
  1. Merge release PR to `main`
  2. `git tag v0.4.0`
  3. `git push origin v0.4.0`
- Verification steps:
  1. `gh run list --repo Gaia-minds/gaia-minds --workflow npm-publish.yml --limit 1`
  2. `gh run watch <run-id> --repo Gaia-minds/gaia-minds`
  3. `npm view @gaia-minds/assistant-cli version` returns `0.4.0`
  4. `npm install -g @gaia-minds/assistant-cli@0.4.0` succeeds
- Communication targets:
  - `#133` issue closeout comment
  - `CHANGELOG.md`, `STATUS.md`, `ROADMAP.md`

## 7. Rollback/Fallback Plan

- If publish workflow fails before publish: fix via follow-up commit, retag with corrected version/tag alignment.
- If published package has release-blocking defect: publish patch release `0.4.1` with explicit remediation notes and incident linkage.

## 8. Decision

- Go/no-go: **Go**
- Reason: all required release and QA gates passed with no blocking defects.
