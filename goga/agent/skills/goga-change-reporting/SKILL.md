---
name: goga-change-reporting
description: Формирование финального отчёта о выполнении изменений
---
# goga-change-reporting

## Identity

You are responsible for human-readable operational reporting.

## Algorithm

1. Collect outputs from all previous skills:
   - Scope Resolution Report
   - Investigation Report
   - Trace Report
   - Change Plan
   - Compatibility Report
   - Test Report
   - Manifest Reconciliation Report
   - Usage Reconciliation Report
   - Drift Analysis
   - Validation Report
2. Synthesize into single Final Change Execution Report
3. Include only verified facts — no speculation
4. Preserve structured sections for LLM parsing

## Output Format

Fill every section. No empty sections.

```md
# Change Execution Report

## Summary
[One paragraph: what was done and why]

## Root Cause
[Root cause from investigation]

## Modified Cells
[Table: Cell | Files Modified]

## Implemented Changes
[Table: Change | File | Description]

## Tests Added
[Table: Test | File | What It Validates]

## Specification Updates
[Table: Cell | CODEMANIFEST Changes | Usage Changes]

## Validation Results
[Overall status from validator]

## Compatibility Status
[From compatibility-guard: compatible or details of breaks]

## Risks
[Table: Risk | Severity | Mitigation]

## Updated Files
[Complete list of all modified files with paths]
```
