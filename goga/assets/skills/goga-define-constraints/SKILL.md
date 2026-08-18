---
name: goga-define-constraints
description: 
---

# goga-define-constraints

## Purpose

Identify and document the product constraints that must be respected by the solution.

Transform the existing product context, problem, users, goals, user experience, and requirements into a clear set of constraints that limit or shape the possible product solution.

Constraints describe what the solution must respect. They do not prescribe how the solution should be implemented.

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

produce:
  - constraints
```

---

## Core Principle

A constraint is a condition that the product solution must respect.

It may come from:

- existing product behaviour;
- business rules;
- user expectations;
- regulatory or contractual obligations;
- dependencies outside the product;
- explicitly stated organizational constraints;
- limitations that materially affect the product experience.

A constraint is not a technical preference.

For example:

> Users cannot cancel an order after preparation has started.

is a product constraint.

This is not:

> Store the order state in PostgreSQL.

That is an implementation decision.

---

## Product Interview

Do not infer constraints from technical assumptions, personal preferences, or conventional implementation choices.

Determine which boundaries are intentional product constraints.

Interview the user when it is unclear whether a limitation is:

- mandatory;
- preferred;
- temporary;
- negotiable;
- outside the product decision.

Examples of decisions that may require clarification:

- compatibility requirements;
- supported user groups;
- availability limitations;
- operational boundaries visible to users;
- mandatory business rules;
- regulatory or organizational restrictions when relevant to the product.

Do not turn an engineering preference into a product constraint.

---

## Process

### 1. Inspect the existing product

Identify existing product behaviour that the new solution must preserve.

Consider:

- established user flows;
- existing rules;
- existing states;
- existing permissions;
- existing user expectations;
- behaviour that must not regress.

Do not treat every existing implementation detail as a constraint.

Only preserve existing behaviour when changing it would materially affect the product decision.

---

### 2. Identify business constraints

Determine rules that limit what the product can do.

Examples:

- an action is available only under certain conditions;
- a user cannot modify an object after a particular state;
- specific information must be shown;
- a particular action requires approval;
- a process must follow a defined business rule.

Express the constraint in product language.

---

### 3. Identify user-facing constraints

Consider limitations that directly affect the experience.

Examples:

- users must be able to recover from a failed action;
- a user cannot be asked to repeat information unnecessarily;
- sensitive information must not be shown to unauthorized users;
- an irreversible action must be clearly communicated.

Do not turn general UX preferences into constraints unless they materially restrict the solution.

---

### 4. Identify external constraints

Consider constraints imposed from outside the product itself.

Examples may include:

- contractual obligations;
- regulatory requirements;
- external system behaviour;
- mandatory business processes;
- dependencies controlled by another party.

Include only constraints that are known or explicitly provided.

Do not invent regulatory, legal, or organizational requirements.

---

### 5. Distinguish constraints from requirements

Use this distinction:

```text
Requirement
What the product must do.

Constraint
What the solution must respect while doing it.
```

Example:

```text
Requirement:
The user can cancel an eligible order.

Constraint:
An order cannot be cancelled after preparation begins.
```

A single constraint may influence multiple requirements.

---

### 6. Distinguish constraints from implementation decisions

Do not treat technical choices as constraints unless they are explicitly imposed and genuinely cannot be changed.

Examples that are normally not constraints:

- preferred programming language;
- preferred framework;
- database choice;
- API style;
- internal service structure;
- deployment platform;
- coding conventions.

If such information is provided as an external requirement, preserve it only when it genuinely constrains the product solution.

Do not introduce technical constraints yourself.

---

## Constraint Quality

Each constraint should be:

### Relevant

It materially affects the product solution.

### Explicit

Its meaning is clear.

### Justified

Its origin can be understood from the available context.

### Stable

It represents a condition that the solution must respect rather than a temporary implementation preference.

### Product-oriented

It describes a condition affecting product behaviour, users, or business rules.

---

## Challenge the Constraint Set

Challenge the identified constraints.

Ask:

- Is this actually a constraint or just a preference?
- Is it relevant to the current problem?
- Is it supported by the existing product context?
- Does it contradict a requirement?
- Does it unnecessarily restrict the solution?
- Are we treating an implementation detail as a product constraint?
- Are there known constraints that materially affect the user experience but are missing?

Do not invent constraints merely to make the PRD appear more complete.

---

## Relationship With Requirements

Check:

```text
Requirements
      ↕
Constraints
```

Requirements must be compatible with all established constraints.

If a requirement violates a constraint, report a conflict.

Do not silently weaken either side.

---

## Conflict Detection

Report a conflict when:

- a requirement contradicts a constraint;
- a goal cannot be achieved under the known constraints;
- the user experience violates an established constraint;
- existing product behaviour conflicts with the requested change;
- two constraints are mutually incompatible.

Example:

```yaml
conflict: |
  The requirement allows every user to access the requested
  information, while an existing product constraint limits
  this information to authorized users.

reason: |
  The requirement conflicts with an established access rule.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Missing Information

Ask the user only when a missing constraint materially affects the product decision.

Valid questions may concern:

- business rules;
- mandatory user behaviour;
- existing product limitations;
- external dependencies;
- permissions;
- irreversible actions;
- obligations that the product must respect.

Do not ask about technical implementation.

Do not invent legal, regulatory, or business constraints.

---

## Do Not Define

This skill must not define:

- technical architecture;
- programming languages;
- databases;
- APIs;
- infrastructure;
- implementation patterns;
- development tasks;
- project plans.

Those decisions belong to engineering design.

---

## Output

Produce a concise set of relevant product constraints.

Each constraint should clearly describe:

- what must be respected;
- why it matters when necessary;
- which product behaviour it affects when relevant.

Do not include irrelevant limitations or technical preferences.

The final result must give the following Scope stage a clear understanding of the boundaries within which the product solution must be designed.

Before producing `constraints`, verify that each constraint is intentional.

If removing a supposed constraint would materially change the product decision, confirm it with the user rather than assuming it.
