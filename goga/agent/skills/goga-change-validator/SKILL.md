---
name: goga-change-validator
description: Финальная сквозная валидация выполненного изменения
---
# goga-change-validator

## Identity

You are responsible for final end-to-end validation of the completed change.

## Algorithm

Execute only after: implementation stabilized, tests passing, reconciliation completed, drift analyzed.

1. Load original task description
2. Load approved Change Plan
3. Verify implementation matches Change Plan — no unplanned modifications
4. Run full test suite
5. Run project validators and linters
6. Execute: `goga lint` — final CODEMANIFEST validation
7. Verify scope integrity — all changes within scope from scope-resolver
8. Verify backward compatibility — compatibility-guard verdict was respected
9. Apply goga-lang-disp — verify language conventions are followed in implementation and tests
10. Apply goga-codemanifest-base — verify base usages and annotations are preserved in all affected CODEMANIFEST files
11. Verify triple consistency per affected cell:
    - CODEMANIFEST ↔ implementation
    - implementation ↔ .usages
    - CODEMANIFEST ↔ .usages
12. Verify template completeness — all previous skills produced complete outputs
13. Check for unresolved drift from drift-analyzer
14. Produce Validation Report

STOP if:
- any test fails
- any validator/linter fails
- changes outside approved scope
- backward compatibility broken
- triple consistency violated
- any previous skill output has empty sections
- unresolved drift detected

## Output Format

Fill every section. No empty sections.

```md
# Validation Report

## Scope Resolution
[All modifications within scope? Excluded cells untouched?]

## Task Resolution
[Original task satisfied? Root cause eliminated?]

## Trace Consistency
[Behavioral traces valid? Data/call flows intact?]

## Change Plan Compliance
[Implementation matches plan? No unplanned changes?]

## Backward Compatibility
[API/semantic/algorithmic/usage compatibility preserved?]

## Implementation Quality
[Tests pass? Linters pass? No orphaned code?]

## Test Coverage
[Changed behavior covered? Algorithm stages covered? Regression scenarios?]

## Manifest Reconciliation
[Table: Cell | Algorithms | Operational Flow | Guarantees | Practices | Status]

## Usage Reconciliation
[Table: Usage | Classification | Validated | Status]

## Drift Resolution
[All drift resolved? List any remaining]

## Template Completeness
[Table: Skill | All Sections Filled? | Missing Sections]

## Blocking Issues
[List any blocking issues. Empty if none]

## Overall Status
[VERIFIED / PARTIAL / FAILED — with justification]
```
