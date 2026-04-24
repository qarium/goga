# Analyze Cell

## Purpose

Analyzes a cell across three dimensions and proposes concrete actions to fix discovered issues. Each action requires user confirmation before execution.

You **identify** problems, **propose** solutions, and **execute** approved actions (calling other commands, editing files).

---

## Key Principle

**Identify the exact problem before proposing a solution.** The three analysis dimensions target different root causes and require different fixes. Do not mix them — each finding must be clearly classified into one of the three categories before any action is proposed.

---

## Sources of Truth

1. `CODEMANIFEST` — the cell's contract (located at `<cell-path>/CODEMANIFEST`)
2. DSL specification — `dsl.md` (in skill directory) — defines the CODEMANIFEST DSL syntax rules (see Step 1)
3. Source files — implementation code in the cell directory
4. Usages files — `.usages/*.md` inside the cell (if they exist)
5. `goga schema` — project cell hierarchy for context
6. `goga linter` — CODEMANIFEST DSL syntax validation
7. `goga contract` — CODEMANIFEST vs source code comparison

---

## Steps

### Step 1: Load context

1. Read the DSL specification at `dsl.md` (located in the skill directory)
   - Defines CODEMANIFEST DSL syntax, structure rules, and semantics
   - **Critical for correct analysis**: without understanding the DSL rules, you will misinterpret CODEMANIFEST entries (e.g. path resolution rules, signature format semantics, import constraints)
   - Refer to the spec when in doubt about whether a CODEMANIFEST entry is valid
2. Read the cell's `CODEMANIFEST` file
3. Parse all entities, methods, properties, imports, usages, annotations, re-exports, and locations
4. List all source files in the cell directory (excluding `.usages/`, `__pycache__/`, tests, and other non-contract files)
5. Read all source files that match declared `location` values
6. Read all `.usages/*.md` files if the `.usages/` directory exists
7. Check if `__init__.py` exists (facade file)

---

### Step 2: Run tools

#### 2a. Run linter

```
docker run --rm -v .:/project -w /project qarium/goga:latest linter
```

If the linter reports errors — record each as a DSL syntax issue. Fix DSL syntax errors before proceeding with analysis.

#### 2b. Run schema

```
docker run --rm -v .:/project -w /project qarium/goga:latest schema
```

Extract the cell's position in the project hierarchy for context.

#### 2c. Run contract comparison

```
docker run --rm -v .:/project -w /project qarium/goga:latest contract <cell-path>
```

Extract the codemanifest vs source comparison for the target cell. The JSON output contains two sides for each entity/routine:

- **codemanifest** — what CODEMANIFEST declares
- **source** — what Python source code actually implements

Use discrepancies between the two sides as primary inputs for Analysis 1 (Step 3).

---

### Step 3: Analysis 1 — Code vs Requirements

**Question: Does the code implement what CODEMANIFEST requires?**

For each entity declared in CODEMANIFEST, verify the implementation matches the contract.

#### 3a. Checks

Using the `goga contract` output from Step 2c, compare codemanifest vs source for the target cell:

For each entity:
- **Signature match**: Compare `"()"` (constructor signature) between codemanifest and source sides
- **Methods coverage**: Compare `"methods"` dict — missing, extra, or mismatched method signatures
- **Properties coverage**: Compare `"properties"` dict — missing, extra, or mismatched property types
- **Facade exposure**: Is the entity listed in both sides? Missing from source means it's not exported via `__all__`

For each routine:
- **Signature match**: Compare the signature string between codemanifest and source sides
- **Existence**: Missing from source means not exported via `__all__`

Additional checks not covered by `goga contract`:
- **Location**: Does the source file exist at `<cell-path>/<location>`?
- **Behavioral compliance**: Does the implementation reflect behavioral requirements from annotations?
- **Import usage**: Are imported types from `Imports` actually used in the source code?

#### 3b. Present findings

If any issues found — present each finding to the user with:
- Exact location (entity, method/property, file)
- What CODEMANIFEST requires vs what the code actually does

#### 3c. Proposed action

**Formulate a task** describing the discrepancy between code and contract.

Propose: call `/goga:design` with **brainstorm** mode, passing the task as context. This will redesign the implementation to match the contract.

Ask the user to confirm before proceeding.

---

### Step 4: Analysis 2 — Requirements vs Code and Usages

**Questions: Are the CODEMANIFEST requirements accurate relative to the actual code and usages? Is the CODEMANIFEST well-written?**

The contract may be incomplete, incorrect, outdated, or poorly written compared to what the code actually does and what usages describe.

#### 4a. Checks: Accuracy

- **Undocumented entities**: Are there public classes/functions in code not declared in CODEMANIFEST?
- **Undocumented methods/properties**: Are there public API members on documented classes not in CODEMANIFEST?
- **Contract vs usages accuracy**: Do annotations reference usages that are actually applicable? Are usages used in code but unreferenced in annotations?
- **Requirements accuracy**: Do described signatures, types, and behaviors match what the code actually does? If the code is correct and the contract is wrong — the contract needs fixing.

#### 4b. Checks: Writing quality

For each entity and routine in CODEMANIFEST, verify annotations follow these writing quality criteria. Even if the contract is technically correct, poorly written annotations degrade the quality of the entire contract.

**Content recommendations:**
- Begin each annotation with a clear statement of purpose — what this entity/routine/method does and why it exists
- For every parameter, provide a description using `` `param_name`: description `` syntax
- When logic is non-trivial (multi-step transformations, conditional flows, state transitions), include an `Algorithm:` section with numbered steps that trace the execution flow
- When there are constraints, edge cases, format requirements, or preconditions — include a `Requirements:` section describing them explicitly
- Document the return value format when the semantics are not obvious from the signature alone (e.g., when the meaning differs from the type, or when the structure is complex)
- Include usage examples when they help clarify the contract — configuration examples for builders, input/output pairs for parsers, call patterns for facades

**Quality recommendations:**
- Each annotation must be concrete enough to implement from — no TBD, TODO, or vague wording
- Each annotation should have exactly one possible interpretation — if you can read it two ways, rewrite it
- Maintain consistent style and structure across all annotations within the same CODEMANIFEST file
- All backtick references (`` `name` ``) must point to entities that actually exist in the current CODEMANIFEST context — types from `Imports`, practices from `Usages`, or parameters from the signature

#### 4c. Present findings

If any issues found — present each finding to the user with:
- Exact location in CODEMANIFEST (entity, method/property, section)
- What is wrong: missing declaration, inaccurate description, wrong type, stale reference, poor annotation quality
- For writing quality issues: specific recommendation on how to improve (e.g., "add `Алгоритм:` section", "describe parameter `path`", "restructure annotation with `Алгоритм:` and `Требования:` sections")

#### 4d. Proposed action

**Edit CODEMANIFEST** to fix the inaccuracies and improve writing quality, then call `/goga:design` with **changes** mode to update the design document based on the corrected contract.

Ask the user to confirm before proceeding.

---

### Step 5: Analysis 3 — Usages existence and fitness

**Question: Do usages files exist, and are they adequate for the cell's implementation?**

#### 5a. Checks

- **Existence**: For each `Usages` entry with a file path — does the file exist? Does `.usages/` directory exist?
- **Referenced in annotations**: Is each declared usage referenced in some annotation via backtick syntax?
- **Imported usages exist**: For each imported usage from `Imports` → `Usages` — does `{from_path}/.usages/{usage_name}.md` exist?
- **Fitness**: Does each `.usages/*.md` file describe how to use the cell's API? Is the content accurate and detailed enough for consumers?
- **Missing usages**: Are there external library imports, recurring patterns, or conventions in code not covered by any Usages entry?
- **Categorization**: Are `.usages/` functional categories well-defined and non-overlapping? Should inline usages be moved to category files?

#### 5b. Present findings

If any issues found — present each finding to the user with:
- Which usage is missing, stale, or inadequate
- What practice it should describe

#### 5c. Proposed action

**Create or update `.usages/*.md` files** directly. This does not require calling another command — usages files are practice documentation that can be edited directly.

Ask the user to confirm before proceeding.

---

### Step 6: Execute approved actions

For each action the user approved across all three analyses:

#### 6a. Code vs Requirements (Step 3)

1. Summarize discrepancies from `goga contract` output
2. Formulate a clear task description of what needs to be redesigned
3. Call `/goga:design` and select **brainstorm** mode
4. Pass the task as context — the design command will handle the redesign

#### 6b. Requirements vs Code/Usages (Step 4)

1. Apply the CODEMANIFEST edits directly
2. Run linter to validate: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`
3. Fix any DSL syntax errors from the edits
4. Call `/goga:design` and select **changes** mode
5. The design command will detect the changes via git diff and update accordingly

#### 6c. Usages (Step 5)

1. Create or update the relevant `.usages/*.md` files
2. Ensure the content accurately describes how to use the cell's API, with enough detail for consumers (implementation details may be present but are secondary)

---

## Output

- Analysis results across all three dimensions
- For Analysis 1 (Code vs Requirements): task passed to `/goga:design brainstorm`
- For Analysis 2 (Requirements vs Code/Usages): CODEMANIFEST edits + `/goga:design changes`
- For Analysis 3 (Usages): created or updated `.usages/*.md` files

---

## Final Self-Check

Before completing, verify:

1. Was the DSL specification (`dsl.md` in skill directory) read before analysis?
2. Was the cell's CODEMANIFEST fully parsed?
3. Were all source files checked against the contract?
4. Were all `.usages/` files analyzed?
5. Was `goga linter` run?
6. Was `goga schema` run?
7. Was `goga contract <cell-path>` run?
8. Was Analysis 1 (Code vs Requirements) completed with clear findings and proposed action?
9. Was Analysis 2 (Requirements vs Code/Usages) completed with both accuracy checks and writing quality checks?
10. Was Analysis 3 (Usages existence and fitness) completed with clear findings and proposed action?
11. Was each finding clearly classified into the correct analysis category before proposing an action?
12. Were all actions confirmed by the user before execution?
13. Were approved actions executed correctly?

If any answer is "no" — complete the missing work before returning.

---

## Retrospective

After completing the main work, perform a retrospective as defined in CLAUDE.md → Skill Retrospective.

Related skills for improvement: `design-by-changes` (creates design documents), `design-by-brainstorm` (brainstorm-based design), `review-design` (reviews designs).
