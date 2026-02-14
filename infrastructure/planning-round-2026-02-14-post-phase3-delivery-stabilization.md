# Post-Phase-3-Delivery Stabilization + Release Planning Round - 2026-02-14

Updated: February 14, 2026
Coordinator: Codex (planner main role)
Activated sub-roles: `gaia-planner`, `gaia-researcher`,
`gaia-integration-coordinator`, `gaia-technical-writer`

## 1. Planning Question

- Decision to make:
  - publish an execution-ready stabilization queue after Phase 3 delivery
    (`#93`-`#97`) with explicit merge order for:
    - dead-code/dead-artifact audit
    - `tools/gaia-assistant.py` modular refactor
    - README live-preview refresh
    - npm release cut
- Decision deadline:
  - February 14, 2026 (UTC)
- Scope boundary:
  - planning, issue decomposition, and state-sync updates only
  - no runtime implementation changes in this round

## 2. Inputs Reviewed

- `ROADMAP.md`:
  - Phase 3 queue (`#93`-`#97`) is marked delivered.
  - no post-delivery execution queue is published yet.
- `STATUS.md`:
  - all current sprint items are shipped.
  - `In Progress` and `Next Up` are empty.
- `CHANGELOG.md`:
  - `Unreleased` contains cumulative scope since `v0.2.0` and is release-ready
    but large.
- `infrastructure/self-evolution-evidence-rubric.md`:
  - still required for any self-evolution implementation PRs included in the
    next release scope.
- `assistant/reliability-baseline-phase3.json`:
  - reliability thresholds remain active and must be checked during release
    readiness for Phase 3 framework scope.
- Repository evidence snapshot (2026-02-14):
  - `tools/gaia-assistant.py` is `10,762` LOC.
  - largest function is `build_parser` (`823` LOC); multiple command handlers
    exceed `200` LOC.
  - two top-level helper functions appear unreferenced in-file:
    - `_collect_provider_profiles`
    - `_pick_profile_id`
  - live preview SVG assets still show older runtime text
    (for example `gaia-agent v0.1.0`) and do not surface latest command paths.
- Issues/PRs (live snapshot on 2026-02-14):
  - open issues before queue publication: none.
  - open PRs: none.
  - published this round:
    - `#104` planning lane
    - `#105` dead-code/dead-artifact audit
    - `#106` assistant modular refactor
    - `#107` README live-preview refresh
    - `#108` npm release `0.3.0`

## 3. Current State Snapshot

- Shipped:
  - Phase 3 queue (`#93`-`#97`) is complete and merged.
  - CI/check matrix was green on latest merged queue work.
- In progress:
  - none.
- Blocked:
  - none.
- Risk hotspots:
  - assistant runtime maintainability risk from monolithic command surface in
    `tools/gaia-assistant.py`.
  - release drift risk from a large `Unreleased` set without a new npm cut.
  - docs trust risk from stale live-preview assets.
  - dead-code/dead-artifact accumulation risk if refactor proceeds without a
    triage pass.

## 4. Proposed Work Items

### Item `#105` - Dead-code/dead-artifact audit across runtime/docs/release surfaces

- Scope and non-goals:
  - Scope: produce evidence-backed keep/remove/defer classification for dead
    code and stale artifacts.
  - Non-goal: broad behavior changes to assistant workflows.
- Architecture deltas:
  - none required; reporting artifact + targeted cleanup recommendations.
- Validation plan:
  - `make check-all`
  - targeted smoke/UAT checks when audit findings require code edits.
- Evidence contract (self-evolution applicability):
  - Not applicable (no self-evolution behavior change expected).
- Rollback/fallback:
  - keep candidate paths with explicit `defer` classification when confidence is
    insufficient for safe removal.
- Acceptance criteria:
  - no untriaged dead-code/dead-artifact candidates remain in scope.
- Owner recommendation:
  - contributor with `gaia-researcher` + `gaia-technical-writer`.

### Item `#106` - Refactor `tools/gaia-assistant.py` into modular command packages

- Scope and non-goals:
  - Scope: reduce monolith size/risk by extracting command-family modules while
    preserving CLI behavior.
  - Non-goal: net-new command surfaces.
- Architecture deltas:
  - extract parser builder and command handlers into cohesive modules while
    keeping stable entrypoint semantics for `bin/gaia.js` + npm package.
  - update `infrastructure/architecture.md` with module-boundary delta.
- Validation plan:
  - `python3 -m py_compile tools/gaia-assistant.py` + extracted modules
  - `make test-smoke`
  - `make test-uat`
  - `make check-all`
- Evidence contract (self-evolution applicability):
  - Not applicable unless behavior changes are introduced.
- Rollback/fallback:
  - keep compatibility wrapper path so module extraction can be rolled back
    without CLI contract changes.
- Acceptance criteria:
  - reduced monolith with explicit module boundaries and no command regressions.
- Owner recommendation:
  - contributor with `gaia-integration-coordinator` + `gaia-qa-evaluator`.

### Item `#107` - Refresh README live preview assets for current CLI capabilities

- Scope and non-goals:
  - Scope: refresh `assistant/assets/*` and README references so previews match
    current behavior (feedback, response profile, memory summarize).
  - Non-goal: full website redesign.
- Architecture deltas:
  - none.
- Validation plan:
  - `make check-all`
  - local markdown/link verification for touched docs.
- Evidence contract (self-evolution applicability):
  - Not applicable (documentation/asset refresh).
- Rollback/fallback:
  - retain previous SVG assets in git history; revert asset commit if quality
    or fidelity is disputed.
- Acceptance criteria:
  - preview assets reflect current runtime and no stale capability claims remain
    in README surfaces.
- Owner recommendation:
  - contributor with `gaia-technical-writer`.

### Item `#108` - Prepare and publish npm release `@gaia-minds/assistant-cli@0.3.0`

- Scope and non-goals:
  - Scope: cut next release from accumulated `Unreleased` scope with mandatory
    release/readiness gates and post-publish verification.
  - Non-goal: adding new runtime features during release PR.
- Architecture deltas:
  - none (release orchestration + versioning/changelog).
- Validation plan:
  - `npm pack --dry-run`
  - `python3 -m py_compile tools/gaia-assistant.py`
  - `make check-all`
  - `make test-smoke`
  - `make test-uat`
  - tag-triggered publish workflow success.
- Evidence contract (self-evolution applicability):
  - release notes must link required evidence for included self-evolution PRs
    per rubric and reliability checkpoint gate.
- Rollback/fallback:
  - no-go release decision until all gates pass; if publish incident occurs,
    document rollback path in readiness report and issue incident follow-up.
- Acceptance criteria:
  - npm version `0.3.0` published and verified installable.
  - changelog/version/release notes fully aligned to shipped scope.
- Owner recommendation:
  - contributor with required release gates:
    - `gaia-release-manager`
    - `gaia-qa-evaluator`

## 5. Dependencies and Merge Order

- Shared contracts:
  - CLI entrypoint contract (`bin/gaia.js` -> `tools/gaia-assistant.py`)
  - npm package payload contract in `package.json` (`files`)
  - release workflow version/tag contract (`.github/workflows/npm-publish.yml`)
  - reliability baseline thresholds (`assistant/reliability-baseline-phase3.json`)
- Item dependencies:
  - `#106` depends on `#105` candidate classification.
  - `#107` should merge after `#106` to avoid duplicate preview churn.
  - `#108` depends on `#106` + `#107` merge completion.
- Parallelization notes:
  - `#105` can start immediately.
  - `#107` capture workflow can be prepared in parallel, but final asset commit
    should wait for `#106`.
  - release lane `#108` starts only after prior lanes are merged and green.
- Proposed merge order:
  1. `#105`
  2. `#106`
  3. `#107`
  4. `#108`

## 6. Unclear Items Requiring Research

- Unknown:
  - final module boundary cut for `tools/gaia-assistant.py` that minimizes
    import cycles and keeps parser wiring deterministic.
  - Why blocked:
    - naive extraction can create hidden coupling and regress command dispatch.
  - Required research output:
    - short module-boundary map + import dependency check in refactor PR notes.

- Unknown:
  - preferred reproducible process for live-preview asset generation
    (hand-authored SVG vs scripted capture/render).
  - Why blocked:
    - without a repeatable process, preview assets drift quickly after CLI
      changes.
  - Required research output:
    - documented capture/render workflow committed with refreshed assets.

## 7. State Sync Checklist

- [x] `STATUS.md` updated with next-up queue `#105`-`#108`.
- [x] `ROADMAP.md` updated with post-delivery stabilization queue.
- [x] `CHANGELOG.md` updated to log this planning round + issue set publication.
- [x] Coordination issue comment posted (`#104`) with main-role declaration.

## 8. Exit

- Final decision:
  - execute a stabilization-to-release sequence with audit-first triage,
    refactor second, docs-preview refresh third, and release cut last.
- Next review date:
  - February 18, 2026 (or immediately at release gate if lanes finish earlier).
- Open follow-ups:
  - contributor role should claim `#105` first and enforce mandatory gates for
    each downstream work type before merge.
