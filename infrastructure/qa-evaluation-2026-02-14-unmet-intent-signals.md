# QA Evaluation - Unmet-Intent Signals (2026-02-14)

## 1. Evaluation Scope

- Feature/lane:
  - Phase 3 privacy-preserving unmet-intent signal extraction (`#111`)
- Acceptance criteria source:
  - GitHub issue `#111` scope, privacy requirements, and validation checklist
- Evaluator:
  - Codex (`gaia-qa-evaluator` sub-role)

## 2. Test Matrix

| Scenario | Expected | Actual | Status |
| --- | --- | --- | --- |
| `signals_extraction_privacy_controls` UAT scenario | Derived-only ledger, opt-out no-write, retention/cap enforcement, export/clear paths pass | `python3 tools/uat-runner.py --run signals_extraction_privacy_controls` passed | Pass |
| Smoke regression suite | No assistant/runtime regression across deterministic smoke set | `make test-smoke` passed (`24/24`) | Pass |
| Full UAT suite | No command-surface regressions across deterministic UAT scenarios | `make test-uat` passed (`40/40`) | Pass |
| Repo checks | Docs/index/compatibility checks pass | `make check-all` passed | Pass |
| Python syntax | Updated Python files compile cleanly | `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/check-uat-policy.py` passed | Pass |
| UAT governance policy | Command-to-scenario mapping valid after parser modularization | `make uat-policy` pass recorded after committing branch changes | Pass |

## 3. Regression Check

- Baseline reference:
  - `origin/main` after `v0.3.0` release merge (`6484ebb` lineage)
- Regressions found:
  - None in smoke/UAT/check-all coverage
- Severity:
  - N/A (no blocking regressions)

## 4. Commands and Evidence

- `make test-smoke`:
  - Pass (`suite=gaia-smoke`, `total=24`, `failed=0`)
- `make check-all`:
  - Pass (docs/index/compatibility checks green)
- UAT/benchmark artifacts:
  - `make test-uat` pass (`suite=gaia-uat`, `total=40`, `failed=0`)
  - targeted UAT run pass:
    - `python3 tools/uat-runner.py --manifest ./assistant/uat-scenarios.json --run signals_extraction_privacy_controls --json-out /tmp/uat-signals-results.json`
  - UAT artifacts:
    - `assistant/uat-artifacts/20260214T170419Z/`

## 5. Decision

- Release readiness:
  - Yes (for this lane)
- Blocking defects:
  - None
- Follow-up actions:
  - `#112`: classify signal outputs into skill-first triage outcomes
  - `#113`: consume bounded signal aggregates in hypothesis candidate generation
