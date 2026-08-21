---
name: goga-define-goals
description: 
---

# goga-define-goals

## Purpose

Define the product outcomes that should be achieved by solving the identified problem for the relevant users.

Transform the established understanding of the product, problem, and users into a small set of clear product goals.

Goals describe the change we want to create, not the features or implementation used to create it.

---

## Contract

```yaml
consume:
  - product
  - problem
  - users

produce:
  - goals
```

---

## Core Principle

A goal describes an outcome, not a solution.

The skill must answer:

> What should become different if we successfully solve the problem?

Do not turn the user's requested feature into a goal.

For example:

> "Build an export to Excel."

is not a goal.

A better goal is:

> "Allow operations managers to easily share the relevant order data with colleagues who do not use the product."

The specific mechanism used to achieve this belongs to later stages.

---

## Product Interview

Goals are product decisions and must not be inferred from the requested feature alone.

Use the problem and users to formulate candidate outcomes, then validate the intended outcome with the user.

Interview the user when necessary to determine:

- what should change as a result of solving the problem;
- which outcome is most important;
- whether there are multiple competing outcomes;
- what should explicitly not be optimized;
- whether the requested feature is actually the intended outcome.

Do not assume that the requested solution represents the user's actual goal.

If multiple reasonable goals would lead to materially different solutions, present the distinction and ask the user to choose.

---

## Process

### 1. Connect goals to the problem

Review the established `problem`.

For each proposed goal, verify:

```text
Problem
  ↓
Goal
```

The goal must directly contribute to solving the problem.

Do not create goals merely because they sound beneficial.

---

### 2. Consider the relevant users

Use `users` to determine what outcome matters to the people affected by the problem.

Consider:

- what users need to accomplish;
- what currently prevents them;
- what should become easier, possible, clearer, safer, or more predictable;
- what meaningful outcome should result from the change.

Do not restate user personas as goals.

---

### 3. Define product outcomes

Describe the desired change in product terms.

Good goals typically express:

- an outcome users should be able to achieve;
- an improvement in the user experience;
- a capability that removes the identified problem;
- a meaningful change in product behaviour.

Avoid implementation language.

---

### 4. Keep goals focused

Prefer a small number of meaningful goals over a long list.

Do not create separate goals for every requirement or user interaction.

For example, these are usually requirements rather than separate goals:

```text
The user can click the button.
The system shows a confirmation.
The user receives a notification.
```

A goal may be:

> The user can complete the task confidently and understand the result.

---

### 5. Distinguish goals from requirements

Use this distinction:

```text
Goal
What outcome should be achieved?

Requirement
What must the product do to achieve that outcome?
```

Example:

```text
Goal:
Users should be able to determine the current state of their order
without contacting support.

Requirement:
The product must clearly display the current order state.
```

Do not put requirements into `goals`.

---

### 6. Challenge the requested solution

Check whether the proposed solution is actually necessary to achieve the goal.

For example:

```text
Requested:
Add a CSV export.

Underlying goal:
Allow users to transfer selected data to another workflow.
```

The goal should remain independent of the proposed implementation.

Do not reject the user's proposed solution at this stage. Preserve the desired outcome and allow later stages to determine how the product should behave.

---

### 7. Check for missing goals

Look for meaningful outcomes implied by the problem and users but absent from the current goal set.

Consider:

- Is the main user outcome covered?
- Are important secondary users affected by the outcome?
- Does solving the problem require a specific trust, clarity, control, or safety outcome?
- Would achieving the stated goals actually solve the problem?

Do not add speculative goals.

---

## Goal Quality

A good goal should be:

### Relevant

Directly connected to the identified problem.

### User-oriented

Expressed in terms of meaningful user or product outcomes.

### Actionable

Specific enough to guide the next stages.

### Solution-independent

Does not prescribe a particular feature or implementation.

### Limited

Does not introduce unrelated improvements.

---

## Goal Relationship

The final goals should form a coherent chain:

```text
Problem
  ↓
User needs
  ↓
Goals
```

If a goal cannot be explained as a response to the problem or a relevant user need, challenge it.

If solving the stated goals would not adequately address the problem, report a conflict.

---

## Conflict Detection

Report a conflict if:

- a goal contradicts the problem;
- goals require mutually incompatible outcomes;
- a goal contradicts established product behaviour;
- the requested solution cannot reasonably achieve the stated goals;
- an essential outcome is impossible under the known constraints.

For example:

```yaml
conflict: |
  The current goal requires users to complete the workflow
  without leaving the product, while the existing product
  constraint requires this workflow to be completed externally.

reason: |
  The goals and existing product constraints describe
  incompatible product outcomes.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Missing Information

If a meaningful goal cannot be defined because a critical product decision is missing, ask the user for the minimum necessary information.

Do not ask questions about implementation.

Do not create speculative goals to fill gaps.

---

## Do Not Define

This skill must not define:

- user experience;
- user journeys;
- product requirements;
- UI behaviour;
- technical architecture;
- APIs;
- databases;
- implementation details;
- scope;
- success metrics as a separate analytics system.

Success criteria are defined in a later stage.

---

## Goal Decision Check

Before producing `goals`, verify:

- every goal is intentionally chosen;
- no important competing goal remains unresolved;
- goals are outcomes rather than implementation requests;
- the priority between materially conflicting goals is known.

Do not produce goals while a material product trade-off remains implicit.

---

## Output

Produce a concise set of product goals.

Each goal should clearly describe:

- the desired outcome;
- who benefits from it when relevant;
- how it addresses the problem.

Avoid:

- feature lists;
- implementation plans;
- technical details;
- duplicate goals;
- unrelated product improvements.

The final result must provide a clear direction for the subsequent User Experience stage.
