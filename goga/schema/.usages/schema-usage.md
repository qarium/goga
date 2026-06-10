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

# Filter by dependencies
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
  "types": ["Config", "load_config"],
  "usages": ["configuration.md"],
  "dependencies": {
    "goga/ast": {"types": ["AST"], "usages": []}
  },
  "children": []
}
```

## Side Effects

- The routine reads CODEMANIFEST files from the current working directory
- The routine does not modify the file system
