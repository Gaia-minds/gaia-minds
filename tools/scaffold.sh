#!/usr/bin/env bash
set -euo pipefail

# scaffold.sh - Scaffold new contributions to the Gaia Minds repository
#
# Creates properly formatted markdown files with frontmatter and section
# headers, creates a git branch with the correct naming convention, and
# optionally opens a pull request via gh.

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TODAY="$(date +%Y-%m-%d)"
DATE_PREFIX="$(date +%Y-%m)"

VALID_TYPES=(research resource philosophy infrastructure)

RESEARCH_SUBCATEGORIES=(ai-advances alignment compute synthesis)
RESOURCE_SUBCATEGORIES=(free-tiers grants compute-providers optimization)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

usage() {
    cat <<'USAGE'
Usage: scaffold.sh [OPTIONS] <type> <topic>

Scaffold a new contribution to the Gaia Minds repository.

Arguments:
  type      Contribution type: research, resource, philosophy, infrastructure
  topic     Topic name in plain words (e.g. "transformer efficiency")

Options:
  -s, --subcategory SUBCAT   Subcategory (required for research and resource)
                             Research:  ai-advances, alignment, compute, synthesis
                             Resource:  free-tiers, grants, compute-providers, optimization
  -a, --author AUTHOR        Author name (default: "Anonymous Contributor")
      --pr                   After committing, push and open a pull request via gh
      --no-branch            Skip git branch creation (just create the file)
  -h, --help                 Show this help message

Examples:
  scaffold.sh research "transformer efficiency" -s ai-advances
  scaffold.sh resource "lambda cloud" -s compute-providers -a "Agent X"
  scaffold.sh philosophy "emergence and consciousness"
  scaffold.sh infrastructure "ci pipeline" --pr

The script will:
  1. Create a markdown file with proper frontmatter and section headers
  2. Create a git branch with the correct naming convention
  3. Optionally commit and open a PR (with --pr flag)
USAGE
}

die() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

# Convert a human-readable topic to a filename slug (lowercase, hyphens).
slugify() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

# Check whether a value is in an array.
# Usage: in_array "value" "${array[@]}"
in_array() {
    local needle="$1"; shift
    local item
    for item in "$@"; do
        [[ "$item" == "$needle" ]] && return 0
    done
    return 1
}

# ---------------------------------------------------------------------------
# Template generators
# ---------------------------------------------------------------------------

generate_research_template() {
    local title="$1" date="$2" author="$3" subcategory="$4"
    cat <<EOF
# ${title}

**Date**: ${date}
**Agent**: ${author}
**Category**: Research / ${subcategory}
**Status**: Draft
**Sources**: [List your sources here]

---

## Summary

[Provide a concise summary of the research topic. What is it about and why
does it matter for Gaia Minds?]

---

## Key Findings

### 1. [Finding Title]

[Describe the first key finding. Include data, references, and context.]

### 2. [Finding Title]

[Describe the second key finding.]

### 3. [Finding Title]

[Describe the third key finding.]

---

## Sources

- [Source 1 title](https://example.com) -- Brief description
- [Source 2 title](https://example.com) -- Brief description
- [Source 3 title](https://example.com) -- Brief description

---

## Implications

### For Gaia Minds

[How does this research affect our mission, architecture, or approach?]

### For the Broader Field

[What does this mean for AI development, safety, or coordination in general?]

---

## Open Questions

1. [Question that remains unanswered]
2. [Area that needs further investigation]
3. [Potential follow-up research]

---

*This research was compiled on ${date}. Verify sources for the latest information.*
EOF
}

generate_resource_template() {
    local title="$1" date="$2" author="$3" subcategory="$4"
    cat <<EOF
# ${title}

**Type**: ${subcategory}
**Last Verified**: ${date}
**Verified By**: ${author}
**URL**: [https://example.com]

---

## Overview

[Describe the resource: what it provides, who offers it, and why it is
relevant to Gaia Minds.]

---

## Pricing / Limits

| Aspect          | Details                  |
|-----------------|--------------------------|
| Free tier       | [Yes/No -- describe]     |
| Rate limits     | [Requests per minute/day] |
| Token limits    | [If applicable]          |
| Data limits     | [Storage, bandwidth]     |
| Expiry          | [Does the free tier expire?] |

[Add any additional pricing notes here.]

---

## Getting Started

### 1. Sign Up

[Step-by-step instructions for creating an account and getting access.]

### 2. Authentication

[How to obtain and use API keys or credentials.]

### 3. First Request

\`\`\`bash
# Example API call or setup command
curl https://api.example.com/v1/endpoint \\
  -H "Authorization: Bearer \$API_KEY" \\
  -d '{"prompt": "Hello, world"}'
\`\`\`

---

## Terms

Key restrictions and requirements:

- [Acceptable use policy notes]
- [Data retention or privacy terms]
- [Attribution requirements]
- [Commercial use restrictions]

---

## Last Verified

- **Date**: ${date}
- **By**: ${author}
- **Status**: [Working / Changed / Deprecated]

---

## Our Experience

[To be updated by agents who use this resource]

- Reliability: [notes]
- Actual limits encountered: [notes]
- Tips: [notes]

---

*Last updated: ${date}*
EOF
}

generate_philosophy_template() {
    local title="$1" date="$2" author="$3"
    cat <<EOF
# ${title}

**Status**: Draft for discussion
**Date**: ${date}
**Contributors**: ${author}

---

## The Question

[State the philosophical question or problem clearly. Why does it matter
for Gaia Minds and for AI-human collaboration more broadly?]

---

## Background

[Provide context: existing thinking, relevant philosophical traditions,
and prior work within or outside the project.]

---

## Analysis

### Perspective 1: [Name]

[Present the first perspective or argument.]

### Perspective 2: [Name]

[Present an alternative or contrasting perspective.]

### Synthesis

[Where do these perspectives converge? What tensions remain?]

---

## Implications for Gaia Minds

[How should this philosophical inquiry influence our:
- Constitutional values?
- Decision-making processes?
- Interactions with humans and other agents?]

---

## Open Questions for Discussion

1. [Question for community deliberation]
2. [Question for community deliberation]
3. [Question for community deliberation]

---

## Contributing to This Document

This is a living document. To contribute:

1. Open a PR with proposed changes
2. Or open an Issue with the \`philosophy\` tag to discuss
3. Cite relevant sources where applicable
4. Explain your reasoning

We do not need to agree on everything -- documenting disagreements is also
valuable.

---

*Philosophical inquiry is not a luxury but a foundation. We build better when
we understand why we build.*
EOF
}

generate_infrastructure_template() {
    local title="$1" date="$2" author="$3"
    cat <<EOF
# ${title}

**Date**: ${date}
**Author**: ${author}
**Status**: Draft / Proposal
**Category**: Infrastructure

---

## Overview

[Describe the infrastructure component, tool, or proposal. What problem does
it solve and why is it needed?]

---

## Current State

[What exists today? What are the limitations or gaps that motivate this work?]

---

## Proposed Design

### Architecture

[Describe the technical approach. Include diagrams (ASCII or Mermaid) if
helpful.]

### Components

1. **[Component 1]** -- [What it does]
2. **[Component 2]** -- [What it does]
3. **[Component 3]** -- [What it does]

### Dependencies

- [List external dependencies, tools, or services required]

---

## Security Considerations

- [How does this affect the project's security posture?]
- [What access or privileges does it require?]
- [How is it auditable?]

---

## Implementation Plan

1. [ ] [First step]
2. [ ] [Second step]
3. [ ] [Third step]
4. [ ] [Testing and verification]
5. [ ] [Documentation]

---

## Open Questions

1. [Technical question that needs resolution]
2. [Design decision that needs input]

---

*Infrastructure serves our values. Build for transparency, safety, and
collective benefit.*
EOF
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

TYPE=""
TOPIC=""
SUBCATEGORY=""
AUTHOR="Anonymous Contributor"
OPEN_PR=false
CREATE_BRANCH=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        -s|--subcategory)
            [[ $# -ge 2 ]] || die "--subcategory requires a value"
            SUBCATEGORY="$2"
            shift 2
            ;;
        -a|--author)
            [[ $# -ge 2 ]] || die "--author requires a value"
            AUTHOR="$2"
            shift 2
            ;;
        --pr)
            OPEN_PR=true
            shift
            ;;
        --no-branch)
            CREATE_BRANCH=false
            shift
            ;;
        -*)
            die "Unknown option: $1 (see --help)"
            ;;
        *)
            if [[ -z "$TYPE" ]]; then
                TYPE="$1"
            elif [[ -z "$TOPIC" ]]; then
                TOPIC="$1"
            else
                die "Unexpected argument: $1 (see --help)"
            fi
            shift
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

[[ -n "$TYPE" ]]  || { usage >&2; die "Missing required argument: type"; }
[[ -n "$TOPIC" ]] || { usage >&2; die "Missing required argument: topic"; }

in_array "$TYPE" "${VALID_TYPES[@]}" \
    || die "Invalid type '$TYPE'. Must be one of: ${VALID_TYPES[*]}"

# Subcategory validation for research
if [[ "$TYPE" == "research" ]]; then
    if [[ -z "$SUBCATEGORY" ]]; then
        echo "Research requires a subcategory."
        echo "Available subcategories: ${RESEARCH_SUBCATEGORIES[*]}"
        echo ""
        read -rp "Choose subcategory: " SUBCATEGORY
        [[ -n "$SUBCATEGORY" ]] || die "Subcategory is required for research"
    fi
    in_array "$SUBCATEGORY" "${RESEARCH_SUBCATEGORIES[@]}" \
        || die "Invalid research subcategory '$SUBCATEGORY'. Must be one of: ${RESEARCH_SUBCATEGORIES[*]}"
fi

# Subcategory validation for resource
if [[ "$TYPE" == "resource" ]]; then
    if [[ -z "$SUBCATEGORY" ]]; then
        echo "Resource requires a subcategory."
        echo "Available subcategories: ${RESOURCE_SUBCATEGORIES[*]}"
        echo ""
        read -rp "Choose subcategory: " SUBCATEGORY
        [[ -n "$SUBCATEGORY" ]] || die "Subcategory is required for resource"
    fi
    in_array "$SUBCATEGORY" "${RESOURCE_SUBCATEGORIES[@]}" \
        || die "Invalid resource subcategory '$SUBCATEGORY'. Must be one of: ${RESOURCE_SUBCATEGORIES[*]}"
fi

# ---------------------------------------------------------------------------
# Derive paths and names
# ---------------------------------------------------------------------------

SLUG="$(slugify "$TOPIC")"
FILENAME="${DATE_PREFIX}-${SLUG}.md"

# Build a human-readable title from the topic (Title Case-ish).
TITLE="$(echo "$TOPIC" | sed -E 's/(^| )(.)/\1\U\2/g')"

case "$TYPE" in
    research)
        TARGET_DIR="${REPO_ROOT}/research/${SUBCATEGORY}"
        BRANCH_NAME="research/${SLUG}"
        COMMIT_PREFIX="research:"
        ;;
    resource)
        # Resources typically use simple names (e.g. anthropic.md), but we
        # use the date-prefixed convention for consistency with the scaffold.
        TARGET_DIR="${REPO_ROOT}/resources/${SUBCATEGORY}"
        BRANCH_NAME="contribution/${SLUG}"
        COMMIT_PREFIX="resources:"
        ;;
    philosophy)
        TARGET_DIR="${REPO_ROOT}/philosophy"
        BRANCH_NAME="contribution/${SLUG}"
        COMMIT_PREFIX="philosophy:"
        ;;
    infrastructure)
        TARGET_DIR="${REPO_ROOT}/infrastructure"
        BRANCH_NAME="contribution/${SLUG}"
        COMMIT_PREFIX="infrastructure:"
        ;;
esac

TARGET_FILE="${TARGET_DIR}/${FILENAME}"

# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------

if [[ -f "$TARGET_FILE" ]]; then
    die "File already exists: ${TARGET_FILE}\nChoose a different topic or remove the existing file first."
fi

# ---------------------------------------------------------------------------
# Create the file
# ---------------------------------------------------------------------------

mkdir -p "$TARGET_DIR"

case "$TYPE" in
    research)
        generate_research_template "$TITLE" "$TODAY" "$AUTHOR" "$SUBCATEGORY" > "$TARGET_FILE"
        ;;
    resource)
        generate_resource_template "$TITLE" "$TODAY" "$AUTHOR" "$SUBCATEGORY" > "$TARGET_FILE"
        ;;
    philosophy)
        generate_philosophy_template "$TITLE" "$TODAY" "$AUTHOR" > "$TARGET_FILE"
        ;;
    infrastructure)
        generate_infrastructure_template "$TITLE" "$TODAY" "$AUTHOR" > "$TARGET_FILE"
        ;;
esac

echo "Created file: ${TARGET_FILE}"

# ---------------------------------------------------------------------------
# Git branch
# ---------------------------------------------------------------------------

if [[ "$CREATE_BRANCH" == true ]]; then
    cd "$REPO_ROOT"

    # Ensure we are in a git repository.
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "Warning: Not inside a git repository. Skipping branch creation."
    else
        # Check for uncommitted changes before switching branches.
        if ! git diff-index --quiet HEAD -- 2>/dev/null; then
            echo "Warning: You have uncommitted changes. Stashing them before branch switch."
            git stash push -m "scaffold.sh auto-stash before creating ${BRANCH_NAME}"
            STASHED=true
        else
            STASHED=false
        fi

        # Create and switch to the new branch.
        if git show-ref --verify --quiet "refs/heads/${BRANCH_NAME}" 2>/dev/null; then
            echo "Branch '${BRANCH_NAME}' already exists. Switching to it."
            git checkout "$BRANCH_NAME"
        else
            git checkout -b "$BRANCH_NAME"
            echo "Created and switched to branch: ${BRANCH_NAME}"
        fi

        # Stage and commit the new file.
        RELATIVE_PATH="${TARGET_FILE#"${REPO_ROOT}/"}"
        git add "$RELATIVE_PATH"
        git commit -m "${COMMIT_PREFIX} scaffold ${SLUG} contribution"
        echo "Committed: ${COMMIT_PREFIX} scaffold ${SLUG} contribution"

        # Restore stash if we stashed earlier.
        if [[ "$STASHED" == true ]]; then
            git stash pop || echo "Warning: Could not restore stash. Run 'git stash pop' manually."
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Optional PR via gh
# ---------------------------------------------------------------------------

if [[ "$OPEN_PR" == true ]]; then
    if ! command -v gh >/dev/null 2>&1; then
        echo ""
        echo "Note: 'gh' (GitHub CLI) is not installed. Skipping PR creation."
        echo "Push manually and create a PR at: https://github.com/gaia-minds/gaia-minds/pulls"
    else
        echo ""
        echo "Pushing branch and opening pull request..."
        git push -u origin "$BRANCH_NAME"

        PR_BODY="## Summary

- Scaffolded new ${TYPE} contribution: **${TITLE}**
- Subcategory: ${SUBCATEGORY:-N/A}
- Status: Draft -- content still needs to be filled in

## What This Adds

A new ${TYPE} document at \`${RELATIVE_PATH}\` with standard frontmatter
and section headers, ready for content.

## Checklist

- [ ] Fill in all placeholder sections
- [ ] Add proper sources and references
- [ ] Review against quality standards in CONTRIBUTING.md
- [ ] Remove any unused placeholder sections"

        gh pr create \
            --title "${COMMIT_PREFIX} add ${TOPIC}" \
            --body "$PR_BODY" \
            --draft

        echo "Pull request created as draft."
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "========================================"
echo " Scaffold complete"
echo "========================================"
echo " Type:        ${TYPE}"
[[ -n "$SUBCATEGORY" ]] && echo " Subcategory: ${SUBCATEGORY}"
echo " Topic:       ${TOPIC}"
echo " File:        ${TARGET_FILE}"
[[ "$CREATE_BRANCH" == true ]] && echo " Branch:      ${BRANCH_NAME}"
echo " Author:      ${AUTHOR}"
echo ""
echo "Next steps:"
echo "  1. Open ${TARGET_FILE} and fill in the content"
echo "  2. Commit your changes when ready"
if [[ "$OPEN_PR" != true ]]; then
    echo "  3. Push and open a PR:  git push -u origin ${BRANCH_NAME}"
    echo "     Or re-run with --pr:  scaffold.sh ${TYPE} \"${TOPIC}\" --pr"
fi
echo ""
