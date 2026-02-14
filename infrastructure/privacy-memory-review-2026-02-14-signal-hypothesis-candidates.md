# Privacy and Memory Review

Updated: 2026-02-14

## 1. Scope

- Lane: `#113` Integrate unmet-intent signals into hypothesis candidate
  generation
- Reviewer: `@TonyThePredictor / Codex` (`gaia-privacy-memory-steward` sub-role)
- Components reviewed:
  - `tools/hypothesis-pipeline.py` (`signals-candidates` subcommand)
  - `assistant/hypothesis-signal-candidate-fixtures.json`
  - `tools/hypothesis-signal-candidate-check.sh`
  - hypothesis workflow/contract docs updates

## 2. Data Classification and Sources

- Inputs used for candidate generation:
  - derived unmet-intent signal ledger (`unmet-intent-signals.json`)
  - derived signal triage ledger (`unmet-intent-signal-triage.json`)
  - local config (`signals.enabled`, retention settings)
- Prohibited input class:
  - raw conversation transcript content
  - free-form correction text payloads
- Candidate artifacts include only derived summary fields:
  - signal id/type/tag
  - counts/confidence/recency
  - triage class/confidence/follow-up action
  - threshold gate pass/fail evidence

## 3. Privacy Guardrails

- Opt-out control enforced:
  - if `signals.enabled=false`, candidate promotion is disabled (`hold` mode).
- Retention-window guard enforced:
  - candidate recency gates are bounded by effective retention window and remain
    within default 90-day policy unless user lowers retention.
- Raw-content rejection guard enforced:
  - forbidden raw-text key classes (`raw_text`, `transcript`, `messages`,
    `content`, etc.) reject candidate promotion.
- No network export:
  - command writes local artifacts only.

## 4. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Raw text accidentally enters source ledgers | Privacy boundary breach in candidate artifact | Forbidden-key detection rejects promotion and surfaces explicit reason |
| Opt-out ignored in candidate generation | Policy violation | Config + ledger collection flags are both required for promotion |
| Long-tail stale signals drive candidate noise | Low-quality self-evolution suggestions | Deterministic recency threshold bounded by retention window |

## 5. Verification

- `make hypothesis-signals-candidate-fixture`: pass
- `python3 tools/hypothesis-pipeline.py signals-candidates ... --json` fixture
  paths: pass
- fixture asserts:
  - derived-only payload keys
  - threshold routing (`promote|hold|reject`)
  - opt-out enforcement (`promoted_count=0` when disabled)
  - generated promoted stubs validate under existing hypothesis contract

## 6. Decision

- Privacy/memory review status: approve
- Conditions:
  - keep candidate generation suggestion-only and gate-controlled
  - continue expanding forbidden-key corpus as new leakage patterns emerge
