# goga schema

Generate a JSON schema tree from project CODEMANIFEST files.

## Synopsis

```bash
goga schema [CELLS]... [--max-depth N] [--depends-on PATH]...
```

## Description

`goga schema` walks the current directory tree, discovers all CODEMANIFEST files, and builds a hierarchical JSON structure representing the project cell tree. Each cell entry includes its path, description, types, usages, dependencies, and nested children.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `CELLS` | no | Zero or more cell paths to filter the output. When omitted, all cells are included. |

## Options

| Option | Default | Description |
|---|---|---|
| `--max-depth` | unlimited | Maximum nesting depth for the cell tree. |
| `--depends-on` | (none) | Filter cells to those that depend on the specified cell path. Repeatable. |

## Output

A JSON array of root cell objects, each with the following structure:

```json
[
    {
        "cell": "path/to/cell",
        "children": [
            {
                "cell": "path/to/cell/child",
                "children": [],
                "dependencies": {
                    "path/to/dep": {
                        "types": ["DepType"],
                        "usages": ["DepUsage"]
                    }
                },
                "description": "Cell description text",
                "types": ["EntityA", "RoutineB"],
                "usages": ["usage_file.md"]
            }
        ],
        "dependencies": {},
        "description": "Root cell description",
        "types": ["RootEntity"],
        "usages": []
    }
]
```

| Field | Description |
|---|---|
| `cell` | Normalized path to the CODEMANIFEST folder |
| `description` | Text from the footer Description section |
| `types` | Sorted list of entity and routine names from the body |
| `usages` | List of `.md` filenames found in `<path>/.usages/` |
| `dependencies` | Imports grouped by normalized `from_path`, each with `types` and `usages` lists |
| `children` | Nested child cells with the same structure (recursive) |

## Examples

Generate the full schema:

```bash
goga schema
```

Filter to specific cells:

```bash
goga schema src/core src/api
```

Limit nesting depth to 2 levels:

```bash
goga schema --max-depth 2
```

Show only cells that depend on a given path:

```bash
goga schema --depends-on src/core/types
```

Combine filters:

```bash
goga schema src/api --max-depth 1 --depends-on src/core/types
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Schema generated successfully |
| `1` | AST parsing errors found |
