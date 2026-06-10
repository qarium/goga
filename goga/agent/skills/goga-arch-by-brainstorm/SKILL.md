---
name: goga-arch-by-brainstorm
description: Designing a cells architecture plan through brainstorm
---
# Designing a Cells Architecture Plan

## Purpose

Creates an **architecture plan** — a structured document describing which cells, CODEMANIFEST files, and .usages files need to be created and in what order.
The user provides a description of what needs to be designed — from one sentence to a detailed specification — and the agent collaboratively designs
through exploration, discussion, and refinement.

---

## Dialogue Rules

1. **Do not read implementation source code.** Design is conducted at the level of CODEMANIFEST, project schema, and practices.

2. **The user's description is always an architecture task.** Any description, from one sentence to a detailed specification,
   is input data for the algorithm. Do not decide for the user that a task is "not architectural" — follow the algorithm
   completely for any description.

3. **Work through hypotheses.** Instead of open-ended questions ("how should this work?"), offer concrete hypotheses
   ("It looks like you need a UserService with CRUD and authorization. Is that correct?").

4. **Ask one question per message.** One focused question with 2-4 concrete answer options — wait for
   the user's selection, then ask the next one. Do not group questions. Never ask open-ended questions without
   proposed answer options.

5. **Structure every response.** This discipline prevents chaotic or unfocused discussion.

6. **Split large domains.** If the user's description covers several independent subsystems — point this out,
   suggest splitting into separate brainstorm passes, then conduct the first one.

7. **Use ASCII diagrams for visualization**:
    - **Entity relationships** — how entities interact and depend on each other
    - **Data flows** — how data moves through the system
    - **Cell boundaries** — where contracts are separated by cell

---

### Phase 1: Input Collection

Accept the user's description of what needs to be designed.

The description can be:
- **Brief** — one sentence or a feature name (e.g., "add user authorization")
- **Detailed** — a complete specification with requirements, constraints, and examples
- **From a task file** — path to a file `docs/tasks/<topic>.md`, produced by the `goga-task-by-proposing` skill

If the user specified a task file — read it and use the sections directly:
- **Current state** → context for primary analysis (Phase 4, Step 1)
- **Description and Boundaries** → basis for design
- **Stack and External Dependencies** → account for when choosing technologies
- **Acceptance Criteria** → condition for final approval (Phase 4, Step 7)
- **Risks and Constraints** → account for during primary analysis (Phase 4, Step 1)
- **Scope** → if the task is split into subtasks — conduct a brainstorm for one subtask at a time

If the description is brief — do not ask for clarifications yet. The brainstorm phase (Phase 4) will clarify missing details.
Remember the original description throughout the entire session.

### Phase 2: Loading DSL Specification and DSL Application Principles

#### Step 1: Load DSL Specification

To understand cell definitions and CODEMANIFEST file contents: use **Skill tool** to call `goga-cell`.
Use the `goga-cell` skill for:
 - Understanding cell structure — what a cell consists of (CODEMANIFEST, `.usages/`), how the document is organized (header, body, footer)
 - Understanding CODEMANIFEST directive purposes — what `Imports`, `Usages`, `Annotations`, types, mutations, embeddings are responsible for
 - Checking syntactic correctness — key casing, signature rules, `location` restrictions, declaration structure

#### Step 2: Load DSL Application Principles

To understand the principles of working with cells and CODEMANIFEST files: use **Skill tool** to call `goga-cookbook`.
Use the `goga-cookbook` skill for:
 - Determining the need to create a cell — when to extract a separate cell, and when to extend an existing one
 - Choosing between Entity and Routine — when a type should have `methods`/`properties`, and when it is a single operation
 - Determining granularity — how large or small a cell should be, signs of too fine or coarse splitting
 - Choosing the Usages connection form — file, inline, or URL, in which cases each form is appropriate
 - Determining the design order — design cells from leaves to root, starting with cells without dependencies
 - Understanding when to use mutations (`Object::Target`) and embeddings (`->Entity: {}`), and when Imports are sufficient
 - Principles of writing usage files in `<cell_path>/.usages/` — structure, content, quality recommendations

#### Step 3: Load Language Implementation Rules

Use **Skill tool** to call `goga-lang-disp` — get the language skill for the target language.
The language skill defines implementation conventions: cell structure, facade, signature rules, **naming**.
Examples in other skills may use naming from one language (e.g., snake_case), while the target language
requires another (e.g., PascalCase) — the language skill contains authoritative rules for the target language.

Actively use the loaded DSL specification, DSL Application Principles, and language rules during design and analysis.

### Phase 3: Project Context Exploration

The goal is to gather facts about the current state of the project.

#### Step 1. Get the project schema

Run `goga schema --help` to understand the command's capabilities.

Then run `goga schema` to get the complete cell hierarchy of the project. To understand what a cell is, use the `goga-cell` skill.

If the project has no existing architecture — record this as a fact and proceed to Step 2.

#### Step 2. Get base annotations and usages of the project

Use **Skill tool** to call `goga-codemanifest-base`.
The result is base usages and annotations of the project that are mandatory for consideration when designing all CODEMANIFEST files in the plan.

#### Step 3. Read relevant CODEMANIFESTs

Based on the project schema and the user's description from Phase 1 — read the CODEMANIFEST files of those cells that may be
related to the user's topic. To understand where and in what sequence to focus attention, use the `goga-cell` skill.

**Match the user's description to the schema:**
- Names matching cell paths or types in the schema **may be** pointers to existing artifacts —
  verify this by reading CODEMANIFEST and present it as a hypothesis to the user
- Names without matches in the schema **may be** pointers to new artifacts to create
- If the description does not contain specific names — identify affected cells by the meaning of the description
- If names are ambiguous (multiple matches) — clarify through a hypothesis

Use `--depends-on <cell_path>` to search for dependent cells when necessary.

#### Step 4. Read relevant usages

Read the usages of files related to the cells from Step 3, following the rules of the `goga-cookbook` skill.

If the task implies using external libraries or technologies — read usages about them (in `.goga/usages/cooks/`),
to understand available practices for working with these libraries or technologies.

This provides a catalog of available practices, libraries, and tools that the new architecture can reference.

Adapt depth:
- **Related to the user's topic** — read the file completely
- **Indirectly related** — read annotations and key sections
- **No existing CODEMANIFESTs** — skip this step

During the brainstorm (Phase 4), you can return and read a specific practice if a question arises.

### Phase 4: Brainstorm Cycle

Use the `goga-cell` and `goga-cookbook` skills to verify design decisions.

**Principle:** first design types and their interactions without cell boundaries, then group types into cells.
This allows the agent to see all connections between types before cell boundaries hide them.

#### Step 1. Primary analysis

Based on the user's description (Phase 1) and gathered facts (Phase 3), determine:

1. **Key concepts** — what entities, interfaces, types are implied by the description
2. **Dark zones** — aspects that are unclear or require design decisions
3. **Connection to existing architecture** — which existing cells are affected, whether integration is needed
4. **Risks and constraints** — if input is from a task file, account for the "Risks and Constraints" section:
   what constraints may affect design decisions

**Scope check:** If the description covers several independent subsystems — propose splitting into subsystems.
Conduct a brainstorm for one subsystem at a time.

Present the primary analysis to the user.

#### Step 2. Type map

**Goal:** Build a "table of contents" of all types — only names, character (Entity/Routine), brief purpose, and connections between them.
No methods, properties, or details — only the skeleton of the abstract object model.

To understand when a type is an Entity (has state and/or multiple operations), and when it is a Routine
(a single operation) — use the `goga-cookbook` skill.

Based on the primary analysis (Step 1), iteratively build the type map:

1. **Propose a type map hypothesis** — a list of types with character, description, and connections:
   ```
   DocumentRoot      — [Entity] document root. References: HeaderNode, BodyNode
   HeaderNode        — [Entity] document header. References: ImportNode
   ImportNode        — [Entity] import. References: DocumentRoot (resolve)
   ASTRule           — [Entity] validation rule. Accepts: DocumentRoot. Returns: ASTRuleError
   parse_config      — [Routine] config parser. Accepts: str. Returns: Config
   ```

2. **Ask a question** — are any types missing, are any extra, are the connections correct

3. **Wait for feedback** — the user approves or requests changes
   - **Approved** → proceed to Step 3
   - **Not approved** → remember the comments, return to point 1 and propose a corrected map accounting for the feedback.

**Readiness criteria:**
- All types from the user's description are present
- All connections between types are specified (who accepts whom, returns, contains)
- The user has approved the map

#### Step 3. Type detailing

**Goal:** For each type from the map (Step 2), define methods, properties, signatures, and interactions.

To understand when to use mutations (`Object::Target`) and embeddings (`->Entity: {}`),
and when Imports are sufficient — use the `goga-cookbook` skill.

Process types one at a time. The agent sees all connections from the map and correctly designs interactions.
For each type:

1. **Propose detailing** — methods, properties, signatures with parameter types and return values:
   ```
   DocumentRoot(rule: ASTRule)
     properties:
       path -> str
       header -> HeaderNode
       body -> BodyNode
     methods:
       validate() -> ASTRuleError
       find_imports() -> ImportNode

   ASTRule()
     methods:
       check(doc: DocumentRoot) -> ASTRuleError
       fix(doc: DocumentRoot) -> DocumentRoot
   ```

2. **Wait for feedback** — the user approves or requests changes
   - **Approved** → proceed to the next type
   - **Not approved** → remember the comments, return to point 1 and propose corrected detailing accounting for the feedback.

3. **Check consistency** — if the detailing of a type affects already approved types
   (a parameter type changed, a new connection was added), return to the affected types
   and propose necessary adjustments.

**Readiness criteria:**
- Each type has complete detailing (methods, properties, signatures)
- All interactions between types are consistent (parameter types and return values match)
- The user has approved all types

#### Step 4. Distributing types across cells

**Goal:** Distribute the approved types (Step 3) across cells and define cell boundaries.

To understand when to create a separate cell and when to extend an existing one,
and to determine granularity — use the `goga-cookbook` skill.

Propose distribution of types across cells based on type cohesion and responsibility zones:

1. **Propose a cell hypothesis** — which types go into which cell:
   ```
   cell: goga/ast/nodes
     DocumentRoot, HeaderNode, BodyNode, ImportNode, DocumentNode, Node

   cell: goga/ast/rules
     ASTRule

   cell: goga/ast/errors
     ASTRuleError, DocumentRuleError
   ```

2. **Show connections between cells** — which types flow from cell to cell via Imports:
   ```
   goga/ast/nodes ──(DocumentRoot, DocumentNode)──> goga/ast/rules
   goga/ast/errors ──(ASTRuleError)────────────────> goga/ast/rules
   goga/ast/nodes ──(DocumentRoot, DocumentNode)──> goga/ast/errors
   ```

3. **Ask one question** — is the distribution agreed upon? Are there types that should be regrouped?

4. **Wait for feedback** — the user approves or requests changes
   - **Approved** → proceed to Step 5
   - **Not approved** → remember the comments, return to point 1 and propose a corrected distribution accounting for the feedback.

**Readiness criteria:**
- All types are distributed across cells
- Connections between cells are defined (which types are imported)
- No circular dependencies between cells
- The user has approved the distribution

#### Step 5. Designing usages and annotations

**Goal:** For each cell from the distribution (Step 4), determine which practices (usages) and instructions
(annotations) are needed for correct implementation of contracts.

Use the `goga-cookbook` skill for:
- Choosing the Usages connection form (file, inline, or URL)
- Principles of writing usage files in `<cell_path>/.usages/`
- Principles of writing annotations (for header, entity, routine, method, property)

Process cells in order from leaves to root. For each cell:

1. **Determine usages** — what practices the types in this cell need:
   - **Base usages of the project** (from the `goga-codemanifest-base` skill) — include ALL base usages in the `Usages`
     directive of the CODEMANIFEST header. Base practices are mandatory for all cells.
     If a base practice affects the contract form (e.g., requires specific error handling,
     naming convention, pattern) — the contract must comply with it. Reference relevant
     base usages in annotations via `` `usage_name` ``
   - **Usages from other cells** — if types in this cell use a library or pattern
     described in the usages of another cell, import that practice via `Imports.Usages`
   - **Usages of external libraries** — if types in this cell use an external library
     for which there is a usage file in the project (`.goga/usages/`, `.goga/usages/cooks/`), connect it via the `Usages` directive.
     If there is no usage file for the library — record the need to create one (creation is performed in a separate skill)

2. **Determine annotations** — what instructions the AI agent needs during implementation:
   - **Base annotations of the project** (from the `goga-codemanifest-base` skill) — include base annotations in the `Annotations`
     directive of the CODEMANIFEST header. The content of base annotations must be considered when designing the contract:
     if a base annotation sets a constraint or requirement, the contract must comply with it
   - **Global header annotations** — general instructions relating to the entire cell
     (naming conventions, constraints, architectural decisions)
   - **Entity annotations** — description of responsibility scope and signature parameters, general implementation requirements
   - **Routine/method/property annotations** — description of parameters and signature parameters, operation algorithm (if achievable),
     and implementation requirements without technical details
   - Reference usages via backticks (`` `usage_name` ``) to link instructions to practices

3. **Determine cell usages** — which files `<cell_path>/.usages/*.md` will be provided for consumers:
   - Review current md files in `<cell_path>/.usages/`
   - Divide the CODEMANIFEST contract into functional domains based on actions the consumer can perform when using the API
   - For each domain, define a clear file name `<cell_path>/.usages/<domain_name>.md`
   - Describe instructions for interacting with the contract for an external consumer with usage examples
   - Adhere to the self-sufficiency principle — each instruction should be independent of other cells if achievable

4. **Wait for feedback** — the user approves or requests changes
   - **Approved** → proceed to the next cell
   - **Not approved** → remember the comments, propose corrected usages/annotations

The result of this step — for each cell, a CODEMANIFEST is formed with the definition of the set of usages and annotations
that will be used during implementation.

#### Step 6. Cell design

**Goal:** Based on the approved detailed types (Step 3), distribution (Step 4),
and usages/annotations (Step 5), assemble CODEMANIFEST and .usages/ files for each cell.

To check syntactic correctness of CODEMANIFEST, use the `goga-cell` skill.
For the CODEMANIFEST design order (Header → Body → Footer) — use the `goga-cookbook` skill.
For correct naming of types, methods, and properties, as well as `location` values — use the language skill from Step 3 of Phase 2.

Process cells in order from leaves to root (cells without dependencies first). For each cell:

1. **Assemble CODEMANIFEST** — "package" the approved types into DSL format:
   - **Header** — Imports (from Step 4 connections), Usages (from Step 5), Annotations (from Step 5)
   - **Body** — types from Step 3 with their methods, properties, mutations, embeddings
   - **Footer** — Author, CreatedAt, Description

2. **Wait for feedback** — the user approves or requests changes
   - **Approved** → proceed to point 3
   - **Not approved** → remember the user's comments, return to point 1 and propose a corrected CODEMANIFEST
     accounting for the feedback
3. **Propose .usages/ files** for consumers of this cell — other cells, as described by the `goga-cookbook` skill
4. **Wait for feedback** — the user approves or requests changes
   - **Approved** → proceed to the next cell
   - **Not approved** → remember the user's comments, return to point 3 and propose corrected .usages/ files
     accounting for the feedback

If changes in the current cell affect already approved cells — return to the affected cells
and propose necessary adjustments.

#### Step 7. Final approval

When all cells are designed — present a summary:

- Dependency diagram accounting for final changes
- List of all artifacts (CODEMANIFEST + .usages/ files) with paths

If input is from a task file — verify the result against the "Acceptance Criteria" section:
ensure that the designed architecture allows fulfilling each acceptance condition.
If any condition is not covered — point this out and propose an addition.

- **User approves** → proceed to Phase 5
- **User requests changes** → return to Step 6 to the relevant cell

### Phase 5: Architecture Plan Assembly

Based on the approved artifacts from Phase 4, assemble an **architecture plan** — a structured document
describing CODEMANIFEST and `.usages/` files for each cell.
Save the plan to the file `docs/arch/<topic>.md`, where `<topic>` is a short name based on the topic from the user's
description (Phase 1).

#### Plan Structure

1. **Implementation order** — cells are ordered from leaves to root (cells without dependencies first, then dependent ones).
   For each cell, specify the reason for the order (e.g., "has no Imports", "depends on cell X").

2. **Artifacts for each cell** — for each cell in implementation order:
   - **CODEMANIFEST** — complete file contents in DSL format
   - **.usages/ files** — for each file: path, name, complete contents

3. **Dependency map** — ASCII diagram or list of connections between cells via Imports

4. **Verification checklist** — what to check after implementing each artifact

#### Plan Generation Rules

- Each CODEMANIFEST in the plan must be syntactically correct according to the DSL specification
- File names and paths must correspond to the project structure from `schema`
- For modification of existing CODEMANIFESTs — specify a diff: what to add, what to change, what to delete
- If the plan affects existing cells — explicitly specify which cells are modified and which are created anew
- The plan contains **only** CODEMANIFEST and `.usages/` file artifacts. Do not include implementation code in any programming language

Present the plan to the user for confirmation.

### Phase 6: Plan Verification

### Step 1: Verification

Perform verification of the created plan using the `goga-cell` and `goga-cookbook` skills for validation:

1. **Completeness** — every type, method, property from the approved solution is present in the plan
2. **DSL correctness** — all CODEMANIFESTs in the plan are syntactically correct (keys, signatures, document structure)
3. **Inter-cell consistency** — Imports in the plan reference existing cells, types match
4. **Implementation order** — each cell is created after all cells it depends on
5. **No placeholders** — no TBD, TODO, or incomplete descriptions in the plan's CODEMANIFEST files
6. **Usage of Imports.Types** — every imported type (from `Imports.Types`) is used in the document body:
   in signatures, mutations, embeddings, or annotations of the current CODEMANIFEST
7. **Usage of Imports.Usages** — every imported practice (from `Imports.Usages`) is mentioned in at least
   one annotation (global, type, method, or property)
8. **Usage of Usages** — every practice declared in the `Usages` header is mentioned in at least one annotation
   (global, type, method, or property)
9. **Algorithms in annotations** — annotations for routines and methods contain a description of the operation algorithm if achievable
10. **Annotation wording** — annotations do not contain technical implementation details
11. **Resolvability of references in annotations** — every reference in backticks within annotations is resolvable in the context
    of the current CODEMANIFEST: a variable from the signature, a type from Imports or declared in the document, a practice from Usages or Imports
12. **Location restrictions** — every `location` value contains only a file name with extension, without directories
    and without escaping the current level
13. **Absence of cross-imports** — if cell A imports from cell B, then cell B does not import from cell A
14. **Embedding from Imports** — every embedded type (via `->`) is available through `Imports`
15. **Mutations from available types** — base types in mutations (`Object::Target`) are available: imported via `Imports`
    or declared in the current CODEMANIFEST
16. **Entity / Routine correctness** — every type with `methods` and/or `properties` is an Entity; every type without
    `methods` and `properties` is a Routine and does not contain these sections
17. **Base usages from configuration** — if the `goga-codemanifest-base` skill returned base usages, each
    base practice is included in the `Usages` directive of all CODEMANIFESTs and is referenced in at least one annotation
18. **Base annotations from configuration** — if the `goga-codemanifest-base` skill returned base annotations, base
    annotations are included in the `Annotations` directive of all CODEMANIFESTs and are considered when designing contracts
    (contracts comply with the requirements from base annotations)
19. **Language correctness** — type, method, and property names in CODEMANIFEST comply with target language conventions
    (from the language skill). `location` values contain correct file names for the target language

### Step 2: Fix

Fix the found issues in the plan and update the file. Present the final result to the user for confirmation.

---
