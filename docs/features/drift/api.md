# Drift — API

The facade of the domain package **`goga.drift`** — the structural drift report between the declared and the code-derived views.

The signatures below are the CODEMANIFEST contracts of the cell.

```python
drift(cells: list[str] = [], max_depth: int | None = None, depends_on: list[str] = []) -> list[DriftEntry]

compare_views(schema_tree: list[SchemaNode], codegraph_tree: list[CodegraphNode]) -> list[DriftEntry]

scope_entries(
    entries: list[DriftEntry],
    schema_tree: list[SchemaNode], codegraph_tree: list[CodegraphNode],
) -> list[DriftEntry]
```

`drift` builds the two complete views (`schema([], None, [])` and `codegraph([], None, [])`), compares them, and scopes the result by the two filtered views (`schema(cells, max_depth, depends_on)` and `codegraph(cells, max_depth, depends_on)`) — the filters select what is reported, never what is compared. It returns the flat list of `DriftEntry` records in the stable order (cell path, then kind); the caller owns the serialization (see [CLI](cli.md) for the output shape). The routine reads no manifests and no sources itself — the views arrive fully assembled from the two producers — and never prints.

`compare_views` and `scope_entries` are the two pure steps behind it: the name-level comparison of two complete view trees (`SchemaNode` from `goga.schema.hooks`, `CodegraphNode` from `goga.codegraph.facts`) and the survival scoping of computed entries over two filtered view trees — an entry survives iff its cell survives in at least one of the two filtered views; the input order is preserved, and no entry is fabricated, altered, or reordered.

`DriftEntry` is a frozen keyword-only record:

| Field | Type | Description |
|---|---|---|
| `kind` | `str` | Direction of the discrepancy — `schema_only` or `codegraph_only` |
| `cell` | `str` | Normalized cell path of the discrepancy subject |
| `types` | `list[str] \| None` | Sorted type names missing from the other view; `None` marks a cell-level discrepancy |

**Raises:**

- `FileNotFoundError` — `.goga/config.yml` is absent (the uninitialized-project error of the code-derived view).
- `ValueError` — the AST has parsing errors, the configured language is outside `python`, `golang`, `javascript`, `kotlin`, `swift`, a source file fails to parse (the message names the file), or a schema checkpoint hard-fails — every producer error propagates unchanged.

The routine is read-only, deterministic, and idempotent — identical project state, configuration, and filters produce identical reports.

## Example

```python
from goga.drift import drift

report = drift(cells=[], max_depth=None, depends_on=[])
for entry in report:
    print(entry.kind, entry.cell, entry.types)
```
