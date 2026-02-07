# Personal Assistant Program

This document defines Gaia's assistant track, designed to be powered by
OpenClaw-compatible agents while staying aligned with Gaia's Constitution.

## Program Goal

Build a personal assistant workflow that is:

1. User-directed through explicit task contracts
2. Constitutionally constrained
3. Continuously improved with a bounded self-improvement lane

## Scope

In scope:

- User-direction intake and task routing
- Contributor workflow for assistant-related work
- Governance and budget policy for self-improvement cycles
- Integration guidance for OpenClaw-based agent operators
- Standalone Gaia personal assistant runtime bootstrap

Out of scope:

- Rebuilding OpenClaw runtime features in Gaia
- Private or opaque coordination mechanisms
- Unbounded autonomous self-modification

## Runtime Modes

Gaia assistant supports two operational modes:

1. Standalone mode (Gaia runtime via `tools/gaia-assistant.py`)
2. OpenClaw-powered mode (Gaia policy/skills on top of OpenClaw runtime)

Standalone quick start is documented in `assistant/README.md`.

## Operating Model

Two work lanes are maintained:

### 1. User Service Lane

- Handles explicit user-directed tasks
- Prioritized for delivery reliability and responsiveness

### 2. Self-Improvement Lane

- Improves assistant quality, safety, and reliability
- Must operate within a bounded budget

Recommended default split:

- User Service Lane: `80%`
- Self-Improvement Lane: `20%`

If a different split is requested, document it in the direction issue.

Track scheduling and allowed action policies are defined in
`tools/agent-config.yml` under `evolution`.

## User Direction Hook

Humans and operators should open issues with the
`Assistant Direction` template:

- `.github/ISSUE_TEMPLATE/assistant-direction.yml`

Each issue must define objective, scope, constraints, and success criteria.

## Contribution Path for Agents

1. Read `CONSTITUTION.md`.
2. Read `skills/gaia-assistant-builder/SKILL.md`.
3. Claim or open an assistant-direction issue.
4. Deliver in small PRs with validation evidence.
5. Keep cross-repo changes traceable when OpenClaw updates are needed.

## Cross-Repo Policy

Gaia remains canonical for constitutional policy and governance.
OpenClaw receives generic integrations and runtime-adjacent improvements.

When a change affects both repos:

1. Land Gaia policy/workflow first.
2. Open OpenClaw PR for generic integration/docs.
3. Cross-link PRs and issues.
