# Contract — Hooks

How a `goga_tool_*` package contributes per-type facts onto the contract comparison. For tool-package authors; no goga code changes are needed. The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).

The contract domain opens one action — the contract amendment. It is a read-and-contribute view over the comparison facts of one cell, delivered at the comparison moment of the run, right after the built-in comparison of every requested cell. It is a **hard** action. The command also passes through the config amendment checkpoint at its configuration load (see [Configuration — Hooks](../../configuration/hooks.md)).

## The events

| Address | Error class | Fires |
|---|---|---|
| `contract / amend_contract` | **hard** | At the comparison moment of every requested cell (`goga contract`). One delivery per unique normalized cell path in first-request order — a path spelled two ways in one invocation is delivered once — tools in enumeration order within each cell. |

A request with no cells fires nothing: with no cells compared the command never builds the registry, so no tool package is even enumerated.

## Subscribe

```python
def register_hooks(hooks):
    hooks.subscribe("contract", "amend_contract", "cover", cover_contract)
```

- `domain` — always `"contract"`; `action` — from the table; `name` — unique per tool per address; `hook` — the callable executed when the event fires.
- A hook receives values only for the parameters it declares by the fixed offered names: `context`, `self`.

## The amendment view

`amend_contract` delivers a `ContractAmendment` view per tool, once per cell. The reads: `cell` — the comparison facts of the cell being amended (read-only; attribute assignment is blocked): `path` (the normalized cell path) and `types` (the comparison facts of each declared type). Each `TypeFacts` carries `name`, the compared `signature`, and the compared `properties` / `methods` — empty lists for a routine; each compared form is a `FormFacts` pair — `codemanifest`, the declared string, and `implementation`, the extracted counterpart or `None` when the implementation carries none; each member is a `MemberFacts` with `name` and `form`. The view never carries another tool's contributions, and the facts are exactly the authored and extracted strings the command's output shows — identical for every tool, one shape for every implementation language.

```python
def cover_contract(context):
    if is_interesting(context.cell.path):
        context.contribute({
            "ProjectConfig": {
                "coverage": measure_coverage(context.cell.path),
            },
        })
```

- `contribute(facts)` buffers one type-addressed mapping for this cell — declared type name to the tool's fact mapping for that type; a repeated type address merges its facts, a later write replacing an earlier one on fact-name conflict.
- Your facts land on the addressed type's node under your tool identity inside the `tools` wrapper area: `tools -> {<tool> -> {<fact>: <value>}}`. The identity is assigned by goga from the package name — a tool never names itself.

## The merge rules

- One JSON mapping per tool per type address; multiple hooks of your tool merge fact-wise in registration order, later writes replacing earlier ones on fact-name conflict.
- Tools never collide — each namespace lives under its own identity key; the comparison fields and extensions stay structurally separated.
- Empty objects never appear: the `tools` key exists on a type node iff at least one tool wrote at least one fact for that type; your key exists iff you wrote at least one fact. An empty `contribute` contributes nothing.
- Tools are mutually blind — every hook reads the same comparison facts; each tool's contribution commits as a unit, in enumeration order, per cell.

## Failure treatment

The action is hard. The first failing hook in the delivery walk stops the command with a clean error naming the hook, the tool, the action, and the failing cell path — no partial JSON is printed. A structurally malformed contribution — a non-mapping payload, non-string keys, non-JSON-serializable values (a non-dict mapping or a self-referencing container included), or an empty mapping at any nesting level — fails the same way; only JSON-representable facts are valid. A contribution addressed to a type the cell does not declare fails the same way, the error naming the offending type. A tool package whose facade fails to import (raised as `ImportError` at the registry build) stops the command the same way, the error naming the package — keep the package facade import-clean.

## The run output

With no subscriptions — or no tool packages installed — `goga contract` output is byte-identical to the comparison without the extension: no `tools` key appears anywhere. The comparison fields of every type node are exactly what they would be without the extension. The output is composed fresh from the command's own comparison; repeated runs with the same tools reproduce the output deterministically. stdout stays data-clean JSON — every warning and diagnostic goes to stderr.

## API

The zone facade is importable as `goga.contract.hooks`:

```python
from goga.contract.hooks import (
    CellFacts, ContractAmendment, ContractHooks, FormFacts,
    MemberFacts, ToolContribution, TypeFacts, merge_type_contributions,
)
```

`ContractHooks().amend_contract(cell)` is the checkpoint surface the command calls — once per unique cell path over one registry per run; `CellFacts` / `TypeFacts` / `FormFacts` / `MemberFacts` are the comparison facts records, `ContractAmendment` the delivered view, `ToolContribution` / `merge_type_contributions` the committed-contribution pairing and the deterministic tools-area composition. See [Hooks — API](../hooks/api.md) and [Contract — API](api.md).
