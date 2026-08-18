---
name: goga-define-resolve
description: 
---

# goga-define-resolve

## Purpose

Resolve product-level conflicts discovered during the definition process.

Review the conflicting decisions together with the complete product context, determine the correct product decision, and update the affected parts of the definition so the pipeline can continue with a consistent model.

This skill is invoked only when a conflict exists.

---

## Contract

```yaml
consume:
  - product
  - problem
  - users
  - goals
  - user_experience
  - requirements
  - constraints
  - scope
  - success_criteria
  - conflicts

produce:
  - resolved_context
```

---

## Core Principle

Resolve the decision, not the symptom.

A conflict may appear in one section while its real cause exists somewhere else.

For example:

```text
Requirement conflicts with constraint
```

may actually mean:

```text
Goal was defined incorrectly
```

Do not blindly modify the artifact where the conflict was detected.

Trace the conflict back through the product definition and determine which decision is actually wrong.

---

## User-Owned Decisions

Not every conflict should be resolved autonomously.

First determine whether the conflict can be resolved from:

- explicit user decisions;
- established product facts;
- previously accepted constraints;
- logical consequences of the existing context.

If the conflict represents a genuine product choice between multiple materially different outcomes, the user must decide.

Do not choose on behalf of the user.

Examples:

- which user group should be prioritized;
- which competing goal is more important;
- whether a related workflow belongs in scope;
- which of two materially different UX behaviours is intended.

---

## When This Skill Runs

The skill is invoked by the orchestrator when another skill reports a conflict.

It must not be part of the normal linear pipeline unless a conflict has been detected.

The normal workflow is:

```text
Linear pipeline
      ↓
Conflict detected
      ↓
goga-define-resolve
      ↓
Updated context
      ↓
Continue pipeline
```

---

## Process

### 1. Understand the conflict

Read the reported conflicts together with the complete product context.

Determine:

- what decisions contradict each other;
- where the contradiction originates;
- which decisions depend on the conflicting decision;
- whether the conflict is real or caused by an incorrect interpretation.

Do not resolve the conflict using only the local section where it was detected.

---

### 2. Trace dependencies

Follow the affected decision through the product definition:

```text
Problem
Users
Goals
User Experience
Requirements
Constraints
Scope
Success Criteria
```

Determine which parts of the context depend on the conflicting decision.

A change to one decision may require updating several downstream decisions.

---

### 3. Identify the root decision

Determine the smallest product decision that can resolve the conflict.

Prefer changing the root decision over introducing additional exceptions.

For example:

```text
Bad resolution:

Keep two contradictory requirements and add
an exception explaining when each one applies.

Better resolution:

Clarify the underlying business rule and update
the requirements to follow it.
```

Avoid accumulating special cases.

---

### 4. Challenge both sides

Do not assume that the earlier decision is correct.

Challenge:

- the newly produced decision;
- the existing product context;
- the original user request;
- the underlying assumptions.

Determine which interpretation best explains the complete product context.

---

### 5. Preserve established facts

Do not change information merely to eliminate a conflict.

Distinguish between:

```text
Fact
Known product behaviour or explicit constraint.

Decision
A product choice made during this definition process.

Assumption
An interpretation that may be challenged.

Proposal
A possible way to solve the problem.
```

Facts should not be rewritten without evidence.

Decisions and assumptions may be reconsidered.

---

### 6. Resolve ambiguity

If the conflict exists because the product decision is ambiguous, make the smallest decision necessary to remove the ambiguity.

Prefer:

> Users can cancel an order until preparation begins.

over:

> Users can generally cancel orders, except in some cases.

The resolved decision should be precise enough for downstream skills to use without reinterpretation.

---

### 7. Update the affected context

After resolving the conflict, update every affected product decision.

For example, if the user experience changes:

```text
User Experience
    ↓
Requirements
    ↓
Scope
    ↓
Success Criteria
```

may also require revision.

Do not update unrelated sections.

---

### 8. Re-check the complete model

After applying the resolution, verify that:

- the original conflict is gone;
- no new contradiction was introduced;
- goals still address the problem;
- the user experience still supports the goals;
- requirements still describe the experience;
- constraints are respected;
- scope remains coherent;
- success criteria still demonstrate the intended outcome.

If the resolution creates another conflict, continue resolving it within the same invocation.

Do not return a partially inconsistent context.

---

## Decision Principles

When multiple resolutions are possible, prefer the option that:

1. best solves the original problem;
2. best serves the identified users;
3. preserves established product behaviour when possible;
4. introduces the least unnecessary complexity;
5. minimizes scope expansion;
6. avoids adding exceptions;
7. keeps the product definition internally consistent.

Do not optimize for implementation convenience.

---

## User Input

Ask the user when the conflict cannot be resolved from the established context without making a new product decision.

The question must present the actual decision.

Prefer:

> Should the existing workflow remain unchanged for administrators, or should the new behaviour apply to them as well?

over:

> Can you clarify the requirements?

Do not ask the user to resolve technical implementation choices.

After receiving the answer, update the affected decisions and continue resolving downstream consequences.

---

## Do Not Resolve With Technical Decisions

Do not resolve a product conflict by choosing:

- a programming language;
- a framework;
- an API;
- a database;
- an architecture;
- an implementation pattern.

If a technical decision is genuinely required to resolve the product conflict, report that the product definition depends on an engineering decision rather than inventing one.

---

## Avoid Scope Expansion

Do not resolve conflicts by automatically adding more functionality.

For example:

```text
Conflict:
The user cannot complete the flow in one of the identified states.

Bad resolution:
Add a completely new workflow for that state.

Better:
Determine whether that state is actually in scope.
```

Only expand scope when the original product goals genuinely require it.

---

## Output

Produce the updated product context affected by the resolution.

The result must contain:

```yaml
resolved_context:
  problem: ...
  users: ...
  goals: ...
  user_experience: ...
  requirements: ...
  constraints: ...
  scope: ...
  success_criteria: ...
```

Only include sections that were changed or are required to understand the resolution.

Also provide:

```yaml
resolution:
  decision: |
    <the product decision that resolved the conflict>

  rationale: |
    <why this decision is consistent with the complete context>
```

The resolution must leave the product definition internally consistent.

Do not return unresolved contradictions.

If a required product decision genuinely cannot be determined without user input, ask the user before producing the final resolution.
