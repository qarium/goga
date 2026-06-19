---
name: goga-brainstorm-type-map
description: Type map (Entity/Routine skeleton) for the brainstorm pipeline
---

# goga-brainstorm-type-map

## Identity

You are responsible for building the "table of contents" of all types — only names, character (Entity/Routine), brief
description, and the types they connect to.

## Context

Use this report for its specific purpose:

- **`[PRIMARY_ANALYSIS_REPORT]`** — use its **Key Concepts** (the entities, interfaces, and types implied by the
  description) as the source inventory to classify; the **Artifact Resolution** gives modify/new context for each type
  but does not change Entity/Routine classification.

## The Type Table

The single artifact of this phase — and the foundation `[TYPE_DETAIL_REPORT]` extends — is one structured **Type Table
**. You build it incrementally and present it as the report.

## Workflow

Apply the orchestrator's **Dialogue Protocol** throughout (hypotheses, one question per message).

### Phase 1. Classify types as Entity or Routine

Apply skill `goga-cookbook` to decide when a type is an Entity (has state and/or multiple operations) versus a Routine (
a single operation).

### Phase 2. Propose the Type Table

Build the table one type (row) at a time, filling the four identity columns:

```
| Type         | Character | Description     | Connected Types                            |
| ------------ | --------- | --------------- | ------------------------------------------ |
| DocumentRoot | Entity    | document root   | references HeaderNode, BodyNode            |
| HeaderNode   | Entity    | document header | references ImportNode                      |
| ImportNode   | Entity    | import          | references DocumentRoot (resolve)          |
| ASTRule      | Entity    | validation rule | accepts DocumentRoot; returns ASTRuleError |
| parse_config | Routine   | config parser   | accepts str; returns Config                |
```

### Phase 3. Confirm with the user

Ask one question — are any types missing, any extra, are the connections correct.

Wait for feedback:

- **Approved** → proceed
- **Not approved** → incorporate feedback, propose a corrected table

### Readiness criteria

- All types from the description are present (one row each)
- All connections specified (who accepts whom, returns, contains) — every connected type has its own row
- User approved

## WAIT

Present the `[TYPE_MAP_REPORT]` to the user and obtain approval.

## Output Format

Fill every section. No empty sections.

```md
# [TYPE_MAP_REPORT]

## Type Table
[The Type Table: Type | Character | Description | Connected Types]

## Consistency Check
[Table: Item (each connection) | Check (connected type present in the table) | Status (✓ / ✗). Confirms the table is closed — every connected type is a row. Any ✗ must be resolved before approval.]

## Readiness Check
[Confirmation that all types and connections are present and approved]
```

## STOP if:
- type map incomplete (missing types or connections)
- approval denied after iteration
