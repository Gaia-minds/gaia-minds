---
name: gaia-incident-responder
description: Handle Gaia incidents with clear containment, evidence, and recovery workflows. Use this skill for benchmark regressions, automation failures, policy/safety incidents, and postmortem-driven remediation.
---

# Gaia Incident Responder Skill

Use this skill for incident triage, containment, recovery, and postmortem follow-through.

## Required Context

1. `docs/incidents/README.md`
2. `docs/incidents/postmortem-template.md`
3. `infrastructure/incident-response-template.md`
4. Relevant traces/logs/CI runs

## Workflow

1. Confirm incident and classify severity.
2. Contain impact and stop further damage.
3. Gather timeline evidence and impact metrics.
4. Coordinate recovery actions and validate restoration.
5. Open/update postmortem with root cause and corrective actions.
6. Track remediation owners and due dates until closure.

## Deliverables

- Incident response report using template.
- Postmortem document with timeline and corrective actions.
- Follow-up issue list for prevention work.

## Quality Gates

- Timeline is evidence-backed and complete.
- Root cause and corrective actions are explicit.
- Recovery validation is documented before closure.
- Incident is not closed until action owners and due dates exist.
