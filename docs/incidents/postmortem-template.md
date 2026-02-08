# Incident Postmortem Template

Use this template for reliability and regression incidents.

## Metadata

- Incident ID:
- Title:
- Date detected (UTC):
- Date resolved (UTC):
- Severity: `sev1 | sev2 | sev3`
- Status: `open | mitigated | resolved`
- Owner:
- Related issue(s):
- Related PR(s):
- Related workflow run(s):

## Summary

What happened, in one concise paragraph.

## Impact

- User impact:
- Runtime impact:
- CI/release impact:
- Duration:

## Detection

- How was it detected?
- First alert/signal (logs, workflow, user report):
- Why detection did or did not happen early:

## Timeline (UTC)

| Time | Event | Owner |
| --- | --- | --- |
| 2026-02-10T03:20:00Z | Example: nightly benchmark failed on T14 | gaia-bot |

## Root Cause Analysis

### Immediate Cause

What directly failed?

### Contributing Factors

What conditions made this more likely?

### Why It Escaped Earlier Checks

What guardrail was missing or insufficient?

## Mitigation and Recovery

- Short-term mitigation:
- Recovery steps executed:
- Rollback used? (`yes/no`) and details:

## Corrective Actions

| Action | Type (`prevention`/`detection`/`response`) | Owner | Due Date | Status |
| --- | --- | --- | --- | --- |
| Example: add benchmark scenario for edge case | prevention | @owner | 2026-02-15 | open |

## Verification

- Commands/checks run after fix:
- Evidence links (artifacts, logs, traces):
- Confirmation criteria met:

## Lessons Learned

- What we should repeat:
- What we should stop doing:
- What to automate next:

## Follow-up Tracking

- [ ] Actions linked to issue(s)
- [ ] Actions scheduled/planned
- [ ] Status reviewed in next sprint update
