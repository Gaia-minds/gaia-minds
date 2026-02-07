# Gaia Minds Roadmap

Updated: February 7, 2026

This roadmap is now optimized for fast execution.

We are no longer planning on quarter-scale timelines by default. Because work is
performed by coding assistants plus the Gaia assistant itself, we can ship in
weekly cycles with daily improvements.

## Vision

Build a benevolent, life-protecting personal assistant and a self-evolving
framework that continuously improves the assistant under constitutional
constraints.

## Execution Model (Compressed)

### Acceleration assumptions

- Most implementation and documentation work is done by coding assistants.
- Gaia assistant contributes back to its own improvement loop.
- PR flow remains human-reviewable, but execution cadence is daily.
- Releases are expected weekly, with patch releases as needed.

### Dual-track operating model

1. Assistant Evolution Track
   - Improve user-facing behavior, reliability, and usefulness.
2. Framework Evolution Track
   - Improve the self-evolution engine, governance, safety gates, and evaluation stack.

Default budget remains:

- User service: 80%
- Self-improvement: 20%

## Timeline At A Glance

## Phase 0: Baseline (Completed)

Timeline: February 1 to February 7, 2026

Delivered:

- Gaia standalone CLI published on npm (`@gaia-minds/assistant-cli`)
- Gaia-native auth onboarding path (Codex broker + local token store)
- Dual-track scheduler in config and runtime loop
- npm release automation workflow and dry-run validation
- Refreshed onboarding docs and live demo assets

## Phase 1: Daily Assistant Utility

Timeline: February 8 to February 14, 2026
Status: In Progress

Assistant track outcomes:

- Add interactive session mode (`gaia chat`) for direct user requests.
- Add first-party personal workflows:
  - capture note/task
  - summarize research links
  - generate actionable plans from user goals
- Add profile-aware preferences in local config.

Framework track outcomes:

- Add capability registry with explicit permission levels (`safe`, `confirm`, `forbidden`).
- Add structured action traces for every executed step.
- Add deterministic smoke test suite for assistant critical paths.

Exit criteria:

- 20 canonical user tasks with >=80% success.
- 100% of executed actions written to structured logs.
- Zero unreviewed high-risk actions.

## Phase 2: Trusted Automation

Timeline: February 15 to February 28, 2026
Status: Planned

Assistant track outcomes:

- Add scoped autopilot mode for approved capability sets.
- Add recurring/scheduled task execution.
- Add proactive reminders with user-controlled cadence.

Framework track outcomes:

- Add policy engine for action gating by risk, source, and user scope.
- Add rollback primitives for failed automation runs.
- Add incident log schema and postmortem template for regressions.

Exit criteria:

- >=90% pass rate on regression suite.
- <5% failed runs requiring manual recovery.
- All automated tasks linked to explicit policy decisions.

## Phase 3: Framework Self-Evolution v1

Timeline: March 1 to March 21, 2026
Status: Planned

Assistant track outcomes:

- Improve quality through feedback loops (`helpful`, `not helpful`, correction capture).
- Add personalized response profiles and memory summarization.

Framework track outcomes (self-evolution core):

- Add evaluation harness with benchmark task set and score history.
- Add hypothesis pipeline:
  - propose improvement
  - run offline eval
  - open PR with evidence
  - canary rollout
  - full rollout on pass
- Add automatic drift detection against safety and quality baselines.
- Add hard token-budget enforcement per cycle and per track.

Exit criteria:

- Three consecutive releases with measurable quality gain.
- No constitutional/safety regression across benchmark suite.
- Every self-evolution PR includes before/after metrics.

## Phase 4: Multi-Agent Assistant Runtime

Timeline: March 22 to April 12, 2026
Status: Planned

Assistant track outcomes:

- Introduce specialist agents (research, coding, planning, operations).
- Add coordinator behavior for delegation and synthesis.
- Add user-visible execution plans before multi-agent runs.

Framework track outcomes:

- Add delegation policy with confidence and risk thresholds.
- Add cost and latency-aware task routing.
- Add per-agent quality scoring and fallback strategies.

Exit criteria:

- Multi-agent mode outperforms single-agent baseline on quality and latency.
- Delegation failures auto-fallback without user impact.

## Phase 5: Scale, Reliability, and Ecosystem

Timeline: April 13 to May 10, 2026
Status: Planned

Assistant track outcomes:

- Expand integrations and connectors based on contributor demand.
- Ship stable UX around install, onboarding, and long-running operation.

Framework track outcomes:

- Add nightly benchmark runs with trend dashboards.
- Add release train automation with quality gates.
- Add contributor playbooks for rapid, safe iteration.

Exit criteria:

- Weekly stable releases with no critical regressions.
- Onboarding to first useful result in <=10 minutes.
- Full auditability for assistant and framework changes.

## Framework Self-Evolution Backlog (Always Active)

The framework track continuously maintains these pillars:

1. Evaluation
   - benchmark tasks, pass/fail criteria, quality scoring
2. Governance
   - risk taxonomy, policy gates, reviewer protocols
3. Safety
   - constitutional checks, anomaly detection, rollback controls
4. Learning
   - feedback ingestion, lesson extraction, memory summaries
5. Delivery
   - CI gates, release automation, canary strategy

## KPI Dashboard

Assistant KPIs:

- Task success rate on canonical suite
- Time to first useful user output
- User correction rate per session
- End-to-end latency by task type

Framework KPIs:

- Self-evolution PR throughput per week
- Percentage of PRs with eval evidence
- Regression incident count and MTTR
- Safety gate violation rate

## Ongoing Guardrails

- Constitutional compliance is non-negotiable.
- No hidden behavior, opaque autonomy, or secret data paths.
- High-risk changes require explicit review.
- Security and auditability are first-class release requirements.

## Immediate 14-Day Priorities

1. Ship `gaia chat` MVP with local session memory.
2. Implement capability registry + permission prompts.
3. Add benchmark harness and baseline scoring artifacts.
4. Add autopilot-scoped task runner with rollback.
5. Publish contributor playbook for assistant vs framework changes.

## Milestones Log

| Date | Milestone | Notes |
|------|-----------|-------|
| 2026-02-01 | Repository created | Initial structure |
| 2026-02-07 | npm CLI published (`0.1.0`) | First global install path live |
| 2026-02-07 | npm CLI patch published (`0.1.1`) | Global runtime fixes + refreshed docs/demo |

This roadmap is a living document and should be updated at least weekly.
