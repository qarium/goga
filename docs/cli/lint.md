# goga lint

Validate CODEMANIFEST files in a project.

## Synopsis

```bash
goga lint [PATH]
```

## Description

`goga lint` parses all CODEMANIFEST files found in the project tree and validates them against a comprehensive rule set. It reports any errors with the document path, rule name, message, and the offending YAML fragment.

The linter validates against **document-level rules** and **tree-level rules**, covering structural correctness, required fields, type signatures, and cross-reference integrity.

## Ignoring directories

`goga lint` reads an optional `lint.ignore` list from `.goga/config.yml` and prunes matching directories (and everything beneath them) from traversal before validation:

```yaml
lint:
  ignore:
    - .venv/
    - build/dist
```

A directory is pruned when its exact normalized relative path matches an `ignore` entry. Matching is literal — glob patterns are **not** interpreted, and a trailing separator is insignificant (`.venv/` and `.venv` are equivalent). Only full relative paths match: `ignore: [.venv]` prunes a top-level `.venv` but not a nested `a/b/.venv`. The `lint` section is optional; when it is absent or the config cannot be loaded, lint behavior is unchanged (every directory is linted). See [Configuration](../configuration/index.md#lint).

## Arguments

| Argument    | Default | Description                          |
|-------------|---------|--------------------------------------|
| `PATH`      | `.`     | Path to the directory to lint (lint changes into it before validating). |

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
