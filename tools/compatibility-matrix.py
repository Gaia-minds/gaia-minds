#!/usr/bin/env python3
"""Render and validate the Gaia compatibility matrix baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = REPO_ROOT / "assistant" / "compatibility-matrix-baseline.json"
DEFAULT_MATRIX = REPO_ROOT / "assistant" / "compatibility-matrix.md"
STATUS_CHOICES = {"supported", "partial", "gap"}


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _display_repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def _validate_evidence(item: Dict[str, Any], row_id: str) -> List[str]:
    errors: List[str] = []
    kind = str(item.get("type", "")).strip().lower()
    value = str(item.get("value", "")).strip()
    if kind not in {"path", "command", "note"}:
        errors.append(f"row '{row_id}' evidence has unsupported type '{kind}'")
        return errors
    if not value:
        errors.append(f"row '{row_id}' evidence value cannot be empty")
        return errors
    if kind == "path":
        if not (REPO_ROOT / value).exists():
            errors.append(f"row '{row_id}' references missing path '{value}'")
    return errors


def _validate_baseline(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if int(payload.get("schema_version", 0)) != 1:
        errors.append("schema_version must be 1")

    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        for key in ("repository", "reference", "default_branch", "checked_at"):
            if not str(source.get(key, "")).strip():
                errors.append(f"source.{key} is required")

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("rows must be a non-empty array")
        return errors

    seen_ids = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("rows entries must be objects")
            continue
        row_id = str(row.get("id", "")).strip()
        if not row_id:
            errors.append("row id cannot be empty")
            continue
        if row_id in seen_ids:
            errors.append(f"duplicate row id '{row_id}'")
        seen_ids.add(row_id)

        for key in ("dimension", "upstream_expectation", "gaia_status", "rationale"):
            if not str(row.get(key, "")).strip():
                errors.append(f"row '{row_id}' missing required field '{key}'")

        status = str(row.get("gaia_status", "")).strip().lower()
        if status and status not in STATUS_CHOICES:
            errors.append(
                f"row '{row_id}' has invalid gaia_status '{status}' (expected one of {sorted(STATUS_CHOICES)})"
            )

        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"row '{row_id}' must include a non-empty evidence array")
            continue
        for item in evidence:
            if not isinstance(item, dict):
                errors.append(f"row '{row_id}' evidence entries must be objects")
                continue
            errors.extend(_validate_evidence(item, row_id))

    return errors


def _format_evidence(items: List[Dict[str, Any]]) -> str:
    rendered: List[str] = []
    for item in items:
        kind = str(item.get("type", "")).strip().lower()
        value = str(item.get("value", "")).strip()
        if kind == "path":
            rendered.append(f"`{value}`")
        elif kind == "command":
            rendered.append(f"`{value}`")
        else:
            rendered.append(value)
    return "<br>".join(rendered)


def _render_matrix(payload: Dict[str, Any], baseline_path: Path) -> str:
    source = payload.get("source", {})
    rows = payload.get("rows", [])
    baseline_display = _display_repo_path(baseline_path)

    lines: List[str] = [
        "# Gaia Compatibility Matrix (agent-skills baseline)",
        "",
        "This matrix compares Gaia's skill/sandbox quality model against "
        "`vercel-labs/agent-skills` and is generated from a pinned baseline.",
        "",
        f"- Source repository: `{source.get('repository', '')}`",
        f"- Source branch: `{source.get('default_branch', '')}`",
        f"- Source reference: `{source.get('reference', '')}`",
        f"- Source checked at: `{source.get('checked_at', '')}`",
        f"- Baseline file: `{baseline_display}`",
        "",
        "| Dimension | Upstream expectation | Gaia status | Rationale | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        if not isinstance(row, dict):
            continue
        dimension = str(row.get("dimension", "")).replace("|", "\\|")
        expectation = str(row.get("upstream_expectation", "")).replace("|", "\\|")
        status = str(row.get("gaia_status", "")).strip().lower()
        rationale = str(row.get("rationale", "")).replace("|", "\\|")
        evidence = _format_evidence(row.get("evidence", []))
        lines.append(f"| {dimension} | {expectation} | `{status}` | {rationale} | {evidence} |")

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "```bash",
            "# regenerate matrix markdown from pinned baseline",
            "python3 tools/compatibility-matrix.py \\",
            "  --baseline assistant/compatibility-matrix-baseline.json \\",
            "  --matrix-out assistant/compatibility-matrix.md",
            "",
            "# verify committed markdown is current",
            "python3 tools/compatibility-matrix.py \\",
            "  --baseline assistant/compatibility-matrix-baseline.json \\",
            "  --matrix-out assistant/compatibility-matrix.md --check",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render/check Gaia compatibility matrix")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="Path to compatibility baseline JSON")
    parser.add_argument("--matrix-out", default=str(DEFAULT_MATRIX), help="Path to generated markdown matrix")
    parser.add_argument("--check", action="store_true", help="Fail if generated markdown differs from committed file")
    args = parser.parse_args()

    baseline_path = Path(args.baseline).expanduser()
    matrix_path = Path(args.matrix_out).expanduser()

    try:
        baseline = _load_json(baseline_path)
    except Exception as exc:
        print(f"error: could not read baseline: {exc}", file=sys.stderr)
        return 1

    errors = _validate_baseline(baseline)
    if errors:
        print("compatibility baseline validation failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    rendered = _render_matrix(baseline, baseline_path)
    if args.check:
        current = _read_file(matrix_path)
        if current != rendered:
            print(
                f"compatibility matrix drift detected: regenerate {matrix_path} from {baseline_path}",
                file=sys.stderr,
            )
            return 1
        print(f"compatibility matrix check passed: {matrix_path}")
        return 0

    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.write_text(rendered, encoding="utf-8")
    print(f"compatibility matrix written: {matrix_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
