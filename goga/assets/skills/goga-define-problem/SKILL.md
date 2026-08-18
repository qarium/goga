---
name: goga-define-problem
description: 
---

# goga-define-problem

## Purpose

Define the actual product problem that needs to be solved.

Transform the initial product idea into a clear problem statement that explains:

- what is wrong or missing;
- who is affected;
- in what context the problem occurs;
- why the problem matters;
- what outcome is currently prevented.

The result must describe the problem, not the proposed solution.

---

## Contract

```yaml
consume:
  - product
  - input

produce:
  - problem
```

---

## Core Principle

Do not accept the user's proposed solution as the problem.

A request such as:

> "Add export to Excel."

is not a problem statement.

Determine what problem the requested capability is intended to solve.

For example:

> Users need to share operational data with colleagues, but the current product does not provide a convenient way to transfer the relevant information outside the product.

The proposed Excel export may or may not be the right solution.

Do not decide that at this stage.

---

## Product Interview

The problem must be established with the user, not inferred from the requested feature alone.

Treat the initial request as a hypothesis about the problem.

Before producing the problem definition, identify the decisions that materially affect the problem statement and interview the user about them.

In particular, clarify when necessary:

- who actually experiences the problem;
- what situation triggers it;
- what the user is trying to achieve;
- what prevents the desired outcome;
- whether the request describes a problem or already assumes a solution;
- what makes the problem important.

Do not silently convert a feature request into a problem statement based on assumptions.

Do not stop interviewing merely because one interpretation appears plausible.

Continue until all materially different interpretations of the problem have been resolved.

---

## Process

### 1. Understand the initial request

Analyze the user's original input.

Identify:

- the requested outcome;
- any explicitly stated problem;
- any proposed solution;
- affected users;
- relevant product area;
- known constraints.

Do not assume that the user's initial framing is correct.

---

### 2. Separate problem from solution

Identify whether the request describes:

- a problem;
- a desired outcome;
- a feature;
- an implementation;
- or a mixture of these.

If the input is primarily a proposed solution, reconstruct the underlying problem.

Do not preserve the proposed implementation merely because it was explicitly requested.

---

### 3. Use the existing product context

Use `product` to understand:

- how the product currently works;
- which users are involved;
- existing product behaviour;
- existing capabilities;
- relevant product rules.

Do not redesign the existing product.

Use the context only to understand the problem.

---

### 4. Define the affected user situation

Describe the situation in which the problem occurs.

Answer:

- Who encounters the problem?
- What are they trying to accomplish?
- At what point does the problem appear?
- What prevents them from achieving the desired outcome?

Avoid creating formal personas unless they are necessary to understand the problem.

---

### 5. Determine the impact

Explain why the problem matters.

Consider:

- user friction;
- inability to complete a task;
- loss of information;
- repeated manual work;
- confusion;
- errors;
- inability to achieve an important outcome;
- other meaningful consequences.

Do not invent quantitative business impact without evidence.

---

### 6. Challenge the problem

Actively challenge the initial framing.

Ask yourself:

- Is this actually a problem or just a requested feature?
- Is the stated problem caused by the proposed solution being absent?
- Is the problem already solved somewhere else in the product?
- Is the problem specific enough to solve?
- Is the problem too broad?
- Is the proposed change solving a symptom rather than the underlying problem?
- Is there evidence in the provided context that this problem exists?
- Does the problem matter enough to justify a product change?

If the requested solution does not follow naturally from the problem, preserve the problem independently from the proposed solution.

---

## Problem Statement

Produce a concise problem statement.

A good problem statement should communicate:

```text
Who
+
Situation
+
Problem
+
Impact
```

Example:

> Operations managers need to share selected order data with colleagues who do not use the product, but the current workflow requires them to manually copy the information, which is slow and prone to errors.

Avoid solution-oriented formulations such as:

> Operations managers need an Excel export.

---

## Scope of the Problem

The problem statement must be specific enough to guide the following stages.

Avoid:

> The product has a bad user experience.

Prefer:

> Users cannot determine whether their payment has been completed after returning from the payment provider, causing them to repeat the payment attempt or contact support.

---

## Do Not Solve the Problem

This skill must not:

- define product goals;
- design user experience;
- define requirements;
- define scope;
- propose features;
- select a solution;
- specify technical implementation.

Those decisions belong to later stages of the pipeline.

---

## Interview Completion

Do not treat missing information as the only reason to ask the user.

Ask whenever the problem can reasonably be framed in materially different ways.

A question is required when the answer would change:

- who the problem is for;
- what outcome matters;
- the scope of the problem;
- the reason the problem matters;
- the nature of the requested change.

The skill must not produce `problem` while such decisions remain unresolved.

---

## Conflict Detection

If the product context contradicts the initial problem framing, report a conflict rather than silently choosing one interpretation.

For example:

```yaml
conflict: |
  The request assumes that users cannot perform the operation,
  but the existing product context shows that the operation
  is already available through another workflow.

reason: |
  The proposed change may be solving a different problem than
  the one described in the request.
```

The orchestrator will invoke `goga-define-resolve`.

Do not resolve cross-context conflicts yourself.

---

## Output

Produce only the information necessary to populate `problem`.

The result should be concise, specific, and written in product language.

The output must not contain:

- implementation details;
- technical architecture;
- proposed APIs;
- technology choices;
- solution specifications;
- unresolved alternative problem statements.

The final result must clearly state the problem that the product workflow will address.
