# Continuous Security Validation Strategy for Broad-Source Skill Imports (Phase 3 `#115`)

Updated: 2026-02-14
Owner: @TonyThePredictor / Codex

## 1. Research Question

- Question: Which security-validation strategy should Gaia adopt to continuously harden broad-source skill imports against prompt-injection and malicious-instruction risks while keeping validation deterministic and contributor-operable?
- Decision this supports: Define implementation-ready validation-gate deltas for the signal-driven self-evolution queue (`#112`, `#113`) and ongoing skill-import safety posture.
- Constraints:
  - local-first, deterministic validation workflow
  - no raw-conversation telemetry requirement
  - bounded operational cost for CI + contributor terminal runs
  - compatibility with existing `gaia skills validate` and quality-matrix harness

## 2. Scope and Method

- In scope:
  - assess current Gaia validation baseline and identify security gaps
  - synthesize current primary guidance/research on prompt-injection and supply-chain controls
  - produce actionable, issue-linked recommendations for near-term hardening
- Out of scope:
  - direct runtime rollout of new policy/validator behavior in this lane
  - redesign of full agent runtime policy engine
- Research method:
  - baseline review of current Gaia validator/runtime docs and fixtures
  - external-source synthesis using standards/org docs and current research papers
  - option tradeoff analysis (security efficacy, complexity, operational cost, compatibility)

## 3. Evidence Log

| Source | Date | Claim Supported | Notes |
| --- | --- | --- | --- |
| OWASP GenAI Top 10, LLM01 Prompt Injection | 2025 (accessed 2026-02-14) | Prompt injection remains a primary risk class for LLM apps and agents. | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ |
| OWASP GenAI Top 10, LLM03 Supply Chain | 2025 (accessed 2026-02-14) | Third-party components/plugins/agents create supply-chain risk requiring integrity controls. | https://genai.owasp.org/llmrisk/llm03-supply-chain/ |
| NIST AI RMF 1.0 | 2023-01-26 | AI risk management should be governed with continuous measurement + controls, not one-off checks. | https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10 |
| NIST SP 800-218 (SSDF) | 2022-02-04 | Secure software practice requires integrity, provenance, and repeatable verification in SDLC. | https://csrc.nist.gov/pubs/sp/800/218/final |
| Microsoft Learn: Secure your AI app from prompt injection attacks | accessed 2026-02-14 | Defense-in-depth controls are needed (input controls, privilege minimization, monitoring). | https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/prompt-injection |
| Anthropic docs: Mitigate prompt injection | accessed 2026-02-14 | Treat tool-bound instructions as untrusted and apply layered mitigations for indirect injection. | https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/mitigate-prompt-injection |
| OpenAI Codex docs: Internet access & prompt-injection risk notes | accessed 2026-02-14 | When external content is fetched, prompt-injection risk must be explicitly mitigated and bounded. | https://developers.openai.com/codex/cloud/environments/internet-access |
| SLSA v1.1 approval | 2024-04-16 | Provenance/attestation frameworks are available and mature enough for practical adoption. | https://slsa.dev/blog/2024/04/16/slsa-v1.1/ |
| in-toto specification | accessed 2026-02-14 | Supply-chain metadata/attestation model supports integrity verification in automation pipelines. | https://in-toto.io/docs/in-toto/ |
| arXiv: StruQ (structured-query defense) | 2024-02-09 | Data/instruction separation improves prompt-injection resistance with minimal utility loss in tested setups. | https://arxiv.org/abs/2402.06363 |
| arXiv: SecAlign (preference-optimization defense) | 2024-10-07 | Training-based defenses can materially reduce injection success under benchmark conditions. | https://arxiv.org/abs/2410.05451 |
| arXiv: ZEDD (embedding-drift detector) | 2026-01-18 | Lightweight runtime detection can provide high detection performance across models in benchmarked settings. | https://arxiv.org/abs/2601.12359 |

## 4. Findings

### Facts

- Gaia already has deterministic `gaia skills validate` controls with blocking severities (`high`, `critical`) and fixed static signatures for prompt-injection, exfiltration, and unsafe shell patterns (`tools/gaia-assistant.py`).
- Gaia quality matrix includes deterministic malicious fixtures for direct prompt-injection, exfiltration, pipe-to-shell, and reverse-shell payload classes (`assistant/fixtures/skills/manifest.json`, `tools/quality-matrix.py`).
- Current validator enforces bounded scan limits (`SKILL_VALIDATION_MAX_SCAN_FILES=120`) and report artifacts, but does not yet enforce provenance-admission policy (for example attestation requirements for broad-source imports) (`tools/gaia-assistant.py`).
- OWASP and major platform guidance consistently treat prompt injection and third-party/supply-chain risk as first-order concerns in production LLM/agent systems.
- Current research indicates two simultaneous truths:
  - structured or training-based defenses can significantly reduce attack success in controlled evaluation
  - attackers continue to discover transferable/obfuscated variants, so single-layer controls are brittle.

### Inferences

- Gaia’s current static signatures are a strong baseline but are likely vulnerable to obfuscation and formatting-based bypasses that do not match current pattern rules.
- For broad-source skill imports, provenance trust must be enforced as an admission gate, not only logged post hoc.
- The right near-term strategy is layered and incremental: strengthen deterministic static checks + provenance policy now, while evaluating lightweight runtime detectors as optional secondary gates.
- Continuous research should remain operationalized (monthly + incident-triggered refresh) because attack techniques evolve faster than fixed rule sets.

## 5. Options and Tradeoffs

| Option | Benefits | Risks | Cost/Complexity | Compatibility |
| --- | --- | --- | --- | --- |
| A. Signature-only expansion | Fast to ship; deterministic; low infra overhead. | Evasion risk remains high for obfuscation/novel phrasing; weak provenance guarantees. | Low | High (fits current validator/fixtures). |
| B. Layered deterministic gate: signatures + obfuscation-aware canonicalization + provenance admission policy (attestation/pinning/health checks) | Strongest immediate risk reduction with auditable deterministic behavior; aligns with OWASP/NIST/SLSA guidance. | More policy/config surface; potential false positives if rules are too aggressive. | Medium | High (extends existing `skills validate` + quality matrix + policy traces). |
| C. Model-based detector/judge layer (embedding drift/classifier/LLM referee) in addition to deterministic checks | Can catch patterns missed by static rules; adaptive against novel attacks. | Non-determinism risk, model drift, extra latency/cost, additional governance burden. | Medium-high | Medium (requires careful CI/test contract changes). |

## 6. Recommendation

- Recommended option: **Option B now**, with scoped exploratory track from Option C.
- Confidence level: **Medium-High**.
- Why this option:
  - maximizes practical risk reduction in the current architecture
  - remains deterministic and auditable for CI/contributor workflows
  - directly supports `#112` without blocking on uncertain model-based detector behavior
- Adoption criteria:
  - land provenance-admission implementation lane (`#122`)
  - land obfuscation-aware validator hardening + adversarial fixtures (`#123`)
  - update `#112` implementation plan to consume these security gate outputs in skill-first triage decisions
  - define monthly `#115` refresh cadence and incident-triggered expedited updates
- Rollback path:
  - keep new provenance and obfuscation controls behind explicit policy modes (`warn` -> `enforce`) so operators can degrade safely if false-positive rates exceed thresholds
  - retain current validator baseline as fallback execution path during rollout stabilization

## 7. Unknowns and Follow-Up Research

- Unknown: realistic false-positive rates from obfuscation-aware scanning on benign skill corpora.
- Impact: excessive false positives can block legitimate imports and reduce contributor throughput.
- Follow-up task: build benign-corpus regression fixture set and threshold contract (proposal under `#123`).

- Unknown: best minimum provenance policy that is strict enough for safety but practical for ecosystem adoption.
- Impact: too strict stalls imports; too lax weakens trust guarantees.
- Follow-up task: prototype policy tiers in `#122` (`warn`, `enforce`) and measure acceptance/failure rates.

- Unknown: when lightweight model-based detectors provide net benefit over deterministic gates.
- Impact: premature adoption could add noise/cost without meaningful security gain.
- Follow-up task: keep as research-only evaluation stream under recurring `#115` updates before runtime adoption.

## 8. Actionable Next Steps

- Issue/PR actions:
  - `#122` implement provenance admission gate for broad-source skill imports.
  - `#123` implement obfuscation-aware skill validation hardening and adversarial fixture expansion.
  - `#112` consume `#122/#123` outputs for skill-first unmet-intent triage (`existing-skill-enable` vs `skill-import-candidate` vs `core-feature-gap`).
- Owner suggestions:
  - `#122`: contributor + required sub-roles `gaia-security-reviewer`, `gaia-qa-evaluator`.
  - `#123`: contributor + required sub-roles `gaia-security-reviewer`, `gaia-qa-evaluator`.
  - `#115` cadence owner: rotating `gaia-researcher` contributor monthly or incident-driven.

## 9. State Sync Checklist

- [x] `STATUS.md` updated (marked `#115` In Progress)
- [x] `ROADMAP.md` updated (added seeded security-hardening follow-on lanes `#122`, `#123`)
- [x] `CHANGELOG.md` updated (added research artifact + follow-on issue references)

No architecture delta in this research packet.
