# codegraph — registering hooks

How a `goga_tool_*` package subscribes its hooks to the codegraph domain
actions. For tool package authors; no goga code changes are needed.

The domain opens two hard actions — the node amendment, a
read-and-contribute view over the code-derived facts of one node, and the
validation gate, an observe-and-veto pass over the final assembled tree.

## The events

| Address | Error class | Fires |
|---|---|---|
| `codegraph / amend_node` | hard | At the assembly moment of every entry path that derives the code graph (`goga codegraph`, the codegraph routine, and every codegraph producer call inside a drift run). One delivery per node surviving the filters — nodes in tree order, tools in enumeration order within each node. |
| `codegraph / validate_graph` | hard | Once over the final assembled tree of every entry path that derives the code graph — after assembly, filters, and the tools overlay, before serialization. The walk runs to completion; one violation per vetoing or crashing tool. |

An empty graph fires nothing.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("codegraph", "amend_node", "coverage", cover_node)
```

- `domain` — always `"codegraph"`; `action` — from the table; `name` —
  unique per tool per address; `hook` — the callable executed when the
  event fires.
- A hook receives values only for the parameters it declares by the fixed
  offered names: `context`, `self`.

## The amendment view

`amend_node` delivers a `NodeAmendment` view per tool, once per node.
The reads: `node` — the code-derived facts of the node being built
(read-only; attribute assignment is blocked): `cell` (the cell path),
`types` (the facade type names), `dependencies` (target cell path to its
imported facade types), and `children` (the nested child cell paths of
the complete code-derived tree beneath the node — identical in every run
of the same code). The view never carries another tool's contributions or
the run's filter parameters.

```python
def cover_node(context):
    if is_interesting(context.node.cell):
        context.contribute(
            {
                "coverage": measure_coverage(context.node.cell),
                "owner": owning_team(context.node.types),
            }
        )
```

- `contribute(facts)` buffers one mapping of facts for this node — fact
  names to JSON-representable values; a later contribution of your tool
  on the same node merges key-wise, a later write replacing an earlier
  one on key conflict.
- Your facts land on the node under your tool identity inside the `tools`
  wrapper area: `tools -> {<tool> -> {<fact>: <value>}}`. The identity is
  assigned by goga from the package name — a tool never names itself.

## The validation view

`validate_graph` delivers a `GraphValidation` view per tool: the
read-only final tree (`context.tree` — recursive `CodegraphNode` with
`cell`, `types`, `dependencies`, `children`, `tools`, the overlay
included) and `veto(reason)`.

```python
def validate_tree(context):
    for node in context.tree:
        if broken(node):
            context.veto(f"{node.cell}: broken shape")
            return
```

- Veto or crash = exactly one violation of your tool (tool, hook,
  reason); every subscribed tool runs — no early stop.
- On any violation: nothing on stdout, one merged error, the command
  stops before any output — exit 1 for `goga codegraph`; inside a drift
  run the drift command exits 2. Observe and veto only — the tree is
  never modified.
- With no subscriptions the output is byte-for-byte unchanged.

## The merge rules

- One JSON mapping per tool per node; multiple hooks of your tool merge
  key-wise in registration order, later writes replacing earlier ones on
  key conflict.
- Tools never collide — each namespace lives under its own identity key.
- Empty objects never appear: the `tools` key exists on a node iff at
  least one tool wrote at least one fact there; your key exists iff you
  wrote at least one fact. An empty `contribute` contributes nothing.
- Tools are mutually blind — every hook reads the same code-derived
  facts; each tool's contribution commits as a unit, in enumeration
  order, per node.

## Failure treatment

Both actions are hard. For the amendment, the first failing hook in the
delivery walk stops the command with a clean error naming the tool, the
action, and the failing node cell path — no partial output is printed. A
structurally malformed contribution — a non-mapping payload, non-string
keys, non-JSON-serializable values, or an empty mapping at any nesting
level — fails the same way. A tool package whose facade fails to import
stops the command the same way, the error naming the package.

## The run output

With no subscriptions — or no tool packages installed — `goga codegraph`
output is byte-identical to the run without the extension: no `tools` key
appears anywhere. The four base fields of every node are exactly what
they would be without the extension. Repeated runs with the same tools
reproduce the output deterministically; stdout stays data-clean JSON.

## Integration scenarios

- **Per-node fact attachment** — subscribe to `amend_node`; attach
  coverage, ownership, or any JSON facts to each node you measure through
  `context.contribute`.
- **Whole-tree policy veto** — subscribe to `validate_graph`; walk
  `context.tree` and `veto(reason)` on violation — every veto merges into
  one clean error that stops the run before any output.
- **Drift symmetry** — the same subscriptions fire inside every codegraph
  producer call of a drift run: one subscription, both entry paths.
