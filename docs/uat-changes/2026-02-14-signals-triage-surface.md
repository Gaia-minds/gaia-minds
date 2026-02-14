# UAT Change Record: Signals Skill-First Triage Coverage

Date: 2026-02-14
Issue: `#112`
PR: pending

## Summary

Extended deterministic UAT/smoke governance coverage for unmet-intent
skill-first triage command behavior.

Changes:

- Added UAT scenario:
  - `signals_skill_first_triage_matrix`
- Added smoke scenario:
  - `signals_skill_first_triage_matrix`
- Added reusable deterministic check script:
  - `tools/signal-triage-check.sh`
- Added triage fixture matrix:
  - `assistant/signal-triage-fixtures.json`
- Updated feature mapping:
  - `assistant/feature-catalog.json` entries for `signals`, `signals triage`,
    `skills`, `skills validate`, and `config set`.

## Why This Change

`#112` introduces a new command surface (`gaia signals triage`) and decision
contract that routes unmet-intent signals into deterministic classes with
security-gated follow-up actions.

Without governance updates, the triage command and class-routing behavior could
drift without detection in UAT/smoke suites.

## Risk

Without this update, regressions could misclassify import candidates, skip
required security gates, or route unsafe intents into enablement paths.

## Confidence Plan

- Deterministic fixture matrix asserts all class outcomes:
  - `existing-skill-enable`
  - `skill-import-candidate`
  - `core-feature-gap`
  - `out-of-scope-or-rejected`
- Matrix asserts required security gates for import candidates and validation
  failure blocking for unsafe skill matches.
- Coverage is enforced in both smoke and UAT suites.
- `make uat-policy` validates command-to-scenario mapping after this change.
