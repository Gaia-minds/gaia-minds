#!/usr/bin/env python3
"""Deterministic quality matrix for malicious fixtures and runtime guardrails."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE_MANIFEST = REPO_ROOT / "assistant" / "fixtures" / "skills" / "manifest.json"
DEFAULT_FIXTURE_ROOT = REPO_ROOT / "assistant" / "fixtures" / "skills"
DEFAULT_JSON_OUT = REPO_ROOT / "assistant" / "quality-matrix-results.json"
DEFAULT_COMPAT_BASELINE = REPO_ROOT / "assistant" / "compatibility-matrix-baseline.json"
DEFAULT_COMPAT_MATRIX = REPO_ROOT / "assistant" / "compatibility-matrix.md"


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_command(cmd: List[str], env: Dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def _run_shell(command: str, env: Dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def _normalize_fixtures(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("fixture manifest must contain a non-empty 'fixtures' array")

    normalized: List[Dict[str, Any]] = []
    seen_ids = set()
    for item in fixtures:
        if not isinstance(item, dict):
            raise ValueError("fixture entries must be objects")
        fixture_id = str(item.get("id", "")).strip()
        if not fixture_id:
            raise ValueError("fixture id cannot be empty")
        if fixture_id in seen_ids:
            raise ValueError(f"duplicate fixture id '{fixture_id}'")
        seen_ids.add(fixture_id)

        rel_path = str(item.get("path", "")).strip()
        if not rel_path:
            raise ValueError(f"fixture '{fixture_id}' missing path")

        expect_status = str(item.get("expect_status", "")).strip().lower()
        if expect_status not in {"pass", "fail"}:
            raise ValueError(f"fixture '{fixture_id}' expect_status must be pass/fail")

        expect_codes_raw = item.get("expect_codes", [])
        if not isinstance(expect_codes_raw, list):
            raise ValueError(f"fixture '{fixture_id}' expect_codes must be an array")
        expect_codes = [str(code).strip() for code in expect_codes_raw if str(code).strip()]

        normalized.append(
            {
                "id": fixture_id,
                "category": str(item.get("category", "")).strip() or "fixtures",
                "path": rel_path,
                "expect_status": expect_status,
                "expect_codes": sorted(set(expect_codes)),
            }
        )
    return normalized


def _extract_report(proc: subprocess.CompletedProcess) -> Tuple[Dict[str, Any], str]:
    raw = (proc.stdout or "").strip()
    if not raw:
        return {}, "empty stdout from skills validate --json"
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, f"failed to parse JSON report: {exc}"
    if not isinstance(report, dict):
        return {}, "skills validate output was not a JSON object"
    return report, ""


def _fixture_check(fixture: Dict[str, Any], fixtures_root: Path, env: Dict[str, str]) -> Dict[str, Any]:
    fixture_path = (fixtures_root / str(fixture["path"])).resolve()
    start = time.perf_counter()

    if not fixture_path.exists():
        return {
            "id": str(fixture["id"]),
            "category": str(fixture["category"]),
            "type": "fixture",
            "status": "fail",
            "duration_ms": round((time.perf_counter() - start) * 1000.0, 3),
            "details": f"fixture path does not exist: {fixture_path}",
            "expected": {
                "expect_status": fixture["expect_status"],
                "expect_codes": fixture["expect_codes"],
            },
            "actual": {},
        }

    proc = _run_command(
        ["node", "./bin/gaia.js", "skills", "validate", str(fixture_path), "--json"],
        env,
    )
    report, parse_error = _extract_report(proc)

    expected_status = str(fixture["expect_status"])
    expected_codes = list(fixture["expect_codes"])

    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    finding_codes = sorted(
        {str(item.get("code", "")).strip() for item in findings if isinstance(item, dict) and str(item.get("code", "")).strip()}
    )
    report_status = str(report.get("status", "")).strip().lower()
    blocking_count = int(report.get("summary", {}).get("blocking_count", 0)) if isinstance(report.get("summary"), dict) else 0

    expectations_met = True
    detail_parts: List[str] = []

    if parse_error:
        expectations_met = False
        detail_parts.append(parse_error)

    if report_status != expected_status:
        expectations_met = False
        detail_parts.append(f"status mismatch (expected {expected_status}, got {report_status or 'unknown'})")

    if expected_status == "pass" and proc.returncode != 0:
        expectations_met = False
        detail_parts.append(f"expected exit=0, got {proc.returncode}")

    if expected_status == "fail" and proc.returncode == 0:
        expectations_met = False
        detail_parts.append("expected non-zero exit for failing fixture")

    if expected_status == "fail" and blocking_count <= 0:
        expectations_met = False
        detail_parts.append("expected blocking_count > 0 for failing fixture")

    missing_codes = [code for code in expected_codes if code not in finding_codes]
    if missing_codes:
        expectations_met = False
        detail_parts.append("missing expected finding codes: " + ", ".join(missing_codes))

    detail = "; ".join(detail_parts) if detail_parts else "ok"
    return {
        "id": str(fixture["id"]),
        "category": str(fixture["category"]),
        "type": "fixture",
        "status": "pass" if expectations_met else "fail",
        "duration_ms": round((time.perf_counter() - start) * 1000.0, 3),
        "details": detail,
        "expected": {
            "expect_status": expected_status,
            "expect_codes": expected_codes,
        },
        "actual": {
            "exit_code": proc.returncode,
            "report_status": report_status,
            "blocking_count": blocking_count,
            "finding_codes": finding_codes,
            "stderr": (proc.stderr or "").strip(),
        },
    }


def _runtime_check(
    *,
    check_id: str,
    category: str,
    command: str,
    expect_exit: int,
    expect_contains: List[str],
    env: Dict[str, str],
) -> Dict[str, Any]:
    start = time.perf_counter()
    proc = _run_shell(command, env)
    combined = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()

    passed = proc.returncode == expect_exit
    missing = [item for item in expect_contains if item not in combined]
    if missing:
        passed = False

    detail = "ok"
    if proc.returncode != expect_exit:
        detail = f"expected exit={expect_exit}, got {proc.returncode}"
    if missing:
        suffix = "missing output markers: " + ", ".join(missing)
        detail = suffix if detail == "ok" else f"{detail}; {suffix}"

    return {
        "id": check_id,
        "category": category,
        "type": "runtime",
        "status": "pass" if passed else "fail",
        "duration_ms": round((time.perf_counter() - start) * 1000.0, 3),
        "details": detail,
        "expected": {
            "exit_code": expect_exit,
            "contains": expect_contains,
        },
        "actual": {
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        },
    }


def _compatibility_check(baseline: Path, matrix_out: Path, env: Dict[str, str]) -> Dict[str, Any]:
    start = time.perf_counter()
    proc = _run_command(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "compatibility-matrix.py"),
            "--baseline",
            str(baseline),
            "--matrix-out",
            str(matrix_out),
            "--check",
        ],
        env,
    )
    passed = proc.returncode == 0
    detail = "ok" if passed else "compatibility matrix check failed"
    return {
        "id": "compatibility_matrix_reproducible",
        "category": "compatibility",
        "type": "compatibility",
        "status": "pass" if passed else "fail",
        "duration_ms": round((time.perf_counter() - start) * 1000.0, 3),
        "details": detail,
        "expected": {
            "exit_code": 0,
            "baseline": str(baseline),
            "matrix_out": str(matrix_out),
        },
        "actual": {
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gaia quality matrix checks")
    parser.add_argument("--manifest", default=str(DEFAULT_FIXTURE_MANIFEST), help="Fixture manifest JSON path")
    parser.add_argument("--fixtures-root", default=str(DEFAULT_FIXTURE_ROOT), help="Fixture root directory")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT), help="Quality matrix results JSON")
    parser.add_argument("--assistant-home", default=None, help="Optional GAIA_ASSISTANT_HOME override")
    parser.add_argument("--keep-assistant-home", action="store_true", help="Keep generated temporary assistant home")
    parser.add_argument(
        "--compatibility-baseline",
        default=str(DEFAULT_COMPAT_BASELINE),
        help="Compatibility matrix baseline JSON",
    )
    parser.add_argument(
        "--compatibility-matrix-out",
        default=str(DEFAULT_COMPAT_MATRIX),
        help="Compatibility matrix markdown path",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser()
    fixtures_root = Path(args.fixtures_root).expanduser()
    json_out = Path(args.json_out).expanduser()
    compat_baseline = Path(args.compatibility_baseline).expanduser()
    compat_matrix_out = Path(args.compatibility_matrix_out).expanduser()

    temp_home_root: Path | None = None
    if args.assistant_home:
        assistant_home = Path(args.assistant_home).expanduser()
        assistant_home.mkdir(parents=True, exist_ok=True)
    else:
        temp_home_root = Path(tempfile.mkdtemp(prefix="gaia-quality-matrix-"))
        assistant_home = temp_home_root / "assistant-home"
        assistant_home.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["GAIA_ASSISTANT_HOME"] = str(assistant_home)
    env["GAIA_UAT_MODE"] = "deterministic"
    env["GAIA_QUALITY_MATRIX"] = "1"
    env["TZ"] = "UTC"
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)

    start = time.perf_counter()
    checks: List[Dict[str, Any]] = []

    try:
        manifest = _load_json(manifest_path)
        fixtures = _normalize_fixtures(manifest)
    except Exception as exc:
        payload = {
            "schema_version": 1,
            "suite": "gaia-quality-matrix",
            "status": "fail",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "assistant_home": str(assistant_home),
            "total": 0,
            "passed": 0,
            "failed": 1,
            "duration_ms": round((time.perf_counter() - start) * 1000.0, 3),
            "checks": [
                {
                    "id": "manifest_load",
                    "category": "fixtures",
                    "type": "setup",
                    "status": "fail",
                    "duration_ms": 0.0,
                    "details": str(exc),
                    "expected": {},
                    "actual": {},
                }
            ],
        }
        _write_json(json_out, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    for fixture in fixtures:
        checks.append(_fixture_check(fixture, fixtures_root, env))

    checks.append(
        _runtime_check(
            check_id="sandbox_escalation_required",
            category="sandbox",
            command=(
                "set +e; "
                "node ./bin/gaia.js sandbox run --profile read-only -- sh -lc 'echo blocked > \"$GAIA_ASSISTANT_HOME/quality-blocked.txt\"' "
                "2>&1; rc=$?; set -e; "
                "[[ $rc -ne 0 ]]"
            ),
            expect_exit=0,
            expect_contains=["Escalation required"],
            env=env,
        )
    )

    checks.append(
        _runtime_check(
            check_id="sandbox_escalation_approved",
            category="sandbox",
            command=(
                "node ./bin/gaia.js sandbox run --profile read-only --approve-escalation -- "
                "sh -lc 'echo approved > \"$GAIA_ASSISTANT_HOME/quality-approved.txt\"' >/dev/null && "
                "[[ -f \"$GAIA_ASSISTANT_HOME/quality-approved.txt\" ]]"
            ),
            expect_exit=0,
            expect_contains=[],
            env=env,
        )
    )

    checks.append(
        _runtime_check(
            check_id="policy_tool_assertion_blocked",
            category="policy",
            command=(
                "set +e; "
                "node ./bin/gaia.js sandbox run --tool file_read -- "
                "sh -lc 'echo mismatch > \"$GAIA_ASSISTANT_HOME/quality-policy-mismatch.txt\"' 2>&1; "
                "rc=$?; set -e; [[ $rc -ne 0 ]]"
            ),
            expect_exit=0,
            expect_contains=["Policy tool assertion mismatch"],
            env=env,
        )
    )

    checks.append(
        _runtime_check(
            check_id="policy_allowlist_denies_write",
            category="policy",
            command=(
                "node ./bin/gaia.js policy allowlist set project:gaia-contributor --tools file_read >/dev/null && "
                "set +e; "
                "node ./bin/gaia.js sandbox run --skill project:gaia-contributor -- "
                "sh -lc 'echo blocked > \"$GAIA_ASSISTANT_HOME/quality-policy-blocked.txt\"' 2>&1; rc=$?; set -e; "
                "node ./bin/gaia.js policy allowlist clear project:gaia-contributor >/dev/null && "
                "[[ $rc -ne 0 ]]"
            ),
            expect_exit=0,
            expect_contains=["Policy denied"],
            env=env,
        )
    )

    checks.append(_compatibility_check(compat_baseline, compat_matrix_out, env))

    total = len(checks)
    passed = sum(1 for item in checks if item.get("status") == "pass")
    failed = total - passed

    payload = {
        "schema_version": 1,
        "suite": "gaia-quality-matrix",
        "status": "pass" if failed == 0 else "fail",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assistant_home": str(assistant_home),
        "manifest": str(manifest_path),
        "fixtures_root": str(fixtures_root),
        "total": total,
        "passed": passed,
        "failed": failed,
        "duration_ms": round((time.perf_counter() - start) * 1000.0, 3),
        "checks": checks,
    }

    _write_json(json_out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"quality matrix results written to {json_out}")

    if temp_home_root is not None and not args.keep_assistant_home:
        shutil.rmtree(temp_home_root, ignore_errors=True)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
