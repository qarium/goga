---
name: goga-define-users
description: 
---

# goga-define-users

## Purpose

Define the users and usage contexts that are relevant to the identified product problem.

Transform the problem into a clear understanding of:

- who encounters the problem;
- what they are trying to accomplish;
- in what context the problem occurs;
- what matters to them in that situation;
- which other actors may participate in the same product flow.

The result must provide enough understanding of the relevant users to design an appropriate product experience.

---

## Contract

```yaml
consume:
  - product
  - problem

produce:
  - users
```

---

## Core Principle

Focus on users relevant to the problem, not on generic personas.

Do not create personas simply because they are a common product-management artifact.

A user is relevant when understanding their goals, context, or behaviour can materially affect the product decision.

---

## Product Interview

Do not infer the user model solely from the project structure or the wording of the request.

Interview the user when multiple actors may be involved and their roles would materially change the product solution.

Clarify when necessary:

- who experiences the problem;
- who initiates the relevant action;
- who receives the outcome;
- who may be affected by the action;
- whether different user groups have materially different needs;
- which user is the primary focus of the current change.

Do not create personas or user groups merely because they are technically present in the product.

The user model must reflect the product decision being made, not the structure of the system.

---

## Process

### 1. Identify the primary user

Determine who directly experiences the problem.

Describe the user in terms of their role in the product and the situation in which they encounter the problem.

Avoid demographic or fictional persona details unless they materially affect the product experience.

---

### 2. Understand the user's context

Determine:

- what the user is trying to accomplish;
- why they are doing it;
- when the problem occurs;
- what triggers the interaction;
- what the user already knows or expects;
- what constraints exist in their situation;
- what happens if they cannot accomplish the task.

Focus on context that can influence product behaviour.

---

### 3. Identify secondary actors

Determine whether other people participate in the relevant product flow.

Examples include:

- a recipient of information;
- an approver;
- an operator;
- a colleague;
- an administrator;
- another customer;
- a person affected by the primary user's action.

Include secondary actors only when their behaviour or expectations affect the product solution.

Do not expand the scope merely because other users exist in the product.

---

### 4. Identify user goals

Determine what each relevant user is trying to accomplish in the context of the problem.

Do not define product goals here.

Distinguish between:

```text
User goal
What the user wants to accomplish.

Product goal
What the product should achieve.
```

For example:

> User goal: quickly understand whether the payment was completed.

is appropriate.

> Product goal: provide a payment status indicator.

belongs to a later stage.

---

### 5. Identify user expectations

Determine what users reasonably expect from the product in this situation.

Consider:

- expected feedback;
- expected control;
- expected visibility;
- expected timing;
- expected consequences of an action;
- expected recovery from errors.

Do not invent expectations without support from the problem or product context.

---

### 6. Challenge the user model

Challenge the assumptions about who the product is being changed for.

Ask:

- Is the identified user actually the person experiencing the problem?
- Are there multiple users with materially different needs?
- Is a secondary actor important enough to affect the solution?
- Are we confusing the buyer, operator, administrator, and end user?
- Does the problem occur in the same way for all identified users?
- Are we introducing users that are irrelevant to the current problem?

If different users require materially different behaviour, preserve that distinction.

---

## Avoid Premature Personas

Do not produce elaborate personas containing:

- age;
- location;
- personality;
- hobbies;
- fictional biography;
- unrelated demographics.

Such information is useful only when it changes the product experience relevant to the problem.

Prefer:

> Support agent handling a customer request during an active support session.

over:

> Anna, 34, lives in Helsinki, enjoys running and has worked in support for seven years.

---

## User Context

For each relevant user, describe enough context to answer:

```text
Who is the user?
What are they trying to accomplish?
When does the problem occur?
What matters to them at that moment?
What constraints affect their behaviour?
```

Keep the description focused on the current product problem.

---

## Missing Information

If the available context is insufficient to determine a critical aspect of the user model, ask the user for the minimum necessary information.

Do not ask questions merely to make the persona more detailed.

Questions should only address information that can materially change:

- the user experience;
- the product behaviour;
- the requirements;
- the scope of the solution.

---

## Conflict Detection

If the existing product context contradicts the current understanding of the users, report a conflict rather than silently choosing an interpretation.

For example:

```yaml
conflict: |
  The problem is currently framed around end customers,
  but the existing product context indicates that the
  described workflow is performed exclusively by support agents.

reason: |
  The user model affects the expected interaction and may
  change the product solution.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Output

Produce only the information necessary to populate `users`.

The result should clearly describe:

- primary user;
- relevant secondary actors, if any;
- user context;
- user goals;
- relevant expectations and constraints.

Do not include:

- product requirements;
- proposed features;
- UI design;
- technical implementation;
- product goals;
- solution decisions.

The final result must provide a sufficiently precise user model for the next stage of the product workflow.

Before producing `users`, verify that the primary user and all materially relevant actors have been established.

If different answers would lead to different product behaviour, ask the user rather than choosing an interpretation.
