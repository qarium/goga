---
name: goga-brainstorm-contracts-usages-inline
description: Connecting header Usages for a single cell in the brainstorm contracts pipeline
---

# goga-brainstorm-contracts-usages-inline

## Algorithm

For the given cell, connect the practices it **consumes** into the CODEMANIFEST header.

- **Base usages** (from `goga-codemanifest-base`) — include ALL of them in the `Usages` directive. If a base practice
  constrains the contract form (error style, naming, pattern), the contract must comply with it.
- **Cross-cell usages** — if a type here uses a library/pattern described in another cell's usages, import it via
  `Imports.Usages`.
- **External usages** — if a type uses an external library with a usage file in `.goga/usages/` or
  `.goga/usages/cooks/`, connect it via `Usages`. If no file exists yet, record the gap to the report; creating the file
  is a separate skill.
