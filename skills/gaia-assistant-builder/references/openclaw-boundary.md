# Gaia vs OpenClaw Boundary

Use this file to decide where a change should land first.

## Gaia Repository

Keep these in `gaia-minds/gaia-minds`:

- Constitutional policy and governance rules
- User-direction workflow and templates
- Contributor-facing program docs
- Gaia-specific skills and repo automation
- Token budget policy for Gaia self-improvement cycles

## OpenClaw Repository

Keep these in `openclaw/openclaw`:

- Generic runtime features
- Generic model/channel/tool integrations
- Generic onboarding and operator documentation
- Generic skill platform behavior

## Cross-Repo Pattern

1. Define policy and contract in Gaia.
2. Upstream generic integration/docs hooks to OpenClaw.
3. Link PRs both ways for traceability.

## Anti-Patterns

Avoid:

- Duplicating the same policy text in both repos
- Putting Gaia governance rules into OpenClaw core docs
- Putting OpenClaw runtime internals into Gaia policy docs

