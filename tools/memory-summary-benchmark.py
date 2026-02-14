#!/usr/bin/env python3
"""Deterministic memory summarization benchmark for Gaia memory runtime."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_FIXTURES = REPO_ROOT / "assistant" / "memory-summary-fixtures.json"
DEFAULT_JSON_OUT = REPO_ROOT / "assistant" / "memory-summary-benchmark-results.json"
GAIA_CMD = ["node", str(REPO_ROOT / "bin" / "gaia.js")]
PROFILE_LIMITS = {"concise": 3, "balanced": 5, "detailed": 8}


def _run_command(args: List[str], env: Dict[str, str]) -> Tuple[int, str, str]:
    proc = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _word_count(value: str) -> int:
    return len([token for token in str(value).strip().split() if token])


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(0, math.ceil(0.95 * len(sorted_values)) - 1)
    return float(sorted_values[idx])


def _reset_assistant_home(assistant_home: Path) -> None:
    for rel in ("data", "sessions", "traces", "state"):
        target = assistant_home / rel
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    (assistant_home / "config.json").unlink(missing_ok=True)


def _memory_add(record: Dict[str, Any], env: Dict[str, str]) -> None:
    args = [
        *GAIA_CMD,
        "memory",
        "add",
        "--memory-id",
        str(record.get("memory_id", "")).strip(),
        "--type",
        str(record.get("memory_type", "user_long")),
        "--subject",
        str(record.get("subject_id", "user:summary-benchmark")),
        "--content",
        str(record.get("content", "")),
        "--summary",
        str(record.get("summary", "")),
        "--confidence",
        str(record.get("confidence", 0.5)),
        "--importance",
        str(record.get("importance", 0.5)),
        "--consent-scope",
        str(record.get("consent_scope", "user")),
        "--retention-ttl",
        str(record.get("retention_ttl", "P30D")),
    ]
    rc, _, err = _run_command(args, env)
    if rc != 0:
        raise RuntimeError(f"memory add failed for {record.get('memory_id')}: {err.strip()}")


def _normalize_feedback_label(raw: str) -> str:
    value = str(raw).strip().lower().replace("_", "-")
    value = value.replace(" ", "-")
    if value == "nothelpful":
        value = "not-helpful"
    if value not in ("helpful", "not-helpful"):
        raise ValueError(f"Invalid feedback label in fixtures: {raw}")
    return value


def _seed_feedback(records: List[Dict[str, Any]], assistant_home: Path) -> None:
    if not records:
        return
    data_dir = assistant_home / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "feedback.json"
    now = datetime.now(timezone.utc).isoformat()
    payload: List[Dict[str, Any]] = []
    for idx, item in enumerate(records, start=1):
        if not isinstance(item, dict):
            continue
        label = _normalize_feedback_label(item.get("label", "helpful"))
        payload.append(
            {
                "id": str(item.get("id", f"fb-bench-{idx}")).strip() or f"fb-bench-{idx}",
                "label": label,
                "correction": str(item.get("correction", "")).strip(),
                "session_id": str(item.get("session_id", f"bench-session-{idx}")).strip(),
                "trace_id": str(item.get("trace_id", "")).strip(),
                "created_at": str(item.get("created_at", now)).strip(),
                "updated_at": str(item.get("updated_at", now)).strip(),
                "source": str(item.get("source", "benchmark")).strip() or "benchmark",
                "schema_version": 1,
            }
        )
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _normalize_profile(raw: str) -> str:
    value = str(raw).strip().lower().replace("_", "-").replace(" ", "-")
    if value in ("auto", "concise", "balanced", "detailed"):
        return value
    return ""


def _memory_summarize(case: Dict[str, Any], env: Dict[str, str]) -> Tuple[Dict[str, Any], float]:
    args: List[str] = [*GAIA_CMD, "memory", "summarize", "--json"]
    source_type = str(case.get("memory_type", "")).strip()
    if source_type:
        args.extend(["--type", source_type])
    subject_id = str(case.get("subject_id", "")).strip()
    if subject_id:
        args.extend(["--subject", subject_id])
    query = str(case.get("query", "")).strip()
    if query:
        args.extend(["--q", query])
    limit = int(case.get("limit", 200))
    if limit > 0:
        args.extend(["--limit", str(limit)])
    if bool(case.get("include_deleted", False)):
        args.append("--include-deleted")

    response_profile = _normalize_profile(case.get("response_profile", ""))
    if response_profile:
        args.extend(["--response-profile", response_profile])

    summary_type = str(case.get("summary_memory_type", "session_short")).strip() or "session_short"
    summary_subject = str(case.get("summary_subject_id", subject_id or "memory:summary")).strip()
    args.extend(["--summary-type", summary_type, "--summary-subject", summary_subject])

    summary_scope = str(case.get("summary_consent_scope", "")).strip()
    if summary_scope:
        args.extend(["--summary-consent-scope", summary_scope])
    retention_ttl = str(case.get("retention_ttl", "")).strip()
    if retention_ttl:
        args.extend(["--retention-ttl", retention_ttl])

    start = time.perf_counter()
    rc, out, err = _run_command(args, env)
    latency_ms = (time.perf_counter() - start) * 1000
    if rc != 0:
        raise RuntimeError(f"memory summarize failed for case '{case.get('id', '')}': {err.strip()}")

    payload = json.loads(out)
    if not isinstance(payload, dict):
        raise RuntimeError(f"memory summarize returned non-object payload for case '{case.get('id', '')}'")
    return payload, latency_ms


def _evaluate_case(case: Dict[str, Any], env: Dict[str, str], seeded_ids: set[str]) -> Dict[str, Any]:
    payload, latency_ms = _memory_summarize(case, env)
    summary_memory = payload.get("summary_memory", {})
    summary_event = payload.get("summary_event", {})
    source_memory_ids = payload.get("source_memory_ids", [])
    source_memory_ids = [str(item).strip() for item in source_memory_ids if str(item).strip()]

    if not isinstance(summary_memory, dict) or not isinstance(summary_event, dict):
        raise RuntimeError(f"Invalid summarize payload for case '{case.get('id', '')}'")

    event_source_ids = [
        str(item).strip()
        for item in summary_event.get("source_memory_ids", [])
        if str(item).strip()
    ]
    selected_source_count = int(summary_event.get("selected_source_count", len(source_memory_ids)))
    summary_content = str(summary_memory.get("content", "")).strip()
    summary_text = str(summary_memory.get("summary", "")).strip()
    summary_memory_id = str(summary_memory.get("memory_id", "")).strip()
    event_summary_memory_id = str(summary_event.get("summary_memory_id", "")).strip()
    actual_profile = _normalize_profile(summary_event.get("response_profile", ""))
    configured_profile = _normalize_profile(case.get("response_profile", ""))
    expected_profile = _normalize_profile(case.get("expected_profile", configured_profile))

    all_sources_known = all(item in seeded_ids for item in source_memory_ids)
    traceability_ok = (
        bool(summary_memory_id)
        and summary_memory_id == event_summary_memory_id
        and selected_source_count == len(source_memory_ids)
        and set(source_memory_ids) == set(event_source_ids)
        and all_sources_known
    )
    profile_match = (not expected_profile) or (actual_profile == expected_profile)

    selected_min = int(case.get("min_selected_sources", 1))
    selected_max = int(case.get("max_selected_sources", PROFILE_LIMITS.get(expected_profile or actual_profile or "balanced", 5)))
    words_min = int(case.get("min_content_words", 1))
    words_max = int(case.get("max_content_words", 400))
    summary_words = _word_count(summary_content)
    summary_text_words = _word_count(summary_text)

    failures: List[str] = []
    if not profile_match:
        failures.append(f"profile mismatch actual={actual_profile or '-'} expected={expected_profile or '-'}")
    if not traceability_ok:
        failures.append("traceability contract violated (summary/source linkage mismatch)")
    if selected_source_count < selected_min:
        failures.append(f"selected_source_count {selected_source_count} < {selected_min}")
    if selected_source_count > selected_max:
        failures.append(f"selected_source_count {selected_source_count} > {selected_max}")
    if summary_words < words_min:
        failures.append(f"summary_content_words {summary_words} < {words_min}")
    if summary_words > words_max:
        failures.append(f"summary_content_words {summary_words} > {words_max}")

    return {
        "id": str(case.get("id", "")),
        "response_profile_requested": configured_profile or "",
        "response_profile_expected": expected_profile or "",
        "response_profile_actual": actual_profile or "",
        "summary_memory_id": summary_memory_id,
        "summary_event_id": str(summary_event.get("summary_event_id", "")).strip(),
        "source_memory_ids": source_memory_ids,
        "selected_source_count": selected_source_count,
        "summary_content_words": summary_words,
        "summary_text_words": summary_text_words,
        "traceability_ok": traceability_ok,
        "profile_match": profile_match,
        "latency_ms": round(latency_ms, 3),
        "pass": len(failures) == 0,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gaia memory summarize benchmark")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Fixture JSON path")
    parser.add_argument("--assistant-home", default=None, help="GAIA_ASSISTANT_HOME override")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT), help="Benchmark JSON output path")
    parser.add_argument("--check", action="store_true", help="Fail when thresholds are not met")
    args = parser.parse_args()

    fixtures_path = Path(args.fixtures).expanduser()
    payload = _load_json(fixtures_path)
    records = payload.get("records", [])
    feedback = payload.get("feedback", [])
    cases = payload.get("cases", [])
    thresholds = payload.get("thresholds", {})
    if not isinstance(records, list) or not records:
        raise SystemExit("fixtures.records must be a non-empty array")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("fixtures.cases must be a non-empty array")
    if not isinstance(feedback, list):
        feedback = []
    if not isinstance(thresholds, dict):
        thresholds = {}

    managed_temp_home = False
    if args.assistant_home:
        assistant_home = Path(args.assistant_home).expanduser()
        assistant_home.mkdir(parents=True, exist_ok=True)
    else:
        assistant_home = Path(tempfile.mkdtemp(prefix="gaia-memory-summary-benchmark-")).resolve()
        managed_temp_home = True

    env = dict(os.environ)
    env["GAIA_ASSISTANT_HOME"] = str(assistant_home)
    env["GAIA_UAT_MODE"] = "deterministic"
    env["TZ"] = "UTC"
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)

    _reset_assistant_home(assistant_home)
    rc, _, err = _run_command([*GAIA_CMD, "init", "--force"], env)
    if rc != 0:
        raise SystemExit(f"gaia init failed: {err.strip()}")

    seeded_ids: set[str] = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        _memory_add(item, env)
        memory_id = str(item.get("memory_id", "")).strip()
        if memory_id:
            seeded_ids.add(memory_id)

    _seed_feedback([item for item in feedback if isinstance(item, dict)], assistant_home)

    case_results: List[Dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_results.append(_evaluate_case(case, env, seeded_ids))

    latencies = [float(item.get("latency_ms", 0.0)) for item in case_results]
    selected_counts = [float(item.get("selected_source_count", 0.0)) for item in case_results]
    content_words = [float(item.get("summary_content_words", 0.0)) for item in case_results]
    profile_matches = [1.0 if bool(item.get("profile_match", False)) else 0.0 for item in case_results]
    traceability = [1.0 if bool(item.get("traceability_ok", False)) else 0.0 for item in case_results]
    passes = [1.0 if bool(item.get("pass", False)) else 0.0 for item in case_results]

    summary = {
        "case_count": len(case_results),
        "case_pass_rate": round(statistics.fmean(passes) if passes else 0.0, 6),
        "profile_match_rate": round(statistics.fmean(profile_matches) if profile_matches else 0.0, 6),
        "traceability_rate": round(statistics.fmean(traceability) if traceability else 0.0, 6),
        "p95_latency_ms": round(_p95(latencies), 3),
        "avg_selected_sources": round(statistics.fmean(selected_counts) if selected_counts else 0.0, 3),
        "avg_summary_content_words": round(statistics.fmean(content_words) if content_words else 0.0, 3),
    }

    failures: List[str] = []
    for item in case_results:
        case_failures = [str(entry).strip() for entry in item.get("failures", []) if str(entry).strip()]
        for failure in case_failures:
            failures.append(f"{item.get('id', '<unknown-case>')}: {failure}")

    case_pass_rate_min = float(thresholds.get("case_pass_rate_min", 1.0))
    profile_match_min = float(thresholds.get("profile_match_rate_min", 1.0))
    traceability_min = float(thresholds.get("traceability_rate_min", 1.0))
    p95_latency_max = float(thresholds.get("p95_latency_ms_max", float("inf")))
    avg_selected_max = float(thresholds.get("avg_selected_sources_max", float("inf")))
    avg_content_words_max = float(thresholds.get("avg_summary_content_words_max", float("inf")))

    if summary["case_pass_rate"] < case_pass_rate_min:
        failures.append(f"case_pass_rate {summary['case_pass_rate']:.3f} < threshold {case_pass_rate_min:.3f}")
    if summary["profile_match_rate"] < profile_match_min:
        failures.append(f"profile_match_rate {summary['profile_match_rate']:.3f} < threshold {profile_match_min:.3f}")
    if summary["traceability_rate"] < traceability_min:
        failures.append(f"traceability_rate {summary['traceability_rate']:.3f} < threshold {traceability_min:.3f}")
    if summary["p95_latency_ms"] > p95_latency_max:
        failures.append(f"p95_latency_ms {summary['p95_latency_ms']:.3f} > threshold {p95_latency_max:.3f}")
    if summary["avg_selected_sources"] > avg_selected_max:
        failures.append(f"avg_selected_sources {summary['avg_selected_sources']:.3f} > threshold {avg_selected_max:.3f}")
    if summary["avg_summary_content_words"] > avg_content_words_max:
        failures.append(
            "avg_summary_content_words "
            f"{summary['avg_summary_content_words']:.3f} > threshold {avg_content_words_max:.3f}"
        )

    result: Dict[str, Any] = {
        "suite": "gaia-memory-summary-benchmark",
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixtures": str(fixtures_path),
        "assistant_home": str(assistant_home),
        "summary": summary,
        "thresholds": thresholds,
        "cases": case_results,
        "status": "pass" if not failures else "fail",
    }
    if failures:
        result["failures"] = failures

    json_out = Path(args.json_out).expanduser()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

    if managed_temp_home:
        shutil.rmtree(assistant_home, ignore_errors=True)

    if args.check and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
