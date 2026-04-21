# Output Template for Plan

Output of Phase 1 (structure) + Phase 2 (Usages calibration).
Saved to `docs/plans/<feature-name>.md`.
This format is compatible with ralphex execution.

Design Document template is in `design-doc-template.md`.

If a section cannot be completed because information is unavailable, keep the section and explicitly state what is unavailable.

---

# Plan: `<feature-name>`

## Goal

Concise statement of what will be implemented or changed.
Cover:
- what the package must provide after implementation,
- the most important contract-to-code gaps,
- the overall implementation strategy.

## Context

### Contract Surface

For each contract entity:

**Entity: `<entity name>`**
- Kind: `<class | function | re-export>`
- Declared `location`: `<file path>`
- Facade obligation: must be importable from `<package>`
- Mutations: `Type::` declarations (if any)
- Properties: (list with types and descriptions)
- Methods: (list with signatures and descriptions)
- Semantic requirements from descriptions: (key behavioral expectations)
- Imported dependencies: (types from `Imports` used by this entity)
- Annotations context: (if present, include file-level → entity-level → method-level cascade)

Repeat for every contract entity.

### Re-exports

For each re-export block (`->Name: {}` or `->usage.Type: {}`):
- Name:
- Source: corresponding `Imports` entry (for internal types, resolved from `Types` list with optional `AS` aliases) or `Usages` entry (for external types)
- Facade obligation: must be importable from `__init__.py`
- Hierarchy constraint (for `Imports` only): source must be at a lower filesystem level

### Usages Context

For each usage entry:
- Name:
- Description or spec reference:
- Relevance to implementation:

### Imported Usages

For each imported usage from `Imports` → `Usages`:
- Name:
- From cell:
- Source path: `{from_path}/.usages/{usage_name}.md`
- Description or spec content:
- Relevance to implementation:

### Local Usages

For each planned local usage file (from design document):
- File path: `.usages/<name>.md`
- Description: <what this practice covers>
- Creation task reference: <Task N>

### External Dependencies

List all external dependencies the implementation relies on:
- External library types from `Usages` (third-party packages)
- Pattern/convention references from `Usages`
- Required tools or frameworks

## Facts

List all facts directly stated in the contract or observed in the workspace:
- ...

## Assumptions

List every non-explicit planning inference:
- Assumption:
- Basis:
- Criticality:
- Safe to proceed without confirmation: `<yes | no>`

## Open Questions

List unresolved questions:
- Question:
- Why it matters:
- Blocking in strict mode: `<yes | no>`

## Gap Analysis

Compare the contract with the current visible package state:
- Missing contract entities:
- Missing facade exposure:
- Wrong `location` placement:
- API mismatches:
- Behavioral mismatches:
- Existing code that can be reused:
- Test coverage gaps:
- Missing workspace or git visibility:

---

## Tasks

> **Per-package ordering rule**: Each package's coding tasks are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow).

<!-- For each package, repeat this block: -->

### Task 1: `<descriptive title>` (infrastructure)

<Context paragraph: what this task does — package structure, `__init__.py`, re-exports. Provide enough context for an AI agent to implement this task independently.>

**Usages relevant to this task:**
- `<usage name>`: <specific information — what to use, how to call it, what it provides>
  (This section is populated during Phase 2 calibration. If no Usages are relevant to this task, omit this section.)

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] <specific implementation step 1 — e.g., "Create file `path/to/location.py`">
- [ ] <specific implementation step 2 — e.g., "Add `EntityName` to `package/__init__.py`">
- [ ] Verify facade availability: `python -c "from package import EntityName"`
- [ ] Lint: `ruff check src/` — fix formatting if needed

### Task 2: `<descriptive title>`

<Context paragraph: what this task does, which contract entities it covers, relevant imports/annotations. Provide enough context for an AI agent to implement this task independently.>

**Usages relevant to this task:**
- `<usage name>`: <specific information>

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: <specific tests — facade availability, API shape, method signatures for entities in this task> (expected to fail at this stage)
- [ ] **Code**: <specific implementation step 1>
- [ ] **Code**: <specific implementation step 2>
- [ ] **Code**: <specific implementation step N>
- [ ] **Verify interfaces**: run contract tests from above — `pytest tests/test_<entity>.py -v` — all must pass
- [ ] **Logic tests**: <specific behavioral tests — positive, negative, edge cases from plan>
- [ ] **Debug**: `pytest tests/ -x` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Re-check contracts**: verify all contract obligations — facade, API shape, behavior
- [ ] **Lint**: `ruff check src/` — fix formatting, apply decomposition if needed

Continue for all coding tasks **for this package**.

### Task N: Integration tests for `<scope>`

<Context: what cross-entity scenarios are being tested for this package>

**Usages relevant to this task:**
- `<usage name>`: <specific information — e.g., mocking instructions, test fixtures>

- [ ] Create test file `tests/test_<scope>.py`
- [ ] Test cross-entity interaction: <specific scenario>
- [ ] Test edge case: <specific boundary condition>
- [ ] Run validation: `pytest tests/test_<scope>.py -v`

<!-- Repeat the entire block (coding tasks + integration tests) for the next package -->

---

## Validation Commands

- `<command>`: <what it verifies>
- `<command>`: <what it verifies>
- `pytest tests/ -x`: Run all tests
- `python -c "from package import Entity1, Entity2"`: Verify all facade entities are importable

---

## Done Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is available from the package facade
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior
- [ ] Contract dependencies are respected
- [ ] Re-exports are available from facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verify → logic tests → debug → re-check → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them
- [ ] No package boundary has been expanded
- [ ] No `CODEMANIFEST` files were modified (read-only contract)
- [ ] All validation commands pass
- [ ] Assumptions and open questions are explicitly documented
- [ ] Every Usages entry is referenced in at least one task (Phase 2 calibration)
