---
name: goga-review-plan
description: Verify execution plan completeness and correctness
---
# Plan Verification

## Objective

Verify the execution plan (the file at the path printed by `goga history path -f plan.md`) for **completeness and correctness** against the design document and `CODEMANIFEST` contracts before passing to ralphex.

You **verify** the plan, **report** findings, and **fix** the plan upon discovery of issues (subject to user approval).

---

## Key Principle

**Every affected contract obligation and design decision must be traceable within the plan.** The plan covers only entities affected by the current feature (as defined in the design document). For all entities the plan claims to cover, it must be correct with respect to the contract and complete with respect to the design. Tasks in the plan that are not traceable to any contract or design also constitute a finding.

## Verifiable Artifact

- Plan file at the path printed by `goga history path -f plan.md` — the execution plan, verified against sources of truth

---

## Phases

### Phase 1: Load Context

1. Invoke `goga-lang-disp` via the **Skill tool** — retrieve the target language skill.
   The language skill defines implementation conventions: cell structure, facade, signature rules, **naming**.
   Examples in other skills may use naming conventions of one language (e.g., snake_case), while the target language
   requires different conventions (e.g., PascalCase) — the language skill is the authoritative source for the target language.
2. Read the plan from the path printed by `goga history path -f plan.md`
3. Read the design document from the path printed by `goga history path -f design.md`
4. Read all relevant `CODEMANIFEST` files referenced by the design document
5. Load the DSL specification and DSL application principles:
   - Invoke `goga-cell` via the **Skill tool** — obtain the DSL reference
     (signature syntax, rules for Imports, Usages, Annotations, types, mutations, embeddings, constraints)
   - Invoke `goga-cookbook` via the **Skill tool** — understand cell and CODEMANIFEST design principles
     (when to use Entity vs Routine, when to apply mutations and embeddings, usage file authoring guidelines, cell granularity)

---

### Phase 2: Run Linter

Execute:
```
goga lint
```

If the linter reports errors, record each error as a **Critical** finding. CODEMANIFEST syntax must be valid before the plan can pass verification.

---

### Phase 3: Consistency — Plan vs CODEMANIFEST

The plan covers only entities affected by the current feature (as defined in the design document), not the entire CODEMANIFEST. Use CODEMANIFEST as a correctness reference, not a completeness checklist.

For each entity/obligation the plan **actually** covers:

#### Step 1. Entity Details

For each contract entity referenced in the plan:
- Verify the entity name and facade obligation match CODEMANIFEST — record as **Critical** on mismatch
- Verify the plan specifies implementation in the correct file `location` per CODEMANIFEST — record as **Critical** on error
- Verify method/property **descriptions** from the contract are reflected in task instructions — record as **High** if absent

#### Step 2. Annotation Detailing

For each `annotations` declaration within the plan's scope (at file, entity, or method/property level):
- Verify the plan embeds annotation content into the corresponding task descriptions
- Verify cascading: file-level annotations appear in every task of the package, entity-level in entity tasks, method-level in the method task
- If annotations are absent from tasks — record as **High**

#### Step 3. Import Context

For each `Imports` entry within the plan's scope:
- Verify plan tasks reference imported types using correct names (including `AS` aliases)
- For imported usages from `Imports` → `Usages`: verify plan tasks correctly reference the imported usage content, including the source path `{from_path}/.usages/{usage_name}.md`
- If import context is absent from tasks that use imported types — record as **High**
- If imported usage context is absent from tasks that depend on the imported practice — record as **High**

#### Step 4. Re-export Coverage

For each re-export block the plan claims to handle:
- Identify a task that ensures the name is importable from the facade
- If a re-export referenced in the plan is not covered — record as **Critical**

#### Step 5. Mutation Coverage

For each `Type::` mutation the plan claims to handle:
- Identify a task that implements the mutation
- If a mutation referenced in the plan is not covered — record as **High**

---

### Phase 4: Consistency — Plan vs Design Document

#### Step 1. Design Entity Traceability

For each entity and design decision described in the design document:
- Identify where they are reflected in the plan's tasks
- If a design decision is absent from all tasks — record as **High**

#### Step 2. Test Scenario Traceability

For each test scenario in the design document:
- Identify the corresponding test instruction in the plan's tasks
- If a test scenario is absent — record as **Medium**

#### Step 3. Absence of Orphan Tasks

For each task in the plan:
- Verify it is traceable to a contract entity, design decision, or justified infrastructure requirement
- If a task has no traceable origin — record as **Medium**

---

### Phase 5: TDD Completeness

For each **coding task** in the plan (entity skeleton, property, method, mutation implementation):

Verify the task includes all TDD steps as checkboxes:
1. **Contract tests** — written first, expected to fail
2. **Code** — implementation steps
3. **Interface verification** — run contract tests
4. **Logical tests** — behavioral tests
5. **Debugging** — run tests, fix the implementation (NOT the tests)
6. **Contract re-verification** — verify contract obligations
7. **Lint** — formatting check

If any TDD step is absent — record as **High**.

Infrastructure tasks (Cell structure, facade, re-exports) are exempt — they follow a simplified workflow.

---

### Phase 6: Self-contained Tasks

For each task in the plan, verify all of the following. If any check fails — record as **High**:

1. Does the task contain its own context paragraph explaining what it does and which contract entities it covers? If absent — record as **High**.
2. Does the task include relevant imports, Usages, and annotations? If absent — record as **High**.
3. Does the task specify target files? If absent — record as **High**.
4. Does the task depend on another task for implementation context (e.g., "see Task 3 for API") instead of inlining it? If so — record as **High**.

---

### Phase 7: Task Order

Verify the overall task order conforms to the convention:

1. **Infrastructure tasks** (Cell structure, facade, re-exports)
2. **Entity skeleton tasks**
3. **Property implementation tasks**
4. **Method implementation tasks**
5. **Interface mutation tasks**
6. **Integration test tasks**

In a multi-package plan:
- Leaf packages are processed before parent packages
- Each package's coding tasks complete before the next package begins

If the order is violated — record as **Medium**.

---

### Phase 8: Usages Coverage

For each `Usages` entry within the plan's scope (from affected entities per the design document):
- Identify at least one task in the plan that references this Usages entry
- Verify the task contains specific information (what to use, how to invoke), not merely a name reference
- If the Usages entry value is a file path — verify the plan reflects the actual file content, not merely the path or usage name

For each imported usage from `Imports` → `Usages` within the plan's scope:
- Identify at least one task referencing this imported usage
- Verify the task references the correct source path `{from_path}/.usages/{usage_name}.md`
- Verify the task contains specific information from the imported usage, not merely a name reference

For each planned local `.usages/` file specified in the design document:
- Identify a task or step that creates or extends the `.usages/<category-name>.md` file
- Verify the task specifies the expected file content
- If the file extends an existing category — verify the plan specifies addition, not replacement
- Verify file creation is planned alongside the code, not as a separate stage

If a Usages entry is absent from all tasks — record as **Medium**.
If a Usages mention is too vague — record as **Low**.
If a Usages file path is referenced but its content is not reflected — record as **Medium**.
If an imported usage is absent from all tasks — record as **Medium**.
If a planned local `.usages/` file lacks a creation task — record as **Medium**.

---

### Phase 9: CODEMANIFEST Read-Only Check

For each task in the plan:
- Verify no task instructs the implementation agent to modify `CODEMANIFEST` files
- Verify the plan instructs the implementation agent not to modify CODEMANIFEST files (look for a "read-only" warning in the task context)

If a task proposes CODEMANIFEST modification — record as **Critical**.
If the "read-only" warning is absent — record as **Medium**.

---

### Phase 10: Report and Fix Findings (Interactive)

Aggregate all findings from Phases 2–9 before presenting them. Sort by severity: Critical → High → Medium → Low.

Present findings **one at a time**. For each finding:

#### Step 1. Present the Finding

Display one finding with:

- **Severity** (Critical / High / Medium / Low)
- **Direction** (CODEMANIFEST / Design / TDD / Self-containment / Order / Usages / Read-Only)
- **Location** — exact reference to the task, plan section, or CODEMANIFEST line
- **What's wrong** — clear description of the problem
- **Suggested fix** — the precise change required, not vague advice

#### Step 2. Request User Decision

Use AskUserQuestion with options:

1. **Apply suggested fix** — apply the fix to the plan immediately
2. **Suggest alternative** — the user describes a different fix approach
3. **Skip** — the user dismisses the finding

#### Step 3. Apply the Decision

- **Apply suggested fix**: update the plan file at the path printed by `goga history path -f plan.md`, then re-verify that the fix introduces no new issues (re-run the relevant checks). Briefly report the re-verification result.
- **Skip**: record the finding as "skipped" and proceed.
- **Suggest alternative**: discuss the alternative with the user, agree on a fix, apply it, and re-verify.

#### Step 4. Proceed to Next Finding

Repeat from Step 1 for the next finding. Display a brief counter: "Finding 3 of 12".

After processing all findings, display the summary:

- **Fixed**: N findings (listed by severity and direction)
- **Skipped**: N findings (listed by severity and direction)
- **Plan status**: updated / unchanged

---

## Output

- Findings summary: count of fixed / skipped findings by severity and direction
- Updated plan file (if fixes were applied)
- Verification verdict: passed / failed

---

## Final Self-Check

Before completing, verify:

1. Were all relevant CODEMANIFEST files read and each plan entity verified for correctness against the contract (names, locations, descriptions, annotations, imports)?
2. Was the design document read and each entity/design decision/test scenario traced in the plan? Were orphan tasks identified?
3. Was `goga lint` executed and results analyzed?
4. Was each coding task checked for TDD completeness (all 7 steps)?
5. Was each task checked for self-contained context?
6. Was task order verified against the convention?
7. Was each Usages entry checked for coverage in the plan?
8. Was each imported usage from `Imports` → `Usages` checked for coverage and correct source path reference?
9. Was each planned local `.usages/` file checked for a creation task with expected content?
10. Was each task checked for CODEMANIFEST "read-only" compliance?
11. Was each finding presented one at a time with a fix decision via AskUserQuestion?
12. Were approved fixes applied and re-verified?
13. Was a summary of fixed/skipped findings provided?

If any answer is "no" — complete the missing verification before returning.

---
