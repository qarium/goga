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

## Gap Analysis

- Missing contract entities:
- Incorrect locations:
- Missing re-exports:
- Signature mismatches:
- Existing code that can be reused:
- Test coverage gaps:

## Implementation Detail Decisions

- <Topic>: <decision> (source: brainstorm / confirmed by user)

## Entity Interaction and Data Flow

### Interaction diagram
<!-- Describe or present as mermaid/ASCII how contract entities interact with each other -->

### Data flows
<!-- For each significant scenario: which entities participate, what data is passed, in what order -->

### Dependencies between entities
<!-- Which entities depend on which, initialization order, circular dependencies (if any) -->

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

## Open Questions and Answers

- <Question>: <user answer (if any)>

## Additional Instructions for the Implementation Agent

- <instruction>
