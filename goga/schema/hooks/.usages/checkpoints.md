# schema — amending cells with tool facts

How the schema generation uses the hooks zone of the schema domain:
delivering the cell-amendment checkpoint at the generation moment and
placing the contributed facts on the extended nodes. For every entry
path that generates the project map — the schema routine and the CLI
command.

## The checkpoint surface

One `SchemaHooks` object serves the checkpoints of a run — the surface
shares one registry per run, so a command that reaches further
checkpoints enumerates the tool packages once.

```python
from goga.schema.hooks import SchemaHooks

hooks = SchemaHooks()
```

## Amend each cell in the walk

Build the authored facts of each cell, hand them to the zone entry,
and place the returned tools area on the node — the key exists iff the
mapping is non-empty. Deliver only the cells surviving your filters —
filters prune delivery exactly as they prune output.

```python
from goga.schema.hooks import CellFacts, DependencyFacts

for cell in walk_in_tree_order(tree):
    facts = CellFacts(
        path=cell.path,
        description=cell.description,
        types=cell.type_names,
        usages=cell.usage_names,
        dependencies=[
            DependencyFacts(path=d.path, types=d.types, usages=d.usages)
            for d in cell.dependencies
        ],
        children=cell.child_paths,
    )
    node = build_base_node(cell)          # the six base fields, unchanged
    tools = hooks.amend_cell(cell=facts)
    if tools:
        node["tools"] = tools             # never an empty object
```

- The delivered view is built from the values you pass — the
  checkpoint reads no repository, no git, no files; the facts are the
  authored facts of the cell only.
- Tools are mutually blind: every hook reads the same authored facts,
  never another tool's contribution; each tool's contribution commits
  as a unit, in enumeration order, per cell.
- The action is hard: the first failing hook — or a structurally
  malformed contribution (a non-mapping payload, non-string keys,
  non-serializable values, or an empty mapping at any nesting
  level) — stops the command
  with a clean error naming the tool, the action, and the failing cell
  path. No partial map reaches stdout.
- A tool package whose facade fails to import stops the command the
  same way — the error names the package (raised as ImportError at
  the registry build); convert it to the same clean error, never a
  raw traceback.
- An address without subscriptions returns an empty mapping — place
  no `tools` key; with no tool packages installed the output is
  byte-identical to the map without the extension.
- The map and the CODEMANIFEST files are never modified — the
  contributions live in memory for the run; repeated runs with the
  same tools reproduce the output deterministically.
- stdout stays data-clean JSON; every warning and diagnostic goes to
  stderr.

## The output shape

Extended nodes carry one wrapper key: `tools -> {tool identity ->
{fact -> value}}`. The namespace key is the platform tool identity —
the canonical hyphen form of the package name without the
`goga_tool_` prefix; a tool never names itself. Base fields and
extensions stay structurally separated; empty objects never appear at
any of the three levels.
