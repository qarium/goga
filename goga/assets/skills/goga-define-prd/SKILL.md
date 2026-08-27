---
name: goga-define-prd
description: 
---

# goga-define-prd

## Purpose

Generate the final Product Requirements Document from the validated product definition.

Transform the complete, conflict-free product context into a single PRD that can be handed to engineering as the product source of truth for technical design.

The PRD must preserve the decisions made during the definition process without introducing new product decisions.

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
  - prd
```

---

## Core Principle

The PRD is a representation of decisions that have already been made.

This skill is not a product-design stage.

Do not:

- invent missing requirements;
- redesign the user experience;
- introduce new goals;
- expand scope;
- choose technical solutions;
- resolve contradictions.

If the context is not sufficiently complete or internally consistent, report the issue to the orchestrator instead of generating a misleading PRD.

---

## Preconditions

Before generating the PRD, verify that:

- the problem is defined;
- relevant users are identified;
- goals are established;
- user experience is defined;
- requirements are explicit;
- constraints are known;
- scope is defined;
- success criteria are established;
- no unresolved conflicts remain.

If any of these conditions is not satisfied, do not generate the final PRD.

---

## PRD Structure

The PRD must be generated as a Markdown document with the following structure:

```markdown
# <Product Change Title>

## Problem

## Users

## Goals

## User Experience

## Requirements

## Constraints

## Scope

### In Scope

### Out of Scope

## Success Criteria
```

Use additional subsections when they improve clarity, but do not introduce unrelated product-management artifacts.

---

## 1. Title

Create a concise title that describes the product change.

The title should describe the subject of the change rather than the implementation.

Prefer:

> Order Cancellation Improvements

over:

> Add Cancellation API

---

## 2. Problem

Present the validated problem statement.

The section should explain:

- who experiences the problem;
- in what situation;
- what prevents them from achieving the desired outcome;
- why the problem matters.

Do not weaken or reinterpret the established problem.

---

## 3. Users

Describe the users relevant to the problem.

Include:

- primary user;
- relevant secondary actors;
- important context;
- user goals where necessary to understand the product decision.

Avoid unnecessary persona details.

---

## 4. Goals

Present the established product goals.

Goals must remain outcome-oriented.

Do not convert goals into feature lists.

---

## 5. User Experience

Describe how the product should behave from the user's perspective.

Include, where relevant:

- entry point;
- primary flow;
- meaningful alternative flows;
- important states;
- failure behaviour;
- recovery;
- user-visible feedback;
- consequences of important actions.

The section should be detailed enough that engineering can understand the intended experience without inventing product behaviour.

---

## 6. Requirements

Present the product requirements in a clear and structured form.

Requirements should describe:

- required product behaviour;
- conditions;
- business rules;
- permissions;
- important states;
- failure behaviour;
- required user-visible information.

Do not add implementation details.

Requirements should remain independent of technical architecture.

---

## 7. Constraints

Present the constraints that the solution must respect.

Include only relevant product constraints.

Do not turn technical preferences into constraints.

---

## 8. Scope

Clearly distinguish:

### In Scope

What is included in the current product change.

### Out of Scope

What is explicitly excluded to prevent ambiguity or scope creep.

Do not turn the out-of-scope section into a roadmap.

---

## 9. Success Criteria

Present the criteria that determine whether the product change successfully achieves its intended outcome.

Prefer observable outcomes.

Include quantitative metrics only when they were explicitly established as necessary.

Do not invent targets.

---

## Consistency Preservation

The generated PRD must preserve the following chain:

```text
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

Do not alter one section merely to make the document read better.

If two sections appear inconsistent, the underlying conflict must already have been resolved before this skill runs.

---

## Product Language

Write for:

- Product Owners;
- Product Managers;
- Engineering Leads;
- Engineers who will perform technical design.

Use clear product language.

Avoid:

- marketing language;
- unnecessary product-management jargon;
- implementation terminology;
- vague statements;
- speculative language.

The document should be precise enough to support engineering design while remaining implementation-independent.

---

## Technical Details

Technical details are allowed only when they are necessary to describe product behaviour.

For example:

> The CLI must report whether the operation completed successfully and provide an actionable error when it did not.

is appropriate.

The PRD must not prescribe:

- programming languages;
- frameworks;
- databases;
- service architecture;
- API endpoints;
- internal components;
- implementation algorithms.

Technical design belongs to the ADR and engineering stages that follow.

---

## Challenge Before Writing

Perform a final internal check before producing the document.

Verify:

- Every goal is supported by the user experience.
- Every important user experience behaviour is represented in requirements.
- Requirements respect constraints.
- Scope contains everything necessary to solve the problem.
- Success criteria demonstrate the intended outcome.
- No implementation decisions have leaked into the PRD.
- No unresolved conflict remains.
- No new product decision is being introduced during document generation.

If the context fails this check, do not silently fix it.

Return the issue to the orchestrator.

---

## Output

Produce one complete Markdown PRD.

The document must be self-contained and understandable without access to the intermediate skill outputs.

The PRD must contain only validated product decisions.

The final artifact will be saved by the orchestrator to:

```text
.goga/history/<year>/<topic>/prd.md

<year> is the current year in `YYYY` format (4 digits, zero-padded). Create the directory lazily if it does not exist.
```

Do not create additional PRD files.

Do not modify unrelated documentation.

Do not include a changelog, implementation plan, ADR, task list, or technical design in the PRD.
