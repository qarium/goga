# Plan: `add-hooks-to-schema`

Result of Phase 1 (structure) + Phase 2 (Usages calibration).
Compiled from `.goga/history/2026/add-hooks-to-schema/design.md` (post design-review).
This format is compatible with ralphex execution.

---

## Purpose

Deliver the cell-amendment checkpoint — the hooks zone of the schema domain.
After implementation:

- the action catalog carries `domain="schema"`, `name="amend_cell"`,
  `error_class="hard"` (the 20th record);
- the new zone `goga/schema/hooks` provides the per-cell authored-facts read
  view (`CellFacts` / `DependencyFacts`), the per-tool read-and-contribute
  view (`CellAmendment.contribute`), the deterministic tools-area composition
  (`ToolContribution`, `merge_cell_contributions`), and the checkpoint surface
  (`SchemaHooks.amend_cell`) over the platform facade `goga.hooks`;
- the `schema` generation walk delivers the checkpoint for every surviving
  cell and places the returned tools area on the node under the `tools` key
  (iff non-empty);
- the CLI `schema` command converts **every** error of `schema_logic` — AST
  errors, checkpoint hard failures, register-facade import failures — into a
  clean stderr message + exit 1.

The most important gaps between contract and code: the zone has a CODEMANIFEST
and `.usages/` on disk but **zero implementation**; the catalog lacks the
record; the walk delivers nothing; the CLI catches `ValueError` only (a
register-facade `ImportError` would reach the terminal as a raw traceback).

Overall strategy: implement in the dependency order catalog → zone
(facts → amendments → overlay → events → facade) → walk → CLI, mirroring the
config zone (`goga/config/hooks/`) structurally, one TDD task per module,
ralphex protocol inside every coding task.

## Context

### Interaction and Data Flow (verbatim from the design)

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

Data flows:

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

### Contract Surface

**Entity: `declared_actions()`** (modified — data only)
- Type: routine (existing, on the `goga.hooks.catalog` facade)
- Declared `location`: `goga/hooks/catalog/catalog.py`
- Change: append `Action(domain="schema", name="amend_cell",
  error_class="hard")` to `_DECLARED_ACTIONS` (after the config record,
  domain-addition order). `declared_actions()` sorts by `(domain, name)` —
  the record's sorted position is between `("pipeline", "run_created",
  "soft")` and `("statuses", "register_statuses", "soft")`.
- No entity, algorithm, or constraint text changes; published records
  untouched (catalog additivity law).

**Entity: `CellFacts`** (new)
- Type: class — frozen `kw_only` dataclass, properties only
- Declared `location`: `goga/schema/hooks/facts.py`
- Facade obligation: importable from `goga.schema.hooks`
- Properties: `path -> str`, `description -> str`, `types -> list[str]`,
  `usages -> list[str]`, `dependencies -> list[DependencyFacts]`,
  `children -> list[str]`
- Semantic requirements: pure facts — the constructing operation passes
  resolved values, nothing is read inside; authored projection only —
  identical in every run regardless of filters; never another tool's
  contributions, generated data, or the run's filter parameters
- Edge cases: all-list fields may be empty (`usages == []` with no
  `.usages/`; `children == []` for leaves; `dependencies == []` for
  import-free cells)
- Imported dependencies: none (zone-internal `DependencyFacts`)

**Entity: `DependencyFacts`** (new)
- Type: class — frozen `kw_only` dataclass, properties only
- Declared `location`: `goga/schema/hooks/facts.py`
- Facade obligation: importable from `goga.schema.hooks`
- Properties: `path -> str`, `types -> list[str]`, `usages -> list[str]`
- Semantic requirements: pure data — constructed by the caller from the
  document's imports

**Entity: `CellAmendment`** (new)
- Type: class — `kw_only` dataclass (NOT frozen: it owns the mutable buffer)
- Declared `location`: `goga/schema/hooks/amendments.py`
- Facade obligation: importable from `goga.schema.hooks`
- Property: `cell -> CellFacts` — the authored facts of the cell being
  built; read-only and identical for every tool
- Method: `contribute(facts: dict[str, object])` — buffer one fact-mapping
  contribution of this tool
- Semantic requirements: the call buffers into the buffer of this tool alone
  and changes nothing until the delivery commits it; the buffer merges
  key-wise (a later write replaces an earlier one on key conflict); an empty
  mapping contributes nothing
- Constraints: do not cancel, redirect, or defer the operation
- Internal state: `_pending` list (`field(init=False,
  default_factory=list, repr=False)`) — private-buffer access from the
  delivery is the config-zone precedent
- Imported dependencies: `CellFacts` from `.facts`

**Entity: `ToolContribution`** (new)
- Type: class — frozen `kw_only` dataclass, properties only
- Declared `location`: `goga/schema/hooks/overlay.py`
- Facade obligation: importable from `goga.schema.hooks`
- Properties: `tool -> str` (the tool identity assigned by the platform),
  `facts -> dict[str, object]` (the committed contribution)
- Semantic requirements: pure data — constructed by the checkpoint delivery
  alone

**Routine: `merge_cell_contributions(contributions: list[ToolContribution]) -> tools: dict[str, dict[str, object]]`** (new)
- Declared `location`: `goga/schema/hooks/overlay.py`
- Facade obligation: importable from `goga.schema.hooks`
- Algorithm: (1) take the contributions in enumeration order; (2) skip a
  contribution whose mapping is empty — a tool's key exists iff that tool
  wrote at least one fact; (3) place each remaining mapping under its tool
  identity key; (4) return the composed mapping — empty when every
  contribution was empty or none committed
- Requirements: deterministic; pure — the inputs stay unmutated, the result
  is a new mapping; structural validation is not here (it happened at the
  tool commit point of the delivery)
- Constraints: do not read or write the filesystem; do not mutate
  `contributions` or their maps

**Entity: `SchemaHooks`** (new)
- Type: class (plain class, no constructor parameters)
- Declared `location`: `goga/schema/hooks/events.py`
- Facade obligation: importable from `goga.schema.hooks`
- Method: `amend_cell(cell: CellFacts) -> tools: dict[str, dict[str, object]]`
- Requirements: cheap construction — no enumeration and no imports at
  construction; one `HookRegistry` per run (assembly once per run whatever
  the number of checkpoints); every context is built from the values the
  caller passes — no repository, git, or file reads at the checkpoint
- Full delivery algorithm: see Task 6 (verbatim)
- Imported dependencies: `HookRegistry`, `wrap_context`,
  `build_hook_arguments`, `declared_actions` from the platform facade
  `goga.hooks` (`from ...hooks import ...` — three dots up, no import cycle);
  zone-internal `.facts`, `.amendments`, `.overlay`

**Routine: `schema(cells, max_depth, depends_on)`** (modified — `goga/schema`)
- Declared `location`: `goga/schema/schema.py` (already on the
  `goga.schema` facade — unchanged facade)
- Change: the generation walk now delivers the cell-amendment checkpoint for
  every surviving cell and places the returned tools area on the node (iff
  non-empty). Full walk algorithm: see Task 7 (verbatim)
- New node field: `"tools": {<tool identity>: {<fact>: <value>}}` — present
  iff at least one tool wrote at least one fact on that cell; never an empty
  object at any of the three levels
- The six base fields of every node are exactly what they would be without
  the extension; with no subscriptions (or no tool packages installed) the
  output is byte-identical to the six-field map
- Errors: propagates `ValueError` (AST count; checkpoint hard failures
  naming tool/action/cell path) and `ImportError` (register facade naming
  the package); never prints, never returns partial JSON

**Routine: `schema` CLI command** (modified — `goga/commands/schema`)
- Declared `location`: `goga/commands/schema/schema.py` (already registered
  on the `goga.cli` app — unchanged facade)
- Change: broaden `except ValueError` to `except Exception` — every error of
  `schema_logic` converts to stderr + exit 1; nothing on stdout, no raw
  traceback; `BaseException` (`KeyboardInterrupt` / `SystemExit`) passes
  through untouched
- Also: the command docstring's structure block gains the `tools` line
  (after `children`) so `--help` documents the extended node

### Re-exports

- `goga/schema/hooks/__init__.py` (Python facade): `__all__` must expose
  exactly `CellAmendment`, `CellFacts`, `DependencyFacts`, `SchemaHooks`,
  `ToolContribution`, `merge_cell_contributions` — every name importable
  from `goga.schema.hooks`. Built incrementally (config-zone precedent:
  "each entity task added its module"); completed in Task 6.
- `goga/schema/__init__.py`: `schema` already exported — no change.
- `goga/commands/schema/__init__.py`: command wiring unchanged — no change.
- `goga/hooks/catalog/__init__.py`: `Action`, `declared_actions` already on
  the facade — no change.

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — mandatory Python
  conventions: relative imports, `kw_only` dataclasses, Google docstrings
  (Args/Returns/Raises), test structure mirroring
  (`tests/schema/hooks/` ← `goga/schema/hooks/`), test naming
  (`test_<what>_<scenario>`, classes `Test<Component>`), `tmp_path` for file
  I/O, mocks only at external boundaries, Python 3.10+ compatibility.
- `documents` (inline, `goga/schema`) — the AST load contract:
  `ast_obj = AST("."); ast_obj.load()`; `ast_obj.tree` for the walk;
  `ast_obj.errors` for the count guard.
- `beautiful_json` (inline, `goga/schema`) — output serialization:
  `json.dumps(result, indent=4, sort_keys=True, ensure_ascii=False)`; the
  `tools` key sorts alphabetically among the node keys deterministically.
- `click` (`.goga/usages/cooks/click.md`, `goga/commands/schema`) — CLI
  command construction; unchanged decorators; `click.echo(result)` for
  stdout; `click.echo(str(e), err=True)` + `ctx.exit(1)` for failures.

### Imported Usages

- `per-tool-delivery` from `goga/hooks` —
  `goga/hooks/.usages/per-tool-delivery.md`: the staged delivery loop
  skeleton (registry + `build_once`, `subscriptions_for` grouping by tool,
  `wrap_context` / `build_hook_arguments` projection, tool-granular commit,
  one registry per run, deliver to every subscriber). Applies to Task 6
  as written, with the schema-domain hard semantics (stop at first failure)
  replacing the soft skip of the usage's example.
- `registering-hooks` from `goga/hooks` —
  `goga/hooks/.usages/registering-hooks.md`: the registration contract
  behind the checkpoint — facade `register_hooks`, `subscribe(domain,
  action, name, hook)`, offered parameter names `context` / `self`, failure
  behavior (a broken package import is the only fatal case). Applies to
  Tasks 4 and 6.
- `checkpoints` from `goga/schema/hooks` —
  `goga/schema/hooks/.usages/checkpoints.md`: the zone's consumer
  documentation — the `SchemaHooks()` surface, the per-cell amend loop,
  hard-failure handling, output shape. Applies to Tasks 7, 8, 9.

### Local Usages

All `.usages/` files of this topic are already on disk (created/updated by
the architecture stage; verified current by the design review, including the
applied empty-mapping fix). **No creation tasks are needed**; Task 9 carries
the final existence/consistency verification.

- `goga/schema/hooks/.usages/checkpoints.md` — zone consumer docs
  (`SchemaHooks`, `CellFacts`, `DependencyFacts`). Status: on disk, current.
- `goga/schema/.usages/registering-hooks.md` — domain-level tool-author
  docs (`CellAmendment`, `contribute`, the `schema / amend_cell` address).
  Status: on disk, current.
- `goga/schema/.usages/schema-usage.md` — node example carries the
  conditional `tools` field; Side Effects carry the checkpoint delivery and
  byte-identity bullets. Status: on disk, current.
- `goga/commands/schema/.usages/schema.md` — Purpose carries the tools
  sentence; Exit codes carry the checkpoint hard-failure entry. Status: on
  disk, current.
- `goga/hooks/catalog` has no `.usages/` directory — skip (catalog
  additivity law: the record bullet is the whole change).

### External Dependencies

- None new. stdlib only (`dataclasses`, `collections.abc`, `math`,
  `json`, `os`, `pathlib`); the platform facade `goga.hooks` is in-repo;
  `click`, `pytest`, `ruff` are already project dependencies.
  Ruff line-length: 120.

## Facts

- The four CODEMANIFESTs and every `.usages/` file of the topic are already
  on disk; `goga lint` reports 81 cells, 0 errors. The manifests are
  read-only for the implementation agent.
- Dependency graph: exactly `goga/schema` and `goga/commands/schema` import
  the zone (`goga schema --depends-on goga/schema/hooks` confirms the
  subtree). No import cycle: the zone imports only `goga.hooks`
  (`from ...hooks import ...`), never `goga.schema`.
- The platform derives the tool identity from the package name:
  `goga_tool_docs` → `docs` (canonical hyphen form without the
  `goga_tool_` prefix); a tool never names itself.
- `declared_actions()` sorts by `(domain, name)`; with the record added the
  catalog has 20 records and the schema block orders between `pipeline` and
  `statuses`.
- The config zone (`goga/config/hooks/`: `events.py`, `amendments.py`,
  `overlay.py`, `__init__.py`) is the structural mirror — module layout,
  `_ensure_registry` shape, per-tool delivery loop, frozen `kw_only`
  records, private-buffer access from the delivery, docstring density.
- The existing walk helpers (`_filter_tree`, `_build_cell_tree`,
  `_filter_by_depends_on`, `_prune_depth`, `_find_usages_files`,
  `_build_dependencies`) are unchanged; the delivered facts values mirror
  their outputs exactly (sorted types, sorted usages, normalized paths).
- The structural check must be an explicit recursive validator — NOT a
  `json.dumps` try/except (dumps coerces non-string keys and accepts
  NaN/Infinity; both must fail). Non-mapping payloads are rejected at the
  commit merge with a per-payload `collections.abc.Mapping` guard BEFORE
  `dict.update` runs — `dict.update` would silently accept an iterable of
  key-value pairs and coerce it into a valid mapping.
- Pinned failure formats (verbatim):
  `unknown hook action: schema.amend_cell`;
  `hook {name} of tool {tool} failed on schema.amend_cell at {cell_path}: {reason}`;
  `tool {tool} failed on schema.amend_cell at {cell_path}: structurally malformed contribution ({detail})`.
- Boundary fixtures for tests: `pin_package_environment` (pins
  `goga.hooks.tools.packages.packages_distributions`, returns the boundary
  mock for `call_count` assertions) and `install_tool_package` (installs a
  fake `goga_tool_*` facade into `sys.modules`) — both in
  `tests/hooks/conftest.py`, re-exported by `tests/config/hooks/conftest.py`
  and `tests/commands/conftest.py`; `tests/schema/conftest.py` does not
  exist yet (created in Task 7).
- Shared test helpers: `tests/conftest.py` provides the `cwd` context
  manager (`from tests.conftest import cwd as _cwd`) and the
  `is_kw_only_dataclass` helper (portable across Python 3.10–3.14).
- The broken-package test precedent is
  `test_build_once_broken_import_is_fatal_through_the_real_import` in
  `tests/hooks/registry/test_state.py`: a `tmp_path` package dir whose
  `__init__.py` imports a missing dependency + `syspath_prepend` + pinned
  environment — the platform wrapper raises
  `ImportError("package goga_tool_broken failed to import: ...")`.
- The CLI currently catches `ValueError` only; the platform precedent for
  the broadened catch is `emit_hook_event` (catches `Exception` only —
  `BaseException` passes through).
- Frozen-dataclass semantics: `FrozenInstanceError` subclasses
  `AttributeError`, so the registering-hooks promise "attribute assignment
  is blocked" is satisfied by frozen `kw_only` dataclasses.

## Gap Analysis

- Missing contract entities: the entire zone implementation —
  `goga/schema/hooks/facts.py`, `amendments.py`, `overlay.py`, `events.py`,
  `__init__.py` do not exist (only CODEMANIFEST + `.usages/` on disk).
- Missing facade exposure: `goga.schema.hooks` is not an importable package
  yet (`__init__.py` absent).
- Missing catalog record: `_DECLARED_ACTIONS` carries 19 records; the
  contract requires the schema record as the 20th.
- Behavioral mismatches:
  - `schema()` delivers no checkpoint and places no `tools` key; it also
    lacks the explicit early `"[]"` return (an empty tree must skip package
    enumeration entirely — the registry must never build);
  - the CLI converts only `ValueError` — a register-facade `ImportError`
    would reach the terminal as a raw traceback.
- Existing code that can be reused: all walk/filter helpers (unchanged);
  `_build_dependencies` normalization for the facts; the platform facade
  `goga.hooks`; the config zone as the structural mirror; the boundary
  fixtures and their conftest re-exports (`tests/commands/conftest.py`
  already re-exports them for CLI tests).
- Test coverage gaps: no `tests/schema/hooks/` suite; catalog tests pin the
  count to 19; `tests/schema/test_schema.py` and
  `tests/commands/test_schema.py` have no delivery / failure-conversion
  tests.
- Missing visibility in workspace or git: none — the contract and usage
  files are already committed to the working tree of this topic branch.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within each coding task, contract tests are written first (TDD workflow). Package order: `goga/hooks/catalog` → `goga/schema/hooks` → `goga/schema` → `goga/commands/schema` → integration. Only ONE task is executed per ralphex iteration.

### Task 1: Add the `schema.amend_cell` record to the action catalog (TDD coding)

The catalog is the single source of known subscription addresses; every
later step of this plan resolves `("schema", "amend_cell")` against it, so
the record lands first. This task touches exactly one data constant and its
test file: append `Action(domain="schema", name="amend_cell",
error_class="hard")` to `_DECLARED_ACTIONS` in
`goga/hooks/catalog/catalog.py` (after the `config` record —
domain-addition order; the sorted position is irrelevant to behavior but
keep the list tidy), and update `tests/hooks/catalog/test_catalog.py`
(counts pinned to 19 must become 20, the frozen full-catalog list gains the
row, and a new record test mirrors the config record test). The CODEMANIFEST
Requirements already carry the record bullet — the manifest is read-only.

**Usages relevant to this task:**
- `convention`: maintained data only — no mocks in catalog tests; test
  naming `test_<what>_<scenario>`; class grouping `Test<Component>`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: in `tests/hooks/catalog/test_catalog.py` (`TestCatalogContract`), add `test_schema_amend_cell_record_present` mirroring `test_config_amend_config_record_present`: assert `Action(domain="schema", name="amend_cell", error_class="hard") in records`; a `pre_existing` list of the other 19 triples with `all(triple in triples ...)`; `len(triples) == len(pre_existing) + 1`; the schema block is exactly `[("amend_cell", "hard")]`; `domains.index("pipeline") < domains.index("schema") < domains.index("statuses")`; `pairs == sorted(pairs)` and unique; `len(records) == 20` (expected to fail — the record is absent)
- [x] **Code**: append `Action(domain="schema", name="amend_cell", error_class="hard")` to `_DECLARED_ACTIONS` in `goga/hooks/catalog/catalog.py`, after the `config` record; no other line changes
- [x] **Interface verification**: `pytest tests/hooks/catalog/test_catalog.py -k schema_amend_cell_record_present -x` — the new record test passes
- [x] **Logic tests**: update the stale pins in `tests/hooks/catalog/test_catalog.py`: the three `len == 19` assertions → `20` (the topics block test, the pipeline block test, the config record test); the pipeline test docstring "the catalog grows to 19 records additively" → 20; insert `("schema", "amend_cell", "hard")` into the frozen `expected` list of `test_catalog_carries_the_five_build_records` (sorted position between `("pipeline", "run_created", "soft")` and `("statuses", "register_statuses", "soft")`); add the schema triple to the `pre_existing` list of `test_config_amend_config_record_present` (its derived `len(triples) == len(pre_existing) + 1` then stays consistent)
- [x] **Debugging**: `pytest tests/hooks/catalog -x` — all pass (fix implementation code, not test code, if the record test and the pins disagree)
- [x] **Contract re-verification**: `Action` / `declared_actions` still importable from `goga.hooks.catalog`; no published record rewritten; the record sorts between `pipeline` and `statuses`
- [x] **Lint**: `ruff check goga/hooks/catalog tests/hooks/catalog` — fix formatting if necessary

### Task 2: Zone skeleton — importable package and test scaffolding (infrastructure)

Create the importable skeleton of the zone so later entity tasks can land
module by module (the config-zone build pattern: "each entity task added its
module"). No contract entity is implemented here — only the package marker
and the test scaffolding. `goga/schema/hooks/` currently contains only
`CODEMANIFEST` and `.usages/`.

**Usages relevant to this task:**
- `convention`: test directories must contain `__init__.py`; local fixtures
  live in `tests/<package>/conftest.py`; the suite mirrors
  `goga/schema/hooks/` as `tests/schema/hooks/`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Code**: create `goga/schema/hooks/__init__.py` — a module docstring naming the zone (the hooks zone of the schema domain: the per-cell read view, the per-tool contribution merge, the checkpoint surface over the hooks platform) with the note that the zone is built incrementally and each entity task adds its module, plus `__all__: list[str] = []` (the six contract names land with their entity tasks; the facade completes in Task 6)
- [x] **Code**: create `tests/schema/hooks/__init__.py` (empty package marker)
- [x] **Code**: create `tests/schema/hooks/conftest.py` mirroring `tests/config/hooks/conftest.py`: a docstring explaining the re-export, then `from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401`
- [x] Verify facade accessibility: `python -c "import goga.schema.hooks; print(goga.schema.hooks.__all__)"` prints `[]`; importing the package enumerates no tool packages and reads no distributions (verified with a spy on `packages_distributions` — 0 calls during import)
- [x] Verify test scaffolding: `pytest tests/schema/hooks --collect-only -q` collects no tests and reports no collection errors — exit code 5 is the expected outcome at this point (the suite is empty until Task 3; any exit other than 5, or an `error` line, is a failure)
- [x] Lint: `ruff check goga/schema/hooks tests/schema/hooks` — fix formatting if necessary

### Task 3: `CellFacts` and `DependencyFacts` — the authored-facts read view (TDD coding)

The immutable authored-facts projection of one cell, delivered to subscribed
hooks. Both entities share `location: facts.py` → one task. Frozen `kw_only`
dataclasses, Google docstrings, `from __future__ import annotations`;
constructed by the caller (the schema walk, Task 7) from resolved values —
nothing is read inside.

**Usages relevant to this task:**
- `convention`: `kw_only` frozen dataclasses for the facts records; relative
  imports (`from .facts import ...` inside the zone); Google docstrings with
  Args/Returns/Raises; tests mirror `tests/schema/hooks/test_facts.py` ←
  `goga/schema/hooks/facts.py`; use `is_kw_only_dataclass` from
  `tests/conftest` for the kw_only assertion.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/schema/hooks/test_facts.py`: both names importable from the facade `goga.schema.hooks`; both are frozen `kw_only` dataclasses (`dataclasses.is_dataclass`, `__dataclass_params__.frozen`, `is_kw_only_dataclass`, positional construction raises `TypeError`); exact field sets — `CellFacts` fields are exactly `path, description, types, usages, dependencies, children`, `DependencyFacts` fields are exactly `path, types, usages` (via `dataclasses.fields`) (expected to fail — the module does not exist)
- [x] **Code**: create `goga/schema/hooks/facts.py` with a module docstring in the config-zone style; `CellFacts(path: str, description: str, types: list[str], usages: list[str], dependencies: list[DependencyFacts], children: list[str])` and `DependencyFacts(path: str, types: list[str], usages: list[str])` as `@dataclass(frozen=True, kw_only=True)`; docstrings carry the contract property descriptions and the pure-facts / authored-projection requirements
- [x] **Code**: update `goga/schema/hooks/__init__.py` — `from .facts import CellFacts, DependencyFacts` and extend `__all__` (keep it sorted)
- [x] **Interface verification**: `pytest tests/schema/hooks/test_facts.py -x` — all contract tests pass
- [x] **Logic tests**: fields hold the passed values verbatim (pure facts); edge cases — `usages == []` when the cell has no `.usages/`, `children == []` for leaves, `dependencies == []` for import-free cells all construct and compare equal; `facts.path = "x"` raises `dataclasses.FrozenInstanceError` (the direct-unit half of the blocked-assignment guarantee; also assert it surfaces as `AttributeError` — `FrozenInstanceError` subclasses it)
- [x] **Debugging**: `pytest tests/schema/hooks -x` — all pass
- [x] **Contract re-verification**: both names importable from `goga.schema.hooks`; no extra public names on the facade beyond `CellFacts` and `DependencyFacts` (plus whatever earlier tasks added)
- [x] **Lint**: `ruff check goga/schema/hooks tests/schema/hooks` — fix formatting if necessary

### Task 4: `CellAmendment` — the per-tool read-and-contribute view (TDD coding)

The context one tool receives at the checkpoint: `cell` (the per-tool fresh
facts view — read-only and identical for every tool) plus `_pending` (the
buffer of this tool's contributions). `contribute(facts)` appends the
payload verbatim — no validation, no interpretation; the commit (key-wise
merge, Mapping guard, structural check) is driven by the delivery and lands
in Task 6. Mirror `goga/config/hooks/amendments.py` structurally:
`@dataclass(kw_only=True)` (NOT frozen — it owns the mutable buffer),
`_pending: list = field(init=False, default_factory=list, repr=False)`.

**Usages relevant to this task:**
- `convention`: `kw_only` dataclasses; relative imports
  (`from .facts import CellFacts`); Google docstrings; tests mirror as
  `tests/schema/hooks/test_amendments.py`.
- `registering-hooks` (from Imports, `goga/hooks`): the hook signature that
  receives this view — a hook declares `context` and reads/calls freely,
  attribute assignment on the delivered object is blocked (the proxy lands
  in Task 6; the view itself just carries `cell` and the buffer).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: create `tests/schema/hooks/test_amendments.py`: `CellAmendment` importable from the facade; `kw_only` dataclass (not frozen — the buffer is mutable state); field set is exactly `cell` plus the internal `_pending` (`init=False`, `repr=False` — absent from the constructor signature and from `repr`); `contribute` exists with signature `(facts: dict[str, object]) -> None` (inspect the parameters and the empty return) (expected to fail)
- [x] **Code**: create `goga/schema/hooks/amendments.py`: module docstring in the config-zone style; `CellAmendment` with `cell: CellFacts`, `_pending: list = field(init=False, default_factory=list, repr=False)`, and `contribute(facts)` appending `facts` verbatim to `self._pending` and returning `None`; docstrings carry the contract Requirements — buffers into this tool's buffer alone, changes nothing until the delivery commits it, the buffer merges key-wise (later write replaces on conflict), an empty mapping contributes nothing — and the Constraint (do not cancel, redirect, or defer the operation)
- [x] **Code**: update `goga/schema/hooks/__init__.py` — `from .amendments import CellAmendment`, extend sorted `__all__`
- [x] **Interface verification**: `pytest tests/schema/hooks/test_amendments.py -x` — all contract tests pass
- [x] **Logic tests**: `contribute` buffers verbatim — `contribute({"a": 1, "b": 2})` then `contribute({"a": 3})` leaves `_pending == [{"a": 1, "b": 2}, {"a": 3}]`; `contribute({})` buffers `[{}]` (buffering changes nothing outside the view — validation is not here); a non-dict payload is also stored verbatim (no validation at the view; the delivery's guard is Task 6); `contribute` returns `None`; `view.cell` returns the passed `CellFacts`
- [x] **Debugging**: `pytest tests/schema/hooks -x` — all pass
- [x] **Contract re-verification**: facade exposes `CellAmendment` alongside the earlier names; signature and field set match the contract
- [x] **Lint**: `ruff check goga/schema/hooks tests/schema/hooks` — fix formatting if necessary

### Task 5: `ToolContribution` and `merge_cell_contributions` — the tools-area composition (TDD coding)

The overlay layer: one committed contribution (frozen `kw_only` pairing of
the tool identity with its merged fact mapping — constructed by the delivery
alone) and the deterministic pure routine composing the `tools` mapping.
Both share `location: overlay.py` → one task. Structural validation is NOT
here — it happened at the tool commit point of the delivery (Task 6).

**Usages relevant to this task:**
- `convention`: frozen `kw_only` dataclass for the record; Google docstrings
  with Args/Returns; pure routine (no filesystem, no mutation); tests mirror
  as `tests/schema/hooks/test_overlay.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/schema/hooks/test_overlay.py`: both names importable from the facade; `ToolContribution` is a frozen `kw_only` dataclass with exactly the fields `tool, facts` (positional construction raises `TypeError`); `merge_cell_contributions` is a module-level function with the signature `(contributions: list[ToolContribution]) -> dict` (expected to fail)
- [ ] **Code**: create `goga/schema/hooks/overlay.py`: module docstring in the config-zone style; `@dataclass(frozen=True, kw_only=True) class ToolContribution` with `tool: str` and `facts: dict[str, object]`; `merge_cell_contributions(contributions)` implemented as the composition `{c.tool: c.facts for c in contributions if c.facts}` with the contract's four-step algorithm in the docstring (enumeration order; skip empty — a tool's key exists iff that tool wrote at least one fact; place under the tool identity key; return `{}` when nothing committed)
- [ ] **Code**: update `goga/schema/hooks/__init__.py` — `from .overlay import ToolContribution, merge_cell_contributions`, extend sorted `__all__`
- [ ] **Interface verification**: `pytest tests/schema/hooks/test_overlay.py -x` — all contract tests pass
- [ ] **Logic tests**: `test_merge_cell_contributions_composes_in_enumeration_order` — with `ToolContribution(tool="alpha", facts={"x": 1})`, `ToolContribution(tool="beta", facts={"y": 2})`, `ToolContribution(tool="gamma", facts={})`: result `== {"alpha": {"x": 1}, "beta": {"y": 2}}`; `list(result) == ["alpha", "beta"]` (enumeration order preserved); inputs unchanged after the call (purity — the list and each mapping are unmutated); `merge_cell_contributions([]) == {}`; every contribution empty → `{}`
- [ ] **Debugging**: `pytest tests/schema/hooks -x` — all pass
- [ ] **Contract re-verification**: facade exposes both names; the routine is pure (no filesystem access, no input mutation)
- [ ] **Lint**: `ruff check goga/schema/hooks tests/schema/hooks` — fix formatting if necessary

### Task 6: `SchemaHooks` — the checkpoint surface; facade completion (TDD coding)

The core delivery task. `SchemaHooks` owns the lazily-built run registry and
drives the hard `schema / amend_cell` delivery per tool over the public
platform primitives, then commits each passing tool as one
`ToolContribution` and returns the composed tools area. This task also
completes the zone facade (all six contract names) and writes
`tests/schema/hooks/test_events.py` — the largest suite of the plan — plus
the zone facade suite `tests/schema/hooks/test_facade.py` (the
`tests/config/hooks/test_facade.py` precedent).

Delivery algorithm (verbatim from the contract and the design):

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

Implementation notes (mandatory, from the design's Additional
Instructions):
- `_read_only_view(cell)` builds a fresh `CellFacts` — fresh lists at every
  level (`types`, `usages`, `children` as new lists) and fresh
  `DependencyFacts` entries. It is not an optimization: it closes the
  in-place-write channel between tools (mutual blindness).
- The structural check is an explicit recursive validator — NOT a
  `json.dumps` try/except (dumps coerces non-string keys and accepts
  NaN/Infinity; both must fail). Reject: non-mapping payloads, non-string
  keys, empty mappings anywhere, non-finite floats
  (`math.isfinite`), any non-JSON scalar type. Evaluate on the **merged**
  buffer. The empty-mapping rule applies to mappings **inside** the merged
  buffer; the empty merged buffer itself is not an error — it commits
  nothing silently (guard `if merged:` before the structural check, or let
  the validator accept the empty top level).
- The per-payload `collections.abc.Mapping` guard runs BEFORE
  `dict.update` — `dict.update` would silently accept an iterable of
  key-value pairs (`[("a", 1)]` → `{"a": 1}`) and coerce it, violating the
  contract enumeration; the guard's failure converts into the structural
  hard-failure format (never a raw `TypeError`, never a coercion).
- Imports: `from ...hooks import (HookRegistry, build_hook_arguments,
  declared_actions, wrap_context)` (three dots up — no import cycle);
  `from .amendments import CellAmendment`; `from .facts import CellFacts`;
  `from .overlay import ToolContribution, merge_cell_contributions`.
- The zone never logs and never prints — the caller owns all output.
- Follow `goga/config/hooks/events.py` as the structural mirror
  (`_ensure_registry` shape, delivery loop, docstring density) with the
  schema-domain differences: the facts view instead of the config snapshot,
  the cell path in the failure formats, the buffer-merge commit instead of
  the merge-config call.

**Usages relevant to this task:**
- `convention`: Google docstrings; relative imports; tests mirror as
  `tests/schema/hooks/test_events.py`; the platform boundary fixtures
  (`pin_package_environment`, `install_tool_package` from the zone
  conftest) pin the two outside-world points — the platform code runs for
  real, no mocks inside business logic.
- `per-tool-delivery` (from Imports, `goga/hooks`): the staged delivery
  loop skeleton applies as written — `HookRegistry()` + `build_once()`,
  group `subscriptions_for(domain, action)` by `sub.tool` into an
  insertion-ordered dict, `wrap_context` / `build_hook_arguments`
  projection, tool-granular commit, one registry per run, deliver to every
  subscriber — with the hard semantics of this action (stop at the first
  failure with the pinned `ValueError`) replacing the soft skip of the
  usage's example.
- `registering-hooks` (from Imports, `goga/hooks`): the registration
  contract behind the checkpoint — a hook receives values only for the
  parameters it declares by the offered names `context` / `self`
  (`build_hook_arguments` is the single projection — never deliver an
  undeclared value); a broken package import is the only fatal platform
  case (raised at `build_once`, message names the package).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/schema/hooks/test_events.py`: `SchemaHooks` importable from the facade; constructor takes no arguments; `amend_cell` signature is `(cell: CellFacts) -> dict` (expected to fail)
- [ ] **Code**: create `goga/schema/hooks/events.py` — module docstring in the config-zone style; `_read_only_view(value)` helper; `SchemaHooks` with `__init__`, `_ensure_registry`, and `amend_cell` implementing the algorithm above; the three pinned failure formats exactly as specified
- [ ] **Code**: implement the commit inside `amend_cell`: per-payload `collections.abc.Mapping` guard before `dict.update`, then the explicit recursive `_check_json_map` structural validator on the merged buffer, then `if merged: contributions.append(ToolContribution(tool=tool, facts=merged))`
- [ ] **Code**: complete the facade — `goga/schema/hooks/__init__.py` re-exports all six contract names from the four modules with the final zone docstring; `sorted(__all__) == ["CellAmendment", "CellFacts", "DependencyFacts", "SchemaHooks", "ToolContribution", "merge_cell_contributions"]`
- [ ] **Code**: create `tests/schema/hooks/test_facade.py` mirroring `tests/config/hooks/test_facade.py` — the facade suite of the assembled zone (the `_IMPLEMENTING` name-to-entity map, the exact alphabetical `__all__`, cheap construction)
- [ ] **Interface verification**: `pytest tests/schema/hooks/test_events.py -x` — the contract tests above pass (the logic tests are not written yet at this step)
- [ ] **Logic tests (positive)**: `test_amend_cell_commits_buffered_facts` — pin `{"goga_tool_docs": ["docs-dist"]}` + install `goga_tool_docs` subscribing `("schema", "amend_cell", "cover", cover)` with `cover(context)` calling `context.contribute({"coverage": 3})`; one `CellFacts(path="goga/config", ..., types=["ProjectConfig"], usages=[], dependencies=[], children=[])`; `SchemaHooks().amend_cell(cell=facts) == {"docs": {"coverage": 3}}` (the identity `goga_tool_docs` → `docs` is derived by the platform)
- [ ] **Logic tests (positive)**: `test_amend_cell_empty_contribute_commits_nothing` — a hook contributing `{}` leaves the buffer `[{}]` but the merged buffer empty → result `{}`; the inversion on the same fixture: a hook writing `{"a": 1}` yields `{"docs": {"a": 1}}` (a tool's key exists iff the **merged** buffer is non-empty)
- [ ] **Logic tests (positive)**: `test_contribute_merges_key_wise_later_wins` — one tool whose hook contributes `{"a": 1, "b": 2}` then `{"a": 3}` → `amend_cell` returns `{"docs": {"a": 3, "b": 2}}` (the delivery's merged buffer, later write replaces)
- [ ] **Logic tests (positive)**: `test_amend_cell_builds_registry_once_per_run` — pinned environment with a subscribed scratch tool; two consecutive `amend_cell` calls over two different `CellFacts` → `boundary.call_count == 1` and both calls return the tool's composed area
- [ ] **Logic tests (negative)**: `test_amend_cell_crashed_hook_is_hard_failure_naming_cell_path` — installed `goga_tool_boom` subscribing `("schema", "amend_cell", "explode", explode)` with `explode(context)` raising `RuntimeError("kaput")`; facts.path `"goga/config"` → `pytest.raises(ValueError, match="hook explode of tool boom failed on schema.amend_cell at goga/config: kaput")`
- [ ] **Logic tests (negative)**: `test_amend_cell_structurally_malformed_contribution_is_hard_failure` — installed `goga_tool_bad` contributing a malformed payload, parametrized over `{"cfg": {}}`, `{"cfg": {"deep": {}}}`, `{1: "x"}`, `{"v": {1, 2}}`, `{"v": float("nan")}`, `[("a", 1)]` (the non-mapping payload); facts.path `"goga/schema"` → `pytest.raises(ValueError, match=r"tool bad failed on schema\.amend_cell at goga/schema: structurally malformed contribution")`; the merged-buffer semantics case: hook1 contributes `{"a": {}}`, hook2 contributes `{"a": {"b": 1}}` → NO raise (the check runs on the merged buffer) and the area is `{"bad": {"a": {"b": 1}}}`
- [ ] **Logic tests (edge)**: `test_amend_cell_without_subscriptions_returns_empty_mapping` — `pin_package_environment({})` → `amend_cell` returns `{}`
- [ ] **Logic tests (edge)**: `test_construction_enumerates_nothing` — `pin_package_environment({"goga_tool_demo": ["demo"]})`; after `SchemaHooks()` alone, `boundary.call_count == 0`
- [ ] **Logic tests (edge)**: `test_frozen_facts_block_attribute_assignment_and_isolate_tools` (delivery half) — two subscribed tools over one caller `CellFacts`: tool_alpha's hook mutates its view in place (`context.cell.types.append("junk")`), tool_beta reads `context.cell.types` afterwards → beta reads the authored list with no `"junk"`, and the caller's `facts.types` is unchanged after the whole delivery
- [ ] **Logic tests (facade)**: `test_zone_facade_reexports_six_contract_names` in `tests/schema/hooks/test_facade.py` — `from goga.schema.hooks import (CellAmendment, CellFacts, DependencyFacts, SchemaHooks, ToolContribution, merge_cell_contributions)`; the alphabetical `__all__` equals exactly the six names; each name resolves to the implementing class or function of its declaring module (`facts` / `amendments` / `overlay` / `events`, the config-precedent `_IMPLEMENTING` map); `SchemaHooks()` constructs without enumerating packages (boundary unread)
- [ ] **Debugging**: `pytest tests/schema/hooks -x` — all pass
- [ ] **Contract re-verification**: all six names importable from `goga.schema.hooks`; `amend_cell` shape and the three pinned failure formats match the contract; no printing, no logging in the zone
- [ ] **Lint**: `ruff check goga/schema/hooks tests/schema/hooks` — fix formatting, apply decomposition if necessary

### Task 7: The `schema` walk integration — checkpoint delivery and the `tools` node key (TDD coding)

Extend `schema()` in `goga/schema/schema.py`: after all filters, deliver the
cell-amendment checkpoint for every surviving cell and place the returned
tools area on the node. The walk algorithm (verbatim from the design):

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

Facts-construction detail (the authored projection — values mirror
`_build_cell_tree` / `_build_dependencies` exactly): `types` is
`sorted(entity names + routine names)`; `usages` is
`_find_usages_files(doc.path)`; `dependencies` is one `DependencyFacts` per
sorted **normalized** source path with its sorted types and sorted usages
(the same normalization `_build_dependencies` applies — reuse its grouping
logic or factor a shared private helper); `children` is
`[os.path.normpath(c.path) for c in doc.children]` — the **authored**
children even when the node's children were pruned by filters, and the
facts never come from the filtered dict node. The delivery runs after all
filters over the authored doc tree with the surviving-path set; a cell is
delivered iff its node appears in the output tree. The routine propagates
`ValueError` (AST, checkpoint) and `ImportError` (facade) untouched — it
never prints and never returns partial JSON.

**Usages relevant to this task:**
- `convention`: walk tests build CODEMANIFEST trees under `tmp_path`
  (the `tests/commands/test_schema.py` fixture style: `_write_codemanifest`
  + `ROOT_WITH_CHILD` / `CHILD` manifests) with `_cwd` from
  `tests.conftest` — no mocks inside business logic; the boundary fixtures
  come from the new `tests/schema/conftest.py`.
- `documents` (from Usages): `ast_obj = AST("."); ast_obj.load()`;
  `ast_obj.tree` for the walk; `ast_obj.errors` for the count guard.
- `beautiful_json` (from Usages): `json.dumps(result, indent=4,
  sort_keys=True, ensure_ascii=False)` — the `tools` key sorts
  alphabetically among the node keys deterministically.
- `checkpoints` (from Imports, `goga/schema/hooks`): the consumer practice
  for the walk — one `SchemaHooks` per run, build the authored facts of
  each cell, `tools = hooks.amend_cell(cell=facts)`, place the key iff
  non-empty, deliver only surviving cells.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/schema/test_schema.py` (extended): `from goga.schema import schema` still imports; `schema([], None, [])` on a `tmp_path` project with a contributing scratch tool returns parseable JSON whose nodes carry `"tools": {"docs": {"score": 3}}` (expected to fail — no delivery exists yet)
- [ ] **Code**: create `tests/schema/conftest.py` mirroring `tests/config/hooks/conftest.py` — re-export `install_tool_package` / `pin_package_environment` from `tests.hooks.conftest` (the walk tests pin the environment boundary)
- [ ] **Code**: modify `schema()` in `goga/schema/schema.py` per the walk algorithm — early `return "[]"` on the empty result (before `SchemaHooks()` is ever constructed), the surviving path set + `path -> node` map from the final dict tree, `hooks = SchemaHooks()` once per run, the pre-order walk of `ast_obj.tree` building `CellFacts` / `DependencyFacts` and calling `hooks.amend_cell(cell=facts)`, and `node["tools"] = tools` iff non-empty; imports `from .hooks import CellFacts, DependencyFacts, SchemaHooks`
- [ ] **Code**: update the `schema()` docstring — extended purpose, the node format with the conditional `tools` field, and `Raises: ValueError` (AST errors; checkpoint hard failures naming the tool, the action, and the failing cell path) and `ImportError` (register-facade import failure naming the package)
- [ ] **Interface verification**: the contract test above passes; `pytest tests/schema/test_schema.py -x` stays green (the six base fields and all filter behavior unchanged)
- [ ] **Logic tests**: `test_schema_walk_places_tools_and_keeps_base_fields` (routine half) — `tmp_path` root CODEMANIFEST + `subpkg` child; a scratch tool package (pinned environment + installed facade) contributing `{"score": 3}` on every cell; `schema([], None, [])` → `data[0]["tools"] == {"docs": {"score": 3}}`, `data[0]["children"][0]["tools"] == {"docs": {"score": 3}}`, and `set(data[0].keys()) == {"cell", "children", "dependencies", "description", "tools", "types", "usages"}`
- [ ] **Logic tests**: `test_schema_output_byte_identical_without_subscriptions` — `tmp_path` project (root + child + `.usages` files); run A with `pin_package_environment({})`, run B with a subscribed-but-silent tool (a hook that only reads `context.cell.path`); `"tools"` not in either output; `output_a == output_b` (byte-identical); `boundary.call_count == 1` per run
- [ ] **Logic tests**: `test_schema_empty_tree_skips_enumeration_entirely` — empty `tmp_path` (no CODEMANIFEST) with a non-vacuous environment: `pin_package_environment({"goga_tool_docs": ["docs-dist"]})` + installed subscribed tool whose hook contributes `{"x": 1}` (the provocateur — were the delivery to start, it would commit and break the asserts); `schema([], None, []) == "[]"` and `boundary.call_count == 0`
- [ ] **Logic tests**: `test_filters_prune_delivery_exactly_as_output` — `tmp_path` project root `.` → `pkg` → (`sub_a`, `sub_b`) with `pkg/sub_a` importing from `lib`; a recording scratch tool appending every delivered `context.cell.path` to a list; parametrized over `cells=["pkg"]`, `max_depth=1`, `depends_on=["lib"]`, and combined `cells=["pkg"] + depends_on=["lib"]` → `delivered_paths == {node["cell"] for node in pre_order(parsed_output)}` per filter
- [ ] **Logic tests**: `test_delivered_facts_carry_authored_children_under_max_depth` — root → `pkg` → `leaf` project, `max_depth=1` (leaf pruned from output); a recording tool capturing `context.cell.children` on `pkg` → `recorded_children == ["pkg/leaf"]` while the parsed output's `pkg` node has `children == []` (authored projection)
- [ ] **Logic tests**: `test_schema_hard_failure_propagates_without_partial_output` — `tmp_path` project with two cells; a scratch tool whose hook raises on the second delivered cell (counting invocations); `pytest.raises(ValueError, match="at <second cell path>")` out of `schema([], None, [])` — the raised error carries the failing cell path, not the first one
- [ ] **Debugging**: `pytest tests/schema -x` — all pass
- [ ] **Contract re-verification**: `from goga.schema import schema` importable; the six base fields of every node byte-identical to a no-tool run; the `tools` key exists iff non-empty; errors propagate (no printing, no partial JSON)
- [ ] **Lint**: `ruff check goga/schema tests/schema` — fix formatting, apply decomposition if necessary

### Task 8: CLI `schema` — convert every `schema_logic` error into a clean failure (TDD coding)

Broaden the failure conversion in `goga/commands/schema/schema.py`. The
algorithm (verbatim from the design):

```
1. try: result = schema_logic(list(cells), max_depth, list(depends_on))
2. except Exception as e: click.echo(str(e), err=True); ctx.exit(1)
3. click.echo(result)
```

`except Exception` (broadened from `except ValueError`) converts the AST
count `ValueError`, the checkpoint hard `ValueError`s, and the
register-facade `ImportError` into a clean stderr message + exit 1 — no raw
traceback, nothing on stdout (`click.echo(result)` runs only on success).
`KeyboardInterrupt` / `SystemExit` are `BaseException` — they pass through
untouched (never catch `BaseException`). Also update the command
docstring's structure block with the `tools` line (after `children`) so
`--help` documents the extended node.

**Usages relevant to this task:**
- `click` (from Usages, `.goga/usages/cooks/click.md`): unchanged
  decorators; `click.echo(result)` for stdout; `click.echo(str(e),
  err=True)` + `ctx.exit(1)` for failures; CliRunner drives the command in
  tests (`tests/commands/test_schema.py` `_run_schema` helper).
- `checkpoints` (from Imports, `goga/schema/hooks`): the hard-failure
  handling of the generation checkpoint — every failure of `schema_logic`
  surfaces as a clean command failure; a facade `ImportError` converts the
  same way, never a raw traceback.
- `convention`: CLI tests via the existing `_run_schema` + `_cwd` style;
  the boundary fixtures are already re-exported by
  `tests/commands/conftest.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/commands/test_schema.py` (extended): a scratch project + failing tool (pinned environment) driven through `_run_schema()` exits 1 with the checkpoint message on stderr and no `"Traceback"` (expected to fail — the current `except ValueError` lets an `ImportError` crash with a traceback and this test pins the broadened shape)
- [ ] **Code**: restructure the command body to the algorithm above — `except Exception as e:` with `click.echo(str(e), err=True)` + `ctx.exit(1)`, `click.echo(result)` after the try/except; the call shape `schema_logic(list(cells), max_depth, list(depends_on))` unchanged
- [ ] **Code**: add the `tools` line to the docstring's JSON structure block (after `children`): the tool contributions of the cell-amendment checkpoint — present iff at least one tool wrote at least one fact
- [ ] **Interface verification**: the contract test above passes; `pytest tests/commands/test_schema.py -x` stays green (including `test_schema_with_ast_errors_exits_1` — the `ValueError` path is still caught by `except Exception`)
- [ ] **Logic tests**: `test_cli_converts_checkpoint_hard_failure_cleanly` — the scratch project and failing tool (pinned environment); `_run_schema()` → `result.exit_code == 1`, `"failed on schema.amend_cell" in result.output`, `"Traceback" not in result.output` (stdout carries nothing on failure)
- [ ] **Logic tests**: `test_cli_converts_register_facade_import_failure` — a real broken package on disk (the `tests/hooks/registry/test_state.py` precedent): a `tmp_path` directory `goga_tool_broken/` whose `__init__.py` contains `import goga_missing_dependency`; `monkeypatch.syspath_prepend(tmp_path)`; `pin_package_environment({"goga_tool_broken": ["goga-tool-broken"]})`; a one-cell `tmp_path` project; `_run_schema()` → `result.exit_code == 1`, `"goga_tool_broken" in result.output`, `"Traceback" not in result.output`
- [ ] **Logic tests**: the CLI half of `test_schema_walk_places_tools_and_keeps_base_fields` — the contributing scratch tool over the root+child project; `_run_schema()` → exit 0, `data[0]["tools"] == {"docs": {"score": 3}}`, child node carries its tools
- [ ] **Debugging**: `pytest tests/commands/test_schema.py -x` — all pass
- [ ] **Contract re-verification**: stdout carries the machine-consumed JSON only; exit 0 only on a complete generation; `--help` documents the `tools` field
- [ ] **Lint**: `ruff check goga/commands/schema tests/commands/test_schema.py` — fix formatting if necessary

### Task 9: Integration tests — both entry paths agree; final verification battery (integration tests)

The cross-cell end-to-end scenarios: routine and CLI produce the same
extended tree, the six base fields stay identical with and without tool
contributions, and the real repository output stays byte-identical (no
`tools` key — this repo installs no `goga_tool_*` packages). This task adds
no production code; it pins the topic's end-to-end guarantees and runs the
full validation battery.

**Usages relevant to this task:**
- `checkpoints` (from Imports, `goga/schema/hooks`): the output shape —
  `tools -> {tool identity -> {fact -> value}}`; base fields and extensions
  stay structurally separated; empty objects never appear at any of the
  three levels; with no subscriptions the output is byte-identical to the
  map without the extension.
- `convention`: integration tests for interaction between packages; test
  naming and the `tmp_path` + `_cwd` style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create the integration test in `tests/commands/test_schema.py` (it already imports the CliRunner and the app; add `from goga.schema import schema as schema_logic`): `test_schema_walk_places_tools_and_keeps_base_fields` (full form) — the root+child project with the contributing scratch tool: the direct `schema([], None, [])` call and `_run_schema()` produce identical parsed trees (both nodes carry `tools == {"docs": {"score": 3}}`); a second run of the same project with `pin_package_environment({})` yields nodes whose six base fields are identical to the tooled run and carry no `tools` key
- [ ] Test edge case: determinism — repeated runs over the same project with the same installed tools produce identical output (fixed walk order, tool enumeration order, `sort_keys`)
- [ ] Verify the local usage files are consistent with the landed implementation: `goga/schema/hooks/.usages/checkpoints.md`, `goga/schema/.usages/registering-hooks.md`, `goga/schema/.usages/schema-usage.md`, `goga/commands/schema/.usages/schema.md` exist and their names, loop shape, failure naming, and output shape match the contract (documentation-only check; fix nothing in CODEMANIFEST)
- [ ] Run the targeted battery: `pytest tests/hooks/catalog tests/schema/hooks tests/schema tests/commands/test_schema.py -x`
- [ ] Run the full suite: `pytest tests/ -x`
- [ ] Run validation: `goga lint` — 81 cells, 0 errors
- [ ] Run facade check: `python -c "from goga.schema.hooks import CellAmendment, CellFacts, DependencyFacts, SchemaHooks, ToolContribution, merge_cell_contributions"`
- [ ] Run the repo-level byte-identity check: from the repository root, `goga schema` output contains no `"tools"` key anywhere (no `goga_tool_*` packages installed here — combined with `test_schema_output_byte_identical_without_subscriptions` this proves byte-identity for real consumers of `goga schema`)

---

## Validation Commands

- `pytest tests/hooks/catalog tests/schema/hooks tests/schema tests/commands/test_schema.py -x`: the topic's targeted battery (catalog record, zone suites, walk, CLI)
- `pytest tests/ -x`: run all tests
- `ruff check goga/ tests/`: lint (line-length 120)
- `goga lint`: manifest linter — 81 cells, 0 errors
- `python -c "from goga.schema.hooks import CellAmendment, CellFacts, DependencyFacts, SchemaHooks, ToolContribution, merge_cell_contributions"`: facade check — all six zone names importable
- `goga schema` from the repository root: no `"tools"` key in the output (byte-identity for real consumers)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`catalog.py`, `facts.py`, `amendments.py`, `overlay.py`, `events.py`, `schema.py` ×2)
- [ ] Every contract entity is accessible from the facade (`goga.schema.hooks` exposes the six names; `goga.schema` / `goga.cli` unchanged)
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior (authored projection, mutual blindness, tool-granular commit, key-wise merge, pinned failure formats, byte-identity, hard semantics)
- [ ] Contract dependencies are met (`goga.hooks` platform primitives; zone-internal imports)
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them (Task 9)
- [ ] No package boundary was expanded (no new cells beyond the contract's `goga/schema/hooks`)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `documents`, `beautiful_json`, `click`, `per-tool-delivery`, `registering-hooks`, `checkpoints`)
