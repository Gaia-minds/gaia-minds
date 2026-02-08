# Terminal UAT Policy

This document defines deterministic user-acceptance testing (UAT) policy for
Gaia's terminal assistant.

## Goals

- Drive assistant features the same way a user would in the terminal.
- Keep runs deterministic/local (no live provider dependency).
- Block PRs when new feature surfaces are not covered by UAT.
- Produce enough diagnostics to root-cause failures quickly.

## Deterministic Provider Digital Twins

UAT runs in local deterministic mode with API keys unset.

Provider-facing features are exercised through local provider twins:

- `openai` -> expected reply prefix: `[local-openai]`
- `openrouter` -> expected reply prefix: `[local-openrouter]`
- `anthropic` -> expected reply prefix: `[local-anthropic]`
- `openai-codex` -> expected reply prefix: `[local-openai-codex]`

## Command Surface Coverage

Coverage registry files:

- Scenario manifest: `assistant/uat-scenarios.json`
- Feature catalog: `assistant/feature-catalog.json`

Policy script `tools/check-uat-policy.py` enforces that every command path in
`tools/gaia-assistant.py` and every action type in `tools/agent-actions.py`
has an explicit mapping to scenario IDs.

## Required CI Checks

- `uat-tests` workflow (`make test-uat`)
- `uat-policy` workflow (coverage + governance enforcement)

## Failure Diagnostics Bundle

On every UAT run, the runner writes:

- Structured report: `assistant/uat-results.json`
- Bundle root: `assistant/uat-artifacts/<run-id>/`

Bundle contents include:

- per-scenario transcript logs (`<scenario>.log`)
- environment/runtime metadata (`metadata.json`)
- failure summary with log tails (`failure-summary.md`, on failures)
- deterministic reproduction command per scenario (`repro` field in JSON)

## UAT Change Governance

Protected UAT files:

- `assistant/feature-catalog.json`
- `assistant/uat-scenarios.json`
- `tools/uat-runner.py`
- `tools/check-uat-policy.py`

When protected files change, PRs must include:

1. `## UAT Change Justification` section in PR body.
2. Change record under `docs/uat-changes/`.
3. Approval from `@TonyThePredictor` (or PR authored by `@TonyThePredictor`).

## Local Commands

```bash
# Run full deterministic UAT
make test-uat

# Validate feature/UAT policy
make uat-policy

# Re-run one scenario
python3 tools/uat-runner.py --run provider_twin_openai
```
