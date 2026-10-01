# Schema — API

The facade of the domain package **`goga.schema`** — the JSON schema tree generation from project CODEMANIFEST files.

The signature below is the CODEMANIFEST contract of the cell.

```python
schema(cells: list[str], max_depth: int | None, depends_on: list[str]) -> str
```

Walk the project cells and emit the JSON schema tree. `cells` — the positional scope (the named cells only); `max_depth` — the bound on the nesting depth of the cell tree; `depends_on` — keep only the cells connected to the named ones. The returned string is the JSON document the `goga schema` command prints: every declared entity and routine with its signature, location, annotations, methods, and properties.

After every filter has pruned the tree, the walk delivers the [cell-amendment checkpoint](hooks.md) (`schema / amend_cell`) for every surviving cell and places the returned tools area on the node under the `tools` key — present iff at least one tool wrote at least one fact on that cell. Between the amendment walk and the serialization the routine fires the [validation gate](hooks.md) (`schema / validate_schema`) exactly once over the final assembled tree — the read-only `SchemaNode` projection of every surviving node, the committed tools overlay included; an approved verdict changes nothing, and an emptied tree returns `"[]"` before any checkpoint, the gate included. With no subscriptions — or no tool packages installed — the output is byte-identical to the six-field map.

**Raises:**

- `ValueError` — the AST has parsing errors (the count), a checkpoint hard failure stops the walk (the message names the tool, the action, and the failing cell path), or the validation gate vetoed the final tree (the message lists every violation — one line per tool and hook).
- `ImportError` — a tool-package facade fails to import (the message names the package).

The routine never prints and never returns partial JSON.

## Example

```python
from goga.schema import schema

doc = schema(cells=[], max_depth=None, depends_on=[])
print(doc)
```
