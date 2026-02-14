# Agent Memory

This directory is the persistent memory of the Gaia Minds autonomous agent.
All files are committed to git so that every decision and lesson is fully
transparent and auditable.

## Files

| File | Format | Purpose |
|---|---|---|
| `state.json` | JSON | Current agent state: cycle counter, cumulative statistics, and current focus. Updated at the end of every cycle. |
| `decisions.jsonl` | JSONL (one JSON object per line) | Append-only log of every action the agent considered or executed, including reasoning, alignment-check result, risk level, and outcome. Older entries are rotated once the limit in `agent-config.yml` is reached. |
| `budget-decisions.jsonl` | JSONL (one JSON object per line) | Structured token-budget gate decisions (allow/warn/defer/block), threshold/breach evidence, and projected/applied usage snapshots per cycle. |
| `lessons.jsonl` | JSONL (one JSON object per line) | Lessons the agent has extracted from merged PRs, rejected PRs, errors, and general observations. Used to improve future decision-making. Summarized periodically according to the configured interval. |

## Rotation policy

- `decisions.jsonl` keeps at most `memory.max_decisions_log_entries` entries
  (see `agent-config.yml`). When the limit is exceeded the oldest entries are
  archived or dropped.
- `budget-decisions.jsonl` keeps at most
  `memory.max_budget_decision_entries` entries.
- `lessons.jsonl` keeps at most `memory.max_lessons_entries` entries. Every
  `memory.summary_interval_cycles` cycles the agent distills older lessons into
  a summary before discarding the raw entries.
