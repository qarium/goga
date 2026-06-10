# goga lint

Validate CODEMANIFEST files in a project.

## Synopsis

```bash
goga lint [CELL_PATH]
```

## Description

`goga lint` parses all CODEMANIFEST files found in the project tree and validates them against a comprehensive rule set. It reports any errors with the document path, rule name, message, and the offending YAML fragment.

The linter validates against **document-level rules** and **tree-level rules**, covering structural correctness, required fields, type signatures, and cross-reference integrity.

## Arguments

| Argument    | Default | Description                          |
|-------------|---------|--------------------------------------|
| `CELL_PATH` | `.`     | Path to the cell of project to lint. |

## Output

Errors are printed to stdout in the following format:

```
[RULE_NAME] Error message
  --> path/to/CODEMANIFEST
      ---
      yaml_fragment_key: value
      ...
```

After all errors, a summary is printed:

```
goga lint
-------------------------
cells: N errors: M
```

## Examples

Lint the current directory:

```bash
goga lint
```

Lint a specific project path:

```bash
goga lint /path/to/project
```

## Exit Codes

| Code | Meaning                             |
|------|-------------------------------------|
| `0`  | All CODEMANIFEST files are valid    |
| `1`  | One or more validation errors found |
