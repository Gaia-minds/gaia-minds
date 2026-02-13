#!/usr/bin/env python3
"""Deterministic memory retrieval benchmark for Gaia memory runtime."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_FIXTURES = REPO_ROOT / "assistant" / "memory-retrieval-fixtures.json"
DEFAULT_JSON_OUT = REPO_ROOT / "assistant" / "memory-retrieval-benchmark-results.json"
GAIA_CMD = ["node", str(REPO_ROOT / "bin" / "gaia.js")]


def _run_command(args: List[str], env: Dict[str, str]) -> Tuple[int, str, str]:
    proc = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def _word_count(value: str) -> int:
    return len([token for token in str(value).strip().split() if token])


def _dcg(relevances: List[int]) -> float:
    total = 0.0
    for idx, rel in enumerate(relevances):
        total += float(rel) / math.log2(idx + 2)
    return total


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
        str(record.get("subject_id", "benchmark:default")),
        "--content",
        str(record.get("content", "")),
        "--summary",
        str(record.get("summary", "")),
        "--confidence",
        str(record.get("confidence", 0.5)),
        "--importance",
        str(record.get("importance", 0.5)),
        "--consent-scope",
        str(record.get("consent_scope", "session")),
        "--retention-ttl",
        str(record.get("retention_ttl", "")),
    ]
    rc, _, err = _run_command(args, env)
    if rc != 0:
        raise RuntimeError(f"memory add failed for {record.get('memory_id')}: {err.strip()}")


def _memory_retrieve(case: Dict[str, Any], env: Dict[str, str]) -> Tuple[List[Dict[str, Any]], float]:
    query = str(case.get("query", "")).strip()
    if not query:
        raise ValueError("query cannot be empty")

    args = [*GAIA_CMD, "memory", "retrieve", "--query", query, "--json"]
    subject_id = str(case.get("subject_id", "")).strip()
    if subject_id:
        args.extend(["--subject", subject_id])
    memory_type = str(case.get("memory_type", "")).strip()
    if memory_type:
        args.extend(["--type", memory_type])
    k = int(case.get("k", 5))
    if k > 0:
        args.extend(["--limit", str(k)])

    start = time.perf_counter()
    rc, out, err = _run_command(args, env)
    latency_ms = (time.perf_counter() - start) * 1000
    if rc != 0:
        raise RuntimeError(f"memory retrieve failed for query '{query}': {err.strip()}")

    payload = json.loads(out)
    if not isinstance(payload, list):
        raise RuntimeError(f"memory retrieve returned non-list payload for query '{query}'")
    records = [item for item in payload if isinstance(item, dict)]
    return records, latency_ms


def main() -> int:
    parser = argparse.ArgumentParser(description="Gaia memory retrieval benchmark")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Fixture JSON path")
    parser.add_argument("--assistant-home", default=None, help="GAIA_ASSISTANT_HOME override")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT), help="Benchmark JSON output path")
    parser.add_argument("--check", action="store_true", help="Fail when thresholds are not met")
    args = parser.parse_args()

    fixtures_path = Path(args.fixtures).expanduser()
    payload = _load_json(fixtures_path)
    records = payload.get("records", [])
    queries = payload.get("queries", [])
    thresholds = payload.get("thresholds", {})

    if not isinstance(records, list) or not records:
        raise SystemExit("fixtures.records must be a non-empty array")
    if not isinstance(queries, list) or not queries:
        raise SystemExit("fixtures.queries must be a non-empty array")
    if not isinstance(thresholds, dict):
        thresholds = {}

    managed_temp_home = False
    assistant_home: Path
    if args.assistant_home:
        assistant_home = Path(args.assistant_home).expanduser()
        assistant_home.mkdir(parents=True, exist_ok=True)
    else:
        assistant_home = Path(tempfile.mkdtemp(prefix="gaia-memory-benchmark-")).resolve()
        managed_temp_home = True

    env = dict(os.environ)
    env["GAIA_ASSISTANT_HOME"] = str(assistant_home)

    # Ensure deterministic empty state per run.
    for rel in ("data", "sessions", "traces", "state", "config.json"):
        target = assistant_home / rel
        if target.is_file():
            target.unlink(missing_ok=True)
        elif target.is_dir():
            for child in sorted(target.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    child.rmdir()
            target.rmdir()

    # Bootstrap config and fixture records.
    rc, _, err = _run_command([*GAIA_CMD, "init", "--force"], env)
    if rc != 0:
        raise SystemExit(f"gaia init failed: {err.strip()}")

    for item in records:
        if not isinstance(item, dict):
            continue
        _memory_add(item, env)

    query_results: List[Dict[str, Any]] = []
    recalls: List[float] = []
    ndcgs: List[float] = []
    latencies: List[float] = []
    token_overheads: List[float] = []

    for case in queries:
        if not isinstance(case, dict):
            continue
        result_rows, latency_ms = _memory_retrieve(case, env)
        expected_ids = [str(item).strip() for item in case.get("expected_ids", []) if str(item).strip()]
        k = int(case.get("k", 5))
        if k <= 0:
            k = 5

        top_rows = result_rows[:k]
        top_ids = [str(item.get("memory_id", "")).strip() for item in top_rows]

        expected_set = set(expected_ids)
        if expected_set:
            hit_count = len([item for item in top_ids if item in expected_set])
            recall = hit_count / float(len(expected_set))
            relevances = [1 if item in expected_set else 0 for item in top_ids]
            ideal_relevances = [1] * min(len(expected_set), k)
            dcg = _dcg(relevances)
            idcg = _dcg(ideal_relevances)
            ndcg = (dcg / idcg) if idcg > 0 else 1.0
        else:
            recall = 1.0
            ndcg = 1.0

        token_overhead = float(
            sum(_word_count(item.get("content", "")) + _word_count(item.get("summary", "")) for item in top_rows)
        )

        recalls.append(recall)
        ndcgs.append(ndcg)
        latencies.append(latency_ms)
        token_overheads.append(token_overhead)

        query_results.append(
            {
                "id": str(case.get("id", "")),
                "query": str(case.get("query", "")),
                "subject_id": str(case.get("subject_id", "")),
                "k": k,
                "expected_ids": expected_ids,
                "returned_ids": top_ids,
                "recall_at_k": round(recall, 6),
                "ndcg_at_k": round(ndcg, 6),
                "latency_ms": round(latency_ms, 3),
                "token_overhead_estimate": round(token_overhead, 3),
            }
        )

    summary = {
        "recall_at_k": round(statistics.fmean(recalls) if recalls else 0.0, 6),
        "ndcg_at_k": round(statistics.fmean(ndcgs) if ndcgs else 0.0, 6),
        "p95_latency_ms": round(_p95(latencies), 3),
        "avg_token_overhead": round(statistics.fmean(token_overheads) if token_overheads else 0.0, 3),
    }

    result: Dict[str, Any] = {
        "suite": "gaia-memory-benchmark",
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixtures": str(fixtures_path),
        "assistant_home": str(assistant_home),
        "summary": summary,
        "thresholds": thresholds,
        "queries": query_results,
    }

    failures: List[str] = []
    recall_min = float(thresholds.get("recall_at_k_min", 0.0))
    ndcg_min = float(thresholds.get("ndcg_at_k_min", 0.0))
    latency_max = float(thresholds.get("p95_latency_ms_max", float("inf")))
    token_max = float(thresholds.get("avg_token_overhead_max", float("inf")))

    if summary["recall_at_k"] < recall_min:
        failures.append(
            f"recall_at_k {summary['recall_at_k']:.3f} < threshold {recall_min:.3f}"
        )
    if summary["ndcg_at_k"] < ndcg_min:
        failures.append(
            f"ndcg_at_k {summary['ndcg_at_k']:.3f} < threshold {ndcg_min:.3f}"
        )
    if summary["p95_latency_ms"] > latency_max:
        failures.append(
            f"p95_latency_ms {summary['p95_latency_ms']:.3f} > threshold {latency_max:.3f}"
        )
    if summary["avg_token_overhead"] > token_max:
        failures.append(
            f"avg_token_overhead {summary['avg_token_overhead']:.3f} > threshold {token_max:.3f}"
        )

    result["status"] = "pass" if not failures else "fail"
    if failures:
        result["failures"] = failures

    json_out = Path(args.json_out).expanduser()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))

    if managed_temp_home:
        # Best-effort cleanup of temporary benchmark state.
        for child in sorted(assistant_home.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        assistant_home.rmdir()

    if args.check and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
