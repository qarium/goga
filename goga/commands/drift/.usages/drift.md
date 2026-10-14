# CLI Command: drift

## Purpose

CLI wrapper for the drift command. Delegates business logic to `goga/drift`. Compares the declared contract view (`goga schema`) with the code-derived view (`goga codegraph`) and prints the flat JSON report of their structural discrepancies to stdout. Discrepancies are computed on the complete views; the filters scope the report only.

## Syntax

```
goga drift [cells...] [--max-depth N] [--depends-on PATH]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `cells` | list[str] | Paths to cells for scoping the report (optional; a cell is reported when it survives the filters in at least one of the two filtered views) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--max-depth` | int | None | Nesting depth limit for the report scope |
| `--depends-on` | list[str] | None | Scope the report by dependency (repeatable) |

## Exit code

- 0 — comparison completed, no discrepancies (an empty JSON list is printed)
- 1 — comparison completed, discrepancies found (the full report is printed)
- 2 — the comparison could not be performed: an uninitialized project (no `.goga/config.yml`); a configured language outside python, golang, javascript, kotlin, swift; an unparseable source file (the message names the file); manifest loading and validation failures; hard failures of the schema hooks checkpoints — nothing is printed to stdout

## Output

A flat JSON array of report entries, sorted by cell path then kind:

| Field | Description |
|-------|-------------|
| `kind` | Direction — `schema_only` (exists only in the declared view) or `codegraph_only` (exists only in the code-derived view) |
| `cell` | Normalized cell path of the subject |
| `types` | Sorted type names of the cell missing from the other view; present only on type-level entries — its absence marks a cell-level discrepancy |

Healthy projects render as `[]`.

## Examples

```bash
goga drift
goga drift goga/config goga/ast --max-depth 2
goga drift --depends-on goga/ast
```

