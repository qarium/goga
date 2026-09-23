# Design Document: `add-hooks-to-schema`

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST`: `declared_actions` Requirements gains one
  additive record bullet — `domain="schema"`, `name="amend_cell"`,
  `error_class="hard"` (appended after the config record, domain-addition
  order). No entity, algorithm, or constraint text changes.
- `goga/schema/hooks/CODEMANIFEST` (created): the hooks zone of the schema
  domain — six types (`CellFacts`, `DependencyFacts`, `CellAmendment`,
  `ToolContribution`, `merge_cell_contributions`, `SchemaHooks`) over the
  `goga/hooks` facade.
- `goga/schema/CODEMANIFEST`: second Imports entry (`SchemaHooks`, `CellFacts`,
  `DependencyFacts` + usage `checkpoints` from `goga/schema/hooks`); Usages key
  `conventions` → `convention` (base-config spelling); rewritten global
  Annotations; the `schema` routine annotation extended — checkpoint delivery
  steps 4–5 in the algorithm, the `tools` node field, nine new requirements,
  one constraint.
- `goga/commands/schema/CODEMANIFEST`: second Imports entry (usage
  `checkpoints` from `goga/schema/hooks`); Usages key `conventions` →
  `convention`; rewritten global Annotations; the CLI `schema` annotation
  broadened — algorithm step 2 now converts **any** error of `schema_logic`
  to stderr + exit 1, plus two requirements.

### New Entities

- `CellFacts` — the per-cell authored-facts read view; `facts.py`
- `DependencyFacts` — the imported facts of one dependency; `facts.py`
- `CellAmendment` — the per-tool read-and-contribute view (`cell` property +
  `contribute(facts)` method); `amendments.py`
- `ToolContribution` — one committed tool contribution; `overlay.py`
- `merge_cell_contributions` — the deterministic tools-area composition;
  `overlay.py`
- `SchemaHooks` — the checkpoint surface (`amend_cell(cell)` method);
  `events.py`

### Changed Entities

- `schema` (`goga/schema`) — the generation walk now delivers the
  cell-amendment checkpoint for every surviving cell and places the returned
  tools area on the node.
- `schema` (`goga/commands/schema`) — the CLI converts every `schema_logic`
  error (AST errors, checkpoint hard failures, register-facade import
  failures) into a clean command failure.

### Deleted Entities

- None.

### Usages and Annotations Changes

- `goga/schema/hooks` header: `convention` (file), imported `per-tool-delivery`
  and `registering-hooks` from `goga/hooks` — all referenced in global and
  member annotations.
- `goga/schema` header: `convention` key rename; imported usage `checkpoints`;
  the routine annotation references `checkpoints`, `SchemaHooks`, `CellFacts`,
  `DependencyFacts`.
- `goga/commands/schema` header: `convention` key rename; imported usage
  `checkpoints`; annotations and routine annotation reference it.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga/schema/hooks/CODEMANIFEST` (`SchemaHooks.amend_cell`, algorithm
  step 3): the malformed-shape enumeration "(a non-mapping payload,
  non-string keys, or non-serializable values at any nesting level)" did not
  cover an **empty mapping** — a contribution `{"cfg": {}}` would pass the
  check and render `"cfg": {}`, violating the output invariant "never an
  empty object at any of the three levels" pinned in `goga/schema`
  Requirements and both usage files → enumeration extended to "(a non-mapping
  payload, non-string keys, non-serializable values, **or an empty mapping**
  at any nesting level)" (reason: Interface ↔ Interface consistency — output
  invariant vs enforcement enumeration; approved by the user, variant A).
- `goga/schema/hooks/.usages/checkpoints.md`: the malformed-contribution
  parenthetical aligned with the same enumeration.
- `goga/schema/.usages/registering-hooks.md` (Failure treatment): the
  malformed-contribution enumeration aligned identically.

## Entity Interaction and Data Flow

### Interaction Diagram

```
                        CLI (goga/commands/schema/schema.py)
                          │ schema_logic(cells, max_depth, depends_on)
                          ▼
        schema()  (goga/schema/schema.py)
          │ AST(".") + load()                    ┌──────────────────────┐
          │ _filter_tree / _build_cell_tree /    │  authored documents  │
          │ _filter_by_depends_on / _prune_depth │  (AST.tree)          │
          ▼                                       └──────────────────────┘
        surviving node tree (dicts) + surviving path set
          │ facts = CellFacts(... DependencyFacts ...)   ← built from the
          │                                                 DocumentRoot
          ▼
        SchemaHooks.amend_cell(cell=facts)        (one SchemaHooks per run)
          │ _ensure_registry() ──> HookRegistry().build_once()   [once per run]
          │                              └─> enumerate_tool_packages()
          │                                   + register_hooks of each package
          │ resolve ("schema", "amend_cell") against declared_actions()
          │ per tool (enumeration order):
          │   fresh per-tool CellFacts view ──> CellAmendment(view)
          │   wrap_context(view) ──> proxy
          │   build_hook_arguments(hook, proxy, registry.self_context(tool))
          │   hook(**arguments)  ──> context.contribute({...}) buffers
          │ structural check of the merged buffer (hard on malformed)
          │   └─> ToolContribution(tool, merged)
          ▼
        merge_cell_contributions(contributions) ──> tools area dict
          ▼
        node["tools"] = tools   (iff non-empty)  ──> json.dumps (beautiful_json)
          ▼
        click.echo(json)  /  except Exception ──> stderr + exit 1
```

### Data Flows

1. **Generation flow** — CLI → `schema()` → AST load → filters → surviving
   set → per-cell facts → `amend_cell` → tools area → `node["tools"]` → JSON
   string → stdout.
2. **Contribution flow** — hook call → `CellAmendment.contribute(payload)` →
   per-tool pending payloads → key-wise merged buffer → structural check →
   `ToolContribution` → `merge_cell_contributions` → tools area.
3. **Failure flow** — crashed hook / malformed merged buffer / unknown
   address → `ValueError` out of `amend_cell` → propagates out of `schema()`
   → CLI catches `Exception` → stderr message + exit 1. Register-facade
   `ImportError` propagates the same path (message names the package).

### Entity Dependencies

Implementation order (matches the plan's dependency graph):

1. `goga/hooks/catalog/catalog.py` — the record (everything else resolves the
   address against it).
2. `goga/schema/hooks/facts.py` — no intra-zone dependencies.
3. `goga/schema/hooks/amendments.py` — imports `CellFacts` from `.facts`.
4. `goga/schema/hooks/overlay.py` — standalone pure data + routine.
5. `goga/schema/hooks/events.py` — imports `.facts`, `.amendments`, `.overlay`
   and the platform facade `goga.hooks`.
6. `goga/schema/hooks/__init__.py` — re-exports the six contract names.
7. `goga/schema/schema.py` — the walk integration.
8. `goga/commands/schema/schema.py` — the failure conversion.

No import cycle: the zone imports only `goga.hooks` (three dots up:
`from ...hooks import ...`), never `goga.schema`.

## Code Stack Trace

### Trace: `SchemaHooks()` (construction)

#### Chain
1. **Input**: constructor call, no arguments.
2. **Step**: `self._registry = None` — nothing enumerated, nothing imported →
   checkpoint: cheap construction ✓ (config-zone precedent `ConfigHooks.__init__`;
   `packages_distributions` unread).
3. **Output**: the surface object; the registry builds lazily on the first
   `amend_cell`.

### Trace: `SchemaHooks.amend_cell(cell)`

#### Chain
1. **Input**: the caller's `CellFacts` — authored facts of one surviving cell.
2. **Step**: `_ensure_registry()` — first call: `HookRegistry()` +
   `build_once()` → enumerates installed `goga_tool_*` packages
   (alphabetical), imports each facade, runs `register_hooks`; a broken
   facade import raises `ImportError` naming the package; later calls reuse
   the instance → checkpoint: one registry per run ✓
   (`enumerate_tool_packages` alphabetical; `packages_distributions` read once).
3. **Step**: resolve `("schema", "amend_cell")` against `declared_actions()`
   → the record exists once `catalog.py` carries it; `None` →
   `ValueError("unknown hook action: schema.amend_cell")` → checkpoint: the
   catalog record is a precondition ✓.
4. **Step**: `registry.subscriptions_for("schema", "amend_cell")` grouped by
   `subscription.tool` into an insertion-ordered `dict` → checkpoint:
   enumeration order preserved ✓ (subscription order = package alphabetical
   order = tool enumeration order).
5. **Step**: per tool — build a **fresh per-tool facts view**
   (`_read_only_view`: fresh `CellFacts` with fresh lists at every level and
   fresh `DependencyFacts` entries), wrap it in `CellAmendment`, deliver via
   `wrap_context` (attribute writes blocked), project via
   `build_hook_arguments` (only declared `context`/`self` receive values),
   call each hook of the tool → checkpoint: mutual blindness ✓ — every tool
   reads value-identical authored facts; an in-place list write stays local
   to that tool's view and dies with it (the caller's instance is never
   handed to any hook).
6. **Step**: a raising hook → `ValueError(f"hook {name} of tool {tool} failed
   on schema.amend_cell at {cell.path}: {reason}")` — stops the walk at the
   first failure → checkpoint: names hook + tool + action + cell path ✓
   (format extends the platform/config format with the cell path).
7. **Step**: after the tool's every hook returned — commit: merge the pending
   payloads key-wise into one buffer (each payload guarded as a `Mapping`
   before `dict.update` — an iterable of pairs is a malformed payload, not
   a coerced one); run the **structural check** on the merged buffer (see
   `CellAmendment` below); a malformed buffer →
   `ValueError(f"tool {tool} failed on schema.amend_cell at {cell.path}:
   structurally malformed contribution ({detail})`) → checkpoint: hard
   failure, the tool's contribution discarded, nothing returns ✓.
8. **Step**: an empty merged buffer commits nothing, silently; a passing tool
   commits `ToolContribution(tool, merged)` → checkpoint: tool-granular commit ✓.
9. **Output**: `merge_cell_contributions(contributions)` — the tools area;
   `{}` when nothing committed.

#### Checkpoint Summary
- Registry single-build per run: passed (mirrors `ConfigHooks._ensure_registry`).
- Address resolution against the catalog: passed (record added in fix scope).
- Type flow `CellFacts` → `CellAmendment.cell` → hook reads: passed.
- `contribute` buffer → `ToolContribution.facts` → merge → node `tools`:
  passed (all `dict[str, object]` / `dict[str, dict[str, object]]`).
- Hard-failure naming (tool, action, cell path): passed; formats pinned
  (D-4 below).

### Trace: `CellAmendment.contribute(facts)`

#### Chain
1. **Input**: the payload the hook passes — anything a callable can send.
2. **Step**: `self._pending.append(facts)` — stored verbatim, no
   interpretation, no validation → checkpoint: buffering changes nothing
   outside this tool's view ✓.
3. **Output**: None; the commit (inside `amend_cell`, after the tool's hooks
   return) merges the pending payloads key-wise — `for payload in pending:
   merged.update(payload)`, each payload guarded by a
   `collections.abc.Mapping` check — a payload that is not a Mapping (an
   iterable of key-value pairs included — `dict.update` accepts those
   silently) is rejected into the delivery's structural-failure conversion
   (not a raw escape and never a silent coercion into a mapping), because
   the guarded merge runs inside the commit step's intercept.

#### Checkpoint Summary
- Later-wins key-wise merge: passed (`dict.update` semantics).
- Empty mapping contributes nothing: passed (`{}` updates nothing).
- A non-mapping payload can neither pass nor escape as a raw `TypeError`:
  passed — the commit rejects any payload that is not a `Mapping` (an
  iterable of pairs included) into the hard-failure conversion before
  `dict.update` could coerce it.

### Trace: `merge_cell_contributions(contributions)`

#### Chain
1. **Input**: committed contributions in enumeration order.
2. **Step**: `{c.tool: c.facts for c in contributions if c.facts}` — a fresh
   outer mapping; each non-empty merged buffer placed under its tool identity
   key (by reference — the buffer is single-owner, built by the delivery) →
   checkpoint: empty skipped ✓, deterministic ✓, pure ✓ (inputs unmutated).
3. **Output**: the tools area — `{}` when every contribution was empty or
   none committed.

### Trace: `schema(cells, max_depth, depends_on)` (modified walk)

#### Chain
1. **Input**: filters from the CLI (or a direct caller).
2. **Step**: `AST(".")` + `load()`; `ast_obj.errors` non-empty → `ValueError`
   with the error count (unchanged behavior) → checkpoint: pre-existing
   contract preserved ✓.
3. **Step**: `_filter_tree(ast_obj.tree, cells)` → `_build_cell_tree(doc,
   allowed)` → `_filter_by_depends_on(result, depends_on)` →
   `_prune_depth(cell, max_depth)` — all unchanged → checkpoint: filters in
   the order `cells`, `depends_on`, `max_depth` ✓; the six base fields of
   every node are exactly the pre-change fields ✓.
4. **Step**: empty result → return `"[]"` (early, before any delivery — the
   registry never builds) → checkpoint ✓.
5. **Step**: build the surviving path set (pre-order walk of the final dict
   tree) and a `path -> node` map → checkpoint: a cell is delivered iff its
   node appears in the output tree ✓.
6. **Step**: `hooks = SchemaHooks()` (one per run) — then pre-order walk of
   the **authored** doc tree (`ast_obj.tree`): for each doc whose
   `os.path.normpath(doc.path)` is in the surviving set, build
   `facts = CellFacts(path=normpath(doc.path), description=doc.footer.description,
   types=sorted(entity names + routine names), usages=_find_usages_files(doc.path),
   dependencies=[DependencyFacts(path, sorted types, sorted usages) per sorted
   source path], children=[normpath(child.path) for child in doc.children])`
   → checkpoint: **authored projection** ✓ — `children` carries the authored
   children even when the node's children were pruned by filters; the field
   values mirror the node's base fields exactly (`_build_cell_tree` /
   `_build_dependencies` produce the same sorted values).
7. **Step**: `tools = hooks.amend_cell(cell=facts)`; `if tools:
   node["tools"] = tools` → checkpoint: the key exists iff non-empty ✓; no
   other node field touched ✓; cell-major tree order ✓ (doc pre-order = node
   pre-order of the surviving skeleton).
8. **Output**: `json.dumps(result, indent=4, sort_keys=True,
   ensure_ascii=False)` (`beautiful_json`) — byte-identical to the
   six-field map when no `tools` key was placed ✓.

#### Checkpoint Summary
- Byte-identity with no subscriptions/no packages: passed (delivery returns
  `{}`, no key placed; `sort_keys` unaffected).
- Filters prune delivery exactly as output: passed (surviving-set design).
- Authored facts regardless of filters: passed (facts from `DocumentRoot`).
- Determinism: passed (fixed walk order, tool enumeration order, `sort_keys`).

### Trace: CLI `schema` command (modified)

#### Chain
1. **Input**: click-parsed `cells` tuple, `max_depth`, `depends_on` tuple.
2. **Step**: `try: result = schema_logic(list(cells), max_depth,
   list(depends_on))` — unchanged call shape.
3. **Step**: `except Exception as e:` (broadened from `except ValueError`) →
   `click.echo(str(e), err=True)`; `ctx.exit(1)` → checkpoint: AST
   `ValueError`, checkpoint hard `ValueError`, and register-facade
   `ImportError` all convert to a clean stderr message + exit 1, no raw
   traceback ✓; `KeyboardInterrupt`/`SystemExit` are `BaseException` — pass
   through untouched ✓ (platform precedent: `emit_hook_event` catches
   `Exception` only).
4. **Output**: `click.echo(result)` on success — stdout carries the JSON
   only; exit 0 only on a complete generation.

## Algorithm Design

### `CellFacts` / `DependencyFacts` (facts.py)

**Responsibility**: the immutable authored-facts projection of one cell.

**Algorithm:**
```
1. Constructed by the caller (the schema walk) from resolved values —
   nothing is read inside: path, description, types, usages,
   dependencies, children arrive as arguments
   → frozen kw_only dataclasses; field assignment raises
   (FrozenInstanceError ⊂ AttributeError — "attribute assignment is
   blocked" of registering-hooks.md)
2. DependencyFacts: path + sorted types + sorted usages per source path
   → pure data, frozen kw_only
```

**Errors:** none — construction only.

**Edge cases:** all-list fields may be empty (`usages == []` when the cell
has no `.usages/`); `children == []` for leaves; `dependencies == []` for
import-free cells.

### `CellAmendment` (amendments.py)

**Responsibility**: the per-tool read-and-contribute view.

**Algorithm:**
```
1. Holds `cell` (the per-tool fresh facts view) and `_pending`
   (list of buffered payloads, init=False, repr=False)
2. contribute(facts):
   - append the payload verbatim — no validation, no interpretation
3. Commit (driven by the delivery, not by the view):
   - merged = {}; for payload in _pending: a payload that is not a
     collections.abc.Mapping (an iterable of key-value pairs included —
     dict.update accepts those silently) is the structural failure here
     → converted by the delivery into the structural hard failure
     (never a raw escape, never silently coerced into a mapping);
     otherwise merged.update(payload)
   - key-wise later-wins merge; an empty payload updates nothing
```

**Errors:** none raised by the view itself; the commit's errors belong to
the delivery.

**Edge cases:** `contribute({})` contributes nothing; two payloads
`{"a": 1}` then `{"a": 2}` merge to `{"a": 2}`.

### `ToolContribution` (overlay.py)

**Responsibility**: one committed contribution — frozen kw_only pairing of
the tool identity with its merged fact mapping. Constructed by the delivery
alone.

### `merge_cell_contributions(contributions)` (overlay.py)

**Responsibility**: the deterministic tools-area composition.

**Algorithm:**
```
1. Take the contributions in enumeration order
2. IF a contribution's mapping is empty → skip (a tool's key exists
   iff that tool wrote at least one fact)
3. Place each remaining mapping under its tool identity key
   → result = {c.tool: c.facts for c in contributions if c.facts}
4. RETURN the composed mapping — {} when nothing committed
```

**Errors:** none — structural validation already happened at the tool
commit point.

**Edge cases:** empty list → `{}`; every contribution empty → `{}`.

### `SchemaHooks` (events.py)

**Responsibility**: the checkpoint surface — the staged per-tool delivery of
the hard `schema / amend_cell` action.

**Algorithm:**
```
1. __init__: _registry = None (cheap)
2. _ensure_registry(): IF _registry is None → HookRegistry() +
   build_once(); store → returned on every call
   → ImportError of a broken facade propagates (names the package)
3. amend_cell(cell):
   a. registry = _ensure_registry()
   b. record = the ("schema", "amend_cell") entry of declared_actions()
      → IF None: ValueError("unknown hook action: schema.amend_cell")
   c. groups = {} ; for sub in
      registry.subscriptions_for("schema", "amend_cell"):
      groups.setdefault(sub.tool, []).append(sub)
   d. FOR tool, subscriptions in groups.items() (enumeration order):
      - view = CellAmendment(cell=_read_only_view(cell))
        (fresh lists at every level, fresh DependencyFacts entries —
        the caller's instance is never handed to a hook)
      - proxy = wrap_context(view)
      - FOR sub in subscriptions:
          sub.hook(**build_hook_arguments(sub.hook, proxy,
                                          registry.self_context(tool)))
          → on Exception: ValueError(f"hook {sub.name} of tool {tool}
            failed on schema.amend_cell at {cell.path}: {reason}")
      - commit (in its own intercept, after the tool's hook loop):
        merged = key-wise merge of view._pending — each payload must
        be a Mapping; a payload that is not a Mapping (an iterable of
        key-value pairs included) is the structural failure, not a
        raw escape and never a silent coercion into a mapping
      - _check_json_map(merged) — the structural check:
        mappings only (collections.abc.Mapping, dict-like; payloads
        delivered to hooks arrive as plain data), string keys only,
        no empty mapping anywhere, values recursively: mapping
        (same rules) | list/tuple of recursively-checked items |
        str | int | finite float | bool | None; everything else
        (set, bytes, object, NaN/inf, non-str keys, {} anywhere)
        → ValueError(f"tool {tool} failed on schema.amend_cell at
          {cell.path}: structurally malformed contribution ({detail})")
      - IF merged: contributions.append(ToolContribution(tool, merged))
        (empty buffer commits nothing, silently)
   e. RETURN merge_cell_contributions(contributions)
```

**Errors:**
- `ValueError` — unknown address; crashed hook (names hook, tool, action,
  cell path); structurally malformed contribution (names tool, action, cell
  path, detail) → the consumer (`schema()` / CLI) surfaces a clean failure.
- `ImportError` — broken tool facade at the registry build (names the
  package) → propagates raw out of the routine; the CLI converts.

**Edge cases:** no subscriptions → `{}` (registry still builds once — the
enumeration happened, the delivery is unobservable); no tool packages
installed → `{}`; a tool whose every hook contributed nothing → no key.

### `schema` routine (goga/schema/schema.py)

**Responsibility**: the extended generation walk.

**Algorithm:**
```
1. AST(".") + load(); IF errors → ValueError with the count
2. result = the existing pipeline: _filter_tree → _build_cell_tree →
   _filter_by_depends_on → _prune_depth   (unchanged helpers)
3. IF not result → return "[]"            (no delivery, no registry)
4. surviving = {node paths of the pre-order walk of result};
   nodes = {path: node}
5. hooks = SchemaHooks()                   (one per run)
6. FOR doc in pre-order(ast_obj.tree):
     path = os.path.normpath(doc.path)
     IF path not in surviving → continue
     facts = CellFacts(path, doc.footer.description,
                       sorted(entity + routine names),
                       _find_usages_files(doc.path),
                       [DependencyFacts(p, t, u) per sorted dep source],
                       [normpath(c.path) for c in doc.children])
     tools = hooks.amend_cell(cell=facts)
     IF tools → nodes[path]["tools"] = tools
7. RETURN beautiful_json(result)
```

**Errors:** propagates `ValueError` (AST, checkpoint) and `ImportError`
(facade) — the routine never prints and never returns partial JSON (an
exception discards the in-progress result).

**Edge cases:** empty tree → `"[]"` without any package enumeration;
pruned children still present in the delivered `facts.children` (authored
projection).

### CLI `schema` command (goga/commands/schema/schema.py)

**Responsibility**: clean failure conversion.

**Algorithm:**
```
1. try: result = schema_logic(list(cells), max_depth, list(depends_on))
2. except Exception as e: click.echo(str(e), err=True); ctx.exit(1)
3. click.echo(result)
```

**Errors:** every `Exception` of the routine → stderr + exit 1 (AST count
message, checkpoint message naming tool/action/cell path, package name for
the import failure); `BaseException` passes through.

**Edge cases:** no output on stdout when exiting 1 — `click.echo(result)`
runs only on success; no traceback reaches the terminal.

### `declared_actions` (goga/hooks/catalog/catalog.py)

**Responsibility**: the catalog record.

**Algorithm:**
```
1. Append to _DECLARED_ACTIONS:
   Action(domain="schema", name="amend_cell", error_class="hard")
   (list position is irrelevant — declared_actions() sorts by
   (domain, name); the record sorts between "pipeline" and "statuses")
```

**Edge cases:** none — data only, published records untouched.

## Cross-cutting Concerns

- **Error handling**: the zone raises `ValueError` for every hard failure of
  the delivery (crashed hook, malformed contribution, unknown address) with
  pinned message formats; the register-facade `ImportError` propagates raw;
  the walk propagates both untouched; the CLI converts every `Exception`
  into stderr + exit 1. Message formats (pinned):
  `hook {name} of tool {tool} failed on schema.amend_cell at {cell_path}: {reason}`;
  `tool {tool} failed on schema.amend_cell at {cell_path}: structurally malformed contribution ({detail})`;
  `unknown hook action: schema.amend_cell`.
- **Logging**: the zone never logs and never prints (the caller owns all
  output). The platform already logs registration warnings at build
  (`skipping hook registration of tool ...`) — unchanged.
- **Validation**: the structural check at the tool commit point (mapping
  shape, string keys, JSON-representable values, no empty mappings, finite
  floats) — evaluated on the **merged** buffer, so intra-tool merges that
  eliminate a malformed shape pass; filters validate nothing new (the
  pre-existing filter semantics are untouched).
- **Caching**: one lazily-built `HookRegistry` per `SchemaHooks` instance —
  `packages_distributions()` read exactly once per run whatever the number
  of delivered cells; nothing is cached across runs.
- **Concurrency**: single-threaded walk; no shared mutable state crosses the
  per-tool views (fresh per-tool facts copies close the in-place-write
  channel).

## Usages Analysis

### `convention`
- **What it provides**: mandatory Python conventions — relative imports,
  kw_only dataclasses, Google docstrings, logging, test structure/mirroring.
- **Where used**: all four manifests (global annotations + member
  annotations).
- **Why chosen**: project-wide baseline (file form — reused, evolves
  independently).
- **How exactly**: frozen `kw_only=True` dataclasses for the facts and
  contribution records; relative imports (`from ...hooks import ...`,
  `from .facts import ...`); Google docstrings with Args/Returns/Raises;
  tests mirror `tests/schema/hooks/` ← `goga/schema/hooks/`.

### `documents` (inline, goga/schema)
- **What it provides**: the AST load contract — `AST(".")`, `AST.load()`,
  `AST.tree`.
- **Where used**: the `schema` routine algorithm step 1.
- **Why chosen**: the existing project-tree load practice of the cell.
- **How exactly**: `ast_obj = AST("."); ast_obj.load()`; `ast_obj.tree` for
  the walk; `ast_obj.errors` for the count guard.

### `beautiful_json` (inline, goga/schema)
- **What it provides**: the output serialization format.
- **Where used**: the `schema` routine final step.
- **Why chosen**: unchanged output format of the cell.
- **How exactly**: `json.dumps(result, indent=4, sort_keys=True,
  ensure_ascii=False)` — the `tools` key sorts alphabetically among the node
  keys deterministically.

### `click` (file, goga/commands/schema)
- **What it provides**: CLI command construction.
- **Where used**: the command decorators and `click.echo`.
- **Why chosen**: the CLI framework practice of the cell.
- **How exactly**: unchanged decorators; `click.echo(result)` for stdout;
  `click.echo(str(e), err=True)` + `ctx.exit(1)` for failures.

### Imported Usages
- `per-tool-delivery` from `goga/hooks` — the staged delivery loop skeleton:
  registry + `build_once`, `subscriptions_for` grouping by tool,
  `wrap_context`/`build_hook_arguments` projection, tool-granular commit.
  Path: `goga/hooks/.usages/per-tool-delivery.md`.
- `registering-hooks` from `goga/hooks` — the registration contract behind
  the checkpoint: facade `register_hooks`, `subscribe(domain, action, name,
  hook)`, offered parameter names `context`/`self`, failure behavior.
  Path: `goga/hooks/.usages/registering-hooks.md`.
- `checkpoints` from `goga/schema/hooks` (imported by `goga/schema` and
  `goga/commands/schema`) — the zone's consumer documentation: the
  `SchemaHooks()` surface, the per-cell amend loop, hard-failure handling,
  output shape. Path: `goga/schema/hooks/.usages/checkpoints.md`.

## `.usages/` Update

### Cell: `goga/schema/hooks`

#### New Files
- **checkpoints** → `goga/schema/hooks/.usages/checkpoints.md`
  - Reason: the zone's consumer documentation (domain-mandated registering
    surface for generation-path consumers).
  - Related entities: `SchemaHooks`, `CellFacts`, `DependencyFacts`.
  - Status: created by the architecture stage; verified against the contract
    (names, loop shape, failure naming, output shape) — current, including
    the applied empty-mapping fix.

### Cell: `goga/schema`

#### Existing Files — Consistency
- **schema-usage** → `goga/schema/.usages/schema-usage.md`
  - Status: current — the node example carries the conditional `tools`
    field; Side Effects carry the checkpoint delivery and byte-identity
    bullets.

#### New Files
- **registering-hooks** → `goga/schema/.usages/registering-hooks.md`
  - Reason: the domain-level tool-author documentation (memory pattern:
    every hooks domain needs domain-level `registering-hooks.md` + zone
    `checkpoints.md`).
  - Related entities: `CellAmendment`, `contribute`, the `schema /
    amend_cell` address.
  - Status: created; verified — the events table, subscribe example,
    amendment-view reads, merge rules, failure treatment (with the applied
    empty-mapping alignment), run-output guarantees all match the contract.

### Cell: `goga/commands/schema`

#### Existing Files — Consistency
- **schema** → `goga/commands/schema/.usages/schema.md`
  - Status: current — Purpose carries the tools sentence; Exit codes carry
    the checkpoint hard-failure entry.

### Cell: `goga/hooks/catalog`
- No `.usages/` directory — skip (catalog additivity law: the record bullet
  is the whole change).

## Test Stack Trace

### General Setup

- Zone suites live in `tests/schema/hooks/` mirroring `goga/schema/hooks/`
  (`test_facts.py`, `test_amendments.py`, `test_overlay.py`,
  `test_events.py`, `test_facade.py`, `conftest.py` re-exporting the
  platform boundary fixtures — the `tests/config/hooks/conftest.py`
  precedent):
  `from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401`
- `pin_package_environment({mapping})` pins `packages_distributions`;
  `install_tool_package("goga_tool_<tool>", register_hooks=...)` installs a
  fake facade into `sys.modules`. The platform code runs for real.
- Walk/CLI tests build CODEMANIFEST trees under `tmp_path` (the
  `tests/commands/test_schema.py` fixture style) and `monkeypatch.chdir` —
  no mocks inside business logic (convention).

### Source File Registry

- Under test: `goga/hooks/catalog/catalog.py`, `goga/schema/hooks/facts.py`,
  `goga/schema/hooks/amendments.py`, `goga/schema/hooks/overlay.py`,
  `goga/schema/hooks/events.py`, `goga/schema/hooks/__init__.py`,
  `goga/schema/schema.py`, `goga/commands/schema/schema.py`.
- Test files: `tests/hooks/catalog/test_catalog.py` (updated),
  `tests/schema/hooks/*` (new), `tests/schema/test_schema.py` (extended),
  `tests/commands/test_schema.py` (extended).

---

### Positive Tests

#### `test_amend_cell_commits_buffered_facts`

**Setup**: `pin_package_environment({"goga_tool_docs": ["docs-dist"]})`;
`install_tool_package("goga_tool_docs", register_hooks=register)` where
`register` subscribes `("schema", "amend_cell", "cover", cover)` and
`cover(context)` calls `context.contribute({"coverage": 3})`; one
`CellFacts(path="goga/config", ..., types=["ProjectConfig"],
usages=[], dependencies=[], children=[])`.

**Input**: `SchemaHooks().amend_cell(cell=facts)`

**Trace**:
```
amend_cell(facts)
  → _ensure_registry()               # build_once: enumerate [goga_tool_docs],
  │                                    import facade, subscribe "cover"
  → declared_actions()               # ("schema", "amend_cell", "hard") found
  → groups = {"docs": [sub]}         # tool identity derived by the platform
  → view = CellAmendment(cell=fresh_copy(facts)); proxy = wrap_context(view)
  → cover(**{"context": proxy})      # only "context" declared
    → view._pending.append({"coverage": 3})
  → merged = {"coverage": 3}         # key-wise commit
  → _check_json_map(merged)          # passes
  → contributions = [ToolContribution("docs", {"coverage": 3})]
  → merge_cell_contributions(...)    # {"docs": {"coverage": 3}}
```

**Assertions**:
```
result == {"docs": {"coverage": 3}}
```

**Sufficiency**: pins the whole delivery chain — the address resolves, the
per-tool view is delivered, `contribute` buffers, the commit merges, the
composition places the mapping under the platform-derived identity
(`goga_tool_docs` → `docs`). Prevents regression of the identity derivation
or the commit granularity.

#### `test_amend_cell_empty_contribute_commits_nothing`

**Setup**: `pin_package_environment({"goga_tool_docs": ["docs-dist"]})`;
`install_tool_package("goga_tool_docs", register_hooks=register)` where
`register` subscribes `("schema", "amend_cell", "empty", empty)` and
`empty(context)` calls `context.contribute({})` — the buffer ends
non-empty (`[{}]`) while the merged buffer stays empty; one `CellFacts`
instance.

**Input**: `SchemaHooks().amend_cell(cell=facts)`

**Trace**:
```
delivery → tool docs: pending = [{}]        # buffer NOT empty
→ commit: merged = {} ∪ {} = {}             # merged empty
→ commits nothing, silently → contributions == []
→ merge_cell_contributions([]) → {}
```

**Assertions**:
```
result == {}
# the inversion on the same fixture: a hook writing {"a": 1} yields
# {"docs": {"a": 1}} — the key exists iff merged is non-empty
```

**Sufficiency**: pins the commit semantics "iff the merged buffer is
non-empty" (not "iff pending is non-empty") — prevents a regression that
commits an empty `ToolContribution` out of a non-empty buffer of empty
payloads; closes the declared `contribute({})` edge case at the delivery
level.

#### `test_contribute_merges_key_wise_later_wins`

**Setup**: a plain `CellAmendment(cell=facts)` (unit level, no platform).

**Input**: `contribute({"a": 1, "b": 2})` then `contribute({"a": 3})`

**Trace**:
```
contribute({"a": 1, "b": 2}) → _pending = [{"a": 1, "b": 2}]
contribute({"a": 3})         → _pending = [{"a": 1, "b": 2}, {"a": 3}]
commit (delivery)            → merged = {"a": 3, "b": 2}
```

**Assertions**:
```
the delivery's merged buffer == {"a": 3, "b": 2}   # a later write replaces
```

**Sufficiency**: the key-wise later-wins merge rule of the contract —
prevents an order-sensitive or append-style merge regression.

#### `test_merge_cell_contributions_composes_in_enumeration_order`

**Setup**: `ToolContribution(tool="alpha", facts={"x": 1})`,
`ToolContribution(tool="beta", facts={"y": 2})`,
`ToolContribution(tool="gamma", facts={})`.

**Input**: `merge_cell_contributions([alpha, beta, gamma])`

**Trace**:
```
loop over contributions → alpha placed; beta placed; gamma skipped (empty)
→ {"alpha": {"x": 1}, "beta": {"y": 2}}
```

**Assertions**:
```
result == {"alpha": {"x": 1}, "beta": {"y": 2}}
list(result) == ["alpha", "beta"]          # enumeration order preserved
inputs unchanged after the call             # purity
merge_cell_contributions([]) == {}
```

**Sufficiency**: the no-empty composition rule, determinism, purity, and the
empty-list passthrough — the exact contract of the routine.

#### `test_schema_walk_places_tools_and_keeps_base_fields`

**Setup**: `tmp_path` with a root CODEMANIFEST + `subpkg` child (the
`ROOT_WITH_CHILD`/`CHILD` fixtures); a scratch tool package (pinned
environment + installed facade) contributing `{"score": 3}` on every cell.

**Input**: `_run_schema()` (CLI) and the direct `schema([], None, [])` call.

**Trace**:
```
schema([], None, [])
  → AST load; filters no-op
  → surviving = {".", "subpkg"}; nodes = {path: node}
  → hooks.amend_cell(facts(".")) → {"docs": {"score": 3}} → node["tools"]
  → hooks.amend_cell(facts("subpkg")) → {"docs": {"score": 3}} → node["tools"]
  → json.dumps(..., sort_keys=True)
```

**Assertions**:
```
data[0]["tools"] == {"docs": {"score": 3}}
data[0]["children"][0]["tools"] == {"docs": {"score": 3}}
set(data[0].keys()) == {"cell", "children", "dependencies",
                        "description", "tools", "types", "usages"}
# six base fields identical to a no-tool run (compare against a second
# project run with pin_package_environment({}))
```

**Sufficiency**: the end-to-end integration — tools appear under the
identity key, base fields stay untouched, both entry paths (routine + CLI)
agree.

#### `test_amend_cell_builds_registry_once_per_run`

**Setup**: `pin_package_environment({"goga_tool_docs": ["docs-dist"]})` with
a subscribed scratch tool; `hooks = SchemaHooks()`.

**Input**: two consecutive `amend_cell` calls over two different `CellFacts`.

**Trace**:
```
amend_cell(cell_1) → _ensure_registry → build_once (boundary called 1st time)
amend_cell(cell_2) → _ensure_registry → cached (boundary NOT called)
```

**Assertions**:
```
boundary.call_count == 1
both calls return the tool's composed area
```

**Sufficiency**: the one-registry-per-run requirement — prevents a
per-cell enumeration regression that would multiply package imports.

#### `test_catalog_carries_schema_amend_cell_record`

**Setup**: none (pure catalog read).

**Input**: `declared_actions()`

**Trace**:
```
declared_actions() → sorted(_DECLARED_ACTIONS, key=(domain, name))
```

**Assertions**:
```
Action(domain="schema", name="amend_cell", error_class="hard") in records
len(records) == 20                       # was 19
("schema", "amend_cell", "hard") at the sorted position between
    ("pipeline", "run_created", "soft") and ("statuses", "register_statuses", "soft")
# the existing length assertions updated 19 → 20 (three sites: the
# topics, pipeline, and config tests); the frozen full-catalog
# `expected` list of test_catalog_carries_the_five_build_records gains
# the row in its sorted position; the derived
# `len(triples) == len(pre_existing) + 1` assertion of
# test_config_amend_config_record_present stays consistent via the
# schema triple added to its `pre_existing` list
```

**Sufficiency**: the catalog additivity law — the record present, published
records untouched, the complete catalog pinned against the frozen list.

---

### Negative Tests

#### `test_amend_cell_crashed_hook_is_hard_failure_naming_cell_path`

**Setup**: pinned environment + installed `goga_tool_boom` subscribing
`("schema", "amend_cell", "explode", explode)` where `explode(context)`
raises `RuntimeError("kaput")`.

**Input**: `SchemaHooks().amend_cell(cell=facts)` with
`facts.path == "goga/config"`.

**Trace**:
```
delivery walk → explode(**{"context": proxy}) raises RuntimeError
→ except Exception → ValueError("hook explode of tool boom failed on
  schema.amend_cell at goga/config: kaput")
```

**Assertions**:
```
pytest.raises(ValueError, match="hook explode of tool boom failed on schema.amend_cell at goga/config: kaput")
```

**Sufficiency**: the hard semantics and the pinned failure format (hook,
tool, action, cell path, reason) — prevents silent skip or anonymous errors.

#### `test_amend_cell_structurally_malformed_contribution_is_hard_failure`

**Setup**: pinned environment + installed `goga_tool_bad` subscribing a hook
that contributes a malformed payload. Parametrized over:
`{"cfg": {}}` (empty mapping), `{"cfg": {"deep": {}}}` (nested empty),
`{1: "x"}` (non-string key), `{"v": {1, 2}}` (a set — non-serializable),
`{"v": float("nan")}` (non-finite float), ` [("a", 1)]` (non-mapping payload).

**Input**: `SchemaHooks().amend_cell(cell=facts)` with `facts.path ==
"goga/schema"`.

**Trace**:
```
hook returns → commit merges → _check_json_map(merged) fails on the shape
→ ValueError("tool bad failed on schema.amend_cell at goga/schema:
  structurally malformed contribution (<detail>)")
```

**Assertions**:
```
pytest.raises(ValueError, match=r"tool bad failed on schema\.amend_cell at goga/schema: structurally malformed contribution")
# one parametrized case per shape; the merged-buffer semantics case:
# hook1 contributes {"a": {}}, hook2 contributes {"a": {"b": 1}} → NO raise
```

**Sufficiency**: the structural-check boundary — every malformed shape of
the contract enumeration (including the applied empty-mapping fix) fails
naming tool + action + cell path, and shapes eliminated by the key-wise
merge pass.

#### `test_schema_hard_failure_propagates_without_partial_output`

**Setup**: `tmp_path` project with two cells; a scratch tool whose hook
raises on the second delivered cell (counting invocations).

**Input**: `schema([], None, [])`.

**Trace**:
```
walk → amend_cell(cell_1) OK → amend_cell(cell_2) raises ValueError
→ propagates out of schema(); json.dumps never runs
```

**Assertions**:
```
pytest.raises(ValueError, match="at <second cell path>")
# nothing was printed (the routine never prints) and the raised error
# carries the failing cell path, not the first one
```

**Sufficiency**: no partial JSON — the hard failure of a mid-walk cell
discards the whole generation.

#### `test_cli_converts_checkpoint_hard_failure_cleanly`

**Setup**: the same scratch project and failing tool (pinned environment).

**Input**: `_run_schema()` via CliRunner.

**Trace**:
```
CLI → schema_logic raises ValueError → except Exception →
click.echo(msg, err=True) → ctx.exit(1)
```

**Assertions**:
```
result.exit_code == 1
"failed on schema.amend_cell" in result.output
"Traceback" not in result.output
```

**Sufficiency**: the CLI failure conversion — exit 1, message present, no
raw traceback (stdout carries nothing on failure).

#### `test_cli_converts_register_facade_import_failure`

**Setup**: a real broken package on disk (the
`test_build_once_broken_import_is_fatal_through_the_real_import`
precedent of `tests/hooks/registry/test_state.py`): a `tmp_path`
directory `goga_tool_broken/` whose `__init__.py` contains
`import goga_missing_dependency`; `monkeypatch.syspath_prepend(tmp_path)`;
`pin_package_environment({"goga_tool_broken": ["goga-tool-broken"]})`;
a one-cell `tmp_path` project.

**Input**: `_run_schema()` on a one-cell `tmp_path` project.

**Trace**:
```
schema() → walk → amend_cell → _ensure_registry → build_once →
import_module("goga_tool_broken") → the facade executes, its own
import of goga_missing_dependency raises ModuleNotFoundError
(exc.name ≠ facade — the deeper miss) → platform wrapper
ImportError("package goga_tool_broken failed to import: ...") →
propagates → CLI except Exception → stderr + exit 1
```

**Assertions**:
```
result.exit_code == 1
"goga_tool_broken" in result.output
"Traceback" not in result.output
```

**Sufficiency**: the single fatal platform case reaches the user as a clean
command failure naming the package.

---

### Edge Case Tests

#### `test_schema_output_byte_identical_without_subscriptions`

**Setup**: `tmp_path` project (root + child + `.usages` files);
`pin_package_environment({})` — no tool packages; capture the output; then
install a subscribed-but-silent tool (a hook that only reads) and re-run.

**Input**: `schema([], None, [])` in both runs.

**Trace**:
```
run A: amend_cell → registry builds over {} → no subscriptions → {} → no key
run B: registry builds, hook reads context.cell.path, contributes nothing
       → {} → no key
```

**Assertions**:
```
"tools" not in output_a and '"tools"' not in output_a
output_a == output_b                      # byte-identical
boundary.call_count == 1 per run          # enumeration still once
```

**Sufficiency**: the no-extension guarantee — byte-identity with no
subscriptions and with silent subscribers (the strongest regression guard
for existing consumers of `goga schema`).

#### `test_schema_empty_tree_skips_enumeration_entirely`

**Setup**: empty `tmp_path` (no CODEMANIFEST anywhere) with a
non-vacuous environment: `pin_package_environment({"goga_tool_docs":
["docs-dist"]})` + `install_tool_package("goga_tool_docs",
register_hooks=register)` where `register` subscribes
`("schema", "amend_cell", "cover", cover)` and `cover(context)` calls
`context.contribute({"x": 1})` — the provocateur: were the delivery to
start, it would commit and break the asserts.

**Input**: `schema([], None, [])` under `_cwd(tmp_path)`.

**Trace**:
```
AST(".") + load() → tree == [] → no errors → result = []
→ IF not result → return "[]"   (early exit; walk/delivery never start)
→ SchemaHooks() never constructed; _ensure_registry never called;
  packages_distributions never read
```

**Assertions**:
```
schema([], None, []) == "[]"
boundary.call_count == 0
```

**Sufficiency**: guards the early return before any delivery state
exists — prevents a regression where an empty run still enumerates (and
imports) the installed tool packages, violating "empty tree → `[]`
without any package enumeration"; the subscribed provocateur ensures the
test cannot pass vacuously through an empty environment.

#### `test_filters_prune_delivery_exactly_as_output`

**Setup**: `tmp_path` project: root `.` → `pkg` → (`sub_a`, `sub_b`), with
`pkg/sub_a` importing from `lib`; a recording scratch tool appending every
delivered `context.cell.path` to a list.

**Input**: parametrized — `cells=["pkg"]`; `max_depth=1`;
`depends_on=["lib"]`; combined `cells=["pkg"] + depends_on=["lib"]`.

**Trace**:
```
schema(filters) → surviving set from the final tree →
pre-order doc walk delivers only surviving paths
```

**Assertions**:
```
delivered_paths == {node["cell"] for node in pre_order(parsed_output)}
# per filter: cells keeps pkg/subtree only; max_depth=1 prunes sub_a/sub_b;
# depends_on=["lib"] keeps root + pkg + sub_a (skeleton preserved)
```

**Sufficiency**: the delivery-pruning equivalence — prevents a regression
where a pruned cell still receives a delivery (or a surviving cell is
skipped).

#### `test_delivered_facts_carry_authored_children_under_max_depth`

**Setup**: root → `pkg` → `leaf` project; `max_depth=1` (leaf pruned from
output); a recording tool capturing `context.cell.children` on `pkg`.

**Input**: `schema([], 1, [])`.

**Trace**:
```
node for pkg: children == [] (pruned)
facts for pkg: children == ["pkg/leaf"] (authored doc tree)
delivery → tool reads ["pkg/leaf"]
```

**Assertions**:
```
recorded_children == ["pkg/leaf"]
parsed_output pkg node["children"] == []
```

**Sufficiency**: the authored-projection rule — the facts are identical in
every run regardless of filters; a pruned node never leaks filter state
into the delivered view.

#### `test_frozen_facts_block_attribute_assignment_and_isolate_tools`

**Setup**: two `CellAmendment` views built by the delivery over one caller
`CellFacts` (one subscribed scratch tool mutating its view's list in place:
`context.cell.types.append("junk")`; a second subscribed tool reading
`context.cell.types` afterwards); direct unit: `facts.path = "x"`.

**Input**: the delivery over both tools; the direct assignment attempt.

**Trace**:
```
facts.path = "x" → FrozenInstanceError (⊂ AttributeError)
tool_alpha: context.cell.types.append("junk") → mutates ITS fresh copy only
tool_beta: reads context.cell.types → the authored list, no "junk"
```

**Assertions**:
```
pytest.raises(AttributeError): facts.path = "x"
beta_reads == authored types (no "junk")
the caller's facts.types unchanged after the whole delivery
```

**Sufficiency**: mutual blindness at the container level + the blocked
attribute-assignment promise of registering-hooks.md.

#### `test_amend_cell_without_subscriptions_returns_empty_mapping`

**Setup**: `pin_package_environment({})`.

**Input**: `SchemaHooks().amend_cell(cell=full_facts)`.

**Trace**:
```
registry builds over {} → subscriptions_for → [] → groups {} →
contributions [] → merge → {}
```

**Assertions**:
```
result == {}
```

**Sufficiency**: the passthrough — the delivery is unobservable; guards the
empty-registry path against a spurious error or a tools key.

#### `test_construction_enumerates_nothing`

**Setup**: `boundary = pin_package_environment({"goga_tool_demo": ["demo"]})`.

**Input**: `SchemaHooks()`.

**Trace**:
```
__init__ → _registry = None; boundary unread
```

**Assertions**:
```
boundary.call_count == 0
```

**Sufficiency**: cheap construction — a construction-time enumeration would
tax every import of the zone even when no checkpoint fires.

#### `test_zone_facade_reexports_six_contract_names`

**Setup**: none.

**Input**: `from goga.schema.hooks import (CellAmendment, CellFacts,
DependencyFacts, SchemaHooks, ToolContribution, merge_cell_contributions)`.

**Trace**:
```
import goga.schema.hooks → __init__ pulls the four modules → names bound
```

**Assertions**:
```
sorted(__all__) == ["CellAmendment", "CellFacts", "DependencyFacts",
                    "SchemaHooks", "ToolContribution",
                    "merge_cell_contributions"]
importing goga.schema.hooks enumerates no packages (boundary unread)
```

**Sufficiency**: the consumer import surface the contract promises (the
plan's facade check); importing the zone stays side-effect-free.

## Additional Instructions for the Implementation Agent

- Implement in the dependency order of "Entity Dependencies" above; the
  catalog record lands first — every later step resolves the address against
  it.
- Follow the config zone (`goga/config/hooks/`) as the structural mirror:
  module layout, `_ensure_registry` shape, per-tool delivery loop, frozen
  kw_only records, private-buffer access from the delivery, docstring
  density.
- The per-tool fresh facts view (`_read_only_view` analog for
  `CellFacts`/`DependencyFacts` — fresh lists at every level) is mandatory,
  not an optimization: it closes the in-place-write channel between tools.
- The structural check must be an explicit recursive validator — NOT a
  `json.dumps` try/except (dumps coerces non-string keys and accepts
  NaN/Infinity; both must fail). Reject: non-mapping payloads, non-string
  keys, empty mappings anywhere, non-finite floats, any non-JSON scalar
  type. Evaluate on the **merged** buffer. Non-mapping payloads are
  rejected at the commit merge with a per-payload
  `collections.abc.Mapping` guard BEFORE `dict.update` runs —
  `dict.update` would silently accept an iterable of key-value pairs
  and coerce it into a valid mapping, violating the contract
  enumeration.
- The delivery walk in `schema()` runs **after all filters** over the
  authored doc tree with a surviving-path set + path→node map; the facts
  (including `children`) come from the `DocumentRoot`, never from the
  filtered dict node.
- Broaden the CLI `except ValueError` to `except Exception` — the
  register-facade `ImportError` must convert too; never catch
  `BaseException`.
- Update `tests/hooks/catalog/test_catalog.py`: every 19-count assertion
  → 20 (three sites: the topics, pipeline, and config record tests);
  insert `("schema", "amend_cell", "hard")` into the frozen `expected`
  list of the build-records test (sorted position between
  `("pipeline", "run_created", "soft")` and
  `("statuses", "register_statuses", "soft")`) and into the
  `pre_existing` list of the config record test; add
  `test_schema_amend_cell_record_present` mirroring the config record
  test.
- Update the CLI command docstring's structure block with the `tools` line
  (after `children`) so `--help` documents the extended node.
- Validation per cell: `goga lint` (81 cells, 0 errors), facade import
  check, `pytest tests/schema/hooks tests/schema tests/commands/test_schema.py
  tests/hooks/catalog -x`, and byte-identity of `goga schema` against the
  pre-change output in this repository (no `tools` key anywhere).
