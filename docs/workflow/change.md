# Change

Specification-governed maintenance workflow. Coordinates sub-skills to modify code while preserving triple consistency across `CODEMANIFEST`, implementation, and `.usages/*.md`.

`change` works as part of the full cycle (post-build bugfix loop) and standalone for point fixes that do not require revisiting architecture.

## Synopsis

```text
/goga:change <description>
```

Examples in this document use Claude Code style (`/goga:<command>`). For other agents, invoke the skill directly: `goga-change`.

## Output artifacts

- Modified implementation code
- Reconciled CODEMANIFEST files
- Reconciled `.usages/*.md` files
- Final Change Execution Report

## Context initialization

| Step | Action |
|---|---|
| 1 | Load `goga-cell` — for understanding CODEMANIFEST structure and directives. |
| 2 | Load `goga-cookbook` — for applying DSL principles. |
| 3 | Load `goga-lang-disp` — for language conventions. |
| 4 | Run `goga schema`. |
| 5 | Load `goga-codemanifest-base` — for base usages and annotations. |
| 6 | Proceed to Pipeline Step 1. |

## Pipeline

Execute steps strictly sequentially. Each step produces its own complete output before the next begins.

### Step 1. Scope resolution (`goga-change-scope-resolver`)

Resolve the **minimal semantic scope** of the change.

1. Read task description.
2. Run `goga schema`.
3. Apply `goga-cell`, `goga-cookbook`, `goga-codemanifest-base`.
4. Identify candidate cells from schema matching task intent.
5. For each candidate: resolve direct dependencies and usage relationships.
6. Trace semantic participation — include only cells with behavioral relevance.
7. Exclude cells with infrastructural-only dependency, no behavioral participation, no manifest involvement, no data flow, or speculative relevance.
8. Prioritize cells by: runtime participation > manifest relevance > usage participation > direct dependency > behavioral proximity.

**Output:** Scope Resolution Report. **STOP** if scope is empty or ambiguity unresolved.

### Step 2. Investigation (`goga-change-investigator`)

Evidence-driven root cause investigation. Internally invokes `goga-change-tracer`.

| Sub-step | Action |
|---|---|
| 1. Load context | Read task, scope report, candidate cells' CODEMANIFEST/implementation/tests; read ALL referenced usages (file paths in `.goga/usages/` and imported usages `{from_path}/.usages/{name}.md`); apply `goga-codemanifest-base`. |
| 2. Trace behavior | Invoke `goga-change-tracer`: trace call flow, data flow, manifest algorithm, usage paths; trace cross-cell dependencies; identify inconsistencies (code path not in manifest, manifest not matching code, usage recipe not matching behavior). Build trace graph. **STOP** on circular dependency, unresolved path, or manifest/code inconsistency. |
| 3. Build and validate hypotheses | Build root cause hypotheses; validate against CODEMANIFEST algorithms, tests, actual code, usage recipes. |
| 4. Breaking change analysis | For every proposed change answer: will same call produce different behavior? will file paths change? output format? return semantics? manifest guarantees? will tests break? **Any YES → STOP.** |
| 5. Confidence estimation | HIGH (deterministic, full evidence), MEDIUM (probable, partial), LOW (ambiguous/speculative). **STOP** on LOW or ambiguous MEDIUM. |
| 6. Produce Investigation Report | Fill all sections — no empty sections. |

### Step 3. Planning (`goga-change-planner`)

Safe specification-governed change planning.

1. Read Investigation Report.
2. Identify affected cells and affected usages.
3. Analyze manifest impact — what CODEMANIFEST sections must change.
4. Analyze usage impact — what usage files must change and how (examples, descriptions, patterns).
5. Verify compatibility with manifest-defined algorithms.
6. Verify behavioral compatibility (same arguments → same behavior).
7. Verify usage compatibility (existing recipes remain valid).
8. Design minimal implementation strategy.
9. Define test strategy.
10. Assess risks.

**STOP** if plan conflicts with manifest, requires breaking change, or exceeds investigation scope.

**WAIT:** present plan to user; obtain approval before proceeding.

### Step 4. Compatibility guard (`goga-change-compatibility-guard`)

For every proposed modification, answer every checklist item YES (compatible) or NO (breaking) with evidence.

- **API compatibility** — signature unchanged, return type unchanged, default values preserved.
- **Semantic compatibility** — same args → same behavior, output format, file paths, error messages/codes.
- **Algorithmic compatibility** — manifest-defined steps preserved, execution order unchanged, side effects unchanged.
- **Consumer compatibility** — existing tests pass, usage recipes valid, downstream consumers unaffected.

**Any unchecked box = BREAKING CHANGE = STOP pipeline.** Generate Breaking Change Escalation Report.

### Step 5. Implementation (`goga-change-implementer`)

Minimal safe implementation changes per plan.

1. Read approved Change Plan.
2. Apply `goga-lang-disp` (naming, file structure, signatures).
3. Apply `goga-codemanifest-base` (conventions, validation rules).
4. For each modification: locate exact code location, apply minimal change, verify match with plan.
5. Run project tests.
6. Run linters and validators.
7. On failure: fix, increment iteration counter; if iteration > 5 → STOP, generate Stabilization Escalation Report.
8. Verify no modifications outside approved scope.

**STOP** if tests/linters fail after 5 iterations, scope exceeds plan, or unintended side effects detected.

### Step 6. Testing (`goga-change-test-engineer`)

Produce test files and coverage report for changed behavior.

**STOP** on coverage gaps for changed behavior.

### Step 7. Manifest reconciliation (`goga-change-manifest-reconciler`)

Reconcile CODEMANIFEST with implementation.

**STOP** on manifest-implementation inconsistency.

### Step 8. Usage reconciliation (`goga-change-usage-reconciler`)

Reconcile `.usages/*.md` with implementation.

**STOP** on usage-implementation inconsistency.

### Step 9. Drift analysis (`goga-change-drift-analyzer`)

Detect specification drift across the triple (manifest ↔ code ↔ usages).

**STOP** on unresolved drift.

### Step 10. Validation (`goga-change-validator`)

Final gates and template completeness check.

**STOP** on any gate failed or incomplete templates.

### Step 11. Reporting (`goga-change-reporting`)

Produce the Final Change Execution Report.

## Breaking change policy

A **breaking change** is any modification where:

- An existing call with the same arguments produces different behavior.
- Existing file paths, output formats, or return semantics change.
- Manifest-defined guarantees are altered.

When detected:

1. STOP pipeline immediately.
2. Generate Breaking Change Escalation Report.
3. Do NOT dismiss risk with justification.
4. Do NOT reinterpret as acceptable.

The agent never decides whether a breaking change is acceptable. Only the user can override a STOP.

## When to use

`change` covers three scenarios:

### 1. Post-build bugfix loop (full cycle)

After `goga build` produces an implementation, you test it. If bugs or defects appear, run `change` to fix them. Repeat the build-test-change loop until stable, then run `accept`.

```
... build → change (loop) → accept
```

### 2. Standalone point fix

For small fixes that do not touch contracts — bug fixes, behavior tweaks, refactors that preserve the API. `change` is followed by `accept` to formally close the fix.

```
change → accept
```

### 3. Propose → Change shortcut

When the cell contract is stable but an external dependency changes — swap one library for another that implements the same logic. The new library needs a new `usage` file, and the implementation must be rewritten against it. Formulate the task with `propose`, then run `change` to perform the rewrite.

```
propose → change → accept
```

This path is significantly faster than the full cycle while preserving quality.

## Inputs and outputs

| | |
|---|---|
| **Input** | Change description (natural language) |
| **Output** | Modified code + reconciled CODEMANIFEST + reconciled `.usages/*.md` + Final Change Execution Report |

## What happens next

- Bugfix loop — re-test, then re-run `change` if needed, or proceed to `accept`.
- Standalone — verify the fix manually.
- Propose → Change shortcut — run [`accept`](accept.md) for final sign-off.
