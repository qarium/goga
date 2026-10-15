# goga drift

Report contract drift between declared manifests and actual code.

## Synopsis

```bash
goga drift [CELLS]... [--max-depth N] [--depends-on CELL]...
```

## Description

`goga drift` builds the two complete views of the project — the declared contract view of [`goga schema`](../schema/cli.md) (the CODEMANIFEST files) and the code-derived view of [`goga codegraph`](../codegraph/cli.md) (the sources) — compares them, and prints the flat JSON report of their structural discrepancies to stdout.

The comparison covers both views completely, always: every cell path present in exactly one view becomes a cell-level entry; every cell present in both views with differing facade type names becomes up to two type-level entries — one per direction. The filters scope the report only: `CELLS`, `--max-depth`, and `--depends-on` select which computed entries are printed, never which cells are compared. An entry survives iff its cell survives the filters in at least one of the two filtered views — a filter that empties one view but not the other therefore cannot fabricate a discrepancy.

The command is deterministic (identical project state and configuration produce byte-identical output) and read-only (the project tree is unchanged after the run). Every diagnostic goes to stderr; stdout carries the JSON report only.

## Arguments

| Argument | Required | Description                                                                        |
|----------|----------|------------------------------------------------------------------------------------|
| `CELLS`  | no       | Zero or more cell paths to scope the report. When omitted, every computed entry is reported. |

## Options

| Option         | Default   | Description                                                                                       |
|----------------|-----------|---------------------------------------------------------------------------------------------------|
| `--max-depth`  | unlimited | Nesting depth limit for the report scope. Roots are at depth 0; `--max-depth 0` drops every nested cell from the scope. |
| `--depends-on` | (none)    | Scope the report to cells that depend on the specified cell path. Repeatable.                     |

## Output

A flat JSON array of report entries, sorted by cell path then kind:

```json
[
    {
        "cell": "extra",
        "kind": "codegraph_only"
    },
    {
        "cell": "ghost",
        "kind": "schema_only"
    },
    {
        "cell": "mix",
        "kind": "codegraph_only",
        "types": [
            "helper2"
        ]
    },
    {
        "cell": "mix",
        "kind": "schema_only",
        "types": [
            "stale"
        ]
    }
]
```

| Field | Description |
|---|---|
| `kind` | Direction of the discrepancy — `schema_only` (declared view only) or `codegraph_only` (code-derived view only) |
| `cell` | Normalized path of the discrepancy subject |
| `types` | Sorted type names of the cell missing from the other view; present only on type-level entries — its absence marks a cell-level discrepancy |

Healthy projects render as `[]` — the command still exits `0` and prints the empty list.

## Examples

Report every discrepancy of the project:

```bash
goga drift
```

Scope the report to specific cells and a nesting bound:

```bash
goga drift goga/config goga/ast --max-depth 2
```

Scope the report by dependency:

```bash
goga drift --depends-on goga/ast
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Comparison completed, no discrepancies — `[]` on stdout |
| `1` | Comparison completed, discrepancies found — the full report on stdout |
| `2` | The comparison could not be performed: an uninitialized project (no `.goga/config.yml`); a configured language outside python, golang, javascript, kotlin, swift; an unparseable source file (the message names the file); manifest loading and validation failures; a hard failure of a declared-view hooks checkpoint — the reason on stderr, nothing on stdout |
