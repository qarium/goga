# Verify Plan

## Purpose

Verifies the execution plan (`docs/plans/<feature-name>.md`) for **completeness and correctness** against the design document and `CODEMANIFEST` contracts before it is handed off to ralphex.

You **verify** the plan, **report** findings, and **fix** the plan when issues are found (with user approval).

---

## Key Principle

**Every affected contract obligation and design decision must be traceable into the plan.** The plan covers only the entities affected by the current feature (as defined in the design document). For everything the plan claims to cover — it must be correct against the contract and complete against the design. If the plan contains tasks that don't trace back to any contract or design — this is also a finding.

---

## Sources of Truth

1. `CODEMANIFEST` files — the contract surface (read **all** hierarchical CODEMANIFEST files)
2. Usages spec files — read by reference: always read root Usages (referenced by global `Annotations`), always read Usages of entities covered by the plan (referenced by entity annotations via backtick syntax), skip Usages not referenced by any covered entity. When a Usages entry value is a file path (relative to the `CODEMANIFEST` file location), read that file to verify the plan correctly reflects the specification content
3. Design document at `docs/design/<feature-name>.md` — architectural solution
3. `dsl.md` — DSL reference
4. `output-template.md` from the `plan-by-design` skill bundle — plan format reference

## Artifact Under Verification

- Plan file at `docs/plans/<feature-name>.md` — the execution plan being checked against the sources of truth

---

## Steps

### Step 1: Load context

1. Read the plan from `docs/plans/<feature-name>.md`
2. Read the design document from `docs/design/<feature-name>.md`
3. Read all relevant `CODEMANIFEST` files referenced in the design document
4. Read `dsl.md` for DSL reference, `output-template.md` and `conventions.md` from the `plan-by-design` skill bundle (same parent directory as this skill)

---

### Step 2: Run linter

Run:
```
docker run --rm -v .:/project -w /project goga linter
```

If the linter reports errors — record each error as a **Critical** finding. The CODEMANIFEST syntax must be valid before the plan can be considered correct.

---

### Step 3: Consistency — plan vs CODEMANIFEST

The plan covers only the entities affected by the current feature (as defined in the design document), not the entire CODEMANIFEST. Use CODEMANIFEST as a reference for correctness, not as a completeness checklist.

For each entity/obligation that the plan **does** cover:

#### 3a. Entity details

For each contract entity that appears in the plan:
- Verify the entity name and facade obligation match the CODEMANIFEST — record as **Critical** if mismatch
- Verify the plan specifies implementation in the correct `location` file per CODEMANIFEST — record as **Critical** if wrong
- Verify that method/property **descriptions** from the contract are reflected in task instructions — record as **High** if missing

#### 3b. Annotations drill-down

For each `annotations` declaration relevant to the plan's scope (file-level, entity-level, method/property-level):
- Verify the plan embeds annotation content in the relevant task descriptions
- Verify the cascade: file-level annotations appear in every task of the package, entity-level in the entity's tasks, method-level in the method's task
- If annotations are missing from tasks — record as **High**

#### 3c. Import context

For each `Imports` entry relevant to the plan's scope:
- Verify the plan tasks reference the imported types with correct names (including `AS` aliases)
- For imported usages from `Imports` → `Usages`: verify plan tasks reference the imported usage content correctly, including the source path `{from_path}/.usages/{usage_name}.md`
- If import context is missing from tasks that use the imported types — record as **High**
- If imported usage context is missing from tasks that depend on the imported practice — record as **High**

#### 3d. Re-export coverage

For each re-export block that the plan claims to handle:
- Find the task that ensures this name is importable from the facade
- If a re-export mentioned in the plan is not covered — record as **Critical**

#### 3e. Mutation coverage

For each `Type::` mutation that the plan claims to handle:
- Find the task that implements the mutation
- If a mutation mentioned in the plan is not covered — record as **High**

---

### Step 4: Consistency — plan vs design document

#### 4a. Design entity traceability

For each entity and design decision described in the design document:
- Find where it is reflected in the plan's tasks
- If a design decision is missing from all tasks — record as **High**

#### 4b. Test scenario traceability

For each test scenario in the design document:
- Find the corresponding test instruction in the plan tasks
- If a test scenario is missing — record as **Medium**

#### 4c. No orphan tasks

For each task in the plan:
- Verify it traces back to a contract entity, design decision, or valid infrastructure need
- If a task has no traceable origin — record as **Medium**

---

### Step 5: TDD completeness

For each **coding task** in the plan (entity skeleton, property, method, mutation implementation):

Verify the task contains all TDD steps as checkboxes:
1. **Contract tests** — written first, expected to fail
2. **Code** — implementation steps
3. **Verify interfaces** — run contract tests
4. **Logic tests** — behavioral tests
5. **Debug** — run tests, fix implementation (NOT tests)
6. **Re-check contracts** — verify contract obligations
7. **Lint** — formatting check

If any TDD step is missing — record as **High**.

Infrastructure tasks (package structure, `__init__.py`, re-exports) are exempt — they follow a simplified workflow.

---

### Step 6: Self-contained tasks

For each task in the plan, check all of the following. If any check fails — record as **High**:

1. Does the task include its own context paragraph explaining what it does and which contract entities it covers? If missing — record as **High**.
2. Does the task include relevant imports, Usages, and annotations? If missing — record as **High**.
3. Does the task specify target files? If missing — record as **High**.
4. Does the task depend on another task for implementation context (e.g., "see Task 3 for the API") instead of restating it inline? If yes — record as **High**.

---

### Step 7: Task ordering

Verify the overall task order follows the convention:

1. **Infrastructure tasks** (package structure, `__init__.py`, re-exports)
2. **Entity skeleton tasks**
3. **Property implementation tasks**
4. **Method implementation tasks**
5. **Interface mutation tasks**
6. **Integration test tasks**

Within a multi-package plan:
- Leaf packages are processed before parent packages
- Each package's coding tasks are completed before starting the next

If ordering is violated — record as **Medium**.

---

### Step 8: Usages coverage

For each `Usages` entry relevant to the plan's scope (from the design document's affected entities):
- Find at least one task in the plan that references this Usages entry
- Verify the task contains specific information (what to use, how to call), not just a name mention
- If the Usages entry value is a file path — verify the plan reflects the actual content from that file, not just the file path or usage name

For each imported usage from `Imports` → `Usages` relevant to the plan's scope:
- Find at least one task referencing this imported usage
- Verify the task references the correct source path `{from_path}/.usages/{usage_name}.md`
- Verify the task contains specific information from the imported usage, not just a name mention

For each planned local `.usages/` file specified in the design document:
- Find a task or step that creates the `.usages/<name>.md` file
- Verify the task specifies the expected content of the file
- Verify the file creation is planned together with code, not as a separate phase

If a Usages entry is not present in any task — record as **Medium**.
If a Usages mention is too vague — record as **Low**.
If a Usages file path is mentioned but its content is not reflected — record as **Medium**.
If an imported usage is not present in any task — record as **Medium**.
If a planned local `.usages/` file has no creation task — record as **Medium**.

---

### Step 9: CODEMANIFEST read-only check

For each task in the plan:
- Verify no task instructs the implementation agent to modify `CODEMANIFEST` files
- Verify the plan instructs the implementation agent not to modify CODEMANIFEST files (look for the read-only warning in task context)

If a task suggests modifying CODEMANIFEST — record as **Critical**.
If the read-only warning is missing — record as **Medium**.

---

### Step 10: Report findings

Present all findings to the user, organized by severity:

#### Critical (blocks ralphex execution)
- <finding with exact reference to plan section and what is wrong>

#### High (will cause implementation bugs)
- <finding>

#### Medium (may cause issues)
- <finding>

#### Low (improvements)
- <finding>

For each finding, propose a **concrete fix** — the exact change needed in the plan.

---

### Step 11: Fix (with user approval)

For each finding the user wants to fix:

- Update the plan file at `docs/plans/<feature-name>.md`
- Re-verify that the fix doesn't introduce new issues (re-run relevant checks)

---

## Output

- List of findings with severity, location, and proposed fix
- Updated plan file (if fixes were applied)
- Verification pass/fail verdict

---

## Final Self-Check

Before completing, verify:

1. Were all relevant CODEMANIFEST files read and every plan entity checked for correctness against the contract (names, locations, descriptions, annotations, imports)?
2. Was the design document read and every entity/design decision/test scenario traced into the plan? Were orphan tasks identified?
3. Was `goga linter` run and results analyzed?
4. Was every coding task checked for TDD completeness (all 7 steps)?
5. Was every task checked for self-contained context?
6. Was task ordering verified against the convention?
7. Was every Usages entry checked for coverage in the plan?
8. Was every imported usage from `Imports` → `Usages` checked for coverage and correct source path reference?
9. Was every planned local `.usages/` file checked for a creation task with expected content?
10. Was every task checked for CODEMANIFEST read-only compliance?
11. Are findings organized by severity with concrete fixes proposed?
12. Were approved fixes applied and re-verified?

If any answer is "no" — complete the missing verification before returning.

---

## Retrospective

After completing the main work, perform a retrospective as defined in CLAUDE.md → Skill Retrospective.

Related skills for improvement: `plan-by-design` (producer of the plan being verified).
