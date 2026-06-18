---
name: goga-brainstorm-contracts-usages-inline
description: Connecting header Usages for a single cell in the brainstorm contracts pipeline
---

# goga-brainstorm-contracts-usages-inline

## Algorithm

Connect every practice the cell **consumes** into its `CODEMANIFEST` header.

- **Syntax and semantics** of the `Usages` and `Imports.Usages` directives (keys, paths, aliasing, conflict rules)
  follow **`goga-cell`**.
- The **choice of connection form** (file / URL / inline) and **when a practice is worth declaring** follow
  **`goga-cookbook`**.

### Step 1 — Collect what the cell consumes

Build the factual basis for all three categories from the reports:

- From **`[CELL_DISTRIBUTION_REPORT]`** — the types this cell imports from other cells (inter-cell `Imports`).
- From **`[TYPE_DETAIL_REPORT]`** — each type's responsibility, signatures, and interactions; identify the **external
  libraries, patterns, and formats** the types rely on.

### Step 2 — Base usages

Take **all** base usages from **`goga-codemanifest-base`** **as-is** and add them to the `Usages` directive unchanged.
Where a base practice constrains the contract form (error style, naming, pattern), the contract must comply — flag it
so the annotations step enforces it.

### Step 3 — Cross-cell usages

For every type imported from another cell (Step 1): if the provider cell has `.usages/` files describing how to work
with that type's API, connect them via `Imports.Usages`. Resolve any name clash with a local `Usages` key through the
`AS` alias (`goga-cell`). These document the provider's facade — they do not impose obligations on this contract.

### Step 4 — External usages

For every external library, pattern, or format the cell relies on (Step 1): look for an existing usage file in
**`.goga/usages/`** or **`.goga/usages/cooks/`**. If found, connect it via `Usages` in the form `goga-cookbook`
prescribes for the situation. If none exists, record it in **External Usage Gaps**.

### Return

Return the connected **base / cross-cell / external usages** and the set of **Usages keys** (the backtick targets the
annotations step references).
