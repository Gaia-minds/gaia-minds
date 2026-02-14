# Status

Updated: February 14, 2026

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

## In Progress

_Nothing currently in progress._

## Next Up (Ordered Queue)

1. `#134` Fix OAuth onboarding activation + provider dependency preflight for `gaia run`.
2. `#129` Governance/state sync reset for README + CONTRIBUTING + STATUS/ROADMAP/CHANGELOG alignment.
3. `#131` Refactor onboarding/auth surfaces out of `tools/gaia-assistant.py`.
4. `#130` Add Claude Code OAuth onboarding in `gaia onboard` / `gaia auth`.
5. `#132` Rebuild live preview from reproducible real Gaia interaction traces.
6. `#133` Prepare next npm release after stabilization lanes merge.

## Planned Next Wave

- Follow-on architecture lane for provider-adapter boundaries if `#131` reveals additional extraction required.

## Blocked

_Nothing blocked._

## How to Use This File

- **Claiming work**: Move an item from "Next Up" to "In Progress" with owner + issue link.
- **Completing work**: Move completed lane to "Shipped This Sprint" with PR/tag link.
- **Sprint rollover**: At sprint boundary, archive shipped history in `CHANGELOG.md` and reset this file to active queue only.
