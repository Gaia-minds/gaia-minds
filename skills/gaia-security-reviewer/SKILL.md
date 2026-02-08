---
name: gaia-security-reviewer
description: Perform structured security reviews for Gaia features, lanes, and PRs. Use this skill for threat analysis, malicious-behavior detection, security gate validation, and mitigation planning before merge.
---

# Gaia Security Reviewer Skill

Use this skill for security-critical review and pre-merge risk gating.

## Required Context

1. `infrastructure/security.md`
2. `infrastructure/contributor-playbook.md`
3. `infrastructure/security-review-template.md`
4. Relevant lane plan in `infrastructure/phase2-lane-implementation-plans.md`

## Workflow

1. Scope the review (lane/PR/components).
2. Identify threat surface and privilege boundaries.
3. Review for:
   - sandbox/policy bypass paths
   - malicious skill vectors (onboarding/runtime)
   - secrets or trust-boundary violations
   - unsafe escalation flows
4. Record findings with severity and exploit path.
5. Define blocking vs non-blocking actions.
6. Re-verify mitigations before final decision.

## Deliverables

- Security review report using template.
- Severity-ranked findings with owners.
- Merge decision: approve/request changes/block.

## Quality Gates

- Findings include evidence and reproducible rationale.
- High/critical issues include explicit blocking actions.
- Mitigations map to concrete code/docs changes.
- Security decision is documented in PR/issue thread.
