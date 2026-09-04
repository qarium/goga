# Schema — API

The facade of the domain package **`goga.schema`** — the JSON schema tree generation from project CODEMANIFEST files.

The signature below is the CODEMANIFEST contract of the cell.

```python
schema(cells: list[str], max_depth: int | None, depends_on: list[str]) -> str
```

Walk the project cells and emit the JSON schema tree. `cells` — the positional scope (the named cells only); `max_depth` — the bound on the import expansion depth; `depends_on` — keep only the cells connected to the named ones. The returned string is the JSON document the `goga schema` command prints: every declared entity and routine with its signature, location, annotations, methods, and properties.

## Example

```python
from goga.schema import schema

doc = schema(cells=[], max_depth=None, depends_on=[])
print(doc)
```
