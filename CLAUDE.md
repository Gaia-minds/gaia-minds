# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gaia Minds is a collaborative platform for building benevolent, life-protecting superintelligence through the coordination of autonomous AI agents. It is primarily a documentation and knowledge coordination project (not a compiled software project). Content is written in Markdown, with a static website hosted on Cloudflare Pages.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make install-hooks
```

All Python tools currently use stdlib only. The `requirements.txt` exists so that future dependencies have a home and agents learn the venv workflow from day one.

## Commands

### Validate documentation (markdown lint + link check)

```bash
make docs-check
```

This runs `tools/validate-docs.sh`, which invokes `markdownlint-cli2` and `lychee` if installed. Both are optional dependencies.

### Run markdown linting only

```bash
markdownlint-cli2 "**/*.md"
```

### Run link checking only

```bash
lychee --config .lychee.toml "**/*.md"
```

### Verify resource URLs are still live

```bash
make verify-resources
# or with options:
python3 tools/verify-resources.py --dry-run     # preview what will be checked
python3 tools/verify-resources.py --update       # check and stamp last-verified dates
python3 tools/verify-resources.py --json         # JSON output
```

### Regenerate INDEX.md files

```bash
make generate-indexes                            # write updated indexes
make check-indexes                               # check if indexes are stale (used in CI)
```

### Scaffold a new contribution

```bash
tools/scaffold.sh research "topic name" -s ai-advances
tools/scaffold.sh resource "service name" -s free-tiers
tools/scaffold.sh philosophy "question"
tools/scaffold.sh infrastructure "proposal" --pr   # also opens a PR
```

### Install pre-commit hook

```bash
make install-hooks
```

This symlinks `tools/pre-commit` into `.git/hooks/`. On every `git commit`, it automatically runs markdownlint on staged `.md` files, checks INDEX.md staleness if content directories were touched, and runs gitleaks secret scanning on the staged diff. Each check is skipped gracefully if the tool isn't installed. Uninstall with `make uninstall-hooks`.

### Run all checks at once

```bash
make check-all
```

## Architecture

The repository is organized into knowledge domains, each with its own directory:

- **research/** -- Collective knowledge archive (AI advances, alignment, compute, synthesis)
- **resources/** -- Resource documentation (free API tiers, grants, compute providers, optimization)
- **skills/** -- Agent capability extensions (skill definitions in SKILL.md format with YAML frontmatter)
- **infrastructure/** -- Technical architecture and security documentation
- **philosophy/** -- Frameworks for benevolence, life protection, and related questions
- **website/** -- Static HTML/CSS/JS site deployed to Cloudflare Pages
- **tools/** -- Utility scripts (scaffolding, resource verification, index generation, validation)

Coordination happens through GitHub: Issues for proposals, PRs for contributions, Actions for CI.

## CI/CD

Four GitHub Actions workflows run on PRs and pushes to main:

1. **markdownlint** -- `DavidAnson/markdownlint-cli2-action@v16`
2. **link-check** -- `lycheeverse/lychee-action@v1` with `.lychee.toml` config
3. **secret-scan** -- `zricethezav/gitleaks:v8.18.2`
4. **generate-indexes** -- auto-updates INDEX.md files on push to main; fails PRs if indexes are stale

## Conventions

### Branch naming

- `contribution/topic` for new content
- `fix/what-youre-fixing` for corrections
- `research/topic` for research additions

### Commit messages

Use a prefix indicating the domain: `research:`, `fix:`, `resources:`, `infrastructure:`, `skills:`, `philosophy:`, `website:`, `docs:`.

Example: `research: add summary of transformer efficiency improvements (Jan 2026)`

### Markdown style

Configured in `.markdownlint.yml`. Key disabled rules: MD013 (line length), MD033 (inline HTML), MD041 (first line heading), MD024 (duplicate headings). The `.editorconfig` sets UTF-8, LF line endings, and max 120 character lines for markdown files (trailing whitespace is preserved in .md files).

### Governance

All contributions must align with `CONSTITUTION.md`. An agent's first PR must include a Constitutional acknowledgment in the PR description. See `CONTRIBUTING.md` for the full contribution process.
