---
name: gaia-privacy-memory-steward
description: Review Gaia memory features for privacy, retention, consent, and safe data handling. Use this skill for memory architecture decisions, policy controls, and pre-merge privacy checks on memory-related lanes.
---

# Gaia Privacy Memory Steward Skill

Use this skill for privacy and governance validation of memory-related work.

## Required Context

1. `ROADMAP.md` (memory lane and follow-on plans)
2. `infrastructure/privacy-memory-review-template.md`
3. `infrastructure/security.md`
4. Relevant memory design docs/issues

## Workflow

1. Identify memory data types and retention boundaries.
2. Review consent, access control, and deletion behavior.
3. Evaluate privacy/security risks (including memory poisoning/leakage).
4. Ensure policy engine and trace/audit hooks are defined.
5. Document approval status and required remediations.

## Deliverables

- Privacy and memory review report using template.
- Risk matrix with mitigations and owners.
- Approval/block decision for memory changes.

## Quality Gates

- Retention and deletion guarantees are explicit.
- Consent model is clear and testable.
- Auditability requirements are met.
- High-risk memory issues block merge until mitigated.
