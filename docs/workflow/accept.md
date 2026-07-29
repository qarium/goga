# Accept

Final acceptance orchestrator. Verifies that completed work satisfies its contracts and tests before the task is considered done. Enforces triple consistency across CODEMANIFEST, implementation, and `.usages/*.md`.

## Synopsis

```text
/goga:accept [<target>]
```

`<target>` is optional. When omitted, the skill determines scope from `git diff` (branch changes) or asks via `AskUserQuestion` (specific functionality / branch changes / all project cells).

When provided, `<target>` is a **functionality description or path** — free-text that the scope resolver matches to cells in the project schema. For example, `auth`, `goga/ast/nodes`, or a short phrase describing the feature.

Examples use the slash-command form `/goga:<command>`, which works in agents that consume the goga command bundle (`claude`, `opencode`, `qwen`). Codex and cursor do not register commands — invoke the skill directly: `goga-accept` (Codex: `$goga-accept`). See [Workflow](index.md).

## Output artifact

A **Final Acceptance Report** with a verdict:

- **ACCEPTED** — all steps passed, test coverage ADEQUATE or above.
- **ACCEPTED_WITH_NOTES** — WARNING/INFO findings that do not block acceptance.
- **REJECTED** — CRITICAL findings or CRITICAL coverage gaps.

## Context initialization

| Step | Action |
|---|---|
| 1 | Load `goga-cell` — to understand CODEMANIFEST structure and DSL syntax. |
| 2 | Load `goga-cookbook` — to apply DSL principles. |
| 3 | Load `goga-lang-disp` — to apply language conventions. |
| 4 | Run `goga schema`. |
| 5 | Load `goga-codemanifest-base` — for base usages and annotations. |
| 6 | Proceed to Pipeline Step 1. |

## Pipeline

Execute steps strictly sequentially. Each step produces complete output before the next begins.

### Step 1. Scope definition (`goga-accept-scope`)

Define the set of cells associated with the functionality. Scope is resolved in priority order:

1. **Arguments contain a functionality description or path** — use as `<target>` and match to cells in the schema.
2. **Arguments are empty** — analyze `git diff` to identify changed files and map them to cells.
3. **No changes found or scope is ambiguous** — prompt the user via `AskUserQuestion`:
   - **Branch changes** — determine from `git diff`.
   - **Specific functionality** — user provides a description.
   - **All project cells** — full acceptance.

| Sub-step | Action |
|---|---|
| Resolve scope | Apply the priority order above. |
| Map scope to cells | Run `goga schema`; match description/diff to cells; for each matched cell verify CODEMANIFEST exists and `.usages/` exists; classify change types (CODE / MANIFEST / USAGE / TEST); discover dependent cells (DIRECT or TRANSITIVE). |

**Output:** Acceptance Scope Report. **STOP** if no cells discovered, a cell lacks CODEMANIFEST, or scope ambiguous.

### Step 2. CODEMANIFEST review (`goga-accept-manifest-review`)

Verify each cell's CODEMANIFEST against its implementation.

| Sub-step | Action |
|---|---|
| 1. Load context | Load Scope Report; load `goga-lang-disp`, `goga-cell`, `goga-cookbook`, `goga-codemanifest-base`. |
| 2. Pre-flight check | Run `goga lint`. Errors → CRITICAL; resolve before proceeding. |
| 3. Per-cell review | For each cell: read CODEMANIFEST; parse entities/methods/properties/imports/usages/annotations/locations; enumerate source files; read every source file at its declared `location`; verify facade exists. Run `goga contract <cell-path>`. For each Entity: compare constructor signature, methods, properties. For each Routine: compare signature. Identify undocumented entities, inaccurate signatures, behavioral mismatches. Update CODEMANIFEST where the contract is wrong; record unresolvable discrepancies. |

**Output:** Manifest Review Report. **STOP** on unresolvable inconsistency.

### Step 3. Usages review (`goga-accept-usage-review`)

Validate cell-level usage files against actual implementation.

| Sub-step | Action |
|---|---|
| 1. Load context | Load Scope Report; for each cell load CODEMANIFEST, implementation files, cell-level usages (`<cell_path>/.usages/*.md`), project usages referenced via `Usages`. |
| 2. Analyze cell-level usages | For each file: example validity, description accuracy, entity name alignment with CODEMANIFEST signatures, coverage completeness, self-sufficiency (no need to read source), no duplication of CODEMANIFEST annotations. Update discrepancies. |
| 3. Analyze project usages | For each referenced project usage: example validity, API coverage, description accuracy. Record remarks **without modifying** the file. |
| 4. Validate updates | Re-run checks after edits. |

**Output:** Usage Review Report. **STOP** on unresolvable inconsistency.

### Step 4. Test coverage assessment (`goga-accept-test-assessment`)

Evaluate test coverage of cells.

| Sub-step | Action |
|---|---|
| 1. Context loading | Load Scope Report; for each cell load CODEMANIFEST, implementation files, existing tests. |
| 2. Coverage point identification | For each cell: contract points (signatures, guarantees, behavior), branch points (conditionals, error handling), integration points (cross-cell calls, side effects), boundary points (empty/nil/edge cases). |
| 3. Test analysis | Enumerate tests; classify as CONTRACT or INTEGRATION; for each coverage point determine whether covered, by which test, and how thoroughly. |
| 4. Coverage verdict | EXCELLENT / ADEQUATE / INSUFFICIENT / CRITICAL_GAPS. |

**Output:** Test Assessment Report. **STOP** on critical coverage gaps in changed behavior.

### Step 5. Acceptance report (`goga-accept-report`)

Synthesize the Final Acceptance Report from all preceding outputs.

| Section | Content |
|---|---|
| Summary | One paragraph: what was verified and the overall result. |
| Acceptance Scope | Table of verified cells and change types. |
| CODEMANIFEST Status | CONSISTENT / INCONSISTENT + number of updates. |
| Usages Status | CONSISTENT / INCONSISTENT + number of updates. |
| Test Coverage Assessment | EXCELLENT / ADEQUATE / INSUFFICIENT / CRITICAL_GAPS + summary. |
| Critical Findings | Table: source / finding / status (fixed/open). |
| Warnings | Table: source / finding / recommendation. |
| Applied Updates | List of files modified during acceptance. |
| Risks | Table: risk / severity / mitigation. |

Determine the verdict: ACCEPTED / ACCEPTED_WITH_NOTES / REJECTED.

## Stop conditions

The pipeline halts on any of:

- No cells detected in scope.
- Unresolvable manifest-implementation inconsistency.
- Unresolvable usage-implementation inconsistency.
- Critical coverage gaps in changed behavior.
- Any output section left empty.

Each stop produces a structured report explaining what to fix.

## When to use

- At the end of the **full cycle**, after the build-test-change loop converges.
- At the end of the **Propose → Change** shortcut.
- Optionally, after a standalone `change` — when formal sign-off on a fix is desired.

## Inputs and outputs

| | |
|---|---|
| **Input** | Completed implementation with reconciled contracts and usages |
| **Output** | Final Acceptance Report with verdict |

## What happens next

- If `accept` passes — the task is complete; merge, deploy, or move on.
- If `accept` stops — fix the reported issues (typically via [`change`](change.md)) and re-run `accept`.
