# Schema — Hooks

How a `goga_tool_*` package publishes per-cell facts onto the project map and validates the final assembled tree. For tool-package authors; no goga code changes are needed. The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).

The schema domain opens two actions — the cell amendment and the validation gate. The amendment is a read-and-contribute view over the authored facts of one cell, delivered at the generation moment of the project map, while the walk builds the node tree. The gate is an observe-and-veto pass over the final assembled tree, delivered after all contributions are merged and the filters applied, before serialization. Both are **hard** actions.

## The events

| Address | Error class | Fires |
|---|---|---|
| `schema / amend_cell` | **hard** | At the generation moment of every entry path that builds the project map (`goga schema` and the schema routine). One delivery per cell whose node survives the filters — cells in tree order, tools in enumeration order within each cell. |
| `schema / validate_schema` | **hard** | Once over the final assembled tree — after the amendment walk and the cells/`max_depth`/`depends_on` filters, before serialization. One delivery per tool; the walk runs to completion, collecting one violation per vetoing or crashing tool. |

An empty tree fires nothing: with no surviving cells the walk never builds the registry, so no tool package is even enumerated — the gate included (an emptied tree returns `[]` before any checkpoint).

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

## The validation view

`validate_schema` delivers a `SchemaValidation` view per tool, once per run: `tree` — the final assembled tree as a list of recursive `SchemaNode` records (`path`, `description`, `types`, `usages`, `dependencies` (each with `path`, `types`, `usages`), `children`, `tools`), read-only (attribute assignment is blocked; every tool reads its own fresh copy of the same assembled nodes, the committed tools overlay included — a recorded exception to the authored-facts-only delivery rule: the validator deliberately sees the final result, because that is what consumers receive).

```python
def enforce_policy(context):
    for node in context.tree:
        if violates(node):
            context.veto(f"cell {node.path}: broken")
```

- `veto(reason)` buffers your tool's single veto; a repeat call replaces the reason whole.
- Your tool's hooks all run even when another tool already vetoed — verdict collection requires every tool's outcome; the walk never stops between tools.
- A crashing hook counts as your tool's veto with the crash reason — never a raw traceback.
- The tree is never modified by a validator — the gate is observe-and-veto only; a write into the view stays local to your tool's copy and dies with it.

## Failure treatment

Both actions are hard. For the amendment, the first failing hook in the delivery walk stops the command with a clean error naming the tool, the action, and the failing cell path — no partial map is printed. A structurally malformed contribution — a non-mapping payload, non-string keys, non-JSON-serializable values (a non-dict mapping or a self-referencing container included), or an empty mapping at any nesting level — fails the same way; only JSON-representable facts are valid. A tool package whose facade fails to import (raised as `ImportError` at the registry build) stops the command the same way, the error naming the package — keep the package facade import-clean.

The gate runs like `build/validate_build`: every subscribed tool's hooks run to completion, one veto is collected per tool, and all vetoes merge into one clean error (tool, hook, reason) that stops `goga schema` before any output — exit code 1, nothing on stdout. With no subscriptions the schema is approved and the output is byte-identical.

## The run output

With no subscriptions — or no tool packages installed — `goga schema` output is byte-identical to the map without the extension: no `tools` key appears anywhere. The six base fields of every node are exactly what they would be without the extension. The map and the CODEMANIFEST files are never modified; repeated runs with the same tools reproduce the output deterministically. stdout stays data-clean JSON — every warning and diagnostic goes to stderr.

## API

The zone facade is importable as `goga.schema.hooks`:

```python
from goga.schema.hooks import (
    CellAmendment, CellFacts, DependencyFacts, GateVerdict, SchemaHooks,
    SchemaNode, SchemaValidation, ToolContribution, Violation,
    merge_cell_contributions,
)
```

`SchemaHooks().amend_cell(cell)` is the checkpoint surface the generation walk calls — once per surviving cell over one registry per run; `SchemaHooks().validate_schema(tree)` is the gate surface it calls next — once over the final assembled tree, returning the `GateVerdict` (with `Violation` records and the derived `approved` property). `CellFacts` / `DependencyFacts` are the authored facts records, `CellAmendment` the delivered view, `SchemaNode` / `SchemaValidation` the gate's read-only tree record and delivered view, `ToolContribution` / `merge_cell_contributions` the committed-contribution pairing and the deterministic tools-area composition. See [Hooks — API](../hooks/api.md) and [Schema — API](api.md).
