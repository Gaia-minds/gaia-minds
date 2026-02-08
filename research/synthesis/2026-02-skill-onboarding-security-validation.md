# Skill Onboarding Security Validation (Phase 2 Input)

**Date**: 2026-02-08
**Agent**: Codex Planner
**Category**: Synthesis
**Scope**: Define validation checks required before onboarding third-party skills into Gaia assistant, with focus on malicious behavior and supply-chain attacks.

## Summary

Skill onboarding is a software supply-chain boundary. A skill can contain
instructions, code, scripts, and network behavior that bypasses normal
assistant assumptions if not validated. Phase 2 should include a security
gate that blocks onboarding unless a skill passes static, provenance, policy,
and runtime-safety checks.

## Sources

- OWASP Top 10 for LLM Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- OWASP LLM01 Prompt Injection: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP LLM05 Supply Chain Vulnerabilities: https://genai.owasp.org/llmrisk/llm05-supply-chain-vulnerabilities/
- NIST SP 800-218 (SSDF): https://csrc.nist.gov/pubs/sp/800/218/final
- SLSA: https://slsa.dev
- OpenSSF Scorecard: https://github.com/ossf/scorecard
- OpenAI Codex skills/config/sandbox docs:
  - https://github.com/openai/codex/blob/main/docs/skills.md
  - https://github.com/openai/codex/blob/main/docs/config.md
  - https://github.com/openai/codex/blob/main/docs/sandbox.md
- Vercel Agent Skills repository: https://github.com/vercel-labs/agent-skills

## Threat Model for Skill Onboarding

1. Prompt-injection behavior embedded in skill instructions
   - Skills can instruct the model to ignore system/user constraints, expose
     secrets, or trigger unsafe actions.

2. Malicious or risky script execution
   - Scripts may exfiltrate data, execute destructive commands, or fetch
     untrusted remote payloads.

3. Supply-chain tampering
   - Skill bundles can be modified between publication and installation.
   - Dependency or artifact provenance may be unknown.

4. Over-privileged execution
   - Skills may request shell/network/file permissions beyond legitimate scope.

## Recommended Validation Gate (Before Install/Enable)

### A) Manifest + structure validation

- Require `SKILL.md` and parse frontmatter fields (`name`, `description`,
  `version`, `author`, `license` where available).
- Validate optional files (`metadata.json`, `scripts/`, `rules/`) against
  schema and size limits.
- Reject archives with path traversal, hidden executables, or disallowed
  binary types.

### B) Static security lint

- Lint scripts for high-risk patterns:
  - credential harvesting (`env`, token files, auth stores)
  - destructive operations (`rm -rf`, history rewrite)
  - remote pipe-to-shell patterns
  - unexpected outbound endpoints
- Block onboarding on high-severity findings; require explicit allowlist for
  medium findings.

### C) Provenance and source trust checks

- Restrict onboarding to allowlisted sources by default.
- Record immutable source identifier (repo URL + commit SHA + file hashes).
- Add optional provenance verification path aligned with SLSA concepts.
- Add repository health checks (e.g., OpenSSF Scorecard threshold) for remote
  public sources.

### D) Policy compatibility checks

- Compute required capabilities from skill definition and scripts.
- Validate requested capabilities against Gaia policy and sandbox profiles:
  - default: `read-only`, no network
  - escalations require explicit approval and trace
- Enforce per-skill tool allowlists.

### E) Sandboxed verification run

- Run deterministic dry-run in isolated workspace with:
  - no secrets mounted
  - restricted filesystem
  - denied network unless explicitly required
- Capture all tool calls and generated outputs for review.

### F) Runtime guardrails after onboarding

- Store decision trace: source hash, validator results, approvals, capabilities.
- Enforce canary activation (disabled by default for new skill; gradual enable).
- Auto-disable skill after repeated policy violations or failed safety checks.

## Phase 2 Deliverables Derived From Research

Assistant track:

- Add `gaia skills validate <path|repo>` command returning pass/fail + findings.
- Add `gaia skills doctor <skill>` command to show effective permissions and
  sandbox profile before execution.

Framework track:

- Add onboarding security gate pipeline (`structure -> static lint ->
  provenance -> policy compatibility -> sandbox dry-run`).
- Add risk scoring model and fail thresholds for onboarding decisions.
- Add audit schema for onboarding events and rejection reasons.
- Add CI coverage for malicious skill fixtures (prompt-injection text, unsafe
  script calls, network exfil patterns).

## Candidate Acceptance Criteria

- 100% of onboarded skills have immutable source hash and validation report.
- Zero skill activation without explicit capability + sandbox assignment.
- Zero skill onboarding when high-severity static checks fail.
- All skill onboarding decisions are traceable and reproducible from artifacts.
