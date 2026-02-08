#!/usr/bin/env python3
"""Enforce Gaia UAT coverage and change-governance policy.

Policy highlights:
- Every command path in tools/gaia-assistant.py must be mapped in assistant/feature-catalog.json.
- Every action type in tools/agent-actions.py must be mapped in assistant/feature-catalog.json.
- New command/action features vs base ref require UAT updates in the same PR.
- Changes to protected UAT assets require:
  1) PR body section '## UAT Change Justification'
  2) a change record under docs/uat-changes/
  3) approval from configured reviewer (when running in PR CI context)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "assistant" / "feature-catalog.json"
DEFAULT_MANIFEST = REPO_ROOT / "assistant" / "uat-scenarios.json"
DEFAULT_ASSISTANT_FILE = REPO_ROOT / "tools" / "gaia-assistant.py"
DEFAULT_ACTIONS_FILE = REPO_ROOT / "tools" / "agent-actions.py"
DEFAULT_PROTECTED_PATHS = [
    "assistant/feature-catalog.json",
    "assistant/uat-scenarios.json",
    "tools/uat-runner.py",
    "tools/check-uat-policy.py",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
]


def _run_git(args: Sequence[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _extract_command_paths(text: str) -> Set[str]:
    add_parser_re = re.compile(r'^\s*(\w+)\s*=\s*(\w+)\.add_parser\("([^"]+)"')
    add_sub_re = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\.add_subparsers\(")

    sub_parent: Dict[str, str] = {}
    var_path: Dict[str, List[str]] = {}
    paths: Set[str] = set()

    for line in text.splitlines():
        sub_match = add_sub_re.match(line)
        if sub_match:
            sub_parent[sub_match.group(1)] = sub_match.group(2)

        parser_match = add_parser_re.match(line)
        if not parser_match:
            continue

        var_name, parent_name, segment = parser_match.groups()
        base_path: List[str] = []
        if parent_name == "sub":
            base_path = []
        elif parent_name in sub_parent:
            base_var = sub_parent[parent_name]
            base_path = list(var_path.get(base_var, []))
        elif parent_name in var_path:
            base_path = list(var_path[parent_name])

        full_path = base_path + [segment]
        var_path[var_name] = full_path
        paths.add(" ".join(full_path))

    return paths


def _extract_action_types(text: str) -> Set[str]:
    marker = "SUPPORTED_ACTIONS"
    idx = text.find(marker)
    scope = text[idx:] if idx != -1 else text
    return set(re.findall(r'"([a-zA-Z0-9_]+)"\s*:\s*_handle_', scope))


def _extract_from_ref(ref: str, rel_path: str) -> str:
    return _run_git(["show", f"{ref}:{rel_path}"])


def _merge_base(ref: str) -> str:
    return _run_git(["merge-base", "HEAD", ref]).strip()


def _changed_files(base_sha: str) -> Set[str]:
    out = _run_git(["diff", "--name-only", f"{base_sha}...HEAD"])
    return {line.strip() for line in out.splitlines() if line.strip()}


def _is_path_changed(changed: Set[str], path: str) -> bool:
    if path.endswith("/"):
        return any(item.startswith(path) for item in changed)
    return path in changed


def _extract_pr_context() -> Tuple[Optional[str], Optional[int], str, str]:
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    author = ""
    if not event_path:
        return None, None, repo, author

    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except Exception:
        return None, None, repo, author

    if not isinstance(payload, dict):
        return None, None, repo, author

    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return None, None, repo, author

    body = str(pr.get("body", "") or "")
    number = pr.get("number")
    pr_number = int(number) if isinstance(number, int) else None
    user = pr.get("user", {})
    if isinstance(user, dict):
        author = str(user.get("login", "") or "").strip()
    if not repo:
        head_repo = pr.get("head", {})
        if isinstance(head_repo, dict):
            repo_info = head_repo.get("repo", {})
            if isinstance(repo_info, dict):
                repo = str(repo_info.get("full_name", "") or "")
    return body, pr_number, repo, author


def _extract_justification(body: str) -> str:
    pattern = re.compile(r"##\s+UAT Change Justification\s*(.+?)(?:\n##\s+|\Z)", re.IGNORECASE | re.DOTALL)
    match = pattern.search(body)
    if not match:
        return ""
    return match.group(1).strip()


def _fetch_reviews(repo: str, pr_number: int, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews?per_page=100"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _reviewer_is_approved(reviews: List[Dict[str, Any]], reviewer: str) -> bool:
    latest_state: Dict[str, str] = {}
    for review in reviews:
        user = review.get("user", {})
        if not isinstance(user, dict):
            continue
        login = str(user.get("login", "")).strip().lower()
        state = str(review.get("state", "")).strip().upper()
        if not login:
            continue
        latest_state[login] = state
    return latest_state.get(reviewer.strip().lower(), "") == "APPROVED"


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce Gaia UAT policy")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="Feature catalog JSON path")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="UAT scenarios JSON path")
    parser.add_argument("--assistant-file", default=str(DEFAULT_ASSISTANT_FILE), help="Assistant CLI source file")
    parser.add_argument("--actions-file", default=str(DEFAULT_ACTIONS_FILE), help="Agent actions source file")
    parser.add_argument("--base-ref", default="origin/main", help="Base ref for new-feature diff checks")
    parser.add_argument("--reviewer", default="TonyThePredictor", help="Required reviewer for protected UAT changes")
    parser.add_argument(
        "--protected-path",
        action="append",
        default=[],
        help="Additional protected UAT path (repeatable)",
    )
    args = parser.parse_args()

    errors: List[str] = []
    notes: List[str] = []

    catalog_path = Path(args.catalog).expanduser()
    manifest_path = Path(args.manifest).expanduser()
    assistant_path = Path(args.assistant_file).expanduser()
    actions_path = Path(args.actions_file).expanduser()

    try:
        catalog = _load_json(catalog_path)
        manifest = _load_json(manifest_path)
    except Exception as exc:
        print(f"error: {exc}")
        return 1

    scenarios_raw = manifest.get("scenarios", [])
    scenario_ids: Set[str] = set()
    if not isinstance(scenarios_raw, list):
        errors.append("assistant/uat-scenarios.json must contain a 'scenarios' array")
    else:
        for item in scenarios_raw:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id", "")).strip()
            if sid:
                scenario_ids.add(sid)

    commands_raw = catalog.get("commands", [])
    actions_raw = catalog.get("agent_actions", [])
    command_map: Dict[str, List[str]] = {}
    action_map: Dict[str, List[str]] = {}

    if not isinstance(commands_raw, list):
        errors.append("assistant/feature-catalog.json must contain a 'commands' array")
        commands_raw = []
    if not isinstance(actions_raw, list):
        errors.append("assistant/feature-catalog.json must contain an 'agent_actions' array")
        actions_raw = []

    for item in commands_raw:
        if not isinstance(item, dict):
            errors.append("command entries must be objects")
            continue
        path = str(item.get("path", "")).strip()
        scenarios = item.get("scenarios", [])
        if not path:
            errors.append("command entry with empty path")
            continue
        if not isinstance(scenarios, list) or not scenarios:
            errors.append(f"command '{path}' must list at least one scenario")
            continue
        scenario_list = [str(x).strip() for x in scenarios if str(x).strip()]
        if not scenario_list:
            errors.append(f"command '{path}' has only empty scenario ids")
            continue
        command_map[path] = scenario_list
        for sid in scenario_list:
            if sid not in scenario_ids:
                errors.append(f"command '{path}' references unknown scenario '{sid}'")

    for item in actions_raw:
        if not isinstance(item, dict):
            errors.append("agent action entries must be objects")
            continue
        action_type = str(item.get("type", "")).strip()
        scenarios = item.get("scenarios", [])
        if not action_type:
            errors.append("agent action entry with empty type")
            continue
        if not isinstance(scenarios, list) or not scenarios:
            errors.append(f"agent action '{action_type}' must list at least one scenario")
            continue
        scenario_list = [str(x).strip() for x in scenarios if str(x).strip()]
        if not scenario_list:
            errors.append(f"agent action '{action_type}' has only empty scenario ids")
            continue
        action_map[action_type] = scenario_list
        for sid in scenario_list:
            if sid not in scenario_ids:
                errors.append(f"agent action '{action_type}' references unknown scenario '{sid}'")

    try:
        assistant_text = assistant_path.read_text(encoding="utf-8")
        actions_text = actions_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: unable to read source files: {exc}")
        return 1

    head_commands = _extract_command_paths(assistant_text)
    head_actions = _extract_action_types(actions_text)

    missing_commands = sorted(head_commands - set(command_map.keys()))
    missing_actions = sorted(head_actions - set(action_map.keys()))
    if missing_commands:
        errors.append("missing command coverage entries: " + ", ".join(missing_commands))
    if missing_actions:
        errors.append("missing agent action coverage entries: " + ", ".join(missing_actions))

    try:
        base_sha = _merge_base(args.base_ref)
        changed_files = _changed_files(base_sha)
        base_assistant = _extract_from_ref(base_sha, str(assistant_path.relative_to(REPO_ROOT)))
        base_actions = _extract_from_ref(base_sha, str(actions_path.relative_to(REPO_ROOT)))
        base_commands = _extract_command_paths(base_assistant)
        base_action_types = _extract_action_types(base_actions)
        new_commands = sorted(head_commands - base_commands)
        new_action_types = sorted(head_actions - base_action_types)
    except Exception as exc:
        errors.append(f"base comparison failed for {args.base_ref}: {exc}")
        changed_files = set()
        new_commands = []
        new_action_types = []

    if new_commands:
        notes.append("new command paths: " + ", ".join(new_commands))
    if new_action_types:
        notes.append("new agent action types: " + ", ".join(new_action_types))

    catalog_changed = _is_path_changed(changed_files, str(catalog_path.relative_to(REPO_ROOT)))
    manifest_changed = _is_path_changed(changed_files, str(manifest_path.relative_to(REPO_ROOT)))

    if (new_commands or new_action_types) and not (catalog_changed and manifest_changed):
        errors.append(
            "new features detected but UAT mapping was not updated in both "
            "assistant/feature-catalog.json and assistant/uat-scenarios.json"
        )

    protected_paths = list(DEFAULT_PROTECTED_PATHS)
    protected_paths.extend([item for item in args.protected_path if item])

    protected_changed = [path for path in protected_paths if _is_path_changed(changed_files, path)]
    if protected_changed or any(item.startswith("assistant/uat-") for item in changed_files):
        if not any(item.startswith("docs/uat-changes/") for item in changed_files):
            errors.append(
                "protected UAT files changed without a change record under docs/uat-changes/"
            )

        pr_body, pr_number, repo, pr_author = _extract_pr_context()
        if pr_body is None:
            notes.append("PR context unavailable locally; skipping justification/reviewer checks")
        else:
            justification = _extract_justification(pr_body)
            if len(re.sub(r"\s+", " ", justification).strip()) < 80:
                errors.append(
                    "PR body must include a substantial '## UAT Change Justification' section "
                    "(at least 80 non-whitespace characters)"
                )

            reviewer_login = args.reviewer.strip().lower()
            if pr_author.strip().lower() == reviewer_login and reviewer_login:
                notes.append(
                    f"PR author @{pr_author} matches required UAT reviewer @{args.reviewer}; "
                    "owner-authored protected UAT changes allowed without separate review"
                )
            else:
                token = os.environ.get("GITHUB_TOKEN", "").strip()
                if not token:
                    errors.append("GITHUB_TOKEN is required to validate protected UAT reviewer approval")
                elif not repo or pr_number is None:
                    errors.append("Unable to resolve PR repository/number for reviewer validation")
                else:
                    try:
                        reviews = _fetch_reviews(repo, pr_number, token)
                        if not _reviewer_is_approved(reviews, args.reviewer):
                            errors.append(
                                f"protected UAT changes require approval from @{args.reviewer}"
                            )
                    except urllib.error.HTTPError as exc:
                        errors.append(f"failed to fetch PR reviews: HTTP {exc.code}")
                    except Exception as exc:
                        errors.append(f"failed to fetch PR reviews: {exc}")

    print("UAT policy summary")
    print("==================")
    print(f"command_paths={len(head_commands)} mapped_commands={len(command_map)}")
    print(f"agent_actions={len(head_actions)} mapped_actions={len(action_map)}")
    if notes:
        for note in notes:
            print(f"note: {note}")

    if errors:
        print("\nUAT policy violations:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("\nUAT policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
