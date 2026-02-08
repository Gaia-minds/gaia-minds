---
name: gaia-qa-evaluator
description: Evaluate Gaia changes against acceptance criteria and regression risk. Use this skill for smoke/UAT/benchmark verification, quality scoring, and release-gate decisions.
---

# Gaia QA Evaluator Skill

Use this skill for validation-heavy QA and evaluation rounds.

## Required Context

1. `STATUS.md`
2. `ROADMAP.md` (exit criteria)
3. `infrastructure/qa-evaluation-template.md`
4. Relevant issue/PR acceptance criteria

## Workflow

1. Build evaluation scope and acceptance matrix.
2. Execute required checks for scope:
   - `make test-smoke`
   - `make check-all`
   - UAT/benchmark tasks as applicable
3. Compare results to baseline and detect regressions.
4. Classify failures by severity and user impact.
5. Produce release-readiness verdict and follow-ups.

## Deliverables

- QA evaluation report using template.
- Pass/fail matrix with command evidence.
- Blocking defect list and retest plan.

## Quality Gates

- Every failed criterion has evidence and owner.
- Regression claims include before/after reference.
- Go/no-go decision is explicit and justified.
- Validation logs are linked in issue/PR notes.
