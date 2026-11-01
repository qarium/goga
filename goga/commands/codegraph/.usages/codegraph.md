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
  outside python, golang, javascript, kotlin, swift; an unparseable
  source file — the message names the file; a hard failure of a codegraph
  hooks checkpoint — a crashed or malformed-contribution amendment hook
  (the error names the tool, the action, and the failing node cell path)
  or a vetoed validation gate (one merged error lists every violation —
  the tool, the hook, the reason); or a tool-package register-facade
  import failure (the error names the package); nothing is printed to
  stdout and no raw traceback is shown

## Output

A JSON array of root cell objects. Each node carries the four base
fields — the schema node minus the manifest-only fields (no
`description` or `usages`) — plus the conditional `tools` key, written
only when at least one tool contributed (never an empty object at any
level):

| Field | Description |
|-------|-------------|
| `cell` | Normalized path of the directory unit |
| `types` | Sorted facade type names of the unit — its exported names under the language visibility rules |
| `dependencies` | Imported facade types grouped by normalized target cell path |
| `children` | Nested child cells with the same structure (recursive) |
| `tools` | The committed per-tool facts overlay — `{tool identity -> {fact -> value}}`; present iff at least one tool contributed |

A project with no analyzable sources renders as `[]`. With no hook
subscriptions — or no tool packages installed — no `tools` key appears
anywhere and the output is byte-identical to the run without the
extension.

## Examples

```bash
goga codegraph
goga codegraph goga/config goga/ast --max-depth 2
goga codegraph --depends-on goga/ast
```
