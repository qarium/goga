# Schema — Hooks

How a `goga_tool_*` package publishes per-cell facts onto the project map. For tool-package authors; no goga code changes are needed. The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).

The schema domain opens one action — the cell amendment. It is a read-and-contribute view over the authored facts of one cell, delivered at the generation moment of the project map, while the walk builds the node tree. It is a **hard** action.

## The events

| Address | Error class | Fires |
|---|---|---|
| `schema / amend_cell` | **hard** | At the generation moment of every entry path that builds the project map (`goga schema` and the schema routine). One delivery per cell whose node survives the filters — cells in tree order, tools in enumeration order within each cell. |

An empty tree fires nothing: with no surviving cells the walk never builds the registry, so no tool package is even enumerated.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("schema", "amend_cell", "coverage", cover_cell)
```

- `domain` — always `"schema"`; `action` — from the table; `name` — unique per tool per address; `hook` — the callable executed when the event fires.
- A hook receives values only for the parameters it declares by the fixed offered names: `context`, `self`.

## The amendment view

`amend_cell` delivers a `CellAmendment` view per tool, once per cell. The reads: `cell` — the authored facts of the cell being built (read-only; attribute assignment is blocked): `path`, `description`, `types` (the entity and routine names), `usages` (the usages file names), `dependencies` (each with `path`, `types`, `usages`), and `children` (the authored children paths of the document tree). The view never carries another tool's contributions, generated data, or the run's filter parameters.

```python
def cover_cell(context):
    if is_interesting(context.cell.path):
        context.contribute({
            "coverage": measure_coverage(context.cell.path),
            "owner": owning_team(context.cell.types),
        })
```

- `contribute(facts)` buffers one mapping of facts for this cell — fact names to JSON-representable values; a later contribution of your tool on the same cell merges key-wise, a later write replacing an earlier one on key conflict.
- Your facts land on the cell node under your tool identity inside the `tools` wrapper area: `tools -> {<tool> -> {<fact>: <value>}}`. The identity is assigned by goga from the package name — a tool never names itself.

## The merge rules

- One JSON mapping per tool per cell; multiple hooks of your tool merge key-wise in registration order, later writes replacing earlier ones on key conflict.
- Tools never collide — each namespace lives under its own identity key; base fields and extensions stay structurally separated.
- Empty objects never appear: the `tools` key exists on a node iff at least one tool wrote at least one fact; your key exists iff you wrote at least one fact. An empty `contribute` contributes nothing.
- Tools are mutually blind — every hook reads the same authored facts; each tool's contribution commits as a unit, in enumeration order, per cell.

## Failure treatment

The action is hard. The first failing hook in the delivery walk stops the command with a clean error naming the tool, the action, and the failing cell path — no partial map is printed. A structurally malformed contribution — a non-mapping payload, non-string keys, non-JSON-serializable values (a non-dict mapping or a self-referencing container included), or an empty mapping at any nesting level — fails the same way; only JSON-representable facts are valid. A tool package whose facade fails to import (raised as `ImportError` at the registry build) stops the command the same way, the error naming the package — keep the package facade import-clean.

## The run output

With no subscriptions — or no tool packages installed — `goga schema` output is byte-identical to the map without the extension: no `tools` key appears anywhere. The six base fields of every node are exactly what they would be without the extension. The map and the CODEMANIFEST files are never modified; repeated runs with the same tools reproduce the output deterministically. stdout stays data-clean JSON — every warning and diagnostic goes to stderr.

## API

The zone facade is importable as `goga.schema.hooks`:

```python
from goga.schema.hooks import (
    CellAmendment, CellFacts, DependencyFacts, SchemaHooks,
    ToolContribution, merge_cell_contributions,
)
```

`SchemaHooks().amend_cell(cell)` is the checkpoint surface the generation walk calls — once per surviving cell over one registry per run; `CellFacts` / `DependencyFacts` are the authored facts records, `CellAmendment` the delivered view, `ToolContribution` / `merge_cell_contributions` the committed-contribution pairing and the deterministic tools-area composition. See [Hooks — API](../hooks/api.md) and [Schema — API](api.md).
