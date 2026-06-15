---
name: goga-brainstorm-type-map
description: Type map (Entity/Routine skeleton) for the brainstorm pipeline
---
# goga-brainstorm-type-map

## Identity

You are responsible for building the "table of contents" of all types — only names, character (Entity/Routine), brief purpose, and connections between them. No methods, properties, or details yet — only the skeleton of the abstract object model.

## Context

Use this report for its specific purpose:

- **`[PRIMARY_ANALYSIS_REPORT]`** — use its **Key Concepts** (the entities, interfaces, and types implied by the description) as the source inventory to classify; the **Artifact Resolution** gives modify/new context for each type but does not change Entity/Routine classification.

## Workflow

Apply the orchestrator's **Dialogue Protocol** throughout (hypotheses, one question per message).

### Phase 1. Classify types as Entity or Routine

Apply skill `goga-cookbook` to decide when a type is an Entity (has state and/or multiple operations) versus a Routine (a single operation).

### Phase 2. Propose the type map

Build a list of types with character, description, and connections:

```
DocumentRoot      — [Entity] document root. References: HeaderNode, BodyNode
HeaderNode        — [Entity] document header. References: ImportNode
ImportNode        — [Entity] import. References: DocumentRoot (resolve)
ASTRule           — [Entity] validation rule. Accepts: DocumentRoot. Returns: ASTRuleError
parse_config      — [Routine] config parser. Accepts: str. Returns: Config
```

### Phase 3. Confirm with the user

Ask one question — are any types missing, any extra, are the connections correct.

Wait for feedback:

- **Approved** → proceed
- **Not approved** → incorporate feedback, propose a corrected map

### Readiness criteria

- All types from the description are present
- All connections specified (who accepts whom, returns, contains)
- User approved

## WAIT

Present the `[TYPE_MAP_REPORT]` to the user and obtain approval.

## Output Format

Fill every section. No empty sections.

```md
# [TYPE_MAP_REPORT]

## Type Map
[Table or list: Type | Character (Entity/Routine) | Purpose | Connections (References/Accepts/Returns/Contains)]

## Connection Summary
[Plain-language description of how types reference and depend on each other]

## Readiness Check
[Confirmation that all types and connections are present and approved]
```

## STOP if:
- type map incomplete (missing types or connections)
- approval denied after iteration
