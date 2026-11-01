# codegraph — amending nodes with tool facts

How the codegraph analysis uses the hooks zone of the codegraph domain:
delivering the node-amendment checkpoint at the assembly moment and the
tree validation gate over the final tree. For every entry path that
derives the code graph — the codegraph routine, the drift comparison's
producer calls, and the CLI command.

## The checkpoint surface

One `CodegraphHooks` object serves the checkpoints of a run — the surface
shares one registry per run, so a run that reaches both checkpoints
enumerates the tool packages once.

```python
from goga.codegraph.hooks import CodegraphHooks

hooks = CodegraphHooks()
```

## Amend each surviving node

Build the code-derived facts of each node surviving the filters, hand them
to the zone entry, and place the returned tools area on the node — the key
exists iff the mapping is non-empty. Deliver only the nodes surviving the
filters — filters prune delivery exactly as they prune output.

```python
from goga.codegraph.hooks import NodeFacts

# complete: cell path -> node of the unfiltered code-derived tree
for node in walk_in_tree_order(tree):
    full = complete[node.cell]
    facts = NodeFacts(
        cell=node.cell,
        types=node.types,
        dependencies=node.dependencies,
        children=[child.cell for child in full.children],
    )
    tools = hooks.amend_node(node=facts)
    if tools:
        node = node_with_tools(node, tools)  # never an empty object
```

- The delivered view is built from the values you pass — the checkpoint
  reads no repository, no git, no files; the facts are the code-derived
  facts of the node only.
- The delivered facts come from the complete code-derived tree — a
  node's child list is its full code-derived subtree and may name cells
  pruned from the current output; the filters decide which nodes are
  delivered, never the facts a delivered node carries.
- Tools are mutually blind: every hook reads the same code-derived facts,
  never another tool's contribution; each tool's contribution commits as a
  unit, in enumeration order, per node.
- The action is hard: the first failing hook — or a structurally malformed
  contribution (a non-mapping payload, non-string keys, non-serializable
  values, or an empty mapping at any nesting level) — stops the command
  with a clean error naming the tool, the action, and the failing node cell
  path. No partial tree is returned.
- A tool package whose facade fails to import stops the command the same
  way — the error names the package; convert it to the same clean error,
  never a raw traceback.
- An address without subscriptions returns an empty mapping — place no
  `tools` key; with no tool packages installed the output is byte-identical
  to the run without the extension.
- The source files are never modified — the contributions live in memory
  for the run; repeated runs with the same tools reproduce the output
  deterministically.

## Validate the final tree

Assemble the final tree — every surviving node with its committed tools
overlay — and deliver the gate before returning the tree.

```python
from goga.codegraph.hooks import CodegraphHooks

hooks = CodegraphHooks()
verdict = hooks.validate_graph(final_tree)
if not verdict.approved:
    raise merge_veto_error(verdict.violations)
```

- The walk runs to completion: every subscribed tool's hooks run, one
  violation per vetoing or crashing tool (tool, hook, reason).
- The delivered tree is the final result, tools overlay included; a
  validator observes and vetoes — never modifies.
- An empty tree fires nothing — return before any checkpoint.
- No subscriptions (or no tool packages installed) → approved; the output
  stays byte-identical.

## The output shape

Amended nodes carry one wrapper key: `tools -> {tool identity ->
{fact -> value}}`. The namespace key is the platform tool identity — the
canonical hyphen form of the package name without the `goga_tool_`
prefix; a tool never names itself. Base fields and extensions stay
structurally separated; empty objects never appear at any of the three
levels.
