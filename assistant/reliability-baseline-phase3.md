# Phase 3 Reliability Baseline

Updated: February 13, 2026

Baseline date (UTC): `2026-02-13`  
Baseline commit: `15b82d3057acdb85fdee8e76e59ed65301fc9510`

Source of truth: `assistant/reliability-baseline-phase3.json`

## SLO-Style Thresholds

| Metric | Threshold |
| --- | --- |
| Benchmark pass rate | `>= 1.00` |
| Benchmark failure rate | `<= 0.00` |
| UAT pass rate | `>= 1.00` |
| UAT failure rate | `<= 0.00` |
| Memory quality pass rate | `>= 1.00` |
| Memory quality p95 latency | `<= 500 ms` |
| Consolidated failure rate | `<= 0.00` |
| MTTR proxy (hours) | `<= 24` |

## Checkpoint Process

Generate checkpoint artifacts:

```bash
make reliability-checkpoint
```

Enforce thresholds (non-zero on breach):

```bash
make reliability-checkpoint-check
```

Simulate a breach for triage validation:

```bash
make reliability-checkpoint-simulate-breach
```

Default artifact location:

- `/tmp/gaia-reliability-checkpoints/latest/reliability-checkpoint.json`
- `/tmp/gaia-reliability-checkpoints/latest/reliability-checkpoint.md`

## Triage Routing

When any threshold breaches, route according to:

- `infrastructure/reliability-triage-workflow.md`

and create/update incident records under:

- `docs/incidents/`
