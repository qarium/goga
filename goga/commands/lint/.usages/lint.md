# CLI Command: lint

## Purpose

Validation of CODEMANIFEST files in the project. Loads the project AST tree, applies validation rules, and outputs found errors.

## Syntax

```
goga lint [path]
```

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `path` | str | `.` | Path to the directory for validation |

## Exit code

- 0 — success (no errors)
- 1 — validation errors found

## Error output format

```
[rule_name] <message>
  --> <path>
      ---
      <yaml_data>
```

- `[rule_name]` is output in red
- `-->` — path to the file with the error
- yaml error data indented 6 spaces

## Summary

After all errors, an empty line and the summary are output:

```
goga lint
-------------------------
cells: 20 errors: 0
```

- `cells` — number of checked cells
- `errors` — number of errors found

## Examples

```bash
goga lint
goga lint goga/config
```
