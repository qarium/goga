# Review Design

## Purpose

Reviews the design document for **logical correctness** by tracing through the full code stack for every entry point and test scenario. This is a **verification pass** — the goal is to find logical errors before the plan is created.

You do **not** write implementation code.
You **trace** every logical chain and **find** where logic breaks.

---

## Key Principle

**Trace, don't assume.** For every logical chain, mentally execute the code path step by step. Read actual source files and library documentation to verify correctness. If a step cannot be verified because information is missing — this itself is a finding.

### CODEMANIFEST Editing

When tracing reveals errors **in the contract itself** (not in the design's interpretation of the contract), you **must** propose CODEMANIFEST edits. These are not design-level findings — they are contract-level errors that block correct implementation regardless of how the design is structured.

Conditions requiring CODEMANIFEST editing:
- **Insufficient requirements**: missing type declarations, incomplete signatures, absent method/property descriptions
- **Inconsistent requirements**: contradictions between entity interfaces, type mismatches between interacting entities
- **Contract interaction errors**: broken type chains across interfaces, `Type::` mutations referencing non-existent or incompatible types, interface contracts that disagree on data shapes

All CODEMANIFEST edits must be **proposed to the user** before applying.

---

## Sources of Truth

Use the following sources jointly, when available:

1. `dsl.md` — DSL specification (in skill directory). Read before reviewing contracts to understand DSL rules and detect contract errors
2. `CODEMANIFEST` files
3. Current package source files
3. Usages specs and external library documentation
4. Design document at `docs/design/<feature-name>.md`

---

## Steps

### Step 1: Load context

1. Read `dsl.md` (in skill directory) to understand CODEMANIFEST DSL rules before reviewing contracts.
2. Read the design document from `docs/design/<feature-name>.md`
2. Read all relevant CODEMANIFEST files referenced in the design
3. Read existing source files referenced in the design (if any)
4. Run `docker run --rm -v .:/project -w /project qarium/goga:latest schema --help` to understand the command, then run `docker run --rm -v .:/project -w /project qarium/goga:latest schema` to get the full project dependency graph. Use `--depends-on <cell_path>` to find cells that depend on cells changed by the design. This ensures the review covers all affected cells.
5. **Read Usages specs by reference**: determine which Usages to read based on reference links:
   - **Always read root Usages** — Usages referenced by global `Annotations` in CODEMANIFEST header (via backtick syntax) are always read
   - **Always read changed entities' Usages** — for each entity covered by the design, scan its annotations for backtick references to Usages. All referenced Usages are read
   - **Skip unreferenced Usages** — Usages entries not referenced by global `Annotations` AND not referenced by any covered entity's annotations are not read

---

### Step 2: Code Stack Trace Verification

For **each entry point** (method, function, constructor) described in the design, perform a full stack trace.

#### 2a. Trace the chain

Follow the logical chain from entry to output, step by step:

1. **Entry** — what triggers this path, what is the calling context
2. **Input** — what data arrives, in what form, from where
3. **Input validation** — is input validated, what happens on invalid input
4. **Each transformation step** — what changes, what types flow through, what is returned
5. **External calls** — what libraries/imports are called, what they actually return
6. **State changes** — what state is modified, what side effects occur
7. **Output** — what is returned, in what form, where it goes

**Trace rule**: at each step, write out explicitly what data exists and what form it takes. Do not skip steps — "and then it works" is not a valid trace.

**Contract interaction tracing** — for each step where entities interact across boundaries:

1. **Interface ↔ Type interaction**: when entity A receives or returns a type from `Imports`/`Usages`, verify:
   - the type is declared in the source CODEMANIFEST
   - the type's shape (fields, methods, properties) matches what the entity expects
   - if mismatch — record as a **CODEMANIFEST issue** (severity: Critical)

2. **Type ↔ Mutation interaction**: for each `Type::` mutation in the chain:
   - verify the base type exists with correct name (alias from `Imports` or qualified name from `Usages`)
   - verify the mutation target's declared methods/properties are compatible with the base type
   - for multi-level mutations (`A::B::Cls`), verify each segment is resolvable and compatible
   - if any segment is broken — record as a **CODEMANIFEST issue** (severity: Critical)

3. **Interface ↔ Interface interaction**: when entity A calls entity B or passes data to it:
   - verify output type of A matches input type expected by B at the **contract level** (not just implementation)
   - verify error types are compatible
   - verify shared type references resolve to the same actual type
   - if mismatch — record as a **CODEMANIFEST issue** (severity: High or Critical depending on impact)

#### 2b. Checkpoint verification

At **each step** in the chain, verify:

- **Type continuity**: does the output type of step N match the input type of step N+1?
- **Logical correctness**: is the transformation actually correct? (e.g., if you need to filter by status "active", does the logic actually check for "active" and not for something else?)
- **Missing steps**: is there a gap between what the contract requires and what the design provides?
- **Error paths**: what happens when this step fails? Is the error handled? Does it propagate correctly?
- **Edge cases at this step**: what happens with empty input, None/null, wrong type, boundary values, concurrent access?

If a checkpoint fails — record the issue: exact location in the chain, what is wrong, what should happen instead.

**Contract consistency checkpoints** — additionally verify:
- **Cross-entity type continuity**: if step N in entity A outputs type T and step M in entity B expects type T, does T mean the same thing in both contexts? (same `Imports` source, same alias, same shape)
- **Mutation contract alignment**: if a `Type::` mutation produces a type used elsewhere, does the mutated contract satisfy all consumers?
- **Annotation ↔ entity consistency**: do annotations reference types/usages/parameters that actually exist in the CODEMANIFEST?

If a contract consistency checkpoint fails — classify as a **CODEMANIFEST issue** (the contract itself has an error), not a design issue. Propose a fix to the CODEMANIFEST.

#### 2c. External dependency verification

For each external call in the chain:

- Read the actual library documentation or Usages spec
- Verify that the called method/function exists and returns what the design assumes
- Verify the calling convention is correct (arguments order, kwargs, etc.)
- Verify the return type matches what the next step expects

For each imported usage from `Imports` → `Usages`:

- Verify the referenced file exists at `{from_path}/.usages/{usage_name}.md`
- Read the imported usage file and verify its content matches what the design assumes
- Verify the imported usage is used correctly (it provides practice guidance, not contractual obligations)
- Check that the design does not treat an imported usage as a type contract

For local usages categorization in the design document:

- Verify that functional categories are semantically distinct — no two categories should cover the same domain
- Verify that practices placed in the same category file are actually related by function
- Verify that existing `.usages/` files in the cell were checked and matched categories were extended, not duplicated

---

### Step 3: Test Logic Verification

For **each test scenario** described in the design, produce a **detailed test trace** with the following structure for every test case.

#### Required format per test case

Each test case MUST be written out with all 6 elements:

1. **Name**: `test_<what>_<scenario>` — self-documenting
2. **Setup**: exact fixture setup (tmp_path contents, mocks, patches) — concrete code or description with exact values
3. **Input**: exact values passed to the function/CLI (arguments, types, structure)
4. **Trace**: step-by-step execution through the code with this exact input — what each helper receives, what it returns, what side effects occur at each step
5. **Assertions**: concrete checks with exact expected values (paths, contents, exit codes, output strings) — written as actual assert statements or equivalent
6. **Sufficiency assessment**: why this test is needed and what regression it prevents

#### 3a. Positive test traces

For each positive test:
1. Write the full 6-element trace
2. Verify the expected output is **correct** based on the design logic traced in Step 2
3. Verify the test input is sufficient — not too trivial to catch real bugs

#### 3b. Negative test trace

For each negative test:
1. Write the full 6-element trace
2. Verify where exactly the code fails and that the failure is handled correctly (right error message, right exit code)
3. Verify the test verifies the **correct** failure mode

#### 3c. Edge case coverage audit

For each entity:
1. List all boundary conditions:
   - empty input, empty collection, empty string
   - None/null values
   - maximum size / boundary values
   - wrong types
   - concurrent access (if applicable)
   - missing dependencies
2. For each boundary condition: write a full 6-element test trace, or record the gap if it belongs in Test gaps section

#### 3d. Test data sufficiency

For each test:
1. Is the test data realistic enough to catch real bugs?
2. Are there enough distinct test cases to cover the described behavior?
3. Does the test data include typical usage patterns, not just trivial "happy path" cases?

---

### Step 4: Report and fix findings (interactive)

Collect all findings from Steps 2 and 3 before presenting them. Sort by severity: Critical → High → Medium → Low → Test gaps → CODEMANIFEST issues.

Separate findings into two categories:
- **Design findings** — issues in the design document (logic errors, missing edge cases, test gaps)
- **CODEMANIFEST findings** — issues in the contract itself (insufficient/inconsistent requirements, broken type chains, missing declarations)

Present findings **one at a time**. For each finding:

#### 4a. Show the finding

Present a single finding with:

- **Category** (Design / CODEMANIFEST)
- **Severity** (Critical / High / Medium / Low / Test gap)
- **Location** — exact reference to design section or CODEMANIFEST file/entity
- **What is wrong** — clear description of the issue
- **Proposed fix** — the exact change needed, not vague advice. For CODEMANIFEST issues: show the exact DSL change. For test gaps: write the full 6-element trace (name, setup, input, trace, assertions, sufficiency)

#### 4b. Ask the user for a decision

Use AskUserQuestion with options:

1. **Apply proposed fix** — apply the fix to the design document or CODEMANIFEST immediately
2. **Skip** — do not fix, move to next finding
3. **Propose alternative** — user describes a different fix approach

#### 4c. Apply the decision

- **Apply proposed fix (design)**: update the design document, then re-verify that the fix doesn't break other chains (trace through affected chains again). Report the re-verification result briefly.
- **Apply proposed fix (CODEMANIFEST)**: edit the CODEMANIFEST file, re-run the linter: `docker run --rm -v .:/project -w /project qarium/goga:latest linter`. If linter reports errors — fix DSL syntax. Re-verify affected design chains against the updated contract.
- **Skip**: record the finding as "skipped" and move on.
- **Propose alternative**: discuss the alternative with the user, agree on the fix, apply it, re-verify affected chains.

#### 4d. Move to next finding

Repeat from 4a for the next finding. Show a brief counter: "Finding 3 of 12".

After all findings are processed, show a summary:

- **Fixed**: N findings (list by severity, split by design/CODEMANIFEST)
- **Skipped**: N findings (list by severity, split by design/CODEMANIFEST)
- **Design document status**: updated / unchanged
- **CODEMANIFEST status**: updated (list files) / unchanged

---

## Output

- Summary of findings: fixed / skipped counts by severity
- Updated design document (if fixes were applied)

---

## Final Self-Check

Before completing, verify:

0. Was `dsl.md` read before reviewing contracts?
1. Was every entry point in the design traced through the full code stack?
2. Was every checkpoint in each chain verified (type, logic, error, edge)?
2a. Were contract interaction checkpoints verified (interface ↔ type, type ↔ mutation, interface ↔ interface)?
3. Were external dependencies verified against actual documentation?
4. Were imported usages from `Imports` → `Usages` verified (file exists, content matches design assumptions)?
5. Was every test scenario traced through (positive, negative, edge)?
6. Was test data sufficiency checked for each test?
7. Was each finding presented one by one with a fix decision?
8. Were approved fixes applied to the design document or CODEMANIFEST?
8a. Were CODEMANIFEST changes re-verified with the linter?
9. Were affected chains re-traced after each fix?
10. Was a summary of fixed/skipped findings provided (split by design/CODEMANIFEST)?
11. Were CODEMANIFEST issues separated from design issues and proposed with concrete DSL fixes?

If any answer is "no" — complete the missing verification before returning.

---

## Retrospective

After completing the main work, perform a retrospective as defined in CLAUDE.md → Skill Retrospective.

Related skills for improvement: `design-by-changes` (source of design document).
