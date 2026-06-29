# Design Document Template

The agent persists this document at `docs/design/<feature-name>.md`.

This is a **complete architectural specification** — every detail fully elaborated.

---

# Design Document: `<feature-name>`

## Contract Changes

### Changed CODEMANIFEST Files
- `<path>`: <summary of changes>

### New Entities
- `<Entity>` — <description, location>

### Changed Entities
- `<Entity>` — <what changed>

### Deleted Entities
- `<Entity>` — <reason/context>

### Usages and Annotations Changes
- `<usage/annotation>`: <what changed>

## Applied Fixes

### Fixed CODEMANIFEST Defects
- `<file>`: <before → after> (reason: <defect type>)

## Entity Interaction and Data Flow

### Interaction Diagram
<!-- ASCII diagram. How entities interact with each other -->

### Data Flows
<!-- Per scenario: participating entities, data passed, execution order -->

### Entity Dependencies
<!-- Which entities depend on which, initialization order -->

## Code Stack Trace

<!-- For each contract entry point (method, function, constructor), trace the full logical chain -->

### Trace: `<Entity.method>` or `<function>`

#### Chain
1. **Input**: <what initiates this path>
2. **Step**: <what happens, what passes downstream> → checkpoint: <type/logic verified?>
3. **Step**: <what happens, what passes downstream> → checkpoint: <type/logic verified?>
4. ... continue to output
5. **Output**: <final result, form, destination>

#### Checkpoint Summary
- <checkpoint 1>: <passed / defect — description>
- <checkpoint 2>: <passed / defect — description>

<!-- Repeat for each entry point -->

## Algorithm Design

<!-- For each contract entity (new and changed): -->

### `<Entity>`

**Responsibility**: <what the entity does, role in the system>

**Algorithm:**
```
1. <step> — <what the entity does, what data>
   → <step result>
2. IF <condition>:
   - <branch A>: <what happens>
   - <branch B>: <what happens>
3. <step> — <what the entity does>
   → <step result>
...
```

**Errors:**
- `<error type>` → <handling> → <what the consumer observes>

**Edge Cases:**
- <case> → <what happens>

<!-- Repeat for each entity -->

## Cross-cutting Concerns

- **Error handling**: <global strategy>
- **Logging**: <what is logged, level, data>
- **Validation**: <where, rules, behavior on invalid data>
- **Caching**: <what, strategy> (if applicable)
- **Concurrency**: <thread safety> (if applicable)

## Usages Analysis

<!-- For each Usages entry: -->

### `<usage name>`
- **What it provides**: <description>
- **Where used**: <entities>
- **Why chosen**: <justification>
- **How exactly**: <specific APIs, patterns>

### Imported Usages
- `<usage>` from `<cell_path>` — <why, what it provides>
  - Path: `<cell_path>/.usages/<usage>.md`

## `.usages/` Update

### Cell: `<cell_path>`

#### Existing Files — Consistency
- **`<file>`** → `<cell_path>/.usages/<file>.md`
  - Status: <current / outdated>
  - Additions needed: <what to add>
  - Updates needed: <what to replace>

#### New Files (if any)
- **`<category>`** → `<cell_path>/.usages/<name>.md`
  - Reason: <new domain>
  - Related entities: <which ones>

## Test Stack Trace

### General Setup
<!-- Fixtures, mocks, base configuration -->

### Source File Registry
<!-- Files under test -->

---

### Positive Tests

#### `test_<what>_<scenario>`

**Setup**: <exact fixture configuration with concrete values>

**Input**: <exact values>

**Trace**:
```
test_function(<input>)
  → target_func(<value>)              # entry point
    → helper_a(<value>)               # step 1
      returns: <value>
    → helper_b(<value>)               # step 2
      side effect: <description>
      returns: <value>
  → assert <check>
```

**Assertions**:
```
<specific checks with exact expected values>
```

**Sufficiency**: <why this test exists, what regression it prevents>

---

### Negative Tests
<!-- same format -->

### Edge Case Tests
<!-- same format -->

## Additional Instructions for the Implementation Agent

- <instruction>
