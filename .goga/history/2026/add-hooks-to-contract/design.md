# Design Document: `add-hooks-to-contract`

Design of the code architecture for the contract-amendment checkpoint: a new
hooks zone of the contract domain (`goga/contract/hooks`), the new hard action
record in the platform catalog, and the `goga contract` command as the root
consumer that delivers the checkpoint and composes the contributed tools areas
onto the type nodes of its JSON output.

The specification below covers **what to implement and how**. The
implementation order and task breakdown stay with the planning stage.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/contract/hooks/CODEMANIFEST` — **created**. New cell: the hooks zone
  of the contract domain. Imports `HookRegistry`, `wrap_context`,
  `build_hook_arguments`, `declared_actions` (Types) and `per-tool-delivery`,
  `registering-hooks` (Usages) from `goga/hooks`; local practice `convention`.
  Declares 8 types across 4 flat modules.
- `goga/hooks/catalog/CODEMANIFEST` — **modified**. One additive Requirements
  bullet on `declared_actions`: the contract amendment action record
  (`domain="contract"`, `name="amend_contract"`, `error_class="hard"`).
- `goga/commands/contract/CODEMANIFEST` — **modified**. New Imports block
  from `goga/contract/hooks` (5 Types + the `contract-checkpoints` usage);
  the local Usages key `conventions` renamed to `convention` (same file);
  the global Annotations extended with the `contract-checkpoints` paragraph;
  the `contract` Routine annotation extended with Algorithm steps 5–6, the
  `tools` key in the output-format example, and three new Requirements.

### New Entities

All in `goga/contract/hooks`:

- `CellFacts(path: str, types: list[TypeFacts])` — the comparison facts of
  one cell; the per-cell read view delivered to a subscribed hook.
  Location: `facts.py`.
- `TypeFacts(name: str, signature: FormFacts, properties: list[MemberFacts], methods: list[MemberFacts])` —
  the comparison facts of one declared type. Location: `facts.py`.
- `FormFacts(codemanifest: str, implementation: str | None)` — one compared
  form: the declared string and its extracted counterpart (absent allowed).
  Location: `facts.py`.
- `MemberFacts(name: str, form: FormFacts)` — the compared form of one named
  member (a property or a method). Location: `facts.py`.
- `ContractAmendment(cell: CellFacts)` — the read-and-contribute view of one
  tool for one cell: the delivered facts plus this tool's contribution
  buffer; `contribute(facts)` is the single write channel.
  Location: `amendments.py`.
- `ToolContribution(tool: str, facts: dict[str, dict[str, object]])` — the
  committed contribution of one tool for one cell. Location: `overlay.py`.
- `merge_type_contributions(contributions: list[ToolContribution]) -> tools: dict[str, dict[str, dict[str, object]]]` —
  the deterministic per-type tools-area composition. Location: `overlay.py`.
- `ContractHooks()` — the checkpoint surface of the contract domain;
  `amend_contract(cell: CellFacts) -> tools` delivers the hard
  `contract/amend_contract` action over the platform facade.
  Location: `events.py`.

### Changed Entities

- `declared_actions` (`goga/hooks/catalog`, location `catalog.py`) — the
  returned catalog gains the record
  `Action(domain="contract", name="amend_contract", error_class="hard")`.
  No signature or behavior change: the routine still returns every record
  ordered by domain then name.
- `contract(cells, lang)` (`goga/commands/contract`, location `contract.py`) —
  the command algorithm gains steps 5–6 (checkpoint delivery after the
  built-in comparison of every requested cell; tools-area composition onto
  the type nodes) and the output format gains the `tools` key on type nodes.

### Deleted Entities

None.

### Usages and Annotations Changes

- `goga/commands/contract` — Usages key rename `conventions` → `convention`
  (the reference in the global Annotations follows; the referenced file
  `.goga/usages/conventions.md` is unchanged).
- `goga/commands/contract` — global Annotations: rewritten `convention`
  bullet list (capitalization) and the new `contract-checkpoints` paragraph
  (checkpoint at the comparison moment).
- `goga/commands/contract` — `contract` Routine annotation: Algorithm steps
  5–6; output-format example extended with
  `"tools": { "tool-name": { "fact": "value" } }` plus the presence-rule
  parenthetical; Requirements extended with the tools-area help clause, the
  comparison-precedence clause, the dedup clause, and the
  byte-identical-without-extensions clause.
- `.usages/contract.md` (`goga/commands/contract`) — the output structure
  gains the `tools` key and a five-sentence semantics note.
- `.usages/contract-checkpoints.md` (`goga/contract/hooks`) — **created**;
  the consumer practice for the checkpoint surface.
- `goga/hooks/catalog` — `declared_actions` Requirements gain the contract
  action record bullet (annotations only; no header change).

## Applied Fixes

### Fixed CODEMANIFEST Defects

None. Phase 3 validation found no defects:

- `goga lint` — 82 cells, 0 errors (structure, casing, signature forms,
  `location` flatness, annotation reference resolution).
- `goga schema` — the dependency map matches the intended graph exactly:
  `goga/hooks` ← `goga/contract/hooks` ← `goga/commands/contract`; no
  cycles; the four pre-existing edges of `goga/commands/contract`
  unchanged.
- Four-dimension consistency audit (interface ↔ type, type ↔ mutation,
  interface ↔ interface, annotations ↔ entity) — no inconsistency; no
  mutations or embeddings are used anywhere in the change.
- Usages resolution — every referenced practice exists and was read:
  `convention` (`.goga/usages/conventions.md`), `click`, `beautiful_json`,
  `per-tool-delivery` and `registering-hooks` (`goga/hooks/.usages/`),
  `contract-checkpoints` (`goga/contract/hooks/.usages/`), plus the
  pre-existing `loading`, `use_contract`, `project-configuration`,
  `checkpoints`.

No CODEMANIFEST edits were proposed, so no user approval round was needed
(Phase 3 Step 4 skipped per its no-defects rule).

Two lint-forced deviations from the original architecture plan were already
applied and validated during the apply-architecture stage (recorded here for
the implementer's context; they are now part of the contract):

- The zone practice file is named `contract-checkpoints.md` (imported as
  `contract-checkpoints`), not `checkpoints.md` — the linter's
  duplicate-usage-import rule compares pre-alias names, and
  `goga/commands/contract` already imports `checkpoints` from
  `goga/config/hooks`.
- Two `tools` references in the `contract` Routine annotation are plain text
  ("under the tools key"), not backtick links — every backtick link must
  resolve to a name of the manifest context, and `tools` is a JSON key, not
  a declared entity.

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
                       CLI: goga contract <cells> [--lang]
                                     |
                                     v
                    goga/commands/contract/contract.py::contract
                        |  1. load_project_config()            (goga/config)
                        |  2. ConfigHooks().amend_config()     (goga/config/hooks)   [existing]
                        |  3. AST(".").load()                  (goga/ast)
                        |  4. per cell: contract_logic()       (goga/contract)
                        |            -> compare dict per normalized path
                        |  5. hooks = ContractHooks()           (goga/contract/hooks) [new]
                        |     for each unique normalized path (first-request order):
                        |       _build_cell_facts(path, compare) -> CellFacts
                        |       hooks.amend_contract(cell=facts) -> tools
                        |  6. result[path][type]["tools"] = area   (iff non-empty)
                        v
                     stdout: JSON (beautiful_json)
                                     ^
        goga/contract/hooks (new zone)                          |
        ------------------------------                           |
        ContractHooks.amend_contract(cell)                      |
          |  declared_actions()  ---------------> goga/hooks/catalog    [new record]
          |  registry.build_once() / subscriptions_for("contract","amend_contract")
          |                     -----------------> goga/hooks/registry  (per-surface run registry)
        per tool (enumeration order):
          ContractAmendment(cell=_read_only_view(cell))         |
            wrap_context(view) ---------------------------------> goga/hooks/dispatch
            build_hook_arguments(hook, proxy, self_context) ---> goga/hooks/dispatch
            hook(context=view)  -> view.contribute({type: {fact: value}})
        per tool commit:
          _commit_tool_buffer(tool, cell.path, declared_names, pending)
            -> merged dict[str, dict[str, object]]   (structural + address check)
          ToolContribution(tool, merged)
        merge_type_contributions(contributions)
          -> {type_name: {tool: {fact: value}}}  -----------------+
                                                                   |
        facts.py: CellFacts / TypeFacts / FormFacts / MemberFacts  |
          (built by the command from its own comparison data) -----+
```

### Data Flows

**Flow 1 — comparison to checkpoint (per cell, steps 4–5).**

Participating: `contract` command loop → `compare` dict →
`_build_cell_facts` → `CellFacts`/`TypeFacts`/`FormFacts`/`MemberFacts` →
`ContractHooks.amend_contract`.

1. The existing loop resolves each requested cell path to its document,
   extracts the implemented contracts, and builds the comparison dict
   `compare = {type_name: {"signature": {...}, "properties": {...}, "methods": {...}}}`
   (routines carry only `signature`), stored under
   `result[os.path.normpath(doc.path)]`.
2. After the loop, for each unique normalized path in first-request order
   (the insertion order of `result` — a re-requested path overwrites the
   same value and does not reorder the dict), `_build_cell_facts` projects
   the comparison dict into facts:
   `name` ← type key; `signature` ← `FormFacts(**compare[name]["signature"])`;
   `properties`/`methods` ← `[MemberFacts(name=n, form=FormFacts(**m)) for n, m in node.get(member_kind, {}).items()]`.
3. The facts are handed to `amend_contract(cell=facts)`; the returned
   mapping flows into Flow 3.

The projection is **exactly** the comparison data — the authored and
extracted strings the output already shows, nothing else. This makes the
delivered view the authored projection: identical for every tool, one shape
for every implementation language.

**Flow 2 — checkpoint delivery (per cell, inside `amend_contract`).**

Participating: `ContractHooks` → `HookRegistry` (build once per surface) →
`wrap_context`/`build_hook_arguments` (dispatch) → tool hooks →
`ContractAmendment.contribute` → `_commit_tool_buffer` →
`ToolContribution` → `merge_type_contributions`.

1. `amend_contract` resolves the address `contract.amend_contract` against
   `declared_actions()` (unknown address → `ValueError`, an emitting-side
   programming error).
2. Subscriptions of the address are grouped per tool in enumeration order.
3. Per tool: a fresh read-only view of the cell facts is built
   (`_read_only_view`), wrapped by `wrap_context`, and each hook of the
   tool is called with `build_hook_arguments` — a hook declaring `context`
   receives the view, a hook declaring `self` receives the tool's isolated
   context. Reads pass through; attribute writes on the view raise.
4. Hooks buffer contributions through `contribute`; payloads are stored
   verbatim (no validation inside the view).
5. After the last hook of the tool: `_commit_tool_buffer` merges the
   payloads (two-level, fact-wise), validates the JSON-map shape and the
   type addresses, and returns the merged contribution; an empty merge
   commits nothing.
6. `merge_type_contributions` composes the per-type tools area; the mapping
   returns to the command.

**Flow 3 — tools-area composition (step 6).**

Participating: command → `result` structure → `json.dumps` (beautiful_json).

1. For each `type_name, area` in the returned mapping:
   `result[path][type_name]["tools"] = area`.
2. The key lands next to the fixed keys (`signature`, and for entities
   `properties`/`methods`) — on routine nodes as well.
3. `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)` —
   the structural check at the commit point guarantees serializability;
   `sort_keys=True` keeps the output deterministic.

### Entity Dependencies

- `goga/contract/hooks` depends on `goga/hooks` only (Types:
  `HookRegistry`, `wrap_context`, `build_hook_arguments`,
  `declared_actions`; Usages: `per-tool-delivery`, `registering-hooks`).
  The zone does **not** import the extended domain `goga/contract` — the
  read view is built from the facts the caller passes. (Python-level note:
  importing the subpackage `goga.contract.hooks` necessarily executes
  `goga/contract/__init__.py` first — package semantics, identical to the
  `goga/config/hooks` precedent; the zone modules themselves never import
  `..dispatcher`, `..python`, or any extractor.)
- `goga/commands/contract` imports from `goga/contract/hooks` exactly the
  five names it uses (`ContractHooks`, `CellFacts`, `TypeFacts`,
  `FormFacts`, `MemberFacts`). `ContractAmendment`, `ToolContribution`,
  and `merge_type_contributions` stay internal to the zone — the command
  never touches them.
- `goga/hooks/catalog` gains a data record; its consumers
  (`goga/hooks/tools`, `goga/hooks/dispatch`, all zones) are unaffected —
  the record is additive and the catalog is data only.
- Initialization order at runtime: `ContractHooks()` construction is cheap
  (no enumeration); the registry builds lazily inside the first
  `amend_contract` call; the command constructs the surface once and reuses
  it across all cells (the `hooks = SchemaHooks()` precedent of the schema
  walk), so the contract checkpoints enumerate the tool packages once per
  run whatever the number of cells. The config checkpoint of the same
  command runs over its own `ConfigHooks` surface — the established
  per-surface registry pattern of the platform (the topics flows compose
  `ConfigHooks` and `TopicHooks` the same way).

---

## Code Stack Trace

Traced against the actual sources: `goga/commands/contract/contract.py`
(current implementation), `goga/schema/hooks/*.py` and
`goga/config/hooks/*.py` (structural precedents), `goga/hooks/registry/state.py`,
`goga/hooks/dispatch/delivery.py`, `goga/hooks/catalog/catalog.py`,
`goga/ast/nodes/body.py`, `goga/contract/dispatcher.py`.

### Trace: `contract(cells, lang)` — the CLI command (full run)

#### Chain

1. **Input**: `goga contract goga/config goga/hooks` invoked through the
   click app; `cells: tuple[str, ...]` from `nargs=-1`, `lang: str | None`
   from `--lang`. → checkpoint: argument surface unchanged by this change
   (`--lang` and `cells` keep their shapes). **passed**
2. **Step** (existing, 1): `load_project_config()` → `ProjectConfig`; the
   config-amendment checkpoint `ConfigHooks().amend_config(config=authored)`
   → `ConfigOverlay`; failures (`FileNotFoundError`, `KeyError`,
   `ValueError`, `ImportError`, `yaml.YAMLError`) wrap into
   `click.ClickException`. `overlay.summary_lines` print to stderr.
   → checkpoint: unchanged by this change. **passed**
3. **Step** (existing, 2–3): language resolution (`lang` or
   `overlay.config.language`); `AST(".")` + `.load()` per the `loading`
   practice. → checkpoint: unchanged. **passed**
4. **Step** (existing, 4): per requested path — `ast_obj.document(path)`
   (`DocumentNotFoundError` → stderr error + `ctx.exit(1)`),
   `contract_logic(lang, path)` (`ModuleNotFoundError`/other → stderr error
   + `ctx.exit(1)`), `_build_cell_compare(...)` → `compare`;
   `result[os.path.normpath(doc.path)] = compare`.
   → checkpoint: a re-requested path (different spelling, same normalized
   document path) overwrites the identical value; dict insertion order
   keeps first-request order — the dedup source for step 5 is `result`
   itself, no extra structure. **passed**
   → checkpoint (contract interaction): the failure channels of step 4 all
   fire **before** any hook runs (the checkpoint loop is strictly after
   this loop) — existing failures keep their precedence per the
   Requirements. **passed**
5. **Step** (new, 5): `hooks = ContractHooks()`; for each `path in result`
   (unique normalized paths, first-request order):
   `_build_cell_facts(path, result[path])` → `CellFacts`;
   `tools = hooks.amend_contract(cell=facts)` with
   `except (ValueError, ImportError) as exc: raise click.ClickException(str(exc)) from exc`.
   → checkpoint (type flow): `compare` values are `{"codemanifest": str, "implementation": str | None}`
   — `FormFacts(codemanifest: str, implementation: str | None)` accepts
   them positionally-by-key exactly (`FormFacts(**pair)`); entity nodes
   carry `properties`/`methods` dicts, routine nodes do not —
   `node.get("properties", {})` yields `[]` for routines, matching the
   `TypeFacts` requirement "empty for a routine". **passed**
   → checkpoint (interface alignment): `amend_contract` declares
   `cell: CellFacts` and returns `dict[str, dict[str, dict[str, object]]]`;
   the command passes `CellFacts` and consumes the mapping keyed by
   declared type names. **passed**
   → checkpoint (error alignment): the zone raises `ValueError` (hard
   action failure — crashed hook, malformed contribution, bad address) and
   lets `ImportError` (broken tool facade at `build_once`) propagate —
   exactly the two types step 5 names; `ClickException` exits code 1 with
   `Error: <message>` on stderr, no stdout output before it (the JSON dump
   happens only after the loop). **passed**
6. **Step** (new, 6): for each `type_name, area in tools.items()`:
   `result[path][type_name]["tools"] = area`.
   → checkpoint: `merge_type_contributions` only returns types with at
   least one fact — the `tools` key never lands as `{}`; a type with no
   contribution stays untouched (key absent). **passed**
   → checkpoint: an addressed name is guaranteed declared (the address
   check validated it against `cell.types`, which mirrors `result[path]`
   keys — both are the CODEMANIFEST body type names), so the
   `result[path][type_name]` lookup cannot miss. **passed**
7. **Output**: `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)`
   (the `beautiful_json` pattern) → `click.echo(json_str)` — stdout carries
   nothing but the JSON structure.
   → checkpoint: contributions are plain `dict`/`str`/`int`/`bool`/`None`/
   finite `float`/`list` values (the structural check), so serialization
   cannot fail. **passed**

#### Checkpoint Summary

- Argument/output surface stability with zero extensions: **passed** — with
  no tool packages installed the delivery returns `{}` and the loop body
  never runs; output is byte-identical to the current command.
- Comparison-before-hooks precedence: **passed** — two sequential loops.
- Dedup in first-request order: **passed** — `dict` insertion order of
  `result`.
- Type flow command ↔ zone: **passed** — facts mirror the comparison dict
  one-to-one.

### Trace: `ContractHooks.amend_contract(cell)`

#### Chain

1. **Input**: `cell: CellFacts` built by the caller from its own
   comparison data; `self._registry` is `None` on the first call.
   → checkpoint: the caller passed resolved values; the surface reads no
   configuration, git, or files. **passed**
2. **Step**: `self._ensure_registry()` — first call creates
   `HookRegistry()` and runs `build_once()` (enumerates installed
   `goga_tool_*` packages, runs their `register_hooks` callbacks; a broken
   facade raises `ImportError` naming the package — the single fatal
   case); later calls return the cached registry.
   → checkpoint (platform API): `build_once` is idempotent per instance —
   N cells share one enumeration. **passed**
3. **Step**: address resolution —
   `next((e for e in declared_actions() if e.domain == "contract" and e.name == "amend_contract"), None)`;
   `None` → `ValueError("unknown hook action: contract.amend_contract")`.
   → checkpoint (catalog): the new record must exist in `catalog.py`, else
   every delivery fails — the catalog change is a hard prerequisite of this
   trace step. **passed** (with the planned record added)
4. **Step**: `declared_names = {t.name for t in cell.types}`; subscriptions
   `registry.subscriptions_for("contract", "amend_contract")` grouped per
   tool (`groups.setdefault(sub.tool, []).append(sub)`) in enumeration
   order. An empty group set → `contributions == []` → step 7 returns `{}`.
5. **Step** (per tool): `amendment = ContractAmendment(cell=_read_only_view(cell))`;
   `proxy = wrap_context(amendment)`; for each subscription:
   `sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))`
   inside `try`; any `Exception` →
   `ValueError(f"hook {sub.name} of tool {tool} failed on contract.amend_contract at {cell.path}: {reason}")`.
   → checkpoint (platform API): `wrap_context` resolves reads and calls,
   blocks writes; `build_hook_arguments` injects only declared names
   (`context`, `self`). **passed**
   → checkpoint (mutual blindness): `_read_only_view` rebuilds every list
   (`cell.types`, `properties`, `methods`) — an in-place `append` by one
   tool's hook stays local to that tool's view; `FormFacts`/`MemberFacts`
   carry only `str` fields (fully immutable, safe to share).
   **passed**
6. **Step** (per tool commit): `merged = _commit_tool_buffer(tool, cell.path, declared_names, amendment._pending)`;
   `if merged: contributions.append(ToolContribution(tool=tool, facts=merged))`.
   → checkpoint: see the `_commit_tool_buffer` trace below. **passed**
7. **Output**: `return merge_type_contributions(contributions)` —
   `{type_name: {tool: {fact: value}}}`, `{}` when nothing committed.
   → checkpoint: the shape matches the declared return type
   `dict[str, dict[str, dict[str, object]]]` and the command's step 6
   consumption. **passed**

#### Checkpoint Summary

- Address-declared, registry-once, never-skip-a-subscriber: **passed**.
- Hard-stop semantics at the first failing tool with the tool, the action,
  and the cell path in the message: **passed** — matches the catalog record
  and the schema-zone message format (plus the offending type name for a
  bad address, added in `_commit_tool_buffer`).
- The zone never prints: **passed** — every outcome is a return value or an
  exception; the caller owns all output.

### Trace: `ContractAmendment.contribute(facts)`

#### Chain

1. **Input**: a tool hook calls `context.contribute(facts)` with
   `facts: dict[str, dict[str, object]]` — declared type name → the tool's
   fact mapping for that type. The call arrives through the
   `wrap_context` proxy (method call — allowed).
2. **Step**: `self._pending.append(facts)` — stored verbatim; no
   validation, no interpretation, no merge here.
   → checkpoint: the buffer is `init=False, repr=False` — invisible in
   construction and repr; the hook sees only `cell` and `contribute`.
   **passed**
   → checkpoint: "changes nothing until the delivery commits it" — nothing
   outside the view is touched. **passed**
3. **Output**: `None`; the payload waits for the tool's commit point.

#### Checkpoint Summary

- Verbatim buffering matches the schema-zone `CellAmendment.contribute`
  precedent: **passed** — structural failures are named at the commit
  point, naming this tool.
- Merge semantics (fact-wise within a type) live in the commit point, not
  here: **passed** — keeps the view free of validation logic.

### Trace: `_commit_tool_buffer(tool, cell_path, declared_names, pending)` (zone-internal helper, events.py)

#### Chain

1. **Input**: the tool identity, the delivered cell's normalized path, the
   declared type-name set, and the view's buffered payloads.
2. **Step** (merge): `merged: dict[str, dict[str, object]] = {}`; per
   payload: `isinstance(payload, Mapping)` else structural failure
   (`ValueError("a contribution payload is not a mapping: ...")` — never a
   silent `dict.update` coercion of an iterable of pairs); per
   `type_name, facts` in the payload: `isinstance(facts, Mapping)` else
   structural failure, and `isinstance(type_name, str)` else structural
   failure (`non-string key {type_name!r} at the merged contribution` —
   the same message `_check_json_map` would produce, raised before the
   `setdefault` so an exotic `Mapping` yielding an unhashable key can
   never crash the merge with a raw `TypeError` that would escape the
   `(ValueError, RecursionError)` wrap); then
   `merged.setdefault(type_name, {}).update(facts)`.
   → checkpoint: the two-level merge realizes the contract — "a repeated
   type address merges its facts; for one type, a later write replaces an
   earlier one on fact-name conflict" — and is total: every non-string
   key failure surfaces as the structural `ValueError`, never an
   uncaught `TypeError`. **passed**
3. **Step** (structural check): `if merged: _check_json_map(merged, "the merged contribution")`
   — plain `dict`s only, string keys only, non-empty mapping at every
   level, values `dict`/`list|tuple`/`str`/`int`/`bool`/`None`/finite
   `float`, cycle-guarded (the schema-zone validator, applied verbatim).
   → checkpoint: a payload `{"A": {}}` fails as "empty mapping at the
   merged contribution.A"; the empty outer payload `{}` merges nothing and
   never reaches the check — "an empty outer mapping contributes
   nothing". **passed**
4. **Step** (address check): the first `type_name` of `merged` (insertion
   order = enumeration order, deterministic) not in `declared_names` →
   `ValueError` naming the offending type.
   → checkpoint: "a contribution addressed to a type the cell does not
   declare" is the same hard failure, with the type name in the message —
   exactly the catalog record's clause. **passed**
   → checkpoint (edge): a cell with no declared types has
   `declared_names == set()` — any non-empty contribution fails here; the
   checkpoint over empty facts is still delivered (hooks run, may read,
   must contribute nothing). **passed**
5. **Output**: `merged` (possibly `{}` — commits nothing); failures raise
   `ValueError(f"tool {tool} failed on contract.amend_contract at {cell_path}: ...")`
   — the tool, the action, and the cell path in every message, the
   offending type name for a bad address.

#### Checkpoint Summary

- Commit granularity is the tool: **passed** — the buffer merges only
  after every hook of the tool returned.
- Deterministic first-failure naming: **passed**.

### Trace: `merge_type_contributions(contributions)`

#### Chain

1. **Input**: committed `ToolContribution`s in enumeration order.
2. **Step**: `tools: dict[str, dict[str, dict[str, object]]] = {}`; per
   contribution, per `type_name, facts` in `contribution.facts.items()`:
   `if facts: tools.setdefault(type_name, {})[contribution.tool] = facts`.
   → checkpoint: a tool appears on a type iff it wrote at least one fact
   for that type (empty areas skipped — defensive; the commit point cannot
   produce them). **passed**
3. **Output**: `tools` — a new mapping; inputs untouched.
   → checkpoint: deterministic (same contributions → same mapping),
   pure (no mutation), no filesystem access, no re-validation (it happened
   at the commit point). **passed**

#### Checkpoint Summary

- Composition shape equals the `tools` key structure of the command output
  example: **passed**.

### Trace: `declared_actions()` (catalog, changed data)

#### Chain

1. **Input**: none.
2. **Step**: returns `sorted(_DECLARED_ACTIONS, key=lambda a: (a.domain, a.name))`
   — a new list of frozen records; the list constant gains
   `Action(domain="contract", name="amend_contract", error_class="hard")`.
   → checkpoint: sorted by domain then name — `contract` lands between
   `config` and `onboarding` in the returned order; the physical position
   of the new entry in the constant is irrelevant to output. **passed**
   → checkpoint: additive only — no published record rewritten, matching
   the catalog's Annotations. **passed**
3. **Output**: the complete catalog including the new record; the
   `amend_contract` address resolution of the new zone succeeds.

#### Checkpoint Summary

- No consumer of the catalog observes a behavioral change besides the new
  record: **passed** — `goga hooks` inspection, registration validation,
  and every zone's address resolution are unaffected.

### Trace: `_build_cell_facts(path, compare)` (command-internal helper)

#### Chain

1. **Input**: the normalized cell path and the cell's comparison dict from
   `result`.
2. **Step**: per `name, node in compare.items()` build
   `TypeFacts(name=name, signature=FormFacts(**node["signature"]), properties=[...], methods=[...])`
   with `MemberFacts(name=member_name, form=FormFacts(**member_pair))` from
   `node.get("properties", {})` / `node.get("methods", {})`; wrap into
   `CellFacts(path=path, types=types)`.
   → checkpoint: every value is already `str` or `None` (the comparison
   built them from `node.signature`/`node.type` strings and extracted
   signatures) — no transformation, a pure projection. **passed**
3. **Output**: `CellFacts` handed to `amend_contract`.

#### Checkpoint Summary

- The delivered view is the comparison the output shows: **passed** —
  identical for every tool, no per-language projection.

---

## Algorithm Design

### `CellFacts`, `TypeFacts`, `FormFacts`, `MemberFacts` — `facts.py`

**Responsibility**: the per-cell comparison read view — pure data the
command constructs from its own comparison values; nothing is read inside.

**Algorithm** (construction contract):

```
1. The caller passes resolved values — path (str), types (list[TypeFacts]) —
   → frozen kw_only dataclasses; lists are the only mutable part (closed
   per tool by the delivery view, see events.py)
2. TypeFacts carries name + signature: FormFacts + properties/methods:
   list[MemberFacts] (empty lists for a routine)
   → each MemberFacts carries a member name + form: FormFacts
3. FormFacts carries codemanifest: str + implementation: str | None
   → pure strings; no parsed structures
```

**Structure**: four `@dataclass(frozen=True, kw_only=True)` records with
Google-style docstrings (Args: per field, Requirements: where the manifest
states them), mirroring `goga/schema/hooks/facts.py`. Module docstring
names all four records and their zone role. No imports beyond
`dataclasses`.

**Errors**: none — pure data.

**Edge cases**:
- a cell whose manifest body is empty → `types=[]` (delivered; any
  non-empty contribution for it is the unknown-address hard failure).
- a member with no implementation counterpart →
  `FormFacts(codemanifest=..., implementation=None)`.

### `ContractAmendment` — `amendments.py`

**Responsibility**: the read-and-contribute view one tool receives at the
checkpoint: the delivered facts (read-only) plus this tool's buffer.

**Algorithm**:

```
1. Construction: cell: CellFacts (kw_only); _pending: list (init=False,
   default [], repr=False)
2. contribute(facts):
   - append facts verbatim to _pending        → no validation, no merge
   - an empty outer mapping is stored like any other — it merges to
     nothing at the commit point
```

**Structure**: `@dataclass(kw_only=True)` (mutable — it owns a buffer);
module docstring mirroring `goga/schema/hooks/amendments.py`.

**Errors**: none raised here — structural failures surface at the commit
point naming this tool.

**Edge cases**:
- repeated `contribute` for the same type — payloads merge fact-wise at the
  commit (later write wins on fact-name conflict).
- `contribute({})` — contributes nothing, silently.

### `ToolContribution` and `merge_type_contributions` — `overlay.py`

**Responsibility**: the committed-contribution pairing and the
deterministic per-type tools-area composition.

**Algorithm** (`merge_type_contributions`):

```
1. FOR each contribution IN enumeration order:
2.   FOR each (type_name, facts) IN contribution.facts:
3.     IF facts is empty: SKIP        (defensive — cannot occur post-commit)
4.     tools.setdefault(type_name, {})[contribution.tool] = facts
5. RETURN tools                       ({} when nothing committed)
```

**Structure**: `ToolContribution` — `@dataclass(frozen=True, kw_only=True)`
with `tool: str` and `facts: dict[str, dict[str, object]]`;
`merge_type_contributions` — a module-level routine with the docstring
algorithm of the manifest. Structural validation is not here.

**Errors**: none.

**Edge cases**:
- empty input list → `{}`.
- two contributions addressing the same type → both tools appear in that
  type's area, in enumeration order (JSON `sort_keys` normalizes the final
  serialization).

### `ContractHooks` — `events.py`

**Responsibility**: the checkpoint surface — the staged per-tool delivery
of the hard `contract/amend_contract` action over the platform facade.

**Algorithm** (`amend_contract`):

```
1. registry = self._ensure_registry()
   → build_once on first use; ImportError (broken facade) propagates
2. record = declared_actions() where domain="contract", name="amend_contract"
   → None: raise ValueError("unknown hook action: contract.amend_contract")
3. declared_names = {t.name for t in cell.types}
4. groups = subscriptions_for("contract", "amend_contract") grouped by tool
5. FOR (tool, subscriptions) IN groups (enumeration order):
   a. amendment = ContractAmendment(cell=_read_only_view(cell))
   b. proxy = wrap_context(amendment)
   c. FOR sub IN subscriptions:
        TRY sub.hook(**build_hook_arguments(sub.hook, proxy,
                                            registry.self_context(tool)))
        EXCEPT Exception as reason:
          raise ValueError(f"hook {sub.name} of tool {tool} failed on "
                           f"contract.amend_contract at {cell.path}: {reason}")
        → first failure stops the walk; the tool's view (and buffer) dies
          with it
   d. merged = _commit_tool_buffer(tool, cell.path, declared_names,
                                   amendment._pending)
   e. IF merged: contributions.append(ToolContribution(tool, merged))
6. RETURN merge_type_contributions(contributions)
```

**Zone-internal helpers** (module-level, private):

- `_read_only_view(cell) -> CellFacts` — rebuild `CellFacts` with fresh
  `types` list; each `TypeFacts` rebuilt with fresh `properties`/`methods`
  lists; `FormFacts`/`MemberFacts` shared (str-only fields — immutable).
  The mutual-blindness guarantee: a tool's in-place list write stays local
  to its own view.
- `_nested_scope(value, where, ancestors)` — cycle guard of the structural
  validator (a container holding an ancestor → `ValueError`; a container
  shared twice in different places stays valid).
- `_check_json_map(value, where, ancestors)` — the JSON-map shape
  validator, applied verbatim from the schema zone: plain `dict` with
  string, keys non-empty at every level; values dict (recursive), list or
  tuple of checked items, or a JSON scalar (`str`, `int`, `bool`, `None`,
  finite `float`); everything else rejected. Explicit recursion — not a
  `json.dumps` probe (dumps coerces non-string keys and accepts
  `nan`/`infinity`).
- `_commit_tool_buffer(tool, cell_path, declared_names, pending) -> dict[str, dict[str, object]]` —
  the tool commit point (trace above): two-level guarded merge (payload
  `Mapping` guard, per-type `Mapping` guard, per-address `str` guard — the
  last closes the unhashable-key `TypeError` escape) → JSON-map
  check → first-undeclared-address check → return the merged mapping.
  Failure messages:
  `f"tool {tool} failed on contract.amend_contract at {cell_path}: structurally malformed contribution ({reason})"`
  and
  `f"tool {tool} failed on contract.amend_contract at {cell_path}: contribution addresses undeclared type {type_name}"`.

**Structure**: `class ContractHooks` with `__init__` (`self._registry:
HookRegistry | None = None`), `_ensure_registry`, `amend_contract` — the
docstrings carry the manifest algorithm/requirements/raises verbatim in
style; module docstring mirroring `goga/schema/hooks/events.py`. Imports:
`math`, `collections.abc.Mapping`, `typing.Any`,
`from ...hooks import HookRegistry, build_hook_arguments, declared_actions,
wrap_context`, and the zone's own `ContractAmendment`, `CellFacts`/
`TypeFacts` (for the view builder), `ToolContribution`,
`merge_type_contributions`. Relative imports throughout.

**Errors**:
- `ValueError` — unknown address (emitting-side bug), a crashed hook (names
  hook, tool, action, cell path, reason), a malformed contribution (names
  tool, action, cell path, detail), a bad address (adds the type name) →
  the command wraps into `click.ClickException` → the user sees one clean
  stderr line, exit code 1.
- `ImportError` — broken tool facade at `build_once` (names the package) →
  the same wrap.
- `RecursionError` — a nesting too deep for the validator is caught with
  the structural failures and re-raised as the same `ValueError`.

**Edge cases**:
- no subscriptions / no tool packages → `{}`; the delivery is unobservable.
- a tool whose every hook returned but buffered nothing → commits nothing,
  silently.
- two hooks of one tool, first contributes, second crashes → the tool
  commits nothing (view discarded) — the crash is the walk-stopping
  failure.
- `ContractHooks()` never constructed cheaply-but-unused enumerates
  nothing; with an empty `cells` request the command builds the surface
  and never calls it.

### `declared_actions` — `goga/hooks/catalog/catalog.py`

**Responsibility**: the single source of known addresses; gains the
contract record.

**Algorithm**: append
`Action(domain="contract", name="amend_contract", error_class="hard"),`
to `_DECLARED_ACTIONS` (placement in the constant is stylistic — the
return sorts by `(domain, name)`; the natural spot is next to the other
hard amendment records). Nothing else changes: `Action` and
`declared_actions` docstrings stay as they are.

**Errors**: none.

**Edge cases**: none new.

### `contract` command — `goga/commands/contract/contract.py`

**Responsibility**: the root consumer — comparison, checkpoint delivery,
tools composition, output.

**Changes**:

1. **Imports** — add
   `from ...contract.hooks import CellFacts, ContractHooks, FormFacts, MemberFacts, TypeFacts`.
2. **New helper** `_build_cell_facts(path: str, compare: dict) -> CellFacts`
   (module-level, private; docstring per project conventions) — the pure
   projection of the comparison dict into facts (trace above).
3. **Delivery block** after the existing comparison loop:

```
hooks = ContractHooks()
for path in result:                       # unique, first-request order
    try:
        tools = hooks.amend_contract(cell=_build_cell_facts(path, result[path]))
    except (ValueError, ImportError) as exc:
        # Hard action failure or broken tool facade — the same clean
        # user-facing error as the config checkpoint, never a traceback.
        raise click.ClickException(str(exc)) from exc
    for type_name, area in tools.items():
        result[path][type_name]["tools"] = area   # never an empty object
```

4. **Command docstring/help** — extend the per-cell JSON description with
   the `tools` key: present on a type node exactly when at least one
   installed tool package contributed at least one fact for that type
   through the contract amendment checkpoint; each inner key is the
   contributing tool's identity (the Requirements clause "command help
   must explain the response structure, including the tools-area
   semantics").

**Errors**: only the new checkpoint wrap (both types → `ClickException`,
exit 1, stderr; stdout stays clean — the dump happens after the loop).

**Edge cases**:
- zero cells requested → `result == {}` → no delivery → `{}` output
  (unchanged behavior).
- a path spelled two ways in one invocation → compared twice (identical
  value), checkpoint delivered once.
- `--lang` still wins over the effective configuration (unchanged).

---

## Cross-cutting Concerns

- **Error handling**: the action is hard — the first failing tool stops
  the command. All failure channels end as one clean stderr line:
  `Error: hook <name> of tool <tool> failed on contract.amend_contract at <path>: <reason>`
  (or the malformed-contribution / bad-address / package-import variants)
  via `ValueError` → `click.ClickException`. Never a raw traceback, never
  partial stdout. Existing per-cell failures (document not found, package
  not importable) keep their precedence — they complete before any hook
  runs. Soft-failure machinery (warn-and-skip) is not used: the catalog
  record is hard.
- **Validation**: exactly one place — the tool commit point of the
  delivery. Rules: payload is a `Mapping`; each per-type value is a
  `Mapping`; the merged buffer satisfies the JSON-map shape (plain dicts,
  string keys, non-empty at every nesting level, JSON scalars / lists /
  tuples, finite floats, no cycles); every addressed type is declared in
  the delivered cell. `contribute` stores verbatim; the command performs
  no contribution validation.
- **Logging**: the zone and the command print nothing about the
  checkpoint; the platform logs registration rejections (existing
  behavior). The command's stderr carries the config amendment summary
  lines (existing) and errors only.
- **Caching**: one lazily built `HookRegistry` per `ContractHooks`
  instance, shared across every cell of the run — the enumeration and the
  `register_hooks` callbacks run once whatever the number of cells (the
  `build_once` flag makes repeated builds no-ops). Nothing is cached
  across runs; registration is never cached across processes.
- **Concurrency**: single-threaded CLI execution; no thread-safety
  requirements (identical to every existing zone). The frozen facts
  records and the per-tool fresh views make the delivery free of
  cross-tool shared mutable state.

---

## Usages Analysis

### `convention`

- **What it provides**: the project's code, REPL, testing, and
  data-model rules (docstring style, dataclass conventions, test layout,
  pytest/ruff gates).
- **Where used**: every annotation of the three manifests; the zone's
  records, views, and routines follow its data-model and docstring rules.
- **Why chosen**: the project-wide practice every cell declares.
- **How exactly**: `@dataclass(frozen=True, kw_only=True)` for pure
  records; Google-style docstrings with `Args:`/`Requirements:`;
  `tests/<package>/` mirror layout; `pytest`/`ruff` gates.

### `click`

- **What it provides**: the CLI framework pattern — command decoration,
  options, `ClickException`, `click.echo(err=True)`.
- **Where used**: the `contract` command (existing surface; the new
  checkpoint wrap reuses `click.ClickException`).
- **Why chosen**: the command layer practice of the project.
- **How exactly**: `@click.command()`, `@click.argument("cells", nargs=-1)`,
  `@click.option("--lang", default=None)`, `@click.pass_context`.

### `beautiful_json`

- **What it provides**: the canonical JSON dump —
  `json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`.
- **Where used**: the command's output step.
- **Why chosen**: deterministic, diff-stable output; the structural check
  guarantees the contributions serialize under it.
- **How exactly**: applied once to the finished `result` (fixed keys and
  tools areas together).

### Imported Usages

- `per-tool-delivery` from `goga/hooks` — the staged delivery loop of the
  amendment checkpoint: its loop skeleton, primitives
  (`HookRegistry`, `subscriptions_for`, `self_context`, `wrap_context`,
  `build_hook_arguments`), and tool-grouped commit apply as written; the
  hard variant raises instead of the practice's soft-sketch `continue`.
  Path: `goga/hooks/.usages/per-tool-delivery.md`.
- `registering-hooks` from `goga/hooks` — the hook signature (`self`,
  `context`), the `register_hooks` facade callback, and the failure
  behavior behind the checkpoint (a broken package import is the only
  fatal case). Path: `goga/hooks/.usages/registering-hooks.md`.
- `contract-checkpoints` from `goga/contract/hooks` — the consumer
  practice the command follows: run the built-in comparison first, walk
  unique normalized paths in first-request order, build facts from the
  command's own comparison data, place each returned tools area on its
  type's node, wrap ValueError/ImportError into the clean command error.
  Path: `goga/contract/hooks/.usages/contract-checkpoints.md`.
- `loading` from `goga/ast` — the AST load/document lookup of step 3–4
  (pre-existing usage, unchanged). Path: `goga/ast/.usages/loading.md`.
- `use_contract` (alias of `contract`) from `goga/contract` — the language
  dispatcher `contract(lang, cell_path)` of step 4 (pre-existing,
  unchanged). Path: `goga/contract/.usages/contract.md`.
- `project-configuration` from `goga/config` — the authored configuration
  load of step 1 (pre-existing, unchanged).
  Path: `goga/config/.usages/project-configuration.md`.
- `checkpoints` from `goga/config/hooks` — the config amendment checkpoint
  of step 1 (pre-existing, unchanged).
  Path: `goga/config/hooks/.usages/checkpoints.md`.

Every imported practice is referenced in at least one annotation of its
importing manifest (verified by the lint pass); the imported usages create
traceable cross-cell links, not contractual obligations — the zone's own
contract decides how failures surface (here: raise `ValueError`, let
`ImportError` propagate, never print).

---

## `.usages/` Update

### Cell: `goga/contract/hooks`

#### Existing Files — Consistency

- **`contract-checkpoints`** → `goga/contract/hooks/.usages/contract-checkpoints.md`
  - Status: **current** (created with the manifest in the apply stage;
    re-verified in this design).
  - Additions needed: none — the described surface (`ContractHooks()`),
    the delivery loop (unique normalized paths, first-request order,
    facts built from the caller's comparison data, `tools` placed iff
    non-empty), the failure semantics (hard action, ValueError/ImportError
    wrap, no partial stdout), and the output-shape paragraph match the
    CODEMANIFEST and this design exactly.
  - Updates needed: none.

#### New Files (if any)

None — one file covers the zone's single functional domain (the contract
amendment checkpoint). No `CODEMANIFEST` `Usages` entry points at the
cell's own `.usages/` (consumer documentation is not a requirement
source).

### Cell: `goga/commands/contract`

#### Existing Files — Consistency

- **`contract`** → `goga/commands/contract/.usages/contract.md`
  - Status: **current** (updated with the manifest in the apply stage;
    re-verified: the `tools` key in the output structure and the
    presence-rule note match the manifest's output format and this
    design's step 6).
  - Additions needed: none.
  - Updates needed: none.

### Cell: `goga/hooks/catalog`

No `.usages/` directory — nothing to update.

### Documentation pages (implementation-stage deliverable, not `.usages/`)

The MkDocs surface drifts once the action lands; the implementation stage
updates:

- `docs/features/contract/hooks.md` — currently states the contract domain
  exposes **no hook actions**; rewrite for `contract / amend_contract`
  (address table row, hook signature example, delivered view fields,
  failure semantics — model on `docs/features/schema/hooks.md`).
- `docs/features/hooks/hooks.md` — the address enumeration and the
  error-class paragraph gain `contract / amend_contract` (**hard**).
- `docs/features/hooks/api.md` — the staged-delivery consumer list gains
  the contract amendment; the action catalog table gains the row.
- `docs/features/contract/cli.md` — the output example gains the `tools`
  key with the presence rule.

---

## Test Stack Trace

### General Setup

- Zone suites: `tests/contract/hooks/` mirroring `tests/schema/hooks/` —
  `__init__.py`, `conftest.py` re-exporting
  `from tests.hooks.conftest import install_tool_package, pin_package_environment`,
  and per-module suites (`test_facts.py`, `test_amendments.py`,
  `test_overlay.py`, `test_events.py`, `test_facade.py`).
- Boundary fixtures (from `tests/hooks/conftest.py`, used as-is):
  `pin_package_environment({"goga_tool_docs": ["docs-dist"]})` pins the
  installed-distributions read; `install_tool_package("goga_tool_docs",
  register_hooks=register)` installs a fake `goga_tool_*` package into
  `sys.modules`. The platform derives the identity `goga_tool_docs` →
  `docs`. The registry, registrars, and delivery run for real.
- Zone fixture `_cell()` (module helper of `test_events.py`):

```python
def _cell(path: str = "goga/config") -> CellFacts:
    return CellFacts(
        path=path,
        types=[
            TypeFacts(
                name="ProjectConfig",
                signature=FormFacts(codemanifest="ProjectConfig(language: str)", implementation="ProjectConfig(language: str)"),
                properties=[MemberFacts(name="language", form=FormFacts(codemanifest="str", implementation="str"))],
                methods=[MemberFacts(name="reload", form=FormFacts(codemanifest="reload() -> None", implementation=None))],
            ),
            TypeFacts(
                name="load_project_config",
                signature=FormFacts(codemanifest="load_project_config() -> config: ProjectConfig", implementation="load_project_config() -> config: ProjectConfig"),
                properties=[],
                methods=[],
            ),
        ],
    )
```

  (two declared types: one entity `ProjectConfig`, one routine
  `load_project_config` with empty member lists).
- Command suites: extend `tests/commands/test_contract.py` — the existing
  helpers `_run_contract`, `_write_goga_yml`, `_write_codemanifest`,
  `ENTITY_CODEMANIFEST`/`ENTITY_IMPL`, `_sys_path`, and the `cwd` fixture
  from `tests/conftest.py` compose with the two boundary fixtures.
- Catalog suite: extend `tests/hooks/catalog/test_catalog.py`.
- All tests run under the project's pytest/ruff gates; test libraries
  belong to the `test` extra if anything new is needed (nothing new is
  needed).

### Source File Registry

- `goga/hooks/catalog/catalog.py` — the new record (catalog suite).
- `goga/contract/hooks/facts.py` — facts records (facts suite).
- `goga/contract/hooks/amendments.py` — the view (amendments suite).
- `goga/contract/hooks/overlay.py` — contribution + merge (overlay suite).
- `goga/contract/hooks/events.py` — the checkpoint surface (events suite).
- `goga/contract/hooks/__init__.py` — the facade (facade suite).
- `goga/commands/contract/contract.py` — the command (command suite).

---

### Positive Tests

#### `test_amend_contract_commits_buffered_facts`

**Setup**: `pin_package_environment({"goga_tool_docs": ["docs-dist"]})`;
a fake package whose hook subscribes `"contract"`, `"amend_contract"`,
`"cover"` and calls
`context.contribute({"ProjectConfig": {"coverage": 3}})`.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**:
```
amend_contract(cell=_cell())
  → _ensure_registry()                  # build_once: enumerate, register
  → declared_actions()                  # record contract/amend_contract found
  → subscriptions_for("contract","amend_contract")  # [docs/cover]
  → groups = {"docs": [sub]}
  → ContractAmendment(cell=_read_only_view(cell))   # fresh lists per tool
  → wrap_context(amendment) → build_hook_arguments   # context=proxy, self=ctx
  → hook(context=proxy) → proxy.contribute({"ProjectConfig": {"coverage": 3}})
      side effect: amendment._pending == [{"ProjectConfig": {"coverage": 3}}]
  → _commit_tool_buffer("docs", "goga/config", {"ProjectConfig", "load_project_config"}, pending)
      merge → {"ProjectConfig": {"coverage": 3}}
      _check_json_map → passes; address check → "ProjectConfig" declared
      returns: {"ProjectConfig": {"coverage": 3}}
  → ToolContribution(tool="docs", facts={...})
  → merge_type_contributions([...])
returns: {"ProjectConfig": {"docs": {"coverage": 3}}}
```

**Assertions**:
```
result == {"ProjectConfig": {"docs": {"coverage": 3}}}
```

**Sufficiency**: the end-to-end happy path over the real platform — proves
the address resolves through the new catalog record, the per-tool commit
works, and the composition nests type → tool → fact exactly as the command
output contract requires.

---

#### `test_amend_contract_two_tools_compose_per_type`

**Setup**: environment pinned with `goga_tool_docs` and `goga_tool_lint`;
two hooks — `docs` contributes `{"ProjectConfig": {"coverage": 3}}`,
`lint` contributes `{"ProjectConfig": {"rules": 7}}`.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: two tool groups in enumeration order; each commits its own
`ToolContribution`; `merge_type_contributions` places both identities
under `ProjectConfig`.

**Assertions**:
```
result == {"ProjectConfig": {"docs": {"coverage": 3}, "lint": {"rules": 7}}}
```

**Sufficiency**: multiple contributors on one type — the per-type area is
the merge of every tool's facts; prevents the regression of one tool's
area overwriting another's.

---

#### `test_amend_contract_repeated_type_address_merges_facts`

**Setup**: one tool; its hook calls `contribute` twice:
`{"ProjectConfig": {"coverage": 3}}` then
`{"ProjectConfig": {"tests": 12}}`.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: both payloads buffered verbatim; the commit-point merge does
`merged.setdefault("ProjectConfig", {}).update(...)` per payload.

**Assertions**:
```
result == {"ProjectConfig": {"docs": {"coverage": 3, "tests": 12}}}
```

**Sufficiency**: pins the two-level merge semantics — a repeated type
address merges its facts rather than replacing the area (a plain
top-level `dict.update` would drop `coverage`).

---

#### `test_amend_contract_fact_conflict_later_write_wins`

**Setup**: one tool; hook contributes
`{"ProjectConfig": {"coverage": 3}}` then
`{"ProjectConfig": {"coverage": 9}}`.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: fact-level update inside the type — the later payload's value
replaces the earlier on the `coverage` key.

**Assertions**:
```
result == {"ProjectConfig": {"docs": {"coverage": 9}}}
```

**Sufficiency**: the documented conflict rule of `contribute` — a later
write replaces an earlier one on fact-name conflict within a type.

---

#### `test_amend_contract_empty_contribute_commits_nothing`

**Setup**: one tool; hook calls `contribute({})`.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: payload `{}` merges nothing; `merged == {}` skips the checks;
no `ToolContribution` appended.

**Assertions**:
```
result == {}
```

**Sufficiency**: the quiet path — an empty outer mapping contributes
nothing, silently (not an error, not an empty tools area).

---

#### `test_amend_contract_no_subscriptions_returns_empty`

**Setup**: environment pinned with `goga_tool_docs`; the package registers
no subscription for the address (subscribes a different address).

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: `subscriptions_for("contract", "amend_contract") == []` → no
groups → `contributions == []`.

**Assertions**:
```
result == {}
```

**Sufficiency**: the unobservable-delivery guarantee — an address without
subscriptions leaves the caller's output byte-identical.

---

#### `test_amend_contract_no_tool_packages_returns_empty`

**Setup**: `pin_package_environment({})`.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: `build_once` enumerates nothing; no groups; empty mapping.

**Assertions**:
```
result == {}
```

**Sufficiency**: the with-no-tools byte-identity requirement of the
command contract, proven at the zone boundary.

---

#### `test_amend_contract_builds_registry_once_per_run`

**Setup**:
`boundary = pin_package_environment({"goga_tool_docs": ["docs-dist"]})`;
a fake package whose hook subscribes `"contract"`, `"amend_contract"`,
`"cover"` and calls `context.contribute({"ProjectConfig": {"coverage": 3}})`.

**Input**: `surface = ContractHooks()`; then
`first = surface.amend_contract(cell=_cell(path="goga/config"))` and
`second = surface.amend_contract(cell=_cell(path="goga/schema"))`.

**Trace**:
```
first amend_contract(cell=_cell("goga/config"))
  → _ensure_registry()        # _registry is None → HookRegistry() + build_once()
      side effect: the single packages_distributions read (boundary.call_count 0 → 1)
  → delivery → commit → {"ProjectConfig": {"docs": {"coverage": 3}}}
second amend_contract(cell=_cell("goga/schema"))
  → _ensure_registry()        # cached registry — no read, no register_hooks
  → delivery → commit → {"ProjectConfig": {"docs": {"coverage": 3}}}
```

**Assertions**:
```
boundary.call_count == 1
first == {"ProjectConfig": {"docs": {"coverage": 3}}}
second == {"ProjectConfig": {"docs": {"coverage": 3}}}
```

**Sufficiency**: pins the manifest Requirement "One `HookRegistry` per run
carries every checkpoint of a command" — a per-cell registry would
multiply the package enumeration and the `register_hooks` callbacks by
the number of cells (the `test_amend_cell_builds_registry_once_per_run`
precedent of the schema zone).

---

#### `test_amend_contract_accepts_list_and_tuple_values`

**Setup**: one tool; its hook subscribes `"contract"`, `"amend_contract"`,
`"emit"` and calls
`context.contribute({"ProjectConfig": {"tags": ["a", 1], "pair": ("x", 1.5, True, None), "mixed": [{"n": 1}]}})`.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: the payload passes both merge guards and the JSON-map check
(lists and tuples of checked items are JSON values); the buffer stores
the sequences verbatim; the commit places them unchanged.

**Assertions**:
```
result == {"ProjectConfig": {"docs": {"tags": ["a", 1], "pair": ("x", 1.5, True, None), "mixed": [{"n": 1}]}}}
```
(the tuple stays a tuple — `json.dumps` serializes it as an array at the
command's dump step)

**Sufficiency**: sequence facts are first-class — prevents a regression
to a scalars-only structural check or an eager list/tuple coercion at
the commit point (the schema-zone precedent
`test_amend_cell_accepts_list_and_tuple_values`).

---

#### `test_merge_type_contributions_skips_empty_and_orders_by_enumeration`

**Setup** (pure unit — no fixtures): `contributions = [
ToolContribution(tool="docs", facts={"A": {"x": 1}, "B": {"y": 2}}),
ToolContribution(tool="lint", facts={"A": {}}),
ToolContribution(tool="lint", facts={"C": {"z": 3}})]`.

**Input**: `merge_type_contributions(contributions)`.

**Trace**: `docs` lands on `A` and `B`; the empty `A` area of `lint` is
skipped; `lint` lands on `C`.

**Assertions**:
```
result == {"A": {"docs": {"x": 1}}, "B": {"docs": {"y": 2}}, "C": {"lint": {"z": 3}}}
contributions unchanged (deep equality with the setup value)
```

**Sufficiency**: determinism, the skip rule (a tool exists on a type iff
it wrote at least one fact), purity (inputs unmutated).

---

#### `test_contract_command_places_tools_area_on_type_node`

**Setup**: tmp project (`cwd` fixture): `.goga/config.yml`
(`language: python`), one cell `cell_one` with `ENTITY_CODEMANIFEST`
(entity `MyClass` with property `name` and method `do_it`) and
`myclass.py` = `ENTITY_IMPL`; environment pinned with `goga_tool_docs`
whose hook contributes `{"MyClass": {"coverage": 3}}`; `_sys_path` for
the impl import.

**Input**: `_run_contract("cell_one")`.

**Trace**:
```
contract(cells=("cell_one",), lang=None)
  → load_project_config → ConfigHooks().amend_config → overlay
  → AST load → document("cell_one") → contract_logic → compare
  → hooks = ContractHooks(); path = result key
  → _build_cell_facts → CellFacts(types=[TypeFacts(MyClass, ...)])
  → amend_contract → {"MyClass": {"docs": {"coverage": 3}}}
  → result["cell_one"]["MyClass"]["tools"] = {"docs": {"coverage": 3}}
  → json.dumps(...)
```

**Assertions**:
```
exit_code == 0
payload = json.loads(stdout)
payload["cell_one"]["MyClass"]["tools"] == {"docs": {"coverage": 3}}
payload["cell_one"]["MyClass"]["signature"]["codemanifest"] unchanged
```

**Sufficiency**: the root consumer end-to-end — the checkpoint composes
onto the type node of the real command output next to the fixed keys.

---

#### `test_contract_command_output_identical_without_tools`

**Setup**: the same tmp project; `pin_package_environment({})`.

**Input**: `_run_contract("cell_one")`.

**Trace**: comparison loop only; `amend_contract` returns `{}`; no
`tools` key anywhere; dump identical to the pre-change structure.

**Assertions**:
```
exit_code == 0
payload = json.loads(stdout)
payload == {
    "cell_one": {
        "MyClass": {
            "signature": {"codemanifest": "()", "implementation": "()"},
            "properties": {"name": {"codemanifest": "str", "implementation": "str"}},
            "methods": {"do_it": {"codemanifest": "(x: int) -> str", "implementation": "(x: int) -> str"}},
        }
    }
}
"tools" not in payload["cell_one"]["MyClass"]
```
(full-structure equality against the pre-change comparison values — the
determinism of the `beautiful_json` dump makes structure equality
equivalent to byte-identity)

**Sufficiency**: the byte-identity requirement — no extensions, no
observable difference.

---

#### `test_declared_actions_carries_the_contract_record`

**Setup** (pure unit): none.

**Input**: `declared_actions()`.

**Trace**: the sorted catalog; filter `domain == "contract"`.

**Assertions**:
```
[(a.name, a.error_class) for a in declared_actions() if a.domain == "contract"] == [("amend_contract", "hard")]
```

**Sufficiency**: the catalog prerequisite — without the record every
delivery fails at address resolution; pins domain/name/error_class
exactly.

---

### Negative Tests

#### `test_amend_contract_crashed_hook_stops_with_clean_error`

**Setup**: environment pinned with `goga_tool_docs`; the hook raises
`RuntimeError("boom")`.

**Input**: `pytest.raises(ValueError)` around
`ContractHooks().amend_contract(cell=_cell())`.

**Trace**:
```
  → hook(context=proxy) raises RuntimeError("boom")
  → except Exception → raise ValueError(
      "hook cover of tool docs failed on contract.amend_contract at goga/config: boom")
```

**Assertions**:
```
str(excinfo.value) == "hook cover of tool docs failed on contract.amend_contract at goga/config: boom"
excinfo.value.__cause__ is the RuntimeError
```

**Sufficiency**: the hard-action contract — first failure stops the walk;
the message names the hook, the tool, the action, and the cell path.

---

#### `test_amend_contract_first_failing_tool_stops_the_walk`

**Setup**: environment pinned with `goga_tool_alpha` and `goga_tool_beta`
(enumeration is alphabetical — alpha before beta); the alpha package
subscribes `"explode"` — its hook appends `"alpha"` to a module-level
`invocations` list and raises `RuntimeError("kaput")`; the beta package
subscribes `"record"` — its hook appends `"beta"` and contributes
`{"ProjectConfig": {"late": True}}`.

**Input**: `pytest.raises(ValueError, match=r"hook explode of tool alpha failed on contract\.amend_contract at goga/config: kaput")`
around `ContractHooks().amend_contract(cell=_cell())`.

**Trace**:
```
groups = {"alpha": [sub], "beta": [sub]}          # enumeration order
→ alpha's hook raises → ValueError stops the walk
→ beta's group never reached — no hook call, no side effect
```

**Assertions**:
```
invocations == ["alpha"]        # beta never ran
```

**Sufficiency**: pins the manifest Requirement "A hard failure stops the
delivery at the first failure in the walk" as an observable side-effect
guarantee — catches the regression of the walk continuing past the first
failure (a hard action silently turning soft); the schema-zone precedent
is `test_amend_cell_first_failing_tool_stops_the_delivery`.

---

#### `test_amend_contract_non_mapping_payload_fails`

**Setup**: one tool; hook calls `contribute([("ProjectConfig", {"x": 1})])`
(a list of pairs).

**Input**: `pytest.raises(ValueError)` around `amend_contract(cell=_cell())`.

**Trace**: commit point — `isinstance(payload, Mapping)` is false →
structural failure wrapped with tool/action/path.

**Assertions**:
```
"tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution" in str(excinfo.value)
"a contribution payload is not a mapping: list" in str(excinfo.value)
```

**Sufficiency**: no silent coercion — `dict.update` would accept the
iterable of pairs; the contract forbids it.

---

#### `test_amend_contract_non_string_key_fails`

**Setup**: one tool; hook contributes `{42: {"x": 1}}`.

**Input**: `pytest.raises(ValueError)`.

**Trace**: the merge rejects the int key at the per-address `str` guard —
"non-string key 42 at the merged contribution", the same message the
JSON-map check carries — wrapped with tool/action/path (a non-string key
never reaches `merged.setdefault`).

**Assertions**:
```
"structurally malformed contribution" in str(excinfo.value)
"non-string key 42" in str(excinfo.value)
```

**Sufficiency**: type-name keys must be strings — a non-string address is
never silently stringified (the `json.dumps` coercion hole), and the
guard's message matches the JSON-map family so the failure stays
indistinguishable from a nested non-string key.

---

#### `test_amend_contract_non_serializable_value_fails`

**Setup**: one tool; hook contributes
`{"ProjectConfig": {"stamp": object()}}`.

**Input**: `pytest.raises(ValueError)`.

**Trace**: `_check_json_map` reaches the bare object → "value of type
object at ...".

**Assertions**:
```
"structurally malformed contribution" in str(excinfo.value)
"value of type object" in str(excinfo.value)
```

**Sufficiency**: the structural check guarantees the command's
`json.dumps` can never crash on a contribution.

---

#### `test_amend_contract_empty_nested_mapping_fails`

**Setup**: one tool; hook contributes `{"ProjectConfig": {}}`.

**Input**: `pytest.raises(ValueError)`.

**Trace**: merge yields `{"ProjectConfig": {}}`; `_check_json_map`
rejects the empty mapping at `the merged contribution.ProjectConfig`.

**Assertions**:
```
"empty mapping at the merged contribution.ProjectConfig" in str(excinfo.value)
```

**Sufficiency**: empty objects never appear at any of the three levels of
the tools area — the usage file's output-shape rule.

---

#### `test_amend_contract_non_dict_mapping_value_fails`

**Setup**: one tool; hook contributes
`{"ProjectConfig": {"cfg": MappingProxyType({"a": 1})}}` (a non-dict
`Mapping` value).

**Input**: `pytest.raises(ValueError)`.

**Trace**: both merge guards pass (`MappingProxyType` is a `Mapping`, the
key a `str`); `_check_json_map` reaches the value — it is not a plain
`dict`, not a list/tuple, not a JSON scalar → "value of type
mappingproxy at the merged contribution.ProjectConfig.cfg", wrapped with
tool/action/path.

**Assertions**:
```
"structurally malformed contribution" in str(excinfo.value)
"value of type mappingproxy at the merged contribution.ProjectConfig.cfg" in str(excinfo.value)
```

**Sufficiency**: a mapping-like value is not JSON-representable — the
commit point must reject it with the pinned format instead of letting
the command's `json.dumps` crash without attribution (the schema-zone
precedent `test_amend_cell_non_dict_mapping_fails_at_the_commit_point`).

---

#### `test_amend_contract_cyclic_contribution_fails_at_the_commit_point`

**Setup**: one tool; the payload is self-referencing —
`cyclic = {"note": "a cell fact"}; cyclic["self"] = cyclic` — and the
hook contributes `{"ProjectConfig": cyclic}`.

**Input**: `pytest.raises(ValueError)`.

**Trace**: the merge accepts the payload (mapping, string address,
mapping facts); `_check_json_map` descends into the value —
`_nested_scope` finds the container's identity among the ancestors →
"circular reference at the merged contribution.ProjectConfig.self",
wrapped with tool/action/path; never a `RecursionError` escape.

**Assertions**:
```
"structurally malformed contribution" in str(excinfo.value)
"circular reference at the merged contribution.ProjectConfig.self" in str(excinfo.value)
```

**Sufficiency**: the cycle guard is copied verbatim from the schema zone
— this pins it in the new zone; without it the command's `json.dumps`
would crash with `ValueError: Circular reference detected` on the caller
side, unattributed to the offending tool.

---

#### `test_amend_contract_unknown_address_is_a_clean_error`

**Setup**: `pin_package_environment({})` and monkeypatch
`goga.contract.hooks.events.declared_actions` with a function returning
every record except the `domain="contract"` one.

**Input**: `pytest.raises(ValueError, match=r"unknown hook action: contract\.amend_contract")`
around `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: the registry builds; the address resolution `next(...)` yields
`None` → the emitting-side programming error with the pinned message
(the `test_amend_cell_unknown_address_is_a_clean_error` precedent).

**Assertions**:
```
str(excinfo.value) == "unknown hook action: contract.amend_contract"
```

**Sufficiency**: the address must resolve through the catalog — pins the
exact clean-error message of the emitting side (the catalog record is
the hard prerequisite; a removed record must fail here, not deep inside
the delivery).

---

#### `test_amend_contract_undeclared_type_address_fails_naming_type`

**Setup**: one tool; hook contributes
`{"NotDeclared": {"x": 1}}`.

**Input**: `pytest.raises(ValueError)`.

**Trace**: merge and JSON-map check pass; the address check finds
`"NotDeclared"` not in `{"ProjectConfig", "load_project_config"}` →
bad-address failure.

**Assertions**:
```
str(excinfo.value) == (
    "tool docs failed on contract.amend_contract at goga/config: "
    "contribution addresses undeclared type NotDeclared"
)
```

**Sufficiency**: the bad-address clause of the catalog record — the error
names the tool, the action, the cell path, **and the offending type
name**; a routine-only cell or a misspelled type fails loudly instead of
dropping the contribution.

---

#### `test_contract_command_checkpoint_failure_is_clean_cli_error`

**Setup**: the tmp project; environment pinned with `goga_tool_docs`
whose hook raises `RuntimeError("boom")`.

**Input**: `_run_contract("cell_one")`.

**Trace**:
```
  → comparison completes → amend_contract raises ValueError(...)
  → except (ValueError, ImportError) → click.ClickException(str(exc))
  → CliRunner captures: exit_code 1, stderr line "Error: hook cover of ..."
```

**Assertions**:
```
result.exit_code == 1
"Error: hook cover of tool docs failed on contract.amend_contract" in result.output
result.stdout == ""          # no partial JSON
```

**Sufficiency**: the user-facing failure channel — one clean stderr line,
exit 1, stdout data-clean; never a traceback.

---

#### `test_amend_contract_broken_facade_raises_import_error`

**Setup**: make the enumeration boundary fail —
`boundary = pin_package_environment({"goga_tool_broken": ["broken-dist"]})`
then set `boundary.side_effect = ImportError("cannot import
goga_tool_broken")` on the returned mock (the fixture pins the
`packages_distributions` read at `ENUMERATION_TARGET`; a `side_effect`
makes that read raise).

**Input**: `pytest.raises(ImportError)` around
`ContractHooks().amend_contract(cell=_cell())`.

**Trace**: `_ensure_registry` → `build_once` → enumeration raises →
propagates unchanged.

**Assertions**:
```
"cannot import goga_tool_broken" in str(excinfo.value)
```

**Sufficiency**: the single fatal case keeps its type — the command's
`except ImportError` arm is reachable, and the zone never swallows it
into a `ValueError`.

---

### Edge Case Tests

#### `test_amend_contract_cell_without_types_rejects_any_contribution`

**Setup**: one subscribed tool contributing
`{"ProjectConfig": {"x": 1}}`; input cell
`CellFacts(path="goga/empty", types=[])`.

**Input**: `pytest.raises(ValueError)`.

**Trace**: `declared_names == set()`; merge + JSON-map pass; the address
check fails on `"ProjectConfig"`.

**Assertions**:
```
"contribution addresses undeclared type ProjectConfig" in str(excinfo.value)
```

**Sufficiency**: the empty-cell landing-zone rule of the usage file — the
checkpoint is delivered over empty facts, and any non-empty contribution
is the unknown-address hard failure.

---

#### `test_amend_contract_routine_type_receives_tools_area`

**Setup**: one tool contributing
`{"load_project_config": {"calls": 4}}` (the routine of `_cell()`).

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: the routine is a declared type; the address check passes; the
merge places the area.

**Assertions**:
```
result == {"load_project_config": {"docs": {"calls": 4}}}
```

**Sufficiency**: routines are addressable — the composition is per
declared type, not per entity; prevents an entity-only filter sneaking
into the address check or the merge.

---

#### `test_amend_contract_tool_view_lists_are_not_shared`

**Setup**: two tools — `docs` hook mutates
`context.cell.types.append(...)` (in-place write attempt through the
read-only fresh view), `lint` hook contributes normally.

**Input**: `ContractHooks().amend_contract(cell=_cell())`.

**Trace**: `docs`'s write lands on its own fresh list (the caller's and
`lint`'s views unaffected); `docs` commits nothing; `lint` commits.

**Assertions**:
```
result == {"ProjectConfig": {"lint": {...}}}
cell.types length unchanged after the call   # the caller's facts untouched
```

**Sufficiency**: the mutual-blindness guarantee — a hostile or careless
in-place write never reaches another tool's view or the caller's facts.

---

#### `test_contract_command_duplicate_path_delivered_once`

**Setup**: the tmp project with cell `cell_one`; environment pinned with
`goga_tool_docs`; the hook increments a counter on the tool `self`
context and contributes `{"MyClass": {"calls": count}}`.

**Input**: `_run_contract("cell_one", "./cell_one")`.

**Trace**: two requests normalize to one `result` key; the delivery loop
iterates `result` — one `amend_contract` call, one hook invocation.

**Assertions**:
```
exit_code == 0
json.loads(stdout)["cell_one"]["MyClass"]["tools"] == {"docs": {"calls": 1}}
```

**Sufficiency**: the dedup requirement — a path requested more than once
is delivered once, in first-request order (a counter of 2 would prove the
regression).

---

#### `test_contract_command_existing_failure_precedes_hooks`

**Setup**: the tmp project; environment pinned with `goga_tool_docs`
whose hook sets a module-level flag when invoked; request a nonexistent
cell path.

**Input**: `_run_contract("no/such/cell")`.

**Trace**: step 4 — `ast_obj.document` raises `DocumentNotFoundError` →
stderr error + `ctx.exit(1)`; the delivery loop is never reached.

**Assertions**:
```
result.exit_code == 1
"Error: document not found: no/such/cell" in result.output
hook_flag is False        # the hook never ran
```

**Sufficiency**: the precedence requirement — existing failures fire
before any hook; a hook running before the comparison would break the
guarantee.

---

#### `test_construction_enumerates_nothing`

**Setup**:
`boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})`.

**Input**: `ContractHooks()` (construction alone, no checkpoint call).

**Trace**: `__init__` only sets `self._registry = None` — no enumeration,
no imports, no environment read.

**Assertions**:
```
boundary.call_count == 0
```

**Sufficiency**: pins the manifest Requirement "Cheap construction — no
enumeration and no imports happen at construction"; a constructor that
enumerated would make the empty-`cells` command run observable (the
schema-zone precedent `test_construction_enumerates_nothing`).

---

#### `test_facts_records_are_frozen_pure_data`

**Setup** (pure unit): none.

**Input**: construct `CellFacts(...)` / `TypeFacts(...)` / `FormFacts(...)`
/ `MemberFacts(...)` with concrete values (`path="goga/x"`, one type, one
member, `implementation=None`).

**Trace**: attribute reads return the passed values; field assignment
raises `FrozenInstanceError`.

**Assertions**:
```
facts.path == "goga/x"
form.implementation is None
with pytest.raises(FrozenInstanceError): facts.path = "other"
```

**Sufficiency**: the read view is immutable data — a tool's write channel
is `contribute` alone; also pins the absent-counterpart form
(`implementation is None`).

---

#### `test_facade_reexports_the_zone_contract_names`

**Setup** (pure unit): import `goga.contract.hooks as facade`.

**Input**: `facade.__all__` and the name identity checks.

**Trace**: the facade imports from the four modules and re-exports.

**Assertions**:
```
sorted(facade.__all__) == [
    "CellFacts", "ContractAmendment", "ContractHooks",
    "FormFacts", "MemberFacts", "ToolContribution",
    "TypeFacts", "merge_type_contributions",
]
facade.ContractHooks is goga.contract.hooks.events.ContractHooks
```

**Sufficiency**: the consumer import surface — the command and the tool
docs import from the facade; a missing re-export breaks consumers at
import time.

---

## Additional Instructions for the Implementation Agent

- Implement in dependency order: (1) the catalog record
  (`goga/hooks/catalog/catalog.py` — one line), (2) the zone leaves →
  root: `facts.py` → `amendments.py` → `overlay.py` → `events.py` →
  `__init__.py`, (3) the command (`contract.py`), (4) tests, (5) docs.
- Reuse the schema zone (`goga/schema/hooks/`) as the structural template:
  copy `_check_json_map` / `_nested_scope` verbatim; adapt
  `_commit_tool_buffer` for the two-level merge and the address check;
  adapt `_read_only_view` for the contract facts shape.
- The two-level merge is the one deliberate semantic difference from the
  schema zone — do not copy schema's flat `dict.update(payload)` merge.
- Every zone module uses relative imports; the zone never imports
  `..dispatcher` or any language extractor of `goga/contract`.
- Error message formats are contractual (they name the hook/tool, the
  action `contract.amend_contract`, the cell path, and — for a bad
  address — the offending type name): keep them byte-stable for the
  command's `ClickException` passthrough.
- The command constructs `ContractHooks()` exactly once per run and
  reuses it across cells; do not construct it inside the per-cell loop.
- Do not add a `tools` key when the returned area mapping is empty, and
  never emit an empty object at any level of the tools area.
- Update the four documentation pages listed in `.usages/` Update —
  Documentation pages; `goga hooks` output and any catalog-listing docs
  gain the record automatically through `declared_actions()`.
- Gates: `pytest tests/ -x` and `ruff` must pass; the new suites live at
  `tests/contract/hooks/` (with `__init__.py` and the conftest
  re-export), extensions go into `tests/commands/test_contract.py` and
  `tests/hooks/catalog/test_catalog.py`.
- Do not modify the CODEMANIFEST files, the `.usages/` practice files, or
  any pipeline/Dockerfile assets — the contracts are settled; the
  out-of-scope working-tree changes (Dockerfile, `goga/assets/pipelines/*.yml`)
  belong to a different effort and must be left untouched.
