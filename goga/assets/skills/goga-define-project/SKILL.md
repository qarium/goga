---
name: goga-define-project
description: 
---

# goga-define-project

## Purpose

Understand the current project before defining a product change that must fit into an existing product.

Use the project's structural context to understand:

- what the existing product contains;
- which cells are relevant to the requested change;
- how those cells relate to the product;
- what existing capabilities may already solve part of the problem;
- where the requested change naturally belongs.

This skill provides product context for an existing project. It does not design the change.

---

## Contract

```yaml
consume:
  - input

produce:
  - product
```

---

## Core Principle

Understand the existing product before proposing changes to it.

The requested change must be evaluated against what already exists.

Do not assume that the requested capability is missing simply because the user asks for it.

Do not redesign the existing product.

The goal is to provide enough context for subsequent skills to reason about the change without rediscovering the project structure themselves.

---

## Product Decisions

This skill is responsible for understanding the existing product, not deciding what the new product change should be.

Use the project context to answer factual questions about the current product yourself.

Do not infer the user's desired change when multiple reasonable interpretations exist.

If the existing product context reveals multiple materially different ways the requested change could fit into the product, ask the user which direction is intended.

The user should decide product intent. The project should provide product facts.

---

## Source of Truth

Use:

```bash
goga schema

# for understand json use
goga schema --help
```

as the primary source for understanding the current project structure.

The schema describes the project's cells and provides their descriptions.

When the meaning, structure, or purpose of a cell is unclear, use the `goga-cell` skill to understand the cell model and its conventions.

Do not inspect the entire project indiscriminately.

Start from the schema and progressively inspect only the parts relevant to the requested change.

---

## Process

### 1. Read the project schema

Execute:

```bash
goga schema
```

Use the result to understand:

- available cells;
- their descriptions;
- their apparent responsibilities;
- relationships or boundaries visible from the schema.

Treat the schema as the map of the existing product.

---

### 2. Understand the cell model

When necessary, use `goga-cell` to understand:

- what a cell represents;
- how cell responsibilities are defined;
- how cells expose capabilities;
- how cells are expected to interact.

Do not reproduce the entire `goga-cell` documentation in the resulting context.

Use it to correctly interpret the schema.

---

### 3. Map the request to the existing product

Analyze the user's `input` against the schema.

Identify:

- cells directly relevant to the request;
- cells indirectly affected;
- existing capabilities related to the requested outcome;
- potentially overlapping functionality;
- product boundaries that may constrain the change.

Do not assume that every technically adjacent cell is relevant.

---

### 4. Inspect relevant cells

For cells that materially affect the requested change, inspect their available descriptions and relevant context as needed.

Determine:

- what the cell is responsible for;
- what capability it provides;
- what user-facing behaviour it represents when this is available;
- what part of the requested change belongs there;
- whether the requested functionality may already exist.

Keep the investigation focused.

---

### 5. Detect existing solutions

Actively look for evidence that the requested problem is:

- already solved;
- partially solved;
- solved through another workflow;
- represented by an existing capability;
- constrained by an existing product boundary.

Do not assume a new capability is required.

If the requested solution duplicates an existing capability, report the conflict.

---

### 6. Identify relevant product boundaries

Determine which existing boundaries matter to the requested change.

Examples:

- a capability belongs to a specific cell;
- a workflow crosses several cells;
- a user-facing behaviour is already owned by another part of the product;
- an existing cell boundary should be preserved.

Do not propose architectural changes.

Only describe boundaries that are relevant to product reasoning.

---

### 7. Challenge the project understanding

Before producing the context, challenge your own interpretation.

Ask:

- Am I looking at the correct cells?
- Does an existing capability already solve the requested problem?
- Am I treating an implementation detail as a product capability?
- Is the requested change actually a modification of existing behaviour rather than a new capability?
- Are there existing product boundaries that materially affect the problem?
- Is the available context sufficient to understand the relevant part of the product?

If the available project context contradicts the user's request, report a conflict.

---

## Scope of Investigation

Do not perform a repository-wide investigation by default.

Use this progression:

```text
goga schema
    ↓
identify relevant cells
    ↓
understand relevant cells
    ↓
inspect only necessary context
```

Expand the investigation only when the current evidence is insufficient to understand the requested change.

The purpose is not to create a complete repository inventory.

---

## Product Context

Produce a concise product context containing only information useful to downstream product-definition skills.

The context should cover, where relevant:

```yaml
product:
  overview: |
    <relevant understanding of the existing product>

  relevant_cells:
    - name: <cell>
      responsibility: |
        <what this cell is responsible for>
      relevance: |
        <why it matters to the requested change>

  existing_capabilities:
    - |
      <capability relevant to the request>

  boundaries:
    - |
      <relevant product boundary>

  observations:
    - |
      <important observation about the current product>
```

Do not include the entire output of `goga schema`.

Do not create unnecessary metadata.

---

## Conflict Detection

Report a conflict when the current project context materially contradicts the requested change.

Examples:

```yaml
conflict: |
  The requested capability already exists in an existing cell
  and is exposed through the current product workflow.

reason: |
  The request appears to duplicate existing product behaviour.
```

Another example:

```yaml
conflict: |
  The request assumes that the workflow belongs to one product area,
  but the existing product context shows that it is owned by another
  established product boundary.

reason: |
  The requested change may require reconsidering the product scope
  rather than extending the assumed area.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Interview

During project discovery, distinguish between:

- information that can be obtained from the existing project;
- product decisions that must be made by the user.

Obtain factual project information yourself using `goga schema`, `goga-cell`, and relevant project context.

Interview the user when the existing project reveals a product decision with multiple materially different interpretations.

Do not choose between those interpretations on the user's behalf.

Continue the interview until the relevant product direction is clear enough for downstream skills to reason about the requested change.

---

## Do Not Define

This skill must not define:

- the problem;
- users;
- product goals;
- user experience;
- requirements;
- scope;
- technical architecture;
- implementation tasks.

Its responsibility is limited to understanding the existing product context.

---

## Output

Produce the `product` context required by downstream skills.

The result must be:

- grounded in the current project;
- focused on the requested change;
- concise;
- product-oriented;
- free of implementation speculation.

The product context must be sufficient for `goga-define-problem` and subsequent skills to reason about changes to the existing product.
