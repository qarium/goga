# Codegraph Usage — producing and consuming the prospective cell graph

Domain: how to run the codegraph analysis and consume its object tree.
Target audience: the CLI command that wraps this cell, the drift
comparison domain, and the later bootstrap stages that draft
CODEMANIFEST files from the graph.

## Import

The entry point is importable from the cell facade:

```python
from goga.codegraph import codegraph
```

## Running the analysis

No arguments are required — the command reads the configured language and the
lint exclusions from the project configuration:

```python
tree = codegraph()
```

All three schema-compatible filters are optional:

```python
filtered = codegraph(
    cells=["goga/codegraph"],  # only these cell paths
    max_depth=2,  # nesting limit
    depends_on=["goga/config"],  # keep only cells depending on these
)
```

## Output node format

The routine returns a list of root `CodegraphNode` records — the
code-derived tree. Each node carries the four code-derivable fields
(the schema node minus the manifest-only fields — no description or
usages; dependencies carry types only) plus the conditional `tools`
area — the tool-contribution surface, present iff at least one tool
contributed:

| Field | Description |
|-------|-------------|
| `cell` | Normalized path of the directory unit |
| `types` | Sorted facade type names of the unit |
| `dependencies` | Imported facade types grouped by normalized target cell path |
| `children` | Nested child nodes (recursive) |
| `tools` | The committed per-tool facts overlay — {tool identity -> {fact -> value}}; present iff at least one tool contributed |

A project with no analyzable sources yields `[]`.

The caller owns the serialization of the returned tree: the record
fields map one-to-one to the family JSON output keys, serialized with
`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.

## Guarantees for the consumer

- Deterministic: identical code and configuration produce identical trees
- Read-only: the project tree is unchanged after the run
- Purely descriptive: import cycles between prospective cells appear as links
  in both directions, with no verdicts or warnings
- Names resolving outside the project (standard library, third-party) never
  appear as links and never fail the run
- Hook extension: the run delivers the codegraph checkpoints of installed
  tool packages; both hard — a failing or vetoing hook stops the run as a
  clean error before any output; the same checkpoints fire inside every
  codegraph producer call of a drift run; with no subscriptions the output
  is byte-identical

## Failure behavior relevant to the caller

Each condition raises an error the caller surfaces as a clean command
failure:

- an uninitialized project — no .goga/config.yml
- a configured language outside python, golang, javascript, kotlin, swift
- an unparseable source file — the error names the file
- hard failures of the codegraph hooks checkpoints — a crashed or
  malformed-contribution amendment hook, or a vetoed validation gate (the
  merged error lists every violation)

