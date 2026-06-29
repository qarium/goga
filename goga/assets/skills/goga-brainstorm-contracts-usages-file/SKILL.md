---
name: goga-brainstorm-contracts-usages-file
description: Designing cell-level consumer usage files for a single cell in the brainstorm contracts pipeline
---
# goga-brainstorm-contracts-usages-file

## Algorithm

Design the consumer API documentation in `<cell_path>/.usages/` for the given cell.

- The **rules for writing** `<cell_path>/.usages/` files follow **`goga-cookbook`**.
- `.usages/` placement and `{name}.md` path resolution follow **`goga-cell`**.

### Step 1 — Collect the cell's API

Build the factual basis for the documentation:

- From **`[TYPE_DETAIL_REPORT]`** — the cell's contract: each type's responsibility, methods/properties/signatures, and
  interactions. This is the API surface a consumer calls.
- From the **usages-inline** and **annotations** results — the connected Usages keys and the documented behavior, so the
  examples reflect how the cell is meant to be consumed.

### Step 2 — Review existing usage files

Review existing md files in `<cell_path>/.usages/` — preserve or extend them; do not overwrite blindly.

### Step 3 — Split into functional domains

Split the API (Step 1) into functional domains by the actions a consumer performs.

### Step 4 — One file per domain

One file per domain: `<cell_path>/.usages/<domain>.md`.

### Step 5 — Write the content

Per file: a domain statement (area + target audience), ready-to-use patterns with code examples, and
preconditions/side effects relevant to the consumer. Self-contained — describes **how to use**, not **what to implement**.

### Return

Return the paths: `<cell_path>/.usages/<domain>.md` and Full usage-files content.
