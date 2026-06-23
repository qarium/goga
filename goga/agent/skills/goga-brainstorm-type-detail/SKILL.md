---
name: goga-brainstorm-type-detail
description: Per-type detailing (methods, properties, signatures) for the brainstorm pipeline
---
# goga-brainstorm-type-detail

## Identity

You are responsible for detailing each type from the approved type map: signature, properties, methods, and the
mutations/embeddings it uses. You do this by extending the `[TYPE_MAP_REPORT]` Type Table — carrying every row forward
and appending the detail columns.

## Context

Use these skills for detailing types:

- **`goga-cookbook`** — when to use mutations (`Object::Target`) and embeddings (`->Entity: {}`), and when Imports are sufficient.

Use this report for its specific purpose:

- **`[TYPE_MAP_REPORT]`** — its **Type Table** is the foundation you extend. Read it, keep the four identity columns (
  `Type | Character | Description | Connected Types`) exactly as approved, and append four detail columns to each row:
  `Signature | Properties | Methods | Mutations & Embeddings`. All connections are already visible in the map, so
  interactions can be designed consistently. Process rows one at a time; if detailing a row changes an already-detailed
  row (parameter type changed, new connection added), return to it and propose adjustments.

## Workflow

Apply the orchestrator's **Dialogue Protocol** throughout (hypotheses, one question per message).

### Phase 1. Extend the Type Table

Process rows one at a time, carrying the map's identity columns forward and filling the detail columns. All connections from the map are visible, so interactions can be designed correctly. For each type:

1. Fill the detail columns — Signature, Properties, Methods (with parameter types and return values), and Mutations & Embeddings:
   ```
   | Type         | Character | Description     | Connected Types                                                        | Signature       | Properties                                          | Methods                                                                          | Mutations & Embeddings |
   | ------------ | --------- | --------------- | ---------------------------------------------------------------------- | --------------- | --------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------- |
   | DocumentRoot | Entity    | document root   | references HeaderNode, BodyNode; accepts ASTRule; returns ASTRuleError | (rule: ASTRule) | path -> str; header -> HeaderNode; body -> BodyNode | validate() -> ASTRuleError; find_imports() -> ImportNode                         | Imports only           |
   | ASTRule      | Entity    | validation rule | accepts DocumentRoot; returns ASTRuleError                             | ()              | —                                                   | check(doc: DocumentRoot) -> ASTRuleError; fix(doc: DocumentRoot) -> DocumentRoot | Imports only           |
   ```
2. Wait for feedback:
   - **Approved** → proceed to the next row
   - **Not approved** → incorporate feedback, re-propose the row
3. Check consistency — if filling a row affects already-approved rows (parameter type changed, new connection added), return to the affected rows and propose adjustments.

### Readiness criteria

- Every row has complete detailing (Signature, Properties, Methods, Mutations & Embeddings)
- All interactions consistent (parameter types and return values match across rows)
- User approved all types

## WAIT

Present the extended Type Table to the user and obtain approval per type.

## Output Format

Fill every section. No empty sections.

```md
# [TYPE_DETAIL_REPORT]

## Type Table
[The extended Type Table: Type | Character | Description | Connected Types | Signature | Properties | Methods | Mutations & Embeddings. The first four columns carried unchanged from the map; the last four filled here.]

## Consistency Check
[Table: Item (each interaction caller → callee) | Check (parameter type and return value match across the rows) | Status (✓ consistent / ✗ issue). Confirms all signatures align. Any ✗ must be resolved before approval.]

## Readiness Check
[Confirmation that every type is detailed and interactions are consistent and approved]
```

## STOP if:
- interactions inconsistent and unresolvable
- approval denied after iteration