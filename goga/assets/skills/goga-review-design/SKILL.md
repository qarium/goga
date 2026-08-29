---
name: goga-review-design
description: Design document verification via code stack tracing
---
# Design Review

## Purpose

Verifies the design document (the file at the path printed by `goga history path -f design.md`) for **logical correctness** by tracing the full code stack for each entry point and test scenario. This is a **verification pass** — the goal is to find logical errors before plan creation.

You do **not** write implementation code.
You **trace** each logical chain and **find** where the logic breaks.

---

## Core Principle

**Trace, do not assume.** For each logical chain, mentally execute the code path step by step. Read actual source files and library documentation to verify correctness. If a step cannot be verified due to missing information — that in itself is a remark.

### User Interaction Rule

**Always offer answer choices.** When requesting a user decision or confirmation — always provide 2–4 concrete options. Never ask open-ended questions without selectable choices.

### CODEMANIFEST Editing

When tracing reveals errors **in the contract itself** (not in the design's interpretation of the contract), you **must** propose CODEMANIFEST edits. These are not design-level remarks — they are contract-level errors that block correct implementation regardless of design structure.

Conditions requiring CODEMANIFEST editing:
- **Insufficient requirements**: missing type declarations, incomplete signatures, absent method/property descriptions
- **Contradictory requirements**: contradictions between entity interfaces, type mismatches between interacting entities
- **Contract interaction errors**: broken type chains between interfaces, `Type::` mutations referencing non-existent or incompatible types, interface contracts diverging in data formats

All CODEMANIFEST edits must be **proposed to the user** before applying.

---

## Phases

### Phase 1: Context Loading

1. Load the DSL specification and DSL application principles:
   - Use the **Skill tool** to invoke `goga-cell` — for understanding CODEMANIFEST DSL rules before reviewing contracts
     (document structure, signature syntax, Imports rules, Usages rules, Annotations rules, types, mutations, embeddings, constraints)
   - Use the **Skill tool** to invoke `goga-cookbook` — for understanding cell design principles and CODEMANIFEST
     (when to use Entity vs Routine, when to apply mutations and embeddings, usage file authoring principles, cell granularity)
2. Read the design document from the path printed by `goga history path -f design.md`
3. Read all relevant CODEMANIFEST files referenced by the design
4. Read existing source files referenced by the design (if any)
5. Execute `goga schema --help` to understand the command, then execute `goga schema` to obtain the full project dependency graph. Use `--depends-on <cell_path>` to discover cells that depend on cells modified by the design. This ensures the review covers all affected cells.
6. **Reading Usage specifications by reference**: determine which Usages to read based on references:
   - **Always read root Usages** — Usages (files from `.goga/usages/`) referenced by global `Annotations` in the CODEMANIFEST header (via backtick syntax) are always read
   - **Always read Usages of modified entities** — for each entity covered by the design, scan its annotations for references (backticks) to Usages. All referenced Usages are read
   - **Skip unreferenced Usages** — Usage entries not referenced by global `Annotations` AND not referenced by annotations of any covered entity are skipped

---

### Phase 2: Code Stack Trace Verification

For **each entry point** (method, function, constructor) described in the design, perform a full stack trace.

#### Step 1. Chain Tracing

Trace the logical chain from entry to exit, step by step:

1. **Entry** — what initiates this path, what is the calling context
2. **Input data** — what data arrives, in what form, from where
3. **Input validation** — whether input data is validated, what happens on invalid input
4. **Each transformation step** — what changes, what types pass through, what is returned
5. **External calls** — what libraries/imports are called, what they actually return
6. **State changes** — what state is modified, what side effects occur
7. **Exit** — what is returned, in what form, where it goes

**Tracing rule**: at each step, explicitly write down what data exists and in what form. Do not skip steps — "and then it works" is not an acceptable trace.

**Contract interaction tracing** — for each step where entities interact across boundaries:

1. **Interface ↔ Type interaction**: when entity A receives or returns a type from `Imports`/`Usages`, verify:
   - the type is declared in the source CODEMANIFEST
   - the type shape (fields, methods, properties) matches the entity's expectations
   - on mismatch — record as a **CODEMANIFEST issue** (criticality: Critical)

2. **Type ↔ Mutation interaction**: for each `Type::` mutation in the chain:
   - verify that the base type exists with the correct name (alias from `Imports` or qualified name from `Usages`)
   - verify that declared methods/properties of the mutation target are compatible with the base type
   - for multi-level mutations (`A::B::Cls`) verify that each segment is resolvable and compatible
   - if any segment is broken — record as a **CODEMANIFEST issue** (criticality: Critical)

3. **Interface ↔ Interface interaction**: when entity A calls entity B or passes data to it:
   - verify that A's output type matches B's expected input type at the **contract level** (not just implementation)
   - verify error type compatibility
   - verify that shared type references resolve to the same actual type
   - on mismatch — record as a **CODEMANIFEST issue** (criticality: High or Critical depending on impact)

#### Step 2. Checkpoint Verification

At **each step** in the chain, verify:

- **Type continuity**: does the output type of step N match the input type of step N+1?
- **Logical correctness**: does the transformation work correctly? (e.g., if filtering by "active" status, does the logic actually check for "active" and not something else?)
- **Missing steps**: is there a gap between what the contract requires and what the design provides?
- **Error paths**: what happens on error at this step? Is the error handled? Does it propagate correctly?
- **Boundary cases at this step**: what happens on empty input, None/null, wrong type, boundary values, concurrent access?

If a checkpoint fails — record a remark: exact location in the chain, what is wrong, what should happen.

**Contract consistency checkpoints** — additionally verify:
- **Cross-entity type continuity**: if step N in entity A outputs type T, and step M in entity B expects type T, does T mean the same thing in both contexts? (same `Imports` source, same alias, same shape)
- **Mutation contract consistency**: if a `Type::` mutation creates a type used anywhere else, does the mutated contract satisfy all consumers?
- **Annotation ↔ entity consistency**: do annotations reference types/usages/parameters that actually exist in the CODEMANIFEST?

If a contract consistency checkpoint fails — classify as a **CODEMANIFEST issue** (the error is in the contract itself), not a design issue. Propose a CODEMANIFEST fix.

#### Step 3. External Dependency Verification

For each external call in the chain:

- Read the actual library documentation or Usage specification
- Verify that the called method/function exists and returns what the design assumes
- Verify calling convention correctness (argument order, named parameters, etc.)
- Verify that the return type matches the expectations of the next step

For each imported usage from `Imports` → `Usages`:

- Verify that the specified file exists at path `{from_path}/.usages/{usage_name}.md`
- Read the imported usage file and verify that its content matches the design's assumptions
- Verify that the imported usage is used correctly (it provides practical guidelines, not contractual obligations)
- Ensure the design does not treat the imported usage as a type contract

For categorizing local usages in the design document:

- Verify that functional categories are semantically distinct — no two categories should cover the same domain
- Verify that practices placed in the same category file are actually related by function
- Verify that existing `.usages/` files in the cell have been reviewed and matching categories were extended, not duplicated

---

### Phase 3: Test Logic Verification

For **each test scenario** described in the design, create a **detailed test trace** with the following structure for each test case.

#### Mandatory Format for Each Test Case

Each test case MUST be described by all 6 elements:

1. **Name**: `<test name>` — self-documenting, following target language conventions
2. **Setup**: exact fixture configuration (tmp_path contents, mocks, patches) — specific code or description with exact values
3. **Input**: exact values passed to the function/CLI (arguments, types, structure)
4. **Trace**: step-by-step code execution with this exact input — what each helper receives, what it returns, what side effects occur at each step
5. **Assertions**: specific checks with exact expected values (paths, contents, return codes, output strings) — written as actual assert statements or equivalent
6. **Sufficiency assessment**: why this test is needed and what regression it prevents

#### Step 1. Positive Test Traces

For each positive test:
1. Write a complete 6-element trace
2. Verify that the expected result is **correct** based on the design logic traced in Phase 2
3. Verify that test input is sufficient — not too trivial to catch real bugs

#### Step 2. Negative Test Traces

For each negative test:
1. Write a complete 6-element trace
2. Verify exactly where the code fails and that the error is handled correctly (correct error message, correct return code)
3. Verify that the test checks the **correct** failure mode

#### Step 3. Boundary Case Coverage Audit

For each entity:
1. Enumerate all boundary conditions:
   - empty input, empty collection, empty string
   - None/null values
   - maximum size / boundary values
   - wrong types
   - concurrent access (if applicable)
   - missing dependencies
2. For each boundary condition: write a complete 6-element test trace or record a gap if it belongs in the test gaps section

#### Step 4. Test Data Sufficiency

For each test:
1. Are the test data realistic enough to catch real bugs?
2. Are there enough different test cases to cover the described behavior?
3. Do the test data include typical usage patterns, not just trivial "happy path" cases?

---

### Phase 4: Report and Resolve Remarks (Interactive)

Collect all remarks from Phases 2 and 3 before presenting them. Sort by criticality: Critical → High → Medium → Low → Test Gaps → CODEMANIFEST Issues.

Divide remarks into two categories:
- **Design remarks** — issues in the design document (logical errors, missing boundary cases, test gaps)
- **CODEMANIFEST remarks** — issues in the contract itself (insufficient/contradictory requirements, broken type chains, missing declarations)

Present remarks **one at a time**. For each remark:

#### Step 1. Show the Remark

Present one remark with:

- **Category** (Design / CODEMANIFEST)
- **Criticality** (Critical / High / Medium / Low / Test Gap)
- **Location** — exact reference to the design section or CODEMANIFEST file/entity
- **What is wrong** — clear description of the problem
- **Proposed fix** — the exact change needed, not vague advice. For CODEMANIFEST issues: show the exact DSL change. For test gaps: write the complete 6-element trace (name, setup, input, trace, assertions, sufficiency)

#### Step 2. Request User Decision

Use AskUserQuestion with choices:

1. **Apply the proposed fix** — apply the fix to the design document or CODEMANIFEST immediately
2. **Propose an alternative** — the user describes a different approach to fixing

#### Step 3. Apply the Decision

- **Apply proposed fix (design)**: update the design document, then re-verify that the fix does not break other chains (re-trace affected chains). Briefly report the re-verification result.
- **Apply proposed fix (CODEMANIFEST)**: edit the CODEMANIFEST file, re-run the linter: `goga lint`. If the linter reports errors — fix the DSL syntax. Re-verify affected design chains against the updated contract.
- **Skip**: record the remark as "skipped" and continue.
- **Propose an alternative**: discuss the alternative with the user, agree on a fix, apply it, re-trace affected chains.

#### Step 4. Proceed to Next Remark

Repeat from Step 1 for the next remark. Show a brief counter: "Remark 3 of 12".

After processing all remarks, show the summary:

- **Fixed**: N remarks (breakdown by criticality, split by design/CODEMANIFEST)
- **Skipped**: N remarks (breakdown by criticality, split by design/CODEMANIFEST)
- **Design document status**: updated / unchanged
- **CODEMANIFEST status**: updated (list of files) / unchanged

---

## Output

- Remark summary: count of fixed / skipped by criticality
- Updated design document (if fixes were applied)

---

## Final Self-Check

Before completion, verify:

1. Was the DSL specification loaded via `goga-cell` and `goga-cookbook` skills before reviewing contracts?
2. Was each entry point in the design traced through the full code stack?
3. Was each checkpoint in each chain verified (type, logic, error, boundary case)?
4. Were contract interaction checkpoints verified (interface ↔ type, type ↔ mutation, interface ↔ interface)?
5. Were external dependencies verified against actual documentation?
6. Were imported usages from `Imports` → `Usages` verified (file exists, content matches design assumptions)?
7. Was each test scenario traced (positive, negative, boundary)?
8. Was test data sufficiency verified for each test?
9. Was each remark presented one at a time with a fix decision?
10. Were approved fixes applied to the design document or CODEMANIFEST?
11. Were CODEMANIFEST changes re-verified by the linter?
12. Were affected chains re-traced after each fix?
13. Were summary totals of fixed/skipped remarks provided (split by design/CODEMANIFEST)?
14. Were CODEMANIFEST issues separated from design issues and proposed with specific DSL fixes?

If at least one answer is "no" — complete the missing verification before returning.

---
