# Drift Usage — producing and consuming the contract-drift report

Domain: how to run the drift comparison and consume its report entries.
Target audience: the CLI command that wraps this cell and acceptance
review flows that check delivered functionality against declared
contracts.

## Import

The entry point is importable from the cell facade:

```python
from goga.drift import drift
```

## Running the comparison

No arguments are required — the comparison always covers the complete
declared and code-derived views of the current project:

```python
report = drift()
```

The three family filters are optional and scope the report only:

```python
report = drift(
    cells=["goga/config"],  # scope the report to these cell paths
    max_depth=2,  # nesting limit for the scope
    depends_on=["goga/ast"],  # scope to cells depending on these
)
```

## Report entries

The routine returns a list of `DriftEntry` records — one per
discrepancy, in the stable order (cell path, then kind):

| Field | Description |
|-------|-------------|
| `kind` | Direction — `schema_only` (exists only in the declared view) or `codegraph_only` (exists only in the code-derived view) |
| `cell` | Normalized cell path of the subject |
| `types` | Sorted type names missing from the other view; `None` marks a cell-level discrepancy |

Exactly four semantic kinds map onto direction × presence of `types`:
cell only declared, cell only in code, type only declared, type only
in code. A cell present in both views with type drift in both
directions yields two entries; a cell present in one view only yields
a single cell-level entry. An empty report means the views agree.

The caller owns the serialization of the report: each entry maps to
the keys `kind`, `cell`, and `types` — the `types` key is written
only for type-level entries — serialized with
`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.

## Guarantees for the consumer

- Deterministic: identical project state, configuration, and filters
  produce an identical report
- Read-only: the project tree is unchanged after the run
- Complete-view semantics: discrepancies are computed on the complete
  views; the filters scope the report only — a cell is reported when
  it survives the filters in at least one of the two filtered views,
  and the `depends_on` asymmetry never fabricates cell-level entries

## Failure behavior relevant to the caller

Every failure of a view producer propagates unchanged — the caller
surfaces it as a clean command failure:

- an uninitialized project — no .goga/config.yml
- a configured language outside python, golang, javascript, kotlin, swift
- an unparseable source file — the error names the file
- manifest loading and validation failures of the declared view
- hard failures of the schema hooks checkpoints

