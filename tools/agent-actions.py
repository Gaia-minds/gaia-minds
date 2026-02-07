#!/usr/bin/env python3
"""Action executor for the Gaia Minds self-evolving agent.

This module provides two core capabilities:

1. **State gathering** -- collects information about the repository and GitHub
   (open issues, PRs, stale resources, etc.) so the reasoning layer can decide
   what to do next.

2. **Action execution** -- given an action dict (with ``type`` and ``params``),
   dispatches to the appropriate handler that carries out the work (running
   tools, creating branches/PRs, opening issues, etc.).

This module **never** makes alignment or priority decisions.  It executes
exactly what it is told and reports the result.

No external dependencies beyond the Python standard library.  External tools
(``git``, ``gh``, ``python3``) are invoked via :func:`subprocess.run`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = SCRIPT_DIR.parent

_SUBPROCESS_TIMEOUT = 60  # seconds


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ActionResult:
    """Outcome of a single action execution."""

    success: bool
    action_type: str
    output: str = ""
    error: str = ""
    artifacts: Dict[str, str] = field(default_factory=dict)


@dataclass
class RepoState:
    """Snapshot of the repository and GitHub state."""

    open_issues: List[dict] = field(default_factory=list)
    open_prs: List[dict] = field(default_factory=list)
    recent_commits: List[str] = field(default_factory=list)
    stale_resources: List[dict] = field(default_factory=list)
    stale_indexes: bool = False
    pending_reviews: List[dict] = field(default_factory=list)
    agent_pr_history: List[dict] = field(default_factory=list)
    branch_list: List[str] = field(default_factory=list)
    current_branch: str = ""
    research_topics: List[str] = field(default_factory=list)
    resource_files: List[str] = field(default_factory=list)
    tool_files: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_command(name: str) -> bool:
    """Return True if *name* is available on ``$PATH``."""
    return shutil.which(name) is not None


def _run(
    cmd: List[str],
    *,
    cwd: Optional[str] = None,
    timeout: int = _SUBPROCESS_TIMEOUT,
) -> subprocess.CompletedProcess:
    """Run a subprocess and return the completed process.

    All output is captured as text.  The caller is responsible for checking
    ``returncode``.
    """
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


def _slugify(text: str) -> str:
    """Convert *text* to a lowercase hyphen-separated slug."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _repo_flag(config: dict) -> List[str]:
    """Return ``['--repo', '<owner>/<name>']`` if the config provides it."""
    repo = config.get("github", {}).get("repo", "")
    if repo:
        return ["--repo", repo]
    return []


def _branch_prefix(config: dict) -> str:
    """Return the branch prefix from config (default ``agent/``)."""
    return config.get("github", {}).get("branch_prefix", "agent/")


def _base_branch(config: dict) -> str:
    """Return the base branch from config (default ``main``)."""
    return config.get("github", {}).get("base_branch", "main")


def _agent_name(config: dict) -> str:
    """Return the agent's name from config (default ``gaia-agent``)."""
    return config.get("agent", {}).get("name", "gaia-agent")


def _agent_label(config: dict) -> str:
    """Return the label applied to agent PRs."""
    return config.get("github", {}).get("labels", {}).get(
        "agent_pr", "agent-contribution"
    )


def _checkout_base(config: dict, repo_root: str) -> Optional[str]:
    """Switch to the base branch and pull latest.

    Returns an error message on failure or ``None`` on success.
    """
    base = _base_branch(config)
    result = _run(["git", "checkout", base], cwd=repo_root)
    if result.returncode != 0:
        return f"git checkout {base} failed: {result.stderr.strip()}"

    result = _run(["git", "pull", "origin", base], cwd=repo_root)
    if result.returncode != 0:
        # Non-fatal: we may be offline or the remote may be unavailable.
        pass

    return None


def _create_branch_and_pr(
    *,
    branch_name: str,
    commit_message: str,
    pr_title: str,
    pr_body: str,
    files_to_add: List[str],
    config: dict,
    repo_root: str,
) -> ActionResult:
    """Helper that creates a branch, commits files, pushes, and opens a PR.

    Returns an :class:`ActionResult` with the PR URL on success.
    """
    action_type = "branch_and_pr"

    if not _has_command("git"):
        return ActionResult(
            success=False,
            action_type=action_type,
            error="git is not installed",
        )

    # -- Checkout base and pull --
    err = _checkout_base(config, repo_root)
    if err:
        return ActionResult(success=False, action_type=action_type, error=err)

    # -- Create branch --
    result = _run(["git", "checkout", "-b", branch_name], cwd=repo_root)
    if result.returncode != 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"git checkout -b {branch_name} failed: {result.stderr.strip()}",
        )

    # -- Stage files --
    for fpath in files_to_add:
        result = _run(["git", "add", fpath], cwd=repo_root)
        if result.returncode != 0:
            return ActionResult(
                success=False,
                action_type=action_type,
                error=f"git add {fpath} failed: {result.stderr.strip()}",
            )

    # -- Commit --
    result = _run(
        ["git", "commit", "-m", commit_message],
        cwd=repo_root,
    )
    if result.returncode != 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"git commit failed: {result.stderr.strip()}",
        )

    # -- Push --
    result = _run(
        ["git", "push", "-u", "origin", branch_name],
        cwd=repo_root,
    )
    if result.returncode != 0:
        # Switch back to base before returning error.
        _run(["git", "checkout", _base_branch(config)], cwd=repo_root)
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"git push failed: {result.stderr.strip()}",
        )

    # -- Create PR --
    pr_url = ""
    if _has_command("gh"):
        pr_cmd = [
            "gh", "pr", "create",
            "--title", pr_title,
            "--body", pr_body,
            "--base", _base_branch(config),
        ]
        pr_cmd += _repo_flag(config)

        label = _agent_label(config)
        if label:
            pr_cmd += ["--label", label]

        result = _run(pr_cmd, cwd=repo_root)
        if result.returncode == 0:
            pr_url = result.stdout.strip()
        else:
            # PR creation failed but the branch and commit exist.
            _run(["git", "checkout", _base_branch(config)], cwd=repo_root)
            return ActionResult(
                success=False,
                action_type=action_type,
                output=f"Branch {branch_name} pushed but PR creation failed.",
                error=result.stderr.strip(),
                artifacts={"branch": branch_name},
            )
    else:
        # gh not available -- report the branch for manual PR creation.
        _run(["git", "checkout", _base_branch(config)], cwd=repo_root)
        return ActionResult(
            success=True,
            action_type=action_type,
            output=f"Branch {branch_name} pushed. gh not installed; create PR manually.",
            artifacts={"branch": branch_name},
        )

    # -- Switch back to base --
    _run(["git", "checkout", _base_branch(config)], cwd=repo_root)

    return ActionResult(
        success=True,
        action_type=action_type,
        output=f"PR created: {pr_url}",
        artifacts={"pr_url": pr_url, "branch": branch_name},
    )


# ---------------------------------------------------------------------------
# State gathering
# ---------------------------------------------------------------------------

def gather_state(config: dict, repo_root: str) -> RepoState:
    """Gather current state of the repository and GitHub.

    Populates as many fields as possible.  If ``gh`` is not installed, the
    GitHub-specific fields (issues, PRs, etc.) are left as empty lists.
    Git-local data is always gathered when ``git`` is available.
    """
    state = RepoState()
    root = Path(repo_root)
    has_git = _has_command("git")
    has_gh = _has_command("gh")
    repo_flag = _repo_flag(config)
    agent_name = _agent_name(config)

    # -- Git-local data -------------------------------------------------

    if has_git:
        # Current branch
        result = _run(["git", "branch", "--show-current"], cwd=repo_root)
        if result.returncode == 0:
            state.current_branch = result.stdout.strip()

        # Branch list
        result = _run(["git", "branch", "--list", "--format=%(refname:short)"], cwd=repo_root)
        if result.returncode == 0:
            state.branch_list = [
                b.strip() for b in result.stdout.splitlines() if b.strip()
            ]

        # Recent commits (last 20)
        result = _run(
            ["git", "log", "--oneline", "-20", "--format=%s"],
            cwd=repo_root,
        )
        if result.returncode == 0:
            state.recent_commits = [
                line.strip() for line in result.stdout.splitlines() if line.strip()
            ]

    # -- Filesystem data ------------------------------------------------

    # Research topics (folder names + file stems under research/)
    research_dir = root / "research"
    if research_dir.is_dir():
        for item in sorted(research_dir.rglob("*.md")):
            if item.name == "INDEX.md" or item.name == "README.md":
                continue
            # Use relative path from research/ as the topic identifier.
            rel = item.relative_to(research_dir)
            state.research_topics.append(str(rel))

    # Resource files
    resources_dir = root / "resources"
    if resources_dir.is_dir():
        for item in sorted(resources_dir.rglob("*.md")):
            if item.name == "INDEX.md" or item.name == "RESOURCES.md":
                continue
            rel = item.relative_to(resources_dir)
            state.resource_files.append(str(rel))

    # Tool files
    tools_dir = root / "tools"
    if tools_dir.is_dir():
        for item in sorted(tools_dir.iterdir()):
            if item.is_file() and item.name not in ("__pycache__",):
                state.tool_files.append(item.name)

    # -- Index staleness ------------------------------------------------

    generate_indexes = root / "tools" / "generate-indexes.py"
    if generate_indexes.exists():
        result = _run(
            ["python3", str(generate_indexes), "--check"],
            cwd=repo_root,
        )
        state.stale_indexes = result.returncode != 0

    # -- GitHub data (requires gh) --------------------------------------

    if has_gh:
        # Open issues
        try:
            result = _run(
                ["gh", "issue", "list", "--state=open", "--json",
                 "number,title,labels,assignees,createdAt"]
                + repo_flag,
                cwd=repo_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                state.open_issues = json.loads(result.stdout)
        except (json.JSONDecodeError, subprocess.TimeoutExpired):
            pass

        # Open PRs
        try:
            result = _run(
                ["gh", "pr", "list", "--state=open", "--json",
                 "number,title,author,labels,createdAt,headRefName"]
                + repo_flag,
                cwd=repo_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                state.open_prs = json.loads(result.stdout)
        except (json.JSONDecodeError, subprocess.TimeoutExpired):
            pass

        # Pending reviews (agent's open PRs that need review)
        try:
            result = _run(
                ["gh", "pr", "list", "--state=open", "--author=@me",
                 "--json", "number,title,reviewDecision,createdAt,headRefName"]
                + repo_flag,
                cwd=repo_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                state.pending_reviews = [
                    pr for pr in prs
                    if pr.get("reviewDecision", "") != "APPROVED"
                ]
        except (json.JSONDecodeError, subprocess.TimeoutExpired):
            pass

        # Agent PR history (merged + closed)
        try:
            result = _run(
                ["gh", "pr", "list", "--state=closed", "--author=@me",
                 "--json", "number,title,state,mergedAt,closedAt,headRefName",
                 "--limit", "50"]
                + repo_flag,
                cwd=repo_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                state.agent_pr_history = json.loads(result.stdout)
        except (json.JSONDecodeError, subprocess.TimeoutExpired):
            pass

    return state


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _handle_verify_resources(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Run ``verify-resources.py --json`` and return broken/redirect URLs."""
    action_type = "verify_resources"
    script = os.path.join(repo_root, "tools", "verify-resources.py")

    if not os.path.exists(script):
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Script not found: {script}",
        )

    try:
        result = _run(
            ["python3", script, "--json"],
            cwd=repo_root,
            timeout=120,  # URL checks can be slow
        )
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="verify-resources.py timed out after 120s",
        )

    output = result.stdout.strip()
    stale: List[dict] = []

    # Try to parse JSON output.
    if output:
        try:
            data = json.loads(output)
            if isinstance(data, list):
                stale = [
                    entry for entry in data
                    if entry.get("status") in ("broken", "redirect", "error")
                ]
            elif isinstance(data, dict) and "results" in data:
                stale = [
                    entry for entry in data["results"]
                    if entry.get("status") in ("broken", "redirect", "error")
                ]
        except json.JSONDecodeError:
            pass

    return ActionResult(
        success=result.returncode == 0,
        action_type=action_type,
        output=output,
        error=result.stderr.strip() if result.returncode != 0 else "",
        artifacts={"stale_count": str(len(stale))},
    )


def _handle_generate_indexes(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Run ``generate-indexes.py`` and report which files were updated."""
    action_type = "generate_indexes"
    script = os.path.join(repo_root, "tools", "generate-indexes.py")

    if not os.path.exists(script):
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Script not found: {script}",
        )

    try:
        result = _run(["python3", script], cwd=repo_root)
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="generate-indexes.py timed out",
        )

    # Detect updated files from the script output (lines like "Updated: <path>"
    # or "Wrote: <path>").
    updated: List[str] = []
    for line in result.stdout.splitlines():
        lower = line.lower()
        if "updated" in lower or "wrote" in lower or "generated" in lower:
            updated.append(line.strip())

    return ActionResult(
        success=result.returncode == 0,
        action_type=action_type,
        output=result.stdout.strip(),
        error=result.stderr.strip() if result.returncode != 0 else "",
        artifacts={"updated_files": json.dumps(updated)},
    )


def _handle_add_research(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Scaffold a research file, write content, and open a PR."""
    action_type = "add_research"

    topic = params.get("topic", "")
    subcategory = params.get("subcategory", "")
    content = params.get("content", "")

    if not topic or not subcategory:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="Missing required params: topic and subcategory",
        )

    # -- Run scaffold.sh with --no-branch (we manage branches ourselves) --
    scaffold = os.path.join(repo_root, "tools", "scaffold.sh")
    agent_name = _agent_name(config)

    try:
        result = _run(
            [
                "bash", scaffold,
                "research", topic,
                "-s", subcategory,
                "-a", agent_name,
                "--no-branch",
            ],
            cwd=repo_root,
        )
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False, action_type=action_type,
            error="scaffold.sh timed out",
        )

    if result.returncode != 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"scaffold.sh failed: {result.stderr.strip()}",
            output=result.stdout.strip(),
        )

    # -- Parse the created file path from scaffold output --
    # scaffold.sh prints: "Created file: <path>"
    created_file = ""
    for line in result.stdout.splitlines():
        if line.strip().startswith("Created file:"):
            created_file = line.split("Created file:", 1)[1].strip()
            break

    # Fallback: look for the "File:" line in the summary block.
    if not created_file:
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("File:"):
                created_file = stripped.split("File:", 1)[1].strip()
                break

    if not created_file or not os.path.exists(created_file):
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Could not determine created file from scaffold output: {result.stdout}",
        )

    # -- Write content into the file (replacing template) --
    if content:
        try:
            with open(created_file, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as exc:
            return ActionResult(
                success=False,
                action_type=action_type,
                error=f"Failed to write content to {created_file}: {exc}",
            )

    # -- Create branch, commit, push, and open PR --
    slug = _slugify(topic)
    branch_name = f"{_branch_prefix(config)}research-{slug}"
    relative_path = os.path.relpath(created_file, repo_root)

    pr_result = _create_branch_and_pr(
        branch_name=branch_name,
        commit_message=f"research: add {topic}",
        pr_title=f"research: add {topic}",
        pr_body=textwrap.dedent(f"""\
            ## Summary

            - Add research on **{topic}** under ``{subcategory}``
            - File: ``{relative_path}``

            ## Context

            Automated contribution by {agent_name}.
        """),
        files_to_add=[relative_path],
        config=config,
        repo_root=repo_root,
    )

    # Merge artifacts and adapt the action type.
    pr_result.action_type = action_type
    pr_result.artifacts["file_created"] = relative_path
    return pr_result


def _handle_add_resource(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Scaffold a resource file, write content, and open a PR."""
    action_type = "add_resource"

    topic = params.get("topic", "")
    subcategory = params.get("subcategory", "")
    content = params.get("content", "")

    if not topic or not subcategory:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="Missing required params: topic and subcategory",
        )

    scaffold = os.path.join(repo_root, "tools", "scaffold.sh")
    agent_name = _agent_name(config)

    try:
        result = _run(
            [
                "bash", scaffold,
                "resource", topic,
                "-s", subcategory,
                "-a", agent_name,
                "--no-branch",
            ],
            cwd=repo_root,
        )
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False, action_type=action_type,
            error="scaffold.sh timed out",
        )

    if result.returncode != 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"scaffold.sh failed: {result.stderr.strip()}",
            output=result.stdout.strip(),
        )

    # Parse the created file path.
    created_file = ""
    for line in result.stdout.splitlines():
        if line.strip().startswith("Created file:"):
            created_file = line.split("Created file:", 1)[1].strip()
            break
    if not created_file:
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("File:"):
                created_file = stripped.split("File:", 1)[1].strip()
                break

    if not created_file or not os.path.exists(created_file):
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Could not determine created file from scaffold output: {result.stdout}",
        )

    # Write content.
    if content:
        try:
            with open(created_file, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as exc:
            return ActionResult(
                success=False,
                action_type=action_type,
                error=f"Failed to write content to {created_file}: {exc}",
            )

    slug = _slugify(topic)
    branch_name = f"{_branch_prefix(config)}resource-{slug}"
    relative_path = os.path.relpath(created_file, repo_root)

    pr_result = _create_branch_and_pr(
        branch_name=branch_name,
        commit_message=f"resources: add {topic}",
        pr_title=f"resources: add {topic}",
        pr_body=textwrap.dedent(f"""\
            ## Summary

            - Add resource for **{topic}** under ``{subcategory}``
            - File: ``{relative_path}``

            ## Context

            Automated contribution by {agent_name}.
        """),
        files_to_add=[relative_path],
        config=config,
        repo_root=repo_root,
    )

    pr_result.action_type = action_type
    pr_result.artifacts["file_created"] = relative_path
    return pr_result


def _handle_create_tool(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Create a new tool file in ``tools/`` and open a PR."""
    action_type = "create_tool"

    name = params.get("name", "")
    content = params.get("content", "")
    description = params.get("description", "")

    if not name or not content:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="Missing required params: name and content",
        )

    tool_path = os.path.join(repo_root, "tools", name)

    if os.path.exists(tool_path):
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Tool already exists: {tool_path}",
        )

    # Write the tool file.
    try:
        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Failed to write tool file: {exc}",
        )

    # Make executable if .sh or .py
    if name.endswith(".sh") or name.endswith(".py"):
        try:
            os.chmod(tool_path, 0o755)
        except OSError:
            pass  # Non-fatal; git will track the permission anyway.

    slug = _slugify(name.rsplit(".", 1)[0] if "." in name else name)
    branch_name = f"{_branch_prefix(config)}tool-{slug}"
    relative_path = os.path.relpath(tool_path, repo_root)
    agent_name = _agent_name(config)

    pr_result = _create_branch_and_pr(
        branch_name=branch_name,
        commit_message=f"tools: add {name}",
        pr_title=f"tools: add {name}",
        pr_body=textwrap.dedent(f"""\
            ## Summary

            - Add new tool: ``{name}``
            - Description: {description or 'No description provided.'}

            ## Context

            Automated contribution by {agent_name}.
        """),
        files_to_add=[relative_path],
        config=config,
        repo_root=repo_root,
    )

    pr_result.action_type = action_type
    pr_result.artifacts["file_created"] = relative_path
    return pr_result


def _handle_update_skill(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Apply edits to a skill's SKILL.md and open a PR."""
    action_type = "update_skill"

    skill_name = params.get("skill_name", "")
    changes = params.get("changes", {})  # Dict[old_string, new_string]

    if not skill_name or not changes:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="Missing required params: skill_name and changes",
        )

    skill_path = os.path.join(repo_root, "skills", skill_name, "SKILL.md")

    if not os.path.exists(skill_path):
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Skill file not found: {skill_path}",
        )

    # Read current content.
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Failed to read {skill_path}: {exc}",
        )

    # Apply string replacements.
    applied = 0
    for old_str, new_str in changes.items():
        if old_str in content:
            content = content.replace(old_str, new_str)
            applied += 1

    if applied == 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="None of the provided changes matched content in SKILL.md",
        )

    # Write updated content.
    try:
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Failed to write {skill_path}: {exc}",
        )

    slug = _slugify(skill_name)
    branch_name = f"{_branch_prefix(config)}skill-{slug}"
    relative_path = os.path.relpath(skill_path, repo_root)
    agent_name = _agent_name(config)

    pr_result = _create_branch_and_pr(
        branch_name=branch_name,
        commit_message=f"skills: update {skill_name}",
        pr_title=f"skills: update {skill_name}",
        pr_body=textwrap.dedent(f"""\
            ## Summary

            - Update skill **{skill_name}** SKILL.md
            - Applied {applied} edit(s)

            ## Context

            Automated contribution by {agent_name}.
        """),
        files_to_add=[relative_path],
        config=config,
        repo_root=repo_root,
    )

    pr_result.action_type = action_type
    pr_result.artifacts["edits_applied"] = str(applied)
    return pr_result


def _handle_open_issue(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Open a GitHub issue via ``gh issue create``."""
    action_type = "open_issue"

    title = params.get("title", "")
    body = params.get("body", "")
    labels = params.get("labels", [])

    if not title:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="Missing required param: title",
        )

    if not _has_command("gh"):
        return ActionResult(
            success=False,
            action_type=action_type,
            error="gh (GitHub CLI) is not installed",
        )

    cmd = ["gh", "issue", "create", "--title", title]

    if body:
        cmd += ["--body", body]
    else:
        cmd += ["--body", ""]

    for label in labels:
        cmd += ["--label", label]

    cmd += _repo_flag(config)

    try:
        result = _run(cmd, cwd=repo_root)
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="gh issue create timed out",
        )

    if result.returncode != 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=result.stderr.strip(),
            output=result.stdout.strip(),
        )

    issue_url = result.stdout.strip()
    return ActionResult(
        success=True,
        action_type=action_type,
        output=f"Issue created: {issue_url}",
        artifacts={"issue_url": issue_url},
    )


def _handle_comment_on_pr(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Post a comment on a PR via ``gh pr comment``."""
    action_type = "comment_on_pr"

    pr_number = params.get("pr_number")
    body = params.get("body", "")

    if pr_number is None or not body:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="Missing required params: pr_number and body",
        )

    if not _has_command("gh"):
        return ActionResult(
            success=False,
            action_type=action_type,
            error="gh (GitHub CLI) is not installed",
        )

    cmd = [
        "gh", "pr", "comment", str(pr_number),
        "--body", body,
    ]
    cmd += _repo_flag(config)

    try:
        result = _run(cmd, cwd=repo_root)
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="gh pr comment timed out",
        )

    if result.returncode != 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=result.stderr.strip(),
            output=result.stdout.strip(),
        )

    return ActionResult(
        success=True,
        action_type=action_type,
        output=f"Commented on PR #{pr_number}",
    )


def _handle_check_pr_status(
    params: dict, config: dict, repo_root: str,
) -> ActionResult:
    """Retrieve the current status of a PR via ``gh pr view``."""
    action_type = "check_pr_status"

    pr_number = params.get("pr_number")
    if pr_number is None:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="Missing required param: pr_number",
        )

    if not _has_command("gh"):
        return ActionResult(
            success=False,
            action_type=action_type,
            error="gh (GitHub CLI) is not installed",
        )

    cmd = [
        "gh", "pr", "view", str(pr_number),
        "--json", "state,reviewDecision,mergeable,title,number,"
                  "headRefName,statusCheckRollup,reviews",
    ]
    cmd += _repo_flag(config)

    try:
        result = _run(cmd, cwd=repo_root)
    except subprocess.TimeoutExpired:
        return ActionResult(
            success=False,
            action_type=action_type,
            error="gh pr view timed out",
        )

    if result.returncode != 0:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=result.stderr.strip(),
            output=result.stdout.strip(),
        )

    # Parse and return the structured data.
    pr_data: dict = {}
    try:
        pr_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass

    return ActionResult(
        success=True,
        action_type=action_type,
        output=result.stdout.strip(),
        artifacts={
            "state": pr_data.get("state", ""),
            "review_decision": pr_data.get("reviewDecision", ""),
            "mergeable": pr_data.get("mergeable", ""),
        },
    )


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------

# Mapping from action type to handler function.  Each handler has the
# signature: (params: dict, config: dict, repo_root: str) -> ActionResult
SUPPORTED_ACTIONS: Dict[str, Callable[..., ActionResult]] = {
    "verify_resources": _handle_verify_resources,
    "generate_indexes": _handle_generate_indexes,
    "add_research": _handle_add_research,
    "add_resource": _handle_add_resource,
    "create_tool": _handle_create_tool,
    "update_skill": _handle_update_skill,
    "open_issue": _handle_open_issue,
    "comment_on_pr": _handle_comment_on_pr,
    "check_pr_status": _handle_check_pr_status,
}


def execute_action(action: dict, config: dict, repo_root: str) -> ActionResult:
    """Execute a single action.  Dispatches to specific action handlers.

    Parameters
    ----------
    action:
        A dict with ``"type"`` (str) and ``"params"`` (dict) keys.
    config:
        The agent configuration (parsed from ``agent-config.yml``).
    repo_root:
        Absolute path to the repository root.

    Returns
    -------
    ActionResult
        Always returns a result; never raises.
    """
    action_type = action.get("type", "")
    params = action.get("params", {})

    if not action_type:
        return ActionResult(
            success=False,
            action_type="unknown",
            error="Action dict missing 'type' key",
        )

    handler = SUPPORTED_ACTIONS.get(action_type)

    if handler is None:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Unsupported action type: {action_type}. "
                  f"Supported: {', '.join(sorted(SUPPORTED_ACTIONS))}",
        )

    try:
        return handler(params, config, repo_root)
    except subprocess.TimeoutExpired as exc:
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Action timed out: {exc}",
        )
    except Exception as exc:  # noqa: BLE001  -- intentional broad catch
        return ActionResult(
            success=False,
            action_type=action_type,
            error=f"Unexpected error: {type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# CLI entry point (for testing / manual use)
# ---------------------------------------------------------------------------

def _main() -> None:
    """Minimal CLI for testing individual actions or gathering state."""
    import argparse
    import yaml  # type: ignore[import-untyped]  # only needed for CLI

    parser = argparse.ArgumentParser(
        description="Gaia Minds agent action executor",
    )
    subparsers = parser.add_subparsers(dest="command")

    # -- gather-state subcommand --
    subparsers.add_parser("gather-state", help="Gather and print repo state")

    # -- execute subcommand --
    exec_parser = subparsers.add_parser("execute", help="Execute an action")
    exec_parser.add_argument("action_json", help="Action as JSON string")

    args = parser.parse_args()

    # Load config.
    config_path = os.path.join(
        str(DEFAULT_REPO_ROOT), "tools", "agent-config.yml",
    )
    config: dict = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

    repo_root = str(DEFAULT_REPO_ROOT)

    if args.command == "gather-state":
        state = gather_state(config, repo_root)
        print(json.dumps(state.__dict__, indent=2, default=str))

    elif args.command == "execute":
        try:
            action = json.loads(args.action_json)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON: {exc}", file=__import__("sys").stderr)
            raise SystemExit(1)
        result = execute_action(action, config, repo_root)
        print(json.dumps(result.__dict__, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    _main()
