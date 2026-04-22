# Design by Changes

## Purpose

Creates a **design document** — a complete architectural solution based on changes in `CODEMANIFEST`.

The design document describes **what** and **how** needs to be implemented, but not **in what order** (order is determined by the plan in `plan-by-design`).

You do **not** write implementation code and **not** create an execution plan.
You create an **architectural solution** where every detail has been thought through.

### CODEMANIFEST Editing

`CODEMANIFEST` is the primary contract source, but it may contain **insufficient** or **inconsistent** requirements. When gaps, contradictions, or logical errors are found during analysis — you **must** propose and apply corrections to CODEMANIFEST files (with user approval).

Conditions requiring CODEMANIFEST editing:
- **Insufficient requirements**: missing type declarations, incomplete signatures, absent method/property descriptions that block design
- **Inconsistent requirements**: contradictions between entity interfaces, type mismatches between interacting entities, conflicting annotations
- **Contract interaction errors**: broken type chains across interfaces, incorrect `Imports` references, `Type::` mutations referencing non-existent or incompatible types

All CODEMANIFEST edits must be **proposed to the user** before applying. Never silently modify the contract.

---

## Sources of Truth

Use the following sources jointly, when available:

1. `CODEMANIFEST` — located **inside the package directory** (e.g., `resq/CODEMANIFEST`). Subpackages may have their own CODEMANIFEST files. Read **all** CODEMANIFEST files to build the complete contract.
2. Usages spec files — when a `Usages` entry value is a file path (relative to the `CODEMANIFEST` file location), read that file to get the actual specification content. Usages values can be file paths or inline text.
3. current package file tree
4. current package source files
5. git change context (added, modified, deleted files)

---

## Steps

### Step 1: Git diff CODEMANIFEST

Compare all CODEMANIFEST files between the current branch and the base branch (default from `lead.md` → `default_branch`, fallback `0.0.x`).

Determine:
- added/removed/modified contract entities
- changes in Usages, Imports, Annotations, re-exports
- new or deleted CODEMANIFEST files

If there is no git context — work with the current CODEMANIFEST files as the complete contract.

#### 1a. Schema — dependency impact map

Run `docker run --rm -v .:/project -w /project qarium/goga:latest schema --help` to understand the command capabilities and output structure.

Then run `docker run --rm -v .:/project -w /project qarium/goga:latest schema` to get the full project cell hierarchy. Use `--depends-on <cell_path>` (repeatable) with paths from Step 1 git diff to find all cells affected by the changes — what types and usages they import from changed cells.

This dependency map focuses gap analysis (Step 2) and contract consistency audit (Step 2a) only on affected cells instead of reading all CODEMANIFESTs.

### Step 2: Gap analysis

#### 2-pre. Usages reference resolution

Determine which Usages entries need to be read based on reference links from annotations:

1. **Collect changed entities** — from Step 1 (added/modified entities from git diff, or all entities if no git context)
2. **Always read root Usages** — global `Annotations` in the CODEMANIFEST header may reference Usages via backtick syntax. All Usages referenced by global `Annotations` are always read
3. **Always read changed entities' Usages** — for each changed/created entity, scan its entity-level `annotations` and method/property-level annotations. All Usages referenced by these annotations are always read
4. **Skip unreferenced Usages** — Usages entries not referenced by global `Annotations` AND not referenced by any changed entity's annotations are not read

This means: if a Usages entry exists in the header but no changed entity and no global annotation references it — skip it.

Compare CODEMANIFEST contracts with current implementation:
- missing contract entities
- incorrect locations
- missing re-exports
- signature and behavior mismatches
- existing code that can be reused
- existing local `.usages/` directories and their contents (if any, only for referenced usages)
- imported usages from other cells via `Imports` → `Usages` — verify referenced files exist at `{from_path}/.usages/{usage_name}.md` (only for referenced imports)

#### 2a. Contract consistency audit

Trace cross-entity interactions to detect contract-level errors:

1. **Interface ↔ Type consistency**: for each entity that accepts or returns a type from `Imports` or `Usages`, verify the type is actually declared and its shape matches the expected usage (fields, methods, properties referenced in annotations actually exist in the source type)

2. **Type ↔ Mutation consistency**: for each `Type::` mutation, verify:
   - the base type exists in `Imports` (with correct name/alias) or `Usages` (with qualified name)
   - the mutation target has methods/properties that are compatible with the base type's contract
   - multi-level mutations (`A::B::Cls`) form a valid chain — each segment is resolvable

3. **Interface ↔ Interface consistency**: for entities that interact (one calls another's methods, passes data to another):
   - verify output types of entity A match input types expected by entity B
   - verify method signatures are compatible at the contract level (not just implementation)
   - verify shared type references point to the same actual type

4. **Annotations ↔ Entity consistency**: verify that annotations reference types, usages, and parameters that actually exist in the current CODEMANIFEST context

For each inconsistency found — record it as a **CODEMANIFEST issue** with:
- exact location in CODEMANIFEST (file, entity, method/property)
- what is inconsistent
- proposed fix

Present all CODEMANIFEST issues to the user via AskUserQuestion (grouped by file), offering to:
1. **Apply proposed fix** — edit the CODEMANIFEST file
2. **Skip** — leave as-is, record in design document as a known issue
3. **Propose alternative** — user describes a different fix

### Step 3: Contract validation via linter

Run:
```
docker run --rm -v .:/project -w /project qarium/goga:latest linter
```

Analyze the linter output. Fix syntax errors in CODEMANIFEST if the linter finds them (the linter validates DSL syntax; semantic content of the contract does not change).

### Step 4: Brainstorm

Based on the collected data, perform analysis in the following order:

#### 4a. Code Stack Trace

For each contract entry point (method, function, constructor), trace the full logical chain through the code from start to finish:

1. **Entry point**: what triggers this code path (constructor call, method call, function call)
2. **Input**: what data arrives, in what form, from where
3. **Each intermediate step**: what transformation/validation/lookup happens, what is returned, what is passed forward
4. **External calls**: what imported types provide, what Usages libraries return, how they are called. If a Usages entry references a file — read that file to understand the actual API and usage patterns
5. **Output**: what the final result is, in what form, where it goes

At each step, set **checkpoints** — verify:
- does the data type match what the next step expects?
- is the transformation logically correct?
- are there missing intermediate steps that the contract assumes but doesn't state?
- does the external library usage match its actual API (check Usages specs)?

**Contract interaction checkpoints** — additionally verify at each step where entities interact:
- **Type flow**: if entity A passes data to entity B, does the type declared in A's output match the type declared in B's input? If not — this is a CODEMANIFEST consistency error
- **Mutation compatibility**: if a `Type::` mutation is involved, does the mutated type still satisfy the contract expectations of the consumer? If not — record as a CODEMANIFEST issue
- **Interface contract alignment**: when one entity's method calls another entity's method, do the contracts agree on the data shape (parameter types, return types, error types)?

If a contract interaction checkpoint fails — the issue is in CODEMANIFEST, not in implementation. Propose a fix to the user. Do not work around contract errors in the design.

If at any checkpoint the logic breaks — record the issue and resolve it before continuing.

**Important**: do this trace by reading actual source files for existing code and actual library documentation for Usages. If a Usages entry points to a spec file — read that file. Do not assume — verify.

#### 4b. Analysis

Based on the stack trace results, perform analysis:
- what new contract entities exist and how they interact
- implementation details not specified by the DSL (patterns, specific libraries from Usages, architectural decisions)
- cross-cutting concerns (error handling, logging, validation, caching, concurrency)
- dependencies between entities
- potential issues and edge cases found during tracing
- data flows between entities
- Usages analysis: what each entry provides, where it is used, why it was chosen, how exactly it is used
- **Contract interaction errors**: type mismatches between interacting interfaces, broken type chains in mutations, inconsistencies between entity contracts that interact with each other

**Important — Usages/Practices as interface bridges**: A practice (Usages entry) is a **connecting entity** between cells. If an entity needs to interact with an external library, another cell, or a shared interface — it MUST do so through the declared practice. The practice defines the contract of interaction. When designing how entities connect to external systems, always route through the appropriate Usages entry — never bypass a declared practice with a direct dependency.

**Usages import analysis**: When `Imports` contains `Usages:` groups, the design must:
- Read each imported usage file at `{from_path}/.usages/{usage_name}.md`
- Analyze how the imported practice applies to the current cell's entities
- Trace the dependency: which entities depend on which imported usages
- Document the tracable dependency in the design (imported usages create tracable links between cells but not contractual obligations)

**Local usages design**: For each cell being designed, determine what local `.usages/` files are needed:
- What distinct functional domains exist within this cell's logic?
- For each domain: what practices does it require?
- What practices are already covered by global usages or imported usages?
- Do any existing `.usages/` files in the cell already cover a similar functional domain?
- How do local usages relate to imported usages (do they extend, combine, or replace them?)

#### 4c. Test Scenarios

Generate test scenarios for the feature based on the stack trace and analysis results.

Each test case MUST be written out with all 6 elements:

1. **Name**: `test_<what>_<scenario>` — self-documenting
2. **Setup**: exact fixture setup (tmp_path contents, mocks, patches) — concrete code or description with exact values
3. **Input**: exact values passed to the function/CLI (arguments, types, structure)
4. **Trace**: step-by-step execution through the code with this exact input — what each helper receives, what it returns, what side effects occur at each step
5. **Assertions**: concrete checks with exact expected values (paths, contents, exit codes, output strings) — written as actual assert statements or equivalent
6. **Sufficiency assessment**: why this test is needed and what regression it prevents

Categories to cover:
- **Positive tests** — happy path, default values, explicit values, idempotency
- **Negative tests** — invalid input, unsupported options, missing dependencies
- **Edge cases** — missing directories, existing files preservation, recursive copying, reinstallation

Reference the project test conventions from the Sources of Truth (Usages specs, employee docs) for test structure, naming, and tooling.

### Step 4d: Usages categorization

For each cell being designed, propose a functional categorization of usages.

**Categorization is mandatory** — the agent must propose how practices are organized within the cell's `.usages/` before saving the design.

#### Functional categories

A cell implements logic that can be divided into **functional categories** by meaning — not by entity or by file, but by semantic domain. For example, a cell that parses DSL may have categories: "parsing rules", "validation rules", "AST traversal". A cell that provides CLI may have categories: "command registration", "output formatting", "state management".

Each category becomes a `.usages/<category-name>.md` file describing the practice for that functional area.

#### Categorization process

1. **Analyze cell logic** — identify distinct functional domains within the cell based on entity responsibilities, data flows, and interaction patterns from Step 4b

2. **Check existing `.usages/`** — if the cell already has `.usages/` files:
   - Read each existing file to understand its functional category
   - Map new practices to existing categories where they fit
   - New practices that match an existing category → **extend** that file
   - New practices that don't match any existing category → **create** a new file

3. **Propose categorization** — present to the user:
   - List of functional categories identified
   - For each category: which practices it covers, which entities it relates to
   - Which are new files, which extend existing files
   - Which practices should remain inline in CODEMANIFEST (short, entity-specific, not reusable)

4. **Get user confirmation** — via AskUserQuestion, present the proposal and let the user confirm or adjust category boundaries and names

#### Decision rules

- Practice used by entities from **multiple functional domains** → separate category file
- Practice specific to **one entity's internals** and short → inline in CODEMANIFEST
- Practice that describes **how to work with the cell's API** → category file (consumable by importers)
- Existing `.usages/` file with matching domain → **extend**, do not create parallel files for the same domain

If the cell has no local usages (all usages are global or imported) — still confirm with the user that no local usages are needed.

**Important**: design does NOT create or modify files — it only describes the expected result in the design document.

### Step 5: Questions to the user

Via AskUserQuestion, ask questions about:
- unclear aspects of CODEMANIFEST (contract ambiguities)
- implementation details not determined by the DSL (pattern choices, specific approaches, error handling)
- critical assumptions requiring confirmation
- **CODEMANIFEST changes**: proposed fixes for insufficient/inconsistent requirements collected during Steps 2 and 4

If there are no questions — skip this step.

### Step 5a: Apply approved CODEMANIFEST changes

For each CODEMANIFEST change the user approved in Steps 2a or 5:
1. Apply the edit to the CODEMANIFEST file
2. Re-run the linter: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`
3. If the linter reports errors — fix DSL syntax and re-run
4. Re-verify that the change doesn't introduce new inconsistencies with other entities

After all CODEMANIFEST changes are applied, continue to Step 6 with the updated contract.

### Step 6: Save the design document

Write the results to a file using the template from `design-doc-template.md`.
Path: `docs/design/<feature-name>.md`.

- Ask the user for the feature name if it is not obvious from context.
- Create the `docs/design/` directory if it does not exist.
- If a file with the same name already exists, overwrite it.

---

## Output

- Design document file at `docs/design/<feature-name>.md`
- Understanding of all contract changes
- Resolved questions about implementation details
- Complete architectural solution ready for decomposition into a plan (`plan-by-design`)

---

## Reasoning Discipline

Separate:
- **Facts** — directly stated in the contract or observable in the workspace
- **Assumptions** — cautious inferences necessary for design
- **Open questions** — unresolved ambiguities

Never mix them.

---

## Final Self-Check

Before completing the response, verify:

1. Was a git diff of CODEMANIFEST performed between the current branch and the base branch?
2. Was a gap analysis performed (contract vs current implementation)?
2a. Was a contract consistency audit performed (interface ↔ type, type ↔ mutation, interface ↔ interface, annotations ↔ entity)?
3. Was the linter run: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`?
3a. Were all CODEMANIFEST issues (insufficient/inconsistent requirements) proposed to the user and resolved?
3b. Were approved CODEMANIFEST changes applied and re-verified with the linter?
4. Was a brainstorm performed analyzing implementation details not specified by the DSL?
4b. Was a code stack trace performed for each contract entry point with checkpoints?
4b-ct. Were contract interaction checkpoints verified (type flow, mutation compatibility, interface alignment)?
4c. Were issues found during tracing resolved before proceeding?
4d. Were test scenarios generated using the 6-element format (name, setup, input, trace, assertions, sufficiency)?
5. Is entity interaction and data flow described?
6. For each entity: are pattern, state management, error handling, and edge cases described?
7. Are cross-cutting concerns described (error handling, logging, validation)?
8. For each Usages entry: is it described what it provides, where it is used, why it was chosen, how it is used?
9. Was usages categorization performed with the user (Step 4d) — functional categories proposed, existing files checked, new vs extend decisions made?
10. Were questions asked to the user about unclear aspects and implementation details?
11. Are facts, assumptions, and open questions separated?
12. For each imported usage from `Imports` → `Usages`: was the source file read and analyzed?
13. Is the planned local usages structure documented (which `.usages/` files will be created)?
14. Is the design document saved using the template from `design-doc-template.md`?
15. Are all CODEMANIFEST changes documented in the design document (what changed, why)?

If any answer is "no" — revise the design document before returning it.

---

## Retrospective

After completing the main work, perform a retrospective as defined in CLAUDE.md → Skill Retrospective.

Related skills for improvement: `review-design` (consumer of the design document), `plan-by-design` (consumer of the design document).
Related files within the bundle: `design-doc-template.md`.
