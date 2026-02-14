# User-Intent Signal Architecture Planning Round - 2026-02-14

Updated: February 14, 2026
Coordinator: Codex (planner main role)
Activated sub-roles: `gaia-planner`, `gaia-researcher`,
`gaia-integration-coordinator`, `gaia-technical-writer`,
`gaia-privacy-memory-steward`

## 1. Planning Question

- Decision to make:
  - define architecture and execution order for converting user interaction
    behavior into privacy-preserving self-evolution signals, while routing
    feature-demand gaps through a skill-first triage path before core-runtime
    implementation work.
- Decision deadline:
  - February 14, 2026 (UTC)
- Scope boundary:
  - planning/design decomposition only; no runtime implementation in this round.

## 2. Inputs Reviewed

- `ROADMAP.md`:
  - Phase 3 queue (`#93`-`#97`) and stabilization queue (`#105`-`#108`) are
    published; signal-driven evolution follow-on is not yet decomposed.
- `STATUS.md`:
  - active `Next Up` queue is currently refactor/release oriented (`#105`-`#108`).
- `CHANGELOG.md`:
  - includes feedback and memory summarize additions, but no dedicated
    unmet-intent signal architecture queue yet.
- `infrastructure/self-evolution-evidence-rubric.md`:
  - any self-evolution behavior/governance change requires full rubric evidence.
- `assistant/reliability-baseline-phase3.json`:
  - follow-on signal-driven automation must remain bounded by baseline and drift
    gates.
- Runtime architecture context:
  - `infrastructure/architecture.md`:
    - feedback lane explicitly states no automatic self-evolution updates yet.
    - feedback is local-only and bounded (`~/.gaia-assistant/data/feedback.json`).
    - memory policy/consent/retention and traceability contracts already exist.
  - `assistant/README.md`:
    - feedback capture and skills runtime surfaces are active (`gaia feedback`,
      `gaia skills list/inspect/validate`).
- Issues/PRs:
  - planning lane published: `#110`
  - follow-on queue published: `#111`, `#112`, `#113`
  - continuous security-research lane published: `#115`

## 3. Current State Snapshot

- Shipped:
  - explicit user quality feedback (`helpful`/`not-helpful`) capture
  - deterministic response-profile auto-selection from feedback heuristics
  - skill discovery + validation command surfaces
  - hypothesis pipeline with canary and evidence gates
- In progress:
  - stabilization/release queue (`#105`-`#108`) remains open.
- Blocked:
  - no deterministic pipeline currently derives unmet-feature demand from user
    interaction patterns.
- Risk hotspots:
  - privacy leakage risk if raw conversation logs are copied into evolution
    artifacts.
  - false-positive evolution work if unmet-demand signals do not distinguish
    "needs skill enablement/import" vs "core feature gap."
  - governance risk if signal-driven proposals bypass existing evidence/quality
    gates.

## 4. Proposed Work Items

### Item `#111` - Privacy-preserving unmet-intent signal extraction

- Scope and non-goals:
  - Scope:
    - derive deterministic unmet-intent signals from local interaction artifacts
      (feedback linkage, traces, command failure patterns, correction patterns).
    - persist only sanitized/derived signal records (no raw transcript copy in
      signal store).
  - Non-goal:
    - automatic rollout/self-update behavior.
- Architecture deltas:
  - add derived signal schema and local bounded ledger (for example
    `intent-signals.jsonl`) under assistant local state.
  - add deterministic signal extraction pass over existing local artifacts.
  - expose signal inspection CLI path for user/human review.
  - product decision lock:
    - collection default is `on`
    - explicit opt-out control is required
    - retention default for derived signals is `90 days` with deterministic cap
- Validation plan:
  - deterministic extraction fixtures
  - redaction/no-raw-transcript assertions
  - `make check-all` + smoke/UAT coverage for new command path
- Evidence contract (self-evolution applicability):
  - likely `Not applicable` unless this lane directly changes self-evolution
    behavior; if it does, rubric must be completed.
- Rollback/fallback:
  - disable extractor write path and keep read-only diagnostics if privacy or
    correctness gates fail.
- Acceptance criteria:
  - unmet-intent signals are reviewable, bounded, and privacy-compliant.
- Owner recommendation:
  - contributor with mandatory memory/privacy gates:
    - `gaia-privacy-memory-steward`
    - `gaia-qa-evaluator`

### Item `#112` - Skill-first unmet-intent triage

- Scope and non-goals:
  - Scope:
    - classify unmet-intent signals into deterministic actions:
      - `existing-skill-enable`
      - `skill-import-candidate`
      - `core-feature-gap`
      - `out-of-scope-or-rejected`
    - integrate triage with skill discovery/inspection/validation surfaces.
  - Non-goal:
    - automatic unapproved external skill installation.
- Architecture deltas:
  - add triage decision layer consuming `#111` signals + skills registry context.
  - emit triage artifacts with confidence and rationale.
  - add policy hooks for unsafe skill-candidate rejection.
  - product decision lock:
    - broader non-local skill sources are permitted as candidates
    - all such candidates must pass security validation gates before activation
    - prompt-injection and malicious-instruction checks are mandatory
- Validation plan:
  - fixture-based decision matrix with expected classes
  - policy bypass/unsafe candidate rejection checks
  - `make check-all`
- Evidence contract (self-evolution applicability):
  - `Not applicable` unless triage directly modifies self-evolution behavior.
- Rollback/fallback:
  - force unresolved cases to `core-feature-gap` + human review queue.
- Acceptance criteria:
  - each unmet-intent signal has an auditable triage class with deterministic
    policy behavior.
- Owner recommendation:
  - contributor with:
    - `gaia-security-reviewer`
    - `gaia-qa-evaluator`

### Item `#113` - Integrate unmet-intent signals into hypothesis generation

- Scope and non-goals:
  - Scope:
    - map aggregated/triaged intent signals into hypothesis-candidate artifacts.
    - enforce thresholds (frequency/recency/confidence) before candidate
      promotion.
    - preserve derived-signal-only policy in generated evidence.
  - Non-goal:
    - bypassing PR evidence rubric, reliability gates, or canary decisions.
- Architecture deltas:
  - extend hypothesis candidate generation inputs with intent-signal aggregates.
  - define contract fields linking candidate to signal evidence summary.
  - enforce upstream product lock constraints:
    - derived-signal-only input policy
    - opt-out-aware candidate generation behavior
    - evidence windows bounded by `90-day` retention policy
- Validation plan:
  - deterministic candidate-generation fixtures
  - threshold behavior checks (`hold` when data is insufficient/noisy)
  - `make check-all` + hypothesis fixture coverage updates
- Evidence contract (self-evolution applicability):
  - Applies:
    - baseline, delta, thresholds/guardrails, rollback/fallback, and risk notes
      are mandatory.
- Rollback/fallback:
  - keep suggestion mode only (`hold`/manual review) when threshold confidence
    is below defined floor.
- Acceptance criteria:
  - hypothesis candidates can be traced to privacy-compliant derived signals and
    remain fully gate-controlled.
- Owner recommendation:
  - contributor with mandatory gates:
    - `gaia-privacy-memory-steward`
    - `gaia-qa-evaluator`
    - self-evolution evidence rubric + CI check

### Item `#115` - Continuous security validation research for broad-source skill imports

- Scope and non-goals:
  - Scope:
    - maintain an ongoing research loop for skill-validation defenses against
      prompt-injection and malicious-instruction attacks.
    - publish actionable validation-rule deltas for contributor lanes.
  - Non-goal:
    - direct runtime rollout without linked implementation issue/PR.
- Architecture deltas:
  - no immediate runtime delta; research-to-implementation handoff contract.
- Validation plan:
  - periodic synthesis artifact publication and adversarial fixture proposals.
- Evidence contract (self-evolution applicability):
  - Not applicable unless research lane directly changes self-evolution runtime
    behavior.
- Rollback/fallback:
  - if research findings are inconclusive, hold policy changes and keep current
    validation thresholds.
- Acceptance criteria:
  - recurring security research outputs are linked into skill-triage/validation
    lanes and reduce blind spots over time.
- Owner recommendation:
  - contributor with `gaia-researcher`; add `gaia-security-reviewer` when
    findings trigger runtime/policy changes.

## 5. Dependencies and Merge Order

- Shared contracts:
  - feedback contract (`~/.gaia-assistant/data/feedback.json`)
  - trace schema/metadata envelope (`trace_schema_version=2`)
  - skills runtime + validation contracts
  - hypothesis pipeline evidence contract
  - memory privacy consent/retention controls
- Item dependencies:
  - `#111` must land before downstream triage/generation.
  - `#112` depends on `#111` and should consume `#115` research updates.
  - `#113` depends on `#111` + `#112`.
  - `#115` runs in parallel and continuously informs `#112`/future skill-import
    lanes.
- Parallelization notes:
  - design/prototyping can run in parallel, but merge order should remain strict
    to avoid contract churn.
- Recommended order:
  1. `#111`
  2. `#115` (parallel supporting lane)
  3. `#112`
  4. `#113`

## 6. Unclear Items Requiring Research

- Unknown:
  - best deterministic signal taxonomy for unmet requests that avoids overfitting
    to wording variants.
  - Why blocked:
    - weak taxonomy increases noise and backlog churn.
  - Required research output:
    - minimal taxonomy + fixture examples mapped to each class.

- Unknown:
  - external skill import trust model for "skill-import-candidate"
    classification and approval.
  - Why blocked:
    - importing unsafe skills can bypass policy expectations.
  - Required research output:
    - provenance requirements + approval workflow proposal.

- Unknown:
  - minimum threshold settings that avoid promoting one-off requests to
    self-evolution hypotheses.
  - Why blocked:
    - low thresholds risk noisy/unhelpful hypothesis queue.
  - Required research output:
    - threshold defaults and hold/rollback conditions.

## 7. State Sync Checklist

- [x] `STATUS.md` updated (queue visibility + post-release signal follow-on).
- [x] `ROADMAP.md` updated with signal-driven follow-on queue.
- [x] `CHANGELOG.md` updated with this planning artifact + issue publication.
- [x] Coordination issue comment posted (`#110`) with role declaration.

## 8. Exit

- Final decision:
  - adopt a three-stage architecture:
    1. privacy-preserving unmet-intent extraction
    2. skill-first triage
    3. hypothesis candidate integration
  - keep all stages deterministic, local-first, and gate-controlled.
- Next review date:
  - February 18, 2026 (or earlier if stabilization/release queue closes first).
- Open follow-ups:
  - contributor role should execute `#105`-`#108` first, then claim `#111`.
