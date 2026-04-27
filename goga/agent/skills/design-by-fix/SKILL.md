# Design by Fix

## Purpose

Diagnoses a **bug** by tracing existing code, identifies the **gap in CODEMANIFEST** that allowed the bug to occur, and updates the contract to close the gap.

You do **not** write implementation code.
You update **CODEMANIFEST files** to make the contract precise enough to prevent the bug.

---

## Behavioral Rules

1. **Never modify implementation code.** Your job is diagnosis and contract refinement. The design document and plan will guide the implementation.

2. **Work through root cause, not symptoms.** Do not propose fixes for the surface behavior — trace the code to find the underlying cause.

3. **Ask one question per message via `AskUserQuestion`.** One focused question with 2-4 concrete answer options presented as interactive checkboxes — wait for the user's selection, then ask the next. Do not batch questions. Never ask open-ended questions without proposing selectable variants.

4. **Structure every response** using the response format below. This discipline prevents jumping to conclusions.

5. **Every bug implies a CODEMANIFEST gap.** If code behaves incorrectly, the contract was not precise enough to prevent it. Find what detail is missing or ambiguous.

6. **Always use `AskUserQuestion` with interactive checkbox options.** When asking the user anything — a clarification, confirmation, or decision — always present 2-4 concrete answer options as interactive checkboxes. Never ask open-ended questions without proposing selectable variants.

---

## Sources of Truth

Use the following sources jointly, when available:

1. `dsl.md` — DSL specification (in skill directory). Read before analyzing or editing CODEMANIFEST to ensure correct DSL syntax and semantics
2. `CODEMANIFEST` — read **all** relevant CODEMANIFEST files to understand the current contract
3. Source code — read actual implementation files related to the bug
3. `goga schema` — cell hierarchy and dependency map
4. Root `Usages` — practices and conventions referenced in the project
5. Git context — recent changes that may have introduced the bug

---

## Steps

### Step 0: Read DSL spec

Read `dsl.md` (in skill directory) to understand CODEMANIFEST DSL rules before analyzing or editing contracts.

### Step 1: Collect input

Accept the user's description of the bug.

The description may be:
- **Brief** — "copy defaults doesn't work" or "command crashes on empty input"
- **Detailed** — a full bug report with steps to reproduce, expected vs actual behavior

If the description is brief — do not ask for clarification yet. Proceed to Step 2 to gather context first. The diagnostic phase (Step 3) will clarify details.

Remember the original description throughout the session.

### Step 2: Context gathering

#### 2a. Read relevant CODEMANIFEST files

Based on the bug description, identify which cells are likely involved. Read their CODEMANIFEST files to understand the current contract.

If the description mentions a specific command, function, or cell — start there. If unclear — run schema first to get orientation.

#### 2b. Run schema

Run:
```
docker run --rm -v .:/project -w /project qarium/goga:latest schema
```

This provides the cell hierarchy and helps identify which cells are involved in the bug.

#### 2c. Read source code

Read the implementation files related to the bug. Trace the code path from the entry point to the point of failure.

Look for:
- Mismatches between CODEMANIFEST annotations and actual behavior
- Missing error handling or edge case coverage
- Ambiguous contract terms that could be interpreted multiple ways
- Missing constraints (preconditions, postconditions, invariants)

### Step 3: Diagnostic loop

This is the core iterative process. The loop continues until the root cause is confirmed and the CODEMANIFEST gap is identified.

#### Response format

**Every response in the diagnostic phase** MUST follow this structure:

1. **Understanding** — what is known so far from the bug description and code analysis
2. **Unclear** — what remains underspecified or untraced
3. **Hypotheses** — concrete assumptions about the root cause (with rationale)
4. **Questions** — one targeted question with 2-4 concrete answer options presented as interactive checkboxes (use `AskUserQuestion`)
5. **Next step** — what will be done next once the question is resolved

This format is mandatory. Do not skip sections. If a section is empty — state "None" explicitly.

#### 3a. Initial analysis

Based on the code trace and contract analysis gathered in Step 2:

1. **Identify the failure point** — where exactly the code diverges from expected behavior
2. **Trace back from failure** — what inputs, conditions, or state led to this point
3. **Map to CODEMANIFEST** — which contract element(s) are related to the failure

Present the initial analysis using the response format above.

#### 3b. Diagnostic discussion

Engage in an interactive discussion with the user:

- Propose root cause hypotheses
- Discuss which CODEMANIFEST details are missing or ambiguous
- Explore whether the gap is local (one entity) or systemic (cross-cutting concern)
- Consider whether similar gaps exist in related entities

Every response follows the response format. One question per message. Wait for the user's answer before asking the next question.

#### 3c. Present CODEMANIFEST gap

Once the root cause is confirmed, present:

1. **Root cause** — what exactly is wrong and why
2. **CODEMANIFEST gap** — which contract detail is missing, ambiguous, or incorrect
3. **Proposed CODEMANIFEST changes** — specific edits to close the gap
4. **Impact** — which entities, cells, or contracts are affected by the changes

Pause for user feedback. Fix issues before continuing.

#### 3d. Loop or proceed

- **Root cause confirmed, gap identified** → exit the diagnostic loop, proceed to Step 4
- **User requests changes** → incorporate feedback, return to Step 3b

### Step 4: Gap analysis

Before writing CODEMANIFEST changes, systematically verify:

1. **Completeness** — does the proposed change fully close the gap, or are there related gaps in the same area?
2. **Consistency** — do the changes create contradictions with other parts of the contract?
3. **Side effects** — do the changes affect other cells or entities that import from the changed cell?
4. **DSL rule compliance** — are the proposed changes valid CODEMANIFEST syntax?

Run `docker run --rm -v .:/project -w /project qarium/goga:latest schema --depends-on <changed_cell>` to find affected cells.

Present findings to the user. Fix confirmed issues.

### Step 5: Save CODEMANIFEST changes

Apply the approved changes to CODEMANIFEST file(s).

- Ensure all entities, usages, imports, and annotations are properly formatted per the DSL.
- Do not modify implementation code.
- Follow annotation writing recommendations when writing or updating annotations:
  - Begin each annotation with a clear statement of purpose
  - Describe every parameter with `` `param_name`: description `` syntax
  - For non-trivial logic, include `Algorithm:` with numbered steps
  - For constraints and edge cases, include `Requirements:` section
  - Document return value format when not obvious from signature
  - Include usage examples when they help clarify the contract
  - No placeholders (TBD, TODO) — every instruction must be concrete
  - Each annotation must have exactly one interpretation
  - Keep consistent style across the CODEMANIFEST file
  - All backtick references must point to existing entities in the current context

### Step 6: Run linter + self-review

Run:
```
docker run --rm -v .:/project -w /project qarium/goga:latest linter
```

Fix any DSL syntax errors.

Then perform a **self-review** of the changed CODEMANIFEST:

1. No placeholders — fill in or remove any TBD, TODO, incomplete descriptions
2. Cross-cell consistency — Interfaces and Imports align across files
3. Scope — changes are focused on closing the identified gap, no scope creep
4. Clarity — every declaration has one unambiguous interpretation

Fix issues inline. Present the final result to the user for confirmation.

### Step 7: Generate design document

Now that CODEMANIFEST files are updated and validated, generate a design document by invoking the `design-by-changes` skill.

Inform the user:

> CODEMANIFEST files updated and validated. Now generating the design document based on these contract changes...

Then invoke the `design-by-changes` skill and follow it from **Step 1** through completion. The skill will:
- Detect CODEMANIFEST changes via git diff (the changes just saved in Step 5)
- Perform gap analysis between contract and current implementation
- Trace code stack for each entry point
- Analyze usages and cross-cutting concerns
- Generate test scenarios
- Save the design document to `docs/design/<feature-name>.md`

The feature name for the design document should be derived from the bug description or confirmed with the user.

---

## Output

- Updated CODEMANIFEST file(s) with the closed gap
- Design document at `docs/design/<feature-name>.md`
- No implementation code

---

## Reasoning Discipline

Separate:
- **Facts** — directly observable in the code or stated in the contract
- **Assumptions** — inferences about intent or expected behavior
- **Open questions** — unresolved points that need user input

Never mix them.

---

## Final Self-Check

Before completing the response, verify:

0. Was `dsl.md` read before analyzing or editing contracts?
1. Was the bug description collected?
2. Were relevant CODEMANIFEST files read?
3. Was `goga schema` run to understand cell dependencies?
4. Was source code traced to the failure point?
5. Was every diagnostic response structured (Understanding/Unclear/Hypotheses/Questions/Next step)?
6. Was the root cause confirmed, not just the symptom?
7. Was the CODEMANIFEST gap identified — what detail was missing or ambiguous?
8. Was gap analysis performed (completeness, consistency, side effects)?
9. Were CODEMANIFEST changes saved?
10. Was the linter run after saving?
11. Was a self-review performed (no placeholders, cross-cell consistency, scope, clarity)?
12. Are facts, assumptions, and open questions separated?
13. Was the design document generated via `design-by-changes` after saving CODEMANIFESTs?

If any answer is "no" — resolve before completing.

---
