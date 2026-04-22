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
2. Source files — implementation code in the cell directory
3. Usages files — `.usages/*.md` inside the cell (if they exist)
4. `goga schema` — project cell hierarchy for context
5. `goga linter` — CODEMANIFEST DSL syntax validation

---

## Steps

### Step 1: Load context

1. Read the cell's `CODEMANIFEST` file
2. Parse all entities, methods, properties, imports, usages, annotations, re-exports, and locations
3. List all source files in the cell directory (excluding `.usages/`, `__pycache__/`, tests, and other non-contract files)
4. Read all source files that match declared `location` values
5. Read all `.usages/*.md` files if the `.usages/` directory exists
6. Check if `__init__.py` exists (facade file)

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

---

### Step 3: Analysis 1 — Code vs Requirements

**Question: Does the code implement what CODEMANIFEST requires?**

For each entity declared in CODEMANIFEST, verify the implementation matches the contract.

#### 3a. Checks

For each entity:

- **Location**: Does the file exist at `<cell-path>/<location>`?
- **Entity existence**: Does a matching class/function exist in the declared `location` file?
- **Method/property signatures**: Does each declared method/property exist? Do parameters and return types match?
- **Facade exposure**: Is the entity importable from `__init__.py`? Are re-exports (`->Name: {}`) available?
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

For each entity and routine in CODEMANIFEST, verify annotations follow the established writing standards. Even if the contract is technically correct, poorly written annotations degrade the quality of the entire contract.

**Annotation structure standard** — each annotation should contain:

1. **Описание** (mandatory): краткое назначение сущности/рутины/метода/свойства. Для методов и рутин со параметрами — описание каждого параметра через `` `param`: описание ``
2. **Алгоритм:** (required for non-trivial logic): пошаговое описание алгоритма работы. Использовать нумерованный или маркированный список
3. **Требования:** (if applicable): конкретные требования к реализации — краевые случаи, ограничения, форматы

Checks:

- **Annotation completeness**: Does each entity/routine have a substantive annotation (not a one-liner)? For entities with complex behavior, is the annotation detailed enough to implement from?
- **Algorithm section**: For routines and methods with non-trivial logic — is there an `Алгоритм:` section with step-by-step description?
- **Requirements section**: For routines and methods that have constraints, edge cases, or specific behavioral rules — is there a `Требования:` section?
- **Parameter descriptions**: For each method/routine parameter — is it described with `` `param`: описание `` syntax?
- **Return value description**: For methods/routines with return values — is the return value described?
- **Error templates**: For validators and rules — are error message templates (`Шаблоны ошибок:`) documented?
- **Grammar and clarity**: Are annotations written in clear, correct language without ambiguity? No typos, no incomplete sentences, no vague wording?
- **Structure consistency**: Are annotations across the same CODEMANIFEST written in a consistent style and structure?

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
- **Fitness**: Does each `.usages/*.md` file describe a practice actually used in the implementation? Is the content accurate and detailed enough?
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

1. Formulate a clear task description of what needs to be redesigned
2. Call `/goga:design` and select **brainstorm** mode
3. Pass the task as context — the design command will handle the redesign

#### 6b. Requirements vs Code/Usages (Step 4)

1. Apply the CODEMANIFEST edits directly
2. Run linter to validate: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`
3. Fix any DSL syntax errors from the edits
4. Call `/goga:design` and select **changes** mode
5. The design command will detect the changes via git diff and update accordingly

#### 6c. Usages (Step 5)

1. Create or update the relevant `.usages/*.md` files
2. Ensure the content accurately describes the practice with enough detail for implementation

---

## Output

- Analysis results across all three dimensions
- For Analysis 1 (Code vs Requirements): task passed to `/goga:design brainstorm`
- For Analysis 2 (Requirements vs Code/Usages): CODEMANIFEST edits + `/goga:design changes`
- For Analysis 3 (Usages): created or updated `.usages/*.md` files

---

## Final Self-Check

Before completing, verify:

1. Was the cell's CODEMANIFEST fully parsed?
2. Were all source files checked against the contract?
3. Were all `.usages/` files analyzed?
4. Was `goga linter` run?
5. Was `goga schema` run?
6. Was Analysis 1 (Code vs Requirements) completed with clear findings and proposed action?
7. Was Analysis 2 (Requirements vs Code/Usages) completed with both accuracy checks and writing quality checks?
8. Was Analysis 3 (Usages existence and fitness) completed with clear findings and proposed action?
9. Was each finding clearly classified into the correct analysis category before proposing an action?
10. Were all actions confirmed by the user before execution?
11. Were approved actions executed correctly?

If any answer is "no" — complete the missing work before returning.

---

## Retrospective

After completing the main work, perform a retrospective as defined in CLAUDE.md → Skill Retrospective.

Related skills for improvement: `design-by-changes` (creates design documents), `design-by-brainstorm` (brainstorm-based design), `review-design` (reviews designs).
