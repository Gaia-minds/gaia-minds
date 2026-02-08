## Summary
-

## Track Declaration
- [ ] `assistant-track`
- [ ] `framework-track`
- [ ] Cross-track (`assistant-track` + `framework-track`)

## Risk Level
- [ ] Low
- [ ] Medium
- [ ] High (requires explicit maintainer review before merge)

## Validation
- [ ] `make check-all`
- [ ] `make test-smoke` (if assistant/runtime behavior changed)
- [ ] `make test-uat` (required for assistant feature changes)
- [ ] Additional targeted checks documented below

## Checklist
- [ ] Changes are small, safe, and incremental
- [ ] No breaking changes to structure or website
- [ ] Docs follow repo markdown standards
- [ ] Links added/updated were verified
- [ ] Track and risk are declared
- [ ] Handoff notes included (files changed, validations, follow-ups)
- [ ] New feature surfaces include UAT updates in this PR

## UAT Change Justification
- Required when changing UAT governance files (`assistant/feature-catalog.json`, `assistant/uat-scenarios.json`, `tools/uat-runner.py`, `tools/check-uat-policy.py`)
- Explain why the change is needed, risk, and how confidence is maintained.

## Notes
-
