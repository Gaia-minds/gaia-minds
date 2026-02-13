# Gaia Standalone Assistant

This is the standalone Gaia personal assistant runtime path.

It supports the following provider auth patterns:

1. Subscription OAuth flows (for providers that support it in your environment)
2. Direct API key access

Current npm release: `@gaia-minds/assistant-cli@0.2.0`

## Quick Start

```bash
# Install from npm (recommended)
npm install -g @gaia-minds/assistant-cli
gaia onboard
gaia auth status
gaia doctor

# Local development from this repository
npm install
npm run gaia -- onboard
npm run gaia -- auth status
npm run gaia -- doctor

# Single dry-run cycle
npm run gaia -- run --mode single --dry-run

# Deterministic benchmark run
make benchmark

# Deterministic memory retrieval benchmark gate
make memory-benchmark

# Deterministic quality matrix run
make quality-matrix

# Deterministic terminal UAT run
make test-uat

# Autopilot dry-run preview
gaia autopilot run --profile safe-daily --dry-run

# Continuous assistant track
npm run gaia -- run --mode continuous --track assistant

# Optional global command from this clone
npm install -g .
gaia doctor
```

## Provider Onboarding

Run the guided onboarding wizard:

```bash
gaia onboard
```

The wizard lets you choose provider and connection style:

1. `openrouter` -> API key + model selection
2. `openai` -> API key
3. `anthropic` -> API key
4. `openai-codex` -> OAuth via Codex CLI

Direct non-interactive examples:

```bash
# OpenRouter
gaia onboard --provider openrouter --api-key "$OPENROUTER_API_KEY" --model openrouter/auto --yes

# Anthropic
gaia onboard --provider anthropic --api-key "$ANTHROPIC_API_KEY" --yes

# OpenAI API key
gaia onboard --provider openai --api-key "$OPENAI_API_KEY" --model gpt-4.1-mini --yes

# OpenAI Codex OAuth
gaia onboard --provider openai-codex --yes
```

Gaia still supports explicit auth commands if you prefer manual control.
For Codex OAuth:

```bash
npm run gaia -- auth login --source codex-cli --provider openai-codex
npm run gaia -- auth status
```

## Token Safety

- OAuth tokens are stored in Gaia local state:
  `~/.gaia-assistant/auth-profiles.json` (or `$GAIA_ASSISTANT_HOME/auth-profiles.json`)
- API keys can be stored in Gaia local secret store:
  `~/.gaia-assistant/secrets.json` (or `$GAIA_ASSISTANT_HOME/secrets.json`)
- Launcher config stores profile selection metadata in:
  `~/.gaia-assistant/config.json` (or `$GAIA_ASSISTANT_HOME/config.json`)
- Never commit auth stores or local runtime state to git.
- If you want strict separation, keep `GAIA_ASSISTANT_HOME` outside this repo.

## Tracks

The evolution loop runs with two tracks:

1. `assistant` — user-facing personal assistant improvements
2. `framework` — evolution framework and governance improvements

Default scheduling and policy live in `tools/agent-config.yml`.

## Action Traces

Gaia writes structured local traces to:

- `~/.gaia-assistant/traces/actions.jsonl`

Use:

```bash
gaia traces --last 5
gaia traces --type file_read
gaia traces --type policy_decision --policy-decision deny --last 5
gaia traces --skill-id project:gaia-contributor --sandbox-profile read-only --last 10
gaia traces --correlation-id <trace-correlation-id> --json
```

Trace schema fields:

- `id` (UUID)
- `timestamp` (ISO-8601 UTC)
- `action_type` (for example `chat_turn`, `note_capture`, `permission_decision`)
- `input_summary` (redacted summary string)
- `output_summary` (redacted summary string)
- `duration_ms` (float)
- `permission_level` (`safe`, `confirm`, `forbidden`)
- `status` (`ok`, `error`, `blocked`)
- `schema_version` (integer)
- `metadata` (optional object for downstream tooling)

Trace metadata now includes a normalized schema (`trace_schema_version=2`) for
skills/policy/sandbox cross-lane auditability. Key fields:

- `correlation_id` (links related traces from one command flow)
- `skill_id`
- `skill_source`
- `policy_decision`
- `policy_id`
- `sandbox_profile`
- `sandbox_network_mode`
- `sandbox_escalated`
- `sandbox_approved`

Capability policy can be reviewed and overridden locally:

```bash
gaia capability list
gaia capability set send_email confirm
```

## Benchmarking

Benchmark the 20 canonical Phase 1 tasks plus quality-matrix guardrails:

```bash
make benchmark
make memory-benchmark
make quality-matrix
make benchmark-trend
```

- Methodology and update process: `assistant/benchmarking.md`
- Baseline artifact: `assistant/benchmark-baseline.json`
- Memory retrieval benchmark fixture: `assistant/memory-retrieval-fixtures.json`
- Memory retrieval benchmark result: `assistant/memory-retrieval-benchmark-results.json`
- Quality matrix artifact: `assistant/quality-matrix-results.json`
- Trend history: `assistant/benchmark-trend-history.json`
- Trend summary: `assistant/benchmark-trend-summary.md`
- Incident postmortem template: `docs/incidents/postmortem-template.md`

Compatibility matrix baseline (agent-skills parity snapshot):

- Baseline JSON: `assistant/compatibility-matrix-baseline.json`
- Generated matrix: `assistant/compatibility-matrix.md`
- Repro command: `make compatibility-matrix`

## Terminal UAT

Gaia enforces deterministic terminal UAT coverage for feature surfaces.

```bash
make test-uat
make uat-policy
```

- Scenario manifest: `assistant/uat-scenarios.json`
- Feature catalog: `assistant/feature-catalog.json`
- Policy details: `assistant/uat-policy.md`
- Results: `assistant/uat-results.json`
- Failure bundle: `assistant/uat-artifacts/<run-id>/`
- Quality matrix scenario: `quality_matrix_guardrails`

## Autopilot

Autopilot is limited to explicit approved profiles and capability sets.

Run preview first:

```bash
gaia autopilot run --profile safe-daily --dry-run
```

Execute profile:

```bash
gaia autopilot run --profile safe-daily
```

Validate traces:

```bash
gaia traces --type autopilot_run --last 10
```

Failure/rollback validation:

```bash
gaia autopilot run --profile safe-daily --force-failure-step list_open_tasks
```

Structured logs:

- Run log: `~/.gaia-assistant/traces/autopilot-runs.jsonl`
- Incident log: `~/.gaia-assistant/traces/autopilot-incidents.jsonl`

## Scheduler

Scheduler commands provide durable one-shot and recurring execution for approved
autopilot profiles.

```bash
# create recurring schedule
gaia schedule create --profile safe-daily --every-minutes 60

# create one-shot schedule
gaia schedule create --profile safe-daily --at 2026-02-10T09:30:00Z

# inspect + run due jobs
gaia schedule list --status all
gaia schedule run-due

# update/cancel
gaia schedule update <schedule-id> --window-minutes 20
gaia schedule cancel <schedule-id>
```

Scheduler persistence:

- Schedule store: `~/.gaia-assistant/data/schedules.json`
- Run/idempotency log: `~/.gaia-assistant/data/schedule-runs.jsonl`
- Reminder delivery log: `~/.gaia-assistant/data/reminder-events.jsonl`
- Trace events in `actions.jsonl`: `schedule_create`, `schedule_run`,
  `schedule_skip`, `schedule_fail`, `schedule_update`, `schedule_cancel`

## Reminders

Reminder commands add proactive cadence-driven reminders backed by scheduler
state from `P2-A`.

```bash
# create interval reminder (daily default when cadence omitted)
gaia reminder create "Review open tasks" --every-minutes 60

# list reminders and lifecycle controls
gaia reminder list --status all
gaia reminder pause <reminder-id>
gaia reminder resume <reminder-id> --at 2026-02-10T09:30:00Z
gaia reminder snooze <reminder-id> --minutes 30
gaia reminder dismiss <reminder-id>

# update cadence/message
gaia reminder update <reminder-id> --every-minutes 120 --message "Updated reminder text"
```

Reminder lifecycle traces are recorded in `actions.jsonl` with
`reminder_create`, `reminder_run`, `reminder_skip`, `reminder_update`,
`reminder_pause`, `reminder_resume`, `reminder_snooze`, `reminder_dismiss`,
and `reminder_fail`.

## Memory Runtime

Memory commands provide deterministic local SQLite CRUD and retrieval/ranking
flows for structured long-term memory records.

```bash
# add one memory record
gaia memory add \
  --memory-id user_pref_concise \
  --type user_long \
  --subject user:default \
  --content "User prefers concise updates." \
  --summary "concise preference" \
  --consent-scope user \
  --retention-ttl P30D

# retrieve and filter
gaia memory get <memory-id>
gaia memory list --subject user:default --q concise --limit 20
gaia memory retrieve --query "concise updates" --subject user:default --limit 5

# update and soft-delete
gaia memory update <memory-id> --summary "concise style preference" --importance 0.9
gaia memory delete <memory-id>

# run deterministic retrieval benchmark thresholds
make memory-benchmark
```

Memory persistence:

- Local SQLite store: `~/.gaia-assistant/data/memory.db`
- Schema version: `memory_store_schema_version=1` in `memory_meta`
- Record contract: `memory_id`, `memory_type`, `subject_id`, `content`,
  `summary`, `source_trace_id`, `confidence`, `importance`, `retention_ttl`,
  `consent_scope`, timestamps, and soft-delete marker

Retrieval pipeline:

- deterministic stage order: exact -> lexical -> semantic fallback
- optional semantic fallback disable flag: `--no-semantic-fallback`
- ranking components: stage match score + importance + recency decay
- retrieval diagnostics in JSON output: stage, score breakdown, rank

Memory traces:

- `memory_capture`
- `memory_retrieve`
- `memory_update`
- `memory_delete`

## Skills Runtime

Skills runtime commands provide deterministic discovery and inspection of
approved skill entrypoints.

```bash
# list skills from project + local approved roots
gaia skills list

# list only project skills
gaia skills list --source project

# inspect one skill by id (preferred) or unique name
gaia skills inspect project:gaia-contributor
gaia skills inspect gaia-contributor

# validate one skill by id/name/path
gaia skills validate project:gaia-contributor
gaia skills validate ./skills/gaia-contributor

# strict mode for sandbox contract dependency
gaia skills validate project:gaia-contributor --require-sandbox
```

Approved source roots:

- `project`: `<repo>/skills`
- `local`: `~/.gaia-assistant/skills` (or `config.skills.local_dir`)

Contract reference:

- `infrastructure/skill-contract-v1.md`

Skills runtime traces:

- `skills_list`
- `skills_inspect`
- `skills_validate`

Validation report artifacts:

- default report dir: `~/.gaia-assistant/traces/skill-validation-reports/`
- report schema: `gaia.skill-validation.v1`
- blocking severities: `high`, `critical`

## Sandbox

Sandbox commands provide explicit execution profiles and escalation approval
events for shell command execution paths.

```bash
# inspect profile contract
gaia sandbox profiles

# run command in default profile (from config, default read-only)
gaia sandbox run -- echo "hello sandbox"

# run write command in read-only profile with explicit escalation approval
gaia sandbox run --profile read-only --approve-escalation -- sh -lc 'echo test > "$GAIA_ASSISTANT_HOME/sandbox-test.txt"'

# request network mode explicitly (still policy-gated)
gaia sandbox run --profile workspace-write --allow-network --approve-escalation -- curl https://example.com

# run with skill context so policy uses skill source + allowlist gates
gaia sandbox run --skill project:gaia-contributor -- printf "policy-checked\n"

# assert inferred policy tool classification (mismatch blocks execution)
gaia sandbox run --tool file_read -- cat README.md
```

Sandbox artifacts:

- approval events: `~/.gaia-assistant/traces/sandbox-approvals.jsonl`
- action traces: `sandbox_profiles`, `sandbox_approval`, `sandbox_run`
- contract reference: `infrastructure/sandbox-contract-v1.md`

## Policy Engine

Policy commands provide explicit risk/source/scope evaluation and per-skill tool
allowlists.

```bash
# evaluate one policy decision
gaia policy evaluate --tool file_write --source project --scope standard

# inspect the same decision payload as JSON
gaia policy evaluate --tool delete_files --source project --scope standard --json

# set/list/clear per-skill tool allowlists
gaia policy allowlist set project:gaia-contributor --tools file_read,file_write
gaia policy allowlist list --skill project:gaia-contributor
gaia policy allowlist clear project:gaia-contributor
```

Policy traces:

- `policy_decision` (emitted before sandbox command execution)
- `policy_evaluate`
- `policy_allowlist_set`
- `policy_allowlist_clear`
- `policy_allowlist_list`

## Budget Policy

Default budget split:

- User service: `80%`
- Self-improvement: `20%`

Adjust in `tools/agent-config.yml` under `budget`.

## Auth Notes

Expected environment variables for direct API mode:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`

Reasoning provider selection is configured by onboarding in launcher config,
and can be overridden per run:

```bash
# one-off override from Gaia launcher
gaia run --mode single --reasoning-provider openai --reasoning-model gpt-4.1-mini
gaia run --mode single --reasoning-provider openrouter --reasoning-model openrouter/auto

# npm/local clone equivalent
npm run gaia -- run --mode single --reasoning-provider openai --reasoning-model gpt-4.1-mini
npm run gaia -- run --mode single --reasoning-provider openrouter --reasoning-model openrouter/auto
```

OpenRouter quick setup:

```bash
export OPENROUTER_API_KEY="your-openrouter-key"
gaia onboard --provider openrouter
gaia run --mode single --reasoning-provider openrouter --reasoning-model openrouter/auto
```

OpenAI quick setup:

```bash
export OPENAI_API_KEY="your-openai-key"
gaia onboard --provider openai --model gpt-4.1-mini
gaia run --mode single --reasoning-provider openai --reasoning-model gpt-4.1-mini
```

Provider OAuth profile support is exposed through Gaia-native commands:

- `gaia onboard`
- `gaia auth login --source codex-cli --provider openai-codex`
- `npm run gaia -- onboard`
- `npm run gaia -- auth login --source codex-cli --provider openai-codex`

Direct Python fallback (if preferred):
- `python3 tools/gaia-assistant.py onboard`
- `python3 tools/gaia-assistant.py auth login --source codex-cli --provider openai-codex`

The self-evolution loop planner supports Anthropic, OpenAI, and OpenRouter in
non-dry runs. Tier-2 LLM alignment checks currently run only with Anthropic;
when using OpenAI or OpenRouter, Tier-1 deterministic alignment checks still apply.

## Agent Follow-Up

For agents continuing this track, use contributor workflow from:

- `skills/gaia-contributor/SKILL.md`
- `skills/gaia-assistant-builder/SKILL.md`

Recommended handoff protocol:

1. Pull latest main and read this file + `tools/agent-config.yml`.
2. Check open work first:
   - `gh issue list --state open`
   - `gh pr list --state open`
3. Avoid duplication:
   - `rg -n "<topic>" assistant tools infrastructure skills`
4. Prefer small, reviewable PRs for runtime changes.
5. Before pushing, run:
   - `make check-all`
   - `make test-smoke`
   - `make test-uat`
   - `make uat-policy`
   - `python3 -m py_compile tools/gaia-assistant.py tools/agent-loop.py tools/agent-alignment.py`
6. Update `CHANGELOG.md` with meaningful behavior changes.
7. If this is your first PR to Gaia, include Constitutional acknowledgment from
   `skills/gaia-contributor/SKILL.md` in PR description.

## Maintainer Release Flow

`@gaia-minds/assistant-cli` is publish-ready via GitHub Actions.

1. Ensure npm auth is configured in repository settings:
   - preferred: npm Trusted Publisher for this repo/workflow
   - fallback: repository secret `NPM_TOKEN`
2. Bump version in `package.json` and create a tag like `v0.2.0`.
3. Push the version commit and tag.
4. GitHub Action `.github/workflows/npm-publish.yml` validates and publishes.
5. For rehearsal, run workflow manually with `dry_run=true`.
