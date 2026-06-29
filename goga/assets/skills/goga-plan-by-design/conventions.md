# General Project Conventions for Contract-Oriented Package Implementation

## Purpose

This file defines **general, language-independent project conventions** for implementing code from package contracts.

These conventions are not tied to a specific programming language.
They define how implementation should be organized relative to:
- cell contracts,
- facade boundaries,
- internal decomposition,
- traceability,
- testing.

Language-specific conventions, such as syntax, typing style, exception style, or naming mechanics, should be defined separately in a language-specific conventions file.

---

## Rule Types

This file contains:
- **Mandatory rules** — must be followed unless an explicit contract or project directive states otherwise
- **Recommended rules** — should be followed when they improve clarity and consistency

When a project contains both general and language-specific conventions:
1. follow the contract first,
2. follow the package boundary and facade obligations second,
3. follow explicit project conventions next,
4. follow target language idioms next.

---

## Scope

These conventions apply within a single user package.

They govern:
- internal code organization,
- public surface vs internal implementation,
- traceability from contract to code and tests,
- test classification,
- project consistency.

These conventions do **not** authorize:
- creating new packages,
- redefining package boundaries,
- modifying user facade contracts.

---

## Internal Cell Structure

### Mandatory
- Implementation may be decomposed into additional internal files within the current cell.
- Internal helpers may be extracted into separate internal modules if this improves clarity, cohesion, reuse, or testability.
- Public facade code and internal helper code must remain clearly distinguishable.
- Internal decomposition must preserve the contract surface and required placement in `location`.

### Recommended
- Group implementation by responsibility so that contract-facing code remains easily discoverable.
- Keep facade assembly logic near the cell surface, and reusable internal details deeper in internal modules.
- Prefer decomposition that simplifies contract coverage tracking and testing.

### Clarification
There is **no** general rule that one public contract entity must map to one implementation file.
Multiple contract entities may legitimately point to the same `location` if the contract provides for this.

---

## Public Surface vs Internal Implementation

### Mandatory
- The public contract surface must remain explicit and stable.
- Internal helper code may be freely added as long as it does not replace or shadow contract entities.
- Internal implementation details must not be treated as a replacement for facade-level contract behavior.
- Planning and coding must clearly distinguish between:
  - public items facing the contract,
  - internal implementation items.

### Recommended
- Keep contract-facing entry points easily identifiable.
- Avoid unnecessary mixing of facade behavior and private implementation details in the same place when separation improves clarity.

---

## Naming Principles

### Mandatory
- Use naming conventions idiomatic to the target language and consistent with the existing project.
- Keep naming consistent with the contract vocabulary wherever possible.
- Use naming that makes public entities, internal helpers, and tests distinguishable by role.

### If the project already has code
- Follow existing project naming patterns unless they directly contradict the contract.

### If the project has no code yet
- Use naming idiomatic to the target language.
- Use the contract vocabulary as the semantic foundation.
- Keep naming consistent between entities, helpers, and tests so the emerging project style starts with a consistent base.

### Recommended
- Prefer names reflecting responsibility and relationship to the contract.
- Let internal helper names reflect support intent, not facade intent.
- Let test names reflect the entity under test, scenario, and expected behavior.

---

## Traceability Rules

### Mandatory
Implementation and tests must be traceable back to the contract.

For any meaningful unit of implementation or test, it must be possible to determine:
- which contract entity it supports,
- which contract property or method it covers,
- whether it supports facade behavior or internal behavior,
- which described requirement it verifies.

### Recommended
- Maintain a clear mapping: contract entity → implementation location → validation → tests.
- Make it easy to verify whether each contract requirement has corresponding implementation and corresponding tests.

---

## Contract-to-Test Mapping

### Mandatory
Every contract element must have explicit test coverage.

At minimum, for each meaningful contract entity and each meaningful contract behavior:
- facade accessibility must be tested,
- declared API shape must be tested,
- behavior described in the contract must be tested.

Descriptions in the contract are not optional.
If a behavior or constraint is described there, test coverage must reflect it.

### Recommended
- Make contract test coverage easily auditable by grouping tests around entities, methods, or behaviors in a way natural to the target language and project.

---

## Test Classification

Tests are classified into three categories.

### 1. Contract Tests
Verify the package's contract surface.

They must cover:
- facade accessibility,
- public API shape,
- method/property signatures.

These tests are written FIRST in each coding task (TDD approach) and are expected to fail initially.

These tests are mandatory.

### 2. Logic Tests
Verify behavioral requirements from contract descriptions.

They must cover:
- positive scenarios,
- negative scenarios,
- edge cases.

These tests are written AFTER implementation in each coding task.

These tests are mandatory.

### 3. Integration Tests
Verify cross-entity interactions and end-to-end scenarios.

They are written as separate tasks after all coding tasks for a package.

They are created when internal complexity or cross-entity interactions justify direct verification.

### Mandatory Rule
Integration tests do **not** replace contract or logic tests.

A package does not have sufficient coverage if only integration tests exist while contract and logic tests per entity are missing.

---

## Test Naming Principles

### Mandatory
Test names must clearly indicate:
- the contract entity or internal item under test,
- the scenario,
- the expected behavior or result.

### Language-Independent Rule
Do not enforce a specific casing style here.
Instead:
- use the naming mechanics natural to the target language and test framework,
- maintain clarity of the covered subject, scenario, and expectation.

### Recommended
A good test name should communicate:
- **who/what** is being tested,
- **under what condition**,
- **what should happen**.

---

## Internal Decomposition Guidelines

### Recommended
- Introduce internal helpers when they reduce duplication or cleanly isolate behavior.
- Decompose internal logic when it improves contract traceability, readability, or testability.
- Prefer internal structure that facilitates absorbing future contract changes.

### Mandatory Boundary
Internal decomposition must remain within the current cell and must not create new cells.

---

## Relationship to Language-Specific Conventions

This file intentionally avoids language-specific rules such as:
- exact naming casing,
- typing mechanics,
- exception mechanics,
- async/sync details,
- import syntax,
- file naming syntax,
- language-specific test framework rules.

These should be defined in a supplementary language-specific conventions file when needed.

This layer of general conventions defines **structural expectations and traceability expectations**, not language syntax policy.
