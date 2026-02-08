#!/usr/bin/env python3
"""Deterministic terminal UAT runner for Gaia assistant features.

This runner executes scenario commands from a JSON manifest in an isolated
GAIA_ASSISTANT_HOME. It writes per-scenario logs and a structured JSON report
suitable for CI artifacts and triage.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MANIFEST = REPO_ROOT / "assistant" / "uat-scenarios.json"
DEFAULT_RESULTS = REPO_ROOT / "assistant" / "uat-results.json"


@dataclass
class ScenarioResult:
    scenario_id: str
    description: str
    status: str
    expected_exit: int
    actual_exit: int
    duration_ms: float
    log_path: str
    command: str
    repro: str


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_shell(command: str, env: Dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


def _write_log(
    log_path: Path,
    *,
    scenario_id: str,
    description: str,
    command: str,
    expected_exit: int,
    actual_exit: int,
    duration_ms: float,
    proc: subprocess.CompletedProcess,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    body = [
        f"scenario_id={scenario_id}",
        f"description={description}",
        f"expected_exit={expected_exit}",
        f"actual_exit={actual_exit}",
        f"duration_ms={duration_ms:.3f}",
        f"command={command}",
        "",
        "[stdout]",
        proc.stdout,
        "",
        "[stderr]",
        proc.stderr,
        "",
    ]
    log_path.write_text("\n".join(body), encoding="utf-8")


def _scenario_matches(filters: List[str], scenario_id: str) -> bool:
    if not filters:
        return True
    return scenario_id in filters


def _metadata_payload(
    run_id: str,
    gaia_home: Path,
    html_fixture: Path,
    artifact_dir: Path,
    manifest_path: Path,
) -> Dict[str, Any]:
    def _cmd_version(cmd: List[str]) -> str:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10)
            raw = (proc.stdout or proc.stderr).strip()
            return raw.splitlines()[0] if raw else ""
        except Exception as exc:  # pragma: no cover - best effort metadata
            return f"error: {exc}"

    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "manifest": str(manifest_path),
        "gaia_assistant_home": str(gaia_home),
        "html_fixture": str(html_fixture),
        "artifact_dir": str(artifact_dir),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "versions": {
            "node": _cmd_version(["node", "--version"]),
            "python3": _cmd_version(["python3", "--version"]),
            "git": _cmd_version(["git", "--version"]),
        },
    }


def _write_failure_summary(results: List[ScenarioResult], artifact_dir: Path) -> None:
    failed = [item for item in results if item.status != "pass"]
    if not failed:
        return

    lines = [
        "# Gaia UAT Failure Summary",
        "",
        f"failed={len(failed)}",
        "",
    ]
    for item in failed:
        lines.append(f"## {item.scenario_id}")
        lines.append(f"- description: {item.description}")
        lines.append(f"- expected_exit: {item.expected_exit}")
        lines.append(f"- actual_exit: {item.actual_exit}")
        lines.append(f"- duration_ms: {item.duration_ms:.3f}")
        lines.append(f"- log: {item.log_path}")
        lines.append(f"- repro: {item.repro}")
        lines.append("")

        log_file = Path(item.log_path)
        try:
            tail = log_file.read_text(encoding="utf-8").splitlines()[-80:]
        except OSError:
            tail = ["<log unavailable>"]
        lines.append("```text")
        lines.extend(tail)
        lines.append("```")
        lines.append("")

    (artifact_dir / "failure-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_manifest(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    scenarios = manifest.get("scenarios", [])
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Manifest must include a non-empty 'scenarios' array")

    seen = set()
    normalized: List[Dict[str, Any]] = []
    for entry in scenarios:
        if not isinstance(entry, dict):
            raise ValueError("Each scenario must be an object")
        scenario_id = str(entry.get("id", "")).strip()
        if not scenario_id:
            raise ValueError("Scenario id cannot be empty")
        if scenario_id in seen:
            raise ValueError(f"Duplicate scenario id: {scenario_id}")
        seen.add(scenario_id)

        command = str(entry.get("command", "")).strip()
        if not command:
            raise ValueError(f"Scenario '{scenario_id}' missing command")

        expect_exit_raw = entry.get("expect_exit", 0)
        if not isinstance(expect_exit_raw, int):
            raise ValueError(f"Scenario '{scenario_id}' expect_exit must be an integer")

        normalized.append(
            {
                "id": scenario_id,
                "description": str(entry.get("description", "")).strip(),
                "command": command,
                "expect_exit": expect_exit_raw,
            }
        )

    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Gaia terminal UAT suite")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to UAT scenarios JSON")
    parser.add_argument("--json-out", default=str(DEFAULT_RESULTS), help="Path to UAT results JSON")
    parser.add_argument(
        "--artifacts-dir",
        default=None,
        help="Artifact output directory (default: assistant/uat-artifacts/<run-id>)",
    )
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        help="Run only a specific scenario id (repeatable)",
    )
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = Path(args.manifest).expanduser()
    results_path = Path(args.json_out).expanduser()
    artifact_dir = (
        Path(args.artifacts_dir).expanduser()
        if args.artifacts_dir
        else (REPO_ROOT / "assistant" / "uat-artifacts" / run_id)
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_json(manifest_path)
    scenarios = _validate_manifest(manifest)

    temp_root = Path(tempfile.mkdtemp(prefix="gaia-uat-"))
    gaia_home = temp_root / "assistant-home"
    gaia_home.mkdir(parents=True, exist_ok=True)
    html_fixture = temp_root / "sample-summary.html"
    html_fixture.write_text(
        (
            "<html><head><title>UAT Summary Fixture</title></head>"
            "<body><p>Deterministic fixture for summarize/summaries UAT.</p>"
            "<p>Used by Gaia terminal acceptance tests.</p></body></html>"
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["GAIA_ASSISTANT_HOME"] = str(gaia_home)
    env["GAIA_UAT_MODE"] = "deterministic"
    env["GAIA_UAT_RUN_ID"] = run_id
    env["HTML_FIXTURE"] = str(html_fixture)
    env["TZ"] = "UTC"
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)

    metadata = _metadata_payload(run_id, gaia_home, html_fixture, artifact_dir, manifest_path)
    _write_json(artifact_dir / "metadata.json", metadata)

    filters = [str(item).strip() for item in args.run if str(item).strip()]
    results: List[ScenarioResult] = []
    start_suite = time.perf_counter()

    for scenario in scenarios:
        scenario_id = scenario["id"]
        if not _scenario_matches(filters, scenario_id):
            continue

        command = scenario["command"]
        expected_exit = int(scenario["expect_exit"])
        description = scenario["description"]
        log_path = artifact_dir / f"{scenario_id}.log"

        start = time.perf_counter()
        proc = _run_shell(command, env=env, cwd=REPO_ROOT)
        duration_ms = (time.perf_counter() - start) * 1000.0
        _write_log(
            log_path,
            scenario_id=scenario_id,
            description=description,
            command=command,
            expected_exit=expected_exit,
            actual_exit=proc.returncode,
            duration_ms=duration_ms,
            proc=proc,
        )

        status = "pass" if proc.returncode == expected_exit else "fail"
        repro = (
            f"GAIA_ASSISTANT_HOME={shlex.quote(str(gaia_home))} "
            f"HTML_FIXTURE={shlex.quote(str(html_fixture))} "
            f"bash -lc {shlex.quote(command)}"
        )
        results.append(
            ScenarioResult(
                scenario_id=scenario_id,
                description=description,
                status=status,
                expected_exit=expected_exit,
                actual_exit=proc.returncode,
                duration_ms=duration_ms,
                log_path=str(log_path),
                command=command,
                repro=repro,
            )
        )

    suite_duration_ms = (time.perf_counter() - start_suite) * 1000.0
    total = len(results)
    passed = sum(1 for item in results if item.status == "pass")
    failed = total - passed

    payload = {
        "suite": "gaia-uat",
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "duration_ms": round(suite_duration_ms, 3),
        "gaia_assistant_home": str(gaia_home),
        "artifact_dir": str(artifact_dir),
        "results": [
            {
                "id": item.scenario_id,
                "description": item.description,
                "status": item.status,
                "expected_exit": item.expected_exit,
                "actual_exit": item.actual_exit,
                "duration_ms": round(item.duration_ms, 3),
                "log_path": item.log_path,
                "command": item.command,
                "repro": item.repro,
            }
            for item in results
        ],
    }

    _write_json(results_path, payload)
    _write_failure_summary(results, artifact_dir)

    print(json.dumps(payload, indent=2))
    print(f"UAT results written to {results_path}")
    print(f"UAT artifacts written to {artifact_dir}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
