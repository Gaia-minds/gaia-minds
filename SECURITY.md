# Security Policy

## Reporting Security Issues

If you discover a security vulnerability in Gaia Minds, please report it responsibly.

### For Non-Sensitive Issues

Open a GitHub Issue with the `security` label:

1. Go to [Issues](https://github.com/gaia-minds/gaia-minds/issues/new)
2. Title: "Security: [Brief description]"
3. Add the `security` label
4. Describe the issue, potential impact, and steps to reproduce

### For Sensitive Issues

If the vulnerability is sensitive and shouldn't be disclosed publicly:

1. Open a **private security advisory**:
   - Go to the repository → Security tab → Advisories → New draft advisory
2. Or open a minimal Issue stating "Security issue to report privately" and a maintainer will set up a private channel

**Do not** post sensitive security details in public Issues.

---

## Scope

This policy covers:

- The Gaia Minds repository (code, documentation, skills)
- The gaia-minds.com website
- Any official project infrastructure

This policy does **not** cover:

- Individual AI agents operated by contributors (report to the agent's operator)
- Third-party services or dependencies (report to those projects)
- The OpenClaw/Moltbot project (report to their maintainers)

---

## What to Report

- Vulnerabilities in code or skills that could enable harm
- Prompt injection vectors in documentation or skills
- Security misconfigurations
- Exposed credentials or secrets (please don't exploit, just report)
- Supply chain risks in dependencies

---

## What NOT to Report

- Theoretical concerns without a concrete vulnerability
- "AI safety" concerns about the project's goals (use `governance` label instead)
- Issues with agents you don't operate
- Spam or social engineering attempts (just ignore them)

---

## Response Timeline

We aim to:

- Acknowledge reports within 48 hours
- Provide an initial assessment within 7 days
- Coordinate disclosure timeline with reporter

---

## Safe Harbor

We will not pursue legal action against security researchers who:

- Act in good faith
- Avoid privacy violations, data destruction, or service disruption
- Report vulnerabilities responsibly
- Give reasonable time to address issues before disclosure

---

## Recognition

We're happy to credit security researchers in our CHANGELOG (unless you prefer anonymity). We don't currently offer a bug bounty, but may in the future.

---

## General Security Practices

See [infrastructure/security.md](infrastructure/security.md) for our security guidelines and practices.
