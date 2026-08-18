---
name: goga-define-challenge
description: 
---

# goga-define-challenge

## Purpose

Challenge the complete product definition before the PRD is generated.

Review the entire product context as one coherent system and identify contradictions, missing decisions, logical gaps, unsupported assumptions, and product behaviours that remain insufficiently defined.

The challenge is a validation stage, not another product-design stage.

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

produce:
  - conflicts
```

---

## Core Principle

Do not ask whether the PRD sounds reasonable.

Ask whether the product decision is internally consistent and sufficiently complete to be handed to engineering for technical design.

The challenge must actively try to break the current product definition.

Look for contradictions across the entire context, not only within the most recently produced section.

---

## Product Interview

The challenge stage must distinguish between:

- a contradiction that can be resolved from the established context;
- a product decision that requires the user's choice.

If the context contains enough information to resolve a contradiction, resolve it through the normal resolver flow.

If two or more materially different product interpretations remain valid and the context does not establish which one is intended, report the decision as requiring user input.

Do not choose an interpretation merely because it appears more reasonable.

---

## Validation Model

Review the following relationships:

```text
Product
  ↓
Problem
  ↓
Users
  ↓
Goals
  ↓
User Experience
  ↓
Requirements
  ↓
Constraints
  ↓
Scope
  ↓
Success Criteria
```

Every stage should support the next one.

The complete model must also remain consistent in the reverse direction:

```text
Success Criteria
       ↓
Goals
       ↓
Problem
```

---

## Process

### 1. Validate the problem

Check:

- Is the problem clearly defined?
- Is it a real product problem rather than a feature request?
- Is it specific enough to guide the solution?
- Does the proposed product change actually address it?

Report a conflict if the problem remains solution-oriented, contradictory, or insufficiently defined.

---

### 2. Validate the users

Check:

- Are the relevant users identified?
- Is the primary user clear?
- Are secondary actors included when they materially affect the solution?
- Does the user context explain how the problem occurs?
- Are different users incorrectly treated as having identical needs?

Report a conflict when the user model prevents the product solution from being unambiguous.

---

### 3. Validate the goals

Check:

- Does every important goal address the problem?
- Are goals expressed as outcomes rather than features?
- Are goals compatible with one another?
- Can the described user experience actually achieve them?

Look for goals that are:

- unrelated to the problem;
- duplicates;
- mutually incompatible;
- implementation-oriented.

---

### 4. Validate the user experience

Check:

- Is there a clear entry point?
- Is the primary scenario complete?
- Are meaningful alternative paths covered?
- Are important failures covered?
- Are important states defined?
- Does the user understand what happened after significant actions?
- Can the user recover from relevant failures?
- Are consequences of important actions clear?

Look for gaps that would force engineering to invent user-visible behaviour.

---

### 5. Validate requirements

Check:

- Does every important part of the experience have supporting requirements?
- Are requirements observable and testable?
- Are important business rules explicit?
- Are permissions defined where relevant?
- Are important states represented?
- Are failure behaviours defined?
- Do requirements accidentally prescribe implementation?
- Are there duplicate or contradictory requirements?

The key question is:

> Could engineering make a technical design without having to invent product behaviour?

If not, report the missing product decision as a conflict.

---

### 6. Validate constraints

Check:

- Are all relevant product constraints represented?
- Do requirements respect them?
- Do goals remain achievable under them?
- Are technical preferences incorrectly represented as constraints?
- Are constraints mutually compatible?

Do not invent constraints during the challenge.

---

### 7. Validate scope

Check:

- Does scope contain everything required to solve the problem?
- Does scope exclude unrelated work?
- Are any requirements accidentally outside the scope?
- Does the scope introduce capabilities that are not justified by the goals?
- Is scope being used to hide an unresolved product decision?

---

### 8. Validate success criteria

Check:

- Can success actually be demonstrated?
- Does every important goal have evidence of success?
- Do criteria reflect meaningful outcomes?
- Are quantitative metrics used only where necessary?
- Are criteria compatible with requirements and constraints?
- Could every criterion pass while the original problem remains unsolved?

---

## Cross-Context Contradictions

Pay special attention to contradictions between distant parts of the context.

Examples:

### Goal vs Constraint

```text
Goal:
Users can complete the operation immediately.

Constraint:
The operation requires external approval before completion.
```

### Experience vs Requirement

```text
Experience:
The user can retry after failure.

Requirement:
The operation becomes unavailable after the first failure.
```

### Requirement vs Scope

```text
Requirement:
Administrators configure the behaviour.

Scope:
Administrative configuration is explicitly out of scope.
```

### Problem vs Goal

```text
Problem:
Users cannot understand the current state.

Goal:
Reduce the time required to perform the operation.
```

The second goal may not actually solve the stated problem.

---

## Hidden Assumptions

Identify assumptions that materially affect the product decision.

Examples:

- assuming users understand an unfamiliar state;
- assuming a user has information that the product does not provide;
- assuming an operation is always available;
- assuming another workflow can remain unchanged;
- assuming an external actor always responds;
- assuming a particular user has permission.

Do not report trivial assumptions.

Only report an assumption when the product could behave differently depending on whether it is true.

---

## Missing Behaviour

Challenge the model for undefined behaviour that is necessary for implementation.

Look especially for:

- state transitions;
- permissions;
- errors;
- retries;
- cancellation;
- irreversible actions;
- repeated actions;
- conflicting states;
- user-visible consequences.

Do not require every theoretical edge case to be defined.

Focus on behaviour that can materially change the product outcome.

---

## Scope Creep

Look for functionality that entered the definition without a clear connection to the original problem.

Ask:

> If this item were removed, would the product still solve the original problem?

If yes, challenge whether it belongs in the current scope.

---

## Technical Leakage

Identify technical decisions that have accidentally become product requirements.

Examples:

- specific database;
- programming language;
- framework;
- internal service;
- API design;
- implementation algorithm.

Do not report a technical detail as a conflict if it is explicitly an external constraint.

The challenge should distinguish between:

```text
Product constraint
and
Engineering decision
```

---

## Conflict Classification

When a problem is found, classify it by type.

Use one of:

```text
contradiction
missing_decision
logical_gap
unsupported_assumption
scope_conflict
technical_leakage
```

Example:

```yaml
conflicts:
  - type: contradiction
    description: |
      The requirements allow the user to cancel an order after
      preparation begins, while the established constraint forbids it.

  - type: missing_decision
    description: |
      The experience defines a retry action after failure, but
      does not define what happens after repeated failures.
```

---

## Do Not Resolve Conflicts

This skill identifies conflicts.

It must not resolve them.

Do not:

- choose between conflicting decisions;
- rewrite requirements;
- modify goals;
- change scope;
- invent missing behaviour;
- silently remove contradictions.

Return the conflict to the orchestrator.

The orchestrator will invoke `goga-define-resolve`.

---

## False Positives

Do not treat every ambiguity as a question.

Ask the user only when different reasonable interpretations would materially change the product outcome.

Minor wording differences, implementation choices, or details that do not affect the product decision should not trigger an interview.

---

## Output

If the product definition is internally consistent:

```yaml
conflicts: []
```

If issues are found:

```yaml
conflicts:
  - type: <type>
    description: |
      <clear description of the problem>
```

Every reported conflict must be:

- specific;
- actionable;
- grounded in the existing context;
- relevant to the product decision.

Do not include recommendations for resolving the conflict.

The result must allow `goga-define-resolve` to understand exactly what needs to be reconsidered.
