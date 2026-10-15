# `goga drift` compares schema and codegraph domain objects in-process

`drift` owns no traversal of its own: it reuses the existing view producers.
The `schema` and `codegraph` domains are refactored to return clean Python
objects, their CLI commands take over JSON serialization (user-visible output
byte-identical, C2 holds), and `drift` calls both domains and compares the
results as object trees. Rejected alternatives: parsing the JSON strings
(a needless round-trip), shelling out to the CLI processes (version skew,
latency), and re-implementing the walks (a private walker would itself drift
from the commands it audits).

## Decisions

- **Discrepancies are facts of the complete views; filters only scope the
  report.** An entry is reported iff its cell survives the filters in at least
  one of the two filtered views. `--depends-on` selects cells by declared
  dependencies in the schema view and by resolved imports in the codegraph
  view; comparing the filtered trees directly would fabricate cell-level
  entries out of that asymmetry — the pass-through variant was rejected for
  violating the "nothing extra" precision contract.
- **Report encoding: two directions with grouped types.** `kind` is
  `schema_only` or `codegraph_only`; an entry with `types` carries the sorted
  list of that cell's type names missing from the other view; absence of
  `types` marks a cell-level discrepancy. The four semantic discrepancy kinds
  (PRD R4) map onto direction × presence of `types`; no-double-reporting holds
  — a cell-level entry never coexists with type-level entries of the same
  cell, and a cell with type drift in both directions yields two entries.
- **Stable order `(cell, kind)`**, serialized in the family JSON style
  (`indent=4`, `sort_keys=True`, `ensure_ascii=False`).
- **Execution failure exits `2` — a deliberate deviation** from the installed
  family (`schema`, `codegraph`, `usages status` fail with `1`): drift's
  three-outcome contract reserves `1` for "discrepancies found". Do not
  "align" this later.
- **The command help documents the JSON report structure**, as `schema` and
  `codegraph` document theirs.

## Consequences

- `schema` and `codegraph` gain an internal object-returning domain API; the
  serialization moves to the command layer. Their CLI behavior and output stay
  unchanged.
- The PRD was amended alongside this ADR (UX entry point and primary flow, R2,
  R7, R8, In Scope 1 and 6, SC1, SC7) to state the scope-gating semantics, the
  grouped report encoding, the sort key, and the help-format obligation.
