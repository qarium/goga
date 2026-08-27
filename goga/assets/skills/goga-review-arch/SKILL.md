---
name: goga-review-arch
description: Review an architecture plan for semantic correctness
---
# Architecture Review

## Objective

Validate the architecture plan (`.goga/history/<year>/<topic>/arch.md`) for **semantic correctness** — assess model cohesion, domain boundary
soundness, and requirement sufficiency for implementation.
The agent **analyzes** the architecture plan, **reports** findings, and **applies fixes** when issues are detected
(subject to user approval).

---

## Core Principle

**Architecture is a cohesive system, not a collection of isolated contracts.** The agent validates the interaction across
all types, domains, and requirements as a unified whole — not each CODEMANIFEST in isolation.

---

## Input

- **Required**: architecture plan at `.goga/history/<year>/<topic>/arch.md`
- **Optional**: task file at `.goga/history/<year>/<topic>/task.md` — when present, used to verify requirements coverage. The year may differ from the architecture plan's year; locate the task file as `.goga/history/*/<topic>/task.md` with a 4-digit year segment.

---

## Phases

### Phase 1: Context Loading

1. Read the architecture plan from `.goga/history/<year>/<topic>/arch.md`
2. Load the DSL specification and DSL application principles:
    - Invoke `goga-cell` via **Skill tool** — to understand DSL rules
      (signature syntax, Import/Usage/Annotation rules, types, mutations, embeddings, constraints)
    - Invoke `goga-cookbook` via **Skill tool** — to understand cell and CODEMANIFEST design principles
      (Entity vs Routine selection criteria, when to apply mutations and embeddings, usage file authoring guidelines,
      cell granularity)
3. Load language-specific implementation rules:
    - Invoke `goga-lang-disp` via **Skill tool** — to obtain the target language skill.
      The language skill defines implementation conventions: cell structure, facade pattern, signature rules, **naming**.
      Examples in other skills may follow naming conventions of one language (e.g., snake_case), whereas the target
      language requires another (e.g., PascalCase) — the language skill is the authoritative source for the target language.
4. Invoke `goga-codemanifest-base` via **Skill tool** — to obtain the project's baseline usages and annotations
5. Retrieve the current project schema:
    - Run `goga schema` to obtain the existing cell hierarchy
    - Classify plan cells: newly created vs. modified
6. Read the existing CODEMANIFESTs of cells the plan marks for modification
7. Read the existing `.usages/` files of cells marked for modification
8. If the task file `.goga/history/*/<topic>/task.md` exists (4-digit year; the year may differ from the architecture plan's year) — read it for subsequent requirements coverage verification

---

### Phase 2: Plan Structure Validation

Verify the architecture plan contains **all mandatory sections**:

1. **Implementation order** — cells sequenced with rationale for ordering
2. **Artifacts per cell** — CODEMANIFEST and `.usages/` files
3. **Dependency map** — ASCII diagram or enumerated cell-to-cell connections
4. **Verification checklist** — post-implementation validation criteria

If any section is missing — log as a **Critical** finding.
If a section is present but empty or contains placeholders (TBD, TODO) — log as **High**.

#### No Implementation Code

The architecture plan must contain **only** CODEMANIFEST and `.usages/` file artifacts.
If implementation code blocks in any programming language are found — log as **Critical**.

---

### Phase 3: Flat Model Reconstruction

**Goal:** Construct a cross-cell type graph from all CODEMANIFESTs in the plan — disregarding cell boundaries to reveal the
full picture.

From each CODEMANIFEST in the plan, extract:

- All declared types (Entity and Routine) with their signatures
- All inter-type connections: parameter acceptance, return types, mutations, embeddings
- All Import relationships (source of each referenced type)

Construct a unified type graph:

- **Vertices** — all types across all plan CODEMANIFESTs + all imported types from existing cells
- **Edges** — inter-type interactions (parameters, returns, mutations, embeddings, calls via Imports)

Render the graph to the user as an ASCII diagram.

---

### Phase 4: Flat Model Cohesion

Validate the type graph (Phase 3) for integrity.

#### Step 1. Type Graph Completeness

- Every type referenced in signatures (parameters, returns), mutations (`Object::Target`), or embeddings (
  `->Entity: {}`) must exist as a declared type in the model
- No implicit types — types that are used but nowhere declared (neither in plan CODEMANIFESTs nor in existing cells
  via Imports)

If a type is used but undeclared — log as **Critical** (model gap blocks implementation).

#### Step 2. Graph Connectivity

- All types must be reachable from entry points (EntryPoint types — those that initiate data flows)
- No "dangling" types — types that nothing uses and that use nothing (entry points excepted)
- A type that no other type references and that is not itself an entry point is suspicious

Unreachable types — log as **High** (possibly extraneous or missing a connection).
Dangling types — log as **Medium** (may serve future expansion, but should be explicitly documented).

#### Step 3. Connection Consistency

- Where type A passes type X to type B — type X must have a consistent form (same source, same signature)
- Input/output types must align along interaction chains: output of type N must match input of type N+1
- No "magical" type transformations — every type transition must be explained by a contract (signature, mutation,
  embedding)

Inconsistencies — log as **Critical**.

---

### Phase 5: Cell Cohesion

**Goal:** Verify that cell boundaries are well-defined — high internal cohesion, minimal cross-cell coupling.

#### Step 1. Internal Cell Cohesion

For each cell in the plan:

- Types within a single cell must interact with each other (exchange data via parameters, returns, mutations)
- A type in a cell with no interaction with any other type in that cell signals a potential composition error

If a type has no connections to other types in its cell — log as **Medium** (may belong in a different cell).

#### Step 2. Boundary Soundness

- Each cell must have a single area of responsibility — describable in one phrase without "and" (see `goga-cookbook`)

If a cell requires "and" to describe — log as **High** (consider splitting).
If closely coupled types are placed in separate cells without justification — log as **Medium**.

#### Step 3. Dependency Directionality

- Dependencies must flow from leaves to root: cells without Imports are designed first, dependent cells follow
- No cycles between cells: if cell A imports from cell B, cell B must not import from cell A
- Implementation order in the plan must match the dependency direction

Cycles — log as **Critical**.
Implementation order mismatch — log as **Critical** (implementation will be blocked).

#### Step 4. Minimal Cross-Cell Coupling

- A cell must not import more types from another cell than necessary
- If cell A imports a significant portion of cell B's types — this indicates incorrect decomposition (cell B is too
  granular or boundaries are misdrawn)

If a cell imports the majority of another cell's types — log as **High** (re-examine boundaries).

#### Step 5. Usages Connections Between Cells

Use `goga-cookbook` as the authoritative source for usages validation rules.
Verify that `.usages/` files and their CODEMANIFEST connections conform to `goga-cookbook` principles.

Violations — log as **High**.

#### Step 6. Usages Isolation

**Principle:** Every `.usages/` file must be self-contained — consumers must understand the pattern without consulting
other practices. Cross-references to other practices create implicit dependencies and violate isolation
(see `goga-cookbook`).

For each `.usages/` file in the plan, verify:

- The file contains no references to other practices — no names of other usage files, no backticks referencing
  practices from other `.usages/`
- All necessary context is self-contained — consumers must not need to locate additional practices

Cross-reference to another practice — log as **High** (isolation violation).
Non-self-contained usage file — log as **High**.

---

### Phase 6: CODEMANIFEST Requirements Sufficiency

**Goal:** Verify that CODEMANIFESTs contain sufficient information to support implementation.

#### Step 1. Contract Precision

- Signatures must be unambiguous — a method/property signature must clearly convey its behavior, input types, and return
  types
- No methods/properties open to dual interpretation
- Mutations and embeddings must be justified (not used simply "because available") — see criteria in `goga-cookbook`
- Entity vs Routine classification must be justified for each type — see criteria in `goga-cookbook`
- Type, method, and property names must conform to target language conventions (from `goga-lang-disp`)

Ambiguous signature — log as **High**.
Unjustified mutation/embedding — log as **Medium**.
Incorrect Entity/Routine classification — log as **High**.
Non-conformant naming — log as **High**.

#### Step 2. Usages Quality

For each CODEMANIFEST of the plan:

- The header `Usages:` directive must include the project's base usages retrieved via `goga-codemanifest-base`
  (`goga config codemanifest.usages`) — these practices are mandatory for every CODEMANIFEST in the project

Missing base usage in `Usages:` — log as **High**.

#### Step 3. Annotation Quality

For each annotation in every CODEMANIFEST of the plan:

- The global `Annotations:` directive (document header) must contain the project's base annotations retrieved via skill `goga-codemanifest-base`, transferred **as-is (verbatim)** — without rephrasing, summarizing, or modifying the original text
- Annotations must not contain technical implementation details
- Annotations must contain sufficient information for implementation — implementers must not need to guess behavior
- For non-trivial logic, describe an algorithm or execution flow (step-by-step) where achievable
- Document constraints and edge cases: empty input, None/null, errors, boundary values
- No placeholders (TBD, TODO) — annotations must be complete

Missing base annotation in global `Annotations:` — log as **High**.
Base annotation rephrased or modified (not transferred as-is) — log as **High**.
Insufficient annotation — log as **Critical**.
Non-conformant annotation format — log as **High**.
Missing step-by-step logic description — log as **High**.
Missing edge cases — log as **Medium**.

#### Step 4. Task Requirements Coverage

If the task file `.goga/history/<year>/<topic>/task.md` exists:

- Each requirement from the "Description" section must map to type(s) in the plan that fulfill it
- Each acceptance criterion must have a contractual basis in the plan — the plan must enable fulfilling the criterion
- Each risk from the task must be accounted for (via types, annotations, or architectural decisions)
- Each subtask from the "Scope" section must be covered by the plan (if the task is decomposed)

Uncovered requirement — log as **Critical**.
Unfulfilled acceptance criterion — log as **High**.
Unaccounted risk — log as **Medium**.

---

### Phase 7: Impact on Existing Architecture

For cells marked as modifiable (already present in the project schema):

#### Step 1. Modification Correctness

- The plan must explicitly distinguish modified cells from newly created ones
- For modified cells, the plan must provide a diff: additions, changes, and deletions
- Modifications must not break existing contracts referenced by other cells

Modification not described as a diff — log as **High**.
Modification breaks existing contracts — log as **Critical**.

#### Step 2. Impact on Dependent Cells

- Determine whether changes affect cells not mentioned in the plan but dependent on modified cells
- Run `--depends-on <cell_path>` to locate dependent cells

Unacknowledged affected cells — log as **High**.

---

### Phase 8: Report and Finding Resolution (Interactive)

Aggregate all findings from Phases 2–7 before presenting. Sort by severity: Critical → High → Medium.

Present findings **one at a time**. For each finding:

#### Step 1. Present the Finding

Display one finding with:

- **Severity** (Critical / High / Medium)
- **Direction** (Flat Model / Cells / Requirements / Existing Architecture)
- **Location** — precise reference to the type, cell, plan section, or CODEMANIFEST
- **Issue** — clear problem description
- **Suggested fix** — specific change required, not vague guidance

#### Step 2. Request User Decision

Use AskUserQuestion with these options:

1. **Apply suggested fix** — apply the fix to the architecture plan immediately
2. **Propose alternative** — user provides a different fix approach
3. **Skip** — user defers the finding

#### Step 3. Apply Decision

- **Apply suggested fix**: update the architecture plan, then re-verify that the fix introduces no
  new issues (re-run relevant checks). Report the re-verification result briefly.
- **Skip**: mark the finding as "skipped" and proceed.
- **Propose alternative**: discuss the alternative with the user, agree on a fix, apply it,
  re-verify.

#### Step 4. Proceed to Next Finding

Repeat from Step 1 for the next finding. Display a brief counter: "Finding 3 of 12".

After all findings are processed, present the summary:

- **Fixed**: N findings (grouped by severity and direction)
- **Skipped**: N findings (grouped by severity and direction)
- **Architecture plan status**: updated / unchanged

---

## Output

- Finding summary: fixed/skipped counts by severity and direction
- Updated architecture plan file (if fixes were applied)
- Verification verdict: passed / failed

---

## Final Self-Check

Before completion, verify:

1. Was the DSL specification loaded via `goga-cell` and `goga-cookbook`?
2. Was the current project schema loaded?
3. Was plan structure validated (all 4 mandatory sections, no implementation code)?
4. Was the flat model reconstructed (unified type graph)?
5. Was flat model cohesion validated (completeness, reachability, consistency)?
6. Was cell cohesion validated (internal cohesion, boundaries, directionality, minimal coupling, usages connections)?
7. Was usages isolation validated (no cross-references to other practices, self-contained files)?
8. Was requirements sufficiency validated (contract precision, usages quality, annotation quality)?
9. If a task file exists — was task requirements coverage verified?
10. Was consistency with existing architecture validated (modifications, dependent cells)?
11. Was each finding presented individually with a fix decision?
12. Were approved fixes applied and re-verified?
13. Was a fixed/skipped findings summary provided?
14. Were language rules loaded and applied via `goga-lang-disp`?

If any answer is "no" — complete the missing verification before returning.

---
