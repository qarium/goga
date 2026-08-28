# Review

A dispatcher that routes the request to a specialized review skill based on the artifact type. Each specialized skill performs a deep verification pass against authoritative sources (CODEMANIFEST, schema, source code, usages).

## Synopsis

```text
/goga:review <path-or-cell>
/goga:review               # interactive: choose a type
```

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-review` (Codex: `$goga-review`). See [Workflow](index.md).

## Dispatch logic

When the argument is a path under `.goga/history/`, it must match `.goga/history/<year>/<topic>/<kind>.md` (a 4-digit `<year>`); the review type comes from the `<kind>` filename:

| Artifact kind | Type | Specialized skill |
|---|---|---|
| `prd.md` | `prd` | *review not supported* (no dedicated skill yet) |
| `adr.md` | `adr` | *review not supported* (no dedicated skill yet) |
| `task.md` | `task` | `goga-review-task` |
| `arch.md` | `architecture` | `goga-review-arch` |
| `design.md` | `design` | `goga-review-design` |
| `plan.md` | `plan` | `goga-review-plan` |

Any other filename, a path outside `.goga/history/`, or a cell directory → **cell** (`goga-review-cell`). For `prd` and `adr` the dispatcher stops with "review not supported" — no dedicated review skill exists for those kinds yet.

If the argument is empty, the dispatcher asks which type to review via `AskUserQuestion`.

## When to use

After each command that produces an artifact, before moving to the next step. Reviews belong to both workrounds — see [Workflow](index.md):

```
# refinement
propose → review(task)    → development starts

# development
brainstorm → review(arch) → apply
design → review(design)   → plan
plan → review(plan)       → build
```

The task review `review(task)` is the checkpoint that closes refinement: it verifies the task before implementation effort is spent. Review is a checkpoint — it catches drift while changes are still cheap.

---

## Algorithm — Task review (`goga-review-task`)

Validates `.goga/history/<year>/<topic>/task.md` for completeness, correctness, and consistency.

| Phase | Action |
|---|---|
| 1. Load context | Read the task; load `goga-cell` and `goga-cookbook`; run `goga schema`; read CODEMANIFESTs and usages referenced by the task. |
| 2. Structure completeness | Verify all 9 mandatory sections exist and are not empty or placeholders. Missing → Critical; placeholder → High. |
| 3. Current state correctness | Compare "Current State" claims against the actual project schema and CODEMANIFEST. Mismatch → Critical/High. |
| 4. Description & boundaries consistency | Cross-check description, scope (in/out), and acceptance criteria for contradictions. Non-specific criteria → High. |
| 5. Stack & dependencies correctness | Verify usage files exist for declared dependencies; check stack covers description needs. Missing file marked "created" → Critical. |
| 6. Existing architecture correctness | Verify cells mentioned in the task exist; check integration description and impact direction. Non-existent cell → Critical. |
| 7. Risks & constraints | Verify risks are concrete and complete (compatibility, performance, architecture-induced). Generic risks → Medium. |
| 8. Scope | Verify scope estimate matches the description; check subtask breakdown for overlap and coverage. |
| 9. Report and fix | Present findings one at a time (Critical → High → Medium). For each: show severity, area, location, issue, suggested fix; offer `Apply fix` / `Suggest alternative` / `Skip`; re-verify after applying. |

---

## Algorithm — Architecture review (`goga-review-arch`)

Validates `.goga/history/<year>/<topic>/arch.md` for semantic correctness across the whole plan — model cohesion, cell boundaries, requirement sufficiency.

| Phase | Action |
|---|---|
| 1. Load context | Read the plan; load `goga-cell`, `goga-cookbook`, `goga-lang-disp`, `goga-codemanifest-base`; run `goga schema`; read existing CODEMANIFESTs and `.usages/` of modified cells; read task file if present. |
| 2. Plan structure validation | Verify 4 mandatory sections exist: implementation order, artifacts per cell, dependency map, verification checklist. Implementation code in the plan → Critical. |
| 3. Flat model reconstruction | Build a cross-cell type graph (vertices = types, edges = interactions) and render as ASCII. |
| 4. Flat model cohesion | Completeness (no implicit types), connectivity (no dangling types), consistency (input/output type alignment along chains). |
| 5. Cell cohesion | Internal cohesion (types in a cell interact), boundary soundness (single responsibility, no "and"), dependency directionality (leaves→root, no cycles), minimal cross-cell coupling, usages connections, usages isolation (no cross-references between `.usages/` files). |
| 6. CODEMANIFEST requirements sufficiency | **Contract precision** (unambiguous signatures, justified mutations/embeddings, correct Entity/Routine classification, conformant naming); **usages quality** — the header `Usages:` directive includes the project's base usages from `goga-codemanifest-base` (`goga config codemanifest.usages`); **annotation quality** — the global `Annotations:` includes the project's base annotations transferred **verbatim** (no rephrasing or summarizing), no placeholders, algorithm steps where achievable. |
| 7. Task requirements coverage | If a task file exists: each requirement, acceptance criterion, risk, and subtask must map to plan elements. |
| 8. Impact on existing architecture | Modified cells must be described as diffs; changes must not break existing contracts; dependent cells must be acknowledged. |
| 9. Report and resolve findings | Present findings one at a time (Critical → High → Medium), offer `Apply fix` / `Propose alternative` / `Skip`, re-verify after applying. |

---

## Algorithm — Design review (`goga-review-design`)

Verifies `.goga/history/<year>/<topic>/design.md` for logical correctness by tracing the full code stack for each entry point and test scenario.

| Phase | Action |
|---|---|
| 1. Context loading | Load `goga-cell` and `goga-cookbook`; read the design document; read relevant CODEMANIFESTs and source files; run `goga schema` (including `--depends-on`); read referenced usages. |
| 2. Code stack trace verification | For each entry point: trace the chain (entry → input → validation → transformations → external calls → state changes → exit). At each step, verify type continuity, logical correctness, missing steps, error paths, boundary cases. Cross-entity checkpoints: interface↔type, type↔mutation, interface↔interface. Failures classified as **CODEMANIFEST issues** (criticality Critical/High) trigger contract edits. |
| 3. Test logic verification | For each test scenario, write a 6-element trace: name, setup, input, trace, assertions, sufficiency. Categories: positive, negative, boundary cases, sufficiency audit. |
| 4. Report and resolve remarks | Sort by criticality (Critical → High → Medium → Low → Test Gaps → CODEMANIFEST issues). Split into design remarks vs CODEMANIFEST remarks. Present one at a time with proposed fixes; offer `Apply fix` / `Propose alternative`. Re-trace affected chains after each fix. |

---

## Algorithm — Plan review (`goga-review-plan`)

Verifies `.goga/history/<year>/<topic>/plan.md` for completeness and correctness before passing to the ralph-loop.

| Phase | Action |
|---|---|
| 1. Load context | Load `goga-lang-disp`, `goga-cell`, `goga-cookbook`; read the plan, design document, and relevant CODEMANIFESTs. |
| 2. Linter | Run `goga lint`. Errors → Critical. |
| 3. Plan vs CODEMANIFEST | Verify each covered entity: name/location match, descriptions in tasks, annotations cascading into tasks, import context, re-export coverage, mutation coverage. |
| 4. Plan vs design document | Each design entity and test scenario traceable to a task; no orphan tasks. |
| 5. TDD completeness | Each coding task has all 7 TDD steps as checkboxes (contract tests → code → interface verification → logic tests → debugging → contract re-verification → lint). |
| 6. Self-contained tasks | Each task has its own context, imports/usages/annotations, target files; does not depend on other tasks for implementation context. |
| 7. Task order | Infrastructure → entity skeletons → properties → methods → mutations → integration tests. Leaf cells before parent cells. |
| 8. Usages coverage | Each Usages entry referenced in a task with specific content (not just a name); imported usages reference correct source path; planned `.usages/` files have creation tasks. |
| 9. CODEMANIFEST read-only check | No task proposes modifying CODEMANIFEST; "read-only" warning present. |
| 10. Report and fix | Findings presented one at a time (Critical → High → Medium → Low); offer `Apply fix` / `Suggest alternative` / `Skip`. |

---

## Algorithm — Cell review (`goga-review-cell`)

Reviews a cell across three dimensions and proposes remediation per dimension.

| Step | Action |
|---|---|
| 1. Load context | Load `goga-lang-disp`, `goga-cell`, `goga-cookbook`; read CODEMANIFEST and source files; enumerate cell files; read `.usages/*.md`; verify facade. |
| 2. Run tools | `goga lint` (fix syntax before analysis), `goga schema` (for context). |
| 3. Analysis 1 — Code vs Requirements | Compare signatures, methods, properties, location validity, behavioral conformance, import utilization. Proposed action: `goga-design` (`/goga:design`) in **brainstorm** mode. |
| 4. Analysis 2 — Requirements vs Code/Usages | Find undocumented entities, inaccurate descriptions, poor annotation authoring (purpose statement, parameter descriptions, `Algorithm:`/`Requirements:` sections). Proposed action: edit CODEMANIFEST, then `goga-design` (`/goga:design`) in **changes** mode. |
| 5. Analysis 3 — Usages | Verify existence, annotation references, adequacy, categorization. Proposed action: create or update `.usages/*.md` directly. |
| 6. Execute approved actions | For each approved action, execute the proposed remediation; run `goga lint` after all actions and fix any errors. |

## Inputs and outputs

| | |
|---|---|
| **Input** | Path to an artifact, or a type selected interactively |
| **Output** | Findings report; updated artifact file (if fixes applied); verification verdict (passed / failed) |

## What happens next

- If the review passes — proceed to the next workflow step.
- If the review fails — fix the artifact and re-run review until it passes.
