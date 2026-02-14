# QA Evaluation Report

Updated: 2026-02-14

## 1. Evaluation Scope

- Feature/lane: `#113` Integrate unmet-intent signals into hypothesis candidate
  generation
- Acceptance criteria source: issue `#113` + planning-round contract (`#110`)
- Evaluator: `@TonyThePredictor / Codex` (`gaia-qa-evaluator` sub-role)

## 2. Test Matrix

| Scenario | Expected | Actual | Status |
| --- | --- | --- | --- |
| Threshold promotion path | high-confidence/recent/high-count triaged signal is promoted | fixture `sig-promote` => `promote` | Pass |
| Low-confidence suppression | low-confidence signal remains hold | fixture `sig-hold-confidence` => `hold` | Pass |
| Recency-window suppression | stale signal outside effective retention window remains hold | fixture `sig-hold-recency` => `hold` | Pass |
| Non-promotable triage class | `out-of-scope-or-rejected` stays non-promotable | fixture `sig-reject-class` => `reject` | Pass |
| Derived-only redaction guard | forbidden raw-text keys reject promotion | fixture `sig-redaction-block` => `reject` | Pass |
| Opt-out enforcement | no promoted candidates when `signals.enabled=false` | fixture rerun returns `promoted_count=0`, `opt_out_respected=true` | Pass |
| Hypothesis integration | promoted candidate stubs validate under pipeline contract | generated stub(s) pass `hypothesis-pipeline.py validate` | Pass |

## 3. Regression Check

- Baseline reference: `origin/main` at `c573dfa` (post-`#112`)
- Regressions found: none
- Severity: none

## 4. Commands and Evidence

- `python3 -m py_compile tools/hypothesis-pipeline.py`: pass
- `bash ./tools/hypothesis-signal-candidate-check.sh`: pass
- `make hypothesis-dry-run`: pass
- `make hypothesis-hold-fixture`: pass
- `make hypothesis-failure-fixture` (expected non-zero): pass
- `make check-all`: pass

## 5. Decision

- Release readiness: yes
- Blocking defects: none
- Follow-up actions:
  - connect promoted candidates to controlled proposal review queue UX
  - expand deterministic fixture corpus for class-mix edge cases and retention
    boundary transitions
