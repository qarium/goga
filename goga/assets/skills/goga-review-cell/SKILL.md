---
name: goga-review-cell
description: Three-dimension cell review
---
# Cell Review

## Purpose

Reviews a cell across three dimensions and proposes concrete remediation actions for each detected issue. Each action requires explicit user confirmation before execution.

You **identify** issues, **propose** solutions, and **execute** user-approved actions (invoking other skills, editing files).

---

## Key Principle

**Identify the exact problem before proposing a solution.** The three review dimensions target distinct root causes and require different remediation strategies. Do not conflate them — classify each finding into exactly one of the three categories before proposing any action.

### User Interaction Rule

**Always provide answer options.** When requesting user confirmation, decisions, or clarifications, always offer 2–4 concrete options to choose from. Never pose open-ended questions without selectable choices.

---

## Steps

### Step 1: Load Context

1. Invoke `goga-lang-disp` via the **Skill tool** to load the target language skill.
   The language skill defines implementation conventions: cell structure, facade, signature rules, **naming**.
   Examples in other skills may follow naming conventions of one language (e.g., snake_case), while the target language
   requires different conventions (e.g., PascalCase). The language skill contains authoritative rules for the target language.
2. Load the DSL specification and DSL application principles:
   - Invoke `goga-cell` via the **Skill tool** to understand CODEMANIFEST DSL syntax, structural rules, and semantics
     (cell structure, `Imports`, `Usages`, `Annotations` directives, types, signatures, mutations, embeddings, constraints)
   - Invoke `goga-cookbook` via the **Skill tool** to understand cell and CODEMANIFEST working principles
     (when to use Entity vs Routine, when to apply mutations and embeddings, usage file authoring principles, cell granularity)
   - **Critical for accurate analysis**: without understanding DSL rules, CODEMANIFEST entries will be misinterpreted
   - Consult the loaded specification and principles whenever CODEMANIFEST entry correctness is uncertain
3. Read the cell's `CODEMANIFEST` file
4. Parse all entities, methods, properties, imports, usages, annotations, re-exports, and locations
5. Enumerate all source files in the cell directory (excluding `.usages/`, build artifacts, tests, and other non-contract files)
6. Read all source files corresponding to declared `location` values
7. Read all `.usages/*.md` files if the `.usages/` directory exists
8. Verify the facade file exists

---

### Step 2: Run Tools

#### 2a. Run Linter

```
goga lint
```

If the linter reports errors, record each as a DSL syntax issue. Fix all DSL syntax errors before proceeding with analysis.

#### 2b. Run Schema

```
goga schema
```

Extract the cell's position in the project hierarchy for contextual reference.

---

### Step 3: Analysis 1 — Code vs Requirements

**Question: Does the code implement what CODEMANIFEST requires?**

For each entity declared in CODEMANIFEST, verify that the implementation satisfies the contract.

#### 3a. Checks

For each entity:
- **Signature conformance**: Compare `"()"` (constructor signature) between CODEMANIFEST and source code
- **Method coverage**: Compare the `"methods"` dictionary — identify missing, extra, or mismatched method signatures
- **Property coverage**: Compare the `"properties"` dictionary — identify missing, extra, or mismatched property types
- **Facade exposure**: Verify the entity appears on both sides. Absence in source code means it is not exported via the facade

For each function (routine):
- **Signature conformance**: Compare the signature string between CODEMANIFEST and source code
- **Existence**: Absence in source code means the function is not exported via the facade

Additional checks:
- **Location validity**: Does the source file exist at path `<cell-path>/<location>`?
- **Behavioral conformance**: Does the implementation satisfy behavioral requirements from annotations?
- **Import utilization**: Are imported types from `Imports` actually referenced in source code?

#### 3b. Findings Presentation

When issues are detected, present each finding with:
- Exact location (entity, method/property, file)
- What CODEMANIFEST requires vs. what the code actually does

#### 3c. Proposed Action

**Formulate a task** describing the discrepancy between code and contract.

Propose: invoke `/goga:design` in **brainstorm** mode, passing the task as context. This produces an implementation redesign that satisfies the contract.

Request user confirmation before execution.

---

### Step 4: Analysis 2 — Requirements vs Code and Usages

**Questions: Do CODEMANIFEST requirements match the actual code and usages? Is CODEMANIFEST well-authored?**

The contract may be incomplete, incorrect, outdated, or poorly written compared to what the code actually implements and what usages describe.

#### 4a. Checks: Accuracy

- **Undocumented entities**: Are there public classes/functions in the code not declared in CODEMANIFEST?
- **Undocumented methods/properties**: Are there public API members of documented classes missing from CODEMANIFEST?
- **Contract accuracy vs usages**: Do annotations reference actually applicable usages? Are usages used in code but not mentioned in annotations?
- **Requirements accuracy**: Do described signatures, types, and behaviors match what the code actually does? If the code is correct and the contract is wrong — the contract requires correction.

#### 4b. Checks: Authoring Quality

For each entity and function (routine) in CODEMANIFEST, verify that annotations satisfy the following authoring quality criteria. Even a technically correct contract degrades overall quality when annotations are poorly written.

**Content guidelines:**
- Begin each annotation with a clear purpose statement — what this entity/function/method does and why it exists
- For each parameter, provide a description using `` `parameter_name`: description `` syntax
- For non-trivial logic (multi-step transformations, conditional flows, state transitions), include an `Algorithm:` section with numbered steps tracing the execution flow
- For constraints, edge cases, format requirements, or preconditions — include a `Requirements:` section with explicit descriptions
- Document return value format when semantics are non-obvious from the signature (e.g., when meaning differs from type or structure is complex)
- Include usage examples when they help clarify the contract — configuration examples for builders, input/output pairs for parsers, invocation patterns for facades

**Quality guidelines:**
- Each annotation must be specific enough for direct implementation — no TBD, TODO, or vague phrasing
- Each annotation must permit exactly one interpretation — if ambiguous, rewrite it
- Maintain consistent style and structure across all annotations within a single CODEMANIFEST file
- All backtick references (`` `name` ``) must resolve to entities in the current CODEMANIFEST context — types from `Imports`, practices from `Usages`, or parameters from the signature

#### 4c. Findings Presentation

When issues are detected, present each finding with:
- Exact CODEMANIFEST location (entity, method/property, section)
- Nature of the issue: missing declaration, inaccurate description, incorrect type, outdated reference, poor annotation quality
- For authoring quality issues: a specific improvement recommendation (e.g., "add `Algorithm:` section", "describe parameter `path`", "restructure annotation with `Algorithm:` and `Requirements:` sections")

#### 4d. Proposed Action

**Edit CODEMANIFEST** to correct inaccuracies and improve authoring quality, then invoke `/goga:design` in **changes** mode to update the design document based on the corrected contract.

Request user confirmation before execution.

---

### Step 5: Analysis 3 — Usage Existence and Adequacy

**Question: Do usage files exist and are they adequate for the cell implementation?**

#### 5a. Checks

- **Existence**: For each `Usages` entry with a file path — does the file exist? (project-level in `.goga/usages/`, cell-level in `.usages/` directory)
- **Annotation reference**: Is each declared usage referenced in an annotation via backtick syntax?
- **Imported usage existence**: For each imported usage from `Imports` → `Usages` — does `{from_path}/.usages/{usage_name}.md` exist?
- **Adequacy**: Does each `.usages/*.md` file describe cell API usage? Is the content accurate and sufficiently detailed for consumers?
- **Missing usages**: Are there external library imports, recurring patterns, or code conventions not covered by any Usages entry?
- **Categorization**: Are `.usages/` functional categories clearly defined and non-overlapping? Should inline usages be extracted into category files?

#### 5b. Findings Presentation

When issues are detected, present each finding with:
- Which usage is missing, outdated, or inadequate
- What practice it should describe

#### 5c. Proposed Action

**Create or update `.usages/*.md` files** directly. This does not require invoking another command — usage files are practice documentation editable directly.

Request user confirmation before execution.

---

### Step 6: Execute Approved Actions

For each user-approved action across all three analyses:

#### 6a. Code vs Requirements (Step 3)

1. Formulate a clear redesign task description
2. Invoke `/goga:design` and select **brainstorm** mode
3. Pass the task as context — the design skill will handle the redesign

#### 6b. Requirements vs Code/Usages (Step 4)

1. Apply CODEMANIFEST edits directly
2. Run linter for validation: `goga lint`
3. Fix all DSL syntax errors after edits
4. Invoke `/goga:design` and select **changes** mode
5. The design skill will detect changes via git diff and update the document accordingly

#### 6c. Usages (Step 5)

1. Create or update the corresponding `.usages/*.md` files
2. Ensure content accurately describes cell API usage with sufficient detail for consumers (implementation details may be present but are secondary)

#### 6d. Final Validation

After executing **all** approved actions (6a, 6b, 6c):

1. Run linter for final validation: `goga lint`
2. If the linter reports errors — fix them
3. Repeat steps 1–2 until the linter passes without errors

---

## Result

- Review findings across all three dimensions
- Analysis 1 (Code vs Requirements): task delegated to `/goga:design brainstorm`
- Analysis 2 (Requirements vs Code/Usages): CODEMANIFEST edits + `/goga:design changes`
- Analysis 3 (Usages): created or updated `.usages/*.md` files

---

## Final Self-Check

Before completion, verify:

1. Was the DSL specification loaded via `goga-cell` and `goga-cookbook` skills before analysis?
2. Was the cell's CODEMANIFEST fully parsed?
3. Were all source files verified against the contract?
4. Were all `.usages/` files analyzed?
5. Was `goga lint` executed?
6. Was `goga schema` executed?
7. Was Analysis 1 (Code vs Requirements) completed with clear findings and a proposed action?
8. Was Analysis 2 (Requirements vs Code/Usages) completed with both accuracy and authoring quality checks?
9. Was Analysis 3 (Usage Existence and Adequacy) completed with clear findings and a proposed action?
10. Was each finding classified into the correct analysis category before proposing an action?
11. Were all actions confirmed by the user before execution?
12. Were approved actions executed correctly?
13. Was `goga lint` executed **after** all actions and did it pass without errors?

If any answer is "no" — complete the outstanding work before returning.

---
