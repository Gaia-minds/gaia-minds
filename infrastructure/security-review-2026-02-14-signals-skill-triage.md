# Security Review Report

Updated: 2026-02-14

## 1. Review Scope

- PR/issue/lane: `#112` Skill-first triage for unmet-intent signals
- Components reviewed:
  - `tools/gaia-assistant.py` (`signals triage` classification + skill
    matching + validation-aware gating)
  - `tools/gaia_assistant_parser.py` (CLI surface wiring)
  - `assistant/signal-triage-fixtures.json`
  - `tools/signal-triage-check.sh`
  - smoke/UAT governance updates
- Reviewer: `@TonyThePredictor / Codex` (`gaia-security-reviewer` sub-role)

## 2. Threat Surface

- Entry points:
  - `gaia signals triage`
  - `gaia skills validate` report ingestion used for triage decisions
- Privileged operations:
  - local reads of signal ledger + skill contracts + validation reports
  - local write of triage ledger artifact
- External dependencies:
  - none in triage decision path
  - no network fetch or dynamic skill installation added

## 3. Findings

| Severity | Finding | Evidence | Exploit Path | Mitigation |
| --- | --- | --- | --- | --- |
| Medium | Token/capability overlap heuristics can mis-rank ambiguous skills. | `_match_signal_skill_candidate` uses deterministic overlap scoring. | Ambiguous intent tags could route to a suboptimal candidate. | Enforced security gates, validation evidence checks, and blocked-class fallback paths; triage output includes explicit rationale for human review. |
| Low | Missing validation evidence defaults to required gate rather than deny. | `existing-skill-enable` path can emit `validate_then_enable:*`. | Operator could ignore required gate and enable unsafely outside flow. | `security_gate.status=required` + required checks are explicit in output; unsafe/failed validation paths are blocked by default. |
| Low | Dangerous marker list is bounded and pattern-based. | `SIGNALS_TRIAGE_DANGEROUS_MARKERS` static set. | Novel harmful intent phrasing may evade marker match. | Unsafe routing also enforced by capability-policy and validation gates; marker corpus is extendable with deterministic fixtures. |

## 4. Required Actions

- Blocking actions:
  - None for this lane; deterministic security gates are enforced for import and
    validation-sensitive paths.
- Non-blocking hardening:
  - Expand intent-marker and matching fixtures as new patterns appear.
  - Add periodic false-positive/false-negative review against real triage
    telemetry summaries (derived signals only).
- Owners:
  - Follow-on hypothesis integration and triage refinements (`#113` and later).

## 5. Verification

- Commands/tests executed:
  - `python3 -m py_compile tools/gaia-assistant.py tools/gaia_assistant_parser.py tools/check-uat-policy.py`
  - `tmp_home="$(mktemp -d)" && GAIA_ASSISTANT_HOME="$tmp_home" bash ./tools/signal-triage-check.sh`
  - `make uat-policy`
  - `make quality-matrix`
  - `make test-smoke`
  - `make test-uat`
  - `make check-all`
- Result summary:
  - Triage class routing is deterministic and fully covered by fixture matrix.
  - Import candidates are security-gated and unsafe/failed-validation paths are
    rejected.
  - No blocking unresolved security defects identified for merge.

## 6. Decision

- Review status: approve
- Rationale:
  - Lane adds secure default behavior to self-evolution signal routing with
    deterministic, test-backed gating and explicit rejection paths.
