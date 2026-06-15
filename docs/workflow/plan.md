# Plan

Compile a design document into a ralphex-compatible execution plan. The plan is a structured markdown file that ralphex autonomously executes through Claude Code to produce the implementation.

## Synopsis

```text
/goga:plan <function-name>
```

Examples in this document use Claude Code style (`/goga:<command>`). For other agents, invoke the skill directly: `goga-plan`.

## Output artifact

`docs/plans/<function-name>.md` — an execution plan with this structure:

- `### Task N: <title>` headings define individual tasks
- `- [ ]` checkboxes mark incomplete items
- `## Validation Commands` section lists verification commands
- Three task types: **infrastructure** (cell structure, facade, re-exports), **TDD coding** (entity implementation with the ralphex protocol), **integration tests** (cross-entity scenarios)

Only ONE task is executed per ralphex iteration.

## Algorithm

### Phase 1. Context loading

| Step | Action |
|---|---|
| 1 | Load DSL specification via `goga-cell`. |
| 2 | Load DSL application principles via `goga-cookbook`. |
| 3 | Load language implementation rules via `goga-lang-disp`. |
| 4 | Load the plan template from `output-template.md`. |
| 5 | Load project conventions from `conventions.md`. |
| 6 | Read the design document from `docs/design/<function-name>.md`. Halt if missing. |

### Phase 2. Compile design document into plan

| Step | Action |
|---|---|
| 1. Extract data from design | Contract changes → task scope; applied fixes → context; entity interactions → diagrams; code stack traces → verified chains; algorithm design → checkboxes; cross-cutting concerns → distributed across tasks; usages analysis → task context; `.usages/` updates → tasks; test stack traces → test instructions. Transfer traces and diagrams **verbatim**, do not summarize. |
| 2. Compile into ralphex tasks | For each entity: create tasks following DSL compilation rules, cell boundaries, ralphex format requirements, task ordering, TDD workflow, task formation rules, templates, and project conventions. |
| 3. Save the plan | Write to `docs/plans/<function-name>.md`. Create directory if missing. |

### Phase 3. Plan verification

10-point checklist:

1. Every entity from contract changes covered by a task.
2. Every test scenario included in task test instructions.
3. Every Usages analysis entry referenced in at least one task.
4. Every planned `.usages/` entry has a creation task or step.
5. Interaction diagrams and traces transferred verbatim.
6. All coding tasks follow the TDD workflow.
7. Ralphex format correct (`### Task N:` headings, `- [ ]` checkboxes).
8. Every task atomic and self-contained.
9. Validation commands defined.
10. CODEMANIFEST files marked as read-only.

If any answer is "no" — rework the plan.

### Phase 4. Present summary

- Task table (numbered, with type and one-line description)
- Key design decisions (3–5 points)
- Total test count

## DSL compilation mapping

| DSL element | Result in plan |
|---|---|
| `Types Import` | Context section — internal types grouped under one `From` |
| `Usages Import` | Context section — imported practice from another cell's `.usages/` |
| `Usages` | Context section with implementation guidance |
| `Annotations` | Contextual hints embedded into task descriptions |
| `->Re-exports` | Task: ensure importability from the facade |
| `Entity` with `properties` | Task: create entity in `location`, implement properties |
| `Entity` with `methods` | Task: implement methods with behavior from descriptions |
| Standalone function | Task: implement function in `location` |
| `Type::` mutation | Task: implement interface mutation mechanism |
| Method/property descriptions | Reflected in task implementation instructions |

## Task ordering (within a cell)

1. Infrastructure tasks (cell structure, facade, re-exports)
2. Entity skeleton tasks
3. Property implementation tasks
4. Method implementation tasks
5. Interface mutation tasks
6. Integration test tasks

Leaf cells first, then parent cells. Entities sharing the same `location` are grouped into one task.

## Ralphex execution protocol (embedded in each coding task)

Each coding task includes steps 0–8 as checkboxes:

| Step | Action |
|---|---|
| 0 | Declaration — declare which task is being worked on |
| 1 | Contract tests — write contract tests (they will fail) |
| 2 | Implementation — write the code |
| 3 | Interface verification — run contract tests |
| 4 | Logic tests — write behavioral tests |
| 5 | Debugging — run tests, fix implementation until all pass |
| 6 | Contract re-verification — verify contract obligations still met |
| 7 | Lint — run linter, fix formatting |
| 8 | Completion — mark checkboxes as completed |

After completion: `→ REVIEW → APPROVAL → NEXT_TASK`.

## Boundaries

**Allowed within a cell:** additional internal files, helper functions/classes, private abstractions, internal restructuring, decomposition into smaller units.

**Prohibited:** creating new cells, defining new cell-level interfaces outside the current one, replacing contract entities with internal-only abstractions, ignoring `location`, modifying `CODEMANIFEST` files (read-only).

## Resolving the function name

If `<function-name>` is omitted:

1. Scan `docs/design/`.
2. **Single file** — use automatically.
3. **Multiple files** — ask the user.
4. **Empty or missing** — halt and ask the user to run `design` first.

## Inputs and outputs

| | |
|---|---|
| **Input** | `docs/design/<function-name>.md` |
| **Output** | `docs/plans/<function-name>.md` |

## What happens next

- Run [`review`](review.md) on the plan artifact (`review(plan)`).
- On approval, run [`goga build`](build.md) to execute the plan.
