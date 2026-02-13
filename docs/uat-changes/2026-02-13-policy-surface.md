# Policy Engine Surface UAT Update (2026-02-13)

## Why this change

`P2-F` adds new policy command paths in `tools/gaia-assistant.py`:

- `policy evaluate`
- `policy allowlist set`
- `policy allowlist clear`
- `policy allowlist list`

It also routes `sandbox run` through policy decisions before execution.

UAT and smoke coverage were extended so policy decisions, allowlist behavior,
and tool-override bypass attempts remain deterministic and policy-enforced in
CI.

## Risk

- High.
- Policy-gating drift can silently weaken enforcement if command mappings and
  deterministic scenarios are not updated with runtime changes.

## Confidence and Safeguards

- Added deterministic scenario `policy_engine_gating_and_allowlists` validating:
  - `policy evaluate` allow + deny outcomes
  - allowlist set/list/clear lifecycle
  - `sandbox run` deny path via per-skill allowlist
  - blocked tool-assertion mismatch path to prevent manual policy relabeling
  - `policy_decision` trace emission
- Added feature-catalog mappings for:
  - `policy`
  - `policy evaluate`
  - `policy allowlist`
  - `policy allowlist set`
  - `policy allowlist clear`
  - `policy allowlist list`
- Added matching smoke coverage for the same flow.

## Validation

- `make test-smoke`
- `make test-uat`
- `make uat-policy`
