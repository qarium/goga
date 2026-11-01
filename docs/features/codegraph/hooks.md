# Codegraph — Hooks

How a `goga_tool_*` package publishes per-node facts onto the code graph and validates the final assembled tree. For tool-package authors; no goga code changes are needed. The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md); the registration contract for tool authors in [Hooks — The registration contract](../hooks/hooks.md).

The codegraph domain opens two actions — the node amendment and the validation gate. The amendment is a read-and-contribute view over the code-derived facts of one node, delivered at the assembly moment of the graph, while the walk builds the node tree. The gate is an observe-and-veto pass over the final assembled tree, delivered after all contributions are merged onto their nodes, before serialization. Both are **hard** actions. The same subscriptions fire inside every codegraph producer call of a drift run — one subscription, both entry paths.

## The events

| Address | Error class | Fires |
|---|---|---|
| `codegraph / amend_node` | **hard** | At the assembly moment of every entry path that derives the code graph (`goga codegraph`, the codegraph routine, and every codegraph producer call inside a drift run). One delivery per node surviving the filters — nodes in tree order, tools in enumeration order within each node. |
| `codegraph / validate_graph` | **hard** | Once over the final assembled tree of every entry path that derives the code graph — after assembly, filters, and the tools overlay, before serialization. One delivery per tool; the walk runs to completion, collecting one violation per vetoing or crashing tool. |

An empty graph fires nothing: an emptied tree returns `[]` before any checkpoint, so no tool package is even enumerated — the gate included.

## The contexts

### `amend_node` — `NodeAmendment` (hard)

One fresh view per tool, once per node — the list fields are rebuilt per view, so an in-place append stays local.

| Read | Type | Meaning |
|---|---|---|
| `node` | `NodeFacts` | The code-derived facts of the node being built — `cell` (the cell path), `types` (the facade type names), `dependencies` (target cell path to its imported facade types), `children` (the nested child cell paths of the complete code-derived subtree beneath the node). Read-only; attribute assignment is blocked. |

| Method | Effect |
|---|---|
| `contribute(facts)` | Buffers one mapping of node facts; merged key-wise, later-wins. The payload must be a plain JSON mapping — string keys, JSON scalars / lists / mappings, finite floats. |

```python
def cover_node(context):
    if is_interesting(context.node.cell):
        context.contribute({
            "coverage": measure_coverage(context.node.cell),
            "owner": owning_team(context.node.types),
        })
```

The view never carries another tool's contributions or the run's filter parameters. Your facts land on the node under your tool identity inside the `tools` wrapper area: `tools -> {<tool> -> {<fact>: <value>}}`. The identity is assigned by goga from the package name — a tool never names itself.

### `validate_graph` — `GraphValidation` (hard)

One fresh view per tool, once per run.

| Read | Type | Meaning |
|---|---|---|
| `tree` | `list[CodegraphNode]` | The final assembled tree with the committed tools overlay included. Read-only; attribute assignment is blocked. |

| Method | Effect |
|---|---|
| `veto(reason)` | Buffers your tool's single veto; a repeat call replaces the reason whole. |

```python
def validate_tree(context):
    for node in context.tree:
        if broken(node):
            context.veto(f"{node.cell}: broken shape")
            return
```

Every tool reads its own fresh copy of the same assembled nodes — the validator deliberately sees the final result, because that is what consumers receive. Your tool's hooks all run even when another tool already vetoed — verdict collection requires every tool's outcome; the walk never stops between tools. A crashing hook counts as your tool's veto with the crash reason — never a raw traceback. The tree is never modified by a validator — the gate is observe-and-veto only; a write into the view stays local to your tool's copy and dies with it.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("codegraph", "amend_node", "coverage", cover_node)
```

- `domain` — always `"codegraph"`; `action` — from the table; `name` — unique per tool per address; `hook` — the callable executed when the event fires.
- A hook receives values only for the parameters it declares by the fixed offered names: `context`, `self`.

## The merge rules

- One JSON mapping per tool per node; multiple hooks of your tool merge key-wise in registration order, later writes replacing earlier ones on key conflict.
- Tools never collide — each namespace lives under its own identity key; base fields and extensions stay structurally separated.
- Empty objects never appear: the `tools` key exists on a node iff at least one tool wrote at least one fact there; your key exists iff you wrote at least one fact. An empty `contribute` contributes nothing.
- Tools are mutually blind — every hook reads the same code-derived facts; each tool's contribution commits as a unit, in enumeration order, per node.

## Integration scenarios

- **Per-node fact attachment** — subscribe to `amend_node`; attach coverage, ownership, or any JSON facts to each node you measure through `context.contribute`; the facts land on the node under your tool identity.
- **Whole-tree policy veto** — subscribe to `validate_graph`; walk `context.tree` and `veto(reason)` on violation — every veto merges into one clean error that stops the run before any output.
- **Drift symmetry** — the same subscriptions fire inside every codegraph producer call of a drift run: one subscription, both entry paths.

## Failure treatment

Both actions are hard. For the amendment, the first failing hook in the delivery walk stops the command with a clean error naming the tool, the action, and the failing node cell path — no partial output is printed. A structurally malformed contribution — a non-mapping payload, non-string keys, non-JSON-serializable values, or an empty mapping at any nesting level — fails the same way; only JSON-representable facts are valid. A tool package whose facade fails to import (raised as `ImportError` at the registry build) stops the command the same way, the error naming the package — keep the package facade import-clean.

The gate runs like `build/validate_build` and `schema/validate_schema`: every subscribed tool's hooks run to completion, one veto is collected per tool, and all vetoes merge into one clean error (tool, hook, reason) that stops the command before any output — exit code 1 for `goga codegraph`; inside a drift run the drift command exits 2. With no subscriptions the graph is approved and the output is byte-identical.

## The run output

With no subscriptions — or no tool packages installed — `goga codegraph` output is byte-identical to the run without the extension: no `tools` key appears anywhere. The four base fields of every node are exactly what they would be without the extension. Repeated runs with the same tools reproduce the output deterministically; stdout stays data-clean JSON — every warning and diagnostic goes to stderr.

## API

The zone facade is importable as `goga.codegraph.hooks`:

```python
from goga.codegraph.hooks import (
    CodegraphHooks, GateVerdict, GraphValidation, NodeAmendment, NodeFacts,
    ToolContribution, Violation, merge_node_contributions,
)
```

`CodegraphHooks().amend_node(node)` is the checkpoint surface the assembly walk calls — once per surviving node over one registry per run; `CodegraphHooks().validate_graph(tree)` is the gate surface it calls next — once over the final assembled tree, returning the `GateVerdict` (with `Violation` records and the derived `approved` property). `NodeFacts` is the code-derived facts record, `NodeAmendment` the delivered view, `GraphValidation` the gate's delivered view, `ToolContribution` / `merge_node_contributions` the committed-contribution pairing and the deterministic tools-area composition. See [Hooks — API](../hooks/api.md) and [Codegraph — API](api.md).

## The fact records

| Record | Fields |
|---|---|
| `NodeFacts` | `cell` (the cell path), `types: list[str]` (the facade type names), `dependencies: dict[str, list[str]]` (target cell path to its imported facade types), `children: list[str]` (the nested child cell paths of the complete code-derived subtree). |
| `Violation` | `tool`, `hook`, `reason` — one collected violation of the gate. |
| `GateVerdict` | `violations: list[Violation]` plus the derived `approved` property — `True` iff no tool vetoed or crashed. |
