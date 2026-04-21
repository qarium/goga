# Design Document Template

Output of Phase 0 (Analysis & Design).
Saved to `docs/design/<feature-name>.md`.

This is a **complete architectural solution** — everything is thought through to the smallest detail, but not yet planned how to code (that's the Plan artifact from Phase 1 + 2).

If a section cannot be completed because information is unavailable, keep the section and explicitly state what is unavailable.

---

# Design Document: `<feature-name>`

## Contract Changes

### Modified CODEMANIFEST files
- `<path>`: <brief description of changes>

### New entities
- `<Entity>` — <description, location>

### Modified entities
- `<Entity>` — <what changed>

### Deleted entities
- `<Entity>` — <reason/context>

### Changes in Usages
- `<usage>`: <what changed>

### Changes in Annotations
- `<level>`: <what changed>

## Facts

- <fact directly stated in the contract or observable in the workspace>

## Assumptions

- <Assumption>: <basis> (criticality: <low/medium/high>, safe to proceed without confirmation: <yes/no>)

## Open Questions

- <Question>: <user answer (if any)>

## Gap Analysis

- Missing contract entities:
- Incorrect locations:
- Missing re-exports:
- Signature mismatches:
- Existing code that can be reused:
- Test coverage gaps:

## Contract Consistency

<!-- Track cross-entity contract interaction issues found during analysis -->

### Interface ↔ Type consistency
<!-- For each entity that accepts/returns imported types: does the type shape match expected usage? -->
- <entity> ↔ <type>: <consistency status or issue found>

### Type ↔ Mutation consistency
<!-- For each Type:: mutation: is the base type resolvable, is the mutation target compatible? -->
- <mutation>: <consistency status or issue found>

### Interface ↔ Interface consistency
<!-- For interacting entities: do output/input types match, do shared references agree? -->
- <entity A> ↔ <entity B>: <consistency status or issue found>

### Annotations ↔ Entity consistency
<!-- Do annotations reference types/usages/parameters that exist in current CODEMANIFEST context? -->
- <entity> annotations: <consistency status or issue found>

## CODEMANIFEST Changes

<!-- Document all CODEMANIFEST edits made during design with justification -->

### Applied changes
- `<file>`: <what changed — before → after> (reason: <insufficient/inconsistent/interaction error>)

### Skipped issues
- `<file>`: <issue description> (reason for skipping: <user decision>)

## Implementation Detail Decisions

- <Topic>: <decision> (source: brainstorm / confirmed by user)

## Entity Interaction and Data Flow

### Interaction diagram
<!-- Describe or present as mermaid/ASCII how contract entities interact with each other -->

### Data flows
<!-- For each significant scenario: which entities participate, what data is passed, in what order -->

### Dependencies between entities
<!-- Which entities depend on which, initialization order, circular dependencies (if any) -->

## Code Stack Trace

<!-- For each contract entry point (method, function, constructor), trace the full logical chain -->

### Trace: `<Entity.method>` or `<function>`

#### Chain
1. **Entry**: <what triggers this path>
2. **Step**: <what happens, what is passed forward> → checkpoint: <type/logic verified?>
3. **Step**: <what happens, what is passed forward> → checkpoint: <type/logic verified?>
4. ... continue until output
5. **Output**: <final result, form, destination>

#### Checkpoints summary
- <checkpoint 1>: <verified/issue found — describe>
- <checkpoint 2>: <verified/issue found — describe>

#### Issues found during tracing
- <issue>: <resolution>

## Design Decisions per Entity

<!-- For each contract entity (new and modified): -->

### `<Entity>`
- **Responsibility**: <what this entity does, its role in the system>
- **Pattern**: <chosen implementation pattern and why>
- **State management**: <stateful/stateless, how state is stored, lifecycle>
- **Error handling**: <what errors are possible, how they are handled, what is returned to the client>
- **Edge cases**: <what happens at boundaries — empty inputs, overly large data, timeouts>

## Cross-Cutting Concerns

- **Error handling**: <global strategy — exceptions, return codes, error logging>
- **Logging**: <what is logged, at what level, what data is included>
- **Validation**: <where it occurs, what rules, what happens on invalid data>
- **Caching**: <what is cached, eviction strategy, TTL> (if applicable)
- **Concurrency**: <thread safety, locks, async/sync> (if applicable)
- **Retry/resilience**: <retry strategy, circuit breaker> (if applicable)

## Usages Analysis with Rationale

<!-- For each entry from the Usages section: -->

### `<usage name>`
- **What it provides**: <brief description of the library/resource>
- **Where it is used**: <which contract entities use it>
- **Why this one**: <rationale for the choice — why not an alternative>
- **How exactly it is used**: <specific APIs, call patterns>

## Planned Usages Structure

<!-- For each cell being designed, describe the functional categorization of usages -->
<!-- This section is populated after usages categorization with the user (Step 4d) -->

### Cell: `<cell path>`

#### Functional categories
- **`<category name>`** → `.usages/<category-name>.md`
  - Covers: <what functional domain this category represents>
  - Related entities: <which entities use practices from this category>
  - Status: <new file / extends existing>
  - Content: <what practices this file describes>

#### Inline practices
- `<practice name>` in CODEMANIFEST `Usages` — <why inline: short, entity-specific, not reusable>

#### Categorization rationale
- <why these category boundaries were chosen>
- <which existing files are extended and why>

### Imported usages from other cells
<!-- List usages imported from other cells via Imports → Usages -->
- `<usage name>` from `<cell path>` — <why this usage is imported, what it provides>
- Path: `<cell path>/.usages/<usage name>.md`

## Test Scenarios

<!-- For each test category (positive, negative, edge case), generate detailed test cases using the 6-element format -->

### General setup
<!-- Common test setup: fixtures, mocks, base configuration -->

### Source file registry
<!-- List exact files from source that tests should verify -->

---

### Positive tests

#### test_<what>_<scenario>

**Setup**: <exact fixture setup>

**Input**: <exact values>

**Trace**:
1. <step 1>: <what happens>
2. <step 2>: <what happens>
...

**Assertions**:
```
<assert statements>
```

**Sufficiency**: <why this test is needed and what regression it prevents>

---

### Negative tests
<!-- same format per test case -->

### Edge case tests
<!-- same format per test case -->

## Additional Instructions for the Implementation Agent

- <instruction>
