# Privacy and Memory Review - Unmet-Intent Signals (2026-02-14)

## 1. Scope

- Memory feature/component:
  - Phase 3 unmet-intent signal extraction and local signal ledger (`#111`)
- Reviewer:
  - Codex (`gaia-privacy-memory-steward` sub-role)

## 2. Data Classification

- Data types stored:
  - derived signal aggregates only:
    - `signal_id`, `signal_type`, `intent_tag`, `confidence`, `count`
    - `first_seen_at`, `last_seen_at`
    - `source_event_ids` (feedback/trace IDs only)
- Sensitivity levels:
  - medium (behavioral metadata), no raw transcript content copied to signal artifacts
- Retention targets:
  - default 90-day derived-signal window (`signals_retention_days`)
  - deterministic record cap (`signals_max_records`, default 300)

## 3. Policy Controls

- Consent model:
  - collection default-on with explicit opt-out (`gaia config set signals_enabled false`)
- Access controls:
  - capability gates on command surface:
    - `memory_write` -> `signals extract`
    - `memory_read` -> `signals list`
    - `memory_export` -> `signals export`
    - `memory_delete` -> `signals clear`
- Deletion guarantees:
  - explicit clear path: `gaia signals clear`
  - local file delete equivalent: remove `~/.gaia-assistant/data/unmet-intent-signals.json`
- Encryption/provenance:
  - local-only persistence under assistant home
  - provenance through `source_event_ids` and structured traces:
    - `signals_extract`, `signals_list`, `signals_export`, `signals_clear`

## 4. Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| Raw transcript leakage into signal ledger | High | Low | Extraction stores derived tags/counts only; deterministic privacy test blocks raw phrase presence in ledger |
| Re-identification via source links | Medium | Medium | Source references limited to local feedback/trace IDs; no transcript text copied |
| Unbounded behavioral retention | Medium | Low | Enforced retention window + deterministic cap with config bounds |
| Unauthorized local export/clear operations | Medium | Low | Existing capability policy gates (`memory_export`, `memory_delete`) enforced on command paths |

## 5. Compliance Checks

- [x] Retention policy documented
- [x] User delete/export path defined
- [x] Audit trail coverage confirmed
- [x] Policy engine hooks defined

## 6. Decision

- Approval status:
  - Approved for merge (no blocking privacy defects found)
- Required follow-ups:
  - `#112`: map derived signal classes to deterministic skill-first triage actions
  - `#113`: ensure derived-signal-only constraint is preserved in hypothesis candidate integration
