---
name: goga-define-scope
description: 
---

# goga-define-scope

## Purpose

Define the boundaries of the product change.

Transform the established problem, goals, requirements, and constraints into a clear statement of:

- what is included in the current solution;
- what is explicitly excluded;
- what should not be solved as part of this change.

The result must protect the product work from scope creep while ensuring that everything necessary to solve the identified problem remains inside the scope.

---

## Contract

```yaml
consume:
  - product
  - problem
  - goals
  - requirements
  - constraints

produce:
  - scope
```

---

## Core Principle

Scope is a boundary, not a feature list.

The central question is:

> What must be part of this product change to solve the problem, and what deliberately remains outside it?

Scope must be derived from the problem and goals.

Do not define scope based on what happens to be technically convenient or interesting.

---

## Product Interview

Scope boundaries are product decisions.

Do not infer what belongs in or out of scope solely from implementation convenience.

Interview the user when the boundary between the current change and adjacent functionality is materially ambiguous.

Clarify when necessary:

- which user scenarios are part of the current change;
- which related scenarios should remain unchanged;
- whether an adjacent workflow should be modified;
- what is intentionally deferred;
- what the minimum complete solution is.

Do not automatically include related functionality merely because it would be convenient to change it at the same time.

---

## Process

### 1. Define the required scope

Identify everything that is necessary to solve the problem and achieve the established goals.

Consider:

- essential user scenarios;
- required product behaviour;
- required states;
- necessary user roles;
- necessary supporting behaviour;
- constraints that require additional product behaviour.

If removing something would prevent the product from solving the problem, it belongs in scope.

---

### 2. Define the excluded scope

Identify functionality that may appear related but is not necessary for the current problem.

Common examples:

- future enhancements;
- additional user segments;
- unrelated workflow improvements;
- advanced customization;
- reporting or analytics not required by the goals;
- integrations that are not necessary for the current solution;
- optimizations that do not affect the defined outcome.

Explicitly exclude these when they are likely to become sources of scope creep.

---

### 3. Protect the core problem

Check that scope remains centered on the original problem.

Ask:

- Does everything in scope contribute to solving the problem?
- Is any functionality included simply because it is convenient?
- Are we solving adjacent problems that were not identified?
- Are we adding capabilities because they might be useful later?
- Would removing this item prevent achievement of the goals?

If an item does not contribute materially to the current goals, challenge its inclusion.

---

### 4. Check completeness

Scope must contain everything necessary to deliver the agreed user experience.

Compare:

```text
Problem
  ↓
Goals
  ↓
Requirements
  ↓
Scope
```

Verify that the scope does not accidentally exclude a requirement that is necessary for the solution.

---

### 5. Check constraints

Ensure that the scope can be implemented while respecting established constraints.

A scope decision must not silently invalidate a constraint.

If the goals cannot be achieved within the current constraints and scope, report a conflict.

---

### 6. Handle adjacent concerns

When the problem touches an adjacent product area, determine whether that area is actually required for the current solution.

Do not automatically expand the scope because another part of the product is involved.

Ask:

> Is changing this area necessary to solve the current problem, or merely a potentially better future improvement?

Only the former belongs in scope.

---

## Scope Structure

Produce two explicit boundaries:

```yaml
scope:
  in:
    - ...
  out:
    - ...
```

### `in`

Items that are necessary for the current product change.

### `out`

Items that are intentionally excluded from the current product change.

Do not use `out` as a backlog of future features. Include an item only when its exclusion is relevant to preventing ambiguity or scope creep.

---

## Scope Quality

A good scope is:

### Focused

Centered on the identified problem.

### Complete

Contains everything necessary to achieve the goals.

### Explicit

Leaves important boundaries unambiguous.

### Defensible

Every included item can be justified by the product context.

### Limited

Does not expand into unrelated improvements.

---

## Challenge the Scope

Challenge both inclusion and exclusion.

If both inclusion and exclusion are reasonable interpretations and they would materially change the product outcome, ask the user to choose.

Do not resolve scope boundaries through assumption.

### Challenge `in`

Ask:

- Is this necessary?
- Which goal or requirement requires it?
- Is it solving the current problem?
- Could it be removed without affecting the intended outcome?

### Challenge `out`

Ask:

- Is this actually unnecessary?
- Does excluding it break an important user scenario?
- Does a requirement implicitly depend on it?
- Are we excluding it only because it is inconvenient?

Do not use scope to hide unresolved product decisions.

---

## Conflict Detection

Report a conflict when:

- an in-scope item contradicts a constraint;
- an out-of-scope item is required to achieve a goal;
- the scope excludes a necessary requirement;
- the scope includes functionality unrelated to the problem and its inclusion creates a conflicting goal or requirement;
- the requested solution cannot achieve the goals within the defined scope.

Example:

```yaml
conflict: |
  The current scope excludes the administrative workflow,
  but the requirements require administrators to configure
  the behaviour before users can use the feature.

reason: |
  The excluded workflow is necessary for the defined product
  behaviour to function.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Missing Information

Ask the user only when a scope decision materially affects the product outcome and cannot be derived from the existing context.

Valid questions may concern:

- which users are included;
- which scenarios are required;
- whether an adjacent workflow is part of the current change;
- whether a particular capability is necessary for the core outcome.

Do not ask about technical implementation.

---

## Do Not Define

This skill must not define:

- technical implementation;
- architecture;
- project tasks;
- development estimates;
- release planning;
- technology choices;
- future product roadmap.

Scope is about product boundaries, not engineering planning.

---

## Output

Produce:

```yaml
scope:
  in:
    - ...
  out:
    - ...
```

The result must clearly establish the boundaries of the current product change.

The final scope must be broad enough to solve the problem completely and narrow enough to prevent unrelated work from entering the PRD.
