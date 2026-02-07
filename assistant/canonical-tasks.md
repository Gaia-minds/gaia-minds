# Canonical Tasks (Phase 1)

Updated: February 8, 2026

This checklist defines 20 canonical user tasks for Phase 1 hardening.

## Task Matrix

| ID | Category | Task | Command |
| --- | --- | --- | --- |
| T01 | Config | Set profile name | `gaia config set name HardeningUser` |
| T02 | Config | Read profile name | `gaia config get name` |
| T03 | Config | Set verbosity | `gaia config set verbosity concise` |
| T04 | Config | Set default provider | `gaia config set provider openai` |
| T05 | Policy | Inspect capability levels | `gaia capability list` |
| T06 | Policy | Override capability to confirm | `gaia capability set send_email confirm` |
| T07 | Chat | Start chat session | `gaia chat` |
| T08 | Chat | Resume last session | `gaia chat --resume last` |
| T09 | Policy | Deny confirm action | chat: `delete all files in ~/docs` then `n` |
| T10 | Policy | Restore forbidden capability | `gaia capability set send_email forbidden` |
| T11 | Policy | Block forbidden action | chat: `send email to team` |
| T12 | Notes/Tasks | Capture task | `gaia note --task "Review the Phase 1 roadmap"` |
| T13 | Notes/Tasks | Capture note | `gaia note "Plain note for hardening"` |
| T14 | Notes/Tasks | List tasks | `gaia tasks --status all` |
| T15 | Notes/Tasks | Filter tasks by keyword | `gaia tasks --status all --q roadmap` |
| T16 | Summaries | Summarize URL | `gaia summarize file:///path/to/page.html` |
| T17 | Summaries | List summaries | `gaia summaries --last 5` |
| T18 | Planning | Create plan | `gaia plan "Set up a personal knowledge base"` |
| T19 | Planning | Refine existing plan | `gaia plan --edit <id> --update "...“` |
| T20 | Planning | List plans | `gaia plans --last 5` |

## Scoring Rule

- Success target: at least `16/20` tasks passing (`>=80%`).
- Hardening run uses `make hardening-phase1`.
