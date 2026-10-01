# Schema API — goga/schema

## Overview

The `goga.schema` module generates a JSON schema of the CODEMANIFEST project structure
as a hierarchical tree.

## Usage

```python
from goga.schema import schema

# Full project schema
json_str = schema(cells=[], max_depth=None, depends_on=[])

# Filter by specific cells
json_str = schema(cells=["goga/config", "goga/ast"], max_depth=None, depends_on=[])

# Limit nesting depth
json_str = schema(cells=[], max_depth=2, depends_on=[])

# Filter by dependencies — keep only cells whose own dependencies or
# descendant subtree contains the specified path. Ancestor cells on the
# path to a kept descendant are preserved so the parent-child skeleton
# stays intact; cells with no matching dependency are pruned.
json_str = schema(cells=[], max_depth=None, depends_on=["goga/ast"])
```

## Return Value

The `schema` routine returns a JSON string representing the project schema.
An empty tree returns `"[]"`.

## Node Structure

Each node in the tree follows this structure:

```json
{
  "cell": "goga/config",
  "description": "Cell description",
  "types": ["ProjectConfig", "load_project_config"],
  "usages": ["configuration.md"],
  "dependencies": {
    "goga/ast": {"types": ["AST"], "usages": []}
  },
  "children": [],
  "tools": {"docs": {"score": 3}}
}
```

The `tools` field is present only when at least one installed tool
contributed facts to this cell — never an empty object.

## Side Effects

- The routine reads CODEMANIFEST files from the current working directory
- The routine does not modify the file system
- The routine delivers the cell-amendment checkpoint of the hooks
  platform — a hard action: a failing tool contribution stops the
  routine with an error naming the tool, the action, and the cell
  path; no partial JSON is returned
- With no subscribed tools the output is byte-identical to the map
  without the `tools` key — the routine still does not modify the
  file system
