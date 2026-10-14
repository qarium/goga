# goga codegraph

Derive the prospective cell graph from existing code.

## Synopsis

```bash
goga codegraph [CELLS]... [--max-depth N] [--depends-on CELL]...
```

## Description

`goga codegraph` reads the configured language from `.goga/config.yml` (one of `python`, `golang`, `javascript`, `kotlin`, `swift`), discovers the source files of that language below the current directory — skipping the [`lint`](../lint/cli.md) ignore list and idiomatic test files — parses each file exactly once with tree-sitter, groups the files into directory units, resolves cross-unit imports into typed cell links, and prints the resulting cell tree to stdout.

A **unit** is a directory meeting the language's package rule: `__init__.py` for python, `index.js` for javascript, any directory with sources for golang, kotlin, and swift. A unit is a **cell** when its facade — the names it exports under the language's visibility rules — is non-empty; nested cells surface under their nearest cell ancestor. Names resolving outside the project (standard library, third-party) never appear as links and never fail the run.

The command is deterministic (identical code and configuration produce byte-identical output) and read-only (the project tree is unchanged after the run). Every diagnostic goes to stderr; stdout carries the JSON document only.

## Arguments

| Argument | Required | Description                                                                         |
|----------|----------|-------------------------------------------------------------------------------------|
| `CELLS`  | no       | Zero or more cell paths to filter the output. When omitted, all cells are included. |

## Options

| Option         | Default   | Description                                                                                |
|----------------|-----------|--------------------------------------------------------------------------------------------|
| `--max-depth`  | unlimited | Maximum nesting depth for the cell tree. Roots are at depth 0; `--max-depth 0` empties every root's children. |
| `--depends-on` | (none)    | Filter cells to those that depend on the specified cell path. Repeatable.                  |

## Output

A JSON array of root cell objects, each with the following structure:

```json
[
    {
        "cell": "app",
        "children": [],
        "dependencies": {},
        "types": [
            "Service"
        ]
    },
    {
        "cell": "client",
        "children": [
            {
                "cell": "client/inner",
                "children": [],
                "dependencies": {},
                "types": [
                    "ping"
                ]
            }
        ],
        "dependencies": {
            "app": [
                "Service"
            ]
        },
        "types": [
            "Service"
        ]
    }
]
```

| Field | Description |
|---|---|
| `cell` | Path of the directory unit |
| `types` | Sorted list of the unit's facade type names — its exported names under the language's visibility rules |
| `dependencies` | Imported facade types grouped by target cell path |
| `children` | Nested child cells with the same structure (recursive) |

A node carries exactly these four fields — the [schema](../schema/cli.md) node minus the manifest-only fields (no `description`, `usages`, or `tools`; `dependencies` carry types only). A project with no analyzable sources renders as `[]`.

## Examples

Generate the full graph:

```bash
goga codegraph
```

Filter to specific cells (the matched cells plus their ancestor chain):

```bash
goga codegraph client
```

Limit nesting depth to one level below the roots:

```bash
goga codegraph --max-depth 1
```

Show only cells that depend on a given path:

```bash
goga codegraph --depends-on app
```

Combine filters:

```bash
goga codegraph client --max-depth 1 --depends-on app
```

## Known Limitations

- A JavaScript default import maps to the resolved file's named default export. The recorded export list cannot distinguish an anonymous default export from a trailing clause export, so a file exporting only clause names may map the default import to its last clause-exported public name.
- Aliased plain imports (python `import a as b`) do not expand; augmented `__all__ +=` is not read; CommonJS and bare javascript specifiers are external; GOPATH-mode Go is external.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Graph generated successfully |
| `1` | Failure: uninitialized project (no `.goga/config.yml`); a configured language outside python, golang, javascript, kotlin, swift; or an unparseable source file — the message names the file |
