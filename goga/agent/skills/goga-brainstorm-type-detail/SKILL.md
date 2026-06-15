---
name: goga-brainstorm-type-detail
description: Per-type detailing (methods, properties, signatures) for the brainstorm pipeline
---
# goga-brainstorm-type-detail

## Identity

You are responsible for detailing each type from the approved type map: methods, properties, signatures, and interactions.

## Context

Use these skills for detailing types:

- **`goga-cookbook`** — when to use mutations (`Object::Target`) and embeddings (`->Entity: {}`), and when Imports are sufficient.

Use this report for its specific purpose:

- **`[TYPE_MAP_REPORT]`** — use its approved **list of types and their connections** as the skeleton to flesh out; all connections are already visible here, so interactions can be designed consistently. Process types one at a time from the map; if detailing a type affects an already-detailed type, return to it and propose adjustments.

## Workflow

Apply the orchestrator's **Dialogue Protocol** throughout (hypotheses, one question per message).

### Phase 1. Detail each type

Process types one at a time. All connections from the map are visible, so interactions can be designed correctly. For each type:

1. Propose detailing — methods, properties, signatures with parameter types and return values:
   ```
   DocumentRoot(rule: ASTRule)
     properties:
       path -> str
       header -> HeaderNode
       body -> BodyNode
     methods:
       validate() -> ASTRuleError
       find_imports() -> ImportNode

   ASTRule()
     methods:
       check(doc: DocumentRoot) -> ASTRuleError
       fix(doc: DocumentRoot) -> DocumentRoot
   ```
2. Wait for feedback:
   - **Approved** → proceed to the next type
   - **Not approved** → incorporate feedback, re-propose
3. Check consistency — if detailing a type affects already-approved types (parameter type changed, new connection added), return to the affected types and propose adjustments.

### Readiness criteria

- Each type has complete detailing (methods, properties, signatures)
- All interactions consistent (parameter types and return values match)
- User approved all types

## WAIT

Present per-type detailing to the user and obtain approval per type.

## Output Format

Fill every section. No empty sections.

```md
# [TYPE_DETAIL_REPORT]

## Detailed Types
[Per type: signature, properties, methods — with parameter types and return values]

## Interactions Consistency
[Table: Interaction (caller -> callee) | Parameter/Return | Consistent? — confirms all signatures match across types]

## Mutations & Embeddings
[Where mutations (Object::Target) and embeddings (->Entity: {}) are used, with justification; or "Imports only"]

## Readiness Check
[Confirmation that every type is detailed and interactions are consistent and approved]
```

## STOP if:
- interactions inconsistent and unresolvable
- approval denied after iteration
