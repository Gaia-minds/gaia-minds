# Status

Updated: February 15, 2026

## Current Sprint

**Sprint: Governance + Onboarding Stabilization** (Feb 14–28, 2026)

See `ROADMAP.md` for phase details and dependency order.

## Shipped This Sprint

Historical sprint delivery remains in `CHANGELOG.md`; this section tracks only the
current active sprint window.

- `Phase 3 Dead-Code/Dead-Artifact Audit` (`#105`)
- `Phase 3 Assistant Modular Refactor` (`#106`)
- `Phase 3 README Live-Preview Refresh` (`#107`)
- npm release `@gaia-minds/assistant-cli@0.3.0` (`#108`, tag `v0.3.0`)
- `Phase 3 Privacy-Preserving Unmet-Intent Signals` (`#111`)
- `Phase 3 Skill-Import Security Research` (`#115`)
- `Phase 3 Skill Provenance Admission Gate` (`#122`, PR #125)
- `Phase 3 Obfuscation-Aware Skill Validation Hardening` (`#123`, PR #126)
- `Phase 3 Skill-First Unmet-Intent Triage` (`#112`, PR #127)
- `Phase 3 Signal-Derived Hypothesis Candidate Integration` (`#113`, PR #128)
- `Sprint OAuth onboarding activation + provider preflight fix` (`#134`, PR #136)
- `Sprint onboarding/auth surface extraction` (`#131`, PR #137)
- `Sprint Claude Code OAuth onboarding/auth integration` (`#130`, PR #138)
- `Sprint governance/state sync reset for docs and status surfaces` (`#129`)
- `Sprint live preview rebuild from executable Gaia traces` (`#132`)
- npm release `@gaia-minds/assistant-cli@0.4.0` (`#133`, tag `v0.4.0`)

## In Progress

- `#142` `[Sprint][Assistant] Add provider model selector and live catalog retrieval`
  - owner: `@TonyThePredictor`
  - PR: `#143` (`issue-142-provider-model-selector`)
  - current blocker: CI policy gates failing (`self-evolution-evidence`, `uat-policy`) pending closeout updates

## Next Up (Ordered Queue)

1. `#144` `[Sprint][Assistant] Research provider model discovery contracts (Codex/Claude/OpenAI/Anthropic/OpenRouter)`
2. `#145` `[Sprint][Assistant] Add provider model catalog inspection command`
3. `#146` `[Sprint][Assistant] Add runtime failover for provider quota/auth hard failures`
4. `#147` `[Sprint][Assistant] Add model effort selector across onboarding/config/runtime`

## Planned Next Wave

- Execute planning artifact `infrastructure/planning-round-2026-02-15-post-model-selector-queue.md`.
- After `#145` and `#146` merge, run next planning checkpoint for release/readiness prioritization.

## Blocked

- `#142` merge is blocked on PR `#143` policy checks:
  - `self-evolution-evidence` (missing checklist lines in PR body)
  - `uat-policy` (missing UAT change record + justification section)

## How to Use This File

- **Claiming work**: Move an item from "Next Up" to "In Progress" with owner + issue link.
- **Completing work**: Move completed lane to "Shipped This Sprint" with PR/tag link.
- **Sprint rollover**: At sprint boundary, archive shipped history in `CHANGELOG.md` and reset this file to active queue only.
