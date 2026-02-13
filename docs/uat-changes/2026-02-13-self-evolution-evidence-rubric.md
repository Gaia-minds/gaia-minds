# Self-Evolution Evidence Rubric Governance Update (2026-02-13)

## Why this change

Issue `#85` adds a new PR governance surface for framework self-evolution work:

- self-evolution applicability declaration in `.github/pull_request_template.md`
- mandatory evidence fields (`baseline`, `delta`, `thresholds/guardrails`,
  `rollback/fallback`, `risk notes`)
- deterministic CI enforcement via
  `tools/check-self-evolution-evidence.py` and
  `.github/workflows/self-evolution-evidence.yml`

Because this modifies protected UAT governance assets (the PR template), a
change record is required to keep policy checks deterministic and auditable.

## Risk

- Medium.
- Incorrect parser assumptions could create false-positive CI failures and block
  legitimate framework PRs.

## Confidence and Safeguards

- Applicability is explicit and mutually exclusive (`Applies` vs `Not
  applicable`).
- Evidence fields are only enforced when applicability is `Applies`.
- Checker rejects placeholder-only content and missing required fields.
- Local dry-run support (`--pr-body-file`) allows parser verification before
  push.

## Validation

- `make check-all`
- `python3 -m py_compile tools/check-self-evolution-evidence.py`
- `python3 tools/check-self-evolution-evidence.py --pr-body-file <pass-fixture> --require-context`
- `python3 tools/check-self-evolution-evidence.py --pr-body-file <fail-fixture> --require-context` (expected non-zero)
