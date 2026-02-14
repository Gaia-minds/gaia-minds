# Planning Round: Governance + Onboarding Release Reset (2026-02-14)

Updated: February 14, 2026
Main role: `planner`
Activated sub-roles: `gaia-planner`, `gaia-researcher`, `gaia-technical-writer`, `gaia-integration-coordinator`

## 1. Planning Question

- Decision to make: What is the safest and fastest merge order for the next sprint given doc-state drift, onboarding friction, and release readiness goals?
- Decision deadline: February 14, 2026 (planning round close)
- Scope boundary: planner-only queue definition, dependency ordering, and state-sync updates (no feature implementation in this lane)

## 2. Inputs Reviewed

- `ROADMAP.md`: Phase 3 queue history and immediate priorities
- `STATUS.md`: active sprint queue/shipped/in-progress views
- `CHANGELOG.md`: unreleased vs shipped consistency
- `README.md`: top-level onboarding and live-preview messaging
- `CONTRIBUTING.md`: contributor workflow and protocol references
- `skills/gaia-contributor/SKILL.md`: baseline workflow freshness check
- `assistant/README.md`: runtime docs + live-preview source mapping
- `assistant/uat-policy.md`: UAT governance and command-surface policy
- Runtime evidence (local):
  - `make test-smoke` -> `27/27` pass
  - `make test-uat` -> `43/43` pass
  - `make uat-policy` -> pass (`command_paths=66`, `mapped_commands=69`)
  - manual command flow for `gaia doctor/chat/feedback/memory summarize/traces` -> pass
- User-reported onboarding runtime gap (captured in issue `#134`)
- Issues/PRs reviewed:
  - newly opened sprint queue: `#129`, `#130`, `#131`, `#132`, `#133`, `#134`
- External references for Claude Code OAuth planning:
  - https://docs.claude.com/en/docs/claude-code/quickstart
  - https://docs.anthropic.com/en/docs/claude-code/overview
  - https://docs.anthropic.com/en/docs/claude-code/iam
  - local CLI verification: `claude auth login --help`, `claude auth status --json`

## 3. Current State Snapshot

- Shipped:
  - Signal-driven follow-on queue is merged (`#111`, `#112`, `#113`, `#115`, `#122`, `#123`)
  - npm `0.3.0` is published
- In progress:
  - none
- Blocked:
  - none
- Risk hotspots:
  - onboarding continuity bug: OAuth success does not guarantee runnable provider defaults (`#134`)
  - root docs/state drift (`README` scope creep, stale `STATUS` structure, stale queue framing)
  - onboarding/auth complexity concentrated in `tools/gaia-assistant.py` (12k+ LOC, large command handlers)

## 4. Proposed Work Items

### Item `#134` - OAuth onboarding activation + run preflight fix

- Title: Fix OAuth onboarding activation + provider dependency preflight for `gaia run`
- Scope and non-goals:
  - scope: align onboarding-selected provider with runtime defaults and add deterministic provider dependency preflight
  - non-goal: broad provider architecture redesign
- Architecture deltas:
  - onboarding/auth flow updates in assistant runtime
  - doctor/run dependency readiness checks with explicit remediation/fallback guidance
- Validation plan:
  - `make test-smoke`
  - `make test-uat`
  - `make uat-policy`
  - `make check-all`
- Rollback/fallback:
  - revert onboarding default-switch behavior and keep explicit warning if regressions appear
- Acceptance criteria:
  - post-OAuth onboarding, `gaia run` follows an OAuth-compatible default path or deterministic fallback
- Owner recommendation:
  - contributor with `gaia-qa-evaluator` (required), `gaia-technical-writer` (optional)

### Item `#129` - Governance/state sync reset

- Title: Realign `README`, `CONTRIBUTING`, `STATUS`, `ROADMAP`, `CHANGELOG`
- Scope and non-goals:
  - scope: remove drift/duplication and define doc source-of-truth boundaries
  - non-goal: full information architecture rewrite
- Architecture deltas:
  - none (docs/state governance only)
- Validation plan:
  - `make generate-indexes`
  - `make check-all`
- Rollback/fallback:
  - preserve previous snapshots through git history; reintroduce omitted references if discovered missing
- Acceptance criteria:
  - root README concise + linked; CONTRIBUTING protocol-aligned; STATUS sprint-local; changelog/state consistent
- Owner recommendation:
  - contributor with `gaia-technical-writer` + `gaia-integration-coordinator`

### Item `#131` - Onboarding/auth modular refactor

- Title: Extract onboarding/auth surfaces from `tools/gaia-assistant.py`
- Scope and non-goals:
  - scope: module extraction for onboarding/auth paths to reduce hotspot complexity
  - non-goal: runtime-wide rewrite
- Architecture deltas:
  - onboarding/auth module boundary + parser/runtime wiring updates
- Validation plan:
  - `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py <new-modules>`
  - `make test-smoke`
  - `make test-uat`
  - `make uat-policy`
  - `make check-all`
- Rollback/fallback:
  - module extraction can be reverted independently while preserving command surface
- Acceptance criteria:
  - onboarding/auth behavior parity with reduced hotspot concentration
- Owner recommendation:
  - contributor with `gaia-integration-coordinator` + `gaia-qa-evaluator`

### Item `#130` - Claude Code OAuth onboarding

- Title: Add Claude Code OAuth onboarding to `gaia onboard` / `gaia auth`
- Scope and non-goals:
  - scope: onboarding/status flow integration using official Claude CLI auth surfaces
  - non-goal: raw token ingestion into Gaia stores
- Architecture deltas:
  - onboarding provider registry extension + auth source handling for Claude Code
- Validation plan:
  - `make test-smoke`
  - `make test-uat`
  - `make uat-policy`
  - `make check-all`
- Rollback/fallback:
  - feature-flagged provider entry removal if OAuth linking path proves unstable
- Acceptance criteria:
  - Claude onboarding selectable and status-verifiable with deterministic guidance
- Owner recommendation:
  - contributor with required gates: `gaia-security-reviewer`, `gaia-qa-evaluator`

### Item `#132` - Live preview rebuild

- Title: Rebuild live preview from reproducible real interaction traces
- Scope and non-goals:
  - scope: replace synthetic-feeling assets with reproducible capture pipeline and clear value demonstration
  - non-goal: redesign all docs visuals
- Architecture deltas:
  - docs/assets capture workflow and source-of-truth references
- Validation plan:
  - `make test-smoke`
  - `make test-uat`
  - link-check through `make check-all`
- Rollback/fallback:
  - keep prior assets in history and revert if reproducibility tooling fails
- Acceptance criteria:
  - root preview reflects assistant capabilities and reproducible command flow
- Owner recommendation:
  - contributor with `gaia-technical-writer` + `gaia-integration-coordinator`

### Item `#133` - Release readiness + publish

- Title: Prepare and publish next npm release after stabilization queue
- Scope and non-goals:
  - scope: versioning, release notes, QA packet, publish
  - non-goal: bundling unrelated feature spikes
- Architecture deltas:
  - release metadata/process only
- Validation plan:
  - `make check-all`
  - `make test-smoke`
  - `make test-uat`
  - `make quality-matrix`
  - `make uat-policy`
  - `npm pack --dry-run`
- Rollback/fallback:
  - hold release tag/publish until all mandatory gates pass
- Acceptance criteria:
  - release published with complete readiness + QA evidence artifacts
- Owner recommendation:
  - contributor with required gates: `gaia-release-manager`, `gaia-qa-evaluator`

## 5. Dependencies and Merge Order

- Shared contracts:
  - onboarding/auth contract reused by `#131`, `#130`, and `#134`
  - docs/state source-of-truth contract reused by `#129` and `#132`
- Item dependencies:
  - `#130` depends on `#131` module boundaries
  - `#133` depends on completed queue and merged docs/runtime updates
  - `#134` should land before `#130` to avoid compounding onboarding regressions
- Parallelization notes:
  - `#129` can run in parallel with `#131`
  - `#132` can run after `#129` source-of-truth decisions are merged

Recommended merge order:

1. `#134`
2. `#129`
3. `#131`
4. `#130`
5. `#132`
6. `#133`

## 6. Unclear Items Requiring Research

- Unknown:
  - Best Gaia linkage model for Claude Code auth metadata without token import
- Why blocked:
  - credential storage is OS-managed (keychain/libsecret/credential manager), not a guaranteed portable file format
- Required research output:
  - implementation note defining minimum metadata persisted by Gaia and privacy boundary

## 7. State Sync Checklist

- [x] `STATUS.md` updated
- [x] `ROADMAP.md` updated
- [x] `CHANGELOG.md` updated (planning/state sync notes for this round)
- [x] Sprint queue issues opened on GitHub (`#129`-`#134`)

## 8. Exit

- Final decision:
  - run a stabilization sprint focused on onboarding continuity, governance/docs alignment, modular refactor, Claude OAuth onboarding, preview rebuild, then release
- Next review date:
  - February 18, 2026
- Open follow-ups:
  - confirm post-`#134` runtime onboarding transcript in UAT artifact set
  - lock provider dependency/fallback policy before release lane `#133`
