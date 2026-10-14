# Codegraph Usage — producing and consuming the prospective cell graph

Domain: how to run the codegraph analysis and consume its JSON output.
Target audience: the CLI command that wraps this cell and the later bootstrap
stages that draft CODEMANIFEST files from the graph.

## Import

The entry point is importable from the cell facade:

```python
from goga.codegraph import codegraph
```

## Running the analysis

No arguments are required — the command reads the configured language and the
lint exclusions from the project configuration:

```python
document = codegraph()
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

Each node carries exactly the code-derivable fields — the schema node minus
the manifest-only fields (no description, usages, tools; dependencies carry
types only):

```json
[
    {
        "cell": "goga/codegraph",
        "children": [],
        "dependencies": {
            "goga/config": ["load_project_config"]
        },
        "types": ["codegraph", "discover_sources", "render_graph"]
    }
]
```

A project with no analyzable sources renders as `[]`.

## Guarantees for the consumer

- Deterministic: identical code and configuration produce byte-identical
  output
- Read-only: the project tree is unchanged after the run
- Purely descriptive: import cycles between prospective cells appear as links
  in both directions, with no verdicts or warnings
- Names resolving outside the project (standard library, third-party) never
  appear as links and never fail the run

## Failure behavior relevant to the caller

Each condition raises an error the caller surfaces as a clean command
failure:

- an uninitialized project — no .goga/config.yml
- a configured language outside python, golang, javascript, kotlin, swift
- an unparseable source file — the error names the file
