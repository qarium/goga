---
name: goga-define-requirements
description: 
---

# goga-define-requirements

## Purpose

Define the product requirements that describe what the product must do to deliver the established user experience and achieve the agreed product goals.

Transform the product context and user experience into explicit, observable, and testable product behaviour.

The result must be detailed enough for engineering to begin technical design without requiring product decisions to be invented.

---

## Contract

```yaml
consume:
  - product
  - problem
  - users
  - goals
  - user_experience

produce:
  - requirements
```

---

## Core Principle

A requirement describes required product behaviour.

It answers:

> What must the product do?

It must not answer:

> How should engineers implement it?

For example:

> When the user cancels an eligible order, the product must show that cancellation is in progress.

is a product requirement.

This is not:

> The frontend must call `POST /orders/{id}/cancel`.

The second describes implementation.

---

## Process

### 1. Derive requirements from the experience

Review the complete `user_experience`.

Identify every meaningful product behaviour required to make that experience possible.

Trace:

```text
Goal
  ↓
User Experience
  ↓
Requirement
```

Every significant requirement should have a clear reason to exist in the user experience.

Do not create requirements that are not needed by the established product experience.

---

### 2. Define observable behaviour

Requirements should describe behaviour that can be observed from outside the implementation.

Prefer:

> The user can retry the operation after a recoverable failure.

over:

> The retry handler must invoke the operation again.

The requirement should remain valid regardless of the implementation approach.

---

### 3. Cover the primary scenario

Define the behaviour required for the main user flow.

For each meaningful user action, determine what the product must do.

Consider:

- accepted actions;
- resulting state;
- displayed information;
- available next actions;
- completion behaviour.

Do not describe trivial UI details unless they materially affect the product behaviour.

---

### 4. Cover alternative scenarios

Translate meaningful alternative user paths into requirements.

Consider:

- different valid choices;
- different product states;
- optional actions;
- different user roles;
- repeated actions.

Do not duplicate requirements when the same behaviour applies across multiple scenarios.

---

### 5. Cover failure scenarios

Define product behaviour for relevant failures.

For each meaningful failure, establish:

- what the product must communicate;
- whether the user can retry;
- whether the previous state is preserved;
- what action is available next;
- whether the failure changes the product state.

Do not leave important failure behaviour implicit.

---

### 6. Cover important states

Where the user experience defines meaningful states, describe the required product behaviour for those states.

Examples:

```text
Initial
Processing
Completed
Failed
Unavailable
Cancelled
Expired
```

Only include states that affect observable product behaviour.

Do not expose internal implementation states as requirements.

---

### 7. Define business rules

Capture rules that determine product behaviour.

Examples:

- who can perform an action;
- when an action is available;
- when an action becomes unavailable;
- what conditions must be satisfied;
- what happens when conditions conflict;
- what information must be preserved.

Rules must be expressed as product behaviour or product constraints.

Do not turn technical validation logic into implementation instructions.

---

### 8. Define permissions and access behaviour

If different users have different capabilities, explicitly define:

- who can perform the action;
- who can view the relevant information;
- what happens when a user is not allowed to perform an action.

Do not specify how authorization is implemented.

---

### 9. Define data visible to the user

When the user experience depends on information, define what information must be available to the user.

For example:

> The product must show the current status of the order and the time at which it was last updated.

Do not specify:

- database fields;
- schemas;
- storage;
- API payloads.

Describe only the product-level information required by the user experience.

---

### 10. Define consistency across scenarios

Check whether the same product concept behaves consistently throughout the experience.

For example, if an order is described as cancelled in one scenario, another relevant scenario must not imply that the same order remains active.

Identify inconsistent behaviour as a conflict.

---

## Requirement Quality

Each requirement should be:

### Observable

Its outcome can be understood from product behaviour.

### Specific

It is clear what the product must do.

### Unambiguous

Different engineers should not derive materially different product behaviour from it.

### Necessary

It exists because of a goal, user need, constraint, or user experience.

### Solution-independent

It does not prescribe technical implementation.

### Testable

Its behaviour can be verified after implementation.

---

## Avoid Implementation Leakage

Do not include:

- programming languages;
- frameworks;
- libraries;
- database schemas;
- classes;
- internal services;
- internal events;
- deployment details;
- API endpoint design;
- implementation algorithms.

A REST API, CLI application, background job, or other technical interface may still require extensive product requirements.

Describe those interfaces from the user's perspective.

For example:

> The CLI must clearly indicate whether the requested operation succeeded and provide an actionable error when it cannot be completed.

is a product requirement.

Do not define the command implementation, internal architecture, or libraries here.

---

## Challenge the Requirements

Verify the relationship:

```text
Problem
  ↓
Goals
  ↓
User Experience
  ↓
Requirements
```

Challenge the requirement set:

- Does every major goal have supporting requirements?
- Does every major user scenario have defined behaviour?
- Are failure cases covered where they matter?
- Are important product rules explicit?
- Are there contradictory requirements?
- Are there requirements that have no product justification?
- Are requirements accidentally prescribing implementation?
- Can engineering make a technical decision without having to invent product behaviour?

Do not add technical requirements merely to make implementation easier.

---

## Conflict Detection

Report a conflict when requirements cannot be made consistent with the established context.

Examples:

```yaml
conflict: |
  The requirements allow users to cancel an order at any time,
  while the existing product constraint states that cancellation
  is unavailable after preparation begins.

reason: |
  The requirements contradict an established product constraint.
```

Another example:

```yaml
conflict: |
  The user experience requires the operation to be completed
  immediately, while the requirements define the operation as
  asynchronous with no intermediate user-visible state.

reason: |
  The requirements do not support the established user experience.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Missing Information

Ask the user only when a missing product decision prevents a requirement from being defined unambiguously.

Valid questions may concern:

- user-visible behaviour;
- business rules;
- permissions;
- state transitions;
- error behaviour;
- required information;
- consequences of an action.

Do not ask about technical implementation.

Do not ask questions whose answers can reasonably be derived from the existing context.

---

## Do Not Define

This skill must not define:

- technical architecture;
- API contracts;
- database schemas;
- implementation tasks;
- code structure;
- technology choices;
- deployment;
- ADR decisions.

Those belong to the engineering design process that follows the PRD.

---

## Output

Produce a complete set of product requirements.

Requirements should be organized so that engineering can clearly understand:

- what the product must do;
- under which conditions;
- for which users;
- what happens in important states;
- how relevant failures behave;
- what information must be presented;
- what business rules govern the behaviour.

The result must be detailed enough to support technical design while remaining independent of implementation.
