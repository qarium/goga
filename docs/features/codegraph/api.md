# Codegraph — API

The facade of the domain package **`goga.codegraph`** — the prospective cell graph derived from the project sources.

The signatures below are the CODEMANIFEST contracts of the cell.

```python
codegraph(cells: list[str] = [], max_depth: int | None = None, depends_on: list[str] = []) -> str

discover_sources(language: str, ignore: list[str]) -> list[Path]

render_graph(
    units: list[Unit], links: list[CellLink],
    cells: list[str], max_depth: int | None, depends_on: list[str],
) -> str
```

`codegraph` loads the project configuration, discovers the source files of the configured language, runs the three analysis stages (collect facts, derive units, resolve links), and returns the JSON document the `goga codegraph` command prints — an empty project renders as `"[]"`. `cells`, `max_depth`, and `depends_on` carry the same filter semantics as the CLI arguments (see [CLI](cli.md)).

`discover_sources` is the deterministic path-only walk behind the discovery step; `render_graph` is the tree assembly and serialization behind the render step. The analysis stages (`collect_facts`, `derive_units`, `resolve_links`) and the shared records (`Unit`, `CellLink`, `CodegraphNode`, …) live one level deeper, in the `goga.codegraph.analysis` and `goga.codegraph.facts` cells.

**Raises:**

- `FileNotFoundError` — `.goga/config.yml` is absent (the uninitialized-project error).
- `ValueError` — the configured language is outside `python`, `golang`, `javascript`, `kotlin`, `swift`, or a source file fails to parse (the message names the file).

The routine is read-only, deterministic, and idempotent — identical code and configuration produce byte-identical output; it never prints.

## Example

```python
from goga.codegraph import codegraph

doc = codegraph(cells=[], max_depth=None, depends_on=[])
print(doc)
```
