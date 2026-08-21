---
name: goga-define-success
description: 
---

# goga-define-success

## Purpose

Define the criteria that determine whether the product change successfully solves the identified problem and delivers the intended user experience.

Transform the problem, goals, user experience, requirements, and scope into a concise set of observable success criteria that can be used to verify the completed product.

These criteria are an intermediate PRD artifact. They are not intended to become a long-term analytics or product-metrics framework.

---

## Contract

```yaml
consume:
  - problem
  - goals
  - user_experience
  - requirements
  - scope

produce:
  - success_criteria
```

---

## Core Principle

Success criteria answer:

> How will we know that the implemented product actually delivers what we decided to build?

They should verify the intended product outcome and behaviour.

Do not turn this stage into a metrics-design exercise.

Only define metrics when a quantitative measure is necessary to make the PRD sufficiently precise for engineering and subsequent validation.

---

## Product Interview

Success criteria must reflect what the user considers a successful product outcome.

Do not invent success metrics or targets merely because they appear useful.

Interview the user when it is unclear:

- what outcome should define success;
- which outcome is most important;
- whether a quantitative measure is actually necessary;
- whether several possible success definitions imply different product priorities.

Prefer observable outcomes over arbitrary metrics.

If a quantitative target is not explicitly justified by the product context, do not invent one.

---

## Process

### 1. Start from the goals

For each important goal, determine what evidence would demonstrate that the goal has been achieved.

Use:

```text
Goal
  ↓
Expected outcome
  ↓
Success criterion
```

A criterion should make success observable rather than merely restating the goal.

---

### 2. Validate the user experience

Check whether the important user scenarios described in `user_experience` can be verified.

Consider:

- successful completion;
- important alternative paths;
- meaningful state transitions;
- failure and recovery behaviour;
- user-visible feedback;
- important consequences of actions.

Not every interaction needs a separate success criterion.

Focus on behaviours that determine whether the intended experience was delivered.

---

### 3. Validate requirements

Review the requirements and identify the behaviours that must be demonstrably true for the product to be considered complete.

Examples:

> A user with an eligible order can cancel it before preparation begins.

> After cancellation, the user can see that the order is no longer active.

These are useful success criteria because they describe observable product behaviour.

---

### 4. Use quantitative metrics only when necessary

A quantitative metric may be appropriate when the product decision genuinely depends on measurable behaviour.

Examples:

- completion rate;
- error rate;
- time required to complete an important task;
- adoption of a newly introduced workflow.

Only include a metric when:

- it directly reflects a goal;
- its meaning is clear;
- the metric can reasonably be measured;
- without it, success would remain materially ambiguous.

Do not invent arbitrary targets.

Do not add metrics merely because PRDs often contain metrics.

---

### 5. Prefer verifiable outcomes

Success criteria should make it possible to answer:

```text
Did we solve the problem?
Did users get the intended outcome?
Does the product behave as specified?
```

Prefer observable statements over vague language.

Avoid:

> The experience should be intuitive.

Prefer:

> A user can complete the primary workflow without needing to leave the product.

---

### 6. Distinguish success criteria from acceptance criteria

Success criteria describe whether the product change achieves the intended outcome.

Acceptance criteria may describe detailed conditions for individual requirements and are normally created later during implementation planning or testing.

For example:

```text
Success criterion:
Users can complete the cancellation workflow successfully.

Acceptance criteria:
- Cancellation is available only before preparation starts.
- Confirmation is shown after cancellation.
- The cancelled order cannot be cancelled again.
```

Do not turn this stage into a complete test specification.

---

## Criterion Quality

A good success criterion is:

### Observable

Its outcome can be verified.

### Relevant

It directly relates to a problem, goal, user experience, or important requirement.

### Specific

It is clear what constitutes success.

### Proportionate

It contains enough detail to remove ambiguity without becoming a full test plan.

### Evidence-based

It does not rely on invented facts or arbitrary thresholds.

---

## Challenge the Criteria

Challenge the success criteria against the full context.

Ask:

- If all criteria pass, have we actually solved the problem?
- Does every important goal have evidence of success?
- Are critical user scenarios represented?
- Are we measuring something meaningful rather than something easy to measure?
- Are any criteria actually requirements rather than success criteria?
- Are any metrics arbitrary?
- Are we missing an important observable outcome?
- Could the product technically satisfy every criterion while still failing the original problem?

If the criteria do not provide credible evidence that the problem has been solved, revise them.

---

## Conflict Detection

Report a conflict when:

- a success criterion contradicts a goal;
- a criterion requires behaviour that is not present in the requirements;
- a criterion contradicts an established constraint;
- success cannot be demonstrated within the defined scope;
- a quantitative target is required but cannot be justified from the available context.

Example:

```yaml
conflict: |
  The success criteria require the workflow to be completed
  immediately, but the defined user experience and requirements
  allow the operation to remain pending.

reason: |
  The criteria describe a stronger outcome than the product
  solution currently guarantees.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Missing Information

Ask the user only when success cannot be meaningfully determined without an important product decision.

Valid questions may concern:

- what outcome should count as success;
- whether a particular user behaviour is essential;
- whether a quantitative target is genuinely required.

Do not ask for technical monitoring or implementation details.

Do not invent metrics or numerical targets.

---

## Do Not Define

This skill must not define:

- analytics architecture;
- monitoring implementation;
- dashboards;
- telemetry systems;
- technical tests;
- test automation;
- development tasks;
- long-term KPI frameworks;
- technical performance budgets unless they are explicitly part of the product requirement.

---

## Output

Produce a concise set of success criteria that demonstrate whether the product change achieves its intended outcome.

The result should provide enough evidence to verify:

- the original problem is addressed;
- important goals are achieved;
- the intended user experience is delivered;
- critical product behaviour works as defined.

Use quantitative metrics only where they materially improve the precision of the PRD.

The final result should remain an intermediate product artifact, not a permanent product analytics specification.
