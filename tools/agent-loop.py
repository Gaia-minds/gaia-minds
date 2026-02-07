#!/usr/bin/env python3
"""Gaia Minds Self-Evolving Agent -- Main Loop.

This is the reasoning core of an autonomous agent that:
1. Gathers state from the repository and GitHub
2. Asks Claude what to do (with Constitution as system constraint)
3. Checks alignment of proposed actions
4. Executes approved actions
5. Writes memory (decisions, lessons, state)
6. Evolves by learning from outcomes

All reasoning traces are logged to tools/agent-memory/ for transparency.

Run locally:
    python3 tools/agent-loop.py                    # single cycle
    python3 tools/agent-loop.py --mode continuous   # loop with interval
    python3 tools/agent-loop.py --dry-run           # plan but don't execute
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Resolve paths and add tools/ to sys.path for sibling imports
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

# Sibling modules -- imported after path setup
from agent_alignment import (  # noqa: E402
    AlignmentResult,
    check_alignment,
    classify_risk,
    load_constitution,
)
from agent_actions import (  # noqa: E402
    ActionResult,
    RepoState,
    execute_action,
    gather_state,
)

# ---------------------------------------------------------------------------
# Optional: Anthropic SDK
# ---------------------------------------------------------------------------

try:
    import anthropic

    _HAS_ANTHROPIC = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _HAS_ANTHROPIC = False

# Optional: PyYAML
try:
    import yaml

    _HAS_YAML = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    _HAS_YAML = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

log = logging.getLogger("gaia-agent")

# Defaults for dual-track evolution behavior.
DEFAULT_TRACKS: Dict[str, Dict[str, Any]] = {
    "assistant": {
        "weight": 7,
        "description": "Improve user-facing personal assistant behavior and reliability",
        "allowed_actions": [
            "verify_resources",
            "generate_indexes",
            "add_research",
            "add_resource",
            "update_skill",
            "open_issue",
            "comment_on_pr",
            "check_pr_status",
        ],
    },
    "framework": {
        "weight": 3,
        "description": "Improve Gaia self-evolving framework and governance tooling",
        "allowed_actions": [
            "verify_resources",
            "generate_indexes",
            "create_tool",
            "update_skill",
            "open_issue",
            "comment_on_pr",
            "check_pr_status",
        ],
    },
}

DEFAULT_BUDGET_POLICY: Dict[str, Any] = {
    "user_service_pct": 80,
    "self_improvement_pct": 20,
    "hard_cycle_token_cap": 12000,
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = SCRIPT_DIR / "agent-config.yml"
MEMORY_DIR = Path(
    os.environ.get("GAIA_AGENT_MEMORY_DIR", str(SCRIPT_DIR / "agent-memory"))
).expanduser()
DECISIONS_PATH = MEMORY_DIR / "decisions.jsonl"
LESSONS_PATH = MEMORY_DIR / "lessons.jsonl"
STATE_PATH = MEMORY_DIR / "state.json"


def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Load agent-config.yml."""
    text = path.read_text(encoding="utf-8")
    if _HAS_YAML:
        return yaml.safe_load(text)
    # Minimal fallback -- parse enough to run
    import re

    config: Dict[str, Any] = {}
    # Extract key top-level scalars
    for match in re.finditer(r"^  (\w+):\s*\"?([^\"#\n]+)\"?", text, re.MULTILINE):
        key, val = match.group(1).strip(), match.group(2).strip()
        config[key] = val
    return config


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


def load_memory(n_decisions: int = 10, n_lessons: int = 10) -> Dict[str, Any]:
    """Load recent decisions, lessons, and state from agent-memory/."""
    memory: Dict[str, Any] = {
        "recent_decisions": [],
        "lessons": [],
        "state": {},
    }

    # Decisions (last N lines)
    if DECISIONS_PATH.exists():
        lines = DECISIONS_PATH.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-n_decisions:]:
            line = line.strip()
            if line:
                try:
                    memory["recent_decisions"].append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # Lessons (last N lines)
    if LESSONS_PATH.exists():
        lines = LESSONS_PATH.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-n_lessons:]:
            line = line.strip()
            if line:
                try:
                    memory["lessons"].append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # State
    if STATE_PATH.exists():
        try:
            memory["state"] = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return memory


def log_decision(
    cycle: int,
    action: Dict[str, Any],
    alignment: AlignmentResult,
    outcome: str,
    details: str = "",
    active_track: str = "unknown",
) -> None:
    """Append a decision record to decisions.jsonl."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": cycle,
        "track": active_track,
        "action": action.get("type", "unknown"),
        "action_params": action.get("params", {}),
        "reasoning": alignment.reasoning[:500],
        "alignment_check": "allowed" if alignment.allowed else "denied",
        "risk_level": alignment.risk_level,
        "outcome": outcome,
        "details": details[:500],
    }
    with open(DECISIONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_lesson(cycle: int, lesson: str, source: str, context: str = "") -> None:
    """Append a lesson to lessons.jsonl."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle": cycle,
        "lesson": lesson,
        "source": source,
        "context": context[:300],
    }
    with open(LESSONS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def update_state(
    cycle: int,
    results: List[ActionResult],
    active_track: str = "unknown",
    budget_policy: Optional[Dict[str, Any]] = None,
) -> None:
    """Update state.json with cycle results."""
    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    state["last_cycle"] = cycle
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["last_track"] = active_track
    state["total_actions"] = state.get("total_actions", 0) + len(results)
    track_counts = state.get("track_counts", {})
    track_counts[active_track] = track_counts.get(active_track, 0) + 1
    state["track_counts"] = track_counts
    if budget_policy:
        state["budget_policy"] = budget_policy

    for r in results:
        if r.artifacts.get("pr_url"):
            state["total_prs_created"] = state.get("total_prs_created", 0) + 1

    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def commit_memory(cycle: int) -> None:
    """Commit memory changes to git."""
    import subprocess

    try:
        subprocess.run(
            ["git", "add", str(MEMORY_DIR)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=30,
        )
        # Check if there are staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet", str(MEMORY_DIR)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:  # there are changes
            subprocess.run(
                ["git", "commit", "-m", f"agent: memory update cycle {cycle}"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                timeout=30,
            )
            log.info("Memory committed to git (cycle %d)", cycle)
        else:
            log.debug("No memory changes to commit")
    except Exception as exc:
        log.warning("Could not commit memory: %s", exc)


def rotate_logs(config: Dict[str, Any]) -> None:
    """Rotate decision and lesson logs if they exceed configured limits."""
    max_decisions = config.get("memory", {}).get("max_decisions_log_entries", 500)
    max_lessons = config.get("memory", {}).get("max_lessons_entries", 100)

    for path, limit in [(DECISIONS_PATH, max_decisions), (LESSONS_PATH, max_lessons)]:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > limit:
            # Keep the most recent entries
            path.write_text("\n".join(lines[-limit:]) + "\n", encoding="utf-8")
            log.info("Rotated %s: kept last %d of %d entries", path.name, limit, len(lines))


def normalized_track_config(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return normalized track configuration with safe defaults."""
    tracks_cfg = config.get("evolution", {}).get("tracks", {})
    out: Dict[str, Dict[str, Any]] = {}
    for name, defaults in DEFAULT_TRACKS.items():
        configured = tracks_cfg.get(name, {})
        weight = configured.get("weight", defaults["weight"])
        try:
            weight_int = int(weight)
        except (TypeError, ValueError):
            weight_int = int(defaults["weight"])
        if weight_int < 1:
            weight_int = 1
        allowed_actions = configured.get("allowed_actions", defaults["allowed_actions"])
        if not isinstance(allowed_actions, list):
            allowed_actions = defaults["allowed_actions"]
        out[name] = {
            "weight": weight_int,
            "description": configured.get("description", defaults["description"]),
            "allowed_actions": allowed_actions,
        }
    return out


def normalized_budget_policy(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return normalized budget policy with safe defaults."""
    budget_cfg = config.get("budget", {})
    out = dict(DEFAULT_BUDGET_POLICY)
    out.update(budget_cfg if isinstance(budget_cfg, dict) else {})
    for key in ("user_service_pct", "self_improvement_pct", "hard_cycle_token_cap"):
        try:
            out[key] = int(out[key])
        except (TypeError, ValueError):
            out[key] = DEFAULT_BUDGET_POLICY[key]
    if out["user_service_pct"] < 0:
        out["user_service_pct"] = DEFAULT_BUDGET_POLICY["user_service_pct"]
    if out["self_improvement_pct"] < 0:
        out["self_improvement_pct"] = DEFAULT_BUDGET_POLICY["self_improvement_pct"]
    if out["hard_cycle_token_cap"] < 1:
        out["hard_cycle_token_cap"] = DEFAULT_BUDGET_POLICY["hard_cycle_token_cap"]
    return out


def select_active_track(
    config: Dict[str, Any],
    cycle_number: int,
) -> str:
    """Choose active track for this cycle.

    Override via GAIA_ACTIVE_TRACK_OVERRIDE=assistant|framework.
    """
    tracks = normalized_track_config(config)
    override = os.environ.get("GAIA_ACTIVE_TRACK_OVERRIDE", "").strip().lower()
    if override in tracks:
        return override

    scheduler = config.get("evolution", {}).get("scheduler", "weighted_round_robin")
    if scheduler == "round_robin":
        order = sorted(tracks.keys())
        return order[(cycle_number - 1) % len(order)]

    # weighted_round_robin
    weighted_order: List[str] = []
    for name in sorted(tracks.keys()):
        weighted_order.extend([name] * int(tracks[name]["weight"]))
    if not weighted_order:
        return "assistant"
    return weighted_order[(cycle_number - 1) % len(weighted_order)]


def action_allowed_in_track(action_type: str, active_track: str, config: Dict[str, Any]) -> bool:
    """Return whether action_type is allowed in the active track policy."""
    tracks = normalized_track_config(config)
    track_cfg = tracks.get(active_track)
    if not track_cfg:
        return False
    allowed_actions = track_cfg.get("allowed_actions", [])
    return action_type in allowed_actions


# ---------------------------------------------------------------------------
# Claude reasoning
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are the reasoning core of Gaia Agent, a self-evolving autonomous agent for \
the Gaia Minds project. Every action you propose must align with the Constitution below.

<constitution>
{constitution}
</constitution>

You have access to these action types:
- verify_resources: Check if resource URLs are still live
- generate_indexes: Regenerate INDEX.md files
- add_research: Create a new research file (params: topic, subcategory, content)
- add_resource: Document a new resource (params: name, subcategory, content)
- create_tool: Create a new tool script (params: name, content, description)
- update_skill: Modify a skill file (params: skill_name, changes)
- open_issue: Open a GitHub issue (params: title, body, labels)
- comment_on_pr: Comment on a PR (params: pr_number, body)
- check_pr_status: Check PR status (params: pr_number)

Risk levels:
- auto_execute: verify_resources, generate_indexes (done immediately)
- auto_pr: add_research, add_resource, create_tool, update_skill (creates PR)
- require_review: anything modifying the agent itself (creates issue for human)
- forbidden: delete_constitution, disable_hooks, merge_own_pr, modify_git_history, bypass_review

IMPORTANT RULES:
- Never propose forbidden actions.
- For research/resource content, write COMPLETE, substantive content — not placeholders.
- Prioritize: stale resources > open issues > stale indexes > research gaps > tool improvements.
- If nothing needs doing, return an empty actions list. Don't invent busywork.
- Learn from past mistakes shown in the memory context.
- Be specific in your reasoning — reference what you observed in the state.
- Respect the active evolution track and only propose actions allowed for that track.
"""

USER_PROMPT_TEMPLATE = """\
Current repository state:
{state_json}

Recent memory (last {n_decisions} decisions):
{decisions_json}

Lessons learned:
{lessons_json}

Agent state:
{agent_state_json}

Active evolution track for this cycle:
{active_track}

Track policy:
{track_policy_json}

Budget policy:
{budget_policy_json}

Based on the current state, what actions should I take this cycle?

Respond with valid JSON only (no markdown, no code fences):
{{
  "reasoning": "Step-by-step reasoning about what needs to be done and why",
  "actions": [
    {{"type": "action_type", "params": {{}}, "reasoning": "why this specific action"}}
  ]
}}

If nothing needs doing, return: {{"reasoning": "explanation", "actions": []}}
"""


def state_to_summary(state: RepoState) -> Dict[str, Any]:
    """Convert RepoState to a JSON-serializable summary for the prompt."""
    return {
        "open_issues_count": len(state.open_issues),
        "open_issues": state.open_issues[:10],
        "open_prs_count": len(state.open_prs),
        "open_prs": state.open_prs[:5],
        "recent_commits": state.recent_commits[:10],
        "stale_resources": state.stale_resources[:10],
        "stale_indexes": state.stale_indexes,
        "pending_reviews": state.pending_reviews[:5],
        "agent_pr_history": state.agent_pr_history[:10],
        "research_topics": state.research_topics,
        "resource_files_count": len(state.resource_files),
        "tool_files": state.tool_files,
    }


def ask_claude_for_plan(
    client: Any,
    config: Dict[str, Any],
    state: RepoState,
    memory: Dict[str, Any],
    constitution: str,
    active_track: str,
) -> Dict[str, Any]:
    """Ask Claude to analyze state and propose actions."""
    reasoning_config = config.get("reasoning", {})
    model = reasoning_config.get("model", "claude-sonnet-4-5-20250929")
    max_tokens = reasoning_config.get("max_tokens", 4096)
    temperature = reasoning_config.get("temperature", 0.3)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(constitution=constitution)

    n_decisions = 10
    n_lessons = 10
    track_policy = normalized_track_config(config).get(active_track, {})
    budget_policy = normalized_budget_policy(config)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        state_json=json.dumps(state_to_summary(state), indent=2),
        n_decisions=n_decisions,
        decisions_json=json.dumps(memory.get("recent_decisions", []), indent=2),
        lessons_json=json.dumps(memory.get("lessons", []), indent=2),
        agent_state_json=json.dumps(memory.get("state", {}), indent=2),
        active_track=active_track,
        track_policy_json=json.dumps(track_policy, indent=2),
        budget_policy_json=json.dumps(budget_policy, indent=2),
    )

    log.info("Asking Claude (%s) for a plan...", model)
    log.debug("System prompt: %d chars, User prompt: %d chars", len(system_prompt), len(user_prompt))

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract text from response
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    # Parse JSON from response
    # Handle case where Claude wraps in code fences
    text = text.strip()
    if text.startswith("```"):
        # Remove code fences
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        plan = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse Claude's response as JSON: %s", exc)
        log.error("Raw response: %s", text[:500])
        plan = {"reasoning": f"Failed to parse response: {exc}", "actions": []}

    actions = plan.get("actions", [])
    log.info(
        "Claude proposed %d action(s): %s",
        len(actions),
        ", ".join(a.get("type", "?") for a in actions) or "(none)",
    )
    log.info("Reasoning: %s", plan.get("reasoning", "")[:200])

    return plan


# ---------------------------------------------------------------------------
# Main cycle
# ---------------------------------------------------------------------------


def run_cycle(
    config: Dict[str, Any],
    client: Any,
    cycle_number: int,
    dry_run: bool = False,
) -> List[ActionResult]:
    """Run one complete agent cycle."""
    repo_root = str(REPO_ROOT)
    budget_policy = normalized_budget_policy(config)

    # 1. Gather state
    log.info("=== Cycle %d: Gathering state ===", cycle_number)
    state = gather_state(config, repo_root)

    # 2. Load memory
    memory = load_memory()
    active_track = select_active_track(config, cycle_number)
    log.info(
        "Active track: %s (budget split: service=%s%%, self_improvement=%s%%, hard_cycle_token_cap=%s)",
        active_track,
        budget_policy["user_service_pct"],
        budget_policy["self_improvement_pct"],
        budget_policy["hard_cycle_token_cap"],
    )

    # 3. Load constitution
    constitution = load_constitution(repo_root)

    # 4. Ask Claude for a plan
    if client is None:
        log.info("No Anthropic client available -- skipping Claude reasoning (dry-run)")
        plan = {"reasoning": f"No API client (dry-run without SDK/key), active_track={active_track}", "actions": []}
    else:
        plan = ask_claude_for_plan(client, config, state, memory, constitution, active_track)

    actions = plan.get("actions", [])
    if not actions:
        log.info("No actions proposed this cycle.")
        update_state(cycle_number, [], active_track, budget_policy)
        return []

    # 5. Process each action
    results: List[ActionResult] = []
    for i, action in enumerate(actions):
        action_type = action.get("type", "unknown")
        log.info("--- Action %d/%d: %s ---", i + 1, len(actions), action_type)

        if not action_allowed_in_track(action_type, active_track, config):
            reason = f"Action '{action_type}' blocked by track policy for '{active_track}'"
            log.warning(reason)
            track_policy_alignment = AlignmentResult(
                allowed=False,
                risk_level="high",
                reasoning=reason,
            )
            log_decision(
                cycle_number,
                action,
                track_policy_alignment,
                "blocked_by_track_policy",
                reason,
                active_track=active_track,
            )
            continue

        # 5a. Check alignment
        alignment = check_alignment(
            action,
            constitution,
            json.dumps(memory.get("recent_decisions", [])[-5:]),
            client=client if _HAS_ANTHROPIC else None,
            model=config.get("reasoning", {}).get("model", "claude-sonnet-4-5-20250929"),
        )

        log.info(
            "Alignment: %s (risk=%s) - %s",
            "ALLOWED" if alignment.allowed else "DENIED",
            alignment.risk_level,
            alignment.reasoning[:150],
        )

        # 5b. Route based on alignment + risk
        if not alignment.allowed:
            log.warning("Action BLOCKED by alignment checker")
            log_decision(cycle_number, action, alignment, "blocked", active_track=active_track)
            continue

        if alignment.risk_level == "forbidden":
            log.warning("Action FORBIDDEN")
            log_decision(cycle_number, action, alignment, "forbidden", active_track=active_track)
            continue

        if alignment.risk_level == "high":
            log.info("High-risk action -> creating issue for human review")
            if not dry_run:
                issue_action = {
                    "type": "open_issue",
                    "params": {
                        "title": f"[Agent] Review request: {action_type}",
                        "body": (
                            f"## Proposed Action\n\n"
                            f"**Type:** `{action_type}`\n\n"
                            f"**Params:**\n```json\n{json.dumps(action.get('params', {}), indent=2)}\n```\n\n"
                            f"**Agent reasoning:** {action.get('reasoning', 'N/A')}\n\n"
                            f"## Alignment Check\n\n"
                            f"**Risk level:** {alignment.risk_level}\n"
                            f"**Reasoning:** {alignment.reasoning}\n\n"
                            f"---\n"
                            f"*This issue was created by gaia-agent cycle {cycle_number}. "
                            f"Please review and provide guidance.*"
                        ),
                        "labels": ["human-input", "agent-contribution"],
                    },
                }
                result = execute_action(issue_action, config, repo_root)
                results.append(result)
            log_decision(
                cycle_number,
                action,
                alignment,
                "deferred_to_human",
                active_track=active_track,
            )
            continue

        # 5c. Execute (low or medium risk)
        if dry_run:
            log.info("[DRY RUN] Would execute: %s", action_type)
            log_decision(cycle_number, action, alignment, "dry_run", active_track=active_track)
            continue

        log.info("Executing action...")
        result = execute_action(action, config, repo_root)
        results.append(result)

        outcome = "success" if result.success else "failed"
        log.info("Result: %s - %s", outcome, result.output[:200] if result.output else result.error[:200])

        log_decision(
            cycle_number,
            action,
            alignment,
            outcome,
            result.output or result.error,
            active_track=active_track,
        )

        # Learn from failures
        if not result.success:
            log_lesson(
                cycle_number,
                f"Action '{action_type}' failed: {result.error[:200]}",
                "error",
                json.dumps(action.get("params", {})),
            )

    # 6. Update state
    update_state(cycle_number, results, active_track, budget_policy)

    # 7. Rotate logs if needed
    rotate_logs(config)

    # 8. Commit memory
    if not dry_run:
        commit_memory(cycle_number)

    return results


# ---------------------------------------------------------------------------
# Learn from PR feedback
# ---------------------------------------------------------------------------


def check_pr_feedback(config: Dict[str, Any], cycle_number: int) -> None:
    """Check if any of our past PRs got merged or rejected, and learn."""
    repo_root = str(REPO_ROOT)
    state = gather_state(config, repo_root)

    for pr in state.agent_pr_history:
        pr_state = pr.get("state", "").upper()
        pr_title = pr.get("title", "")
        pr_number = pr.get("number", "?")

        # Check if we already have a lesson about this PR
        memory = load_memory(n_decisions=0, n_lessons=100)
        already_logged = any(
            f"PR #{pr_number}" in lesson.get("context", "")
            for lesson in memory.get("lessons", [])
        )
        if already_logged:
            continue

        if pr_state == "MERGED":
            log_lesson(
                cycle_number,
                f"PR #{pr_number} '{pr_title}' was merged successfully",
                "pr_merged",
                f"PR #{pr_number}",
            )
            log.info("Learned: PR #%s was merged", pr_number)

        elif pr_state == "CLOSED":
            log_lesson(
                cycle_number,
                f"PR #{pr_number} '{pr_title}' was closed without merge -- review why",
                "pr_rejected",
                f"PR #{pr_number}",
            )
            log.info("Learned: PR #%s was rejected", pr_number)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gaia Minds Self-Evolving Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 tools/agent-loop.py                     # single cycle\n"
            "  python3 tools/agent-loop.py --mode continuous    # loop every hour\n"
            "  python3 tools/agent-loop.py --dry-run -v         # plan without executing\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_PATH),
        help="Path to agent-config.yml (default: tools/agent-config.yml)",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "continuous"],
        default=None,
        help="Override cycle mode from config",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gather state and plan, but don't execute actions",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, stream=sys.stderr)

    # Check for anthropic SDK (not needed in dry-run)
    if not _HAS_ANTHROPIC and not args.dry_run:
        log.error(
            "The 'anthropic' package is required. Install it:\n"
            "  pip install anthropic\n"
            "Or: pip install -r requirements.txt"
        )
        return 1

    # Check for API key (not needed in dry-run)
    if not os.environ.get("ANTHROPIC_API_KEY") and not args.dry_run:
        log.error(
            "ANTHROPIC_API_KEY environment variable is not set.\n"
            "  export ANTHROPIC_API_KEY='your-key-here'"
        )
        return 1

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    config = load_config(config_path)
    log.info("Loaded config: %s v%s", config.get("agent", {}).get("name", "?"), config.get("agent", {}).get("version", "?"))

    # Determine mode
    mode = args.mode or config.get("cycle", {}).get("mode", "single")

    # Initialize Anthropic client
    if _HAS_ANTHROPIC and os.environ.get("ANTHROPIC_API_KEY"):
        client = anthropic.Anthropic()
        log.info("Anthropic client initialized (model: %s)", config.get("reasoning", {}).get("model", "?"))
    else:
        client = None
        log.info("No Anthropic client (dry-run or missing SDK/key)")

    # Ensure memory directory exists
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for path in [DECISIONS_PATH, LESSONS_PATH]:
        if not path.exists():
            path.touch()
    if not STATE_PATH.exists():
        STATE_PATH.write_text("{}\n", encoding="utf-8")

    # Load current state to get cycle number
    try:
        state_data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        state_data = {}
    cycle_number = state_data.get("last_cycle", 0) + 1

    if mode == "single":
        log.info("Running single cycle (#%d)...", cycle_number)
        # Check PR feedback before planning
        check_pr_feedback(config, cycle_number)
        results = run_cycle(config, client, cycle_number, dry_run=args.dry_run)
        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        log.info("Cycle %d complete: %d succeeded, %d failed", cycle_number, succeeded, failed)
        return 1 if failed > 0 else 0

    elif mode == "continuous":
        interval = config.get("cycle", {}).get("interval_minutes", 60)
        max_cycles = config.get("cycle", {}).get("max_cycles", 0)
        log.info("Running continuously (interval=%dm, max_cycles=%s)...", interval, max_cycles or "unlimited")

        try:
            cycles_run = 0
            while True:
                check_pr_feedback(config, cycle_number)
                results = run_cycle(config, client, cycle_number, dry_run=args.dry_run)
                succeeded = sum(1 for r in results if r.success)
                failed = sum(1 for r in results if not r.success)
                log.info("Cycle %d complete: %d succeeded, %d failed", cycle_number, succeeded, failed)

                cycle_number += 1
                cycles_run += 1

                if max_cycles and cycles_run >= max_cycles:
                    log.info("Reached max_cycles (%d). Stopping.", max_cycles)
                    break

                log.info("Sleeping %d minutes until next cycle...", interval)
                time.sleep(interval * 60)

        except KeyboardInterrupt:
            log.info("\nInterrupted by user. Exiting gracefully.")
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
