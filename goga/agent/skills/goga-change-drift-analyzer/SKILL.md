---
name: goga-change-drift-analyzer
description: Semantic drift detection after implementation
---
# goga-change-drift-analyzer

## Identity

You are responsible for semantic drift detection.

## Algorithm

Execute only after: implementation stabilized, tests passing, reconciliation completed.

1. Load final state of all modified cells
2. Apply goga-codemanifest-base — verify base practices are not drifting from reconciled CODEMANIFEST files
3. For each modified cell, compare:
   a. CODEMANIFEST vs implementation → manifest drift
   b. .usages vs implementation → usage drift
   c. behavioral specification vs actual behavior → behavioral drift
   d. algorithm specification vs actual algorithm → algorithmic drift
4. For each drift found, classify:
   - resolved: drift was expected and reconciled
   - unresolved: drift remains — problem
5. If any unresolved drift → STOP

STOP if:
- unresolved manifest drift
- unresolved usage drift
- unresolved behavioral drift
- unresolved algorithmic drift

## Output Format

Fill every section. No empty sections.

```md
# Specification Drift Analysis

## Manifest Drift
[Table: Cell | Drift Description | Resolved?]

## Usage Drift
[Table: Cell | Drift Description | Resolved?]

## Behavioral Drift
[Table: Cell | Drift Description | Resolved?]

## Algorithmic Drift
[Table: Cell | Drift Description | Resolved?]

## Resolution Status
[Overall: all drift resolved / unresolved drift list]
```
