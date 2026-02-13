#!/usr/bin/env python3
"""Deterministic benchmark runner for Gaia Phase 1 canonical tasks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
HARDENING_SCRIPT = REPO_ROOT / "tools" / "phase1-hardening.py"
QUALITY_MATRIX_SCRIPT = REPO_ROOT / "tools" / "quality-matrix.py"
DEFAULT_JSON_OUT = REPO_ROOT / "assistant" / "benchmark-results.json"
DEFAULT_BASELINE = REPO_ROOT / "assistant" / "benchmark-baseline.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_phase1_hardening() -> Tuple[int, Dict[str, Any], str, str]:
    json_out = REPO_ROOT / "assistant" / ".benchmark-phase1-hardening.json"
    md_out = REPO_ROOT / "assistant" / ".benchmark-phase1-hardening.md"

    env = os.environ.copy()
    env["TZ"] = "UTC"

    proc = subprocess.run(
        [
            sys.executable,
            str(HARDENING_SCRIPT),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    payload = _load_json(json_out)
    try:
        json_out.unlink(missing_ok=True)
        md_out.unlink(missing_ok=True)
    except OSError:
        pass

    return proc.returncode, payload, proc.stdout.strip(), proc.stderr.strip()


def _run_quality_matrix() -> Tuple[int, Dict[str, Any], str, str]:
    json_out = REPO_ROOT / "assistant" / ".benchmark-quality-matrix.json"

    env = os.environ.copy()
    env["TZ"] = "UTC"

    proc = subprocess.run(
        [
            sys.executable,
            str(QUALITY_MATRIX_SCRIPT),
            "--json-out",
            str(json_out),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )

    payload = _load_json(json_out)
    try:
        json_out.unlink(missing_ok=True)
    except OSError:
        pass

    return proc.returncode, payload, proc.stdout.strip(), proc.stderr.strip()


def _task_key(task_id: str) -> Tuple[int, str]:
    raw = str(task_id).strip()
    if raw.startswith("T") and raw[1:].isdigit():
        return int(raw[1:]), raw
    return 9999, raw


def _build_quality_matrix_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_checks = raw_payload.get("checks", [])
    checks: List[Dict[str, Any]] = []
    if isinstance(raw_checks, list):
        for item in raw_checks:
            if not isinstance(item, dict):
                continue
            check_id = str(item.get("id", "")).strip()
            if not check_id:
                continue
            checks.append(
                {
                    "id": check_id,
                    "category": str(item.get("category", "")).strip() or "quality",
                    "passed": str(item.get("status", "")).strip().lower() == "pass",
                    "details": str(item.get("details", "")).strip(),
                }
            )

    checks.sort(key=lambda row: (str(row.get("category", "")), str(row.get("id", ""))))
    total = len(checks)
    passed = sum(1 for row in checks if bool(row.get("passed", False)))
    failed = total - passed

    return {
        "suite": "gaia-quality-matrix",
        "status": "pass" if failed == 0 else "fail",
        "total": total,
        "passed": passed,
        "failed": failed,
        "checks": checks,
    }


def _build_benchmark_payload(hardening_payload: Dict[str, Any], quality_payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_results = hardening_payload.get("results", [])
    tasks: List[Dict[str, Any]] = []
    if isinstance(raw_results, list):
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("check_id", "")).strip()
            title = str(item.get("title", "")).strip()
            details = str(item.get("details", "")).strip()
            if not task_id:
                continue
            tasks.append(
                {
                    "id": task_id,
                    "title": title,
                    "passed": bool(item.get("passed", False)),
                    "details": details,
                    "canonical_source": "assistant/canonical-tasks.md",
                }
            )

    tasks.sort(key=lambda row: _task_key(str(row.get("id", ""))))
    total = len(tasks)
    passed = sum(1 for row in tasks if bool(row.get("passed", False)))
    failed = total - passed
    score_pct = round((passed / total) * 100, 2) if total else 0.0
    quality = _build_quality_matrix_payload(quality_payload)
    quality_total = int(quality.get("total", 0))
    quality_passed = int(quality.get("passed", 0))
    combined_total = total + quality_total
    combined_passed = passed + quality_passed
    combined_failed = combined_total - combined_passed
    combined_score_pct = round((combined_passed / combined_total) * 100, 2) if combined_total else 0.0

    return {
        "schema_version": 1,
        "suite": "phase1-quality-benchmark",
        "target_score_pct": 80.0,
        "total": combined_total,
        "passed": combined_passed,
        "failed": combined_failed,
        "score_pct": combined_score_pct,
        "tasks": tasks,
        "canonical_tasks": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "score_pct": score_pct,
        },
        "quality_matrix": quality,
        "methodology": {
            "description": "Phase 1 canonical tasks plus quality matrix guardrails benchmark",
            "task_source": "assistant/canonical-tasks.md",
            "runner": "tools/phase1-hardening.py",
            "quality_runner": "tools/quality-matrix.py",
        },
    }


def _compare_with_baseline(current: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    drifts: List[str] = []

    for key in ("suite", "schema_version", "total", "passed", "failed", "score_pct"):
        if current.get(key) != baseline.get(key):
            drifts.append(
                f"summary mismatch for '{key}': current={current.get(key)!r} baseline={baseline.get(key)!r}"
            )

    current_tasks = current.get("tasks", [])
    baseline_tasks = baseline.get("tasks", [])
    if not isinstance(current_tasks, list) or not isinstance(baseline_tasks, list):
        drifts.append("invalid task structure in current or baseline payload")
        return drifts

    current_index = {
        str(item.get("id", "")).strip(): item
        for item in current_tasks
        if isinstance(item, dict)
    }
    baseline_index = {
        str(item.get("id", "")).strip(): item
        for item in baseline_tasks
        if isinstance(item, dict)
    }

    current_ids = sorted([task_id for task_id in current_index if task_id])
    baseline_ids = sorted([task_id for task_id in baseline_index if task_id])

    if current_ids != baseline_ids:
        drifts.append("task id set mismatch between current run and baseline")

    shared_ids = sorted(set(current_ids).intersection(baseline_ids), key=_task_key)
    for task_id in shared_ids:
        current_item = current_index[task_id]
        baseline_item = baseline_index[task_id]
        if bool(current_item.get("passed", False)) != bool(baseline_item.get("passed", False)):
            drifts.append(
                f"task {task_id} pass/fail changed: current={bool(current_item.get('passed', False))} "
                f"baseline={bool(baseline_item.get('passed', False))}"
            )

    current_quality = current.get("quality_matrix", {})
    baseline_quality = baseline.get("quality_matrix", {})
    if not isinstance(current_quality, dict) or not isinstance(baseline_quality, dict):
        drifts.append("quality_matrix summary missing in current or baseline payload")
        return drifts

    for key in ("suite", "total", "passed", "failed", "status"):
        if current_quality.get(key) != baseline_quality.get(key):
            drifts.append(
                f"quality_matrix mismatch for '{key}': "
                f"current={current_quality.get(key)!r} baseline={baseline_quality.get(key)!r}"
            )

    current_checks = current_quality.get("checks", [])
    baseline_checks = baseline_quality.get("checks", [])
    if not isinstance(current_checks, list) or not isinstance(baseline_checks, list):
        drifts.append("invalid quality check structure in current or baseline payload")
        return drifts

    current_checks_index = {
        str(item.get("id", "")).strip(): item
        for item in current_checks
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    baseline_checks_index = {
        str(item.get("id", "")).strip(): item
        for item in baseline_checks
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }

    current_check_ids = sorted(current_checks_index.keys())
    baseline_check_ids = sorted(baseline_checks_index.keys())
    if current_check_ids != baseline_check_ids:
        drifts.append("quality check id set mismatch between current run and baseline")

    shared_check_ids = sorted(set(current_check_ids).intersection(baseline_check_ids))
    for check_id in shared_check_ids:
        current_item = current_checks_index[check_id]
        baseline_item = baseline_checks_index[check_id]
        if bool(current_item.get("passed", False)) != bool(baseline_item.get("passed", False)):
            drifts.append(
                f"quality check {check_id} pass/fail changed: "
                f"current={bool(current_item.get('passed', False))} "
                f"baseline={bool(baseline_item.get('passed', False))}"
            )

    return drifts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gaia canonical benchmark")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT), help="Path for benchmark output JSON")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="Path to baseline JSON")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite baseline with the current benchmark output",
    )
    args = parser.parse_args()

    json_out = Path(args.json_out).expanduser()
    baseline_path = Path(args.baseline).expanduser()

    rc, hardening_payload, hardening_stdout, hardening_stderr = _run_phase1_hardening()
    if not hardening_payload:
        print("Benchmark failed: could not read phase1-hardening output", file=sys.stderr)
        if hardening_stdout:
            print(hardening_stdout, file=sys.stderr)
        if hardening_stderr:
            print(hardening_stderr, file=sys.stderr)
        return 1

    quality_rc, quality_payload, quality_stdout, quality_stderr = _run_quality_matrix()
    if not quality_payload:
        print("Benchmark failed: could not read quality-matrix output", file=sys.stderr)
        if quality_stdout:
            print(quality_stdout, file=sys.stderr)
        if quality_stderr:
            print(quality_stderr, file=sys.stderr)
        return 1

    benchmark_payload = _build_benchmark_payload(hardening_payload, quality_payload)
    _write_json(json_out, benchmark_payload)

    if args.update_baseline:
        _write_json(baseline_path, benchmark_payload)
        print(f"Updated baseline: {baseline_path}")
    else:
        baseline_payload = _load_json(baseline_path)
        if not baseline_payload:
            print(
                f"Baseline not found at {baseline_path}. Run with --update-baseline to create it.",
                file=sys.stderr,
            )
            return 1
        drifts = _compare_with_baseline(benchmark_payload, baseline_payload)
        if drifts:
            print("Benchmark drift detected against baseline:", file=sys.stderr)
            for item in drifts:
                print(f"- {item}", file=sys.stderr)
            print("Run with --update-baseline to accept this new baseline.", file=sys.stderr)
            return 1

    print(json.dumps(benchmark_payload, indent=2, sort_keys=True))
    print(f"Benchmark results written to {json_out}")

    if rc != 0:
        print("Underlying hardening runner returned non-zero status.", file=sys.stderr)
        if hardening_stdout:
            print(hardening_stdout, file=sys.stderr)
        if hardening_stderr:
            print(hardening_stderr, file=sys.stderr)
        return 1

    if quality_rc != 0:
        print("Underlying quality-matrix runner returned non-zero status.", file=sys.stderr)
        if quality_stdout:
            print(quality_stdout, file=sys.stderr)
        if quality_stderr:
            print(quality_stderr, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
