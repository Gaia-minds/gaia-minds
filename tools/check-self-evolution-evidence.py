#!/usr/bin/env python3
"""Enforce self-evolution PR evidence rubric completeness."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


APPLIES_LABEL = "Applies: this PR changes self-evolution behavior/governance."
NOT_APPLIES_LABEL = "Not applicable: no self-evolution behavior/governance changes."
EVIDENCE_HEADING = "## Self-Evolution Evidence"
REQUIRED_FIELDS: Sequence[str] = (
    "Baseline evidence",
    "Delta observed",
    "Thresholds and guardrails",
    "Rollback/fallback",
    "Risk notes",
)
PLACEHOLDER_RE = re.compile(r"^(?:-|n/?a|none|todo|tbd|pending|same|unchanged)$", re.IGNORECASE)


def _parse_event_payload(path: Path) -> Tuple[Optional[str], Optional[str], List[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None, []

    if not isinstance(payload, dict):
        return None, None, []

    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return None, None, []

    body = str(pr.get("body", "") or "")
    title = str(pr.get("title", "") or "")
    labels_raw = pr.get("labels", [])
    labels: List[str] = []
    if isinstance(labels_raw, list):
        for item in labels_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "") or "").strip()
            if name:
                labels.append(name)
    return body, title, labels


def _checkbox_checked(body: str, label: str) -> Optional[bool]:
    pattern = re.compile(rf"(?im)^\s*-\s*\[([ xX])\]\s*{re.escape(label)}\s*$")
    match = pattern.search(body)
    if not match:
        return None
    return match.group(1).strip().lower() == "x"


def _extract_field(body: str, name: str) -> str:
    pattern = re.compile(rf"(?im)^[ \t]*-[ \t]*{re.escape(name)}[ \t]*:[ \t]*([^\r\n]+)[ \t]*$")
    match = pattern.search(body)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _is_substantive(value: str, min_len: int) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip().strip(".")
    if len(normalized) < min_len:
        return False
    return not PLACEHOLDER_RE.fullmatch(normalized)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce self-evolution PR evidence rubric")
    parser.add_argument("--pr-body", default="", help="PR body text override")
    parser.add_argument("--pr-title", default="", help="PR title override")
    parser.add_argument("--pr-body-file", default="", help="Read PR body from file path")
    parser.add_argument(
        "--event-path",
        default=os.environ.get("GITHUB_EVENT_PATH", ""),
        help="GitHub event payload path",
    )
    parser.add_argument(
        "--require-context",
        action="store_true",
        help="Fail if PR context cannot be resolved",
    )
    parser.add_argument(
        "--min-field-chars",
        default=12,
        type=int,
        help="Minimum non-whitespace characters for each required evidence field",
    )
    args = parser.parse_args()

    errors: List[str] = []
    notes: List[str] = []
    labels: List[str] = []

    body = args.pr_body
    title = args.pr_title

    if args.pr_body_file:
        try:
            body = Path(args.pr_body_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: unable to read --pr-body-file: {exc}")
            return 1
    elif not body and args.event_path:
        event_body, event_title, event_labels = _parse_event_payload(Path(args.event_path))
        if event_body is not None:
            body = event_body
            if not title:
                title = event_title or ""
            labels = event_labels

    if not body:
        if args.require_context:
            print("error: PR body context unavailable")
            return 1
        print("Self-evolution evidence rubric: PR context unavailable; skipping.")
        return 0

    applies_checked = _checkbox_checked(body, APPLIES_LABEL)
    not_applies_checked = _checkbox_checked(body, NOT_APPLIES_LABEL)

    if applies_checked is None or not_applies_checked is None:
        errors.append(
            "missing self-evolution applicability checklist lines in PR body "
            f"('{APPLIES_LABEL}' and '{NOT_APPLIES_LABEL}')"
        )
    elif applies_checked == not_applies_checked:
        errors.append("select exactly one self-evolution applicability option")

    self_evolution_labeled = any(label.lower() == "self-evolution" for label in labels)
    if self_evolution_labeled and applies_checked is False:
        errors.append("label 'self-evolution' is present but applicability is marked as not applicable")

    applies = applies_checked is True
    if applies:
        if not re.search(r"(?im)^\s*##\s+Self-Evolution Evidence\s*$", body):
            errors.append(f"missing heading: '{EVIDENCE_HEADING}'")

        for field in REQUIRED_FIELDS:
            value = _extract_field(body, field)
            if not value:
                errors.append(f"missing required evidence field: '{field}'")
                continue
            if not _is_substantive(value, min_len=max(1, args.min_field_chars)):
                errors.append(
                    f"evidence field '{field}' must be substantive (>= {args.min_field_chars} chars and not placeholder)"
                )
    else:
        notes.append("self-evolution rubric marked as not applicable")

    print("Self-evolution evidence rubric summary")
    print("=====================================")
    print(f"title={title or '(not provided)'}")
    print(f"labels={','.join(labels) if labels else '(none)'}")
    print(f"applicability={'applies' if applies else 'not-applicable'}")
    if notes:
        for note in notes:
            print(f"note: {note}")

    if errors:
        print("\nSelf-evolution evidence violations:")
        for item in errors:
            print(f"- {item}")
        return 1

    print("\nSelf-evolution evidence checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
