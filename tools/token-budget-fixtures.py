#!/usr/bin/env python3
"""Deterministic token-budget fixture runner for agent-loop budget gating."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_FIXTURES = REPO_ROOT / "assistant" / "token-budget-fixtures.json"


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _parse_datetime(raw: str) -> datetime:
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _load_agent_loop_module() -> Any:
    module_path = SCRIPT_DIR / "agent-loop.py"
    spec = importlib.util.spec_from_file_location("gaia_agent_loop_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic token-budget fixtures")
    parser.add_argument(
        "--fixtures",
        default=str(DEFAULT_FIXTURES),
        help="Path to token budget fixture manifest JSON",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional output path for fixture results JSON",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Return non-zero when expected fixture outcomes do not match",
    )
    args = parser.parse_args()

    fixtures_path = Path(args.fixtures).expanduser().resolve()
    fixtures = _read_json(fixtures_path)
    module = _load_agent_loop_module()

    base_policy = fixtures.get("policy", {})
    if not isinstance(base_policy, dict):
        raise ValueError("fixtures.policy must be an object")
    scenarios = fixtures.get("scenarios", [])
    if not isinstance(scenarios, list):
        raise ValueError("fixtures.scenarios must be a list")

    report: Dict[str, Any] = {
        "schema_version": 1,
        "suite": "gaia-token-budget-fixture-results",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixtures_path": str(fixtures_path),
        "scenario_count": len(scenarios),
        "status": "pass",
        "scenarios": [],
        "errors": [],
    }
    errors: List[str] = []

    for idx, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            errors.append(f"scenario[{idx}] must be an object")
            continue

        scenario_id = str(scenario.get("id", f"scenario-{idx + 1}")).strip() or f"scenario-{idx + 1}"
        track = str(scenario.get("track", "assistant")).strip() or "assistant"
        estimated = int(scenario.get("estimated_cycle_tokens", 0))

        policy_overrides = scenario.get("policy_overrides", {})
        policy_overrides = policy_overrides if isinstance(policy_overrides, dict) else {}
        raw_policy = _deep_merge(base_policy, policy_overrides)
        normalized_policy = module.normalized_budget_policy({"budget": raw_policy})

        state = scenario.get("state", {})
        state = copy.deepcopy(state) if isinstance(state, dict) else {}
        now_raw = scenario.get("now", "2026-02-14T10:00:00+00:00")
        now = _parse_datetime(str(now_raw))

        decision, runtime = module.evaluate_budget_decision(
            budget_policy=normalized_policy,
            state=state,
            active_track=track,
            estimated_cycle_tokens=estimated,
            now=now,
        )

        actual = {
            "decision": decision.get("decision"),
            "enforced": bool(decision.get("enforced", False)),
            "applied_usage": bool(decision.get("applied_usage", False)),
            "applied": decision.get("usage", {}).get("applied", {}),
            "breach_count": len(decision.get("breaches", [])),
            "warning_count": len(decision.get("warnings", [])),
            "window_key": runtime.get("window_key"),
        }

        expected = scenario.get("expected", {})
        expected = expected if isinstance(expected, dict) else {}

        if "decision" in expected and actual["decision"] != expected.get("decision"):
            errors.append(
                f"{scenario_id}: expected decision={expected.get('decision')!r}, "
                f"got {actual['decision']!r}"
            )
        if "enforced" in expected and actual["enforced"] != bool(expected.get("enforced")):
            errors.append(
                f"{scenario_id}: expected enforced={bool(expected.get('enforced'))!r}, "
                f"got {actual['enforced']!r}"
            )
        if "applied_usage" in expected and actual["applied_usage"] != bool(expected.get("applied_usage")):
            errors.append(
                f"{scenario_id}: expected applied_usage={bool(expected.get('applied_usage'))!r}, "
                f"got {actual['applied_usage']!r}"
            )
        if "applied" in expected:
            expected_applied = expected.get("applied", {})
            if expected_applied != actual["applied"]:
                errors.append(
                    f"{scenario_id}: expected applied usage {expected_applied!r}, "
                    f"got {actual['applied']!r}"
                )
        if "breach_count" in expected and int(expected.get("breach_count")) != actual["breach_count"]:
            errors.append(
                f"{scenario_id}: expected breach_count={int(expected.get('breach_count'))}, "
                f"got {actual['breach_count']}"
            )
        if "warning_count" in expected and int(expected.get("warning_count")) != actual["warning_count"]:
            errors.append(
                f"{scenario_id}: expected warning_count={int(expected.get('warning_count'))}, "
                f"got {actual['warning_count']}"
            )

        report["scenarios"].append(
            {
                "id": scenario_id,
                "track": track,
                "estimated_cycle_tokens": estimated,
                "actual": actual,
                "reason": decision.get("reason", ""),
            }
        )

    if errors:
        report["status"] = "fail"
        report["errors"] = errors

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))

    if args.check and errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
