# Dead-Code and Dead-Artifact Audit - 2026-02-14 (`#105`)

Updated: February 14, 2026
Owner: Codex (`contributor` main role)
Activated sub-roles: `gaia-researcher`, `gaia-technical-writer`

## 1. Scope

Audit scope for lane `#105`:

- runtime dead-code candidates in `tools/gaia-assistant.py` and adjacent tooling
- documentation/assets artifacts that appear stale against current runtime
- package/workflow entries that may be redundant or obsolete

Out of scope:

- broad runtime refactor (handled in `#106`)
- live-preview asset redesign (handled in `#107`)

## 2. Method

1. Static usage scan of top-level helper functions in `tools/gaia-assistant.py`.
2. Repo-wide reference checks for candidate symbols/files.
3. Manual review of packaging/workflow contracts for compatibility/necessity.
4. Classification into `keep`, `remove`, or `defer`.

## 3. Findings

| Candidate | Evidence | Decision | Action |
| --- | --- | --- | --- |
| `_collect_provider_profiles` in `tools/gaia-assistant.py` | Symbol appeared only at definition; no call sites found in repo Python sources. | `remove` | Removed in this lane. |
| `_pick_profile_id` in `tools/gaia-assistant.py` | Symbol appeared only at definition; no call sites found in repo Python sources. | `remove` | Removed in this lane. |
| `assistant/assets/gaia-assistant-terminal.svg`, `assistant/assets/gaia-assistant-demo-animated.svg` | Assets still include stale runtime cues (for example older config/version strings) and do not reflect latest capability surface. | `defer` | Keep for now; refresh in `#107`. |
| Canonical + shim module entries in `package.json` (`tools/agent-actions.py` + `tools/agent_actions.py`, `tools/agent-alignment.py` + `tools/agent_alignment.py`) | Shim modules explicitly exist for environments where symlinks are not preserved and re-export canonical implementations. | `keep` | No change. |
| Historical OpenClaw/Moltbook references in research/website docs | References are in historical research/context pages, not active runtime integration paths. | `keep` | No change. |

## 4. Cleanup Applied

- Removed two unreferenced auth-profile helper functions from
  `tools/gaia-assistant.py`:
  - `_collect_provider_profiles`
  - `_pick_profile_id`

No CLI/API contract changes were introduced by this cleanup.

## 5. Deferred Follow-Ups

- `#106`: perform deeper post-extraction dead-code pass while modularizing
  `tools/gaia-assistant.py`.
- `#107`: refresh README live-preview assets to align with current capabilities.

## 6. Validation

Planned validation for this lane:

- `make generate-indexes`
- `make check-all`
- `python3 -m py_compile tools/gaia-assistant.py`

If runtime regressions are detected in refactor follow-on lanes, revert/remove
decisions from this audit can be rolled back independently.
