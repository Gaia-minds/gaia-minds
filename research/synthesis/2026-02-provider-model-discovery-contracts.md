# Provider Model Discovery Contracts (Codex/Claude/OpenAI/Anthropic/OpenRouter)

**Date**: 2026-02-15  
**Agent**: Codex Contributor  
**Category**: Synthesis  
**Scope**: Define a single Gaia contract for provider model discovery across API providers and CLI-linked providers, including source provenance, fallbacks, schema, and implementation guidance for follow-on lanes.

## Summary

Gaia should treat model discovery as a provider contract with explicit source tags.

- `live`: direct provider API catalog fetch succeeded.
- `curated`: maintained Gaia fallback list for provider runtime continuity.
- `static_cli`: model options inferred from CLI docs/help text (not dynamic API catalogs).

Go decision:

- **Go** live catalog integration: OpenAI API, Anthropic API, OpenRouter API.
- **No-go** direct live catalog integration from CLI surfaces: Codex CLI, Claude Code CLI.
- **Go** for Codex/Claude runtime selectors using provider APIs + curated lists.

## Sources

Primary docs and references:

- OpenAI OpenAPI spec (`/models` list operation in `manual_spec` branch): https://raw.githubusercontent.com/openai/openai-openapi/manual_spec/openapi.yaml
- Anthropic Models API (`GET /v1/models`): https://docs.anthropic.com/en/api/models-list
- Anthropic API errors: https://docs.anthropic.com/en/api/errors
- OpenRouter Models API (`GET /api/v1/models`): https://openrouter.ai/docs/api-reference/models/list-available-models
- OpenRouter available-for-user catalog endpoint: https://openrouter.ai/docs/api-reference/models/list-endpoint-for-models-available-for-your-account
- OpenRouter errors and diagnostics: https://openrouter.ai/docs/api-reference/errors-and-debugging
- Claude Code CLI model settings and aliases: https://docs.anthropic.com/en/docs/claude-code/settings
- Claude Code CLI reference (`--model`, `--effort`): https://docs.anthropic.com/en/docs/claude-code/cli-reference
- OpenAI Codex CLI command-line options: https://developers.openai.com/codex/cli#command-line-options

Local command evidence (executed in this lane on 2026-02-15):

- `codex --version` -> `codex-cli 0.101.0`
- `codex --help` exposes `-m, --model <MODEL>`
- `codex models --help` and `codex model --help` both fall back to top-level help (no dedicated model-list subcommand)
- `claude --version` -> `2.1.42 (Claude Code)`
- `claude --help` exposes `--model <model>`, `--effort <level>`, and `--fallback-model <model>`
- `claude models --help` and `claude model --help` both fall back to top-level help (no dedicated model-list subcommand)

## Evidence by Provider

### 1) OpenAI API

What is contractually available:

- `GET /v1/models` returns a machine-readable model list (`data` array with per-model objects).
- Requires bearer API authentication.

Implication for Gaia:

- **Live catalog source is stable and production-appropriate.**
- Filter required because catalog may include non-reasoning models.

Failure modes to expect:

- Authentication/authorization failures (`401`/`403` classes).
- Rate/quota failures (`429`), including insufficient quota.
- Network/timeout/parse failures.

### 2) Anthropic API

What is contractually available:

- `GET /v1/models` returns a machine-readable list.
- Requires `x-api-key` plus `anthropic-version` header.
- Supports pagination parameters (`before_id`, `after_id`, `limit`).

Implication for Gaia:

- **Live catalog source is stable and production-appropriate.**
- Native model IDs can be used directly for runtime selection.

Failure modes to expect:

- Auth/key errors (`401`/`403`).
- Rate limit (`429`) and overload (`529`) scenarios.
- Network/timeout/parse failures.

### 3) OpenRouter API

What is contractually available:

- `GET /api/v1/models` returns machine-readable model metadata, including pricing/context fields.
- OpenRouter also documents a user-scoped available-models endpoint (`/api/v1/models?category=...`) tied to current account/provider preferences.

Implication for Gaia:

- **Live catalog source is stable and production-appropriate.**
- Prefer general list endpoint for baseline; optionally augment with user-scoped availability if Gaia needs “actually routeable now” semantics.

Failure modes to expect:

- Auth/token errors.
- Provider routing/availability differences versus global catalog.
- Network/timeout/parse failures.

### 4) OpenAI Codex CLI

What is contractually available:

- CLI supports explicit model selection (`--model`) and config overrides.
- No documented machine-readable model listing command in local CLI help.

Implication for Gaia:

- **No-go** for direct live model ingestion from Codex CLI surfaces.
- **Go** using OpenAI API live catalog when key is available; otherwise curated Codex list.
- Keep `gpt-5.3-codex` first in curated rank and default selection for Codex-linked flows.

### 5) Claude Code CLI

What is contractually available:

- CLI supports `--model`, `--effort`, `--fallback-model`.
- Documentation provides aliases and model-setting behavior.
- No documented machine-readable model listing command in local CLI help.

Implication for Gaia:

- **No-go** for direct live model ingestion from Claude CLI surfaces.
- **Go** using Anthropic API live catalog when key is available; otherwise curated Claude list with alias support.

## Recommended Normalized Gaia Catalog Schema

Use one schema for all providers, with explicit provenance and compatibility fields.

```json
{
  "provider": "openai-codex",
  "source": "live",
  "source_detail": "live OpenAI API catalog",
  "fetched_at": "2026-02-15T13:45:00Z",
  "refresh_ttl_seconds": 3600,
  "models": [
    {
      "id": "gpt-5.3-codex",
      "provider": "openai",
      "display_name": "gpt-5.3-codex",
      "source": "live",
      "recommended_rank": 1,
      "supports_effort": false,
      "effort_levels": [],
      "aliases": [],
      "capability_tags": ["reasoning", "coding"],
      "context_window_tokens": null,
      "pricing": {
        "prompt_per_million_usd": null,
        "completion_per_million_usd": null
      },
      "availability": {
        "status": "unknown",
        "region": null
      },
      "raw": {}
    }
  ]
}
```

Required fields:

- Catalog: `provider`, `source`, `source_detail`, `fetched_at`, `models`
- Model: `id`, `provider`, `display_name`, `source`, `recommended_rank`, `supports_effort`, `effort_levels`

Optional fields:

- `aliases`, `capability_tags`, `context_window_tokens`, `pricing`, `availability`, `raw`, `refresh_ttl_seconds`

## Decision Rules: Live vs Curated vs Static CLI

1. Provider is API-native (`openai`, `anthropic`, `openrouter`):
   - attempt live fetch when credential is available;
   - on success + non-empty result -> `source=live`.

2. Provider is CLI-linked (`openai-codex`, `claude-code`):
   - do **not** attempt CLI scraping/parsing as a primary catalog mechanism;
   - attempt corresponding API provider fetch (`openai` for Codex, `anthropic` for Claude) if key exists;
   - if unavailable/fails -> curated fallback (`source=curated`), optionally with CLI alias hints (`source=static_cli` metadata only).

3. Fallback trigger conditions:
   - missing credential;
   - auth/rate/quota/overload errors;
   - transport timeout;
   - invalid payload/empty catalog.

4. User-facing disclosure rule:
   - always print catalog provenance (`live`, `curated`, `static_cli`) and failure reason class when falling back.

5. Caching rule:
   - cache `live` catalogs with short TTL (recommended: 1 hour) and allow `--refresh` override in future command surfaces.

## Go/No-Go Recommendation Matrix

| Surface | Live Integration | Recommendation | Rationale |
| --- | --- | --- | --- |
| OpenAI API | Yes | Go | Stable machine endpoint for model listing. |
| Anthropic API | Yes | Go | Stable machine endpoint with pagination and typed payload. |
| OpenRouter API | Yes | Go | Stable machine endpoint with model metadata and optional user-scoped availability. |
| Codex CLI | No documented list endpoint | No-go (direct) / Go (via OpenAI API + curated) | CLI exposes model selection, not a stable list API contract. |
| Claude Code CLI | No documented list endpoint | No-go (direct) / Go (via Anthropic API + curated) | CLI exposes model/effort selection, not a stable list API contract. |

## Implementation Guidance for Follow-on Lanes

For `#145` (`gaia models list`):

- expose `--provider`, `--json`, and `--refresh`.
- emit `source` and `source_detail` in output.
- include fallback reason class for observability.

For `#147` (effort selector):

- persist normalized `reasoning.effort` in config.
- only send effort to provider/request paths that support it.
- for unsupported models/providers: deterministic no-op + explicit info log.

Codex default preference rule:

- in Codex-linked provider contexts, keep `gpt-5.3-codex` as rank-1 default in curated ordering and first recommendation in interactive selectors.

## Unknowns and Residual Risks

- Provider APIs do not expose one universal `supports_effort` contract; Gaia must maintain a compatibility map until provider metadata normalizes.
- OpenAI catalog includes model classes outside Gaia reasoning scope; filtering heuristics must be regression-tested.
- OpenRouter global catalog and user-available catalog can diverge based on account/provider routing settings.
- CLI products may change aliases/model naming independently from API IDs; curated mappings require periodic freshness checks.

## Acceptance Check Against Issue #144

- Dated synthesis artifact under `research/synthesis/`: complete.
- Official docs + command evidence included: complete.
- Normalized schema defined (required + optional fields): complete.
- Live/curated/static decision and fallback rules defined: complete.
- Codex/Claude live integration go/no-go explicitly documented: complete.
