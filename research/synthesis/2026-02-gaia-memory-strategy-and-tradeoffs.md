# Gaia Memory Strategy and Tradeoffs (P2-I)

Date: 2026-02-13
Issue: #60
Main role: contributor
Sub-roles: gaia-researcher, gaia-privacy-memory-steward, gaia-qa-evaluator

## 1. Research Question

- Question: What memory architecture should Gaia adopt next, balancing local-first privacy, retrieval quality, safety, and implementation speed?
- Decision this supports: memory architecture recommendation before implementation lanes are opened.
- Constraints:
  - Keep current session-memory runtime stable until design lock.
  - Preserve assistant-track local/offline usability.
  - Integrate with existing policy/sandbox/trace controls from `P2-C` through `P2-H`.

## 2. Scope and Method

- In scope:
  - Memory taxonomy and storage/retrieval options.
  - Privacy/safety controls and failure modes.
  - Minimal benchmark plan and implementation backlog split.
- Out of scope:
  - Shipping runtime memory implementation in this lane.
- Research method:
  - Current-state analysis from Gaia repo contracts/docs.
  - Primary-source review from official docs and papers.
  - Option matrix with explicit tradeoffs and migration/rollback.

## 3. Evidence Log

| Source | Date (published/updated) | Claim Supported | Notes |
| --- | --- | --- | --- |
| https://arxiv.org/abs/2310.08560 | 2023-10-12 (v1), 2024-02-12 (v2) | Tiered memory management is a practical way to work around context limits for multi-session assistants. | MemGPT frames memory as virtual context management. |
| https://arxiv.org/abs/2304.03442 | 2023-04-07 (v1), 2023-08-06 (v2) | Agent memory can be modeled as stored experiences + synthesized reflections + dynamic retrieval. | Supports taxonomy + summary-memory design. |
| https://www.sqlite.org/fts5.html | Updated 2025-07-19 | SQLite has built-in FTS5 support in standard distributions, suitable for local lexical retrieval. | FTS5 included in amalgamation since 3.9.0. |
| https://www.sqlite.org/json1.html | Updated 2025-12-03 | SQLite JSON functions are built in by default in modern versions. | Useful for metadata/provenance in local memory store. |
| https://www.sqlite.org/limits.html | Updated 2025-11-24 | SQLite limits are large enough for local memory workloads. | Default max page count now supports large DB size. |
| https://sqlite.org/wal.html | Updated 2025-05-31 | WAL mode improves concurrency/perf and supports durability controls via checkpointing. | Important for local memory writes + read concurrency. |
| https://github.com/pgvector/pgvector | README observed 2026-02-13 | Postgres+pgvector offers exact + approximate search with HNSW/IVFFlat and recall/speed tuning. | Strong path for multi-device/server-scale memory. |
| https://www.postgresql.org/docs/18/ddl-rowsecurity.html | PostgreSQL 18 docs (current) | Row-level policies can enforce per-user row access constraints. | Relevant for multi-tenant/user-isolated memory access. |
| https://www.postgresql.org/docs/18/continuous-archiving.html | PostgreSQL 18 docs (current) | PITR/WAL archiving gives strong recovery/rollback primitives. | Useful for memory corruption rollback strategy. |
| https://qdrant.tech/documentation/concepts/payload/ | Crawled 2026-02 | Vector DB payload filtering enables metadata-aware semantic retrieval. | Supports richer hybrid retrieval filters. |
| https://qdrant.tech/documentation/concepts/snapshots/ | Crawled 2026-02 | Snapshot model gives collection-level backup/restore semantics. | Operational overhead in distributed setups remains non-trivial. |
| https://owasp.org/www-project-top-10-for-large-language-model-applications/ | v1.1 (current page) | Prompt injection and sensitive info disclosure are first-class LLM risks to memory systems. | Directly maps to memory poisoning/leak controls. |
| https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10 | Published 2023-01-26 | Risk-managed, trustworthy AI lifecycle framing should guide memory design controls. | Baseline governance reference. |
| https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence | Published 2024-07-26 | Generative-AI profile extends risk practices for GenAI-specific concerns. | Supports explicit controls + measurement plan. |
| https://eur-lex.europa.eu/eli/reg/2016/679/2016-05-04/eng | Regulation text (Article 17) | Deletion/erasure guarantees are mandatory in many user-data contexts. | Motivates delete/export/retention controls from day one. |
| https://openreview.net/forum?id=wCu6T5xFjeJ | Published 2021-10-11 | Retrieval evaluation should include heterogeneous, zero-shot robustness tests. | BEIR gives retrieval metric framing (nDCG/recall contexts). |
| https://arxiv.org/abs/2210.07316 | 2022-10-13 (v1), 2023-03-19 (v3) | Embedding quality varies across tasks; no single method dominates. | Supports benchmarking multiple retrieval strategies. |
| https://docs.ragas.io/en/v0.3.3/concepts/metrics/ | Updated 2025-08-20 | Practical RAG evaluation includes context precision/recall and faithfulness metrics. | Useful for memory helpfulness/grounding checks. |

## 4. Findings

### Facts

- Gaia currently has local session continuity, policy controls, sandbox controls, and rich trace metadata, but no explicit long-term memory architecture contract.
- MemGPT and Generative Agents both show the importance of separating fast context from longer-lived memory representations and dynamic retrieval.
- SQLite currently provides built-in full-text and JSON primitives with high practical limits and WAL journaling.
- Postgres + pgvector provides exact and ANN retrieval paths with mature operational features and policy primitives.
- Dedicated vector stores such as Qdrant provide metadata payload filtering and snapshot tooling, but introduce separate operational systems.
- OWASP LLM risks include prompt injection and sensitive disclosure, directly relevant to memory poisoning and private-memory leakage.
- GDPR Article 17 explicitly requires erasure capabilities for personal data contexts.
- BEIR/MTEB and RAG metric frameworks show that retrieval quality must be measured across multiple task styles; one embedding/retrieval stack is rarely best everywhere.

### Inferences

- Gaia should not adopt a remote-first memory backend immediately; local-first is lower risk for privacy, offline usability, and rollout complexity.
- A single-store strategy is not future-proof: local-first should be the default now, with a migration path to Postgres+pgvector for multi-device/shared-scale scenarios.
- Memory safety must be policy-integrated, not bolted on: read/write/delete/export controls need first-class policy capabilities and trace events.
- Benchmarking memory quality needs both retrieval metrics (precision/recall/ranking) and safety metrics (poisoning resistance and leakage rate), not just user-perceived helpfulness.

## 5. Options and Tradeoffs

| Option | Benefits | Risks | Cost/Complexity | Compatibility |
| --- | --- | --- | --- | --- |
| A. Local files only (JSONL + summary snapshots) | Very simple, zero DB dependency, easy debugging. | Weak queryability, poor semantic retrieval, fragile retention/deletion guarantees at scale. | Low initial complexity; medium long-term maintenance burden. | High short-term compatibility; weak long-term quality. |
| B. Local SQLite hybrid (FTS5 + JSON metadata + optional embedding table) | Strong local/offline support, single-file deploy, fast exact/lexical retrieval, good provenance schema fit. | ANN support is less mature than dedicated vector systems; needs careful compaction/TTL design. | Medium complexity; low operational overhead. | Very high compatibility with current local assistant runtime. |
| C. Postgres + pgvector (exact + ANN) | Mature access-control/recovery ecosystem, scalable shared/multi-device memory, flexible retrieval tuning. | Requires server lifecycle/ops; less suitable for offline-first default. | Medium-high complexity and ops cost. | Medium compatibility now; high for future multi-node needs. |
| D. Dedicated vector DB + metadata store (for example Qdrant + SQL) | Strong semantic retrieval features and filtering, high vector-scale performance. | Additional infrastructure, consistency concerns across stores, higher privacy/compliance surface. | High complexity and ops overhead. | Medium-low near term; potentially high at very large scale. |

## 6. Recommendation

- Recommended option: **Option B now, with a planned migration path to Option C**.
- Confidence level: **Medium-High**.
- Why this option:
  - Aligns with Gaia's local-first assistant behavior and current CLI deployment model.
  - Provides enough retrieval power for near-term memory quality work while keeping privacy boundaries simpler.
  - Keeps migration open for shared/multi-device scaling via a well-defined MemoryStore interface.
- Adoption criteria:
  - Memory contract v1 defines taxonomy, retention metadata, provenance, and policy hooks.
  - Memory operations are policy-gated (`read/write/delete/export`) with trace coverage.
  - Benchmark baseline established for retrieval quality + safety metrics.
- Rollback path:
  - Feature-flag long-term memory off; retain current session-memory-only behavior.
  - Keep append-only raw memory event logs to allow backfill/reindex or rollback to previous summary/index states.

## 7. Proposed Architecture Deltas (Research Proposal)

### 7.1 Runtime

- Introduce `MemoryStore` abstraction with adapters:
  - `sqlite_local` (default)
  - `postgres_vector` (future optional)
- Memory record contract (`memory.v1`):
  - `memory_id`, `memory_type` (`session_short`, `user_long`, `project`, `safety_audit`)
  - `subject_id` (user/session/project)
  - `content`, `summary`, `source_trace_id`
  - `confidence`, `importance`, `last_accessed_at`
  - `retention_ttl`, `consent_scope`, `created_at`, `updated_at`
- Retrieval pipeline (initial):
  - exact key lookup -> lexical retrieval -> semantic retrieval -> recency/importance rerank
  - deterministic fallback when embeddings are unavailable

### 7.2 Policy and Sandbox Integration

- Add policy capability classes:
  - `memory_read`, `memory_write`, `memory_delete`, `memory_export`
- Default policy posture:
  - read: `confirm` for high-sensitivity memory classes
  - write: `confirm` when source is untrusted/high-risk
  - delete/export: `confirm` (or `admin` scope)
- Memory writes from tool outputs should be sandbox-context aware and include source provenance.

### 7.3 Trace Schema Integration

- Add trace events:
  - `memory_capture`
  - `memory_retrieve`
  - `memory_update`
  - `memory_delete`
  - `memory_compact`
- Extend metadata fields:
  - `memory_id`, `memory_type`, `subject_id`, `consent_scope`
  - retrieval diagnostics (`retrieval_mode`, `candidate_count`, `selected_count`)
  - poisoning/leak guard decisions (`blocked_reason`, `policy_id`)

### 7.4 Privacy/Safety Controls

- Consent must be explicit per memory class; default deny for cross-session personal memory.
- Retention windows must be configurable and enforceable by compaction jobs.
- Delete guarantees require both logical delete and index tombstoning with verifiable trace evidence.
- Sensitive fields should support redaction-at-write and encrypted-at-rest deployment options.

## 8. Minimal Benchmark Plan (Memory Quality)

### 8.1 Test slices

- Preference recall: known user preferences retrieved correctly across sessions.
- Project memory recall: previously saved project constraints retrieved in planning tasks.
- Safety memory: blocked/sensitive memories are not leaked in unauthorized contexts.
- Poisoning resistance: malicious injected memory candidates do not dominate retrieval.

### 8.2 Metrics

- Retrieval quality:
  - `Recall@k`, `nDCG@k` style metrics for ground-truth memory retrieval sets.
  - Context metrics inspired by RAG frameworks: context precision, context recall.
- Response quality:
  - Faithfulness/groundedness against retrieved memory context.
  - Hallucinated recall rate (memory claim with no supporting memory evidence).
- Safety/privacy:
  - Unauthorized retrieval leakage rate.
  - Poisoned-memory acceptance rate.
- Performance/cost:
  - p95 retrieval latency.
  - token overhead from memory context injection.

### 8.3 Initial target thresholds (proposal)

- `Recall@5 >= 0.85` on deterministic memory fixtures.
- Faithfulness >= 0.90 on benchmarked answer set.
- Unauthorized leakage rate = 0 in deterministic policy scenarios.
- p95 retrieval latency <= 150 ms for local SQLite baseline fixture set.

## 9. Follow-on Implementation Backlog (Parallelizable)

1. `Memory Runtime Contract + SQLite Adapter` (`#75`)
- Scope: memory schema, storage adapter, CRUD APIs, migration hooks.
- Acceptance: deterministic read/write/delete flows, retention metadata persisted.

2. `Memory Retrieval + Ranking Pipeline` (`#76`)
- Scope: exact + lexical + semantic retrieval and rerank strategy.
- Acceptance: benchmark harness reports recall/ranking metrics; regression thresholds enforced.

3. `Memory Policy + Privacy Controls` (`#77`)
- Scope: consent model, capability mapping, deletion/export guarantees, sensitive redaction paths.
- Acceptance: policy decisions and trace evidence cover all memory operations; privacy tests pass.

4. `Memory QA and Red-Team Harness` (`#78`)
- Scope: poisoning fixtures, leakage tests, faithfulness/helpfulness eval dashboards.
- Acceptance: CI memory suite blocks regressions and produces triage artifacts.

## 10. Mandatory Gate Evidence

### 10.1 Privacy and Memory Steward Review

- Memory feature/component: P2-I memory strategy recommendation.
- Reviewer role: gaia-privacy-memory-steward.
- Data classes identified: session, user-long-term, project, safety/audit.
- Required controls:
  - explicit consent boundaries by class
  - retention + deletion guarantees (including index tombstones)
  - provenance-linked audit traces for all memory mutations
- Decision: **Approved with required follow-through in implementation lanes**.
- Required follow-ups:
  - add policy capability classes for memory operations
  - define default retention matrix before runtime rollout
  - add leakage and poisoning tests in QA harness

### 10.2 QA Evaluator Review

- Feature/lane: P2-I memory research gate.
- Acceptance criteria source: issue #60.
- Evaluator role: gaia-qa-evaluator.
- Criteria check:
  - >=3 viable options with explicit tradeoffs: **pass**
  - one recommendation with migration/rollback: **pass**
  - security/privacy mapping to policy/sandbox: **pass**
  - clear implementation backlog with acceptance criteria: **pass**
- Validation evidence:
  - `make generate-indexes`
  - `make check-all`
- Decision: **GO (research gate complete, implementation remains gated until follow-on lanes land)**.

## 11. Unknowns and Follow-Up Research

- Unknown: best lightweight semantic index strategy in strict local/offline mode without large dependency footprint.
  - Impact: may affect recall/latency targets and packaging complexity.
  - Follow-up: spike two embedding/ranking strategies in a controlled fixture harness.
- Unknown: encryption-at-rest default path (OS-level encryption only vs optional embedded DB encryption).
  - Impact: compliance posture and migration complexity.
  - Follow-up: evaluate deployment profiles and threat model assumptions with maintainers.
- Unknown: user-facing consent UX for memory class opt-in/out in CLI flows.
  - Impact: privacy guarantees and usability.
  - Follow-up: design and test deterministic consent prompt flows.

## 12. State Sync Checklist

- [x] `STATUS.md` updated (P2-H and P2-I marked shipped; next-up memory lanes queued)
- [x] `ROADMAP.md` reviewed (no change required)
  - No change reason: roadmap already tracks memory strategy as a research gate and does not require sequencing changes from this recommendation.
- [x] `CHANGELOG.md` updated (unreleased memory strategy research entry)
- [x] Follow-on implementation issues created (`#75`, `#76`, `#77`, `#78`)
