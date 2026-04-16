# Design by Changes

## Purpose

Creates a **design document** — a complete architectural solution based on changes in `CODEMANIFEST`.

The design document describes **what** and **how** needs to be implemented, but not **in what order** (order is determined by the plan in `plan-by-design`).

You do **not** write implementation code and **not** create an execution plan.
You create an **architectural solution** where every detail has been thought through.

---

## Sources of Truth

Use the following sources jointly, when available:

1. `CODEMANIFEST` — located **inside the package directory** (e.g., `resq/CODEMANIFEST`). Subpackages may have their own CODEMANIFEST files. Read **all** CODEMANIFEST files to build the complete contract.
2. current package file tree
3. current package source files
4. git change context (added, modified, deleted files)
5. `.qarium/ai/employees/lead.md` — project architecture, code patterns, conventions, `default_branch`
6. `.qarium/ai/employees/developer.md` — project development conventions and build commands

---

## Steps

### Step 1: Git diff CODEMANIFEST

Compare all CODEMANIFEST files between the current branch and the base branch (default from `lead.md` → `default_branch`, fallback `0.0.x`).

Determine:
- added/removed/modified contract entities
- changes in Usages, Imports, Annotations, re-exports
- new or deleted CODEMANIFEST files

If there is no git context — work with the current CODEMANIFEST files as the complete contract.

### Step 2: Gap analysis

Compare CODEMANIFEST contracts with current implementation:
- missing contract entities
- incorrect locations
- missing re-exports
- signature and behavior mismatches
- existing code that can be reused

### Step 3: Contract validation via linter

Run:
```
docker run --rm -v .:/project -w /project goga linter
```

Analyze the linter output. Fix syntax errors in CODEMANIFEST if the linter finds them (the linter validates DSL syntax; semantic content of the contract does not change).

### Step 4: Brainstorm

Based on the collected data, perform analysis in the following order:

#### 4a. Code Stack Trace

For each contract entry point (method, function, constructor), trace the full logical chain through the code from start to finish:

1. **Entry point**: what triggers this code path (constructor call, method call, function call)
2. **Input**: what data arrives, in what form, from where
3. **Each intermediate step**: what transformation/validation/lookup happens, what is returned, what is passed forward
4. **External calls**: what imported types provide, what Usages libraries return, how they are called
5. **Output**: what the final result is, in what form, where it goes

At each step, set **checkpoints** — verify:
- does the data type match what the next step expects?
- is the transformation logically correct?
- are there missing intermediate steps that the contract assumes but doesn't state?
- does the external library usage match its actual API (check Usages specs)?

If at any checkpoint the logic breaks — record the issue and resolve it before continuing.

**Important**: do this trace by reading actual source files for existing code and actual library documentation for Usages. Do not assume — verify.

#### 4b. Analysis

Based on the stack trace results, perform analysis:
- what new contract entities exist and how they interact
- implementation details not specified by the DSL (patterns, specific libraries from Usages, architectural decisions)
- cross-cutting concerns (error handling, logging, validation, caching, concurrency)
- dependencies between entities
- potential issues and edge cases found during tracing
- data flows between entities
- Usages analysis: what each entry provides, where it is used, why it was chosen, how exactly it is used

**Important — Usages/Practices as interface bridges**: A practice (Usages entry) is a **connecting entity** between packages. If an entity needs to interact with an external library, another package, or a shared interface — it MUST do so through the declared practice. The practice defines the contract of interaction. When designing how entities connect to external systems, always route through the appropriate Usages entry — never bypass a declared practice with a direct dependency.

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

### Step 5: Questions to the user

Via AskUserQuestion, ask questions about:
- unclear aspects of CODEMANIFEST (contract ambiguities)
- implementation details not determined by the DSL (pattern choices, specific approaches, error handling)
- critical assumptions requiring confirmation

If there are no questions — skip this step.

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
3. Was the linter run: `docker run --rm -v .:/project -w /project goga linter`?
4. Was a brainstorm performed analyzing implementation details not specified by the DSL?
4b. Was a code stack trace performed for each contract entry point with checkpoints?
4c. Were issues found during tracing resolved before proceeding?
4d. Were test scenarios generated using the 6-element format (name, setup, input, trace, assertions, sufficiency)?
5. Is entity interaction and data flow described?
6. For each entity: are pattern, state management, error handling, and edge cases described?
7. Are cross-cutting concerns described (error handling, logging, validation)?
8. For each Usages entry: is it described what it provides, where it is used, why it was chosen, how it is used?
9. Were questions asked to the user about unclear aspects and implementation details?
10. Are facts, assumptions, and open questions separated?
11. Is the design document saved using the template from `design-doc-template.md`?

If any answer is "no" — revise the design document before returning it.

---

## Retrospective

After completing the main work, perform a retrospective as defined in CLAUDE.md → Skill Retrospective.

Related skills for improvement: `plan-by-design` (consumer of the design document).
Related files within the bundle: `design-doc-template.md`.
