# Codegraph

Derive the prospective cell graph from existing code.

The codegraph domain reconstructs a cell tree from the sources instead of the manifests. Which tasks it solves:

- **Derive the graph** — `goga codegraph` parses the project's source files with tree-sitter (python, golang, javascript, kotlin, swift), groups them into directory units, resolves cross-unit imports, and prints the resulting cell tree as a JSON document.
- **Scope the graph** — positional cells limit the output to the named cells; `--max-depth N` bounds the nesting; `--depends-on CELL` keeps only the cells that import from the given one.
- **Bootstrap manifests** — the JSON output is the machine-readable projection of what the code already declares: drafting CODEMANIFEST files, drift checks, and viewers consume it instead of re-parsing the sources.

## In this directory

- [CLI](cli.md) — the full `goga codegraph` command reference
- [Configuration](configuration.md) — the `language` field and the reused `lint.ignore` exclusion list
- [Hooks](hooks.md) — the two checkpoints: the node amendment `amend_node` and the validation gate `validate_graph`, both hard, firing wherever the codegraph routine runs (inside every drift run's producer calls too)
- [API](api.md) — the `goga.codegraph` facade
