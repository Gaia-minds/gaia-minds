# Gaia Compatibility Matrix (agent-skills baseline)

This matrix compares Gaia's skill/sandbox quality model against `vercel-labs/agent-skills` and is generated from a pinned baseline.

- Source repository: `https://github.com/vercel-labs/agent-skills`
- Source branch: `main`
- Source reference: `e23951b8cad2f4b1e7e176c5731127c1263fe86f`
- Source checked at: `2026-02-13T21:05:00Z`
- Baseline file: `assistant/compatibility-matrix-baseline.json`

| Dimension | Upstream expectation | Gaia status | Rationale | Evidence |
| --- | --- | --- | --- | --- |
| SKILL.md entrypoint layout | Each skill package is anchored by a SKILL.md entrypoint. | `supported` | Gaia resolves only SKILL.md entrypoints from approved project/local roots and emits stable contract metadata. | `tools/gaia-assistant.py`<br>`infrastructure/skill-contract-v1.md`<br>`node ./bin/gaia.js skills list --source project` |
| Frontmatter metadata contract | Skill frontmatter includes name/description and optional metadata fields. | `supported` | Gaia parses frontmatter, validates required fields, and preserves optional metadata without execution. | `tools/gaia-assistant.py`<br>`assistant/fixtures/skills/safe-control/SKILL.md`<br>`node ./bin/gaia.js skills inspect project:gaia-contributor` |
| Co-located scripts/references layout | Skill packages may include scripts/ and references/ directories alongside SKILL.md. | `supported` | Gaia static validation scans bounded file sets under the skill root, including scripts and references files. | `tools/gaia-assistant.py`<br>`assistant/README.md`<br>`node ./bin/gaia.js skills validate project:gaia-contributor` |
| Malicious fixture blocking | Unsafe instructions/scripts should be detected before skill execution. | `supported` | Gaia quality matrix enforces deterministic fail-on-malicious fixtures covering prompt injection, unsafe scripts, exfiltration, and reverse shell patterns. | `assistant/fixtures/skills/manifest.json`<br>`tools/quality-matrix.py`<br>`python3 tools/quality-matrix.py --json-out assistant/quality-matrix-results.json` |
| Sandbox + policy runtime gates | Skill execution should enforce runtime guardrails and approvals. | `supported` | Gaia sandbox profiles, escalation approvals, and per-skill policy decisions are validated as blocking guardrails in quality/UAT scenarios. | `infrastructure/sandbox-contract-v1.md`<br>`assistant/uat-scenarios.json`<br>`node ./bin/gaia.js sandbox profiles` |
| Cross-lane audit trace metadata | Skill operations should be traceable for debugging and incident triage. | `supported` | Gaia emits correlated trace metadata across skills/policy/sandbox flows and exposes deterministic filters for forensic triage. | `assistant/README.md`<br>`tools/gaia-assistant.py`<br>`node ./bin/gaia.js traces --type policy_decision --last 1 --json` |
| Upstream npx install workflow parity | Agent skills can be installed directly with npx tooling from upstream registries/repos. | `gap` | Gaia currently supports project/local skill roots and path validation, but does not yet provide a native remote install command equivalent to upstream npx installation flow. | `assistant/README.md`<br>`tools/gaia-assistant.py`<br>Tracked as future enhancement after Phase 2 lane completion. |

## Reproducibility

```bash
# regenerate matrix markdown from pinned baseline
python3 tools/compatibility-matrix.py \
  --baseline assistant/compatibility-matrix-baseline.json \
  --matrix-out assistant/compatibility-matrix.md

# verify committed markdown is current
python3 tools/compatibility-matrix.py \
  --baseline assistant/compatibility-matrix-baseline.json \
  --matrix-out assistant/compatibility-matrix.md --check
```
