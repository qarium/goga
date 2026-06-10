# Cell

A **cell** is a directory that encapsulates a distinct responsibility domain with a well-defined API boundary. Each cell contains a `CODEMANIFEST` file that describes the contract and an optional `.usages/` directory with documentation for API consumers.

```
cell/
├── CODEMANIFEST       # YAML DSL describing the API contract
└── .usages/*.md       # Practices for working with the cell
```

## When to create a cell

Create a cell when you identify a distinct responsibility domain with a well-defined API boundary. The principle: **one responsibility zone — one cell**.

A separate cell is warranted when **at least one** of the following holds:

- The logic can be decoupled from other system components
- The logic owns a data model distinct from other system components
- The functionality must be reused across multiple areas of the project
- The purpose can be stated in a single phrase without "and"

## Design order

Design cells bottom-up — from leaves to root. If cell A depends on cell B (via Imports), design B first. The CODEMANIFEST of a dependency cell defines the types and practices that dependent cells import. You cannot correctly describe Imports without knowing exactly what the dependency provides.

## Granularity

A cell must be large enough to function as an independent unit, yet small enough to describe its contract without losing focus.

**Too fine** — one cell per function. When multiple types are always used together and have no independent meaning, they belong in the same cell.

**Too coarse** — a cell covers heterogeneous functionality. If describing the cell's purpose requires "and", consider splitting it into multiple cells.
