#!/usr/bin/env python3
"""Generate deterministic live-preview assets from executable Gaia command flow."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
ASSISTANT_DIR = REPO_ROOT / "assistant"
ASSETS_DIR = ASSISTANT_DIR / "assets"
DEFAULT_TERMINAL_SVG = ASSETS_DIR / "gaia-assistant-terminal.svg"
DEFAULT_ANIMATED_SVG = ASSETS_DIR / "gaia-assistant-demo-animated.svg"
DEFAULT_TRANSCRIPT = ASSETS_DIR / "gaia-assistant-live-preview-transcript.md"
GAIA_ASSISTANT = [sys.executable, str(REPO_ROOT / "tools" / "gaia-assistant.py")]


@dataclass(frozen=True)
class FlowStep:
    command: str
    outputs: List[str]


def _run_command(args: Sequence[str], env: Dict[str, str], *, stdin_text: str | None = None) -> str:
    cmd = [*GAIA_ASSISTANT, *args]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        input=stdin_text,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        details = "\n".join(item for item in (stdout, stderr) if item)
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{details}")
    return proc.stdout.rstrip("\n")


def _find_line(output: str, needle: str, *, context: str) -> str:
    for line in output.splitlines():
        if needle in line:
            return line.strip()
    raise RuntimeError(f"could not find '{needle}' in {context} output")


def _extract_id(pattern: str, text: str, *, context: str) -> str:
    match = re.search(pattern, text)
    if not match:
        raise RuntimeError(f"could not extract id from {context}")
    return match.group(0)


def _extract_chat_reply(chat_output: str) -> str:
    for line in chat_output.splitlines():
        if "[local-openai][profile=concise]" not in line:
            continue
        prompt_idx = line.find("gaia>")
        if prompt_idx >= 0:
            return line[prompt_idx:].strip()
        return line.strip()
    raise RuntimeError("could not find local-openai chat reply in chat output")


def _normalize_text(text: str, replacements: Dict[str, str]) -> str:
    normalized = text
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if source:
            normalized = normalized.replace(source, target)

    regex_replacements = (
        (r"\bms\d{14}-[0-9a-f]+\b", "<summary-event-id>"),
        (r"\bs\d{14}-[0-9a-f]+\b", "<session-id>"),
        (r"\bfb\d{14}-[0-9a-f]+\b", "<feedback-id>"),
        (r"\bm\d{14}-[0-9a-f]+\b", "<memory-id>"),
        (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<trace-id>"),
        (r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+00:00|Z)\b", "<timestamp>"),
    )
    for pattern, target in regex_replacements:
        normalized = re.sub(pattern, target, normalized)
    return normalized


def _capture_preview_flow() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gaia-live-preview-") as tmp_home:
        tmp_path = Path(tmp_home)
        env = os.environ.copy()
        env["GAIA_ASSISTANT_HOME"] = tmp_home
        env["GAIA_ASSISTANT_CLI_HINT"] = "gaia"
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
            env.pop(name, None)

        onboard_out = _run_command(
            [
                "onboard",
                "--provider",
                "openai",
                "--api-key",
                "preview-openai-key",
                "--model",
                "gpt-4.1-mini",
                "--yes",
            ],
            env,
        )
        doctor_out = _run_command(["doctor"], env)
        chat_out = _run_command(
            [
                "chat",
                "--response-profile",
                "concise",
                "--secret-store",
                str(tmp_path / "empty-secrets.json"),
            ],
            env,
            stdin_text="Need concise updates\n/exit\n",
        )
        session_id = _extract_id(r"s\d{14}-[0-9a-f]+", chat_out, context="chat")

        chat_trace_json = _run_command(["traces", "--type", "chat_turn", "--last", "1", "--json"], env)
        chat_trace_payload = json.loads(chat_trace_json)
        if not isinstance(chat_trace_payload, list) or not chat_trace_payload:
            raise RuntimeError("chat trace payload is empty")
        last_chat_trace = chat_trace_payload[-1]
        if not isinstance(last_chat_trace, dict):
            raise RuntimeError("chat trace payload has invalid shape")
        trace_id = str(last_chat_trace.get("id", "")).strip()
        if not trace_id:
            raise RuntimeError("chat trace id is missing")

        feedback_out = _run_command(
            [
                "feedback",
                "record",
                "--label",
                "not-helpful",
                "--session-id",
                session_id,
                "--trace-id",
                trace_id,
                "--correction",
                "Need tighter action bullets",
            ],
            env,
        )
        memory_add_out = _run_command(
            [
                "memory",
                "add",
                "--type",
                "user_long",
                "--subject",
                "user:preview",
                "--content",
                "User prefers concise actionable updates.",
                "--summary",
                "concise preference seed",
                "--consent-scope",
                "user",
                "--confidence",
                "0.9",
                "--importance",
                "0.8",
            ],
            env,
        )
        memory_summarize_json = _run_command(
            [
                "memory",
                "summarize",
                "--subject",
                "user:preview",
                "--response-profile",
                "concise",
                "--json",
            ],
            env,
        )
        memory_summarize_payload = json.loads(memory_summarize_json)
        if not isinstance(memory_summarize_payload, dict):
            raise RuntimeError("memory summarize payload has invalid shape")
        summary_memory = memory_summarize_payload.get("summary_memory")
        summary_event = memory_summarize_payload.get("summary_event")
        if not isinstance(summary_memory, dict) or not isinstance(summary_event, dict):
            raise RuntimeError("memory summarize payload is missing summary fields")
        feedback_trace_out = _run_command(["traces", "--type", "feedback_record", "--last", "1"], env)

    return {
        "tmp_home": tmp_home,
        "onboard_out": onboard_out,
        "doctor_out": doctor_out,
        "chat_out": chat_out,
        "chat_trace": last_chat_trace,
        "feedback_out": feedback_out,
        "memory_add_out": memory_add_out,
        "memory_summarize": memory_summarize_payload,
        "feedback_trace_out": feedback_trace_out,
    }


def _build_flow_steps(capture: Dict[str, Any]) -> List[FlowStep]:
    onboard_out = str(capture["onboard_out"])
    doctor_out = str(capture["doctor_out"])
    chat_out = str(capture["chat_out"])
    chat_trace = capture["chat_trace"]
    feedback_out = str(capture["feedback_out"])
    memory_add_out = str(capture["memory_add_out"])
    memory_summary = capture["memory_summarize"]
    feedback_trace_out = str(capture["feedback_trace_out"])
    if not isinstance(chat_trace, dict):
        raise RuntimeError("chat trace record has invalid shape")
    if not isinstance(memory_summary, dict):
        raise RuntimeError("memory summary payload has invalid shape")

    summary_memory = memory_summary.get("summary_memory")
    summary_event = memory_summary.get("summary_event")
    if not isinstance(summary_memory, dict) or not isinstance(summary_event, dict):
        raise RuntimeError("memory summarize output is missing summary fields")

    session_id = _extract_id(r"s\d{14}-[0-9a-f]+", chat_out, context="chat output")
    trace_id = _extract_id(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", str(chat_trace), context="chat trace")
    feedback_id = _extract_id(r"fb\d{14}-[0-9a-f]+", feedback_out, context="feedback output")
    seed_memory_id = _extract_id(r"m\d{14}-[0-9a-f]+", memory_add_out, context="memory add output")
    summary_memory_id = str(summary_memory.get("memory_id", "")).strip()
    summary_event_id = str(summary_event.get("summary_event_id", "")).strip()
    summary_selected_count = int(summary_event.get("selected_source_count", 0))
    summary_profile = str(summary_event.get("response_profile", "")).strip() or "concise"
    chat_status = str(chat_trace.get("status", "")).strip() or "ok"
    chat_action = str(chat_trace.get("action_type", "")).strip() or "chat_turn"

    replacements = {
        str(capture["tmp_home"]): "<gaia-home>",
        str(REPO_ROOT): "<repo-root>",
        "preview-openai-key": "<preview-openai-key>",
        session_id: "<session-id>",
        trace_id: "<trace-id>",
        feedback_id: "<feedback-id>",
        seed_memory_id: "<seed-memory-id>",
        summary_memory_id: "<summary-memory-id>",
        summary_event_id: "<summary-event-id>",
    }

    feedback_trace_line = feedback_trace_out.splitlines()[0].strip() if feedback_trace_out.splitlines() else "feedback_record trace unavailable"

    steps = [
        FlowStep(
            command="gaia onboard --provider openai --api-key preview-openai-key --model gpt-4.1-mini --yes",
            outputs=[
                _find_line(onboard_out, "[ok] selected provider:", context="onboard"),
                _find_line(onboard_out, "[ok] reasoning provider configured", context="onboard"),
                _find_line(onboard_out, "model:", context="onboard"),
            ],
        ),
        FlowStep(
            command="gaia doctor",
            outputs=[
                _find_line(doctor_out, "[ok] required command found: python3", context="doctor"),
                _find_line(doctor_out, "[ok] reasoning config:", context="doctor"),
                _find_line(doctor_out, "Doctor finished with no blocking problems.", context="doctor"),
            ],
        ),
        FlowStep(
            command="gaia chat --response-profile concise",
            outputs=[
                f"Started session: {session_id}",
                _find_line(chat_out, "Response profile:", context="chat"),
                _extract_chat_reply(chat_out),
            ],
        ),
        FlowStep(
            command="gaia traces --type chat_turn --last 1 --json",
            outputs=[
                f"trace_id={trace_id} action={chat_action} status={chat_status} profile=concise",
            ],
        ),
        FlowStep(
            command="gaia feedback record --label not-helpful --session-id <session-id> --trace-id <trace-id> --correction \"Need tighter action bullets\"",
            outputs=[
                feedback_out.strip(),
            ],
        ),
        FlowStep(
            command="gaia memory add --type user_long --subject user:preview --content \"User prefers concise actionable updates.\" --summary \"concise preference seed\" --consent-scope user --confidence 0.9 --importance 0.8",
            outputs=[
                memory_add_out.strip(),
            ],
        ),
        FlowStep(
            command="gaia memory summarize --subject user:preview --response-profile concise --json",
            outputs=[
                f"summary_memory_id={summary_memory_id} selected_source_count={summary_selected_count}",
                f"response_profile={summary_profile} summary_event_id={summary_event_id}",
            ],
        ),
        FlowStep(
            command="gaia traces --type feedback_record --last 1",
            outputs=[
                feedback_trace_line,
            ],
        ),
    ]

    normalized_steps: List[FlowStep] = []
    for step in steps:
        normalized_command = _normalize_text(step.command, replacements)
        normalized_outputs = [_normalize_text(line, replacements) for line in step.outputs]
        normalized_steps.append(FlowStep(command=normalized_command, outputs=normalized_outputs))
    return normalized_steps


def _line_kind(text: str) -> str:
    if text.startswith("$ "):
        return "cmd"
    if text.startswith("[ok]"):
        return "ok"
    if text.startswith("[warn]"):
        return "warn"
    if text.startswith("[missing]"):
        return "warn"
    if text.startswith("[info]"):
        return "meta"
    return "text"


def _flatten_lines(steps: Sequence[FlowStep]) -> List[str]:
    lines: List[str] = []
    for step in steps:
        lines.append(f"$ {step.command}")
        lines.extend(step.outputs)
    return lines


def _render_terminal_svg(steps: Sequence[FlowStep]) -> str:
    flow_lines = _flatten_lines(steps)
    y = 122
    rendered: List[str] = []
    for line in flow_lines:
        kind = _line_kind(line)
        rendered.append(f'  <text x="64" y="{y}" class="{kind}">{html.escape(line)}</text>')
        y += 25

    box_y = y + 16
    coverage = [
        "- onboarding flow with provider setup (`gaia onboard`)",
        "- concise profile chat behavior (`gaia chat --response-profile concise`)",
        "- trace visibility for linked feedback (`gaia traces` + trace id linkage)",
        "- deterministic feedback capture (`gaia feedback record`)",
        "- memory summarize with traceable summary metadata (`gaia memory summarize`)",
    ]

    for idx, line in enumerate(coverage):
        rendered.append(
            f'  <text x="88" y="{box_y + 64 + (idx * 26)}" class="meta">{html.escape(line)}</text>'
        )

    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="980" viewBox="0 0 1280 980" fill="none">',
        "  <defs>",
        "    <style>",
        "      .frame { fill: #0B1220; }",
        "      .panel { fill: #101A2E; stroke: #2A3C64; }",
        "      .titlebar { fill: #172440; }",
        "      .title { fill: #D8E5FF; font-size: 20px; font-family: monospace; }",
        "      .cmd { fill: #8CE99A; font-size: 16px; font-family: monospace; }",
        "      .ok { fill: #8CE99A; font-size: 16px; font-family: monospace; }",
        "      .warn { fill: #F7D070; font-size: 16px; font-family: monospace; }",
        "      .text { fill: #CBD9F8; font-size: 16px; font-family: monospace; }",
        "      .meta { fill: #9AB6E9; font-size: 16px; font-family: monospace; }",
        "    </style>",
        "  </defs>",
        "",
        '  <rect class="frame" width="1280" height="980" rx="20"/>',
        '  <rect class="panel" x="34" y="28" width="1212" height="924" rx="16"/>',
        '  <rect class="titlebar" x="34" y="28" width="1212" height="54" rx="16"/>',
        '  <circle cx="72" cy="55" r="8" fill="#FF5F57"/>',
        '  <circle cx="100" cy="55" r="8" fill="#FEBC2E"/>',
        '  <circle cx="128" cy="55" r="8" fill="#28C840"/>',
        '  <text x="160" y="62" class="title">gaia assistant live preview (generated from executable command traces)</text>',
        "",
        *rendered[: len(flow_lines)],
        f'  <rect x="64" y="{box_y}" width="1150" height="188" rx="12" fill="#0D1628" stroke="#33507E"/>',
        f'  <text x="88" y="{box_y + 36}" class="title">Capability coverage shown</text>',
        *rendered[len(flow_lines) :],
        "</svg>",
    ]
    return "\n".join(svg_lines) + "\n"


def _render_animated_svg(steps: Sequence[FlowStep]) -> str:
    flow_lines = _flatten_lines(steps)
    duration = 22.0
    rendered: List[str] = []
    css_delays: List[str] = []
    y = 122

    for index, line in enumerate(flow_lines, start=1):
        delay = 0.2 + (index - 1) * 0.45
        css_delays.append(f"      .l{index} {{ animation-delay: {delay:.2f}s; }}")
        kind = _line_kind(line)
        rendered.append(
            f'  <text x="64" y="{y}" class="{kind} line l{index}">{html.escape(line)}</text>'
        )
        y += 25

    coverage_start = len(flow_lines) + 1
    coverage_lines = [
        "capabilities: onboarding, response-profile chat, feedback linkage, memory summarize, trace visibility",
        "source-of-truth transcript: assistant/assets/gaia-assistant-live-preview-transcript.md",
    ]
    box_y = y + 16
    for offset, line in enumerate(coverage_lines):
        idx = coverage_start + offset
        delay = 0.2 + (idx - 1) * 0.45
        css_delays.append(f"      .l{idx} {{ animation-delay: {delay:.2f}s; }}")
        rendered.append(
            f'  <text x="88" y="{box_y + 72 + (offset * 26)}" class="meta line l{idx}">{html.escape(line)}</text>'
        )

    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="980" viewBox="0 0 1280 980" fill="none">',
        "  <defs>",
        "    <style>",
        "      .frame { fill: #0B1220; }",
        "      .panel { fill: #101A2E; stroke: #2A3C64; }",
        "      .titlebar { fill: #172440; }",
        "      .title { fill: #D8E5FF; font-family: monospace; font-size: 20px; }",
        "      .cmd { fill: #8CE99A; font-family: monospace; font-size: 16px; }",
        "      .ok { fill: #8CE99A; font-family: monospace; font-size: 16px; }",
        "      .warn { fill: #F7D070; font-family: monospace; font-size: 16px; }",
        "      .text { fill: #CBD9F8; font-family: monospace; font-size: 16px; }",
        "      .meta { fill: #9AB6E9; font-family: monospace; font-size: 16px; }",
        "      .line {",
        "        opacity: 0;",
        f"        animation: reveal {duration:.2f}s linear infinite;",
        "      }",
        *css_delays,
        "      .cursor {",
        "        animation: blink 1s steps(1, end) infinite;",
        "      }",
        "      .bar-bg { fill: #294170; }",
        "      .bar-fill {",
        "        fill: #8CE99A;",
        "        transform-origin: 0 0;",
        f"        animation: fillbar {duration:.2f}s linear infinite;",
        "      }",
        "      @keyframes reveal {",
        "        0% { opacity: 0; }",
        "        3% { opacity: 1; }",
        "        100% { opacity: 1; }",
        "      }",
        "      @keyframes blink {",
        "        0% { opacity: 0; }",
        "        50% { opacity: 1; }",
        "        100% { opacity: 0; }",
        "      }",
        "      @keyframes fillbar {",
        "        0% { transform: scaleX(0.03); }",
        "        30% { transform: scaleX(0.30); }",
        "        60% { transform: scaleX(0.64); }",
        "        100% { transform: scaleX(1); }",
        "      }",
        "    </style>",
        "  </defs>",
        "",
        '  <rect class="frame" width="1280" height="980" rx="20"/>',
        '  <rect class="panel" x="34" y="28" width="1212" height="924" rx="16"/>',
        '  <rect class="titlebar" x="34" y="28" width="1212" height="54" rx="16"/>',
        '  <circle cx="72" cy="55" r="8" fill="#FF5F57"/>',
        '  <circle cx="100" cy="55" r="8" fill="#FEBC2E"/>',
        '  <circle cx="128" cy="55" r="8" fill="#28C840"/>',
        '  <text x="160" y="62" class="title">gaia assistant animated walkthrough (generated from executable traces)</text>',
        "",
        *rendered[: len(flow_lines)],
        f'  <rect x="64" y="{box_y}" width="1150" height="96" rx="12" fill="#0D1628" stroke="#33507E"/>',
        *rendered[len(flow_lines) :],
        f'  <rect x="64" y="{box_y + 118}" width="1150" height="16" rx="8" class="bar-bg"/>',
        f'  <rect x="64" y="{box_y + 118}" width="1150" height="16" rx="8" class="bar-fill"/>',
        f'  <text x="64" y="{box_y + 170}" class="cmd line l{len(flow_lines)}">$ gaia traces --last 5<tspan class="cursor">_</tspan></text>',
        "</svg>",
    ]
    return "\n".join(svg_lines) + "\n"


def _render_transcript(steps: Sequence[FlowStep]) -> str:
    lines: List[str] = [
        "# Gaia Assistant Live Preview Transcript",
        "",
        "This file is generated by `python3 tools/generate-live-preview-assets.py`.",
        "The command flow is executable end-to-end; dynamic ids, timestamps, and temp",
        "paths are normalized for stable diffs.",
        "",
        "## Command Flow",
        "",
        "```text",
    ]

    for step in steps:
        lines.append(f"$ {step.command}")
        for output in step.outputs:
            lines.append(output)
        lines.append("")

    lines.extend(
        [
            "```",
            "",
            "## Deterministic Capture Notes",
            "",
            "- `GAIA_ASSISTANT_HOME` is set to an isolated temporary directory for each run.",
            "- Chat capture uses `--secret-store <gaia-home>/empty-secrets.json` to force deterministic local mock replies.",
            "- One seed memory entry is written before `gaia memory summarize` so summary output has traceable source records.",
            "",
            "## Regenerate",
            "",
            "```bash",
            "python3 tools/generate-live-preview-assets.py",
            "python3 tools/generate-live-preview-assets.py --check",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _write_or_check(path: Path, content: str, *, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if check:
        if current != content:
            rel = path.relative_to(REPO_ROOT)
            print(f"live preview drift detected: {rel}", file=sys.stderr)
            return False
        rel = path.relative_to(REPO_ROOT)
        print(f"check passed: {rel}")
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    rel = path.relative_to(REPO_ROOT)
    print(f"wrote: {rel}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/check Gaia live preview assets from executable traces")
    parser.add_argument("--terminal-svg", default=str(DEFAULT_TERMINAL_SVG), help="Output path for terminal snapshot SVG")
    parser.add_argument("--animated-svg", default=str(DEFAULT_ANIMATED_SVG), help="Output path for animated walkthrough SVG")
    parser.add_argument("--transcript", default=str(DEFAULT_TRANSCRIPT), help="Output path for normalized command transcript")
    parser.add_argument("--check", action="store_true", help="Fail if generated assets differ from committed files")
    args = parser.parse_args()

    try:
        capture = _capture_preview_flow()
        steps = _build_flow_steps(capture)
        terminal_svg = _render_terminal_svg(steps)
        animated_svg = _render_animated_svg(steps)
        transcript_md = _render_transcript(steps)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    terminal_path = Path(args.terminal_svg).expanduser()
    animated_path = Path(args.animated_svg).expanduser()
    transcript_path = Path(args.transcript).expanduser()

    ok = True
    ok = _write_or_check(terminal_path, terminal_svg, check=args.check) and ok
    ok = _write_or_check(animated_path, animated_svg, check=args.check) and ok
    ok = _write_or_check(transcript_path, transcript_md, check=args.check) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
