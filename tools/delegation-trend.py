#!/usr/bin/env python3
"""Append Phase 4 delegation checkpoint trend history and render a summary.

Intended for nightly CI runs and local diagnostics.  Reads the JSON
output of reliability-checkpoint-phase4.py and appends an entry to
assistant/delegation-trend-history.json, then rewrites the trend
summary markdown.

Usage:
    python3 tools/delegation-trend.py \\
        --results /tmp/delegation-checkpoint.json \\
        --history assistant/delegation-trend-history.json \\
        --summary assistant/delegation-trend-summary.md \\
        --runner-status success
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORY = REPO_ROOT / "assistant" / "delegation-trend-history.json"
DEFAULT_SUMMARY = REPO_ROOT / "assistant" / "delegation-trend-summary.md"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(raw: str) -> datetime:
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _normalized_runner_status(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"success", "pass", "passed"}:
        return "pass"
    if value in {"failure", "fail", "failed", "cancelled", "canceled", "timed_out"}:
        return "fail"
    return "unknown"


def _build_entry(results: Dict[str, Any], runner_status_raw: str, args: argparse.Namespace) -> Dict[str, Any]:
    ts = args.timestamp or _iso_now()
    run_id = args.run_id or os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = args.run_attempt or os.environ.get("GITHUB_RUN_ATTEMPT", "")
    sha = args.sha or os.environ.get("GITHUB_SHA", "")
    ref = args.ref or os.environ.get("GITHUB_REF_NAME", "")
    event_name = args.event or os.environ.get("GITHUB_EVENT_NAME", "")
    workflow = args.workflow or os.environ.get("GITHUB_WORKFLOW", "")
    actor = args.actor or os.environ.get("GITHUB_ACTOR", "")

    runner_status = _normalized_runner_status(runner_status_raw)
    gate_status = str(results.get("gate_status", "fail")).strip().lower()
    checkpoint_status = "pass" if gate_status == "pass" else "fail"
    status = checkpoint_status if runner_status == "unknown" else runner_status

    metrics = results.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    return {
        "timestamp_utc": ts,
        "date_utc": ts[:10],
        "suite": "delegation-reliability-checkpoint-phase4",
        "gate_status": gate_status,
        "checkpoint_status": checkpoint_status,
        "status": status,
        "runner_status": runner_status,
        "qa_pass_rate": round(float(metrics.get("qa_pass_rate", 0.0)), 4),
        "dispatch_success_rate": round(float(metrics.get("dispatch_success_rate", 0.0)), 4),
        "trace_complete": bool(metrics.get("trace_complete", False)),
        "total_cases": int(metrics.get("total_cases", 0)),
        "passed_cases": int(metrics.get("passed_cases", 0)),
        "failed_cases": int(metrics.get("failed_cases", 0)),
        "positive_path_fallback_rate": round(float(metrics.get("positive_path_fallback_rate", 0.0)), 4),
        "sha": sha,
        "ref": ref,
        "event_name": event_name,
        "workflow": workflow,
        "run_id": str(run_id).strip(),
        "run_attempt": str(run_attempt).strip(),
        "actor": actor,
    }


def _entry_key(entry: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        str(entry.get("run_id", "")).strip(),
        str(entry.get("run_attempt", "")).strip(),
        str(entry.get("sha", "")).strip(),
        str(entry.get("timestamp_utc", "")).strip(),
    )


def _append_entry(
    entries: List[Dict[str, Any]], entry: Dict[str, Any], max_entries: int
) -> Tuple[List[Dict[str, Any]], bool]:
    key = _entry_key(entry)
    for existing in entries:
        if _entry_key(existing) == key:
            return entries, False
    merged = [*entries, entry]
    merged.sort(key=lambda item: str(item.get("timestamp_utc", "")))
    if max_entries > 0 and len(merged) > max_entries:
        merged = merged[-max_entries:]
    return merged, True


def _rate_stats(entries: List[Dict[str, Any]], field: str, days: int) -> Tuple[float, int]:
    if not entries:
        return 0.0, 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    values: List[float] = []
    for item in entries:
        ts = str(item.get("timestamp_utc", "")).strip()
        if not ts:
            continue
        try:
            if _parse_ts(ts) < cutoff:
                continue
        except ValueError:
            continue
        values.append(float(item.get(field, 0.0)))
    if not values:
        return 0.0, 0
    return round(sum(values) / len(values), 4), len(values)


def _current_pass_streak(entries: List[Dict[str, Any]]) -> int:
    streak = 0
    for item in reversed(entries):
        if str(item.get("status", "")).strip().lower() != "pass":
            break
        streak += 1
    return streak


def _render_summary(history_payload: Dict[str, Any]) -> str:
    entries = history_payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []

    lines: List[str] = [
        "# Delegation Benchmark Trend Summary",
        "",
        f"Updated (UTC): {history_payload.get('updated_at', '')}",
        "",
    ]

    if not entries:
        lines.append("No delegation trend entries recorded yet.")
        return "\n".join(lines) + "\n"

    latest = entries[-1]
    previous = entries[-2] if len(entries) > 1 else None

    lines.extend([
        "## Latest Run",
        f"- status: `{latest.get('status', 'unknown')}`",
        f"- gate_status: `{latest.get('gate_status', 'unknown')}`",
        f"- qa_pass_rate: `{float(latest.get('qa_pass_rate', 0.0)):.2%}`",
        f"- dispatch_success_rate: `{float(latest.get('dispatch_success_rate', 0.0)):.2%}`",
        f"- trace_complete: `{latest.get('trace_complete', False)}`",
        f"- passed_cases: `{latest.get('passed_cases', 0)}/{latest.get('total_cases', 0)}`",
        f"- run: `{latest.get('run_id', '')}` attempt `{latest.get('run_attempt', '')}`",
        f"- commit: `{str(latest.get('sha', ''))[:12]}`",
        f"- event: `{latest.get('event_name', '')}`",
        "",
    ])

    if previous:
        delta_qa = round(
            float(latest.get("qa_pass_rate", 0.0)) - float(previous.get("qa_pass_rate", 0.0)), 4
        )
        delta_dispatch = round(
            float(latest.get("dispatch_success_rate", 0.0)) - float(previous.get("dispatch_success_rate", 0.0)), 4
        )
        lines.extend([
            "## Delta Vs Previous",
            f"- qa_pass_rate_delta: `{delta_qa:+.4f}`",
            f"- dispatch_success_rate_delta: `{delta_dispatch:+.4f}`",
            "",
        ])

    avg_qa_7d, count_7d = _rate_stats(entries, "qa_pass_rate", days=7)
    avg_dispatch_7d, _ = _rate_stats(entries, "dispatch_success_rate", days=7)
    pass_count = sum(1 for item in entries if str(item.get("status", "")).strip().lower() == "pass")
    pass_rate = round((pass_count / len(entries)) * 100.0, 2) if entries else 0.0
    streak = _current_pass_streak(entries)

    lines.extend([
        "## Window Stats",
        f"- total_entries: `{len(entries)}`",
        f"- pass_rate_pct: `{pass_rate:.2f}`",
        f"- current_pass_streak: `{streak}`",
        f"- avg_qa_pass_rate_last_7d: `{avg_qa_7d:.4f}` (from `{count_7d}` run(s))",
        f"- avg_dispatch_success_rate_last_7d: `{avg_dispatch_7d:.4f}`",
        "",
        "## Recent Runs",
        "",
        "| timestamp_utc | status | qa_pass_rate | dispatch_success_rate | passed | sha | run_id |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ])

    for item in reversed(entries[-14:]):
        lines.append(
            "| {ts} | {status} | {qa:.2%} | {ds:.2%} | {passed}/{total} | `{sha}` | `{run}` |".format(
                ts=str(item.get("timestamp_utc", "")),
                status=str(item.get("status", "unknown")),
                qa=float(item.get("qa_pass_rate", 0.0)),
                ds=float(item.get("dispatch_success_rate", 0.0)),
                passed=int(item.get("passed_cases", 0)),
                total=int(item.get("total_cases", 0)),
                sha=str(item.get("sha", ""))[:8],
                run=str(item.get("run_id", "")),
            )
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Gaia delegation benchmark trend history and summary")
    parser.add_argument(
        "--results", required=True,
        help="Path to JSON output from reliability-checkpoint-phase4.py --json"
    )
    parser.add_argument(
        "--history", default=str(DEFAULT_HISTORY),
        help="Path to delegation-trend-history.json"
    )
    parser.add_argument(
        "--summary", default=str(DEFAULT_SUMMARY),
        help="Path to delegation-trend-summary.md"
    )
    parser.add_argument("--runner-status", default="", help="CI runner step outcome (success|failure)")
    parser.add_argument("--max-entries", type=int, default=90, help="Max history entries to retain")
    parser.add_argument("--timestamp", default="", help="Override timestamp (ISO format)")
    parser.add_argument("--run-id", default="", help="Override GITHUB_RUN_ID")
    parser.add_argument("--run-attempt", default="", help="Override GITHUB_RUN_ATTEMPT")
    parser.add_argument("--sha", default="", help="Override GITHUB_SHA")
    parser.add_argument("--ref", default="", help="Override GITHUB_REF_NAME")
    parser.add_argument("--event", default="", help="Override GITHUB_EVENT_NAME")
    parser.add_argument("--workflow", default="", help="Override GITHUB_WORKFLOW")
    parser.add_argument("--actor", default="", help="Override GITHUB_ACTOR")
    args = parser.parse_args()

    results_path = Path(args.results).expanduser().resolve()
    history_path = Path(args.history).expanduser().resolve()
    summary_path = Path(args.summary).expanduser().resolve()

    results = _load_json(results_path)
    if not results:
        print(f"error: could not load checkpoint results from {results_path}")
        return 1

    history = _load_json(history_path)
    entries: List[Dict[str, Any]] = history.get("entries", []) if isinstance(history, dict) else []
    if not isinstance(entries, list):
        entries = []

    entry = _build_entry(results, args.runner_status, args)
    entries, appended = _append_entry(entries, entry, args.max_entries)

    now = _iso_now()
    history_payload: Dict[str, Any] = {
        "schema_version": 1,
        "suite": "delegation-reliability-checkpoint-phase4",
        "updated_at": now,
        "entries": entries,
    }

    _write_json(history_path, history_payload)
    _write_text(summary_path, _render_summary(history_payload))

    if appended:
        print(f"delegation trend: appended entry gate_status={entry['gate_status']} status={entry['status']}")
    else:
        print("delegation trend: entry already present, no update needed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
