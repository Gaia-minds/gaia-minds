# UAT Governance Bootstrap (2026-02-08)

## Why this change

Gaia now requires deterministic terminal UAT coverage for all assistant feature
surfaces, including newly introduced features from manual and self-evolve paths.

## Risk

- Medium: CI now enforces additional policy checks and can block merges when
  UAT mapping/governance requirements are not met.

## Confidence and Safeguards

- Added deterministic local UAT runner with failure bundles.
- Added explicit feature catalog + scenario manifest.
- Added policy checker for command/action coverage and new-feature UAT updates.
- Added PR-body justification and reviewer-approval enforcement for protected
  UAT changes.

## Validation

- `python3 tools/uat-runner.py --manifest assistant/uat-scenarios.json --json-out assistant/uat-results.json`
- `python3 tools/check-uat-policy.py --base-ref origin/main --reviewer TonyThePredictor`
- `make check-all`
