# Brainstorm

Design the cells architecture for a task through a structured, interactive pipeline. The skill is a **pipeline orchestrator**: it coordinates sub-skills in strict order and performs no design work itself — each stage is delegated to the sub-skill responsible for it. The result is an architecture plan that `apply` later materializes into the cell file structure.

## Synopsis

```text
/goga:brainstorm <topic>
```

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-brainstorm` (Codex: `$goga-brainstorm`). See [Workflow](index.md).

## Output artifact

`.goga/history/<year>/<topic>/arch.md` — an architecture plan with four mandatory sections:

1. Implementation order (leaves → root, with rationale per cell)
2. Artifacts per cell (CODEMANIFEST contents + `.usages/` files)
3. Dependency map (ASCII diagram or list of Imports connections)
4. Verification checklist

The plan contains **only** CODEMANIFEST and `.usages/` artifacts — no implementation code.

## Pre-flight check

The skill verifies that `goga` is available:

```bash
goga --help
```

If missing, the skill stops and reports the issue.

## Context initialization

Before the pipeline starts, the orchestrator loads the skills it will derive every design decision from:

| Skill                    | Provides                                                                                    |
|--------------------------|---------------------------------------------------------------------------------------------|
| `goga-cell`              | DSL specification — cell and CODEMANIFEST structure, directives, and syntax.                |
| `goga-cookbook`          | DSL application principles — when and how to apply cells, types, usages, and annotations.   |
| `goga-lang-disp`         | Language implementation rules — naming, signatures, and `location` for the target language. |
| `goga-codemanifest-base` | The project's base usages and annotations from `.goga/config.yml`.                          |

## Design principle

**Design types and their interactions first, then group them into cells.** This exposes every connection between types before cell boundaries hide them. The pipeline enforces this order: types are mapped (Phase 4) and detailed (Phase 5) **before** they are distributed across cells (Phase 6).

## Pipeline

The orchestrator runs ten phases strictly sequentially. Each phase invokes one sub-skill via the **Skill tool**, produces a named report, and passes it to the next phase. Phases marked **WAIT** stop for user approval; every phase defines its own **STOP** conditions.

| #  | Phase             | Sub-skill                           | Report                       | Gate |
|----|-------------------|-------------------------------------|------------------------------|------|
| 1  | Intake            | `goga-brainstorm-intake`            | `[INTAKE_REPORT]`            | —    |
| 2  | Project Context   | `goga-brainstorm-context`           | `[PROJECT_CONTEXT_REPORT]`   | —    |
| 3  | Primary Analysis  | `goga-brainstorm-primary-analysis`  | `[PRIMARY_ANALYSIS_REPORT]`  | WAIT |
| 4  | Type Map          | `goga-brainstorm-type-map`          | `[TYPE_MAP_REPORT]`          | WAIT |
| 5  | Type Detailing    | `goga-brainstorm-type-detail`       | `[TYPE_DETAIL_REPORT]`       | WAIT |
| 6  | Cell Distribution | `goga-brainstorm-cell-distribution` | `[CELL_DISTRIBUTION_REPORT]` | WAIT |
| 7  | Contracts         | `goga-brainstorm-contracts`         | `[CONTRACTS_REPORT]`         | WAIT |
| 8  | Cell Assembly     | `goga-brainstorm-cell-assembly`     | `[CELL_ASSEMBLY_REPORT]`     | WAIT |
| 9  | Plan Assembly     | `goga-brainstorm-plan-assembly`     | `[ARCHITECTURE_PLAN]`        | WAIT |
| 10 | Plan Verification | `goga-brainstorm-plan-verification` | `[VERIFICATION_REPORT]`      | WAIT |

Context flows between phases through these named reports — the orchestrator never carries state of its own.

## Algorithm

### Phase 1. Intake

Accept the description (brief, detailed, or a path to `.goga/history/<year>/<topic>/task.md`). When a task file is supplied, its sections feed the pipeline:

- Current state → context for primary analysis
- Description and boundaries → design basis
- Stack and external dependencies → technology choices
- Acceptance criteria → final approval condition
- Risks and constraints → accounted for in analysis
- Scope → one subtask brainstormed at a time

**STOP if:** description is empty; multiple independent subsystems left unresolved.

### Phase 2. Project Context

Build a picture of the existing architecture: run `goga schema` for the cell hierarchy, read the relevant CODEMANIFESTs (match the description to the schema; use `--depends-on <cell_path>` to find dependents), and read the relevant usages (`.goga/usages/`, `.goga/usages/cooks/`).

**STOP if:** `goga schema` unavailable; an unresolvable cell path.

### Phase 3. Primary Analysis

Identify the key concepts, dark zones, connection to the existing architecture, and risks. Perform a scope check — propose splitting if several subsystems are involved.

**WAIT:** present the analysis and obtain approval. **STOP if:** approval denied after iteration; scope-split left unresolved.

### Phase 4. Type Map

Build a "table of contents" of types as a Type Table: name, character (Entity/Routine), brief description, and connected types. Iterate with the user until approved.

**WAIT:** present the type map and obtain approval. **STOP if:** map incomplete; approval denied after iteration.

### Phase 5. Type Detailing

For each type: signature, properties, methods, and mutations/embeddings. Check interactions for consistency against already-approved types.

**WAIT:** present per-type detailing and obtain approval per type. **STOP if:** interactions inconsistent; approval denied after iteration.

### Phase 6. Cell Distribution

Group the detailed types by cohesion into cells (leaves → root). Show cell-to-cell connections via `Imports` and verify there are no circular dependencies.

**WAIT:** present the distribution and obtain approval. **STOP if:** circular dependency between cells; approval denied after iteration.

### Phase 7. Contracts (Usages & Annotations)

For each cell (leaves → root), determine usages, annotations at every level, and consumer usage files. This phase runs a nested sub-pipeline, gated per cell:

1. **Usages (header)** — `goga-brainstorm-contracts-usages-inline` connects base / cross-cell / external usages and returns the set of Usages keys.
2. **Annotations** — `goga-brainstorm-contracts-annotations` produces global / type-level / member-level annotations.
3. **Cell usage files** — `goga-brainstorm-contracts-usages-file` produces `<cell_path>/.usages/<domain>.md` files in full.

After each cell, the phase halts and waits for the user's verdict before touching the next cell.

**WAIT:** present per-cell usages, annotations, and usage files; obtain approval per cell. **STOP if:** the canonical usage pattern would be violated; approval denied after iteration.

### Phase 8. Cell Assembly & Final Approval

Assemble the CODEMANIFEST for each cell (Header → Body → Footer) and propose the `.usages/` files. After per-cell approval, present the final summary: dependency diagram, full artifact list, and (when input came from a task file) acceptance-criteria coverage.

**WAIT:** obtain per-cell approval, then final approval. **STOP if:** DSL syntax invalid; approval denied after iteration.

### Phase 9. Plan Assembly

Write the architecture plan to `.goga/history/<year>/<topic>/arch.md` with the four mandatory sections. Each CODEMANIFEST must be syntactically correct; modifications are described as diffs; file names must match the project structure.

**WAIT:** present the plan and obtain confirmation. **STOP if:** plan incomplete.

### Phase 10. Plan Verification

Run a checklist over the plan: completeness, DSL correctness, inter-cell consistency, implementation order, no placeholders, use of `Imports.Types` and `Imports.Usages`, use of `Usages`, annotation algorithms, reference resolvability, `location` restrictions, no cross-imports, embedding/mutation correctness, Entity/Routine classification, base usages/annotations inclusion, and language-correct naming.

**WAIT:** present the final (fixed) plan and verification report; obtain final confirmation. **STOP if:** unresolved DSL errors; any verification gate failed.

## Dialogue rules

Applies to every interactive phase:

- Do not read implementation source code — design at the level of CODEMANIFEST, schema, and practices.
- Treat any description as an architecture task — follow the pipeline completely.
- Work through hypotheses — concrete proposals, not open-ended questions.
- One question per message, with 2–4 concrete options.
- Structure every response.
- Split large domains — propose separate brainstorms for independent subsystems.
- Use ASCII diagrams for entity relationships, data flows, and cell boundaries.

## Inputs and outputs

|            |                                                  |
|------------|--------------------------------------------------|
| **Input**  | `.goga/history/<year>/<topic>/task.md` (approved task)          |
| **Output** | `.goga/history/<year>/<topic>/arch.md` — cells architecture plan |

## What happens next

- Run [`review`](review.md) on the architecture artifact (`review(arch)`).
- On approval, run [`apply`](apply.md) to materialize the plan into cell files.
