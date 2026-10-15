# Codegraph — API

The facade of the domain package **`goga.codegraph`** — the prospective cell graph derived from the project sources.

The signatures below are the CODEMANIFEST contracts of the cell.

```python
codegraph(cells: list[str] = [], max_depth: int | None = None, depends_on: list[str] = []) -> list[CodegraphNode]

discover_sources(language: str, ignore: list[str]) -> list[Path]

render_graph(
    units: list[Unit], links: list[CellLink],
    cells: list[str], max_depth: int | None, depends_on: list[str],
) -> list[CodegraphNode]
```

`codegraph` loads the project configuration, discovers the source files of the configured language, runs the three analysis stages (collect facts, derive units, resolve links), and returns the code-derived tree of `CodegraphNode` records (from `goga.codegraph.facts`) — an empty project yields `[]`. The assembly is observed and amended by the installed tool packages before it is returned: every node surviving the filters passes the [node-amendment checkpoint](hooks.md), the committed overlays are placed on their nodes, and the final tree passes the [validation gate](hooks.md) — with no tool packages installed every `tools` area is empty and the tree is value-identical to the run without the extension. The caller owns the serialization: the `goga codegraph` command maps the tree onto the family JSON document (see [CLI](cli.md)). `cells`, `max_depth`, and `depends_on` carry the same filter semantics as the CLI arguments (see [CLI](cli.md)) — filters prune the checkpoint delivery exactly as they prune the output.

`discover_sources` is the deterministic path-only walk behind the discovery step; `render_graph` is the tree assembly behind the render step. The analysis stages (`collect_facts`, `derive_units`, `resolve_links`) and the shared records (`Unit`, `CellLink`, `CodegraphNode`, …) live one level deeper, in the `goga.codegraph.analysis` and `goga.codegraph.facts` cells.

**Raises:**

- `FileNotFoundError` — `.goga/config.yml` is absent (the uninitialized-project error).
- `ValueError` — the configured language is outside `python`, `golang`, `javascript`, `kotlin`, `swift`; a source file fails to parse (the message names the file); a [hooks checkpoint](hooks.md) hard-fails — a crashed hook or a structurally malformed contribution, the message naming the tool, the action, and the failing node cell path; or the [validation gate](hooks.md) vetoed the final tree — the message lists every violation, one line per tool and hook.
- `ImportError` — a tool-package facade failed to import (the message names the package).

The routine is read-only, deterministic, and idempotent — identical code and configuration produce identical trees; it never prints.

## Example

```python
from goga.codegraph import codegraph

tree = codegraph(cells=[], max_depth=None, depends_on=[])
for node in tree:
    print(node.cell, node.types)
```
