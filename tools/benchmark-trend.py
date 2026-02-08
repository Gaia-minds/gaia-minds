#!/usr/bin/env python3
"""Append Gaia benchmark trend history and render a summary report.

This tool is intended for nightly CI runs and local diagnostics.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = REPO_ROOT / "assistant" / "benchmark-results.json"
DEFAULT_HISTORY = REPO_ROOT / "assistant" / "benchmark-trend-history.json"
DEFAULT_SUMMARY = REPO_ROOT / "assistant" / "benchmark-trend-summary.md"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(raw: str) -> datetime:
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _read_results(path: Path) -> Dict[str, Any]:
    payload = _load_json(path)
    required_keys = {"suite", "total", "passed", "failed", "score_pct"}
    if not required_keys.issubset(payload.keys()):
        missing = ", ".join(sorted(required_keys - set(payload.keys())))
        raise ValueError(f"Benchmark results missing keys: {missing}")
    return payload


def _normalized_runner_status(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"success", "pass", "passed"}:
        return "pass"
    if value in {"failure", "fail", "failed", "cancelled", "canceled", "timed_out"}:
        return "fail"
    return "unknown"


def _build_entry(results: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    ts = args.timestamp or _iso_now()
    run_id = args.run_id or os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = args.run_attempt or os.environ.get("GITHUB_RUN_ATTEMPT", "")
    sha = args.sha or os.environ.get("GITHUB_SHA", "")
    ref = args.ref or os.environ.get("GITHUB_REF_NAME", "")
    event_name = args.event or os.environ.get("GITHUB_EVENT_NAME", "")
    workflow = args.workflow or os.environ.get("GITHUB_WORKFLOW", "")
    actor = args.actor or os.environ.get("GITHUB_ACTOR", "")

    score_pct = float(results.get("score_pct", 0.0))
    target_score_pct = float(results.get("target_score_pct", 0.0))
    failed = int(results.get("failed", 0))

    runner_status = _normalized_runner_status(args.runner_status)
    benchmark_status = "pass" if failed == 0 and score_pct >= target_score_pct else "fail"
    status = benchmark_status if runner_status == "unknown" else runner_status

    return {
        "timestamp_utc": ts,
        "date_utc": ts[:10],
        "suite": str(results.get("suite", "")).strip(),
        "total": int(results.get("total", 0)),
        "passed": int(results.get("passed", 0)),
        "failed": failed,
        "score_pct": round(score_pct, 2),
        "target_score_pct": round(target_score_pct, 2),
        "status": status,
        "runner_status": runner_status,
        "benchmark_status": benchmark_status,
        "sha": sha,
        "ref": ref,
        "event_name": event_name,
        "workflow": workflow,
        "run_id": str(run_id).strip(),
        "run_attempt": str(run_attempt).strip(),
        "actor": actor,
    }


def _load_history(path: Path, suite: str) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if suite and str(item.get("suite", "")).strip() and str(item.get("suite", "")).strip() != suite:
            continue
        cleaned.append(item)
    return cleaned


def _entry_key(entry: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        str(entry.get("run_id", "")).strip(),
        str(entry.get("run_attempt", "")).strip(),
        str(entry.get("sha", "")).strip(),
        str(entry.get("timestamp_utc", "")).strip(),
    )


def _append_entry(entries: List[Dict[str, Any]], entry: Dict[str, Any], max_entries: int) -> Tuple[List[Dict[str, Any]], bool]:
    key = _entry_key(entry)
    for existing in entries:
        if _entry_key(existing) == key:
            return entries, False

    merged = [*entries, entry]
    merged.sort(key=lambda item: str(item.get("timestamp_utc", "")))
    if max_entries > 0 and len(merged) > max_entries:
        merged = merged[-max_entries:]
    return merged, True


def _score_stats(entries: List[Dict[str, Any]], days: int) -> Tuple[float, int]:
    if not entries:
        return 0.0, 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    scores: List[float] = []
    for item in entries:
        ts = str(item.get("timestamp_utc", "")).strip()
        if not ts:
            continue
        try:
            if _parse_ts(ts) < cutoff:
                continue
        except ValueError:
            continue
        scores.append(float(item.get("score_pct", 0.0)))

    if not scores:
        return 0.0, 0
    return round(sum(scores) / len(scores), 2), len(scores)


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
        "# Benchmark Trend Summary",
        "",
        f"Updated (UTC): {history_payload.get('updated_at', '')}",
        "",
    ]

    if not entries:
        lines.append("No trend entries recorded yet.")
        return "\n".join(lines) + "\n"

    latest = entries[-1]
    previous = entries[-2] if len(entries) > 1 else None

    lines.extend(
        [
            "## Latest Run",
            f"- status: `{latest.get('status', 'unknown')}`",
            f"- score: `{latest.get('score_pct', 0):.2f}%`",
            f"- passed: `{latest.get('passed', 0)}/{latest.get('total', 0)}`",
            f"- benchmark_status: `{latest.get('benchmark_status', 'unknown')}`",
            f"- run: `{latest.get('run_id', '')}` attempt `{latest.get('run_attempt', '')}`",
            f"- commit: `{str(latest.get('sha', ''))[:12]}`",
            f"- event: `{latest.get('event_name', '')}`",
            "",
        ]
    )

    if previous:
        delta_score = round(float(latest.get("score_pct", 0.0)) - float(previous.get("score_pct", 0.0)), 2)
        delta_passed = int(latest.get("passed", 0)) - int(previous.get("passed", 0))
        lines.extend(
            [
                "## Delta Vs Previous",
                f"- score_delta_pct: `{delta_score:+.2f}`",
                f"- passed_delta: `{delta_passed:+d}`",
                "",
            ]
        )

    avg_7d, count_7d = _score_stats(entries, days=7)
    pass_count = sum(1 for item in entries if str(item.get("status", "")).strip().lower() == "pass")
    pass_rate = round((pass_count / len(entries)) * 100.0, 2) if entries else 0.0
    streak = _current_pass_streak(entries)

    lines.extend(
        [
            "## Window Stats",
            f"- total_entries: `{len(entries)}`",
            f"- pass_rate_pct: `{pass_rate:.2f}`",
            f"- current_pass_streak: `{streak}`",
            f"- avg_score_last_7d: `{avg_7d:.2f}` (from `{count_7d}` run(s))",
            "",
            "## Recent Runs",
            "",
            "| timestamp_utc | status | score_pct | passed | sha | run_id |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )

    for item in reversed(entries[-14:]):
        lines.append(
            "| {ts} | {status} | {score:.2f} | {passed}/{total} | `{sha}` | `{run}` |".format(
                ts=str(item.get("timestamp_utc", "")),
                status=str(item.get("status", "unknown")),
                score=float(item.get("score_pct", 0.0)),
                passed=int(item.get("passed", 0)),
                total=int(item.get("total", 0)),
                sha=str(item.get("sha", ""))[:8],
                run=str(item.get("run_id", "")),
            )
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Gaia benchmark trend history and summary")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="Path to benchmark-results.json")
    parser.add_argument("--history", default=str(DEFAULT_HISTORY), help="Path to benchmark trend history JSON")
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY), help="Path to benchmark trend summary markdown")
    parser.add_argument("--max-entries", type=int, default=90, help="Maximum entries to keep in history")
    parser.add_argument("--timestamp", default="", help="Override timestamp in UTC ISO8601")
    parser.add_argument("--sha", default="", help="Commit SHA override")
    parser.add_argument("--ref", default="", help="Ref name override")
    parser.add_argument("--event", default="", help="Event name override")
    parser.add_argument("--workflow", default="", help="Workflow name override")
    parser.add_argument("--run-id", default="", help="Run ID override")
    parser.add_argument("--run-attempt", default="", help="Run attempt override")
    parser.add_argument("--actor", default="", help="Actor override")
    parser.add_argument(
        "--runner-status",
        default="unknown",
        help="Benchmark step status (success/failure/cancelled). Used for trend status.",
    )
    args = parser.parse_args()

    results_path = Path(args.results).expanduser()
    history_path = Path(args.history).expanduser()
    summary_path = Path(args.summary).expanduser()

    try:
        results = _read_results(results_path)
    except Exception as exc:
        print(f"error: could not read benchmark results: {exc}")
        return 1

    suite = str(results.get("suite", "")).strip()
    if not suite:
        print("error: benchmark results missing suite")
        return 1

    history_entries = _load_history(history_path, suite=suite)
    entry = _build_entry(results, args)
    entries, appended = _append_entry(history_entries, entry, max_entries=args.max_entries)

    payload = {
        "schema_version": 1,
        "suite": suite,
        "updated_at": _iso_now(),
        "entries": entries,
    }
    _write_json(history_path, payload)

    summary = _render_summary(payload)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")

    report = {
        "history_path": str(history_path),
        "summary_path": str(summary_path),
        "entries": len(entries),
        "appended": appended,
        "latest_status": entry.get("status", "unknown"),
        "latest_score_pct": entry.get("score_pct", 0.0),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
