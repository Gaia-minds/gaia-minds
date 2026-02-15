# Release Readiness Report: v0.5.0

Date: February 15, 2026
Issue: `#156`
Main role: `contributor`
Sub-role gates: `gaia-release-manager`, `gaia-qa-evaluator`

## 1. Release Scope

- Version/tag: `0.5.0` / `v0.5.0`
- Included PRs: cumulative scope since `v0.4.0`, including runtime failover/effort/capability/guardrail lanes and Phase 4 kickoff design (`#146`, `#147`, `#153`, `#154`, `#155`, `#157` via PRs `#151`, `#152`, `#158`, `#159`, `#160`, `#165`)
- Release manager: Codex (`@TonyThePredictor`)

## 2. Readiness Checklist

- [x] Required checks green
- [x] Changelog entries complete
- [x] Upgrade notes included (if needed)
- [x] Rollback plan confirmed

## 3. Self-Evolution Evidence Gate (Required when release includes self-evolution PRs)

- [x] Applicability reviewed for each included PR (`Applies` vs `Not applicable`)
- [x] Baseline evidence linked (N/A: no self-evolution behavior/governance PR in this release train)
- [x] Delta evidence linked (N/A)
- [x] Thresholds and guardrails documented (N/A)
- [x] Rollback/fallback evidence documented (N/A)
- [x] Risk notes reviewed and accepted (N/A)

Reference rubric: `infrastructure/self-evolution-evidence-rubric.md`

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
  - release correctness risk (version/tag mismatch, package payload drift, npm publish failure)
  - shipped runtime deltas in this train affect reasoning provider/model/effort and operator startup behavior
- Mitigations:
  - full release gate matrix executed locally before release PR
  - publish workflow enforces tag/version alignment (`vX.Y.Z == package.json`)
  - rollback/fallback plan documented below

## 6. Publish Plan

- Build/publish commands:
  1. Merge release PR to `main`
  2. `git tag v0.5.0`
  3. `git push origin v0.5.0`
- Verification steps:
  1. `gh run list --repo Gaia-minds/gaia-minds --workflow npm-publish.yml --limit 1`
  2. `gh run watch <run-id> --repo Gaia-minds/gaia-minds`
  3. `npm view @gaia-minds/assistant-cli version` returns `0.5.0`
  4. `npm install -g @gaia-minds/assistant-cli@0.5.0` succeeds
- Communication targets:
  - `#156` issue closeout comment
  - `CHANGELOG.md`, `STATUS.md`, `ROADMAP.md`

## 7. Rollback/Fallback Plan

- If publish workflow fails before publish: patch and retag with corrected version/tag alignment.
- If published package has release-blocking defect: publish patch release `0.5.1` with explicit remediation notes and incident linkage.

## 8. Decision

- Go/no-go: **Go**
- Reason: all required release and QA gates passed with no blocking defects.
