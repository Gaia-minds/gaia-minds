# Assistant vs Framework Contributor Playbook

## Purpose

Use this playbook to decide where changes belong, validate them consistently,
and hand off work safely during parallel multi-worktree execution.

This document is the canonical `assistant vs framework` decision guide.

## Track Decision Tree

1. Does the change primarily affect end-user assistant behavior or UX?
   - Yes: `assistant-track`
   - No: continue
2. Does the change primarily affect governance, policies, workflows,
   release process, CI, or contributor coordination?
   - Yes: `framework-track`
   - No: continue
3. Does the change modify both runtime behavior and framework/process surfaces?
   - Yes: mark as cross-track (`assistant-track` + `framework-track`)
   - No: choose the dominant track and explain why in PR notes

When uncertain, default to the narrower scope and open a follow-up issue for the
other track.

## Validation Matrix

| Change Type | Track Declaration | Required Validation | Required Notes |
| --- | --- | --- | --- |
| Assistant feature/runtime behavior | `assistant-track` | `make test-smoke`; relevant `gaia ...` command checks for changed surfaces | Include before/after behavior and capability policy impact |
| Framework policy/process/docs | `framework-track` | `make check-all`; run file-specific checks when applicable (for example `python3 tools/verify-resources.py` for resources) | Include governance/process rationale and migration notes |
| CI/tooling/release workflow | `framework-track` | `make check-all`; dry-run or targeted command proving workflow/tool behavior | Include rollback/fallback path if automation fails |
| Cross-track change | `assistant-track` + `framework-track` | All relevant checks above in one PR, or split into two PRs | Explicitly call out coupling and merge order |

Every PR should include explicit `track declaration` and risk level.

## Risk Levels

- Low: docs-only or non-breaking internal changes with local validation.
- Medium: behavior or tooling changes with bounded blast radius.
- High: auth, permissions, release, safety/policy, or cross-track migrations.

High-risk changes should not merge without explicit maintainer review.

## Multi-Worktree / Multi-Agent Handoff Protocol

1. Claim issue and post implementation plan before coding.
2. Create isolated worktree per issue (`/tmp/...`) and branch from latest
   `origin/main`.
3. Keep PR scope single-purpose; avoid mixing unrelated tracks.
4. Before push, run required validation from matrix and capture outputs.
5. Post handoff comment with:
   - changed files
   - validation commands + results
   - known risks and follow-ups
6. Rebase worktree branch on latest main before merge if parallel PRs merged.
7. After merge, close/refresh issue state with links to PR and remaining work.

## PR Author Checklist

- Declare track: assistant/framework/cross-track.
- Declare risk: low/medium/high.
- List validations run.
- Document follow-up items for the next contributor.
