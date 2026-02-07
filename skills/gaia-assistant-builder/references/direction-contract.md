# User Direction Contract

Use this contract whenever a human asks Gaia agents to do assistant work.

## Input Source

Preferred source: GitHub issue created from
`.github/ISSUE_TEMPLATE/assistant-direction.yml`.

## Required Fields

1. Objective
2. User-facing outcome
3. In-scope work
4. Out-of-scope work
5. Success criteria
6. Safety constraints
7. Budget split preference for user service and self-improvement lanes

## Processing Rules

1. Do not start implementation until required fields are present.
2. If a field is missing, request clarification in the issue thread.
3. Copy success criteria into the implementation PR description.
4. If scope changes, update the issue and PR explicitly.

## Budget Guidance

Default if not specified:

- User service lane: `80%`
- Self-improvement lane: `20%`

If user specifies another split, use it as long as:

1. It does not violate safety constraints.
2. It preserves enough budget for user-facing obligations.
