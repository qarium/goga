# Facts Records — the data vocabulary of the code analysis

Domain: the immutable records produced and consumed by the codegraph analysis
pipeline. Target audience: implementers and consumers of the analysis stages —
every stage reads and writes exactly these records.

## Composition of the analysis flow

The records form one linear flow; each stage consumes the previous output:

    source files
      └─> FileFacts (path, declarations, imports, exports, module)
            ├─> Unit (path, files, facade, is_cell)
            └─> CellLink (source, target, types)
                  └─> CodegraphNode (cell, types, dependencies, children, tools)

Declaration and ImportRef never travel alone — they are nested inside
FileFacts.

## Import

All records are importable from the cell facade:

```python
from goga.codegraph.facts import (
    CellLink,
    CodegraphNode,
    Declaration,
    FileFacts,
    ImportRef,
    Unit,
)
```

## Constructing file facts

One parsed source file contributes declarations and imports:

```python
from pathlib import Path

from goga.codegraph.facts import Declaration, FileFacts, ImportRef

render = Path("goga/codegraph/render.py")

facts = FileFacts(
    path=render,
    declarations=[
        Declaration(path=render, name="render_graph", is_public=True),
    ],
    imports=[
        ImportRef(
            source=render,
            specifier="goga.codegraph.facts",
            names=["CellLink", "CodegraphNode", "Unit"],
            is_relative=False,
            is_wildcard=False,
        ),
    ],
    exports=[],  # empty when the file declares no explicit export list
    module="",  # empty when the language declares no package/module
)
```

Preconditions:

- paths are relative to the project root
- `is_public` is decided by the language visibility rules before construction
- a wildcard import carries no `names`; a Python plain import carries no
  `names`; a JavaScript default import carries the literal name `default`;
  a pure name usage (Swift) carries an empty `specifier`
- a wildcard, plain, or namespace import is accompanied by one usage
  `ImportRef`: the same `specifier` and flags as the base import, `names` =
  the member names accessed through the import's local binding; a wildcard
  or plain usage ref collects every used identifier of the file (generous
  collection — resolution filters by the facade); an aliased plain import
  records the base ref only, with no usage ref — a known v1 limitation

## Deriving units

Group file facts into units; the facade comes from the language facade rules:

```python
from goga.codegraph.facts import Unit

unit = Unit(
    path=Path("goga/codegraph/facts"),
    files=[Path("goga/codegraph/facts/facts.py")],
    facade=["CellLink", "CodegraphNode", "Declaration", "FileFacts", "ImportRef", "Unit"],
    is_cell=True,
)
```

A unit with an empty facade is not a cell: construct it with `is_cell=False` —
it survives only as a structural ancestor of nested cells.

## Composing links and output nodes

Resolution yields one link per unit pair; the renderer folds links into node
dependencies:

```python
from goga.codegraph.facts import CellLink, CodegraphNode

link = CellLink(
    source=Path("goga/codegraph"),
    target=Path("goga/codegraph/facts"),
    types=["CellLink", "CodegraphNode", "FileFacts", "Unit"],
)

node = CodegraphNode(
    cell="goga/codegraph",
    types=["codegraph", "discover_sources", "render_graph"],
    dependencies={
        "goga/codegraph/facts": ["CellLink", "CodegraphNode", "FileFacts", "Unit"],
    },
    children=[],
    # tools omitted — the empty default; the codegraph amendment
    # checkpoint alone places non-empty overlays
)
```

Constraints relevant to the consumer:

- `facade` and link `types` are sorted and duplicate-free; `dependencies`
  values carry sorted type lists
- all records are immutable — build new records instead of mutating
- `CodegraphNode` never carries manifest-only fields (description, usages)
  — they exist only in CODEMANIFEST
- `CodegraphNode.tools` is the committed per-tool facts overlay — empty
  unless the codegraph hooks amendment checkpoint placed it; the analysis
  flow never populates it
