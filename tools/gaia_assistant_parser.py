#!/usr/bin/env python3
"""Gaia assistant CLI parser construction helpers.

Extracted from tools/gaia-assistant.py to keep command registration
modular while preserving runtime behavior.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict


def build_parser(ctx: Dict[str, Any]) -> argparse.ArgumentParser:
    AUTOPILOT_PROFILES = ctx["AUTOPILOT_PROFILES"]
    DEFAULT_CONFIG_PATH = ctx["DEFAULT_CONFIG_PATH"]
    DEFAULT_STATE_DIR = ctx["DEFAULT_STATE_DIR"]
    FEEDBACK_LIST_DEFAULT_LIMIT = ctx["FEEDBACK_LIST_DEFAULT_LIMIT"]
    FEEDBACK_LIST_MAX_LIMIT = ctx["FEEDBACK_LIST_MAX_LIMIT"]
    MEMORY_CONSENT_SCOPE_CHOICES = ctx["MEMORY_CONSENT_SCOPE_CHOICES"]
    MEMORY_LIST_DEFAULT_LIMIT = ctx["MEMORY_LIST_DEFAULT_LIMIT"]
    MEMORY_LIST_MAX_LIMIT = ctx["MEMORY_LIST_MAX_LIMIT"]
    MEMORY_TYPE_CHOICES = ctx["MEMORY_TYPE_CHOICES"]
    AUTH_PROVIDER_CHOICES = ctx["AUTH_PROVIDER_CHOICES"]
    AUTH_SOURCE_CHOICES = ctx["AUTH_SOURCE_CHOICES"]
    ONBOARD_PROVIDER_CHOICES = ctx["ONBOARD_PROVIDER_CHOICES"]
    PERMISSION_LEVEL_CHOICES = ctx["PERMISSION_LEVEL_CHOICES"]
    POLICY_DECISION_CHOICES = ctx["POLICY_DECISION_CHOICES"]
    POLICY_SCOPE_CHOICES = ctx["POLICY_SCOPE_CHOICES"]
    POLICY_SOURCE_CHOICES = ctx["POLICY_SOURCE_CHOICES"]
    POLICY_TOOL_CHOICES = ctx["POLICY_TOOL_CHOICES"]
    PROFILE_KEY_MAP = ctx["PROFILE_KEY_MAP"]
    REMINDER_DEFAULT_CADENCE_MINUTES = ctx["REMINDER_DEFAULT_CADENCE_MINUTES"]
    REMINDER_DEFAULT_WINDOW_MINUTES = ctx["REMINDER_DEFAULT_WINDOW_MINUTES"]
    RESPONSE_PROFILE_CHOICES = ctx["RESPONSE_PROFILE_CHOICES"]
    SANDBOX_PROFILE_CHOICES = ctx["SANDBOX_PROFILE_CHOICES"]
    SIGNALS_LIST_DEFAULT_LIMIT = ctx["SIGNALS_LIST_DEFAULT_LIMIT"]
    SIGNALS_LIST_MAX_LIMIT = ctx["SIGNALS_LIST_MAX_LIMIT"]
    SIGNALS_TYPE_CHOICES = ctx["SIGNALS_TYPE_CHOICES"]
    SCHEDULE_DEFAULT_WINDOW_MINUTES = ctx["SCHEDULE_DEFAULT_WINDOW_MINUTES"]
    SCHEDULE_MUTABLE_STATUS_CHOICES = ctx["SCHEDULE_MUTABLE_STATUS_CHOICES"]
    SCHEDULE_STATUS_CHOICES = ctx["SCHEDULE_STATUS_CHOICES"]
    SKILL_SOURCE_CHOICES = ctx["SKILL_SOURCE_CHOICES"]
    cmd_auth_link = ctx["cmd_auth_link"]
    cmd_auth_login = ctx["cmd_auth_login"]
    cmd_auth_status = ctx["cmd_auth_status"]
    cmd_autopilot_run = ctx["cmd_autopilot_run"]
    cmd_capability_list = ctx["cmd_capability_list"]
    cmd_capability_set = ctx["cmd_capability_set"]
    cmd_chat = ctx["cmd_chat"]
    cmd_config_get = ctx["cmd_config_get"]
    cmd_config_set = ctx["cmd_config_set"]
    cmd_doctor = ctx["cmd_doctor"]
    cmd_feedback_list = ctx["cmd_feedback_list"]
    cmd_feedback_record = ctx["cmd_feedback_record"]
    cmd_init = ctx["cmd_init"]
    cmd_memory_add = ctx["cmd_memory_add"]
    cmd_memory_delete = ctx["cmd_memory_delete"]
    cmd_memory_export = ctx["cmd_memory_export"]
    cmd_memory_get = ctx["cmd_memory_get"]
    cmd_memory_list = ctx["cmd_memory_list"]
    cmd_memory_retrieve = ctx["cmd_memory_retrieve"]
    cmd_memory_summarize = ctx["cmd_memory_summarize"]
    cmd_memory_update = ctx["cmd_memory_update"]
    cmd_models_list = ctx["cmd_models_list"]
    cmd_note = ctx["cmd_note"]
    cmd_onboard = ctx["cmd_onboard"]
    cmd_plan = ctx["cmd_plan"]
    cmd_plans = ctx["cmd_plans"]
    cmd_policy_allowlist_clear = ctx["cmd_policy_allowlist_clear"]
    cmd_policy_allowlist_list = ctx["cmd_policy_allowlist_list"]
    cmd_policy_allowlist_set = ctx["cmd_policy_allowlist_set"]
    cmd_policy_evaluate = ctx["cmd_policy_evaluate"]
    cmd_reminder_create = ctx["cmd_reminder_create"]
    cmd_reminder_dismiss = ctx["cmd_reminder_dismiss"]
    cmd_reminder_list = ctx["cmd_reminder_list"]
    cmd_reminder_pause = ctx["cmd_reminder_pause"]
    cmd_reminder_resume = ctx["cmd_reminder_resume"]
    cmd_reminder_snooze = ctx["cmd_reminder_snooze"]
    cmd_reminder_update = ctx["cmd_reminder_update"]
    cmd_run = ctx["cmd_run"]
    cmd_sandbox_profiles = ctx["cmd_sandbox_profiles"]
    cmd_sandbox_run = ctx["cmd_sandbox_run"]
    cmd_schedule_cancel = ctx["cmd_schedule_cancel"]
    cmd_schedule_create = ctx["cmd_schedule_create"]
    cmd_schedule_list = ctx["cmd_schedule_list"]
    cmd_schedule_run_due = ctx["cmd_schedule_run_due"]
    cmd_schedule_update = ctx["cmd_schedule_update"]
    cmd_signals_clear = ctx["cmd_signals_clear"]
    cmd_signals_export = ctx["cmd_signals_export"]
    cmd_signals_extract = ctx["cmd_signals_extract"]
    cmd_signals_list = ctx["cmd_signals_list"]
    cmd_signals_triage = ctx["cmd_signals_triage"]
    cmd_skills_inspect = ctx["cmd_skills_inspect"]
    cmd_skills_list = ctx["cmd_skills_list"]
    cmd_skills_validate = ctx["cmd_skills_validate"]
    cmd_summaries = ctx["cmd_summaries"]
    cmd_summarize = ctx["cmd_summarize"]
    cmd_tasks = ctx["cmd_tasks"]
    cmd_traces = ctx["cmd_traces"]

    parser = argparse.ArgumentParser(
        description="Gaia standalone personal assistant launcher",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize local Gaia assistant config")
    init.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    init.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Local state directory")
    init.add_argument("--force", action="store_true", help="Overwrite config if it exists")
    init.set_defaults(func=cmd_init)

    onboard = sub.add_parser("onboard", help="Guided provider onboarding (OAuth or API key)")
    onboard.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    onboard.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Local state directory")
    onboard.add_argument(
        "--gaia-auth-store",
        default=None,
        help="Path to Gaia auth-profiles.json (optional override)",
    )
    onboard.add_argument(
        "--codex-auth-path",
        default=None,
        help="Path to Codex auth.json (optional override)",
    )
    onboard.add_argument(
        "--provider",
        choices=list(ONBOARD_PROVIDER_CHOICES),
        default=None,
        help="Provider to onboard (interactive if omitted)",
    )
    onboard.add_argument(
        "--api-key",
        default=None,
        help="API key for API-key providers (openrouter/openai/anthropic)",
    )
    onboard.add_argument(
        "--model",
        default=None,
        help="Reasoning model to set during onboarding",
    )
    onboard.add_argument(
        "--secret-store",
        default=None,
        help="Path to local secrets.json store (optional override)",
    )
    onboard.add_argument(
        "--no-store-api-key",
        action="store_true",
        help="Do not store API key in local secret store",
    )
    onboard.add_argument("--yes", action="store_true", help="Skip onboarding confirmations")
    onboard.set_defaults(func=cmd_onboard)

    models = sub.add_parser("models", help="Inspect provider model catalogs")
    models_sub = models.add_subparsers(dest="models_command", required=True)

    models_list = models_sub.add_parser("list", help="List provider model options with source provenance")
    models_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    models_list.add_argument(
        "--secret-store",
        default=None,
        help="Path to local secrets.json store (optional override)",
    )
    models_list.add_argument(
        "--provider",
        choices=list(ONBOARD_PROVIDER_CHOICES),
        default=None,
        help="Provider to inspect (all providers when omitted)",
    )
    models_list.add_argument(
        "--api-key",
        default=None,
        help="Optional API key override (requires --provider)",
    )
    models_list.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON output")
    models_list.set_defaults(func=cmd_models_list)

    doctor = sub.add_parser("doctor", help="Validate local environment and auth readiness")
    doctor.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    doctor.set_defaults(func=cmd_doctor)

    config = sub.add_parser("config", help="Read or write local assistant preferences")
    config_sub = config.add_subparsers(dest="config_command", required=True)

    config_set = config_sub.add_parser("set", help="Set a preference value")
    config_set.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    config_set.add_argument("key", choices=sorted(PROFILE_KEY_MAP.keys()), help="Preference key")
    config_set.add_argument("value", help="Preference value")
    config_set.set_defaults(func=cmd_config_set)

    config_get = config_sub.add_parser("get", help="Get a preference value")
    config_get.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    config_get.add_argument("key", choices=sorted(PROFILE_KEY_MAP.keys()), help="Preference key")
    config_get.set_defaults(func=cmd_config_get)

    capability = sub.add_parser("capability", help="Inspect or override capability permissions")
    capability_sub = capability.add_subparsers(dest="capability_command", required=True)

    capability_list = capability_sub.add_parser("list", help="List effective capability levels")
    capability_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    capability_list.set_defaults(func=cmd_capability_list)

    capability_set = capability_sub.add_parser("set", help="Set local capability override")
    capability_set.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    capability_set.add_argument("capability", help="Capability name (for example: shell_exec)")
    capability_set.add_argument("level", choices=list(PERMISSION_LEVEL_CHOICES), help="Permission level")
    capability_set.set_defaults(func=cmd_capability_set)

    policy = sub.add_parser("policy", help="Evaluate and manage policy decisions")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)

    policy_evaluate = policy_sub.add_parser("evaluate", help="Evaluate one policy decision")
    policy_evaluate.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    policy_evaluate.add_argument("--trace-dir", default=None, help="Trace directory override")
    policy_evaluate.add_argument(
        "--tool",
        choices=list(POLICY_TOOL_CHOICES),
        required=True,
        help="Tool capability to evaluate",
    )
    policy_evaluate.add_argument(
        "--source",
        choices=list(POLICY_SOURCE_CHOICES),
        default="unknown",
        help="Source provenance for policy evaluation",
    )
    policy_evaluate.add_argument(
        "--scope",
        choices=list(POLICY_SCOPE_CHOICES),
        default=None,
        help="User scope override (defaults to config policy.default_scope)",
    )
    policy_evaluate.add_argument("--skill", default=None, help="Optional skill id/name/path context")
    policy_evaluate.add_argument(
        "--skill-source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter when resolving --skill references",
    )
    policy_evaluate.add_argument("--json", dest="as_json", action="store_true", help="Emit full JSON payload")
    policy_evaluate.set_defaults(func=cmd_policy_evaluate)

    policy_allowlist = policy_sub.add_parser("allowlist", help="Manage per-skill policy tool allowlists")
    policy_allowlist_sub = policy_allowlist.add_subparsers(dest="policy_allowlist_command", required=True)

    policy_allowlist_set = policy_allowlist_sub.add_parser("set", help="Set a skill tool allowlist")
    policy_allowlist_set.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    policy_allowlist_set.add_argument("--trace-dir", default=None, help="Trace directory override")
    policy_allowlist_set.add_argument(
        "--skill-source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter when resolving skill references",
    )
    policy_allowlist_set.add_argument("skill", help="Skill id, unique name, or local skill path")
    policy_allowlist_set.add_argument(
        "--tools",
        required=True,
        help="Comma-separated list of allowed tools",
    )
    policy_allowlist_set.set_defaults(func=cmd_policy_allowlist_set)

    policy_allowlist_clear = policy_allowlist_sub.add_parser("clear", help="Clear one skill tool allowlist")
    policy_allowlist_clear.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    policy_allowlist_clear.add_argument("--trace-dir", default=None, help="Trace directory override")
    policy_allowlist_clear.add_argument(
        "--skill-source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter when resolving skill references",
    )
    policy_allowlist_clear.add_argument("skill", help="Skill id, unique name, or local skill path")
    policy_allowlist_clear.set_defaults(func=cmd_policy_allowlist_clear)

    policy_allowlist_list = policy_allowlist_sub.add_parser("list", help="List policy skill allowlists")
    policy_allowlist_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    policy_allowlist_list.add_argument("--trace-dir", default=None, help="Trace directory override")
    policy_allowlist_list.add_argument(
        "--skill-source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter when resolving --skill references",
    )
    policy_allowlist_list.add_argument("--skill", default=None, help="Optional skill id/name/path filter")
    policy_allowlist_list.add_argument("--json", dest="as_json", action="store_true", help="Emit full JSON payload")
    policy_allowlist_list.set_defaults(func=cmd_policy_allowlist_list)

    traces = sub.add_parser("traces", help="Show structured action traces")
    traces.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    traces.add_argument("--trace-dir", default=None, help="Trace directory override")
    traces.add_argument("--last", type=int, default=20, help="Number of recent trace entries to show")
    traces.add_argument("--type", default=None, help="Filter by action type")
    traces.add_argument("--skill-id", default=None, help="Filter by metadata skill_id")
    traces.add_argument(
        "--skill-source",
        choices=[*list(POLICY_SOURCE_CHOICES), "all"],
        default="all",
        help="Filter by metadata skill_source",
    )
    traces.add_argument(
        "--policy-decision",
        choices=list(POLICY_DECISION_CHOICES),
        default=None,
        help="Filter by metadata policy_decision",
    )
    traces.add_argument(
        "--sandbox-profile",
        choices=list(SANDBOX_PROFILE_CHOICES),
        default=None,
        help="Filter by metadata sandbox_profile",
    )
    traces.add_argument("--correlation-id", default=None, help="Filter by metadata correlation_id")
    traces.add_argument("--json", dest="as_json", action="store_true", help="Emit selected trace records as JSON")
    traces.set_defaults(func=cmd_traces)

    chat = sub.add_parser("chat", help="Start an interactive Gaia chat session")
    chat.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    chat.add_argument("--secret-store", default=None, help="Path to local secrets.json store (optional override)")
    chat.add_argument("--session-dir", default=None, help="Session directory override")
    chat.add_argument("--storage-dir", default=None, help="Data storage directory override")
    chat.add_argument("--trace-dir", default=None, help="Trace directory override")
    chat.add_argument("--resume", default=None, help="Session id or 'last'")
    chat.add_argument(
        "--response-profile",
        choices=list(RESPONSE_PROFILE_CHOICES),
        default=None,
        help="Response profile override (auto/concise/balanced/detailed)",
    )
    chat.add_argument("--max-context-turns", type=int, default=None, help="Override max context turns")
    chat.set_defaults(func=cmd_chat)

    note = sub.add_parser("note", help="Capture a note or task")
    note.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    note.add_argument("--storage-dir", default=None, help="Data storage directory override")
    note.add_argument("--trace-dir", default=None, help="Trace directory override")
    note.add_argument("--task", action="store_true", help="Store as task instead of note")
    note.add_argument("text", help="Note/task text")
    note.set_defaults(func=cmd_note)

    tasks = sub.add_parser("tasks", help="List saved tasks")
    tasks.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    tasks.add_argument("--storage-dir", default=None, help="Data storage directory override")
    tasks.add_argument("--trace-dir", default=None, help="Trace directory override")
    tasks.add_argument("--q", default=None, help="Filter tasks by keyword")
    tasks.add_argument("--since", default=None, help="Filter tasks created since YYYY-MM-DD")
    tasks.add_argument("--status", choices=["open", "done", "all"], default="open", help="Filter by task status")
    tasks.set_defaults(func=cmd_tasks)

    feedback = sub.add_parser("feedback", help="Record and review user feedback on assistant responses")
    feedback_sub = feedback.add_subparsers(dest="feedback_command", required=True)

    feedback_record = feedback_sub.add_parser("record", help="Record one feedback event")
    feedback_record.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    feedback_record.add_argument("--storage-dir", default=None, help="Data storage directory override")
    feedback_record.add_argument("--session-dir", default=None, help="Session directory override")
    feedback_record.add_argument("--trace-dir", default=None, help="Trace directory override")
    feedback_record.add_argument("--label", required=True, help="Feedback label (helpful or not-helpful)")
    feedback_record.add_argument("--correction", default="", help="Optional correction note")
    feedback_record.add_argument("--session-id", default=None, help="Session id linkage (supports 'last')")
    feedback_record.add_argument("--trace-id", default=None, help="Trace id linkage")
    feedback_record.add_argument("--json", dest="as_json", action="store_true", help="Emit feedback JSON")
    feedback_record.set_defaults(func=cmd_feedback_record)

    feedback_list = feedback_sub.add_parser("list", help="List feedback records")
    feedback_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    feedback_list.add_argument("--storage-dir", default=None, help="Data storage directory override")
    feedback_list.add_argument("--session-dir", default=None, help="Session directory override")
    feedback_list.add_argument("--trace-dir", default=None, help="Trace directory override")
    feedback_list.add_argument("--label", default=None, help="Filter by label")
    feedback_list.add_argument("--session-id", default=None, help="Filter by session id (supports 'last')")
    feedback_list.add_argument("--trace-id", default=None, help="Filter by trace id")
    feedback_list.add_argument("--with-correction", action="store_true", help="Only include entries with correction text")
    feedback_list.add_argument(
        "--limit",
        type=int,
        default=FEEDBACK_LIST_DEFAULT_LIMIT,
        help=f"Max rows to return (1..{FEEDBACK_LIST_MAX_LIMIT})",
    )
    feedback_list.add_argument("--json", dest="as_json", action="store_true", help="Emit feedback list JSON")
    feedback_list.set_defaults(func=cmd_feedback_list)

    signals = sub.add_parser("signals", help="Derive and inspect privacy-preserving unmet-intent signals")
    signals_sub = signals.add_subparsers(dest="signals_command", required=True)

    signals_extract = signals_sub.add_parser(
        "extract",
        help="Derive unmet-intent signals from local feedback and trace artifacts",
    )
    signals_extract.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    signals_extract.add_argument("--storage-dir", default=None, help="Data storage directory override")
    signals_extract.add_argument("--trace-dir", default=None, help="Trace directory override")
    signals_extract.add_argument("--json", dest="as_json", action="store_true", help="Emit extraction payload JSON")
    signals_extract.set_defaults(func=cmd_signals_extract)

    signals_triage = signals_sub.add_parser(
        "triage",
        help="Classify unmet-intent signals into skill/core/rejected follow-up buckets",
    )
    signals_triage.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    signals_triage.add_argument("--storage-dir", default=None, help="Data storage directory override")
    signals_triage.add_argument("--trace-dir", default=None, help="Trace directory override")
    signals_triage.add_argument(
        "--source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Skill source filter used when matching existing skills",
    )
    signals_triage.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh signal ledger from local artifacts before triage",
    )
    signals_triage.add_argument(
        "--limit",
        type=int,
        default=SIGNALS_LIST_DEFAULT_LIMIT,
        help=f"Max triage rows to print in table output (1-{SIGNALS_LIST_MAX_LIMIT})",
    )
    signals_triage.add_argument("--json", dest="as_json", action="store_true", help="Emit triage payload JSON")
    signals_triage.set_defaults(func=cmd_signals_triage)

    signals_list = signals_sub.add_parser("list", help="List derived unmet-intent signals")
    signals_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    signals_list.add_argument("--storage-dir", default=None, help="Data storage directory override")
    signals_list.add_argument("--trace-dir", default=None, help="Trace directory override")
    signals_list.add_argument(
        "--type",
        dest="signal_type",
        choices=list(SIGNALS_TYPE_CHOICES),
        default=None,
        help="Filter by signal type",
    )
    signals_list.add_argument("--intent-tag", default=None, help="Filter by intent tag substring")
    signals_list.add_argument(
        "--limit",
        type=int,
        default=SIGNALS_LIST_DEFAULT_LIMIT,
        help=f"Max rows to return (1..{SIGNALS_LIST_MAX_LIMIT})",
    )
    signals_list.add_argument("--json", dest="as_json", action="store_true", help="Emit signal list JSON")
    signals_list.set_defaults(func=cmd_signals_list)

    signals_export = signals_sub.add_parser("export", help="Export the local unmet-intent signal ledger")
    signals_export.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    signals_export.add_argument("--storage-dir", default=None, help="Data storage directory override")
    signals_export.add_argument("--trace-dir", default=None, help="Trace directory override")
    signals_export.add_argument("--path", default=None, help="Export file path (JSON)")
    signals_export.add_argument("--json", dest="as_json", action="store_true", help="Emit export payload JSON")
    signals_export.set_defaults(func=cmd_signals_export)

    signals_clear = signals_sub.add_parser("clear", help="Clear the local unmet-intent signal ledger")
    signals_clear.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    signals_clear.add_argument("--storage-dir", default=None, help="Data storage directory override")
    signals_clear.add_argument("--trace-dir", default=None, help="Trace directory override")
    signals_clear.set_defaults(func=cmd_signals_clear)

    memory = sub.add_parser("memory", help="Manage structured long-term memory records")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)

    memory_add = memory_sub.add_parser("add", help="Create a memory record")
    memory_add.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_add.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_add.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_add.add_argument(
        "--type",
        dest="memory_type",
        choices=list(MEMORY_TYPE_CHOICES),
        required=True,
        help="Memory type",
    )
    memory_add.add_argument("--memory-id", default=None, help="Optional explicit memory id")
    memory_add.add_argument("--subject", dest="subject_id", required=True, help="Memory subject id")
    memory_add.add_argument("--content", required=True, help="Memory content text")
    memory_add.add_argument("--summary", default="", help="Optional summary text")
    memory_add.add_argument("--source-trace-id", default="", help="Optional source trace id")
    memory_add.add_argument("--confidence", type=float, default=0.5, help="Confidence score (0-1)")
    memory_add.add_argument("--importance", type=float, default=0.5, help="Importance score (0-1)")
    memory_add.add_argument("--retention-ttl", default="", help="Retention hint (for example: P30D)")
    memory_add.add_argument(
        "--consent-scope",
        choices=list(MEMORY_CONSENT_SCOPE_CHOICES),
        default="session",
        help="Consent scope class",
    )
    memory_add.add_argument("--json", dest="as_json", action="store_true", help="Emit memory record JSON")
    memory_add.set_defaults(func=cmd_memory_add)

    memory_get = memory_sub.add_parser("get", help="Get a memory record by id")
    memory_get.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_get.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_get.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_get.add_argument("--include-deleted", action="store_true", help="Include soft-deleted records")
    memory_get.add_argument("--json", dest="as_json", action="store_true", help="Emit memory record JSON")
    memory_get.add_argument("memory_id", help="Memory record id")
    memory_get.set_defaults(func=cmd_memory_get)

    memory_list = memory_sub.add_parser("list", help="List memory records")
    memory_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_list.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_list.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_list.add_argument("--type", dest="memory_type", choices=list(MEMORY_TYPE_CHOICES), default=None)
    memory_list.add_argument("--subject", dest="subject_id", default=None, help="Filter by subject id")
    memory_list.add_argument("--q", default=None, help="Filter by content/summary keyword")
    memory_list.add_argument("--limit", type=int, default=MEMORY_LIST_DEFAULT_LIMIT, help="Max rows to return")
    memory_list.add_argument("--include-deleted", action="store_true", help="Include soft-deleted records")
    memory_list.add_argument("--json", dest="as_json", action="store_true", help="Emit memory list JSON")
    memory_list.set_defaults(func=cmd_memory_list)

    memory_retrieve = memory_sub.add_parser("retrieve", help="Run deterministic retrieval + ranking pipeline")
    memory_retrieve.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_retrieve.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_retrieve.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_retrieve.add_argument("--type", dest="memory_type", choices=list(MEMORY_TYPE_CHOICES), default=None)
    memory_retrieve.add_argument("--subject", dest="subject_id", default=None, help="Filter by subject id")
    memory_retrieve.add_argument(
        "--candidate-limit",
        type=int,
        default=MEMORY_LIST_MAX_LIMIT,
        help="Maximum candidate rows before ranking",
    )
    memory_retrieve.add_argument("--limit", type=int, default=MEMORY_LIST_DEFAULT_LIMIT, help="Top results to return")
    memory_retrieve.add_argument("--include-deleted", action="store_true", help="Include soft-deleted candidates")
    memory_retrieve.add_argument(
        "--no-semantic-fallback",
        action="store_true",
        help="Disable deterministic semantic fallback stage",
    )
    memory_retrieve.add_argument("--json", dest="as_json", action="store_true", help="Emit retrieval result JSON")
    memory_retrieve.add_argument("--query", required=True, help="Retrieval query")
    memory_retrieve.set_defaults(func=cmd_memory_retrieve)

    memory_summarize = memory_sub.add_parser("summarize", help="Create a compact traceable summary from memory records")
    memory_summarize.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_summarize.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_summarize.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_summarize.add_argument("--type", dest="memory_type", choices=list(MEMORY_TYPE_CHOICES), default=None)
    memory_summarize.add_argument("--subject", dest="subject_id", default=None, help="Filter source subject id")
    memory_summarize.add_argument("--q", default=None, help="Filter source records by content/summary keyword")
    memory_summarize.add_argument("--limit", type=int, default=MEMORY_LIST_MAX_LIMIT, help="Max source rows before profile compaction")
    memory_summarize.add_argument("--include-deleted", action="store_true", help="Include soft-deleted source records")
    memory_summarize.add_argument(
        "--response-profile",
        choices=list(RESPONSE_PROFILE_CHOICES),
        default=None,
        help="Summary profile override (auto/concise/balanced/detailed)",
    )
    memory_summarize.add_argument("--summary-memory-id", default=None, help="Optional explicit summary memory id")
    memory_summarize.add_argument(
        "--summary-type",
        dest="summary_memory_type",
        choices=list(MEMORY_TYPE_CHOICES),
        default="session_short",
        help="Memory class for the generated summary record",
    )
    memory_summarize.add_argument(
        "--summary-subject",
        dest="summary_subject_id",
        default=None,
        help="Subject id for the generated summary record",
    )
    memory_summarize.add_argument(
        "--summary-consent-scope",
        choices=list(MEMORY_CONSENT_SCOPE_CHOICES),
        default=None,
        help="Consent scope override for generated summary record",
    )
    memory_summarize.add_argument("--retention-ttl", default="", help="Retention hint for generated summary record")
    memory_summarize.add_argument("--source-trace-id", default="", help="Optional source trace id for generated summary record")
    memory_summarize.add_argument("--confidence", type=float, default=0.7, help="Generated summary confidence score (0-1)")
    memory_summarize.add_argument("--importance", type=float, default=0.6, help="Generated summary importance score (0-1)")
    memory_summarize.add_argument("--json", dest="as_json", action="store_true", help="Emit summary payload JSON")
    memory_summarize.set_defaults(func=cmd_memory_summarize)

    memory_export = memory_sub.add_parser("export", help="Export memory records with audit evidence")
    memory_export.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_export.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_export.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_export.add_argument("--type", dest="memory_type", choices=list(MEMORY_TYPE_CHOICES), default=None)
    memory_export.add_argument("--subject", dest="subject_id", default=None, help="Filter by subject id")
    memory_export.add_argument("--q", default=None, help="Filter by content/summary keyword")
    memory_export.add_argument("--limit", type=int, default=MEMORY_LIST_MAX_LIMIT, help="Max rows to export")
    memory_export.add_argument("--include-deleted", action="store_true", help="Include soft-deleted records")
    memory_export.add_argument("--path", default=None, help="Export file path (JSON)")
    memory_export.add_argument("--json", dest="as_json", action="store_true", help="Emit export payload JSON")
    memory_export.set_defaults(func=cmd_memory_export)

    memory_update = memory_sub.add_parser("update", help="Update one memory record")
    memory_update.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_update.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_update.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_update.add_argument("--type", dest="memory_type", choices=list(MEMORY_TYPE_CHOICES), default=None)
    memory_update.add_argument("--subject", dest="subject_id", default=None, help="Updated subject id")
    memory_update.add_argument("--content", default=None, help="Updated content text")
    memory_update.add_argument("--summary", default=None, help="Updated summary text")
    memory_update.add_argument("--source-trace-id", default=None, help="Updated source trace id")
    memory_update.add_argument("--confidence", type=float, default=None, help="Updated confidence score (0-1)")
    memory_update.add_argument("--importance", type=float, default=None, help="Updated importance score (0-1)")
    memory_update.add_argument("--retention-ttl", default=None, help="Updated retention hint")
    memory_update.add_argument(
        "--consent-scope",
        choices=list(MEMORY_CONSENT_SCOPE_CHOICES),
        default=None,
        help="Updated consent scope",
    )
    memory_update.add_argument("--json", dest="as_json", action="store_true", help="Emit updated memory JSON")
    memory_update.add_argument("memory_id", help="Memory record id")
    memory_update.set_defaults(func=cmd_memory_update)

    memory_delete = memory_sub.add_parser("delete", help="Soft-delete one memory record")
    memory_delete.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    memory_delete.add_argument("--storage-dir", default=None, help="Data storage directory override")
    memory_delete.add_argument("--trace-dir", default=None, help="Trace directory override")
    memory_delete.add_argument("memory_id", help="Memory record id")
    memory_delete.set_defaults(func=cmd_memory_delete)

    summarize = sub.add_parser("summarize", help="Fetch and summarize one or more URLs")
    summarize.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    summarize.add_argument("--storage-dir", default=None, help="Data storage directory override")
    summarize.add_argument("--trace-dir", default=None, help="Trace directory override")
    summarize.add_argument("urls", nargs="+", help="One or more URLs to summarize")
    summarize.set_defaults(func=cmd_summarize)

    summaries = sub.add_parser("summaries", help="List saved URL summaries")
    summaries.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    summaries.add_argument("--storage-dir", default=None, help="Data storage directory override")
    summaries.add_argument("--trace-dir", default=None, help="Trace directory override")
    summaries.add_argument("--last", type=int, default=20, help="Number of entries to show")
    summaries.set_defaults(func=cmd_summaries)

    plan = sub.add_parser("plan", help="Generate or refine an actionable plan from a goal")
    plan.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    plan.add_argument("--storage-dir", default=None, help="Data storage directory override")
    plan.add_argument("--trace-dir", default=None, help="Trace directory override")
    plan.add_argument("--edit", default=None, help="Existing plan id to refine")
    plan.add_argument("--update", default=None, help="Refinement instructions for --edit")
    plan.add_argument("goal", nargs="?", help="Goal description")
    plan.set_defaults(func=cmd_plan)

    plans = sub.add_parser("plans", help="List saved plans")
    plans.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    plans.add_argument("--storage-dir", default=None, help="Data storage directory override")
    plans.add_argument("--trace-dir", default=None, help="Trace directory override")
    plans.add_argument("--last", type=int, default=20, help="Number of entries to show")
    plans.set_defaults(func=cmd_plans)

    skills = sub.add_parser("skills", help="Discover, inspect, and validate skill entrypoints")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)

    skills_list = skills_sub.add_parser("list", help="List discovered skills")
    skills_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    skills_list.add_argument("--trace-dir", default=None, help="Trace directory override")
    skills_list.add_argument(
        "--source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter for skill discovery",
    )
    skills_list.add_argument("--json", dest="as_json", action="store_true", help="Emit full JSON payload")
    skills_list.set_defaults(func=cmd_skills_list)

    skills_inspect = skills_sub.add_parser("inspect", help="Inspect one skill contract")
    skills_inspect.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    skills_inspect.add_argument("--trace-dir", default=None, help="Trace directory override")
    skills_inspect.add_argument(
        "--source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter for skill lookup",
    )
    skills_inspect.add_argument("skill_id", help="Qualified skill id or unique skill name")
    skills_inspect.set_defaults(func=cmd_skills_inspect)

    skills_validate = skills_sub.add_parser(
        "validate",
        help="Validate skill structure, static risk patterns, and policy compatibility",
    )
    skills_validate.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    skills_validate.add_argument("--trace-dir", default=None, help="Trace directory override")
    skills_validate.add_argument(
        "--source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter when resolving skill id/name targets",
    )
    skills_validate.add_argument(
        "--report-path",
        default=None,
        help="Optional validation report output path (JSON)",
    )
    skills_validate.add_argument(
        "--require-sandbox",
        action="store_true",
        help="Treat missing sandbox contract integration as a blocking finding",
    )
    skills_validate.add_argument("--json", dest="as_json", action="store_true", help="Emit full JSON report")
    skills_validate.add_argument(
        "target",
        help="Skill id, unique skill name, or local path to skill directory/SKILL.md",
    )
    skills_validate.set_defaults(func=cmd_skills_validate)

    sandbox = sub.add_parser("sandbox", help="Run commands with sandbox profiles and escalation controls")
    sandbox_sub = sandbox.add_subparsers(dest="sandbox_command", required=True)

    sandbox_profiles = sandbox_sub.add_parser("profiles", help="Show sandbox profile contract and defaults")
    sandbox_profiles.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    sandbox_profiles.add_argument("--trace-dir", default=None, help="Trace directory override")
    sandbox_profiles.add_argument("--json", dest="as_json", action="store_true", help="Emit full JSON payload")
    sandbox_profiles.set_defaults(func=cmd_sandbox_profiles)

    sandbox_run = sandbox_sub.add_parser("run", help="Run a command under sandbox profile policy")
    sandbox_run.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    sandbox_run.add_argument("--trace-dir", default=None, help="Trace directory override")
    sandbox_run.add_argument(
        "--profile",
        choices=list(SANDBOX_PROFILE_CHOICES),
        default=None,
        help="Sandbox profile override (defaults to config sandbox.default_profile)",
    )
    sandbox_run.add_argument(
        "--allow-network",
        action="store_true",
        help="Request network mode allow (default is deny)",
    )
    sandbox_run.add_argument(
        "--approve-escalation",
        action="store_true",
        help="Approve required sandbox escalation non-interactively",
    )
    sandbox_run.add_argument(
        "--approve-policy",
        action="store_true",
        help="Approve policy confirmation decisions non-interactively",
    )
    sandbox_run.add_argument(
        "--skill",
        default=None,
        help="Optional skill id/name/path context for policy evaluation",
    )
    sandbox_run.add_argument(
        "--skill-source",
        choices=list(SKILL_SOURCE_CHOICES),
        default="all",
        help="Source filter when resolving --skill references",
    )
    sandbox_run.add_argument(
        "--tool",
        choices=list(POLICY_TOOL_CHOICES),
        default=None,
        help="Assert inferred policy tool for this command",
    )
    sandbox_run.add_argument(
        "--policy-scope",
        choices=list(POLICY_SCOPE_CHOICES),
        default=None,
        help="Policy user scope override (defaults to config policy.default_scope)",
    )
    sandbox_run.add_argument("--dry-run", action="store_true", help="Print sandbox decision without executing")
    sandbox_run.add_argument("--cwd", default=None, help="Working directory override for command execution")
    sandbox_run.add_argument("command", nargs=argparse.REMAINDER, help="Command to run (prefix with --)")
    sandbox_run.set_defaults(func=cmd_sandbox_run)

    schedule = sub.add_parser("schedule", help="Manage recurring and one-shot schedules")
    schedule_sub = schedule.add_subparsers(dest="schedule_command", required=True)

    schedule_create = schedule_sub.add_parser("create", help="Create a schedule")
    schedule_create.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    schedule_create.add_argument("--storage-dir", default=None, help="Data storage directory override")
    schedule_create.add_argument("--trace-dir", default=None, help="Trace directory override")
    schedule_create.add_argument(
        "--profile",
        choices=sorted(AUTOPILOT_PROFILES.keys()),
        required=True,
        help="Autopilot profile to execute when due",
    )
    schedule_create.add_argument("--at", default=None, help="Initial run time in ISO-8601 (UTC recommended)")
    schedule_create.add_argument(
        "--every-minutes",
        type=int,
        default=None,
        help="Recurring cadence in minutes (omit for one-shot schedules)",
    )
    schedule_create.add_argument(
        "--window-minutes",
        type=int,
        default=SCHEDULE_DEFAULT_WINDOW_MINUTES,
        help="Allowed execution lag window in minutes",
    )
    schedule_create.set_defaults(func=cmd_schedule_create)

    schedule_list = schedule_sub.add_parser("list", help="List schedules")
    schedule_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    schedule_list.add_argument("--storage-dir", default=None, help="Data storage directory override")
    schedule_list.add_argument("--trace-dir", default=None, help="Trace directory override")
    schedule_list.add_argument(
        "--status",
        choices=[*list(SCHEDULE_STATUS_CHOICES), "all"],
        default="active",
        help="Filter schedules by status",
    )
    schedule_list.set_defaults(func=cmd_schedule_list)

    schedule_update = schedule_sub.add_parser("update", help="Update schedule configuration")
    schedule_update.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    schedule_update.add_argument("--storage-dir", default=None, help="Data storage directory override")
    schedule_update.add_argument("--trace-dir", default=None, help="Trace directory override")
    schedule_update.add_argument("schedule_id", help="Schedule id")
    schedule_update.add_argument(
        "--profile",
        choices=sorted(AUTOPILOT_PROFILES.keys()),
        default=None,
        help="Autopilot profile to execute",
    )
    schedule_update.add_argument("--at", default=None, help="Next run time in ISO-8601")
    schedule_update.add_argument("--every-minutes", type=int, default=None, help="Recurring cadence in minutes")
    schedule_update.add_argument("--window-minutes", type=int, default=None, help="Execution lag window in minutes")
    schedule_update.add_argument(
        "--status",
        choices=list(SCHEDULE_MUTABLE_STATUS_CHOICES),
        default=None,
        help="Mutable schedule status",
    )
    schedule_update.set_defaults(func=cmd_schedule_update)

    schedule_cancel = schedule_sub.add_parser("cancel", help="Cancel a schedule")
    schedule_cancel.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    schedule_cancel.add_argument("--storage-dir", default=None, help="Data storage directory override")
    schedule_cancel.add_argument("--trace-dir", default=None, help="Trace directory override")
    schedule_cancel.add_argument("schedule_id", help="Schedule id")
    schedule_cancel.set_defaults(func=cmd_schedule_cancel)

    schedule_run_due = schedule_sub.add_parser("run-due", help="Run schedules due at/behind a reference time")
    schedule_run_due.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    schedule_run_due.add_argument("--storage-dir", default=None, help="Data storage directory override")
    schedule_run_due.add_argument("--trace-dir", default=None, help="Trace directory override")
    schedule_run_due.add_argument("--at", default=None, help="Reference time in ISO-8601 (defaults to now UTC)")
    schedule_run_due.add_argument(
        "--window-minutes",
        type=int,
        default=None,
        help="Override schedule window for this run",
    )
    schedule_run_due.set_defaults(func=cmd_schedule_run_due)

    reminder = sub.add_parser("reminder", help="Manage proactive reminders and cadence controls")
    reminder_sub = reminder.add_subparsers(dest="reminder_command", required=True)

    reminder_create = reminder_sub.add_parser("create", help="Create a reminder")
    reminder_create.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    reminder_create.add_argument("--storage-dir", default=None, help="Data storage directory override")
    reminder_create.add_argument("--trace-dir", default=None, help="Trace directory override")
    reminder_create.add_argument("--at", default=None, help="Initial reminder time in ISO-8601 (UTC recommended)")
    reminder_create.add_argument(
        "--every-minutes",
        type=int,
        default=None,
        help=f"Recurring cadence in minutes (default: {REMINDER_DEFAULT_CADENCE_MINUTES})",
    )
    reminder_create.add_argument(
        "--window-minutes",
        type=int,
        default=REMINDER_DEFAULT_WINDOW_MINUTES,
        help="Allowed execution lag window in minutes",
    )
    reminder_create.add_argument("message", help="Reminder message text")
    reminder_create.set_defaults(func=cmd_reminder_create)

    reminder_list = reminder_sub.add_parser("list", help="List reminders")
    reminder_list.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    reminder_list.add_argument("--storage-dir", default=None, help="Data storage directory override")
    reminder_list.add_argument("--trace-dir", default=None, help="Trace directory override")
    reminder_list.add_argument(
        "--status",
        choices=[*list(SCHEDULE_STATUS_CHOICES), "all"],
        default="active",
        help="Filter reminders by status",
    )
    reminder_list.set_defaults(func=cmd_reminder_list)

    reminder_update = reminder_sub.add_parser("update", help="Update reminder configuration")
    reminder_update.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    reminder_update.add_argument("--storage-dir", default=None, help="Data storage directory override")
    reminder_update.add_argument("--trace-dir", default=None, help="Trace directory override")
    reminder_update.add_argument("reminder_id", help="Reminder id")
    reminder_update.add_argument("--message", default=None, help="Updated reminder message")
    reminder_update.add_argument("--at", default=None, help="Next reminder time in ISO-8601")
    reminder_update.add_argument("--every-minutes", type=int, default=None, help="Recurring cadence in minutes")
    reminder_update.add_argument("--window-minutes", type=int, default=None, help="Execution lag window in minutes")
    reminder_update.set_defaults(func=cmd_reminder_update)

    reminder_pause = reminder_sub.add_parser("pause", help="Pause an active reminder")
    reminder_pause.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    reminder_pause.add_argument("--storage-dir", default=None, help="Data storage directory override")
    reminder_pause.add_argument("--trace-dir", default=None, help="Trace directory override")
    reminder_pause.add_argument("reminder_id", help="Reminder id")
    reminder_pause.set_defaults(func=cmd_reminder_pause)

    reminder_resume = reminder_sub.add_parser("resume", help="Resume a paused reminder")
    reminder_resume.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    reminder_resume.add_argument("--storage-dir", default=None, help="Data storage directory override")
    reminder_resume.add_argument("--trace-dir", default=None, help="Trace directory override")
    reminder_resume.add_argument("reminder_id", help="Reminder id")
    reminder_resume.add_argument("--at", default=None, help="Resume at a specific ISO-8601 time")
    reminder_resume.set_defaults(func=cmd_reminder_resume)

    reminder_snooze = reminder_sub.add_parser("snooze", help="Snooze a reminder")
    reminder_snooze.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    reminder_snooze.add_argument("--storage-dir", default=None, help="Data storage directory override")
    reminder_snooze.add_argument("--trace-dir", default=None, help="Trace directory override")
    reminder_snooze.add_argument("reminder_id", help="Reminder id")
    snooze_target = reminder_snooze.add_mutually_exclusive_group(required=True)
    snooze_target.add_argument("--minutes", type=int, default=None, help="Snooze duration in minutes from now")
    snooze_target.add_argument("--until", default=None, help="Snooze until ISO-8601 time")
    reminder_snooze.set_defaults(func=cmd_reminder_snooze)

    reminder_dismiss = reminder_sub.add_parser("dismiss", help="Dismiss a reminder")
    reminder_dismiss.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    reminder_dismiss.add_argument("--storage-dir", default=None, help="Data storage directory override")
    reminder_dismiss.add_argument("--trace-dir", default=None, help="Trace directory override")
    reminder_dismiss.add_argument("reminder_id", help="Reminder id")
    reminder_dismiss.set_defaults(func=cmd_reminder_dismiss)

    autopilot = sub.add_parser("autopilot", help="Run scoped autopilot profiles")
    autopilot_sub = autopilot.add_subparsers(dest="autopilot_command", required=True)

    autopilot_run = autopilot_sub.add_parser("run", help="Run an approved autopilot profile")
    autopilot_run.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    autopilot_run.add_argument("--storage-dir", default=None, help="Data storage directory override")
    autopilot_run.add_argument("--trace-dir", default=None, help="Trace directory override")
    autopilot_run.add_argument(
        "--profile",
        choices=sorted(AUTOPILOT_PROFILES.keys()),
        required=True,
        help="Approved autopilot profile name",
    )
    autopilot_run.add_argument("--dry-run", action="store_true", help="Preview steps without executing")
    autopilot_run.add_argument(
        "--force-failure-step",
        default=None,
        help="Force failure at a step id for rollback validation",
    )
    autopilot_run.set_defaults(func=cmd_autopilot_run)

    auth = sub.add_parser("auth", help="Manage OAuth profile linkage for Gaia assistant")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    auth_login = auth_sub.add_parser("login", help="Run web OAuth login and link profile")
    auth_login.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_login.add_argument(
        "--provider",
        choices=list(AUTH_PROVIDER_CHOICES),
        default="openai-codex",
        help="OAuth provider id (default: openai-codex)",
    )
    auth_login.add_argument(
        "--source",
        choices=list(AUTH_SOURCE_CHOICES),
        default="codex-cli",
        help="OAuth source (default: codex-cli)",
    )
    auth_login.add_argument(
        "--gaia-auth-store",
        default=None,
        help="Path to Gaia auth-profiles.json (optional override)",
    )
    auth_login.add_argument(
        "--codex-auth-path",
        default=None,
        help="Path to Codex auth.json (optional override)",
    )
    auth_login.add_argument(
        "--model",
        default=None,
        help="Preferred runtime model to align after OAuth link",
    )
    auth_login.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    auth_login.add_argument("--no-prompt", action="store_true", help="Skip confirmation prompts")
    auth_login.set_defaults(func=cmd_auth_login)

    auth_link = auth_sub.add_parser("link", help="Link an existing profile without logging in")
    auth_link.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_link.add_argument(
        "--provider",
        choices=list(AUTH_PROVIDER_CHOICES),
        default="openai-codex",
        help="OAuth provider id (default: openai-codex)",
    )
    auth_link.add_argument(
        "--source",
        choices=list(AUTH_SOURCE_CHOICES),
        default="codex-cli",
        help="Profile source (default: codex-cli)",
    )
    auth_link.add_argument(
        "--gaia-auth-store",
        default=None,
        help="Path to Gaia auth-profiles.json (optional override)",
    )
    auth_link.add_argument(
        "--codex-auth-path",
        default=None,
        help="Path to Codex auth.json (optional override)",
    )
    auth_link.add_argument("--profile-id", default=None, help="Explicit profile id to link")
    auth_link.set_defaults(func=cmd_auth_link)

    auth_status = auth_sub.add_parser("status", help="Show linked auth profile status")
    auth_status.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Config JSON path")
    auth_status.set_defaults(func=cmd_auth_status)

    run = sub.add_parser("run", help="Run Gaia assistant loop")
    run.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Launcher config JSON path")
    run.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Local state directory for memory files")
    run.add_argument(
        "--secret-store",
        default=None,
        help="Path to local secrets.json store (optional override)",
    )
    run.add_argument("--mode", choices=["single", "continuous"], default="single")
    run.add_argument("--track", choices=["auto", "assistant", "framework"], default="auto")
    run.add_argument(
        "--reasoning-provider",
        choices=["anthropic", "openai", "openrouter"],
        default=None,
        help="Override reasoning provider for this run",
    )
    run.add_argument(
        "--reasoning-model",
        default=None,
        help="Override reasoning model for this run",
    )
    run.add_argument("--dry-run", action="store_true", help="Plan only, do not execute actions")
    run.add_argument("--verbose", action="store_true", help="Verbose logs")
    run.set_defaults(func=cmd_run)

    return parser
