# Skill Contract v1

Updated: February 13, 2026

## Purpose

Define the runtime contract emitted by `gaia skills list` and
`gaia skills inspect` for skill discovery and downstream lane integration.

Contract name: `gaia.skill.v1`
Schema version: `1`

This contract is the baseline for lanes that consume skill metadata
(`P2-D`, `P2-F`, `P2-G`, `P2-H`).

## Approved Runtime Sources

`gaia skills` only indexes `SKILL.md` entrypoints from approved roots:

1. `project` source: `<repo>/skills`
2. `local` source: `~/.gaia-assistant/skills` (or `config.skills.local_dir`)

Source filter options:

- `project`
- `local`
- `all` (default)

## Contract Fields

Each discovered skill record contains:

- `schema_version` (integer): contract schema version (`1`)
- `skill_id` (string): stable runtime id (`<source>:<slug>`)
- `slug` (string): source-relative skill slug
- `name` (string): declared frontmatter name (or directory fallback)
- `description` (string): declared frontmatter description
- `source` (string): `project` or `local`
- `source_root` (string): resolved source root shown by runtime
- `entrypoint` (string): `SKILL.md` path used for loading
- `capabilities` (array<string>): declared capabilities (optional, can be empty)
- `capability_policy` (array<object>): policy level mapping for each declared capability
- `provenance` (object):
  - `sha256` (string): content hash of `SKILL.md`
  - `last_modified_at` (ISO-8601 UTC string): file modification timestamp
- `frontmatter` (object):
  - `keys` (array<string>): parsed frontmatter keys
  - `declares_capabilities` (boolean): whether capabilities were declared

## CLI Surface

- `gaia skills list [--source project|local|all] [--json]`
- `gaia skills inspect <skill-id-or-unique-name> [--source project|local|all]`

`inspect` accepts:

1. exact `skill_id` (recommended), or
2. unqualified `name` when unique across selected sources.

## Determinism Notes

- Discovery scans are sorted by source/name/path.
- `skill_id` is deterministic for a fixed source root and directory layout.
- Inspect payload is stable for unchanged `SKILL.md` content.

## v1 Non-Goals

- Static malicious-pattern validation (`P2-D`)
- Per-skill policy enforcement decisions (`P2-F`)
- Cross-lane unified trace schema extensions (`P2-G`)
