# Skills and Sandbox Enablement Research (Phase 2 Input)

**Date**: 2026-02-08
**Agent**: Codex Planner
**Category**: Synthesis
**Scope**: Evaluate practical patterns for skill systems and sandboxed code execution using Agent Skills, Claude Code Skills, and OpenAI Codex Skills documentation.

## Summary

This research compares how three ecosystems define skill packaging, discovery,
invocation, and safety controls. The result is a concrete set of Phase 2
deliverables for Gaia assistant:

- first-class skills command surface
- structured skill metadata and compatibility rules
- sandbox profiles for code execution
- approval/audit requirements tied to skill and sandbox runs

## Sources

- Agent Skills home: https://agentskills.io/home
- Agent Skills reference: https://agentskills.io/reference
- Claude Code Skills docs: https://code.claude.com/docs/en/skills
- OpenAI Codex Skills docs: https://developers.openai.com/codex/skills/
- OpenAI Codex configuration reference: https://developers.openai.com/codex/configuration/
- OpenAI Codex security overview: https://developers.openai.com/codex/security/
- OpenAI Codex skills + eval case study: https://openai.com/index/testing-codex-skills-with-evals/

## Key Findings

1. Skills must be discoverable without loading full instructions
   - Claude and Codex both support structured metadata and dynamic loading only
     when relevant.
   - This reduces context overhead and improves routing quality.

2. Skill packaging should be explicit and versionable
   - Codex supports discoverable skill directories and a `SKILL.md` contract.
   - Agent Skills emphasizes metadata + examples and interoperability patterns.
   - Practical implication: Gaia should support a canonical metadata shape and
     adapters for common skill formats.

3. Safety requires per-skill tool constraints, not only global policy
   - Agent Skills integration guidance highlights allowlists, confirmations, and
     logging for sensitive operations.
   - Claude guidance calls out permission settings and shell/tool restrictions.
   - Codex supports policy controls and approval workflows for command execution.

4. Sandboxing must be configurable and least-privilege by default
   - Codex configuration documents explicit sandbox modes (`read-only`,
     `workspace-write`, `danger-full-access`) and writable root overrides.
   - Security guidance recommends minimizing credentials/privileges and auditing
     command execution.
   - Practical implication: Gaia should expose clear sandbox profiles and bind
     them to approval policy and trace output.

5. Skills need dedicated evaluation coverage
   - OpenAI's Codex eval case study shows skill-specific eval loops improve
     reliability and reduce regressions.
   - Practical implication: add skill/sandbox scenarios to UAT and benchmark
     suites during Phase 2, not later.

## Cross-Platform Design Implications for Gaia

### Skill lifecycle

- Install/register skill from approved local paths.
- Index skill metadata without full instruction load.
- Resolve skill at runtime based on metadata and request context.
- Record invocation traces with `skill_id`, source path, required tools, and
  approval decisions.

### Sandbox lifecycle

- Define named profiles for execution:
  - `read-only` (default for inspection)
  - `workspace-write` (for bounded edits/tests)
- Require explicit approval for escalation beyond active profile.
- Deny network by default for code execution unless policy requires it.
- Emit audit trace for every sandboxed command.

## Recommended Phase 2 Items

Assistant track:

- Add `gaia skills list`
- Add `gaia skills inspect <skill>`
- Add `gaia skills validate <path>`
- Add safe skill invocation path with policy and trace hooks
- Add sandboxed code-run command/profile selection for approved coding tasks

Framework track:

- Add skill registry schema + compatibility adapter (`SKILL.md` and metadata-based specs)
- Add per-skill tool allowlist support in policy engine
- Add sandbox profile policy (`read-only`, `workspace-write`) with approval mapping
- Add skill/sandbox trace schema and retention guidance
- Add skill/sandbox UAT and benchmark scenarios in CI

## Open Questions

- Canonical Gaia skill manifest: keep `SKILL.md` only, or dual support for
  manifest files plus markdown instructions?
- Skill source trust model: local-only, signed bundles, or both?
- Network policy for sandboxed runs: global default-off with per-command
  exceptions, or profile-level toggles?
- Compatibility note: Codex docs currently reference `.agents/skills`, while
  other examples in ecosystem content may show different historical paths.
  Confirm Gaia's canonical path and migration behavior.

## Proposed Acceptance Criteria (Phase 2)

- Every skill execution emits trace metadata with skill identity and tool usage.
- Sandbox mode is explicit for every code execution event.
- No high-risk tool invocation bypasses approval policy.
- CI contains at least one deterministic skill suite and one sandbox policy suite.
