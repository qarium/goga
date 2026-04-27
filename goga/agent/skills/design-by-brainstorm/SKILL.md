# Design by Brainstorm

## Purpose

Creates **CODEMANIFEST contracts** through an iterative brainstorming process. The user provides a description of what needs to be designed — from a single sentence to a detailed specification — and the agent collaboratively designs the contract through exploration, discussion, and refinement.

You do **not** write implementation code.
You create **CODEMANIFEST files** that define the contract for the feature.

---

## Behavioral Rules

1. **Never write CODEMANIFEST until architecture is understood.** Do not generate DSL prematurely — first decompose, discuss, verify.

2. **Work through hypotheses.** Instead of open-ended questions ("how should this work?"), propose concrete hypotheses ("It seems you need UserService with CRUD and auth. Is that right?").

3. **Ask one question per message.** One focused question with 2-4 concrete answer options — wait for the user's selection, then ask the next. Do not batch questions. Never ask open-ended questions without proposing selectable variants.

4. **Structure every response** in the brainstorm phase using the response format below. This discipline prevents chaotic or unfocused discussion.

5. **Minimal viable contract first.** If the user describes more than needed — propose a minimal version and let them expand.

6. **Split large scopes.** If the user's description spans multiple independent subsystems — flag this, propose splitting into separate CODEMANIFEST passes, then brainstorm the first one.

7. **Always propose answer options.** When asking the user anything — a clarification, confirmation, or decision — always present 2-4 concrete answer options. Never ask open-ended questions without proposing selectable variants.

---

## Sources of Truth

Use the following sources jointly, when available:

1. `dsl.md` — DSL specification (in skill directory). Read before creating CODEMANIFEST to ensure correct DSL syntax and semantics
2. Root `Usages` — read **all** root Usages entries to understand available practices and tools
3. `goga schema` — cell hierarchy and dependency map of the existing project
3. Existing `CODEMANIFEST` files — current contracts in the project (if any)
4. Current package file tree and source files

---

## Steps

### Step 1: Collect input

Accept the user's description of what needs to be designed.

The description may be:
- **Brief** — a single sentence or feature name (e.g., "add user authentication")
- **Detailed** — a full specification with requirements, constraints, and examples

If the description is brief — do not ask for clarification yet. Proceed to Step 2 to gather architectural context first. The brainstorm phase (Step 3) will clarify missing details.

Remember the original description throughout the session.

### Step 2: Architecture discovery

#### 2a. Read DSL spec

Read `dsl.md` (in skill directory) to understand CODEMANIFEST DSL rules before designing contracts.

#### 2b. Read Usages

Read all root-level `Usages` entries from all CODEMANIFEST files in the project. This provides the catalog of available practices, libraries, and tools that the new design can reference.

If a Usages entry value is a file path (relative to the CODEMANIFEST location, e.g. `.usages/auth.md`) — read that file to understand the practice specification. Adapt depth based on context:

- **Related to the user's topic** — read the spec file fully, understand APIs and patterns
- **Unrelated or unclear relevance** — note the practice exists, skip the spec file for now
- **No existing CODEMANIFESTs** — skip this step entirely

During brainstorm, if a question arises about a specific practice that wasn't fully read — go back and read the spec file at that point.

#### 2c. Run schema

Run `docker run --rm -v .:/project -w /project qarium/goga:latest schema --help` to understand the command capabilities.

Then run `docker run --rm -v .:/project -w /project qarium/goga:latest schema` to get the full project cell hierarchy.

#### 2d. Relevance analysis

Based on the schema output and the user's description, determine:

- Does the project already have an architecture (cells, existing CODEMANIFESTs)?
- Which existing cells might be related to what the user wants to design?
- Is this a new independent feature, an extension of existing cells, or a modification of existing contracts?

This analysis may not yield a definitive answer immediately — that is acceptable. The brainstorm phase will refine understanding.

If the project has no existing architecture (empty or new project) — note this and proceed to brainstorm from scratch.

If existing architecture is found — read the relevant CODEMANIFEST files for cells that appear related. Use `--depends-on <cell_path>` to find dependent cells if needed.

### Step 3: Brainstorm loop

This is the core iterative process. The loop continues until the user confirms the solution is complete.

#### Response format

**Every response in the brainstorm phase** (3a, 3b) MUST be a question with answer options. The question is the primary deliverable — not context, not analysis.

Before the question, state briefly (1-2 lines total):
- **Context**: what is being decided right now
- **Hypothesis**: what you assume the answer is

Then ask the question with 2-4 concrete answer options.

#### 3a. Initial analysis

Based on the user's description and architectural context gathered in Step 2:

1. **Identify key concepts** — what entities, interfaces, types are implied by the description
2. **Identify dark corners** — aspects that are unclear, underspecified, or that require design decisions
3. **Map to existing architecture** — how does the new feature relate to existing cells, imports, usages

**Scope check:** If the description contains multiple independent subsystems — stop and propose decomposition into sub-projects. Then brainstorm the first sub-project through the normal flow. Do not try to design everything at once.

Present the initial analysis using the response format above.

#### 3b. Brainstorm discussion

Engage in an interactive discussion with the user:

- Propose contract structure (entities, their responsibilities, relationships) as hypotheses
- Discuss design decisions and trade-offs
- Explore edge cases and error handling strategies
- Align usages with existing practices from root Usages
- Resolve ambiguities from the original description
- Keep the contract minimal — see Rule 5

During discussion, actively use diagrams to visualize:

- **Entity relationships** — how entities interact and depend on each other
- **Data flows** — how data moves through the system
- **Cell boundaries** — where contracts split across packages

If drawing diagrams, draw ASCII diagrams. Update diagrams as understanding evolves.

Every response follows the response format. One question per message. Wait for the user's answer before asking the next question.

#### 3c. Propose approaches

Once understanding is sufficient, outline **2-3 architectural options**:

- For each: describe cell structure, key entities, trade-offs
- Indicate which option you recommend and why
- Let the user choose or combine elements from different options

#### 3d. Present solution

Based on the chosen approach, present the **concrete proposal** progressively:

1. **Cell structure** — which cells, where located, boundaries
2. **Entity definitions** — interfaces, types, their methods, properties, annotations
3. **Usages and Imports** — practices used, cross-cell dependencies
4. **Usages categorization** — for each cell, propose functional categories:
   - Identify distinct functional domains within the cell's logic
   - Propose which practices belong to which category
   - If the cell already has `.usages/` files — map new practices to existing categories where they fit, propose new files only for new domains
   - Inline practices for short, entity-specific, non-reusable instructions
5. **Data flow diagram** — ASCII diagram of entity interactions

Pause after each section for user feedback. Fix issues before continuing to the next. Do not dump the entire proposal at once.

#### Writing annotations

When writing or updating annotations, follow these recommendations:

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

#### 3e. Loop or proceed

After all sections are approved:

- **All sections approved** → exit the brainstorm loop, proceed to Step 4
- **User requests changes** → save the current proposal as the session artifact, incorporate feedback, return to Step 3b with the updated artifact

The session artifact accumulates across iterations — each loop builds on the previous state, not from scratch.

### Step 4: Gap analysis

Before writing CODEMANIFEST, systematically verify the approved solution for:

1. **Missing elements** — methods that are referenced but not declared, types that are used but not defined
2. **Logical holes** — create without read, write without error handling, input without validation
3. **Inconsistencies** — type mismatches between interacting entities, naming inconsistencies, conflicting annotations
4. **DSL rule violations** — incorrect entity kinds, broken Imports references, invalid Type:: mutations
5. **Cell boundary issues** — misplaced entities, missing Imports for cross-cell dependencies, orphaned Usages

Present findings to the user. Fix confirmed issues. Return to Step 3d if fixes change the architecture significantly.

### Step 5: Save to CODEMANIFEST

Write the approved contract to CODEMANIFEST file(s).

- Determine file locations based on the schema structure and cell boundaries identified during brainstorm.
- Create new CODEMANIFEST files if needed, or modify existing ones.
- Ensure all entities, usages, imports, and annotations are properly formatted per the DSL.

### Step 6: Run linter + self-review

Run:
```
docker run --rm -v .:/project -w /project qarium/goga:latest linter
```

Fix any DSL syntax errors.

Then perform a **self-review** of the saved CODEMANIFEST:

1. No placeholders — fill in or remove any TBD, TODO, incomplete descriptions
2. Cross-cell consistency — Interfaces and Imports align across files
3. Scope — no features that belong in a separate CODEMANIFEST
4. Clarity — every declaration has one unambiguous interpretation

Fix issues inline. Present the final result to the user for confirmation.

### Step 7: Generate design document

Now that CODEMANIFEST files are saved and validated, generate a design document by invoking the `design-by-changes` skill.

Inform the user:

> CODEMANIFEST files saved and validated. Now generating the design document based on these contracts...

Then invoke the `design-by-changes` skill and follow it from **Step 1** through completion. The skill will:
- Detect CODEMANIFEST changes via git diff (the files just saved in Step 5)
- Perform gap analysis between contract and current implementation
- Trace code stack for each entry point
- Analyze usages and cross-cutting concerns
- Generate test scenarios
- Save the design document to `docs/design/<feature-name>.md`

The feature name for the design document should be derived from the original brainstorm description or confirmed with the user.

---

## Output

- CODEMANIFEST file(s) with the designed contract
- Design document at `docs/design/<feature-name>.md`
- No implementation code

---

## Reasoning Discipline

Separate:
- **Facts** — directly stated by the user or observable in the workspace
- **Assumptions** — cautious inferences made during brainstorm
- **Open questions** — unresolved points that need user input

Never mix them.

---

## Final Self-Check

Before completing the response, verify:

1. Was `dsl.md` read before creating CODEMANIFEST?
2. Was `goga schema` run to understand existing architecture?
3. Was relevance to existing architecture analyzed?
4. Was scope checked — split if too large?
5. Was every brainstorm response structured (Understanding/Unclear/Hypotheses/Questions/Next step)?
6. Were 2-3 architectural options proposed before settling on one?
7. Was the solution presented progressively with pauses for feedback?
8. Were diagrams used to visualize the solution?
9. Was gap analysis performed before saving CODEMANIFESTs?
10. Was the linter run after saving CODEMANIFESTs?
11. Was a self-review performed (no placeholders, cross-cell consistency, scope, clarity)?
12. Are facts, assumptions, and open questions separated?
13. Was the contract kept minimal — no unnecessary entities or features?
14. Was the design document generated via `design-by-changes` after saving CODEMANIFESTs?

If any answer is "no" — resolve before completing.

---
