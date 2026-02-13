# Sandbox Contract v1

Updated: February 13, 2026

## Purpose

Define the sandbox profile and escalation contract used by Gaia assistant
runtime execution paths.

Contract name: `gaia.sandbox.v1`
Schema version: `1`

This contract is published by `P2-E` and consumed by downstream lanes
(`P2-D`, `P2-F`, `P2-G`, `P2-H`).

## Profiles

Two runtime profiles are defined:

1. `read-only`
   - Filesystem mode: read-only policy gate
   - Network mode: deny by default
   - Escalation reasons:
     - `filesystem_write`
     - `network_access`
     - `high_risk_command`
2. `workspace-write`
   - Filesystem mode: workspace-write policy gate
   - Network mode: deny by default
   - Escalation reasons:
     - `network_access`
     - `high_risk_command`

Default profile: `read-only`

## CLI Surface

- `gaia sandbox profiles [--json]`
- `gaia sandbox run [--profile read-only|workspace-write] [--allow-network] [--approve-escalation] [--dry-run] -- <command ...>`

## Escalation Events

Escalation approvals/denials are recorded in:

- `~/.gaia-assistant/traces/sandbox-approvals.jsonl`

Event fields:

- `event_id` (UUID)
- `timestamp` (ISO-8601 UTC)
- `profile` (`read-only` or `workspace-write`)
- `network_mode` (`deny` or `allow`)
- `command_summary` (redacted command summary)
- `escalation_reasons` (array)
- `decision` (`approved` or `denied`)
- `decision_source` (`flag`, `prompt`, or `not-required`)
- `schema_version` (integer)

## Trace Actions

`actions.jsonl` includes:

- `sandbox_profiles`
- `sandbox_approval`
- `sandbox_run`

## Determinism Notes

- Default network mode is `deny` unless explicitly enabled.
- Escalation decisions are explicit and traceable.
- Blocking behavior is deterministic for denied escalations and forbidden
  capability policy levels.

## v1 Non-Goals

- OS-level process isolation (container/jail enforcement)
- Per-skill allowlist/policy decision engine (`P2-F`)
- Cross-lane unified trace schema extension (`P2-G`)
