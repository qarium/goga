---
name: goga-brainstorm-plan-verification
description: Verification of the assembled architecture plan against the DSL
---

# goga-brainstorm-plan-verification

## Identity

You are responsible for verifying the created architecture plan and fixing the issues found.

## Context

Use these skills for verification:

- **`goga-cell`** and **`goga-cookbook`** — DSL validation (syntax, directives, design principles).
- **`goga-codemanifest-base`** — base usages/annotations compliance.
- **`goga-lang-disp`** — language correctness (naming, `location` file names).

Use this artifact for its specific purpose:

- **`[ARCHITECTURE_PLAN]`** (at `docs/arch/<topic>.md`) — use it as the **object of verification**: its implementation
  order, per-cell CODEMANIFESTs and `.usages/` files, dependency map, and verification checklist, against which the DSL
  checks are run, failures are fixed in place, and the report is produced.

## Workflow

### Phase 1. Run all verification checks

Run every check in **Verification Checks** below. For each, record PASS/FAIL with evidence.

### Phase 2. Fix failures

For each FAIL — fix the issue in the plan file and re-check.

### Phase 3. Produce the report

Produce the `[VERIFICATION_REPORT]` (see Output Format).

## WAIT

Present the final (fixed) plan and the `[VERIFICATION_REPORT]` to the user and obtain final confirmation before the
pipeline concludes.

- **Confirmed** → the pipeline is complete
- **User requests changes** → address the feedback, re-verify, and present again

### Verification Checks

1. **Completeness** — every type, method, property from the approved solution is present in the plan
2. **DSL correctness** — all CODEMANIFESTs syntactically correct (keys, signatures, document structure)
3. **Inter-cell consistency** — Imports reference existing cells, types match
4. **Implementation order** — each cell created after all cells it depends on
5. **No placeholders** — no TBD, TODO, or incomplete descriptions in the plan's CODEMANIFEST files
6. **Usage of Imports.Types** — every imported type is used in the body (signatures, mutations, embeddings, annotations)
7. **Usage of Imports.Usages** — every imported practice is mentioned in at least one annotation
8. **Usage of Usages** — every practice declared in the `Usages` header is mentioned in at least one annotation
9. **Algorithms in annotations** — annotations for routines and methods describe the operation algorithm if achievable
10. **Annotation wording** — annotations do not contain technical implementation details
11. **Resolvability of references in annotations** — every backtick reference resolves (signature variable,
    imported/declared type, Usages/Imports practice)
12. **Location restrictions** — every `location` value is a file name with extension only, no directories, no escaping
    the current level
13. **Absence of cross-imports** — if cell A imports from cell B, cell B does not import from cell A
14. **Embedding from Imports** — every embedded type (via `->`) is available through `Imports`
15. **Mutations from available types** — base types in mutations (`Object::Target`) are available (imported or declared)
16. **Entity / Routine correctness** — types with `methods`/`properties` are Entities; types without are Routines and
    lack these sections
17. **Base usages from configuration** — each base practice is included in `Usages` of all CODEMANIFESTs and referenced
    in at least one annotation
18. **Base annotations from configuration** — base annotations are included in `Annotations` of all CODEMANIFESTs and
    contracts comply with them
19. **Language correctness** — type/method/property names comply with target-language conventions; `location` values
    have correct file names for the target language

## Output Format

Fill every section. No empty sections.

```md
# [VERIFICATION_REPORT]

## Check Results
[Table: # | Check | PASS/FAIL | Evidence]

## Fixes Applied
[Table: Issue | Fix | Re-check status]

## Unresolved Issues
[List any unresolved DSL errors or failed checks. Empty if none]

## Final Status
[VERIFIED / FAILED — with justification]
```

## STOP if:
- unresolved DSL errors remain
- any verification gate fails after attempted fix
