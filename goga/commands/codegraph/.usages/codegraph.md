# CLI Command: codegraph

## Purpose

CLI wrapper for the codegraph command. Delegates business logic to `goga/codegraph`. Derives the prospective cell graph of the existing project code — tree-sitter analysis of the configured language's sources, directory units, resolved cross-unit imports — and prints the resulting JSON tree to stdout. Output format is symmetric to `goga schema`, minus the manifest-only fields.

## Syntax

```
goga codegraph [cells...] [--max-depth N] [--depends-on PATH]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `cells` | list[str] | Paths to cells for filtering (optional; the matched cells plus their ancestor chain survive) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--max-depth` | int | None | Nesting depth limit; roots are at depth 0 |
| `--depends-on` | list[str] | None | Filter cells by dependency (repeatable) |

## Exit code

- 0 — success (the JSON document is printed to stdout)
- 1 — uninitialized project (no `.goga/config.yml`); a configured language
  outside python, golang, javascript, kotlin, swift; or an unparseable
  source file — the message names the file; nothing is printed to stdout

## Output

A JSON array of root cell objects. Each node carries exactly four fields —
the schema node minus the manifest-only fields (no `description`, `usages`,
or `tools`):

| Field | Description |
|-------|-------------|
| `cell` | Normalized path of the directory unit |
| `types` | Sorted facade type names of the unit — its exported names under the language visibility rules |
| `dependencies` | Imported facade types grouped by normalized target cell path |
| `children` | Nested child cells with the same structure (recursive) |

A project with no analyzable sources renders as `[]`.

## Examples

```bash
goga codegraph
goga codegraph goga/config goga/ast --max-depth 2
goga codegraph --depends-on goga/ast
```
