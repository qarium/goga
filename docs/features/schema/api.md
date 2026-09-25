# Schema — API

The facade of the domain package **`goga.schema`** — the JSON schema tree generation from project CODEMANIFEST files.

The signature below is the CODEMANIFEST contract of the cell.

```python
schema(cells: list[str], max_depth: int | None, depends_on: list[str]) -> str
```

Walk the project cells and emit the JSON schema tree. `cells` — the positional scope (the named cells only); `max_depth` — the bound on the import expansion depth; `depends_on` — keep only the cells connected to the named ones. The returned string is the JSON document the `goga schema` command prints: every declared entity and routine with its signature, location, annotations, methods, and properties.

After every filter has pruned the tree, the walk delivers the [cell-amendment checkpoint](hooks.md) (`schema / amend_cell`) for every surviving cell and places the returned tools area on the node under the `tools` key — present iff at least one tool wrote at least one fact on that cell. With no subscriptions — or no tool packages installed — the output is byte-identical to the six-field map.

**Raises:**

- `ValueError` — the AST has parsing errors (the count), or a checkpoint hard failure stops the walk (the message names the tool, the action, and the failing cell path).
- `ImportError` — a tool-package facade fails to import (the message names the package).

The routine never prints and never returns partial JSON.

## Example

```python
from goga.schema import schema

doc = schema(cells=[], max_depth=None, depends_on=[])
print(doc)
```
