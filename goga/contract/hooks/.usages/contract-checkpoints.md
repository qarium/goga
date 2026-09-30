# contract — amending type nodes with tool facts

How the contract comparison uses the hooks zone of the contract domain:
delivering the contract-amendment checkpoint after the built-in
comparison and placing the contributed facts on the type nodes of the
JSON output. For every entry path that runs the contract comparison —
the CLI command.

## The checkpoint surface

One `ContractHooks` object serves the checkpoints of a run — the
surface shares one registry per run, so a command that reaches further
checkpoints enumerates the tool packages once.

```python
from goga.contract.hooks import ContractHooks

hooks = ContractHooks()
```

## Amend each compared cell

Run the built-in comparison of every requested cell first — existing
failures fire before any hook runs. Then walk the requested cells
deduplicated by normalized path, in first-request order: build the
comparison facts of each cell from your own comparison data, hand them
to the zone entry, and place each returned tools area on its type's
node — the key exists iff the mapping is non-empty.

```python
from goga.contract.hooks import CellFacts, TypeFacts, FormFacts, MemberFacts

for path in unique_normalized_paths(cells):
    facts = CellFacts(
        path=path,
        types=[
            TypeFacts(
                name=type_name,
                signature=FormFacts(codemanifest=declared, implementation=extracted),
                properties=[MemberFacts(name=n, form=FormFacts(codemanifest=d, implementation=i)) for n, d, i in props],
                methods=[MemberFacts(name=n, form=FormFacts(codemanifest=d, implementation=i)) for n, d, i in methods],
            )
            for type_name, declared, extracted, props, methods in comparison_of(path)
        ],
    )
    tools = hooks.amend_contract(cell=facts)
    for type_name, area in tools.items():
        output[path][type_name]["tools"] = area  # never an empty object
```

- The delivered view is built from the values you pass — the
  checkpoint reads no configuration, no git, no files; the facts are
  the comparison facts of the cell only, one shape for every
  implementation language.
- Tools are mutually blind: every hook reads the same comparison
  facts, never another tool's contribution; each tool's contribution
  commits as a unit, in enumeration order, per cell.
- The contribution is addressed per declared type — an address naming
  a type the cell does not declare is the hard failure of the
  delivery.
- The action is hard: the first failing hook — or a structurally
  malformed contribution (a non-mapping payload, non-string keys,
  non-serializable values, or an empty mapping at any nesting level) —
  stops the command with a clean error naming the tool, the action,
  and the failing cell path; a bad address also names the offending
  type. No partial output reaches stdout.
- A tool package whose facade fails to import stops the command the
  same way — the error names the package (raised as ImportError at
  the registry build); convert it to the same clean error, never a
  raw traceback.
- An address without subscriptions returns an empty mapping — place
  no `tools` key on any type node; with no tool packages installed the
  output is byte-identical to the comparison without the extension.
- A cell with no declared types has no landing zone: the checkpoint is
  delivered over empty facts, and any non-empty contribution for it is
  the unknown-address hard failure.
- The output and the CODEMANIFEST files are never modified — the
  contributions live in memory for the run; repeated runs with the
  same tools reproduce the output deterministically.
- stdout stays data-clean JSON; every warning and diagnostic goes to
  stderr.

## The output shape

Each addressed type node carries one wrapper key: `tools -> {tool
identity -> {fact -> value}}`, next to the fixed keys
`signature`/`properties`/`methods`. The namespace key is the platform
tool identity — the canonical hyphen form of the package name without
the `goga_tool_` prefix; a tool never names itself. Base fields and
extensions stay structurally separated; empty objects never appear at
any of the three levels. There is deliberately no cell-level landing:
a tool's cell-level context lives inside its per-type facts.
