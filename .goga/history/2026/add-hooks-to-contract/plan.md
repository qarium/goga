# Plan: `add-hooks-to-contract`

Result of compiling the reviewed design document
(`.goga/history/2026/add-hooks-to-contract/design.md`, 1888 lines, design-review
passed: 6/6 remarks fixed) into a ralphex execution plan.

## Purpose

Implement the contract-amendment checkpoint end to end:

- the new hooks zone of the contract domain — `goga/contract/hooks` — with its
  four flat modules and facade (8 contract entities: 4 facts records, the
  amendment view, the contribution pairing, the merge routine, the checkpoint
  surface);
- the new hard action record `contract/amend_contract` in the platform catalog
  (`goga/hooks/catalog`);
- the `goga contract` command as the root consumer: checkpoint delivery after
  the built-in comparison, tools-area composition onto the type nodes of the
  JSON output;
- the six documentation pages that drift once the action lands.

The contracts are settled: all three CODEMANIFEST files and both `.usages/`
practice files are already in their final state in the working tree and are
**read-only** for the implementation. The gaps are pure implementation: the
zone code, one catalog line, the command steps 5–6, the test suites, the docs.

Strategy: leaf-first dependency order (`goga/hooks/catalog` →
`goga/contract/hooks` modules → zone facade → `goga/commands/contract` →
docs), TDD inside every coding task, and structural mirroring of the schema
zone (`goga/schema/hooks/`) — `_check_json_map` / `_nested_scope` copied
verbatim, `_commit_tool_buffer` adapted for the two-level merge and the
address check, `_read_only_view` adapted for the contract facts shape.

## Context

### Contract Surface

**Entity: `CellFacts(path: str, types: list[TypeFacts])`** (new)
- Type: class (frozen `kw_only` dataclass)
- Declared `location`: `facts.py` (in `goga/contract/hooks/`)
- Facade obligation: importable from `goga.contract.hooks`
- Properties: `path -> str` (the normalized cell path);
  `types -> list[TypeFacts]` (the comparison facts of each declared type)
- Semantic requirements: pure facts — the constructing operation passes
  resolved values, nothing is read inside; authored projection only,
  identical for every tool; one shape for every implementation language

**Entity: `TypeFacts(name: str, signature: FormFacts, properties: list[MemberFacts], methods: list[MemberFacts])`** (new)
- Type: class (frozen `kw_only` dataclass); `location`: `facts.py`
- Facade obligation: importable from `goga.contract.hooks`
- Properties: `name -> str`; `signature -> FormFacts`;
  `properties -> list[MemberFacts]` (empty for a routine);
  `methods -> list[MemberFacts]` (empty for a routine)
- Semantic requirements: pure data — constructed by the caller from its own
  comparison values

**Entity: `FormFacts(codemanifest: str, implementation: str | None)`** (new)
- Type: class (frozen `kw_only` dataclass); `location`: `facts.py`
- Facade obligation: importable from `goga.contract.hooks`
- Properties: `codemanifest -> str` (the declared form);
  `implementation -> str | None` (the extracted counterpart — absent allowed)
- Semantic requirements: pure strings only — no parsed structures

**Entity: `MemberFacts(name: str, form: FormFacts)`** (new)
- Type: class (frozen `kw_only` dataclass); `location`: `facts.py`
- Facade obligation: importable from `goga.contract.hooks`
- Properties: `name -> str`; `form -> FormFacts`
- Semantic requirements: pure data

**Entity: `ContractAmendment(cell: CellFacts)`** (new)
- Type: class (mutable `kw_only` dataclass — it owns a buffer);
  `location`: `amendments.py`
- Facade obligation: importable from `goga.contract.hooks`
- Properties: `cell -> CellFacts` (read-only for the receiving hook)
- Methods: `contribute(facts: dict[str, dict[str, object]])` — buffer one
  type-addressed contribution of this tool; stores verbatim, no validation,
  no merge; an empty outer mapping contributes nothing; for one type a later
  write replaces an earlier one on fact-name conflict, a repeated type
  address merges its facts (realized at the commit point)
- Private buffer: `_pending: list` — `init=False`, `repr=False`,
  `default_factory=list`
- Semantic requirements: the reads deliver the comparison facts — a tool
  never sees another tool's contribution; the buffered contributions belong
  to this tool alone

**Entity: `ToolContribution(tool: str, facts: dict[str, dict[str, object]])`** (new)
- Type: class (frozen `kw_only` dataclass); `location`: `overlay.py`
- Facade obligation: importable from `goga.contract.hooks`
- Properties: `tool -> str`; `facts -> dict[str, dict[str, object]]`
- Semantic requirements: pure data — constructed by the checkpoint delivery
  alone

**Routine: `merge_type_contributions(contributions: list[ToolContribution]) -> tools: dict[str, dict[str, dict[str, object]]]`** (new)
- Type: module-level function; `location`: `overlay.py`
- Facade obligation: importable from `goga.contract.hooks`
- Algorithm (verbatim from the manifest):
  1. Take the contributions in enumeration order
  2. Skip a contribution whose mapping is empty — a tool exists on a type
     iff that tool wrote at least one fact for that type
  3. For each type name the contribution addresses, place the tool's fact
     mapping under the tool identity inside that type's area
  4. A type name absent from every committed contribution is absent from
     the result
  5. Return the composed mapping — empty when every contribution was empty
     or none committed
- Semantic requirements: deterministic; pure (inputs unmutated, new mapping);
  structural validation is not here — it happened at the tool commit point;
  no filesystem access

**Entity: `ContractHooks()`** (new)
- Type: class; `location`: `events.py`
- Facade obligation: importable from `goga.contract.hooks`
- Methods: `amend_contract(cell: CellFacts) -> tools: dict[str, dict[str, dict[str, object]]]` —
  deliver the checkpoint for one cell, return the tools area per addressed
  type (empty when nothing contributed). Full algorithm in Task 6.
- Semantic requirements: cheap construction (no enumeration, no imports at
  construction); one `HookRegistry` per run carries every checkpoint of a
  command; every context is built from the values the caller passes — no
  configuration, git, or file reads; the zone never prints
- Zone-internal helpers (module-level, private, not on the facade):
  `_read_only_view`, `_nested_scope`, `_check_json_map`,
  `_commit_tool_buffer`

**Changed entity: `declared_actions()`** (`goga/hooks/catalog`, `location: catalog.py`)
- The returned catalog gains
  `Action(domain="contract", name="amend_contract", error_class="hard")`.
  No signature or behavior change: the routine still returns every record
  ordered by domain then name. Additive only — no published record rewritten.

**Changed entity: `contract(cells, lang)`** (`goga/commands/contract`, `location: contract.py`)
- Algorithm gains steps 5–6 (checkpoint delivery after the built-in
  comparison of every requested cell; tools-area composition onto the type
  nodes); the output format gains the `tools` key on type nodes; the command
  help must explain the response structure including the tools-area
  semantics. Full detail in Task 8.

### Re-exports

The facade `goga/contract/hooks/__init__.py` must expose exactly eight names
through `__all__` (house style: sorted):

`CellFacts`, `ContractAmendment`, `ContractHooks`, `FormFacts`,
`MemberFacts`, `ToolContribution`, `TypeFacts`, `merge_type_contributions`

Every name must be importable from `goga.contract.hooks` and resolve to the
entity of its module. The command imports exactly five of them
(`ContractHooks`, `CellFacts`, `TypeFacts`, `FormFacts`, `MemberFacts`);
`ContractAmendment`, `ToolContribution`, `merge_type_contributions` stay
importable from the facade but the command never touches them.

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — the project's code, REPL,
  testing, and data-model rules: relative intra-package imports, standard
  library `dataclasses` with `kw_only=True`, Google-style docstrings,
  one-blank-line block separation, `tests/<package>/` mirror layout with
  `__init__.py` per directory, `pytest`/`ruff` gates, Python 3.10+.
  Relevant to every task.
- `click` (`.goga/usages/cooks/click.md`) — the CLI framework pattern:
  `@click.command()`, `@click.argument("cells", nargs=-1)`,
  `@click.option("--lang", default=None)`, `@click.pass_context`,
  `click.ClickException`, `click.echo(err=True)`. Relevant to Task 8.
- `beautiful_json` (`.goga/usages/cooks/beautiful_json.md`) — the canonical
  dump `json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`,
  applied once to the finished `result`. Relevant to Task 8.

### Imported Usages

- `per-tool-delivery` from `goga/hooks`
  (`goga/hooks/.usages/per-tool-delivery.md`) — the staged delivery loop of
  the amendment checkpoint: its loop skeleton, primitives (`HookRegistry`,
  `subscriptions_for`, `self_context`, `wrap_context`,
  `build_hook_arguments`), and tool-grouped commit apply as written; the
  hard variant raises instead of the practice's soft-sketch `continue`.
  Relevant to Task 6.
- `registering-hooks` from `goga/hooks`
  (`goga/hooks/.usages/registering-hooks.md`) — the hook signature
  (`self`, `context`), the `register_hooks` facade callback, and the failure
  behavior behind the checkpoint (a broken package import is the only fatal
  case). Relevant to Tasks 4 and 6.
- `contract-checkpoints` from `goga/contract/hooks`
  (`goga/contract/hooks/.usages/contract-checkpoints.md`) — the consumer
  practice the command follows: run the built-in comparison first, walk
  unique normalized paths in first-request order, build facts from the
  command's own comparison data, place each returned tools area on its
  type's node, wrap ValueError/ImportError into the clean command error.
  Relevant to Task 8.
- `loading` from `goga/ast`, `use_contract` (alias of `contract`) from
  `goga/contract`, `project-configuration` from `goga/config`,
  `checkpoints` from `goga/config/hooks` — pre-existing imports of the
  command manifest, unchanged by this change. Context for Task 8.

### Local Usages

No local usage file is created or updated by this plan — the design's
`.usages/` Update section verified both existing files as current:

- `goga/contract/hooks/.usages/contract-checkpoints.md` — already created
  with the manifest; matches the design exactly; no additions.
- `goga/commands/contract/.usages/contract.md` — already updated with the
  `tools` key and the presence-rule note; no additions.
- `goga/hooks/catalog` — no `.usages/` directory; nothing to update.

The six documentation pages under `docs/` are an implementation-stage
deliverable of this plan (Task 10), not `.usages/` files.

### External Dependencies

- `click` — the command layer (existing dependency, unchanged usage).
- `pyyaml` — the config load of step 1 (pre-existing, unchanged).
- `pytest`, `pytest-cov`, `ruff` — the test and lint gates (test extra;
  nothing new is needed).
- No new third-party dependency is introduced by this change.

### Entity Interaction and Data Flow

Verbatim from the design document (verified knowledge — do not re-derive):

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

**Flow 1 — comparison to checkpoint (per cell, steps 4–5).**

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
extracted strings the output already shows, nothing else.

**Flow 2 — checkpoint delivery (per cell, inside `amend_contract`).**

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

1. For each `type_name, area` in the returned mapping:
   `result[path][type_name]["tools"] = area`.
2. The key lands next to the fixed keys (`signature`, and for entities
   `properties`/`methods`) — on routine nodes as well.
3. `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)` — the
   structural check at the commit point guarantees serializability;
   `sort_keys=True` keeps the output deterministic.

### Code Stack Traces

Verbatim from the design document (all checkpoints passed the design
review; keep these chains intact while implementing).

**Trace: `contract(cells, lang)` — the CLI command.**

1. **Input**: `goga contract goga/config goga/hooks` through the click app;
   `cells: tuple[str, ...]` from `nargs=-1`, `lang: str | None` from
   `--lang`. Argument surface unchanged by this change.
2. **(existing, 1)** `load_project_config()` → `ProjectConfig`; the config
   checkpoint `ConfigHooks().amend_config(config=authored)` → `ConfigOverlay`;
   failures wrap into `click.ClickException`. `overlay.summary_lines` print
   to stderr. Unchanged.
3. **(existing, 2–3)** language resolution (`lang` or
   `overlay.config.language`); `AST(".")` + `.load()`. Unchanged.
4. **(existing, 4)** per requested path — `ast_obj.document(path)`
   (`DocumentNotFoundError` → stderr error + `ctx.exit(1)`),
   `contract_logic(lang, path)` (→ stderr error + `ctx.exit(1)`),
   `_build_cell_compare(...)` → `compare`;
   `result[os.path.normpath(doc.path)] = compare`. A re-requested path
   overwrites the identical value; dict insertion order keeps first-request
   order — the dedup source for step 5 is `result` itself. The failure
   channels of step 4 all fire **before** any hook runs.
5. **(new, 5)** `hooks = ContractHooks()`; for each `path in result`:
   `_build_cell_facts(path, result[path])` → `CellFacts`;
   `tools = hooks.amend_contract(cell=facts)` with
   `except (ValueError, ImportError) as exc: raise click.ClickException(str(exc)) from exc`.
   Type flow: `compare` values are
   `{"codemanifest": str, "implementation": str | None}` — `FormFacts`
   accepts them exactly (`FormFacts(**pair)`); entity nodes carry
   `properties`/`methods` dicts, routine nodes do not — `node.get("properties", {})`
   yields `[]` for routines. Error alignment: the zone raises `ValueError`
   and lets `ImportError` propagate — exactly the two types step 5 names;
   `ClickException` exits code 1 with `Error: <message>` on stderr, no
   stdout output before it.
6. **(new, 6)** for each `type_name, area in tools.items()`:
   `result[path][type_name]["tools"] = area`. The `tools` key never lands
   as `{}`; a type with no contribution stays untouched. An addressed name
   is guaranteed declared (the address check validated it against
   `cell.types`, which mirrors `result[path]` keys), so the lookup cannot
   miss.
7. **Output**: `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)`
   → `click.echo(json_str)` — stdout carries nothing but the JSON.
   Contributions are plain `dict`/`str`/`int`/`bool`/`None`/finite
   `float`/`list` values (the structural check), so serialization cannot
   fail.

**Trace: `ContractHooks.amend_contract(cell)`.**

1. **Input**: `cell: CellFacts` built by the caller; `self._registry` is
   `None` on the first call. The surface reads no configuration, git, or
   files.
2. `self._ensure_registry()` — first call creates `HookRegistry()` and runs
   `build_once()` (enumerates installed `goga_tool_*` packages, runs their
   `register_hooks` callbacks; a broken facade raises `ImportError` naming
   the package — the single fatal case); later calls return the cached
   registry. `build_once` is idempotent per instance — N cells share one
   enumeration.
3. Address resolution —
   `next((e for e in declared_actions() if e.domain == "contract" and e.name == "amend_contract"), None)`;
   `None` → `ValueError("unknown hook action: contract.amend_contract")`.
   The new catalog record must exist, else every delivery fails.
4. `declared_names = {t.name for t in cell.types}`; subscriptions
   `registry.subscriptions_for("contract", "amend_contract")` grouped per
   tool (`groups.setdefault(sub.tool, []).append(sub)`) in enumeration
   order. An empty group set → `contributions == []` → step 7 returns `{}`.
5. Per tool: `amendment = ContractAmendment(cell=_read_only_view(cell))`;
   `proxy = wrap_context(amendment)`; for each subscription:
   `sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))`
   inside `try`; any `Exception` →
   `ValueError(f"hook {sub.name} of tool {tool} failed on contract.amend_contract at {cell.path}: {reason}")`.
   `wrap_context` resolves reads and calls, blocks writes;
   `build_hook_arguments` injects only declared names (`context`, `self`).
   Mutual blindness: `_read_only_view` rebuilds every list (`cell.types`,
   `properties`, `methods`) — an in-place `append` by one tool's hook stays
   local to that tool's view; `FormFacts`/`MemberFacts` carry only `str`
   fields (fully immutable, safe to share).
6. Per tool commit: `merged = _commit_tool_buffer(tool, cell.path, declared_names, amendment._pending)`;
   `if merged: contributions.append(ToolContribution(tool=tool, facts=merged))`.
7. `return merge_type_contributions(contributions)` —
   `{type_name: {tool: {fact: value}}}`, `{}` when nothing committed. The
   zone never prints: every outcome is a return value or an exception.

**Trace: `ContractAmendment.contribute(facts)`.**

1. A tool hook calls `context.contribute(facts)` with
   `facts: dict[str, dict[str, object]]` — declared type name → the tool's
   fact mapping for that type. The call arrives through the `wrap_context`
   proxy (method call — allowed).
2. `self._pending.append(facts)` — stored verbatim; no validation, no
   interpretation, no merge here. The buffer is `init=False, repr=False` —
   invisible in construction and repr.
3. `None`; the payload waits for the tool's commit point. Structural
   failures are named at the commit point, naming this tool.

**Trace: `_commit_tool_buffer(tool, cell_path, declared_names, pending)`.**

1. **Input**: the tool identity, the delivered cell's normalized path, the
   declared type-name set, and the view's buffered payloads.
2. **Merge**: `merged: dict[str, dict[str, object]] = {}`; per payload:
   `isinstance(payload, Mapping)` else structural failure
   (`ValueError("a contribution payload is not a mapping: ...")` — never a
   silent `dict.update` coercion of an iterable of pairs); per
   `type_name, facts` in the payload: `isinstance(facts, Mapping)` else
   structural failure, and `isinstance(type_name, str)` else structural
   failure (`non-string key {type_name!r} at the merged contribution` —
   the same message `_check_json_map` would produce, raised before the
   `setdefault` so an exotic `Mapping` yielding an unhashable key can
   never crash the merge with a raw `TypeError` that would escape the
   `(ValueError, RecursionError)` wrap); then
   `merged.setdefault(type_name, {}).update(facts)`. The two-level merge
   realizes the contract — "a repeated type address merges its facts; for
   one type, a later write replaces an earlier one on fact-name conflict".
3. **Structural check**: `if merged: _check_json_map(merged, "the merged contribution")`
   — plain `dict`s only, string keys only, non-empty mapping at every
   level, values `dict`/`list|tuple`/`str`/`int`/`bool`/`None`/finite
   `float`, cycle-guarded (the schema-zone validator, applied verbatim).
   A payload `{"A": {}}` fails as "empty mapping at the merged
   contribution.A"; the empty outer payload `{}` merges nothing and never
   reaches the check.
4. **Address check**: the first `type_name` of `merged` (insertion order =
   enumeration order, deterministic) not in `declared_names` →
   `ValueError` naming the offending type. A cell with no declared types
   has `declared_names == set()` — any non-empty contribution fails here;
   the checkpoint over empty facts is still delivered (hooks run, may
   read, must contribute nothing).
5. **Output**: `merged` (possibly `{}` — commits nothing); failures raise
   `ValueError(f"tool {tool} failed on contract.amend_contract at {cell_path}: ...")`
   — the tool, the action, and the cell path in every message, the
   offending type name for a bad address.

**Trace: `merge_type_contributions(contributions)`.**

1. **Input**: committed `ToolContribution`s in enumeration order.
2. `tools: dict[str, dict[str, dict[str, object]]] = {}`; per contribution,
   per `type_name, facts` in `contribution.facts.items()`:
   `if facts: tools.setdefault(type_name, {})[contribution.tool] = facts`.
   A tool appears on a type iff it wrote at least one fact for that type
   (empty areas skipped — defensive; the commit point cannot produce them).
3. **Output**: `tools` — a new mapping; inputs untouched. Deterministic,
   pure, no filesystem access, no re-validation.

**Trace: `declared_actions()` (catalog, changed data).**

1. Returns `sorted(_DECLARED_ACTIONS, key=lambda a: (a.domain, a.name))`;
   the list constant gains
   `Action(domain="contract", name="amend_contract", error_class="hard")`.
   Sorted by domain then name — `contract` lands between `config` and
   `onboarding` in the returned order; the physical position of the new
   entry in the constant is irrelevant to output. Additive only. No
   consumer of the catalog observes a behavioral change besides the new
   record.

**Trace: `_build_cell_facts(path, compare)` (command-internal helper).**

1. **Input**: the normalized cell path and the cell's comparison dict from
   `result`.
2. Per `name, node in compare.items()` build
   `TypeFacts(name=name, signature=FormFacts(**node["signature"]), properties=[...], methods=[...])`
   with `MemberFacts(name=member_name, form=FormFacts(**member_pair))` from
   `node.get("properties", {})` / `node.get("methods", {})`; wrap into
   `CellFacts(path=path, types=types)`. Every value is already `str` or
   `None` — no transformation, a pure projection.
3. **Output**: `CellFacts` handed to `amend_contract`. The delivered view
   is the comparison the output shows — identical for every tool, no
   per-language projection.

## Facts

- The three CODEMANIFEST files are in their final, lint-clean state in the
  working tree: `goga/contract/hooks/CODEMANIFEST` (created),
  `goga/hooks/catalog/CODEMANIFEST` and `goga/commands/contract/CODEMANIFEST`
  (modified). `goga lint` passes: 82 cells, 0 errors. The dependency graph
  is `goga/hooks` ← `goga/contract/hooks` ← `goga/commands/contract`; no
  cycles.
- Both `.usages/` files touched by the change exist and are current:
  `goga/contract/hooks/.usages/contract-checkpoints.md` and
  `goga/commands/contract/.usages/contract.md`. Nothing to create or update.
- The structural precedent exists in full: `goga/schema/hooks/`
  (`facts.py`, `amendments.py`, `overlay.py`, `events.py`, `__init__.py`)
  and its test suite `tests/schema/hooks/` (`conftest.py` re-export,
  `test_facts.py`, `test_amendments.py`, `test_overlay.py`,
  `test_events.py`, `test_facade.py`).
- The schema zone's `_check_json_map` / `_nested_scope` are copied
  **verbatim**; `_commit_tool_buffer` is adapted (two-level merge, per-type
  `Mapping` guard, per-address `str` guard, declared-address check);
  `_read_only_view` is adapted for the contract facts shape
  (`path` + `types`, each `TypeFacts` rebuilt with fresh
  `properties`/`methods` lists, `FormFacts`/`MemberFacts` shared).
- The two-level merge is the one deliberate semantic difference from the
  schema zone — do not copy schema's flat `dict.update(payload)` merge.
- The catalog currently carries 26 records; adding the contract record
  makes 27. The existing catalog suite pins the total in seven places —
  five `== 26` assertions and two `len(pre_existing) + 1` totals — plus
  one exact full-catalog list; those pins must be updated
  as expectation maintenance of an additive data change the manifest
  already declares.
- Boundary fixtures exist and are used as-is:
  `tests/hooks/conftest.py::pin_package_environment` (pins
  `goga.hooks.tools.packages.packages_distributions`; returns the boundary
  mock — `call_count` and `side_effect` supported) and
  `install_tool_package` (installs a fake `goga_tool_*` package into
  `sys.modules`). The platform derives the identity `goga_tool_docs` →
  `docs`. Enumeration is alphabetical by top-level module name.
- Command test helpers exist and compose with the boundary fixtures:
  `_run_contract`, `_write_goga_yml`, `_write_codemanifest`,
  `ENTITY_CODEMANIFEST` / `ENTITY_IMPL`, `_sys_path`, and the `cwd`
  fixture from `tests/conftest.py` (also `is_kw_only_dataclass`).
- `tests/contract/` exists with `__init__.py`; the new zone suites live in
  the new subdirectory `tests/contract/hooks/`.
- Error message formats are contractual and byte-stable (they name the
  hook/tool, the action `contract.amend_contract`, the cell path, and — for
  a bad address — the offending type name); the command passes them
  through `click.ClickException` unchanged.
- Lint-forced naming already settled in the contracts: the zone practice
  file is `contract-checkpoints.md` (not `checkpoints.md` — the linter
  compares pre-alias import names and `goga/commands/contract` already
  imports `checkpoints` from `goga/config/hooks`); two `tools` references
  in the command manifest are plain text, not backtick links.
- Python-level note: importing `goga.contract.hooks` executes
  `goga/contract/__init__.py` first — package semantics, identical to the
  `goga/config/hooks` precedent; the zone modules themselves never import
  `..dispatcher`, `..python`, or any extractor of `goga/contract`.
- The out-of-scope working-tree changes (`Dockerfile`,
  `goga/assets/pipelines/*.yml`, `.goga/history/` topic files) belong to a
  different effort and must be left untouched.
- Project gates: `pytest tests/ -x`, `ruff check goga/ tests/`,
  `ruff format --check goga/ tests/` (CI lint.yml), `goga lint`.
  Python 3.10+ compatibility required.

## Gap Analysis

- Missing contract entities (all of `goga/contract/hooks`):
  `facts.py` (CellFacts, TypeFacts, FormFacts, MemberFacts),
  `amendments.py` (ContractAmendment), `overlay.py` (ToolContribution,
  merge_type_contributions), `events.py` (ContractHooks + 4 private
  helpers), `__init__.py` (facade with 8 re-exports).
- Missing facade exposure: the zone package itself — `goga/contract/hooks/`
  currently contains only `CODEMANIFEST` and `.usages/`.
- Missing data record: `Action(domain="contract", name="amend_contract",
  error_class="hard")` in `goga/hooks/catalog/catalog.py`.
- Missing command behavior: steps 5–6 in
  `goga/commands/contract/contract.py` — the five-name import, the
  `_build_cell_facts` helper, the delivery block, the tools-key help text.
- Test coverage gaps: the entire zone suite `tests/contract/hooks/`
  (24 events scenarios, 1 facts scenario, 1 overlay scenario, 1 facade
  scenario, mirrored contract-test classes), 5 command scenarios in
  `tests/commands/test_contract.py`, 1 catalog scenario + pin maintenance
  in `tests/hooks/catalog/test_catalog.py`.
- Documentation drift: `docs/features/contract/hooks.md` states the
  contract domain exposes no hook actions (now false);
  `docs/features/hooks/hooks.md`, `docs/features/hooks/api.md`,
  `docs/features/contract/cli.md` lack the new address and the tools key;
  `docs/features/hooks/index.md` and `docs/features/tools/hooks.md`
  enumerate every declared action in prose ("The declared actions today")
  and lack the contract record.
- Existing code to reuse verbatim or by adaptation: `goga/schema/hooks/`
  modules and their tests; the hooks platform facade (`HookRegistry`,
  `wrap_context`, `build_hook_arguments`, `declared_actions`); the test
  boundary fixtures and command helpers listed in Facts.
- No `location` misplacements, no API mismatches, no deletions.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow). Package order: `goga/hooks/catalog` → `goga/contract/hooks` → `goga/commands/contract` → docs.

> **Global constraint (every task)**: `CODEMANIFEST` files and `.usages/` practice files are read-only contract definitions — do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract. Do not touch `Dockerfile`, `goga/assets/pipelines/*.yml`, or anything under `.goga/history/`.

### Task 1: Add the contract amendment record to the action catalog (TDD coding)

The routine `declared_actions()` (cell `goga/hooks/catalog`, `location: catalog.py`) returns the sorted catalog; the contract change adds exactly one record — `Action(domain="contract", name="amend_contract", error_class="hard")`. The CODEMANIFEST already carries the Requirements bullet describing this record (read-only). The record is the hard prerequisite of the zone's address resolution (Task 6, algorithm step 1) — without it every delivery fails with `unknown hook action`. The catalog is data only; `Action`, `declared_actions`, their docstrings, and the sort behavior stay exactly as they are. The physical position of the new entry in `_DECLARED_ACTIONS` is stylistic (the return sorts by `(domain, name)`); the natural spot is next to the schema record.

**Usages relevant to this task:**
- `convention`: Google-style docstrings, no dead code, `pytest tests/<pkg>/` mirror layout; the catalog stays "supported data, not discovery".

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: in `tests/hooks/catalog/test_catalog.py` add `test_declared_actions_carries_the_contract_record` — setup none (pure unit); assert `[(a.name, a.error_class) for a in declared_actions() if a.domain == "contract"] == [("amend_contract", "hard")]` (expected to fail at this stage — the record is absent)
- [x] **Code**: append `Action(domain="contract", name="amend_contract", error_class="hard"),` to `_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py`, next to the `schema` record; change nothing else in the file
- [x] **Interface verification**: `pytest tests/hooks/catalog/ -v` — the new test passes; the pre-existing pinned-total tests now fail (expected — they pin the old 26-record catalog)
- [x] **Logic tests / pin maintenance**: update the stale pins of the catalog suite to the 27-record catalog — expectation maintenance for the additive data change the manifest declares, not test weakening: the exact full-catalog list in `test_catalog_carries_the_five_build_records` gains `("contract", "amend_contract", "hard")` in sorted position (between the `config` and `onboarding` triples); the `pre_existing` lists of `test_schema_amend_cell_record_present` and `test_config_amend_config_record_present` gain the same triple; every catalog total assertion `26` becomes `27` (`test_declared_actions_carries_the_nine_topics_records`, `test_declared_actions_carries_the_four_usages_records`, `test_catalog_carries_the_three_pipeline_records`, `test_config_amend_config_record_present`, `test_schema_amend_cell_record_present`); the domain-ordering assertions (`build < config < onboarding`, `pipeline < schema < statuses`) stay true with `contract` sorted between `config` and `onboarding` — do not change them
- [x] **Debugging**: `pytest tests/hooks/ -v` — all catalog, registry, dispatch, tools, and facade suites green; fix implementation code if anything beyond the pinned totals fails (do not weaken the new record test)
- [x] **Contract re-verification**: facade `python -c "from goga.hooks.catalog import Action, declared_actions"`; the returned list is sorted by `(domain, name)`, complete, 27 records; `Action` untouched (frozen record, three fields)
- [x] **Lint**: `ruff check goga/ tests/` and `ruff format --check goga/ tests/` — fix formatting if necessary

### Task 2: Zone package and test-directory skeleton (infrastructure)

Create the importable skeleton of the new zone `goga/contract/hooks` and its mirrored test directory, so the module tasks (3–6) have a package to live in and the suites have a place to collect. The facade `__init__.py` is created as a docstring-only placeholder here; the eight contract re-exports land in Task 7 (the modules do not exist yet — a full facade now would not import).

**Usages relevant to this task:**
- `convention`: every test directory carries `__init__.py`; local fixtures in `tests/<package>/conftest.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.**

- [x] Create `goga/contract/hooks/__init__.py` — module docstring naming the zone (the hooks zone of the contract domain: the per-cell comparison read view, the per-tool contribution model, and the checkpoint surface) and stating that the contract re-exports are assembled in the facade below; no imports, no `__all__` yet (Task 7 completes it)
- [x] Create `tests/contract/hooks/__init__.py` — empty file
- [x] Create `tests/contract/hooks/conftest.py` — module docstring mirroring `tests/schema/hooks/conftest.py`, re-exporting `from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401`
- [x] Verify package importability: `python -c "import goga.contract.hooks; print('zone package importable')"` (executes `goga/contract/__init__.py` first — package semantics, same as the `goga/config/hooks` precedent)
- [x] Verify test skeleton: `python -m pytest tests/contract/hooks/ --collect-only -q` collects without import errors (exit code 5 "no tests collected" is acceptable at this stage — the suites arrive with Tasks 3–7)
- [x] Lint: `ruff check goga/contract/hooks/ tests/contract/hooks/`

### Task 3: The comparison facts records — `facts.py` (TDD coding)

Four frozen `kw_only` dataclasses in one location (`facts.py`): `CellFacts(path: str, types: list[TypeFacts])`, `TypeFacts(name: str, signature: FormFacts, properties: list[MemberFacts], methods: list[MemberFacts])`, `FormFacts(codemanifest: str, implementation: str | None)`, `MemberFacts(name: str, form: FormFacts)`. Pure data the command constructs from its own comparison values; nothing is read inside. Module docstring names all four records and their zone role; no imports beyond `dataclasses` (+ `from __future__ import annotations` per house style). Google-style docstrings with `Args:` per field and the manifest `Requirements:` where stated. Follow the `goga/schema/hooks/facts.py` precedent. All fields are required — no defaults (the CODEMANIFEST signatures declare every parameter; the contract wins over the general empty-default convention).

Construction contract (verbatim from the design):

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

Edge cases: a cell whose manifest body is empty → `types=[]` (delivered; any non-empty contribution for it is the unknown-address hard failure); a member with no implementation counterpart → `FormFacts(codemanifest=..., implementation=None)`.

**Usages relevant to this task:**
- `convention`: standard library `dataclasses`, `kw_only=True`, frozen for pure records, Google-style docstrings, relative intra-package imports (none needed here).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/contract/hooks/test_facts.py` (docstring mirroring `tests/schema/hooks/test_facts.py`, adapted to the four contract records). Contract tests import from `goga.contract.hooks.facts` directly (the facade identity assertions belong to Task 7): each of the four records is a frozen `kw_only` dataclass (`dataclasses.is_dataclass`, `is_kw_only_dataclass` from `tests/conftest`, `__dataclass_params__.frozen`, positional construction raises `TypeError`); each carries exactly its declared fields in order (`CellFacts`: `path, types`; `TypeFacts`: `name, signature, properties, methods`; `FormFacts`: `codemanifest, implementation`; `MemberFacts`: `name, form`) (expected to fail — the module does not exist)
- [ ] **Code**: create `goga/contract/hooks/facts.py` per the construction contract above — four `@dataclass(frozen=True, kw_only=True)` records with docstrings carrying the manifest requirements verbatim in style
- [ ] **Interface verification**: `pytest tests/contract/hooks/test_facts.py -v` — all contract tests pass
- [ ] **Logic tests**: add to the same suite — `test_facts_records_are_frozen_pure_data` (designed scenario): construct concrete values (`path="goga/x"`, one `TypeFacts`, one `MemberFacts`, `implementation=None`); assert `facts.path == "goga/x"`, `form.implementation is None`, and `with pytest.raises(FrozenInstanceError): facts.path = "other"`; plus: an entity type carries its member lists, a routine shape carries `properties=[]`/`methods=[]`, and `CellFacts(path=..., types=[])` is constructible (the empty-body cell)
- [ ] **Debugging**: `pytest tests/contract/hooks/ -v` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: every field of every record matches the declared property (name and type hint) of the `CellFacts`/`TypeFacts`/`FormFacts`/`MemberFacts` declarations; `python -c "from goga.contract.hooks.facts import CellFacts, FormFacts, MemberFacts, TypeFacts; print('facts ok')"`
- [ ] **Lint**: `ruff check goga/ tests/` and `ruff format --check goga/ tests/`

### Task 4: The read-and-contribute view — `amendments.py` (TDD coding)

`ContractAmendment(cell: CellFacts)` in `amendments.py`: the view one tool receives at the checkpoint — the delivered facts (read-only) plus this tool's buffer. `@dataclass(kw_only=True)` (mutable — it owns a buffer); `cell: CellFacts` is a plain field; the private buffer `_pending: list = field(init=False, default_factory=list, repr=False)`. `contribute(facts: dict[str, dict[str, object]]) -> None` appends the payload verbatim — no validation, no interpretation, no merge; structural failures surface at the commit point naming this tool. Module docstring mirrors `goga/schema/hooks/amendments.py`. Errors: none raised here.

Algorithm (verbatim from the design):

```
1. Construction: cell: CellFacts (kw_only); _pending: list (init=False,
   default [], repr=False)
2. contribute(facts):
   - append facts verbatim to _pending        → no validation, no merge
   - an empty outer mapping is stored like any other — it merges to
     nothing at the commit point
```

Edge cases: repeated `contribute` for the same type — payloads merge fact-wise at the commit (later write wins on fact-name conflict); `contribute({})` — contributes nothing, silently.

**Usages relevant to this task:**
- `convention`: dataclass rules, Google-style docstrings.
- `registering-hooks` (from `goga/hooks`): the hook signature that receives this view — a hook declaring `context` receives the wrapped view; `contribute` is the single write channel.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/contract/hooks/test_amendments.py` (docstring mirroring `tests/schema/hooks/test_amendments.py`; fixture: one minimal `CellFacts(path="goga/config", types=[])` from Task 3, one `ContractAmendment(cell=...)` view). Contract tests: importable from `goga.contract.hooks.amendments`; `kw_only` dataclass, **not** frozen; fields exactly `["cell", "_pending"]`; `_pending` is `init=False`, `repr=False`, `default_factory=list`, starts `[]`; `inspect.signature(ContractAmendment).parameters == ["cell"]`; `contribute` signature `["self", "facts"]` with type hints `facts: dict[str, dict[str, object]]`, `return` is `None` (expected to fail — the module does not exist)
- [ ] **Code**: create `goga/contract/hooks/amendments.py` per the algorithm above, importing `CellFacts` relatively from `.facts`
- [ ] **Interface verification**: `pytest tests/contract/hooks/test_amendments.py -v` — all contract tests pass
- [ ] **Logic tests**: add to the same suite (the buffer semantics class): payloads buffer verbatim in call order (`view.contribute({"A": {"x": 1}})` then `{"A": {"y": 2}}` → `_pending == [{"A": {"x": 1}}, {"A": {"y": 2}}]`); `contribute({})` buffers `[{}]` verbatim; a non-mapping payload is stored verbatim (`_pending[0] is payload`); `contribute` returns `None`; two views over the same cell never share buffer state; `view.cell is cell`
- [ ] **Debugging**: `pytest tests/contract/hooks/ -v` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: `python -c "from goga.contract.hooks.amendments import ContractAmendment; print('amendments ok)"` — the method annotation and the buffer invisibility match the declaration
- [ ] **Lint**: `ruff check goga/ tests/` and `ruff format --check goga/ tests/`

### Task 5: The committed contribution and the composition — `overlay.py` (TDD coding)

Two entities in one location (`overlay.py`): `ToolContribution(tool: str, facts: dict[str, dict[str, object]])` — frozen `kw_only` dataclass, pure data constructed by the checkpoint delivery alone; and the module-level routine `merge_type_contributions(contributions: list[ToolContribution]) -> dict[str, dict[str, dict[str, object]]]` — the deterministic, pure composition. Structural validation is not here — it happened at the tool commit point. Module docstring mirrors `goga/schema/hooks/overlay.py`.

Algorithm (verbatim from the design):

```
1. FOR each contribution IN enumeration order:
2.   FOR each (type_name, facts) IN contribution.facts:
3.     IF facts is empty: SKIP        (defensive — cannot occur post-commit)
4.     tools.setdefault(type_name, {})[contribution.tool] = facts
5. RETURN tools                       ({} when nothing committed)
```

Edge cases: empty input list → `{}`; two contributions addressing the same type → both tools appear in that type's area, in enumeration order (JSON `sort_keys` normalizes the final serialization).

**Usages relevant to this task:**
- `convention`: dataclass rules, Google-style docstrings, the docstring carries the manifest algorithm.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/contract/hooks/test_overlay.py` (docstring mirroring `tests/schema/hooks/test_overlay.py`). Contract tests: `ToolContribution` importable from `goga.contract.hooks.overlay`, frozen `kw_only` dataclass with exactly the fields `["tool", "facts"]`, positional construction raises `TypeError`; `merge_type_contributions` importable from the same module, `inspect.signature(...).parameters == ["contributions"]`, return type hint `dict[str, dict[str, dict[str, object]]]` (expected to fail — the module does not exist)
- [ ] **Code**: create `goga/contract/hooks/overlay.py` per the algorithm above
- [ ] **Interface verification**: `pytest tests/contract/hooks/test_overlay.py -v` — all contract tests pass
- [ ] **Logic tests**: add to the same suite — `test_merge_type_contributions_skips_empty_and_orders_by_enumeration` (designed scenario, verbatim): setup `contributions = [ToolContribution(tool="docs", facts={"A": {"x": 1}, "B": {"y": 2}}), ToolContribution(tool="lint", facts={"A": {}}), ToolContribution(tool="lint", facts={"C": {"z": 3}})]`; assert `result == {"A": {"docs": {"x": 1}}, "B": {"docs": {"y": 2}}, "C": {"lint": {"z": 3}}}` and `contributions` unchanged (deep equality with the setup value); plus: empty input list → `{}`; two tools addressing the same type both appear in that type's area
- [ ] **Debugging**: `pytest tests/contract/hooks/ -v` — fix implementation code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: `python -c "from goga.contract.hooks.overlay import ToolContribution, merge_type_contributions; print('overlay ok')"` — purity (no input mutation) and determinism hold
- [ ] **Lint**: `ruff check goga/ tests/` and `ruff format --check goga/ tests/`

### Task 6: The checkpoint surface — `events.py` (TDD coding)

`ContractHooks` in `events.py`: the staged per-tool delivery of the hard `contract/amend_contract` action over the platform facade, plus four module-level private helpers. Copy `_check_json_map` / `_nested_scope` **verbatim** from `goga/schema/hooks/events.py`; adapt `_commit_tool_buffer` for the two-level merge and the address check; adapt `_read_only_view` for the contract facts shape. Imports: `math`, `collections.abc.Mapping`, `typing.Any`, `from ...hooks import HookRegistry, build_hook_arguments, declared_actions, wrap_context`, and the zone's own `ContractAmendment`, `CellFacts`/`TypeFacts` (for the view builder), `ToolContribution`, `merge_type_contributions`. Relative imports throughout; the zone never imports `..dispatcher` or any language extractor of `goga/contract`. Module docstring mirrors `goga/schema/hooks/events.py`. Class docstrings carry the manifest algorithm/requirements/raises verbatim in style.

Algorithm `amend_contract` (verbatim from the design):

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

Helper contracts:

- `_read_only_view(cell) -> CellFacts` — rebuild `CellFacts` with a fresh `types` list; each `TypeFacts` rebuilt with fresh `properties`/`methods` lists; `FormFacts`/`MemberFacts` shared (str-only fields — immutable). The mutual-blindness guarantee: a tool's in-place list write stays local to its own view.
- `_nested_scope(value, where, ancestors)` — cycle guard, copied verbatim from the schema zone.
- `_check_json_map(value, where, ancestors)` — the JSON-map shape validator, copied verbatim from the schema zone: plain `dict` with string keys, non-empty at every level; values dict (recursive), list or tuple of checked items, or a JSON scalar (`str`, `int`, `bool`, `None`, finite `float`); everything else rejected. Explicit recursion — not a `json.dumps` probe.
- `_commit_tool_buffer(tool, cell_path, declared_names, pending) -> dict[str, dict[str, object]]` — the tool commit point (trace in Context → Code Stack Traces): guarded two-level merge (payload `Mapping` guard, per-type `Mapping` guard, per-address `str` guard with the message `non-string key {type_name!r} at the merged contribution`) → `_check_json_map(merged, "the merged contribution")` when `merged` is non-empty → first-undeclared-address check (insertion order) → return the merged mapping. Failure messages (byte-stable, contractual):
  `f"tool {tool} failed on contract.amend_contract at {cell_path}: structurally malformed contribution ({reason})"` and
  `f"tool {tool} failed on contract.amend_contract at {cell_path}: contribution addresses undeclared type {type_name}"`.

Errors: `ValueError` — unknown address, a crashed hook (names hook, tool, action, cell path, reason), a malformed contribution (names tool, action, cell path, detail), a bad address (adds the type name); `ImportError` — broken tool facade at `build_once` (propagates unchanged, never swallowed); `RecursionError` — caught with the structural failures and re-raised as the same `ValueError`.

The suite's module helper `_cell()` (verbatim from the design — two declared types, one entity `ProjectConfig`, one routine `load_project_config`):

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

**Usages relevant to this task:**
- `per-tool-delivery` (from `goga/hooks`): the staged delivery loop — its skeleton, primitives (`HookRegistry`, `subscriptions_for`, `self_context`, `wrap_context`, `build_hook_arguments`), and tool-grouped commit apply as written; the hard variant raises instead of the practice's soft-sketch `continue`.
- `registering-hooks` (from `goga/hooks`): the hook signature (`self`, `context`) and the failure behavior behind the checkpoint — a broken package import is the only fatal case.
- `convention`: code style, docstrings, blank-line block separation.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/contract/hooks/test_events.py` (docstring mirroring `tests/schema/hooks/test_events.py`; the `_cell()` helper above; boundary fixtures via the Task 2 conftest). Contract tests: `ContractHooks` importable from `goga.contract.hooks.events`; `inspect.signature(ContractHooks.amend_contract).parameters == ["self", "cell"]` with return hint `dict[str, dict[str, dict[str, object]]]`; construction takes no arguments (expected to fail — the module does not exist)
- [ ] **Code**: create `goga/contract/hooks/events.py` — `class ContractHooks` with `__init__` (`self._registry: HookRegistry | None = None`), `_ensure_registry`, `amend_contract`, and the four private helpers per the contracts above; `_check_json_map` / `_nested_scope` byte-identical to the schema zone
- [ ] **Interface verification**: `pytest tests/contract/hooks/test_events.py -v` — at this point the file carries the contract tests only (the logic tests are added below); all must pass
- [ ] **Logic tests (positive)**: add to the same suite, each with the real platform (fixtures `pin_package_environment` / `install_tool_package`, identity `goga_tool_docs` → `docs`; hook subscription names appear in the asserted messages — keep them exact):
  - `test_amend_contract_commits_buffered_facts` — hook subscribes `("contract", "amend_contract", "cover")`, calls `context.contribute({"ProjectConfig": {"coverage": 3}})`; assert `result == {"ProjectConfig": {"docs": {"coverage": 3}}}`
  - `test_amend_contract_two_tools_compose_per_type` — `docs` contributes `{"ProjectConfig": {"coverage": 3}}`, `lint` contributes `{"ProjectConfig": {"rules": 7}}`; assert `result == {"ProjectConfig": {"docs": {"coverage": 3}, "lint": {"rules": 7}}}`
  - `test_amend_contract_repeated_type_address_merges_facts` — one tool contributes `{"ProjectConfig": {"coverage": 3}}` then `{"ProjectConfig": {"tests": 12}}`; assert `result == {"ProjectConfig": {"docs": {"coverage": 3, "tests": 12}}}`
  - `test_amend_contract_fact_conflict_later_write_wins` — contributes `coverage: 3` then `coverage: 9`; assert `result == {"ProjectConfig": {"docs": {"coverage": 9}}}`
  - `test_amend_contract_empty_contribute_commits_nothing` — `contribute({})`; assert `result == {}`
  - `test_amend_contract_no_subscriptions_returns_empty` — the package subscribes a different address; assert `result == {}`
  - `test_amend_contract_no_tool_packages_returns_empty` — `pin_package_environment({})`; assert `result == {}`
  - `test_amend_contract_builds_registry_once_per_run` — `boundary = pin_package_environment({"goga_tool_docs": ["docs-dist"]})`; two `amend_contract` calls over `_cell("goga/config")` and `_cell("goga/schema")`; assert `boundary.call_count == 1` and both results `== {"ProjectConfig": {"docs": {"coverage": 3}}}`
  - `test_amend_contract_accepts_list_and_tuple_values` — hook subscribes name `"emit"`, contributes `{"ProjectConfig": {"tags": ["a", 1], "pair": ("x", 1.5, True, None), "mixed": [{"n": 1}]}}`; assert the result equals the same nested mapping (the tuple stays a tuple — `json.dumps` serializes it as an array at the command's dump step)
- [ ] **Logic tests (negative)**:
  - `test_amend_contract_crashed_hook_stops_with_clean_error` — the hook raises `RuntimeError("boom")`; assert `str(excinfo.value) == "hook cover of tool docs failed on contract.amend_contract at goga/config: boom"` and `excinfo.value.__cause__` is the `RuntimeError`
  - `test_amend_contract_first_failing_tool_stops_the_walk` — `goga_tool_alpha` (enumeration first) subscribes `"explode"`, appends `"alpha"` to a module-level `invocations` list, raises `RuntimeError("kaput")`; `goga_tool_beta` subscribes `"record"`, appends `"beta"`, contributes; assert `pytest.raises(ValueError, match=r"hook explode of tool alpha failed on contract\.amend_contract at goga/config: kaput")` and `invocations == ["alpha"]`
  - `test_amend_contract_non_mapping_payload_fails` — `contribute([("ProjectConfig", {"x": 1})])` (a list of pairs); assert `"tool docs failed on contract.amend_contract at goga/config: structurally malformed contribution"` and `"a contribution payload is not a mapping: list"` both in `str(excinfo.value)`
  - `test_amend_contract_non_string_key_fails` — `contribute({42: {"x": 1}})`; assert `"structurally malformed contribution"` and `"non-string key 42"` in `str(excinfo.value)`
  - `test_amend_contract_non_serializable_value_fails` — `contribute({"ProjectConfig": {"stamp": object()}})`; assert `"structurally malformed contribution"` and `"value of type object"` in `str(excinfo.value)`
  - `test_amend_contract_empty_nested_mapping_fails` — `contribute({"ProjectConfig": {}})`; assert `"empty mapping at the merged contribution.ProjectConfig"` in `str(excinfo.value)`
  - `test_amend_contract_non_dict_mapping_value_fails` — `contribute({"ProjectConfig": {"cfg": MappingProxyType({"a": 1})}})`; assert `"value of type mappingproxy at the merged contribution.ProjectConfig.cfg"` in `str(excinfo.value)`
  - `test_amend_contract_cyclic_contribution_fails_at_the_commit_point` — `cyclic = {"note": "a cell fact"}; cyclic["self"] = cyclic`; `contribute({"ProjectConfig": cyclic})`; assert `"circular reference at the merged contribution.ProjectConfig.self"` in `str(excinfo.value)`
  - `test_amend_contract_unknown_address_is_a_clean_error` — `pin_package_environment({})` and monkeypatch `goga.contract.hooks.events.declared_actions` with a function returning every record except `domain="contract"`; assert `str(excinfo.value) == "unknown hook action: contract.amend_contract"`
  - `test_amend_contract_undeclared_type_address_fails_naming_type` — `contribute({"NotDeclared": {"x": 1}})`; assert `str(excinfo.value) == "tool docs failed on contract.amend_contract at goga/config: contribution addresses undeclared type NotDeclared"`
  - `test_amend_contract_broken_facade_raises_import_error` — `boundary = pin_package_environment({"goga_tool_broken": ["broken-dist"]})` then `boundary.side_effect = ImportError("cannot import goga_tool_broken")`; assert `pytest.raises(ImportError)` and `"cannot import goga_tool_broken"` in `str(excinfo.value)`
- [ ] **Logic tests (edge)**:
  - `test_amend_contract_cell_without_types_rejects_any_contribution` — input `CellFacts(path="goga/empty", types=[])`, tool contributes `{"ProjectConfig": {"x": 1}}`; assert `"contribution addresses undeclared type ProjectConfig"` in `str(excinfo.value)`
  - `test_amend_contract_routine_type_receives_tools_area` — contributes `{"load_project_config": {"calls": 4}}`; assert `result == {"load_project_config": {"docs": {"calls": 4}}}`
  - `test_amend_contract_tool_view_lists_are_not_shared` — `docs` hook does `context.cell.types.append(...)` (in-place write through its fresh view), `lint` contributes normally; assert the result carries only `lint` and `len(cell.types)` unchanged after the call
  - `test_construction_enumerates_nothing` — `boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})`; bare `ContractHooks()`; assert `boundary.call_count == 0`
- [ ] **Debugging**: `pytest tests/contract/hooks/ -v` — fix implementation code until all tests pass (do NOT fix test code; the asserted message strings are contractual)
- [ ] **Contract re-verification**: the delivery obeys the manifest Constraints — no skipped subscriber, no application outside the single composition, no configuration/git/filesystem reads, no printing; `ImportError` keeps its type; the two-level merge is present (a flat schema-style `dict.update(payload)` merge fails the repeated-address tests)
- [ ] **Lint**: `ruff check goga/ tests/` and `ruff format --check goga/ tests/`

### Task 7: The zone facade — complete `__init__.py` (infrastructure with contract tests)

Complete the placeholder from Task 2 into the contract facade: the eight names re-exported from the four modules, `__all__` sorted (house style). The module docstring names the zone and its re-exported contract names (mirror `goga/schema/hooks/__init__.py`).

**Usages relevant to this task:**
- `convention`: the facade exposes the full contract API through `__all__`; only identifiers listed in `__all__` constitute the facade.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.**

- [ ] **Contract tests**: create `tests/contract/hooks/test_facade.py` — `test_facade_reexports_the_zone_contract_names` (designed scenario, verbatim): `import goga.contract.hooks as facade`; assert `sorted(facade.__all__) == ["CellFacts", "ContractAmendment", "ContractHooks", "FormFacts", "MemberFacts", "ToolContribution", "TypeFacts", "merge_type_contributions"]` and `facade.ContractHooks is goga.contract.hooks.events.ContractHooks`; plus identity checks for the remaining seven names against their modules and `facade.__all__ == sorted(facade.__all__)` (expected to fail — the facade is a placeholder)
- [ ] **Code**: rewrite `goga/contract/hooks/__init__.py` — docstring + `from .amendments import ContractAmendment`, `from .events import ContractHooks`, `from .facts import CellFacts, FormFacts, MemberFacts, TypeFacts`, `from .overlay import ToolContribution, merge_type_contributions`, and the sorted eight-name `__all__`
- [ ] Verify facade accessibility: `python -c "from goga.contract.hooks import CellFacts, ContractAmendment, ContractHooks, FormFacts, MemberFacts, ToolContribution, TypeFacts, merge_type_contributions; print('facade ok')"` — also the command's five-name subset `from goga.contract.hooks import CellFacts, ContractHooks, FormFacts, MemberFacts, TypeFacts`
- [ ] Verify: `pytest tests/contract/hooks/ -v` — the whole zone suite (facts, amendments, overlay, events, facade) is green
- [ ] Lint: `ruff check goga/ tests/` and `ruff format --check goga/ tests/`

### Task 8: The command — checkpoint delivery and tools composition (TDD coding)

The changed entity `contract(cells, lang)` (cell `goga/commands/contract`, `location: contract.py`) gains algorithm steps 5–6 and the `tools` output key. Four changes to the existing file, nothing else:

1. **Imports** — add `from ...contract.hooks import CellFacts, ContractHooks, FormFacts, MemberFacts, TypeFacts` (the five names the manifest Imports declare; the command never touches `ContractAmendment`, `ToolContribution`, `merge_type_contributions`).
2. **New helper** `_build_cell_facts(path: str, compare: dict) -> CellFacts` — module-level, private, Google-style docstring; the pure projection per the Context trace (`FormFacts(**pair)` for the signature and each member; `node.get("properties", {})` / `node.get("methods", {})` yield `[]` for routines).
3. **Delivery block** after the existing comparison loop (verbatim from the design):

```python
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

   The command constructs `ContractHooks()` exactly once per run and reuses it across cells — do not construct it inside the per-cell loop.
4. **Command docstring/help** — extend the per-cell JSON description with the `tools` key: present on a type node exactly when at least one installed tool package contributed at least one fact for that type through the contract amendment checkpoint; each inner key is the contributing tool's identity. Keep the `\b` block structure of the existing help.

Errors: only the new checkpoint wrap (both types → `ClickException`, exit 1, stderr; stdout stays clean — the dump happens after the loop). Edge cases: zero cells requested → `result == {}` → no delivery → `{}` output (unchanged); a path spelled two ways in one invocation → compared twice (identical value), checkpoint delivered once; `--lang` still wins over the effective configuration.

**Usages relevant to this task:**
- `contract-checkpoints` (from `goga/contract/hooks`): run the built-in comparison first, walk unique normalized paths in first-request order, build facts from the command's own comparison data, place each returned tools area on its type's node, wrap `ValueError`/`ImportError` into the clean command error.
- `click`: `ClickException` for the wrap; the command surface (decorators, arguments) is unchanged.
- `beautiful_json`: the single `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)` after the loop — unchanged code path, now carrying the tools areas.
- `convention`: CLI command docstring rules (no `Args`/`Returns`/`Raises` sections in the callback docstring; the `\f` marker for developer-facing notes).
- `loading`, `use_contract`, `project-configuration`, `checkpoints` (pre-existing imports of the command manifest): steps 1–4 they govern are unchanged by this task — the delivery block is appended after them without touching their code paths.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/commands/test_contract.py` the existing `TestFacadeAvailability` / `TestApiShape` classes keep passing unchanged (the argument surface is untouched — run them first); add `test_contract_help_mentions_tools_area`: `["contract", "--help"]` output mentions the `tools` key and its presence rule (the manifest Requirement "command help must explain the response structure, including the tools-area semantics") (the help assertion fails at this stage)
- [ ] **Code**: apply the four changes above to `goga/commands/contract/contract.py` — imports, `_build_cell_facts`, the delivery block, the help extension; nothing else in the file changes
- [ ] **Interface verification**: `pytest tests/commands/test_contract.py -v -k "Facade or ApiShape or help"` — the command surface and help tests pass
- [ ] **Logic tests**: add `test_contract_command_output_identical_without_tools` (designed scenario, verbatim): the standard tmp project (`_write_entity_cell` pattern — `ENTITY_CODEMANIFEST` + `ENTITY_IMPL` + `_write_goga_yml`, `_cwd` + `_sys_path`) with `pin_package_environment({})`; `_run_contract("cell_one")`; assert `exit_code == 0` and the full-structure equality `json.loads(stdout) == {"cell_one": {"MyClass": {"signature": {"codemanifest": "()", "implementation": "()"}, "properties": {"name": {"codemanifest": "str", "implementation": "str"}}, "methods": {"do_it": {"codemanifest": "(x: int) -> str", "implementation": "(x: int) -> str"}}}}}` and `"tools" not in payload["cell_one"]["MyClass"]` (the determinism of the dump makes structure equality equivalent to byte-identity)
- [ ] **Debugging**: `pytest tests/commands/test_contract.py -v` — fix implementation code until all tests pass (do NOT fix test code); the pre-existing command tests (empty cells, not found, not importable, config failures) must stay green — existing failure precedence is preserved by keeping two sequential loops
- [ ] **Contract re-verification**: stdout carries nothing but the JSON; the `tools` key is placed iff non-empty and never as `{}`; the surface constructs `ContractHooks()` once; no contribution validation happens in the command
- [ ] **Lint**: `ruff check goga/ tests/` and `ruff format --check goga/ tests/`

### Task 9: Integration tests for the command checkpoint (integration tests)

Cross-cell scenarios through the real platform: the CLI command ↔ the zone ↔ the real registry and delivery ↔ fake tool packages installed through the pinned boundary fixtures. All go into `tests/commands/test_contract.py`, composing the existing helpers (`_run_contract`, `_write_entity_cell` / `_write_goga_yml` + `_write_codemanifest` + `ENTITY_CODEMANIFEST`/`ENTITY_IMPL`, `_sys_path`, the `cwd` fixture) with `pin_package_environment` / `install_tool_package`. The registry, registrars, and delivery run for real.

**Usages relevant to this task:**
- `convention`: CLI tests invoke the command through the click app; boundary mocks only at the two outside-world points (the distributions read and `sys.modules`).
- `contract-checkpoints` (from `goga/contract/hooks`): the consumer practice these scenarios pin end-to-end.

**CRITICAL: `CODEMANIFEST` files and `.usages/` practice files are read-only contract definitions. Do NOT modify them.**

- [ ] Create the scenarios in `tests/commands/test_contract.py` (new class `TestContractCheckpointIntegration`):
- [ ] `test_contract_command_places_tools_area_on_type_node` (designed scenario, verbatim): tmp project with `cell_one` (`ENTITY_CODEMANIFEST`/`ENTITY_IMPL`), `_write_goga_yml`, `_sys_path`; environment pinned with `goga_tool_docs` whose hook subscribes `("contract", "amend_contract", "cover")` and contributes `{"MyClass": {"coverage": 3}}`; `_run_contract("cell_one")`; assert `exit_code == 0`, `json.loads(stdout)["cell_one"]["MyClass"]["tools"] == {"docs": {"coverage": 3}}`, and `["cell_one"]["MyClass"]["signature"]["codemanifest"]` unchanged
- [ ] `test_contract_command_checkpoint_failure_is_clean_cli_error` (designed scenario, verbatim): the same tmp project; `goga_tool_docs` whose hook subscribes `("contract", "amend_contract", "cover")` and raises `RuntimeError("boom")`; `_run_contract("cell_one")`; assert `result.exit_code == 1`, `"Error: hook cover of tool docs failed on contract.amend_contract"` in `result.output`, and `result.stdout == ""` (no partial JSON)
- [ ] `test_contract_command_duplicate_path_delivered_once` (designed scenario, verbatim): the tmp project; `goga_tool_docs` whose hook increments a counter on the tool `self` context and contributes `{"MyClass": {"calls": count}}`; `_run_contract("cell_one", "./cell_one")`; assert `exit_code == 0` and `json.loads(stdout)["cell_one"]["MyClass"]["tools"] == {"docs": {"calls": 1}}` (a counter of 2 would prove the regression)
- [ ] `test_contract_command_existing_failure_precedes_hooks` (designed scenario, verbatim): the tmp project; `goga_tool_docs` whose hook sets a module-level flag when invoked; request a nonexistent cell `_run_contract("no/such/cell")`; assert `result.exit_code == 1`, `"Error: document not found: no/such/cell"` in `result.output`, and the hook flag is `False` (the hook never ran)
- [ ] Run validation: `pytest tests/commands/test_contract.py -v` — all green; then the full gate `pytest tests/ -x`

### Task 10: Documentation pages for the contract checkpoint (documentation)

The MkDocs surface drifts once the action lands; `goga hooks` output gains the record automatically through `declared_actions()` — the six pages below are the manual updates (all content in English, modeled on the existing pages). Two of the six (`docs/features/hooks/index.md`, `docs/features/tools/hooks.md`) enumerate every declared action in prose and are maintained by hand — they do not pick the record up automatically.

**Usages relevant to this task:**
- `docs/features/schema/hooks.md` — the structural model for the contract hooks page (address table, hook signature example, delivered view fields, failure semantics).

**CRITICAL: `CODEMANIFEST` files and `.usages/` practice files are read-only contract definitions. Do NOT modify them.**

- [ ] Rewrite `docs/features/contract/hooks.md` (currently 5 lines stating the contract domain exposes no hook actions): model on `docs/features/schema/hooks.md` — the address table row `contract / amend_contract` (**hard**); a hook signature example subscribing the address and calling `context.contribute({"TypeName": {"fact": "value"}})`; the delivered view fields (`CellFacts.path`/`types`, `TypeFacts.name`/`signature`/`properties`/`methods`, `FormFacts.codemanifest`/`implementation`, `MemberFacts.name`/`form`); the failure semantics (the first failing tool stops the command; the message names the hook, the tool, the action, and the failing cell path; a bad address adds the offending type name; a broken package facade is the single fatal import case)
- [ ] Update `docs/features/hooks/hooks.md`: the `domain` + `action` enumeration bullet gains `"contract"` / `"amend_contract"` (**hard**) — the contract amendment, the read-and-contribute view over the comparison facts of one cell at the comparison moment (see [Contract — Hooks](../contract/hooks.md)); the error-class paragraph gains the contract amendment to the hard list with its stop-at-first-failure semantics
- [ ] Update `docs/features/hooks/api.md`: the staged-delivery consumer list gains the contract amendment (the fourth hard variant — a failing hook raises instead of being discarded); the per-domain hook-facade list gains `goga.contract.hooks` (the contract amendment zone — `ContractHooks`, `ContractAmendment`, `CellFacts`, `TypeFacts`, `FormFacts`, `MemberFacts`, `ToolContribution`, `merge_type_contributions`; see [Contract — Hooks](../contract/hooks.md)) — the page's `The action catalog` section carries only the signature block, no per-record table
- [ ] Update `docs/features/contract/cli.md`: the Output section example gains the `"tools": { "tool-name": { "fact": "value" } }` key on the entity node with the presence rule — the key appears on a type node exactly when at least one tool contributed at least one fact for that type
- [ ] Update `docs/features/hooks/index.md`: the "The declared actions today" enumeration gains the contract amendment — the `contract / amend_contract` action (**hard**), the read-and-contribute view over the comparison facts of one cell at the comparison moment, with the link to [Contract — Hooks](../contract/hooks.md)
- [ ] Update `docs/features/tools/hooks.md`: the per-domain enumeration of the declared actions ("the declared actions are listed per domain (today: …)") gains the contract amendment of the contract domain — `contract/amend_contract` (**hard**) — alongside the schema and usages entries, with the link to [Contract — Hooks](../contract/hooks.md)
- [ ] Run validation: `grep -rn "amend_contract" docs/features/` shows the new rows on all six pages, no page still claims the contract domain exposes no hook actions, and no catalog-enumerating page (`docs/features/hooks/index.md`, `docs/features/tools/hooks.md`) lacks the contract amendment; `pytest tests/ -x` and `ruff check goga/ tests/` confirm no incidental breakage (docs-only change)

---

## Validation Commands

- `python -c "from goga.contract.hooks import CellFacts, ContractAmendment, ContractHooks, FormFacts, MemberFacts, ToolContribution, TypeFacts, merge_type_contributions; print('facade ok')"`: Verify that all eight facade entities are importable from the zone facade
- `pytest tests/contract/hooks/ -v`: Run the zone suites (facts, amendments, overlay, events, facade)
- `pytest tests/commands/test_contract.py tests/hooks/catalog/ -v`: Run the extended command and catalog suites
- `pytest tests/ -x`: Run all tests
- `ruff check goga/ tests/`: Lint check
- `ruff format --check goga/ tests/`: Format check (the CI lint gate)
- `goga lint`: The manifest gate — 82 cells, 0 errors expected (the contracts are read-only and must stay lint-clean)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`facts.py`, `amendments.py`, `overlay.py`, `events.py` — flat files beside the CODEMANIFEST)
- [ ] Every contract entity is accessible from the facade (`goga.contract.hooks`, eight names in sorted `__all__`)
- [ ] Properties and methods match the declared API (constructor signatures, `contribute`, `amend_contract`, `merge_type_contributions`)
- [ ] Descriptions are reflected in behavior (pure facts, verbatim buffering, two-level merge with later-write-wins, tool-granular commit, hard-stop semantics, byte-stable error messages)
- [ ] Contract dependencies are met (`HookRegistry`, `wrap_context`, `build_hook_arguments`, `declared_actions` from `goga/hooks`; the five names in the command's Imports)
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them (Task 9 — the four CLI checkpoint scenarios)
- [ ] All 33 designed test scenarios from the design document are implemented (24 events + 1 facts + 1 overlay + 1 facade + 5 command + 1 catalog), plus the mirrored contract-test classes and the help-text test
- [ ] The six documentation pages are updated (`docs/features/contract/hooks.md`, `docs/features/hooks/hooks.md`, `docs/features/hooks/api.md`, `docs/features/contract/cli.md`, `docs/features/hooks/index.md`, `docs/features/tools/hooks.md`)
- [ ] No package boundary was expanded (no new cells; the zone imports `goga/hooks` only; the command imports the five declared names only)
- [ ] `CODEMANIFEST` files, `.usages/` practice files, `Dockerfile`, `goga/assets/pipelines/*.yml`, and `.goga/history/` files were not modified (contract and out-of-scope assets are read-only)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `click`, `beautiful_json`, `per-tool-delivery`, `registering-hooks`, `contract-checkpoints`, `loading`, `use_contract`, `project-configuration`, `checkpoints`)
