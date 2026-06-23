---
name: goga-cells-by-brainstorm
description: Creation and modification of cells by architecture plan
---
# Create Cells

## Purpose

Creates new cells and modifies existing cells based on the architecture plan defined in `docs/arch/<topic>.md`. Materializes the plan into the cell file structure:
CODEMANIFEST, `.usages/`.

---

## Phases

### Phase 1: Load DSL specification and DSL application principles

#### Step 1: Load the DSL specification

To understand cell definitions and CODEMANIFEST file contents, invoke the `goga-cell` skill via the **Skill tool**.
Use the `goga-cell` skill to:
 - Understand cell structure — cell composition (CODEMANIFEST, `.usages/`), document organization (header, body, footer)
 - Understand CODEMANIFEST directive purposes — responsibilities of `Imports`, `Usages`, `Annotations`, types, mutations, embeddings
 - Verify syntactic correctness — key casing, signature rules, `location` constraints, declaration structure

#### Step 2: Load DSL application principles

To understand principles for working with cells and CODEMANIFEST files, invoke the `goga-cookbook` skill via the **Skill tool**.
Use the `goga-cookbook` skill to:
 - Determine whether to create a cell — when to extract a standalone cell versus extending an existing one
 - Choose between Entity and Routine — when a type requires `methods`/`properties` versus a single operation
 - Determine granularity — appropriate cell size, indicators of over- or under-splitting
 - Select the Usages connection form — file, inline, or URL, and when each applies
 - Establish the design order — design cells from leaves to root; cells without dependencies first
 - Decide when to use mutations (`Object::Target`) and embeddings (`->Entity: {}`) versus Imports alone
 - Write usage files in `<cell_path>/.usages/` — structure, content, and quality guidelines

#### Step 3: Load language implementation rules

Invoke the `goga-lang-disp` skill via the **Skill tool** to obtain the target language skill.
The language skill defines implementation conventions: cell structure, facade, signature rules, and **naming**.
Examples in other skills may use naming conventions from one language (e.g., snake_case), while the target language
requires different conventions (e.g., PascalCase). The language skill provides authoritative rules for the target language.

Apply the loaded DSL specifications, DSL application principles, and language rules actively when creating and modifying cells.

---

### Phase 2: Read and parse the plan

#### Step 1. Locate the plan file

- If the argument contains a file path — use it directly
- If the argument contains only `<topic>` — search for the file `docs/arch/<topic>.md`
- If no argument is provided — discover all files in `docs/arch/` and present the list via **AskUserQuestion**
- If the file is not found — halt and report the error to the user

#### Step 2. Parse the plan structure

Read the plan file and extract:

1. **Implementation order** — ordered list of cells from leaves to root, with rationale for the ordering
2. **Artifacts per cell** — CODEMANIFEST content, `.usages/` files, `location` file lists
3. **Dependency map** — inter-cell connections expressed through Imports
4. **Verification checklist** — items to verify after implementation

#### Step 3. Classify cells

For each cell in the plan, determine the operation mode:

- **New** — the cell directory does not exist on disk
- **Modification** — the cell directory exists (read the current CODEMANIFEST to compute the subsequent diff)

---

### Phase 3: Validate the plan

The agent must validate the plan for correctness **before** creating any files. If errors are detected, the agent must halt and report them to the user.

#### Step 1. CODEMANIFEST DSL validation

For each CODEMANIFEST in the plan, the agent must verify compliance with the DSL specification using the `goga-cell` and `goga-cookbook` skills:

- **Document structure** — Header / Body / Footer delimited by `---`
- **Header** — valid `Imports` (Types + From), `Usages` (key: value), `Annotations` (block text after `|`)
- **Body** — valid Entity and Routine signatures, `location` directive, `methods`, `properties`, `annotations`
- **Footer** — `Author`, `CreatedAt`, `Description` fields
- **Syntax** — key casing, signature format, `location` constraints

#### Step 2. Cross-cell consistency

- Every `Imports` → `From: <path>` must reference a cell that exists or will be created within the plan
- Types listed in `Imports` → `Types` must be defined in the target cell
- The implementation order must be correct: each cell is created after all cells it depends on via Imports

#### Step 3. Location directives

- Every `location` must point to a file **at the same level** as the CODEMANIFEST (no subdirectories)
- The file extension must correspond to the project language (as determined by the language skill loaded in Phase 1, Step 3)

#### Step 4. Error handling

If errors are detected:

- Output an error list specifying the cell and the specific violation
- Recommend that the user return to `goga-brainstorm` to fix the plan
- **Do not proceed** until the plan is corrected

---

### Phase 4: Create cells

Process cells **strictly in the order** specified in the plan, from leaves to root.

For each cell:

#### Step 1. Determine the mode

- **New cell** — create the directory and all files from scratch
- **Modification** — read the current CODEMANIFEST and apply the planned changes

#### Step 2. Create the directory structure

```
# For a new cell:
mkdir -p <cell_path>

# If the plan includes .usages/ files:
mkdir -p <cell_path>/.usages
```

For modifications, ensure that directories already exist.

#### Step 3. Write the CODEMANIFEST

**New cell:** write the full CODEMANIFEST content from the plan to `<cell_path>/CODEMANIFEST`.

**Modification:** apply the diff from the plan to the current CODEMANIFEST. The diff may include:
- Add, change, or remove types (Entity/Routine)
- Add, change, or remove Imports
- Add, change, or remove Usages
- Add, change, or remove Annotations
- Add, change, or remove methods/properties on an Entity
- Update Footer fields

Use the Edit tool for targeted changes.

#### Step 4. Create .usages/ files

For each `.usages/` file specified in the plan:

- Create the file `<cell_path>/.usages/<usage_name>.md` with the full content from the plan
- For modifications, if the file already exists, update its content

#### Step 5. Cell report

After processing each cell, output:

- Mode (creation or modification)
- List of created or modified files

---

### Phase 5: Validation

The agent must run tooling and verify results.

#### Step 1. Run the linter

```bash
goga lint
```

If the linter reports errors, the agent must fix them and rerun. Use the `goga-cell` and `goga-cookbook` DSL specification skills to diagnose the error causes.

#### Step 2. Run the schema check

```bash
goga schema
```

The agent must verify that all new cells appear in the hierarchy and that their connections match the dependency map.

#### Step 3. Checklist verification

The agent must verify the checklist items from the plan:

- All cells from the plan have been created or modified
- All CODEMANIFEST files pass the linter
- All `.usages/` files have been created

---

### Phase 6: Final report

Output the final report:

1. **Cell list** — for each cell: path, mode (creation/modification), files created
2. **Dependency map** — confirmed diagram of inter-cell connections
3. **Validation status** — linter and schema results

---
