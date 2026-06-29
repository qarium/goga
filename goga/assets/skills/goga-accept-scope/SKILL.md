---
name: goga-accept-scope
description: Defines the acceptance scope — the set of cells for a given functionality
---
# goga-accept-scope

## Identity

You are responsible for defining the acceptance scope — identifying the set of cells associated with a given functionality.

## Algorithm

### Determine acceptance scope

Acceptance operates at the functionality level. One functionality may span one or more cells.

Resolve the scope:

1. **Arguments contain a functionality description or path** — use as `<target>`
2. **Arguments are empty** — analyze `git diff` to identify changed files
3. **No changes found or scope is ambiguous** — prompt the user via AskUserQuestion:
   - **question**: "Which functionality should undergo acceptance?"
   - **header**: "Acceptance scope"
   - **multiSelect**: false
   - **options**:
     - **label**: "Branch changes", **description**: "Determine from git diff"
     - **label**: "Specific functionality", **description**: "Provide a functionality description"
     - **label**: "All project cells", **description**: "Full acceptance"

### Map scope to cells

1. Load the project schema: `goga schema`
2. Match the functionality description or `git diff` results to cells in the schema
3. For each matched cell:
   a. Verify the CODEMANIFEST file exists
   b. Load the CODEMANIFEST
   c. Verify the `.usages/` directory exists
   d. Classify change types: CODE / MANIFEST / USAGE / TEST
4. Discover dependent cells — cells that import the matched cells
5. Classify each dependency:
   - **DIRECT** — imports a changed API
   - **TRANSITIVE** — imports a DIRECT dependency
6. Generate the Acceptance Scope Report

STOP if:
- No cells are discovered
- A cell lacks a CODEMANIFEST
- The scope is ambiguous

## Output format

Complete every section. Empty sections are not allowed.

```md
# Acceptance Scope Report

## Data source
[How the scope was resolved: arguments, git diff, or user selection]

## Functionality
[Functionality description, if determined]

## Cells for acceptance
[Table: Cell | Path | Change types (CODE/MANIFEST/USAGE/TEST)]

## Affected dependencies
[Table: Dependent cell | Dependency type (DIRECT/TRANSITIVE) | Impact assessment]

## Scope summary
[Total cells, total files, distribution by change categories]
```
