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

## Ignoring directories

Declare an optional `lint` section in .goga/config.yml to exclude directories
from validation by exact relative path:

```yaml
lint:
  ignore:
    - .venv/
    - build/dist
```

Behavior:
- Matching directories are skipped during AST traversal (not loaded, no errors).
- Entries are exact paths relative to the `goga lint` invocation cwd; glob
  patterns (`**`, `*`, `?`) are NOT supported.
- When the `lint` section (or .goga/config.yml) is absent OR invalid, lint
  behavior is unchanged — the whole tree is validated; lint never fails due
  to .goga/config.yml.

```bash
goga lint                       # honors lint.ignore when present
goga lint goga/config           # path-scoped; ignore still applies
```
