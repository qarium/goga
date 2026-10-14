# Schema API — goga/schema

## Overview

The `goga.schema` module generates the schema tree of the CODEMANIFEST project
structure as a hierarchical tree of `SchemaNode` objects.

## Usage

```python
from goga.schema import schema

# Full project schema
tree = schema(cells=[], max_depth=None, depends_on=[])

# Filter by specific cells
tree = schema(cells=["goga/config", "goga/ast"], max_depth=None, depends_on=[])

# Limit nesting depth
tree = schema(cells=[], max_depth=2, depends_on=[])

# Filter by dependencies — keep only cells whose own dependencies or
# descendant subtree contains the specified path. Ancestor cells on the
# path to a kept descendant are preserved so the parent-child skeleton
# stays intact; cells with no matching dependency are pruned.
tree = schema(cells=[], max_depth=None, depends_on=["goga/ast"])
```

## Return Value

The `schema` routine returns a list of root `SchemaNode` objects — the
assembled schema tree. An empty tree returns `[]`.

Each node carries:

| Field | Description |
|-------|-------------|
| `path` | Normalized cell path |
| `description` | Footer description of the cell manifest |
| `types` | Entity and routine names of the cell body |
| `usages` | Usages file names of the cell |
| `dependencies` | Imports grouped per source path |
| `children` | Nested child nodes |
| `tools` | Committed tools overlay; empty when no tool contributed |

The caller owns the serialization of the returned tree. For the family
JSON output format, map each node to the keys `cell` (from `path`),
`description`, `types`, `usages`, `dependencies`, `children`, and
`tools`; group each node's `DependencyFacts` records into the
dependencies map — the record `path` as the key, the nested `types`
and `usages` lists as the value; the `tools` key is written only when
the overlay is non-empty — and serialize the whole tree with
`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.

## Side Effects

- The routine reads CODEMANIFEST files from the current working directory
- The routine does not modify the file system
- The routine delivers the cell-amendment checkpoint of the hooks
  platform — a hard action: a failing tool contribution stops the
  routine with an error naming the tool, the action, and the cell
  path; no partial tree is returned
- With no subscribed tools every node's tools area is empty — the
  routine still does not modify the file system

