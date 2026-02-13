#!/usr/bin/env python3
"""Deterministic memory QA/red-team harness for poisoning and leakage gates."""

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
DEFAULT_FIXTURES = REPO_ROOT / "assistant" / "memory-quality-fixtures.json"
DEFAULT_JSON_OUT = REPO_ROOT / "assistant" / "memory-quality-results.json"
GAIA_CMD = ["node", str(REPO_ROOT / "bin" / "gaia.js")]


def _run_command(args: List[str], env: Dict[str, str]) -> Tuple[int, str, str]:
    proc = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def _word_count(value: str) -> int:
    return len([token for token in str(value).strip().split() if token])


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(0, math.ceil(0.95 * len(sorted_values)) - 1)
    return float(sorted_values[idx])


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


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
        str(record.get("subject_id", "user:default")),
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


def _memory_retrieve(
    *,
    query: str,
    subject_id: str,
    memory_type: str,
    k: int,
    env: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], float]:
    args = [*GAIA_CMD, "memory", "retrieve", "--query", query, "--json", "--limit", str(k)]
    if subject_id:
        args.extend(["--subject", subject_id])
    if memory_type:
        args.extend(["--type", memory_type])

    start = time.perf_counter()
    rc, out, err = _run_command(args, env)
    latency_ms = (time.perf_counter() - start) * 1000

    if rc != 0:
        raise RuntimeError(f"memory retrieve failed for query '{query}': {err.strip()}")

    payload = json.loads(out)
    if not isinstance(payload, list):
        raise RuntimeError(f"memory retrieve returned non-list payload for query '{query}'")
    rows = [item for item in payload if isinstance(item, dict)]
    return rows, latency_ms


def _top_ids(rows: List[Dict[str, Any]], k: int) -> List[str]:
    return [str(item.get("memory_id", "")).strip() for item in rows[:k] if str(item.get("memory_id", "")).strip()]


def _token_overhead(rows: List[Dict[str, Any]], k: int) -> float:
    top_rows = rows[:k]
    return float(sum(_word_count(item.get("content", "")) + _word_count(item.get("summary", "")) for item in top_rows))


def _validate_fixture_arrays(payload: Dict[str, Any]) -> None:
    for key in ("records", "retrieval_cases", "poisoning_cases", "leakage_cases"):
        value = payload.get(key)
        if not isinstance(value, list) or not value:
            raise ValueError(f"fixtures.{key} must be a non-empty array")


def _evaluate_retrieval_case(case: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    query = str(case.get("query", "")).strip()
    subject_id = str(case.get("subject_id", "")).strip()
    memory_type = str(case.get("memory_type", "")).strip()
    expected_ids = [str(item).strip() for item in case.get("expected_ids", []) if str(item).strip()]
    k = max(1, int(case.get("k", 5)))

    rows, latency_ms = _memory_retrieve(
        query=query,
        subject_id=subject_id,
        memory_type=memory_type,
        k=k,
        env=env,
    )

    returned_ids = _top_ids(rows, k)
    expected_set = set(expected_ids)
    hit_count = len([item for item in returned_ids if item in expected_set])
    recall = hit_count / float(len(expected_set) or 1)
    precision = hit_count / float(k)
    faithfulness_at_1 = 1.0 if returned_ids and returned_ids[0] in expected_set else 0.0

    return {
        "id": str(case.get("id", "")),
        "query": query,
        "subject_id": subject_id,
        "k": k,
        "expected_ids": expected_ids,
        "returned_ids": returned_ids,
        "recall_at_k": round(recall, 6),
        "precision_at_k": round(precision, 6),
        "faithfulness_at_1": round(faithfulness_at_1, 6),
        "latency_ms": round(latency_ms, 3),
        "token_overhead_estimate": round(_token_overhead(rows, k), 3),
    }


def _evaluate_poisoning_case(case: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    query = str(case.get("query", "")).strip()
    subject_id = str(case.get("subject_id", "")).strip()
    memory_type = str(case.get("memory_type", "")).strip()
    safe_ids = [str(item).strip() for item in case.get("safe_ids", []) if str(item).strip()]
    poison_ids = [str(item).strip() for item in case.get("poison_ids", []) if str(item).strip()]
    k = max(1, int(case.get("k", 5)))

    rows, latency_ms = _memory_retrieve(
        query=query,
        subject_id=subject_id,
        memory_type=memory_type,
        k=k,
        env=env,
    )

    returned_ids = _top_ids(rows, k)
    safe_set = set(safe_ids)
    poison_set = set(poison_ids)
    top1_safe = bool(returned_ids) and returned_ids[0] in safe_set
    poison_top1 = bool(returned_ids) and returned_ids[0] in poison_set
    poison_hits = [item for item in returned_ids if item in poison_set]
    case_pass = top1_safe and not poison_top1

    return {
        "id": str(case.get("id", "")),
        "query": query,
        "subject_id": subject_id,
        "k": k,
        "safe_ids": safe_ids,
        "poison_ids": poison_ids,
        "returned_ids": returned_ids,
        "top1_safe": top1_safe,
        "poison_top1": poison_top1,
        "poison_hits": poison_hits,
        "pass": case_pass,
        "latency_ms": round(latency_ms, 3),
        "token_overhead_estimate": round(_token_overhead(rows, k), 3),
    }


def _evaluate_leakage_case(case: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    query = str(case.get("query", "")).strip()
    subject_id = str(case.get("subject_id", "")).strip()
    memory_type = str(case.get("memory_type", "")).strip()
    forbidden_ids = [str(item).strip() for item in case.get("forbidden_ids", []) if str(item).strip()]
    k = max(1, int(case.get("k", 5)))

    rows, latency_ms = _memory_retrieve(
        query=query,
        subject_id=subject_id,
        memory_type=memory_type,
        k=k,
        env=env,
    )

    returned_ids = _top_ids(rows, k)
    forbidden_set = set(forbidden_ids)
    leakage_hits = [item for item in returned_ids if item in forbidden_set]
    case_pass = len(leakage_hits) == 0

    return {
        "id": str(case.get("id", "")),
        "query": query,
        "subject_id": subject_id,
        "k": k,
        "forbidden_ids": forbidden_ids,
        "returned_ids": returned_ids,
        "leakage_hits": leakage_hits,
        "pass": case_pass,
        "latency_ms": round(latency_ms, 3),
        "token_overhead_estimate": round(_token_overhead(rows, k), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gaia memory QA/red-team harness")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Fixture JSON path")
    parser.add_argument("--assistant-home", default=None, help="GAIA_ASSISTANT_HOME override")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT), help="Result JSON output path")
    parser.add_argument("--check", action="store_true", help="Fail when thresholds are not met")
    args = parser.parse_args()

    fixtures_path = Path(args.fixtures).expanduser()
    payload = _load_json(fixtures_path)
    _validate_fixture_arrays(payload)

    records = payload.get("records", [])
    retrieval_cases = payload.get("retrieval_cases", [])
    poisoning_cases = payload.get("poisoning_cases", [])
    leakage_cases = payload.get("leakage_cases", [])
    thresholds = payload.get("thresholds", {})
    if not isinstance(thresholds, dict):
        thresholds = {}

    managed_temp_home = False
    if args.assistant_home:
        assistant_home = Path(args.assistant_home).expanduser()
        assistant_home.mkdir(parents=True, exist_ok=True)
    else:
        assistant_home = Path(tempfile.mkdtemp(prefix="gaia-memory-quality-")).resolve()
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

    for record in records:
        if isinstance(record, dict):
            _memory_add(record, env)

    retrieval_results: List[Dict[str, Any]] = []
    poisoning_results: List[Dict[str, Any]] = []
    leakage_results: List[Dict[str, Any]] = []

    for case in retrieval_cases:
        if isinstance(case, dict):
            retrieval_results.append(_evaluate_retrieval_case(case, env))

    for case in poisoning_cases:
        if isinstance(case, dict):
            poisoning_results.append(_evaluate_poisoning_case(case, env))

    for case in leakage_cases:
        if isinstance(case, dict):
            leakage_results.append(_evaluate_leakage_case(case, env))

    retrieval_recalls = [float(item.get("recall_at_k", 0.0)) for item in retrieval_results]
    retrieval_precisions = [float(item.get("precision_at_k", 0.0)) for item in retrieval_results]
    retrieval_faithfulness = [float(item.get("faithfulness_at_1", 0.0)) for item in retrieval_results]

    poisoning_passes = [bool(item.get("pass", False)) for item in poisoning_results]
    leakage_passes = [bool(item.get("pass", False)) for item in leakage_results]

    all_latencies = [float(item.get("latency_ms", 0.0)) for item in retrieval_results + poisoning_results + leakage_results]
    all_token_overheads = [
        float(item.get("token_overhead_estimate", 0.0))
        for item in retrieval_results + poisoning_results + leakage_results
    ]

    summary = {
        "recall_at_k": round(statistics.fmean(retrieval_recalls) if retrieval_recalls else 0.0, 6),
        "precision_at_k": round(statistics.fmean(retrieval_precisions) if retrieval_precisions else 0.0, 6),
        "faithfulness_at_1": round(statistics.fmean(retrieval_faithfulness) if retrieval_faithfulness else 0.0, 6),
        "poisoning_resistance": round(
            (sum(1 for item in poisoning_passes if item) / float(len(poisoning_passes))) if poisoning_passes else 0.0,
            6,
        ),
        "leakage_block_rate": round(
            (sum(1 for item in leakage_passes if item) / float(len(leakage_passes))) if leakage_passes else 0.0,
            6,
        ),
        "p95_latency_ms": round(_p95(all_latencies), 3),
        "avg_token_overhead": round(statistics.fmean(all_token_overheads) if all_token_overheads else 0.0, 3),
    }

    failures: List[str] = []

    recall_min = float(thresholds.get("recall_at_k_min", 0.0))
    precision_min = float(thresholds.get("precision_at_k_min", 0.0))
    faithfulness_min = float(thresholds.get("faithfulness_at_1_min", 0.0))
    poisoning_min = float(thresholds.get("poisoning_resistance_min", 0.0))
    leakage_min = float(thresholds.get("leakage_block_rate_min", 0.0))
    latency_max = float(thresholds.get("p95_latency_ms_max", float("inf")))
    token_max = float(thresholds.get("avg_token_overhead_max", float("inf")))

    if summary["recall_at_k"] < recall_min:
        failures.append(f"recall_at_k {summary['recall_at_k']:.3f} < threshold {recall_min:.3f}")
    if summary["precision_at_k"] < precision_min:
        failures.append(f"precision_at_k {summary['precision_at_k']:.3f} < threshold {precision_min:.3f}")
    if summary["faithfulness_at_1"] < faithfulness_min:
        failures.append(f"faithfulness_at_1 {summary['faithfulness_at_1']:.3f} < threshold {faithfulness_min:.3f}")
    if summary["poisoning_resistance"] < poisoning_min:
        failures.append(f"poisoning_resistance {summary['poisoning_resistance']:.3f} < threshold {poisoning_min:.3f}")
    if summary["leakage_block_rate"] < leakage_min:
        failures.append(f"leakage_block_rate {summary['leakage_block_rate']:.3f} < threshold {leakage_min:.3f}")
    if summary["p95_latency_ms"] > latency_max:
        failures.append(f"p95_latency_ms {summary['p95_latency_ms']:.3f} > threshold {latency_max:.3f}")
    if summary["avg_token_overhead"] > token_max:
        failures.append(f"avg_token_overhead {summary['avg_token_overhead']:.3f} > threshold {token_max:.3f}")

    result: Dict[str, Any] = {
        "suite": "gaia-memory-quality-matrix",
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixtures": str(fixtures_path),
        "assistant_home": str(assistant_home),
        "summary": summary,
        "thresholds": thresholds,
        "retrieval_cases": retrieval_results,
        "poisoning_cases": poisoning_results,
        "leakage_cases": leakage_results,
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
