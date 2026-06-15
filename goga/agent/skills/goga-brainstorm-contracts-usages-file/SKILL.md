---
name: goga-brainstorm-contracts-usages-file
description: Designing cell-level consumer usage files for a single cell in the brainstorm contracts pipeline
---
# goga-brainstorm-contracts-usages-file

## Algorithm

Design the consumer API documentation in `<cell_path>/.usages/` for the given cell.

1. Review existing md files in `<cell_path>/.usages/` — preserve or extend them; do not overwrite blindly.
2. Split the contract into functional domains by the actions a consumer performs.
3. One file per domain: `<cell_path>/.usages/<domain>.md`.
4. Content per file: a domain statement, ready-to-use patterns with code examples, preconditions/side effects.
   Self-contained — no cross-references to other practices; describes **how to use**, not **what to implement**.
