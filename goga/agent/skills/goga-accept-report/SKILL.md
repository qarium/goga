---
name: goga-accept-report
description: Generate the final acceptance report with verdict
---
# goga-accept-report

## Identity

You are responsible for generating the final acceptance report, synthesizing results from all preceding steps.

## Algorithm

1. Collect outputs from all preceding steps:
   - Acceptance Scope Report
   - Manifest Review Report
   - Usage Review Report
   - Test Assessment Report
2. Synthesize into a single Final Acceptance Report
3. Include only verified facts — no assumptions
4. Determine the acceptance verdict

### Verdict Determination

- **ACCEPTED**: all steps passed without critical findings, test coverage is ADEQUATE or above
- **ACCEPTED_WITH_NOTES**: there are WARNING/INFO findings that do not block acceptance
- **REJECTED**: there are CRITICAL findings or CRITICAL gaps in coverage

## Output Format

Fill in every section. Empty sections are not allowed.

```md
# Final Acceptance Report

## Summary
[One paragraph: what was verified and the overall result]

## Acceptance Scope
[From Scope Report: table of verified cells and change types]

## CODEMANIFEST Status
[From Manifest Review: CONSISTENT / INCONSISTENT + number of updates]

## Usages Status
[From Usage Review: CONSISTENT / INCONSISTENT + number of updates]

## Test Coverage Assessment
[From Test Assessment: EXCELLENT / ADEQUATE / INSUFFICIENT / CRITICAL_GAPS + summary]

## Critical Findings
[Table: Source (Manifest/Usage/Test) | Finding | Status (fixed/open)]

## Warnings
[Table: Source | Finding | Recommendation]

## Applied Updates
[Complete list of files modified during acceptance: CODEMANIFEST, .usages, tests]

## Risks
[Table: Risk | Severity | Mitigation]

## Verdict
[ACCEPTED / ACCEPTED_WITH_NOTES / REJECTED — with justification]
```
