# Apply

Materialize an architecture plan into the cells file structure. Reads `docs/arch/<topic>.md` and produces actual `CODEMANIFEST` files and `.usages/` directories on disk.

## Synopsis

```text
/goga:apply <topic>
```

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-apply` (Codex: `$goga-apply`). See [Workflow](index.md).

## Output artifacts

For each cell in the plan:

- `<cell_path>/CODEMANIFEST` — the contract file
- `<cell_path>/.usages/*.md` — practice files for consumers (where required)

The skill does **not** write implementation code — only the contract skeleton.

## Algorithm

### Phase 1. Load DSL specification and principles

| Step | Action |
|---|---|
| 1 | Load DSL specification via `goga-cell` — cell structure, directive purposes, syntactic correctness. |
| 2 | Load DSL application principles via `goga-cookbook` — when to create a cell, Entity vs Routine, granularity, Usages connection form, design order, mutation/embedding criteria, usage-file authoring. |
| 3 | Load language implementation rules via `goga-lang-disp` — naming conventions, file structure, signature rules. |

### Phase 2. Read and parse the plan

| Step | Action |
|---|---|
| 1. Locate the plan file | Use argument as path or `docs/arch/<topic>.md`; if no argument, list `docs/arch/` via `AskUserQuestion`; halt if file missing. |
| 2. Parse the plan structure | Extract implementation order, artifacts per cell, dependency map, verification checklist. |
| 3. Classify cells | Mark each as **new** (directory does not exist) or **modification** (directory exists; read current CODEMANIFEST to compute diff). |

### Phase 3. Validate the plan

Validate **before** creating any files. Halt and report on error.

| Step | Action |
|---|---|
| 1. CODEMANIFEST DSL validation | Verify document structure (Header/Body/Footer), header directives, body declarations, footer fields, syntax (casing, signatures, locations). |
| 2. Cross-cell consistency | Every `Imports.From` references a cell that exists or will be created; types match; implementation order respects dependencies. |
| 3. Location directives | Every `location` is a file at the same level as CODEMANIFEST; extension matches the project language. |
| 4. Error handling | Output error list per cell/violation; recommend returning to `brainstorm`; do not proceed. |

### Phase 4. Create cells

Process cells **strictly in plan order** (leaves → root). For each cell:

| Step | Action |
|---|---|
| 1. Determine mode | New cell → create from scratch; modification → apply diff to existing CODEMANIFEST. |
| 2. Create directory structure | `mkdir -p <cell_path>` and `mkdir -p <cell_path>/.usages` if the plan includes usage files. |
| 3. Write CODEMANIFEST | New: write full content from plan. Modification: apply diff (add/change/remove types, imports, usages, annotations, methods, properties, footer). Use targeted edits. |
| 4. Create `.usages/` files | For each file in the plan: write `<cell_path>/.usages/<usage_name>.md`. For modifications, update existing files. |
| 5. Cell report | Output mode (creation/modification) and list of created/modified files. |

### Phase 5. Validation

| Step | Action |
|---|---|
| 1. Run the linter | `goga lint`. Fix errors and rerun; use `goga-cell` and `goga-cookbook` to diagnose. |
| 2. Run the schema check | `goga schema`. Verify all new cells appear and connections match the dependency map. |
| 3. Checklist verification | All cells created/modified; all CODEMANIFESTs pass linter; all `.usages/` files created. |

### Phase 6. Final report

1. **Cell list** — for each cell: path, mode, files created.
2. **Dependency map** — confirmed inter-cell connections.
3. **Validation status** — linter and schema results.

## Resolving the topic

If `<topic>` is omitted:

1. Scan `docs/arch/`.
2. **Single file** — use automatically.
3. **Multiple files** — ask the user via `AskUserQuestion`.
4. **Empty or missing** — halt and report.

## Pre-flight check

```bash
goga --help
```

If `goga` is unavailable, the skill halts.

## Inputs and outputs

| | |
|---|---|
| **Input** | `docs/arch/<topic>.md` |
| **Output** | Cells on disk: `CODEMANIFEST` files and `.usages/` directories |

## What happens next

- Run [`design`](design.md) to produce a detailed design document based on the new CODEMANIFEST files.
