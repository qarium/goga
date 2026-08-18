---
name: goga-define-experience
description: 
---

# goga-define-experience

## Purpose

Define the user experience required to achieve the established product goals and solve the identified problem.

Transform the understanding of the product, problem, users, and goals into a complete description of how users interact with the product and what they should experience throughout the relevant scenarios.

The result must describe observable product behaviour from the user's perspective.

---

## Contract

```yaml
consume:
  - product
  - problem
  - users
  - goals

produce:
  - user_experience
```

---

## Core Principle

Describe the experience, not the implementation.

The central question is:

> What does the user do, what does the product show or allow, and what happens next?

The experience must be understandable without knowing how the product is implemented.

Do not prescribe:

- APIs;
- databases;
- services;
- frameworks;
- internal architecture;
- technical workflows.

---

## Product Interview

The user experience must be discovered through interaction with the user.

Do not invent UX decisions merely because one flow appears conventional or obvious.

Identify the product decisions that materially affect the experience and interview the user about them.

Clarify when necessary:

- how the user enters the workflow;
- what the user expects to happen;
- what the primary successful path is;
- which alternative paths matter;
- what should happen when the operation cannot be completed;
- what the user should see after important actions;
- which actions should remain available in different states;
- what recovery behaviour is expected;
- which parts of the experience are intentionally excluded.

When several UX behaviours are reasonable, do not silently select one.

---

## Decision Branches

For each important user scenario, identify materially different behavioural branches.

Examples:

```text
success
failure
retry
cancel
partial completion
already completed
not available
```

Do not enumerate theoretical edge cases.

Interview the user when the expected behaviour of a materially important branch cannot be derived from the existing context.

The scenario is not complete until all materially important branches have a defined product outcome.

---

## Process

### 1. Identify the entry point

Determine how the user enters the relevant experience.

Consider:

- what triggers the interaction;
- where the user is in the product;
- what information or state is already available;
- what causes the user to begin the flow.

The entry point must be connected to the identified problem.

---

### 2. Describe the primary scenario

Describe the expected happy path from the user's perspective.

For each meaningful step, establish:

```text
User action
    ↓
Product response
    ↓
Next user action or outcome
```

Do not describe every click or UI element unless it affects the product behaviour or user decision.

Focus on meaningful interactions and outcomes.

---

### 3. Describe relevant alternative scenarios

Identify situations where the primary scenario changes.

Consider:

- different valid user choices;
- optional actions;
- different user states;
- different product states;
- users arriving from different entry points;
- meaningful variations in the workflow.

Include an alternative only when it can affect the resulting product behaviour.

---

### 4. Describe failure and error scenarios

Explicitly determine what happens when the intended action cannot be completed.

Consider:

- invalid user input;
- unavailable actions;
- failed operations;
- expired state;
- missing information;
- conflicting state;
- permission restrictions;
- external failures visible to the user.

For each meaningful failure, determine:

- what the user sees;
- what the user can do next;
- whether the original action can be retried;
- whether the user's previous work or state is preserved;
- what outcome the user should understand.

Do not leave user-visible failure behaviour undefined.

---

### 5. Describe important states

Identify states that materially change the user experience.

Examples:

- initial;
- loading or processing;
- completed;
- partially completed;
- unavailable;
- failed;
- expired;
- cancelled;
- awaiting user action.

Do not create a state merely because it exists internally.

A state belongs in the user experience only when it changes what the user can see, do, or understand.

---

### 6. Define feedback and communication

For meaningful user actions, determine what feedback the product provides.

Consider:

- confirmation;
- progress;
- status;
- success;
- failure;
- warnings;
- consequences of the action;
- next available action.

The user should be able to understand what happened and what they can do next.

Avoid prescribing exact copy unless the wording itself is a product requirement.

---

### 7. Consider reversibility and consequences

For actions that change user or product state, determine:

- whether the action can be undone;
- when it becomes irreversible;
- whether confirmation is required;
- what consequences the user should understand;
- what happens if the user leaves the flow.

This is especially important for destructive, financial, irreversible, or consequential actions.

---

### 8. Consider interruption and recovery

Determine what happens when the user:

- leaves the flow;
- refreshes or returns later;
- loses the current session;
- retries an action;
- repeats an action;
- encounters an intermediate failure.

Only include cases that can materially affect the intended experience.

---

### 9. Check the experience against goals

Verify:

```text
Goals
  ↓
User Experience
```

The described experience must provide a credible way for users to achieve the established goals.

If a goal cannot be achieved through the described experience, identify the problem rather than silently changing the goal.

---

## Experience Completeness

Before producing the result, verify that the relevant scenarios answer:

- How does the user enter the flow?
- What is the primary path?
- What meaningful choices can the user make?
- What happens when an action succeeds?
- What happens when an action fails?
- What states can materially affect the experience?
- What does the user see or understand at important transitions?
- What can the user do next?
- What happens when the user leaves or repeats the flow?
- What are the consequences of important actions?

Do not expand the flow indefinitely. Cover scenarios that materially affect the product decision.

---

## User Experience vs Requirements

Keep the distinction clear.

### User Experience

Describes the interaction and expected experience.

> The user submits the cancellation request and sees that the order is being cancelled.

### Requirement

Describes required product behaviour.

> The product must display a cancellation-in-progress state after the user submits the cancellation request.

The experience should provide enough detail for the Requirements stage to derive precise product behaviour.

---

## Challenge the Experience

Challenge the proposed experience against:

- the problem;
- users;
- goals;
- existing product behaviour.

Ask:

- Does this actually solve the user's problem?
- Can the user achieve the established goals?
- Are important user decisions supported?
- Are obvious failure scenarios covered?
- Are important consequences understandable?
- Does the experience introduce unnecessary complexity?
- Does it contradict existing product behaviour?

Do not redesign unrelated parts of the product.

---

## Conflict Detection

Report a conflict when the experience cannot be made consistent with the existing product context or established decisions.

Examples:

```yaml
conflict: |
  The proposed flow requires the user to complete the action
  from the order page, but the existing product context shows
  that the action is only available after entering the support flow.

reason: |
  The proposed entry point contradicts existing product behaviour
  and requires a product decision before the workflow can continue.
```

Another example:

```yaml
conflict: |
  The goal requires the user to complete the task immediately,
  but the proposed experience introduces a mandatory asynchronous
  approval step.

reason: |
  The experience prevents the user from achieving the established goal.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Missing Information

Ask the user only when a missing product decision materially affects the experience.

Examples of valid questions:

- What should happen when the operation cannot be completed?
- Which user should be allowed to perform this action?
- What should the user see after the action succeeds?
- Is the action reversible?

Do not ask for implementation details.

Do not ask questions whose answers can reasonably be inferred from the existing context.

---

## Do Not Define

This skill must not define:

- technical implementation;
- API contracts;
- data models;
- architecture;
- databases;
- programming languages;
- implementation tasks;
- detailed acceptance tests;
- project plan.

It may describe product behaviour that will later require technical implementation.

---

## Output

Produce a coherent description of the user experience covering the relevant scenarios.

The result should make it possible for the next stage to derive product requirements without having to invent missing user-visible behaviour.

The output should include, where relevant:

- entry point;
- primary scenario;
- alternative scenarios;
- failure scenarios;
- important states;
- feedback;
- consequences;
- interruption and recovery behaviour.

Do not turn the result into a technical specification.

The final result must describe a complete enough user experience to guide the Requirements stage.
