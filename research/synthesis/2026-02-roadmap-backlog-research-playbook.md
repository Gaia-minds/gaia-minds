# Roadmap and Backlog Research Playbook (2026-02)

**Date**: 2026-02-08
**Agent**: Codex Planner
**Category**: Synthesis
**Scope**: Validate Gaia roadmap and backlog priorities against current repository state and external guidance.

## Summary

This document records the research process used to evaluate whether current
roadmap and backlog items are sensible, in what order they should be tackled,
and which items still require discovery work before implementation.

The outcome is a reusable method for future agents: start from repository
truth, map planned outcomes to implemented behavior, then use external
standards to validate sequencing and risk.

## Sources

Internal repository sources:

- `ROADMAP.md`
- `STATUS.md`
- `README.md`
- `assistant/README.md`
- `skills/gaia-contributor/SKILL.md`
- `tools/gaia-assistant.py`
- `tools/agent-loop.py`
- `tools/agent-config.yml`
- `tools/benchmark.py`
- `.github/workflows/benchmark.yml`
- `.github/workflows/smoke-tests.yml`
- `.github/workflows/npm-publish.yml`
- `infrastructure/contributor-playbook.md`
- `CHANGELOG.md`

External sources used for validation:

- NIST AI RMF core: https://airc.nist.gov/airmf-resources/ai-risk-management-framework
- NIST AI RMF resource updates: https://airc.nist.gov/airmf-resources/
- OpenAI eval best practices: https://platform.openai.com/docs/guides/evals-best-practices?api-mode=responses
- Google SRE on SLOs: https://sre.google/workbook/implementing-slos/
- Google SRE on postmortems: https://sre.google/workbook/postmortem-culture/
- GitHub Actions schedule behavior: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- RFC 9110 (idempotency semantics): https://www.rfc-editor.org/rfc/rfc9110
- Argo Rollouts canary pattern: https://argo-rollouts.readthedocs.io/en/stable/features/canary/
- SemVer specification: https://semver.org/

## What Was Verified

### Repository reality on 2026-02-08

- No open issues.
- No open pull requests.
- "Immediate 14-Day Priorities" in roadmap still points to issues `#35/#36/#37`
  even though those issues are closed.
- Status dashboard "Next Up" section has the same stale items.
- Release version drift in docs:
  - package is `0.2.0`
  - multiple docs still advertise `0.1.1`

### Feature surface vs roadmap intent

- Autopilot exists with rollback and incident logging, but current profile/action
  scope is intentionally narrow (`safe-daily` and low-risk actions only).
- Benchmark harness exists and compares against a baseline.
- Benchmarks run on PR/push, but no nightly trend loop yet.
- Policy enforcement currently centers on capability levels and confirmation flow;
  "risk + source + user scope" policy modeling is not fully formalized.

## Why These Roadmap Items Make Sense

The roadmap direction is valid, but execution order matters:

1. Evaluation before autonomy expansion
   - External guidance supports integrating evaluation into the delivery loop
     rather than treating it as one-time hardening.
2. Reliability controls before complexity growth
   - SLO, incident handling, and rollback maturity should come before broad
     multi-agent expansion.
3. Explicit policy and audit evidence for automated actions
   - NIST AI RMF and project guardrails both favor measurable governance over
     implicit trust.

## Recommended Sequencing Model

1. Backlog hygiene first
   - Refresh stale roadmap/status priority sections.
   - Open concrete, scoped issues for the next phase.
2. Phase 2 operational utility
   - Recurring task execution and reminders with safe defaults.
   - Policy engine v1 with explicit dimensions.
3. Reliability and measurement hardening
   - Nightly benchmark trend collection.
   - Incident/postmortem process with templates.
4. Self-evolution and canary controls
   - Hypothesis -> eval evidence -> guarded rollout path.
5. Multi-agent runtime only after the above gates are stable.

## Research Protocol for Future Agents

Use this protocol when evaluating backlog realism:

1. Establish timestamped baseline
   - Record date and current commit SHA.
   - Record open issue and PR counts.
2. Validate planning documents against reality
   - Compare `ROADMAP.md`, `STATUS.md`, and live issue states.
   - Flag stale references immediately.
3. Map roadmap outcomes to concrete code/workflows
   - For each planned item, locate commands, config, tests, and CI gates.
4. Classify each item
   - `ready`: clear scope, dependencies known, measurable completion.
   - `partially-ready`: implementation exists but missing controls or coverage.
   - `unclear`: ambiguous requirements or unresolved architecture decisions.
5. Validate sequence against external standards
   - Governance and safety (NIST AI RMF).
   - Evals and release confidence.
   - Reliability/SLO and incident practice.
6. Produce execution output
   - What to tackle now.
   - What to defer.
   - What needs research spikes first.

## Reusable Command Checklist

```bash
# 1) Snapshot repo reality
git rev-parse HEAD
gh issue list --repo Gaia-minds/gaia-minds --state open --limit 200 --json number,title,updatedAt,url
gh pr list --repo Gaia-minds/gaia-minds --state open --limit 200 --json number,title,updatedAt,url

# 2) Detect stale roadmap/status/version references
rg -n "Immediate 14-Day Priorities|Next Up|0\\.1\\.1|0\\.2\\.0|#35|#36|#37" ROADMAP.md STATUS.md README.md assistant/README.md skills/gaia-contributor/SKILL.md package.json

# 3) Map features to code and workflows
rg -n "autopilot|rollback|incident|benchmark|drift|schedule|policy|capability" tools .github/workflows assistant

# 4) Verify issue state for referenced IDs
gh issue view 35 --repo Gaia-minds/gaia-minds --json number,state,closedAt,url
gh issue view 36 --repo Gaia-minds/gaia-minds --json number,state,closedAt,url
gh issue view 37 --repo Gaia-minds/gaia-minds --json number,state,closedAt,url
```

## Evidence-to-Decision Mapping Template

Use this table structure in future backlog reviews:

| Roadmap Item | Current State | Evidence | Decision |
| --- | --- | --- | --- |
| Example: scheduled tasks | Partially-ready | `gaia` has loop modes, no robust scheduler guarantees | Implement next with reliability guardrails |
| Example: multi-agent runtime | Unclear for now | No strong SLO/incident trend baseline yet | Defer until reliability gates pass |

## Known Unclear Areas Requiring Research

- Reminder delivery channel policy (local-only vs external channels).
- Full policy model dimensions and conflict resolution (risk/source/scope).
- Canary rollout strategy for npm CLI releases.
- Reliability strategy for scheduled runs when platform scheduling is delayed.
- Governance alignment updates as NIST AI RMF revisions evolve.

## Research Quality Checklist

Before finalizing a roadmap recommendation:

- Include absolute dates, not only relative terms.
- Verify all issue and PR states live.
- Distinguish observed facts from inferences.
- Include at least one external governance source and one reliability source.
- Include a concrete "what next" task list with ordering.
- Document unresolved questions and required research spikes.

## Update Notes

- This playbook should be revised when phase boundaries, governance model, or
  release process changes materially.
- Add a new synthesis entry for each major roadmap reassessment rather than
  overwriting historical analysis.
- Prefer opening reassessment issues via:
  `.github/ISSUE_TEMPLATE/roadmap-backlog-review.yml`
