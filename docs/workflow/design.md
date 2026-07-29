# Design

Produce a detailed design document based on CODEMANIFEST changes introduced by `apply`. Captures algorithms, data flows, and interaction patterns at the contract level — without prescribing implementation order.

## Synopsis

```text
/goga:design <function-name>
```

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-design` (Codex: `$goga-design`). See [Workflow](index.md).

## Output artifact

`docs/design/<function-name>.md` — a design document with these sections:

- Contract changes (added/removed/modified entities)
- Applied CODEMANIFEST fixes
- Entity interactions and data flows (diagrams)
- Code Stack Trace (verified logical chains per entry point)
- Cross-cutting concerns (error handling, validation, logging, caching, concurrency)
- Usages analysis (per practice: what/where/why/how)
- `.usages/` updates (per cell)
- Test scenarios (6-element traces: name, setup, input, trace, assertions, sufficiency)
- Additional instructions

The document does **not** contain implementation code and does **not** produce an execution plan.

## Algorithm

### Phase 1. DSL loading

| Step | Action |
|---|---|
| 1 | Load DSL specification via `goga-cell`. |
| 2 | Load DSL application principles via `goga-cookbook`. |

### Phase 2. Change collection

| Step | Action |
|---|---|
| 1. Git diff CODEMANIFEST | Diff all CODEMANIFEST files between current and base branch. Identify added/removed/modified entities, usages, imports, annotations, re-exports. |
| 2. Schema — dependency map | Run `goga schema --depends-on <cell_path>` for each changed path to locate affected cells. |

### Phase 3. Contract validation

**Goal:** produce a clean CODEMANIFEST before deep tracing begins.

| Step | Action |
|---|---|
| 1. Resolve Usages references | Always read root usages (referenced by global annotations) and usages of changed entities; skip unreferenced ones. Read files from `.goga/usages/` and `{from_path}/.usages/{name}.md` for imported usages. |
| 2. Gap analysis | Validate DSL rules (signatures, mutations, embeddings, location, casing) with `goga-cell`. Validate design decisions (Entity vs Routine, Usages form, granularity) with `goga-cookbook`. Check for missing entities, invalid locations, missing re-exports, signature/behavior mismatches, existing reusable code, test coverage gaps. |
| 3. Contract consistency audit | Four dimensions: interface↔type, type↔mutation, interface↔interface, annotations↔entity. Each inconsistency is recorded as a CODEMANIFEST defect with location and remediation. |
| 4. User approval of edits | Present defects grouped by file via `AskUserQuestion`. Offer `Apply proposed fix` or `Propose alternative`. Raise questions about ambiguous aspects. |
| 5. Apply edits and validate | For each approved change: edit CODEMANIFEST, validate (`goga-cell`, `goga-cookbook`), re-run `goga lint`, verify no new inconsistencies, assess usages updates. |

### Phase 4. Tracing and algorithmization

**Core of the design document.** Starting from the clean CODEMANIFEST produced in Phase 3, perform detailed elaboration. This phase is a **self-correcting loop** — any step may surface a defect that Phase 3 missed.

| Step | Action |
|---|---|
| 1. Code Stack Trace | For each entry point (method, function, constructor): trace the full chain — entry, input, transformations, external calls, output. Establish checkpoints at each step (type continuity, logical correctness, missing steps, library conformance). Contract interaction checkpoints: type flow, mutation compatibility, interface alignment. Defect → propose fix → on approval, edit CODEMANIFEST and re-trace. |
| 2. Analysis | Identify new entities and interactions; document implementation details unspecified by DSL; map cross-cutting concerns; surface edge cases. Treat imported usages as traceable cross-cell links, not contractual obligations. |
| 3. Usages analysis | For each Usages entry: what it provides, where used, why chosen, how exactly (specific APIs and patterns). For imported usages, read the file at `{from_path}/.usages/{name}.md` and document the dependency. |
| 4. Cross-cutting concerns | Specify error handling strategy, validation locations/rules, logging (level, data), caching strategy, concurrency requirements. |
| 5. Test scenarios | Generate 6-element traces for each test: name, setup, input, trace, assertions, sufficiency. Categories: positive, negative, edge cases. |
| 6. Usages and `.usages/` consistency | For each affected cell with `.usages/`: verify described APIs match CODEMANIFEST, identify outdated descriptions. Decision rules: changes within existing domain → supplement; new functional domain → create; outdated → update in place. Do **not** add `Usages` references pointing to own `.usages/` files. |

### Phase 5. Persist the design document

| Step | Action |
|---|---|
| 1. Write from template | Use the design-doc template. |
| 2. Save | Path: `docs/design/<function-name>.md`. Create directory if missing; overwrite if exists. |

## Resolving the function name

If `<function-name>` is omitted:

1. Scan `docs/design/`.
2. **Single file** — use automatically.
3. **Multiple files** — ask the user.
4. **Empty or missing** — halt and ask the user to run `design` first.

## Inputs and outputs

| | |
|---|---|
| **Input** | Modified CODEMANIFEST files (from `apply`) |
| **Output** | `docs/design/<function-name>.md` |

## What happens next

- Run [`review`](review.md) on the design artifact (`review(design)`).
- On approval, run [`plan`](plan.md) to compile the design into an execution plan.
