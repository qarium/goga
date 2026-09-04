---
name: goga-design-by-changes
description: Generate a design document from CODEMANIFEST change analysis
---
# Design by Changes

## Purpose

The agent produces a **design document** — a complete architectural specification derived from `CODEMANIFEST` changes.

The design document specifies **what** to implement and **how** to implement it.

The agent does **not** write implementation code. The agent does **not** produce an execution plan.
The agent produces an **architectural specification** where every detail is fully elaborated.

---

### Phase 1: DSL Loading

#### Step 1: Load the DSL specification

The agent invokes `goga-cell` via the **Skill tool**.

Use `goga-cell` for:
- Understanding cell structure (CODEMANIFEST, `.usages/`)
- Interpreting directives (Imports, Usages, Annotations, types, mutations, embeddings)
- Validating syntactic correctness

#### Step 2: Load the DSL application principles

The agent invokes `goga-cookbook` via the **Skill tool**.

Use `goga-cookbook` for:
- Selecting between Entity and Routine
- Determining cell granularity
- Choosing the Usages connection form (file / inline / URL)
- Applying principles for writing usage files in `.usages/`

---

### Phase 2: Change Collection

#### Step 1: Git diff CODEMANIFEST

The agent diffs all CODEMANIFEST files between the current branch and the base branch.

Identify:
- Added, removed, and modified contract entities
- Changes to Usages, Imports, Annotations, and re-exports
- New or deleted CODEMANIFEST files

**Output**: Change list grouped by CODEMANIFEST file with entity-level detail.

#### Step 2: Schema — dependency map

The agent executes `goga schema` to retrieve the cell hierarchy.

Apply `--depends-on <cell_path>` for each path from Step 1 to locate affected cells.

**Output**: Dependency map scoped to affected cells.

---

### Phase 3: Contract Validation

The phase objective: produce a **clean CODEMANIFEST** before deep tracing begins. Resolve all static contract defects at this stage.

#### Step 1: Resolve Usages references

Determine which Usages entries require reading:

1. **Gather changed entities** — from Phase 2
2. **Always read root Usages** — referenced by global `Annotations`
3. **Always read Usages of changed entities** — referenced by entity/method/property annotations
4. **Skip unreferenced Usages** — where no changed entity and no global annotation references them

For each Usages entry with a path value, read the file (paths resolve relative to project root; files reside in `.goga/usages/`).
For each imported usage from `Imports` → `Usages`, read `{from_path}/.usages/{usage_name}.md`.

**Output**: Complete set of resolved Usages specifications.

#### Step 2: Gap analysis

Compare CODEMANIFEST contracts against the current implementation.

Validate with `goga-cell`:
- Signature syntax, `::` mutations, `->` embeddings, `Imports` directives
- `location` correctness (file at the same directory level, with extension, no parent traversal)
- Key casing and YAML document structure (header → body → footer)

Validate with `goga-cookbook`:
- Entity vs Routine selection (`methods`/`properties` present where required, absent where inappropriate)
- Usages connection form (file / inline / URL — conformance to selection criteria)
- Cell granularity (neither too fine-grained nor too coarse)

Check for:
- Missing contract entities
- Invalid `location` values
- Missing re-exports
- Signature and behavior mismatches
- Existing code available for reuse
- Existing local `<current_cell_path>/.usages/` directories and their contents (when present, only for referenced usages)
- Imported usages from other cells via `Imports` → `Usages` — verify that referenced files exist at `{from_path}/.usages/{usage_name}.md`
- Test coverage gaps

**Output**: Gap report with specific files and entities.

#### Step 3: Contract consistency audit

Verify four consistency dimensions.

Validate DSL rules with `goga-cell` at each check:
- `::` mutation rules (base type validation, multi-level chain resolution)
- `->` embedding rules (type must appear in `Imports`)
- Annotation reference rules (backtick syntax, resolvability within document context)
- `Imports` rules (no cross-dependencies; same level or below only)

Validate architectural decisions with `goga-cookbook`:
- When mutation is justified versus a standard `Imports` dependency
- When embedding is justified versus a simple import
- Practice connection correctness (each connected practice is referenced in at least one annotation)

Consistency dimensions:

1. **Interface ↔ Type consistency**: For each entity that accepts or returns a type from `Imports` or `Usages`, confirm the type is declared and its shape matches expected usage (fields, methods, and properties referenced by annotations exist in the source type).

2. **Type ↔ Mutation consistency**: For each `Type::` mutation, confirm:
   - The base type exists in `Imports` (correct name/alias) or `Usages` (qualified name)
   - The mutation target exposes methods/properties compatible with the base type contract
   - Multi-level mutations (`A::B::Cls`) form a valid chain where each segment resolves

3. **Interface ↔ Interface consistency**: For interacting entities (one entity calls methods on another, one entity passes data to another):
   - Output types of entity A match input types expected by entity B
   - Method signatures are compatible at the contract level (not merely at the implementation level)
   - Shared type references point to the same concrete type

4. **Annotations ↔ Entity consistency**: Annotations reference types, usages, and parameters that exist in the current CODEMANIFEST context.

Record each detected inconsistency as a **CODEMANIFEST defect** specifying:
- Exact location in CODEMANIFEST (file, entity, method/property)
- Nature of the inconsistency
- Proposed remediation

#### Step 4: User approval of edits

Present all CODEMANIFEST defects to the user via AskUserQuestion (grouped by file). Offer:
1. **Apply proposed fix** — edit the CODEMANIFEST file
2. **Propose alternative** — the user describes a different fix

Also raise questions about:
- Ambiguous CODEMANIFEST aspects
- Implementation details undefined by DSL
- Critical assumptions

If no defects or questions exist — skip this step.

#### Step 5: Apply edits and validate

For each approved change:

1. Apply the edit to CODEMANIFEST
2. Validate syntactic correctness with `goga-cell` (`::` mutations, `->` embeddings, `Imports` structure, key casing)
3. Validate Usages decisions with `goga-cookbook` (connection form, Entity vs Routine, granularity)
4. Re-run the linter: `goga lint`
5. If the linter reports errors — fix the syntax and re-run
6. Verify the change introduces no new inconsistencies
7. Assess whether usages require updates

**Output**: Clean CODEMANIFEST ready for tracing.

---

### Phase 4: Tracing and Algorithmization

**Design document core.** Starting from the clean CODEMANIFEST produced in Phase 3, perform detailed elaboration.

Validate design decisions at each step using `goga-cell` and `goga-cookbook`.

This phase operates as a **self-correcting loop** — any step may surface a CODEMANIFEST defect that Phase 3 static analysis missed. Each step defines explicit transition conditions.

#### Step 1: Code Stack Trace

For each contract entry point (method, function, constructor), trace the complete logical chain through the code from start to finish:

1. **Entry point**: what initiates this code path (constructor invocation, method call, function call)
2. **Input**: what data arrives, in what form, from where
3. **Each intermediate step**: what transformation, validation, or lookup occurs; what returns; what passes to the next step
4. **External calls**: what imported types provide, what Usages libraries return, how they are invoked. If a Usages entry references a file — read that file to understand the actual API and usage patterns
5. **Output**: the final result, its form, and its destination

Establish **checkpoints** at each step. Verify:
- Does the data type match what the next step expects?
- Is the transformation logically correct?
- Are there intermediate steps the contract implies but does not specify?
- Does external library usage conform to the actual API (verify against Usages specifications)?

**Contract interaction checkpoints** — additionally verify at each step where entities interact:
- **Type flow**: If entity A passes data to entity B, the type declared in A's output must match the type declared in B's input. A mismatch is a CODEMANIFEST consistency error.
- **Mutation compatibility**: If a `Type::` mutation is involved, the mutated type must satisfy the consumer's contractual expectations. If not — record as a CODEMANIFEST defect.
- **Interface contract alignment**: When entity X's method calls entity Y's method, verify alignment on data shape (parameter types, return types, error types).

**Important**: Trace by reading actual source files of existing code and actual library documentation for Usages. If a Usages entry points to a specification file — read it. Do not assume — verify.

- **Checkpoint passed** → Record the trace. Proceed to the next entry point.
- **Checkpoint failed** → Record the defect. Propose a fix to the user via AskUserQuestion.
  Upon approval — apply the edit to CODEMANIFEST, validate (`goga-cell`, `goga-cookbook`, linter), check usages,
  **re-trace** the current entry point. Then continue.

Do not work around contract errors — the defect is in CODEMANIFEST, not in the implementation.

All entry points traced → proceed to Step 2.

#### Step 2: Analysis

Analyze the stack trace results:
- Identify new contract entities and their interactions
- Document implementation details unspecified by DSL (patterns, specific libraries from Usages, architectural decisions)
- Map cross-cutting concerns (error handling, logging, validation, caching, concurrency)
- Identify dependencies between entities
- Surface potential issues and edge cases discovered during tracing
- Map data flows between entities

**Usages/Practices as interface bridges**: A practice (Usages entry) is a **bridging entity** between cells. When an entity must interact with an external library, another cell, or a shared interface — it MUST route through a declared practice. The practice defines the interaction contract. Always route external system connections through the corresponding Usages entry — never bypass a declared practice with a direct dependency.

**Import Usages analysis**: When `Imports` contains `Usages:` groups, the agent:
- Reads each imported usages file at `{from_path}/.usages/{usage_name}.md`
- Analyzes how the imported practice applies to the current cell's entities
- Traces which entities depend on which imported usages
- Documents the traced dependency in the design (imported usages create traceable cross-cell links, not contractual obligations)

- **Analysis completed without defects** → proceed to Step 3
- **Contract defect detected** → Propose a fix via AskUserQuestion.
  Upon approval — apply the edit, validate (`goga-cell`, `goga-cookbook`, linter), check usages,
  **return to Step 1** to re-trace the affected entry points.

#### Step 3: Usages analysis

For each Usages entry:

- **What it provides**: Brief description
- **Where used**: Contract entities that reference it
- **Why chosen**: Justification
- **How exactly**: Specific APIs and call patterns

For each imported usage from `Imports` → `Usages`:
- Read the file at `{from_path}/.usages/{usage_name}.md`
- Document the traceable dependency

- **All practices used correctly** → proceed to Step 4
- **Practice unreferenced in any annotation** → Propose a fix (add annotation reference or remove the practice).
  Upon approval — apply the edit, validate (`goga-cell`, `goga-cookbook`, linter),
  **return to Step 1** to re-trace the affected entry points.

#### Step 4: Cross-cutting concerns

Specify cross-cutting concerns:
- **Error handling**: Global strategy
- **Validation**: Locations, rules, behavior on invalid data
- **Logging**: What is logged, at what level, what data
- **Caching**: What is cached, the strategy (if applicable)
- **Concurrency**: Thread safety requirements (if applicable)

- **Cross-cutting concerns consistent with the contract** → proceed to Step 5
- **Contract defect detected** (e.g., error strategy contradicts method signatures) → Propose a fix via AskUserQuestion.
  Upon approval — apply the edit, validate (`goga-cell`, `goga-cookbook`, linter), check usages,
  **return to Step 1** to re-trace the affected entry points.

#### Step 5: Test scenarios

Generate and **record** test scenarios with full call stacks. Each test is written into the design document — tests are deliverables, not intermediate artifacts.

**6 mandatory elements per test:**

1. **Name**: `<test name>` — self-documenting, following target language conventions
2. **Setup**: Exact configuration (fixtures, mocks, tmp_path contents) with concrete values
3. **Input**: Exact values passed to the function under test
4. **Trace**: Step-by-step code execution — what each function receives, returns, and produces as side effects
5. **Assertions**: Specific checks with exact expected values
6. **Sufficiency**: Why this test exists, what regression it prevents

**Categories:**
- **Positive** — happy path, defaults, explicit values
- **Negative** — invalid input, missing dependencies
- **Edge cases** — empty data, boundary values, idempotency

- **Tests reveal no contract defects** → proceed to Step 6
- **Test exposes type or logic incompatibility in contract** → Propose a fix via AskUserQuestion.
  Upon approval — apply the edit, validate (`goga-cell`, `goga-cookbook`, linter), check usages,
  **return to Step 1** to re-trace the affected entry points.

#### Step 6: Usages and `.usages/` consistency

**Critical distinction — `Usages` directive vs practice directories**: These are **independent** concepts:
- **`Usages` directive** (in CODEMANIFEST header) — internal practices consumed by cell entities (libraries, patterns, conventions). Path values resolve to `.goga/usages/`
- **`<current_cell_path>/.usages/` directory** (in the cell folder) — external documentation for consumers importing this cell. Describes how to work with the cell API

For each affected cell:

1. If `.usages/` does not exist — skip
2. If `.usages/` exists — read and verify:
   - Described APIs match the current CODEMANIFEST
   - Which entities lack coverage
   - Which descriptions are outdated

Use `goga-cookbook` for decision-making: `.usages/` file update rules, usage file authoring principles, criteria for supplementing an existing file versus creating a new one.

**Functional categories**: A cell implements logic divisible into semantic domains. If existing `.usages/` files follow a category-based organization — preserve that structure.

**Decision rules:**
- Changes within an existing domain → **supplement** the existing file
- New functional domain → **create** a new file
- Outdated descriptions → **update** in place
- **Do NOT add CODEMANIFEST `Usages` references pointing to own `.usages/` files** — `.usages/` is consumer documentation, not a source of contractual requirements

Propose changes and obtain user confirmation.

Phase complete → proceed to Phase 5.

---

### Phase 5: Persist the design document

#### Step 1: Write from template

Write results to a file using the template from `design-doc-template.md`.

#### Step 2: Save

Path: the path printed by `goga history path -f design.md`.

- Run `goga history ensure` first if the topic directory does not exist
- Overwrite if the file already exists

---
