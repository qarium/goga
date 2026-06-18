# Brainstorm

Design the cells architecture for a task through a structured interactive brainstorm. Produces an architecture plan that `apply` later materializes into the cell file structure.

## Synopsis

```text
/goga:brainstorm <topic>
```

Examples in this document use Claude Code style (`/goga:<command>`). For other agents, invoke the skill directly: `goga-brainstorm`.

## Output artifact

`docs/arch/<topic>.md` — an architecture plan with four mandatory sections:

1. Implementation order (leaves → root, with rationale per cell)
2. Artifacts per cell (CODEMANIFEST contents + `.usages/` files)
3. Dependency map (ASCII diagram or list of Imports connections)
4. Verification checklist

The plan contains **only** CODEMANIFEST and `.usages/` artifacts — no implementation code.

## Algorithm

### Phase 1. Input collection

Accept the description (brief, detailed, or a path to `docs/tasks/<topic>.md`). When a task file is supplied, its sections feed the brainstorm:

- Current state → context for primary analysis
- Description and boundaries → design basis
- Stack and external dependencies → technology choices
- Acceptance criteria → final approval condition
- Risks and constraints → accounted for in analysis
- Scope → one subtask brainstormed at a time

### Phase 2. Loading DSL specification and principles

| Step | Action |
|---|---|
| 1 | Load DSL specification via `goga-cell`. |
| 2 | Load DSL application principles via `goga-cookbook`. |
| 3 | Load language implementation rules via `goga-lang-disp` — naming conventions, facade structure, signature rules. |

### Phase 3. Project context exploration

| Step | Action |
|---|---|
| 1 | Run `goga schema` to obtain the cell hierarchy. |
| 2 | Load base annotations and usages via `goga-codemanifest-base`. |
| 3 | Read relevant CODEMANIFESTs (match user description to schema; use `--depends-on <cell_path>` to find dependents). |
| 4 | Read relevant usages (`.goga/usages/`, `.goga/usages/cooks/`). |

### Phase 4. Brainstorm cycle

**Principle:** design types and interactions first, then group into cells. This exposes all connections before cell boundaries hide them.

| Step | Action |
|---|---|
| 1. Primary analysis | Identify key concepts, dark zones, connection to existing architecture, risks. Scope check — propose splitting if multiple subsystems are involved. |
| 2. Type map | Build a "table of contents" of types: names, character (Entity/Routine), brief purpose, connections. Iterate with the user until approved. |
| 3. Type detailing | For each type: methods, properties, signatures, interactions. Check consistency with already-approved types. |
| 4. Distributing types across cells | Group types by cohesion; show cell-to-cell connections via Imports; verify no circular dependencies. |
| 5. Designing usages and annotations | For each cell (leaves → root): determine usages (base + cross-cell + external libraries), annotations (global/entity/method/property), cell usages (`.usages/` files for consumers). |
| 6. Cell design | Assemble CODEMANIFEST for each cell (Header → Body → Footer); propose `.usages/` files; iterate until approved. |
| 7. Final approval | Present dependency diagram and full artifact list; if input came from a task file, verify acceptance criteria coverage. |

### Phase 5. Architecture plan assembly

Save the plan to `docs/arch/<topic>.md` with the four mandatory sections. Each CODEMANIFEST must be syntactically correct; modifications described as diffs; file names must match the project structure.

### Phase 6. Plan verification

A 19-point checklist verifying completeness, DSL correctness, inter-cell consistency, implementation order, no placeholders, usage of `Imports.Types` and `Imports.Usages`, usage of `Usages`, annotation algorithms, reference resolvability, location restrictions, no cross-imports, embedding/mutation correctness, Entity/Routine classification, base usages/annotations inclusion, and language-correct naming.

## Dialogue rules

- Do not read implementation source code — design at the level of CODEMANIFEST, schema, and practices.
- Treat any description as an architecture task — follow the algorithm completely.
- Work through hypotheses — concrete proposals, not open-ended questions.
- One question per message, with 2–4 concrete options.
- Structure every response.
- Split large domains — propose separate brainstorms for independent subsystems.
- Use ASCII diagrams for entity relationships, data flows, and cell boundaries.

## Pre-flight check

The skill verifies that `goga` is available:

```bash
goga --help
```

If missing, the skill stops and reports the issue.

## Inputs and outputs

| | |
|---|---|
| **Input** | `docs/tasks/<topic>.md` (approved task) |
| **Output** | `docs/arch/<topic>.md` — cells architecture plan |

## What happens next

- Run [`review`](review.md) on the architecture artifact (`review(arch)`).
- On approval, run [`apply`](apply.md) to materialize the plan into cell files.
