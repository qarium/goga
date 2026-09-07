# Plan Output Template

Result of Phase 1 (structure) + Phase 2 (Usages calibration).
Saved to the path printed by `goga history path -f plan.md`.
This format is compatible with ralphex execution.

---

# Plan: `<topic>`

<!-- `<topic>` — the topic name (the topic directory under `.goga/history/<year>/<topic>/`) -->

## Purpose

A brief statement of what will be implemented or changed.
Cover:
- what the package must provide after implementation,
- the most important gaps between contract and code,
- the overall implementation strategy.

## Context

### Contract Surface

For each contract entity:

**Entity: `<entity name>`**
- Type: `<class | function | re-export>`
- Declared `location`: `<file path>`
- Facade obligation: must be importable from `<package>`
- Mutations: `Type::` declarations (if any)
- Properties: (list with types and descriptions)
- Methods: (list with signatures and descriptions)
- Semantic requirements from descriptions: (key behavioral expectations)
- Imported dependencies: (types from `Imports` used by this entity)
- Annotation context: (if present, include cascade: file level → entity level → method level)

Repeat for each contract entity.

### Re-exports

For each re-export block (`->Name: {}` or `->usage.Type: {}`):
- Name:
- Source: corresponding entry from `Imports` (for internal types, resolved from `Types` list with optional `AS` aliases) or entry from `Usages` (for external types)
- Facade obligation: must be importable from the facade
- Hierarchy constraint (for `Imports` only): source must be at a lower filesystem level

### Usages Context

For each usage entry:
- Name:
- Description or specification reference:
- Relevance to implementation:

### Imported Usages

For each imported usage from `Imports` → `Usages`:
- Name:
- From cell:
- Source path: `{from_path}/.usages/{usage_name}.md`
- Description or specification content:
- Relevance to implementation:

### Local Usages

For each planned local usage file (from the design document):
- File path: `.usages/<category-name>.md`
- Functional category: <what semantic area this category covers>
- Status: <new file / extends existing>
- Related entities: <which entities use practices from this category>
- Description: <what practices this file describes>
- Creation task reference: <Task N>

### External Dependencies

List all external dependencies the implementation depends on:
- External library types from `Usages` (third-party packages)
- References to patterns/conventions from `Usages`
- Required tools or frameworks

## Facts

List all facts explicitly stated in the contract or observable in the workspace:
- ...

## Gap Analysis

Compare the contract with the current visible state of the package:
- Missing contract entities:
- Missing facade exposure:
- Incorrect `location` placement:
- API mismatches:
- Behavioral mismatches:
- Existing code that can be reused:
- Test coverage gaps:
- Missing visibility in workspace or git:

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).

<!-- Repeat this block for each package: -->

### Task 1: `<descriptive title>` (infrastructure)

<Context paragraph: what this task does — Cell structure, facade, re-exports. Provide enough context for an AI agent to implement this task independently.>

**Usages relevant to this task:**
- `<usage name>`: <specific information — what to use, how to call it, what it provides>
  (This section is populated during Phase 2 calibration. If no relevant Usages exist for this task, omit this section.)

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] <specific implementation step 1 — e.g., "Create file `path/to/location.{ext}`">
- [ ] <specific implementation step 2 — e.g., "Add re-export `EntityName` to facade">
- [ ] Verify facade accessibility: <facade check command>
- [ ] Lint: <lint command> — fix formatting if necessary

### Task 2: `<descriptive title>`

<Context paragraph: what this task does, which contract entities it covers, relevant imports/annotations. Provide enough context for an AI agent to implement this task independently.>

**Usages relevant to this task:**
- `<usage name>`: <specific information>

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: <specific tests — facade accessibility, API shape, method signatures for entities in this task> (expected to fail at this stage)
- [ ] **Code**: <specific implementation step 1>
- [ ] **Code**: <specific implementation step 2>
- [ ] **Code**: <specific implementation step N>
- [ ] **Interface verification**: run the contract tests above — <entity test run command> — all must pass
- [ ] **Logic tests**: <specific behavioral tests — positive, negative, edge cases from the plan>
- [ ] **Debugging**: <run all tests command> — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: verify all contract obligations — facade, API shape, behavior
- [ ] **Lint**: <lint command> — fix formatting, apply decomposition if necessary

Continue for all coding tasks **for this package**.

### Task N: Integration tests for `<scope>`

<Context: which cross-entity scenarios are being tested for this package>

**Usages relevant to this task:**
- `<usage name>`: <specific information — e.g., mocking instructions, test fixtures>

- [ ] Create test file <test file>
- [ ] Test cross-entity interaction: <specific scenario>
- [ ] Test edge case: <specific edge condition>
- [ ] Run validation: <test run command>

<!-- Repeat the entire block (coding tasks + integration tests) for the next package -->

---

## Validation Commands

- `<command>`: <what it verifies>
- `<command>`: <what it verifies>
- <run all tests command>: Run all tests
- <facade check command>: Verify that all facade entities are importable

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is accessible from the facade
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior
- [ ] Contract dependencies are met
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them
- [ ] No package boundary was expanded
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (Phase 2 calibration)
