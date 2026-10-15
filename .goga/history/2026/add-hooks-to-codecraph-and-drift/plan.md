# Plan: `add-hooks-to-codecraph-and-drift`

<!-- Topic: `add-hooks-to-codecraph-and-drift` — the hooks zones of the codegraph and
     drift domains: the node-amendment checkpoint and the validation gate of the codegraph
     assembly, and the run moments plus the report/entry amendments of the drift run.
     Source: `.goga/history/2026/add-hooks-to-codecraph-and-drift/design.md` (design-review
     completed — 6 remarks fixed, 0 skipped; see the review execution summary). This plan
     compiles the design into ralphex-executable tasks. -->

## Purpose

Deliver the hooks extension of the codegraph and drift domains end-to-end. After
implementation the project provides:

- `goga/hooks/catalog` — six new action records (28 → 34): `codegraph/amend_node`
  (hard), `codegraph/validate_graph` (hard), `drift/run_started` (soft),
  `drift/run_completed` (soft), `drift/amend_report` (hard), `drift/amend_entry` (hard);
- `goga/codegraph/facts` — `CodegraphNode` gains the `tools` field (empty default;
  the amendment checkpoint alone places non-empty overlays);
- `goga/codegraph/hooks` — **new zone cell**: `NodeFacts`, `Violation`, `GateVerdict`,
  `NodeAmendment.contribute`, `GraphValidation.veto`, `ToolContribution`,
  `merge_node_contributions`, and the checkpoint surface `CodegraphHooks`
  (`amend_node`, `validate_graph`);
- `goga/drift/hooks` — **new zone cell**: `DriftFilters`, `EntryFacts`, `ReportEntry`,
  `RunOutcome`, `RunCompletion`, `ReportAmendment.adjust`, `EntryAmendment.contribute`,
  `ToolContribution`, `merge_entry_contributions`, and the checkpoint surface
  `DriftHooks` (`emit_run_started`, `amend_report`, `amend_entry`, `emit_run_completed`);
- `goga/codegraph` — the checkpoint-aware routine: amend every surviving node, rebuild
  the tree with the committed overlays, gate the final tree (one merged veto error);
- `goga/drift` — the run wrapped by the moments: start moment → producers →
  comparison/scoping → report amendment → entry amendment → completion moment, with
  the failure paths emitting the crashed completion and re-raising; `DriftEntry`
  gains the `tools` field;
- `goga/commands/codegraph` — the `_project_node` projection replaces `asdict`
  serialization (the conditional `tools` key — an empty object never appears);
  extended help;
- `goga/commands/drift` — `_project_entry` gains the conditional `tools` key;
  post-amendment grading pinned in the help.

The most important gaps between contract and code: both zone cells have a
CODEMANIFEST and `.usages/` on disk but **zero implementation files**; the catalog
lacks the six records; `CodegraphNode`/`DriftEntry` lack the `tools` field; the
`codegraph` routine delivers nothing and gates nothing; the `drift` routine has no
moments and no amendments; the codegraph CLI serializes via `asdict` — the moment
`tools` exists it would print `"tools": {}` on every node, tearing the byte-identity
guarantee.

Overall strategy: implement strictly in the design's dependency order (catalog →
facts → codegraph zone → drift zone → codegraph domain → drift domain → commands),
mirroring `goga/schema/hooks` (the recorded precedent) for the codegraph zone and
mixing that precedent with the pipeline moments precedent for the drift zone. One
TDD task per module `location`, ralphex protocol inside every coding task, every
task gated by the Mandatory Rules below.

## Mandatory Rules

<!-- Extracted verbatim from the project convention `.goga/usages/conventions.md`
     (the `convention` practice wired into every cell of this feature — for working
     with the codebase, organizing the REPL development cycle, debugging and testing,
     and the test infrastructure), the language rules (`goga-cell-python`), the ruff
     configuration (`pyproject.toml`), and the repo gates (`.github/workflows/lint.yml`,
     `.githooks/`). These rules are MANDATORY for every task in this plan. Where a
     task restates a rule, the restatement is a reminder, not a replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`; all code
  executes within a virtualenv — create it if missing.
- **Imports**: relative imports for ALL intra-package references inside `goga/`
  (`from .facts import NodeFacts`, `from ...hooks import HookRegistry`); absolute
  imports only for stdlib and third-party. Exception — tests: cross-directory
  references inside `tests/` use absolute imports rooted at the `tests` package
  (`from tests.hooks.conftest import install_tool_package`).
- **Data models**: stdlib `dataclasses` only; model classes use `kw_only=True` and,
  for records, `frozen=True`; empty defaults for all fields (`""`, `0`, `[]`/`{}`
  via `default_factory`); `None` only for fields that represent the explicit absence
  of a value (`EntryFacts.types=None` and `RunCompletion.report=None` are the
  recorded absences of this feature). `RunOutcome` is a plain `Enum` with string
  member values (precedent `SyncOutcome` in `goga/usages/hooks/facts.py`) — never
  accept a raw string where `RunOutcome` is declared.
- **Docstrings**: Google style, MANDATORY for every public function, method, and
  class. First line starts with a capital letter and ends with a period. Include
  `Args` when the function accepts parameters, `Returns` when it returns a value,
  `Raises` when it raises beyond built-in types.
- **CLI command docstrings** (click callbacks): user-facing help rendered verbatim by
  `--help` — omit `Args`, `Returns`, `Raises` (Click auto-generates the options
  block; exit codes are Click's; internal exception types stay hidden); keep the
  concise summary line (Click lists it); use `\b` blocks to preserve paragraph
  formatting in help. Google-style docstrings still apply unchanged to every OTHER
  public function in a command module (helpers, projectors, logic functions —
  `_project_node` / `_project_entry` carry full Google docstrings).
- **Code formatting**: inside function and method bodies, separate logical blocks by
  ONE blank line (initialization / conditions and loops / data preparation /
  processing / return).
- **Type hints**: mandatory everywhere (drives facade signature extraction). Allowed
  shapes: `str`, `int`, `float`, `bool`, `list[T]`, `dict[str, T]`, `T | None`
  (with `from __future__ import annotations` — the family pattern). Forbidden:
  `*args`, `**kwargs`, bare `dict`, bare `list`. Mutable contract defaults
  (`cells=[]`, `depends_on=[]`) carry `# noqa: B006` with the family comment (the
  CODEMANIFEST contract default; never mutated) — mirror the existing
  `codegraph()` / `drift()` signatures.
- **Naming**: PascalCase classes, snake_case functions/methods/properties/modules.
- **Facade**: each cell's `__init__.py` exposes the contract API through `__all__`;
  only identifiers in `__all__` constitute the facade. Zone facades are created by
  the first task that lands an entity of the zone and extended by each subsequent
  task (final state documented per task) — no skeleton modules importing
  non-existent names.
- **Logging**: NO new logging in this feature — soft-moment hook-failure warnings
  come from the platform `emit_hook_event` (`logger.warning`); the zones never
  print and never log (`Constraints: Do not print — the caller owns all output`).
- **Dependencies**: no new third-party dependencies — stdlib (`dataclasses`,
  `collections.abc`, `copy`, `enum`, `math`) plus the in-repo platform facade
  `goga.hooks`; any hypothetical new library MUST go into `pyproject.toml` with a
  minimum version.
- **Credential hygiene** (convention "Log Content Restrictions" applied to facts):
  no fact carries a credential-bearing value; `RunCompletion.reason` reuses the
  propagated error's message (`str(reason)`) — producers' clean-error convention is
  the guarantee; never let a traceback string cross the boundary.

### Test Writing Rules (strictly per `conventions.md` — Testing)

- **Tools**: pytest (runner), ruff (lint + format of test code), pytest-cov
  (coverage). Test libraries live in `pyproject.toml`
  `[project.optional-dependencies]` under `test`; all test runs execute in the
  virtualenv.
- **Structure mirrors source directly**:
  `goga/codegraph/hooks/events.py` → `tests/codegraph/hooks/test_events.py`;
  `goga/drift/hooks/facts.py` → `tests/drift/hooks/test_facts.py`;
  `goga/commands/drift/drift.py` → `tests/commands/drift/test_drift.py`. Every test
  directory MUST contain an `__init__.py`.
- **Fixtures**: local fixtures in `tests/<package>/conftest.py`, shared fixtures in
  `tests/conftest.py`. Available shared infrastructure: the boundary fixtures
  `pin_package_environment(mapping)` (pins `packages_distributions`, returns the
  boundary mock for `call_count` assertions) and `install_tool_package(module_name,
  register_hooks)` (installs a fake `goga_tool_*` facade into `sys.modules`) — both
  defined once in `tests/conftest.py` and re-exported by `tests/hooks/conftest.py`;
  the new zone conftests re-export them (the `tests/schema/hooks/conftest.py` shim
  pattern). Planted-project helpers (`_write_config`, `_write_package`,
  `_write_codemanifest`, `_plant_four_kinds`, `_plant_healthy_plus`,
  `_plant_nested_depth`) live in `tests/drift/conftest.py`; the autouse
  `_empty_package_environment` pattern of `tests/drift/conftest.py` pins every
  suite whose routine builds a non-empty tree.
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>` (e.g.
  `test_amend_node_empty_contribute_commits_nothing`); grouping
  `class Test<Component>:` with docstrings; self-documenting test names; keep
  comments minimal.
- **Test types**: Unit — every public function/method/class, main scenario and
  typical data. Edge cases — empty inputs (`None`, `""`, `[]`, `{}`), boundary
  values, invalid types, expected exceptions via `pytest.raises`. Integration —
  only for interaction between modules/packages (the planted-project runs and the
  CliRunner runs are the integration scenarios of this feature and live in their
  mirrored suites per the design's Source File Registry).
- **Boundary tests**: for thresholds, ranges, state transitions use
  `@pytest.mark.parametrize` with a table of values including each boundary (the
  malformed-contribution and malformed-adjustment tables of the zone suites).
- **Mocks**: pure logic — NO mocks (the platform code runs for real under the two
  boundary fixtures — no mocking inside the platform); file I/O — the `tmp_path`
  fixture exclusively; external dependencies — `mock.patch` at the import point.
  Mock only at external boundaries; business-logic tests stay mock-free.
- **CLI testing**: invoke the command through the registered `app` via
  `click.testing` `CliRunner` (direct Python call — no subprocess), as the existing
  command tests do (`_run_codegraph` / `_run_drift` helpers).
- **Zone suites never leave the package environment unpinned** (design,
  Additional Instructions): every test that reaches a checkpoint pins the
  environment — empty for inertness tests, explicit mappings for delivery tests.
- **Expected values are grounded, never recalled**: every fixture expectation in
  this plan was validated by the design's dry-runs against the live producers; if
  an assertion disagrees with a live run during implementation, the live run wins
  and the disagreement is reported — never silently "aligned".

### Linter and Formatter Enforcement (all development stages and local commits)

The following gates are MANDATORY at the end of EVERY task and BEFORE EVERY local
commit, across all development stages. A failing gate is an actionable defect,
never acceptable noise. Local git hooks do NOT enforce formatting (only the
commit-msg/pre-push Co-Authored-By policy does — `core.hooksPath = .githooks`) —
the author runs the formatter deliberately:

1. `ruff check goga/ tests/` — zero violations (CI gate,
   `.github/workflows/lint.yml`).
2. `ruff format --check goga/ tests/` — zero reformattings; run
   `ruff format goga/ tests/` when it reports diffs. Formatting coverage extends to
   the Python examples embedded in usage documents.
3. `goga lint` — cell-level lint, **0 errors over 91 cells**.
4. Focused tests green, then `pytest tests/ -x` green (the full battery).
5. Facade import checks green (the per-zone `python -c "from goga.codegraph.hooks
   import ..."` / `python -c "from goga.drift.hooks import ..."` batteries).
6. **Commit policy**: commit only with all gates green; commit messages MUST NOT
   contain `Co-Authored-By:` trailers (`.githooks/commit-msg` and `pre-push`
   reject them).
7. `CODEMANIFEST` files are READ-ONLY for the implementer — the contract changes
   are already applied in the working tree; if code does not match the contract,
   fix the code, never the contract.

### REPL Cycle Rules (continuous interactive evaluation, hot reloading, migration to source)

The `convention` practice is wired into every cell of this feature for "Organizing
the REPL development cycle". Every coding task in this plan follows the same loop:

1. **Virtualenv first**: all code executes inside the virtualenv — create it if
   missing. The current `.venv` is BROKEN (its `bin/python` resolves to nothing and
   `bin/ruff` raises `Exec format error` — binaries left by a foreign platform);
   Task 1 recreates it (`python -m venv .venv --clear` +
   `pip install -e ".[test]"`) and every subsequent probe, test run, and lint run
   executes inside it.
2. **Probe before writing**: verify each non-trivial behavior interactively
   against real inputs BEFORE the verified snippet is written into a source file.
   The recorded probes of this feature: the live `goga codegraph` output over a
   scratch planted project confirming the `"dependencies": {}` rendering for
   dependency-less cells (Task 1 — the C1 evidence: only `tools` is conditional,
   `dependencies` renders empty); the live schema-zone delivery shapes
   (`goga/schema/hooks/events.py` helper behavior under the boundary fixtures —
   Task 7); the platform `emit_hook_event` soft-warning path observed live through
   `caplog` (Task 11); `_plant_four_kinds` planted in a scratch `tmp_path` with the
   live `schema()`/`codegraph()` producers confirming the asserted views entry for
   entry (Tasks 12–13); the click `ctx.exit`/`CliRunner` stdout-semantics scratch
   invocation (Tasks 14–15). Expected values in tests are grounded in live probe
   runs, never in recollection.
3. **Hot feedback after every edit**: immediately re-run the focused test file and
   the facade import check in the same virtualenv; iterate in small steps. A
   long-lived REPL session re-imports edited modules (`importlib.reload` or a fresh
   `python -c`) — never trust stale module state as evidence.
4. **Migrate verified code to source files**: REPL-verified snippets are migrated
   into the target `location` file with type hints, Google docstrings, relative
   imports, and convention formatting; REPL scratch never ships and is never
   referenced by source.
5. **Close the loop per task**: probe → implement (migrate) → focused tests → full
   battery → lint/format gates → commit (gates green).

## Context

### Interaction and Data Flow (verbatim from the design)

```
                          goga/hooks (platform facade)
   ┌──────────────────────────┼─────────────────────────────────────────┐
   │ HookRegistry.build_once() │ subscriptions_for(domain, action)      │
   │ self_context(tool)        │ wrap_context(view)                      │
   │ build_hook_arguments(...) │ emit_hook_event(registry, d, a, ctx)   │
   │ declared_actions()  (goga/hooks/catalog)                            │
   └──────────────────────────┬─────────────────────────────────────────┘
                              │ imported by both zones
      ┌───────────────────────┴───────────────────────┐
      │                                               │
goga/codegraph/hooks                          goga/drift/hooks
  CodegraphHooks                                DriftHooks
   ├─ amend_node(NodeFacts) -> tools             ├─ emit_run_started(DriftFilters)
   │    └─ NodeAmendment.contribute              ├─ amend_report([EntryFacts]) -> [EntryFacts]
   │       merge_node_contributions              │    └─ ReportAmendment.adjust
   └─ validate_graph(tree) -> GateVerdict        ├─ amend_entry(EntryFacts) -> tools
        └─ GraphValidation.veto                  │    └─ EntryAmendment.contribute
                                                │       merge_entry_contributions
      ▲ reads CodegraphNode                     └─ emit_run_completed(RunCompletion)
      │ (from goga/codegraph/facts)
      │
goga/codegraph (domain routine)                goga/drift (domain routine)
  codegraph(cells, max_depth, depends_on)        drift(cells, max_depth, depends_on)
   ├─ render_graph (filtered + complete)          ├─ schema() ×2  (declared view; fires schema checkpoints)
   ├─ per surviving node: amend_node              ├─ codegraph() ×2 (code view; fires codegraph checkpoints)
   ├─ rebuild tree with overlays                  ├─ compare_views + scope_entries
   └─ validate_graph → merged veto error          ├─ amend_report → settled list
      ▼                                           ├─ per entry: amend_entry → DriftEntry(tools)
      ▼                                           └─ emit_run_completed(finished)
goga/commands/codegraph                          ▼
  CLI: JSON tree, conditional tools key        goga/commands/drift
exit 0 / 1                                       CLI: JSON report, conditional tools key
                                                 exit 0 / 1 / 2
```

**Flow A — `goga codegraph` (and every codegraph producer call inside a drift run)**

1. CLI (click) parses `CELLS`, `--max-depth`, `--depends-on` → calls
   `codegraph(cells, max_depth, depends_on)`.
2. `load_project_config()` → `ProjectConfig` (`FileNotFoundError` = uninitialized
   project); language whitelist check (`ValueError`); `LintConfig.ignore` →
   `discover_sources` → `collect_facts` → `derive_units` → `resolve_links`.
3. `render_graph(units, links, cells, max_depth, depends_on)` → filtered tree
   (`list[CodegraphNode]`, `tools == {}` everywhere). When filters are active, a
   second `render_graph(units, links, [], None, [])` produces the complete tree.
4. Empty filtered tree → return `[]` before any checkpoint.
5. Pre-order walk of the filtered tree: per node build `NodeFacts` (own
   `cell`/`types`/`dependencies` + `children` cell paths from the matching complete
   node) → `CodegraphHooks.amend_node(node=facts)` → per-node tools mapping (empty
   iff nothing contributed).
6. Recursive rebuild of the filtered tree with the committed overlays
   (`dataclasses.replace`).
7. `CodegraphHooks.validate_graph(final_tree)` → `GateVerdict`; not approved → one
   merged `ValueError`; approved → return the final tree.
8. CLI projects nodes to JSON (conditional `tools` key) → `click.echo` → exit 0;
   any error → stderr + exit 1.

**Flow B — `goga drift`**

1. CLI parses filters → `drift(cells, max_depth, depends_on)`.
2. `DriftHooks.emit_run_started(DriftFilters(...))` — soft moment (hook failures
   warn).
3. Producer stage inside the failure wrap: `schema([], None, [])`,
   `codegraph([], None, [])`, `schema(cells, ...)`, `codegraph(cells, ...)` — the
   codegraph calls fire Flow A's checkpoints; the schema calls fire the schema
   checkpoints (existing behavior).
4. `compare_views(complete…)` → entries; `scope_entries(entries, filtered…)` →
   scoped report (all `DriftEntry.tools == {}`).
5. Projection to `EntryFacts` → `DriftHooks.amend_report(facts)` → settled list
   (last adjusting tool wins; hard failure on crash/malformed adjustment).
6. Per settled entry: `DriftHooks.amend_entry(facts)` → tools → final `DriftEntry`
   records.
7. `DriftHooks.emit_run_completed(RunCompletion(final projected to ReportEntry,
   RunOutcome.finished, ""))` → return the final report.
8. Any failure in steps 3–6: `emit_run_completed(RunCompletion(last computed
   stage, RunOutcome.crashed, credential-free reason))` then re-raise. CLI: error →
   stderr + exit 2; report printed → exit 1 iff the final list is non-empty, else
   exit 0.

**Entity dependency order (implementation order, leaves → root)**:

1. `goga/hooks/catalog` (data only; records must exist before zones resolve addresses)
2. `goga/codegraph/facts` (`CodegraphNode.tools` before the gate view delivers the record)
3. `goga/codegraph/hooks` (imports `goga/hooks` + `goga/codegraph/facts`)
4. `goga/drift/hooks` (imports `goga/hooks`)
5. `goga/codegraph` (imports its zone + facts + analysis + config)
6. `goga/drift` (imports its zone + `goga/schema` + `goga/codegraph` + facts)
7. `goga/commands/codegraph`
8. `goga/commands/drift`

No import cycles: zones never import their domains; `goga/codegraph/facts` imports
nothing from the zones; the platform imports neither domains nor zones.

### Contract Surface

**Entity: `declared_actions()` / `_DECLARED_ACTIONS`** (cell `goga/hooks/catalog` —
MODIFIED, data only)
- Type: routine (existing, on the `goga.hooks.catalog` facade) + its private data
  constant
- Declared `location`: `goga/hooks/catalog/catalog.py`
- Change: append six records to `_DECLARED_ACTIONS` (data, not discovery):
  `Action(domain="codegraph", name="amend_node", error_class="hard")`,
  `Action(domain="codegraph", name="validate_graph", error_class="hard")`,
  `Action(domain="drift", name="run_started", error_class="soft")`,
  `Action(domain="drift", name="run_completed", error_class="soft")`,
  `Action(domain="drift", name="amend_report", error_class="hard")`,
  `Action(domain="drift", name="amend_entry", error_class="hard")` — physically
  at the end of the list, after the `usages` block (domain-addition order
  continues: new domains append at the end). `declared_actions()` already
  sorts by `(domain, name)` per call; the sorted positions: `codegraph` between
  `build` and `config`, `drift` between `contract` and `onboarding`. No published
  record rewritten (catalog additivity law).

**Entity: `CodegraphNode`** (cell `goga/codegraph/facts` — MODIFIED)
- Type: class — frozen `kw_only` dataclass (existing)
- Declared `location`: `goga/codegraph/facts/facts.py` (already on the facade)
- Change: add the field `tools: dict[str, dict[str, object]] =
  field(default_factory=dict)` after `children`; document in the docstring
  Attributes; leave `__post_init__` as is (the committed overlays are owned deep
  copies from the delivery — no defensive copying, mirroring `SchemaNode`).
- Requirements: the node fields are exactly cell, types, dependencies, children,
  plus tools; `tools` is empty iff no tool wrote at least one fact on the node; the
  analysis never populates it — the amendment checkpoint alone places non-empty
  overlays.

**Entities: `NodeFacts`, `Violation`, `GateVerdict`** (cell
`goga/codegraph/hooks` — NEW, one `location`)
- Types: classes — frozen `kw_only` dataclasses, properties only; `GateVerdict`
  carries the `approved` property (`not self.violations`)
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.codegraph.hooks`
- `NodeFacts(cell: str, types: list[str], dependencies: dict[str, list[str]],
  children: list[str])` — the code-derived facts of one node, the per-node read
  view; `__post_init__` copies `types`, `dependencies` (each value list),
  `children`. Pure facts — the constructing operation passes resolved values;
  code-derived projection only — identical in every run regardless of filters; the
  filters prune delivery, never the facts (the child list is the complete
  code-derived subtree and may name cells pruned from the current run's output).
- `Violation(tool: str, hook: str, reason: str)` — one collected veto of the
  validation walk; `reason` is a hook-authored message or the crash reason — never
  a raw traceback.
- `GateVerdict(violations: list[Violation])` — the collected verdict; data only —
  acting on it (the merged error, the exit code) belongs to the operation.
- Imported dependencies: none (zone-internal).

**Entity: `NodeAmendment`** (cell `goga/codegraph/hooks` — NEW)
- Type: class — `kw_only` dataclass (NOT frozen: it owns the mutable buffer)
- Declared `location`: `amendments.py`
- Facade obligation: importable from `goga.codegraph.hooks`
- Property: `node -> NodeFacts` — read-only and identical for every tool
- Method: `contribute(facts: dict[str, object])` — buffer one fact-mapping
  contribution of this tool; the buffer merges key-wise (a later write replaces an
  earlier one on key conflict); an empty mapping contributes nothing
- Constraints: do not cancel, redirect, or defer the operation
- Internal state: `_pending: list = field(init=False, default_factory=list,
  repr=False)` — private-buffer access from the delivery is the schema-zone
  precedent
- Imported dependencies: `NodeFacts` from `.facts`

**Entity: `GraphValidation`** (cell `goga/codegraph/hooks` — NEW)
- Type: class — `kw_only` dataclass (NOT frozen: it owns the veto buffer)
- Declared `location`: `contexts.py`
- Facade obligation: importable from `goga.codegraph.hooks`
- Property: `tree -> list[CodegraphNode]` — the final assembled tree in tree order,
  the tools overlay included; read-only for the receiving hook
- Method: `veto(reason: str)` — buffer this tool's veto; the replacement is whole
  (a later call replaces the earlier reason); the view records no hook identity
  (the walk attributes the veto by observing the buffer change around each call);
  an empty or whitespace-only reason is stored as given
- Imported dependencies: `CodegraphNode` from `..facts` (`goga/codegraph/facts`)

**Entities: `ToolContribution`, `merge_node_contributions`** (cell
`goga/codegraph/hooks` — NEW, one `location`)
- Types: frozen `kw_only` record (`tool: str`, `facts: dict[str, object]` —
  constructed by the checkpoint delivery alone) and a pure module-level function
- Declared `location`: `overlay.py`
- Facade obligation: importable from `goga.codegraph.hooks`
- `merge_node_contributions(contributions: list[ToolContribution]) -> tools:
  dict[str, dict[str, object]]` — Algorithm: (1) take the contributions in
  enumeration order; (2) skip a contribution whose mapping is empty — a tool's key
  exists iff that tool wrote at least one fact; (3) place each remaining mapping
  under its tool identity key; (4) return the composed mapping — empty when every
  contribution was empty or none committed. Deterministic; pure — the inputs stay
  unmutated; structural validation is not here. Constraints: do not read or write
  the filesystem; do not mutate `contributions` or their maps.

**Entity: `CodegraphHooks`** (cell `goga/codegraph/hooks` — NEW)
- Type: class (plain class, no constructor parameters)
- Declared `location`: `events.py`
- Facade obligation: importable from `goga.codegraph.hooks`
- Methods: `amend_node(node: NodeFacts) -> tools: dict[str, dict[str, object]]`;
  `validate_graph(tree: list[CodegraphNode]) -> verdict: GateVerdict`
- Requirements: cheap construction — no enumeration and no imports at
  construction; one `HookRegistry` per run carries every checkpoint of a command
  (`amend_node` + `validate_graph` share one enumeration); every context is built
  from the values the caller passes — no repository, git, or file reads at the
  checkpoint
- Full delivery algorithm: see Task 7 (verbatim from the design)
- Imported dependencies: `HookRegistry`, `wrap_context`, `build_hook_arguments`,
  `declared_actions` from the platform facade `goga.hooks`
  (`from ...hooks import …` — three dots up, no import cycle); zone-internal
  `.facts`, `.amendments`, `.contexts`, `.overlay`

**Entities: `DriftFilters`, `EntryFacts`, `ReportEntry`, `RunOutcome`,
`RunCompletion`** (cell `goga/drift/hooks` — NEW, one `location`)
- Types: classes — frozen `kw_only` dataclasses (properties only) plus one `Enum`
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.drift.hooks`
- `DriftFilters(cells: list[str], max_depth: int | None, depends_on: list[str])` —
  the start-moment facts, the filters the run was asked to apply; `__post_init__`
  copies `cells`, `depends_on`; pure facts, identical on every run with the same
  arguments.
- `EntryFacts(kind: str, cell: str, types: list[str] | None)` — the delivered read
  view of one report entry; `__post_init__` copies `types`; tools-free — the
  record never carries contributions; `kind` is one of the comparison's entry
  kinds; the shape is exactly kind, cell, types.
- `ReportEntry(kind: str, cell: str, types: list[str] | None, tools:
  dict[str, dict[str, object]])` — the completion-moment report entry projection;
  `tools` defaults `{}`; on failure-carried stages the tools mapping is empty — no
  facts areas were computed.
- `RunOutcome` — fixed value set of a drift run's terminal outcome, implemented as
  `enum.Enum` with string member values: `finished = "finished"`,
  `crashed = "crashed"` (precedent `SyncOutcome` in `goga/usages/hooks/facts.py`).
- `RunCompletion(report: list[ReportEntry] | None, outcome: RunOutcome, reason:
  str)` — the completion-moment facts; `report` is the last computed report stage
  (`None` when the run failed before the report was computed); `reason` is a
  credential-free crash reason on crashed runs, empty on finished runs; no fact
  carries a credential-bearing value.
- Imported dependencies: `RunOutcome` (zone-internal, referenced by
  `RunCompletion`).

**Entities: `ReportAmendment`, `EntryAmendment`** (cell `goga/drift/hooks` — NEW,
one `location`)
- Types: classes — `kw_only` dataclasses (NOT frozen: they own the buffers)
- Declared `location`: `amendments.py`
- Facade obligation: importable from `goga.drift.hooks`
- `ReportAmendment(report: list[EntryFacts])` — the read-and-adjust view of one
  tool for the report; amending tools are mutually blind — every tool reads the
  same finished scoped report, never another tool's adjustment. Method
  `adjust(entries: list[dict[str, object]])` — buffer the whole-list replacement;
  a later call replaces the earlier adjustment; the view records no hook identity;
  the adjusted list may be empty (clearing the report entirely is a valid
  adjustment). Constraints: do not cancel, redirect, or defer the operation; do
  not emit any provenance. Internal state: `_adjustment: list | None =
  field(init=False, default=None, repr=False)`.
- `EntryAmendment(entry: EntryFacts)` — the read-and-contribute view of one tool
  for one entry. Method `contribute(facts: dict[str, object])` — same buffering
  contract as `NodeAmendment.contribute`. Internal state: `_pending` (the same
  shape as the codegraph zone).
- Imported dependencies: `EntryFacts` from `.facts`

**Entities: `ToolContribution`, `merge_entry_contributions`** (cell
`goga/drift/hooks` — NEW, one `location`)
- Types: frozen `kw_only` record (`tool: str`, `facts: dict[str, object]`) and a
  pure module-level function — the same composition as the codegraph zone, over
  entries
- Declared `location`: `overlay.py`
- Facade obligation: importable from `goga.drift.hooks`
- `merge_entry_contributions(contributions: list[ToolContribution]) -> tools:
  dict[str, dict[str, object]]` — the same four-step algorithm as
  `merge_node_contributions` (enumeration order; skip empty; place under the tool
  identity key; empty when nothing committed); deterministic; pure; structural
  validation is not here.

**Entity: `DriftHooks`** (cell `goga/drift/hooks` — NEW)
- Type: class (plain class, no constructor parameters)
- Declared `location`: `events.py`
- Facade obligation: importable from `goga.drift.hooks`
- Methods: `emit_run_started(filters: DriftFilters)`;
  `amend_report(report: list[EntryFacts]) -> report: list[EntryFacts]`;
  `amend_entry(entry: EntryFacts) -> tools: dict[str, dict[str, object]]`;
  `emit_run_completed(completion: RunCompletion)`
- Requirements: cheap construction; one `HookRegistry` per run — moments and
  amendments share it; every context is built from the values the caller passes —
  no configuration reads, no repository, git, or file reads at the checkpoint; no
  fact carries a credential-bearing value
- The moments are soft (a failing hook is a warning; the delivery continues); the
  two amendments are hard; `amend_report` has list-control semantics (mutual
  blindness over the finished scoped report; last adjusting tool wins;
  adjust-nothing leaves the list unchanged; the closed kind/cell/types shape is
  enforced — never sanitized, never adopted; no adjustment provenance recorded or
  returned anywhere)
- Full delivery algorithm: see Task 11 (verbatim from the design)
- Imported dependencies: `HookRegistry`, `wrap_context`, `build_hook_arguments`,
  `declared_actions`, `emit_hook_event` from the platform facade `goga.hooks`;
  zone-internal `.facts`, `.amendments`, `.overlay`

**Routine: `codegraph(cells, max_depth, depends_on)`** (cell `goga/codegraph` —
MODIFIED)
- Declared `location`: `codegraph.py` (already on the `goga.codegraph` facade —
  unchanged facade)
- Change: the checkpoint-aware 10-step assembly (amend surviving nodes, rebuild
  with overlays, gate the final tree). Full walk algorithm: see Task 12 (verbatim
  from the design)
- Requirements (key): the checkpoints fire wherever the routine runs — in this
  command and inside every producer call of a drift run; filters prune delivery
  exactly as they prune output; the delivered view carries code-derived facts only
  — the facts of a delivered node are identical in every run of the same code; the
  gate view carries the final result, the tools overlay included — the recorded
  exception; delivery is node-major and deterministic; a hard amendment failure
  and a vetoed gate propagate as errors naming the tool, the action, and the
  failing node cell path (the merged veto error lists every violation); no
  partial tree is returned; with no subscriptions — or no tool packages installed
  — every tools area is empty and the output is byte-identical to the run without
  the extension
- Docstring `Raises` gains: checkpoint hard failures (naming tool/action/cell),
  the merged veto error, and the register-facade `ImportError`
- Imported dependencies (new): `CodegraphHooks`, `NodeFacts`, `GateVerdict` +
  `checkpoints` usage from `goga/codegraph/hooks`

**Routine: `drift(cells, max_depth, depends_on)`** (cell `goga/drift` — MODIFIED)
- Declared `location`: `drift.py` (already on the `goga.drift` facade)
- Change: the moments-and-amendments algorithm with failure paths. Full algorithm:
  see Task 13 (verbatim from the design)
- Requirements (key): run ordering is fixed (start moment → view production,
  comparison, scoping → report amendment → entry facts amendment → completion
  moment); the completion moment fires on every terminal state of a started run —
  finished, producer-failed, and amendment-failed alike — carrying the last
  computed report stage (the final report with facts areas on finished runs; the
  scoped pre-amendment report when a later stage failed; `None` when the run
  failed before the report was computed); the returned report is the settled
  post-amendment list — a tool-added or tool-removed entry changes what the
  caller sees and how the caller grades the run; no adjustment provenance appears
  anywhere; facts areas never carry failure semantics; every error of a view
  producer propagates unchanged (the moment never masks the failure — re-raise)
- Docstring `Raises` gains: drift amendment hard failures, in-run codegraph veto /
  hard checkpoint failures, register-facade `ImportError`; `Returns` documents the
  post-amendment list
- Imported dependencies (new): `DriftHooks`, `DriftFilters`, `EntryFacts`,
  `ReportEntry`, `RunOutcome`, `RunCompletion` + `checkpoints` usage from
  `goga/drift/hooks`

**Entity: `DriftEntry`** (cell `goga/drift` — MODIFIED)
- Declared `location`: `compare.py` (already on the facade)
- Change: add the field `tools: dict[str, dict[str, object]] =
  field(default_factory=dict)` after `types`; document in the docstring; the
  comparison never populates `tools` — it stays empty until the entry-facts
  amendment places a non-empty overlay; leave `__post_init__` as is

**Routine: `codegraph` CLI command** (cell `goga/commands/codegraph` — MODIFIED)
- Declared `location`: `codegraph.py` (already registered on the `goga.cli` app)
- Change: replace the `asdict` serialization with the module-level private
  projection `_project_node` (verbatim from the design):

```python
def _project_node(node: CodegraphNode) -> dict:
    projected = {
        "cell": node.cell,
        "types": list(node.types),
        "dependencies": {path: list(types) for path, types in node.dependencies.items()},
        "children": [_project_node(child) for child in node.children],
    }
    if node.tools:
        projected["tools"] = node.tools
    return projected
```

  serialized via `json.dumps([_project_node(n) for n in result], indent=4,
  sort_keys=True, ensure_ascii=False)` (the `beautiful_json` practice). The
  current `asdict`-based serialization would print `"tools": {}` on every node the
  moment the field exists — it MUST be replaced in the same task that adds the
  field to the CLI path; the `asdict` import leaves the module. The click surface,
  the `except Exception` → stderr + `ctx.exit(1)` envelope, and the
  `list(cells)`/`list(depends_on)` call shape are unchanged.
- Help (schema-command mirror): add the `tools` line to the JSON structure block
  ("tool contributions of the node-amendment checkpoint, present iff at least one
  tool wrote at least one fact") and the failure note (a failing or vetoing hook
  stops the run as a clean error before any output)

**Routine: `drift` CLI command** (cell `goga/commands/drift` — MODIFIED)
- Declared `location`: `drift.py` (already registered on the app)
- Change: `_project_entry` gains `if entry.tools: projected["tools"] =
  entry.tools`; grading stays `ctx.exit(1) if report else ctx.exit(0)` — the
  returned list is already post-amendment. Help: add the `tools` line ("present
  iff at least one tool contributed; never affects the exit code") and the
  amendment failure note under exit 2. The `except Exception` → stderr +
  `ctx.exit(2)` envelope is unchanged (its cause list is now realized by the drift
  amendments and the in-run codegraph checkpoints).

### Re-exports

- `goga/codegraph/hooks/__init__.py` (Python facade — created by Task 4): `__all__`
  must expose exactly `CodegraphHooks`, `GateVerdict`, `GraphValidation`,
  `NodeAmendment`, `NodeFacts`, `ToolContribution`, `Violation`,
  `merge_node_contributions` — every name importable from
  `goga.codegraph.hooks`. Built incrementally (each entity task adds its module);
  completed in Task 7.
- `goga/drift/hooks/__init__.py` (Python facade — created by Task 8): `__all__`
  must expose exactly `DriftFilters`, `DriftHooks`, `EntryAmendment`, `EntryFacts`,
  `ReportAmendment`, `ReportEntry`, `RunCompletion`, `RunOutcome`,
  `ToolContribution`, `merge_entry_contributions` — every name importable from
  `goga.drift.hooks`. Built incrementally; completed in Task 11.
- `goga/codegraph/__init__.py`, `goga/drift/__init__.py`,
  `goga/codegraph/facts/__init__.py`, `goga/commands/codegraph/__init__.py`,
  `goga/commands/drift/__init__.py`, `goga/hooks/catalog/__init__.py` — unchanged
  (no new facade names on existing cells; the zone packages are imported by their
  cells, not re-exported by them).

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — mandatory Python conventions:
  relative imports, `kw_only` dataclasses with empty defaults, Google docstrings,
  logging policy, blank-line block formatting, test structure mirroring, test
  naming, `tmp_path` for file I/O, mocks only at external boundaries, CLI testing
  via direct Python call, validation commands. Extracted in full into the
  Mandatory Rules section; applies to every task.
- `click` (`.goga/usages/cooks/click.md`, command cells) — CLI command
  construction; unchanged decorators; `click.echo(result)` for stdout;
  `click.echo(str(e), err=True)` + `ctx.exit(1|2)` for failures; CliRunner drives
  the command in tests.
- `beautiful_json` (`.goga/usages/cooks/beautiful_json.md`, command cells) —
  output serialization: `json.dumps(..., indent=4, sort_keys=True,
  ensure_ascii=False)`; the `tools` key sorts alphabetically among the node keys
  deterministically.

### Imported Usages

- `per-tool-delivery` from `goga/hooks` —
  `goga/hooks/.usages/per-tool-delivery.md`: the staged delivery loop skeleton
  (registry + `build_once`, `subscriptions_for` grouping per tool in enumeration
  order, `wrap_context` / `build_hook_arguments` projection, tool-granular commit,
  one registry per run, deliver to every subscriber). Applies to Tasks 7 and 11
  as written, with this feature's semantics: hard amendments stop at the first
  failure (amendments); the `validate_graph` walk runs to completion collecting
  violations (the recorded refinement); `amend_report` commits whole-list
  replacements.
- `registering-hooks` from `goga/hooks` —
  `goga/hooks/.usages/registering-hooks.md`: the registration contract behind
  every checkpoint — facade `register_hooks`, `subscribe(domain, action, name,
  hook)`, offered parameter names `context` / `self` (`build_hook_arguments` is
  the single projection), attribute assignment blocked on delivered views, a
  broken package import is the only fatal platform case. Applies to Tasks 5, 7,
  9, 11 (zone views and surfaces) and 14, 15 (the command cells import the
  re-authored domain docs).
- `declaring-actions` from `goga/hooks` —
  `goga/hooks/.usages/declaring-actions.md`: how a domain opens an action —
  catalog record, context contract, `emit_hook_event` at the checkpoint. Applies
  to Task 11 (both moments: `emit_hook_event(self._ensure_registry(), "drift",
  "<action>", context_for=lambda _tool: context)`).
- `checkpoints` from `goga/codegraph/hooks` —
  `goga/codegraph/hooks/.usages/checkpoints.md`: the zone's consumer recipes —
  build `NodeFacts`, call `CodegraphHooks.amend_node(node=facts)`, place the
  returned area iff non-empty, `_apply_overlays`, gate before return, the output
  shape (`tools -> {tool -> {fact -> value}}`). The code snippets are the
  reference implementation of Task 12's routine steps.
- `checkpoints` from `goga/drift/hooks` —
  `goga/drift/hooks/.usages/checkpoints.md`: the moments/failure-path wrap, the
  report amendment over `EntryFacts`, the per-entry amendment, the output shape.
  The reference implementation of Task 13's routine steps.
- `codegraph-usage` from `goga/codegraph` —
  `goga/codegraph/.usages/codegraph-usage.md`: the producer contract behind the
  command (node shapes with the conditional `tools` row, hook-extension
  guarantees, checkpoint failure bullets). Applies to Tasks 13 (producer) and 14
  (CLI).
- `drift-usage` from `goga/drift` — `goga/drift/.usages/drift-usage.md`: the
  report and failure contract behind the command (post-amendment paragraph,
  conditional `tools` row, extended exit-code causes). Applies to Task 15.
- `records` from `goga/codegraph/facts`, `stages` from `goga/codegraph/analysis`,
  `project-configuration` from `goga/config`, `schema-usage` from `goga/schema` —
  unchanged links consumed by the domain routines (Tasks 12–13); no content
  change, restated here for task self-containedness.

### Local Usages

All `.usages/` files of this topic are already on disk (created/updated by the
architecture stage; verified current by the design review — the four consumer-doc
fixes were applied there). **No creation tasks are needed**; Task 16 carries the
final existence/consistency verification.

- `goga/codegraph/hooks/.usages/checkpoints.md` — zone consumer docs. Status: on
  disk, current (new).
- `goga/drift/hooks/.usages/checkpoints.md` — zone consumer docs (moments,
  amendments, failure-path wrap). Status: on disk, current (new).
- `goga/codegraph/.usages/registering-hooks.md` — domain-level tool-author docs
  (events table, views, merge rules, failure treatment, drift symmetry
  scenario). Status: on disk, current (new).
- `goga/drift/.usages/registering-hooks.md` — domain-level tool-author docs
  (four-action table, moment/report/entry views, failure treatment, integration
  scenarios). Status: on disk, current (new).
- `goga/codegraph/.usages/codegraph-usage.md` — tools row, hook-extension and
  checkpoint-failure bullets. Status: on disk, current (updated).
- `goga/drift/.usages/drift-usage.md` — tools row, post-amendment paragraph,
  hook-extension and checkpoint-failure bullets. Status: on disk, current
  (updated).
- `goga/codegraph/facts/.usages/records.md` — `tools` in the flow diagram and the
  overlay constraint bullet. Status: on disk, current (fixed in the design).
- `goga/commands/codegraph/.usages/codegraph.md` — conditional `tools` key,
  extended exit-1 causes, byte-identical statement. Status: on disk, current
  (fixed in the design).
- `goga/commands/drift/.usages/drift.md` — post-amendment exit codes, extended
  exit-2 causes, `tools` row, no-provenance statement. Status: on disk, current
  (fixed in the design).
- `goga/hooks/catalog` has no `.usages/` directory — skip (catalog additivity
  law: the six record bullets are the whole change).

No cell points `Usages` at its own `.usages/` files (consumer documentation, not
contractual requirements) — verified for every affected cell.

### External Dependencies

- None new. stdlib only (`dataclasses`, `collections.abc`, `copy`, `enum`,
  `math`); the platform facade `goga.hooks` is in-repo; `click`, `pytest`, `ruff`
  are already project dependencies (ruff line-length 120, `target-version
  py310`).

## Facts

- The eight CODEMANIFESTs and every `.usages/` file of the topic are already on
  disk in the working tree of branch `add-hooks-to-codecraph-and-drift`; `goga
  lint` reports 91 cells, 0 errors; `goga schema` shows both zones present with
  the `RunOutcome` import edge registered and no cycles (verified live at plan
  time). The manifests are read-only for the implementation agent.
- The zone directories `goga/codegraph/hooks/` and `goga/drift/hooks/` contain
  ONLY `CODEMANIFEST` + `.usages/` — zero implementation files, no `__init__.py`.
- The catalog currently carries 28 records (`grep -c "Action("
  goga/hooks/catalog/catalog.py` == 28); `tests/hooks/catalog/test_catalog.py`
  pins `== 28` at five sites (`test_schema_amend_cell_record_present`,
  `test_declared_actions_carries_the_nine_topics_records`,
  `test_declared_actions_carries_the_four_usages_records`,
  `test_catalog_carries_the_three_pipeline_records`,
  `test_config_amend_config_record_present`), the full catalog is frozen in
  the `expected` list of `test_catalog_carries_the_five_build_records`
  (exact equality), and the schema (`+ 2`) and config (`+ 1`) tests carry
  `len(pre_existing)` arithmetic that breaks until the six triples are
  inserted into their lists.
- The platform derives the tool identity from the package name:
  `goga_tool_docs` → `docs`, `goga_tool_gate` → `gate`,
  `goga_tool_baseline` → `baseline` (canonical form without the `goga_tool_`
  prefix); a tool never names itself.
- The platform facade `goga.hooks` exposes exactly: `HookRegistry`, `ToolHooks`,
  `build_hook_arguments`, `declared_actions`, `emit_hook_event`,
  `enumerate_tool_packages`, `wrap_context`.
- The schema zone (`goga/schema/hooks/`: `__init__.py`, `facts.py`,
  `amendments.py`, `contexts.py`, `overlay.py`, `events.py`) is the structural
  mirror for the codegraph zone — module layout, `_ensure_registry` shape,
  per-tool delivery loop, frozen `kw_only` records, private-buffer access from
  the delivery, docstring density. Its `events.py` carries the exact helper
  precedents: `_read_only_view`, `_copy_json`, `_copy_tree`, `_nested_scope`,
  `_check_json_map`, `_commit_tool_buffer`. The drift zone mixes that precedent
  (amendments) with the pipeline moments precedent (`emit_hook_event` + one
  shared frozen context per moment — `goga/pipeline/hooks/events.py`).
- The structural check must be an explicit recursive validator — NOT a
  `json.dumps` try/except (dumps coerces non-string keys and accepts
  NaN/Infinity; both must fail). Non-mapping payloads are rejected at the commit
  merge with a per-payload `collections.abc.Mapping` guard BEFORE `dict.update`
  runs — `dict.update` would silently accept an iterable of key-value pairs and
  coerce it into a valid mapping.
- Pinned failure formats (verbatim from the design):
  `hook {sub.name} of tool {tool} failed on codegraph.amend_node at {node.cell}: {reason}`;
  `tool {tool} failed on codegraph.amend_node at {cell_path}: structurally malformed contribution ({detail})`;
  `codegraph validation failed:\n- tool {v.tool} / hook {v.hook}: {v.reason}` (one line per violation);
  `hook {sub.name} of tool {tool} failed on drift.amend_report: {reason}`;
  `hook {attributed} of tool {tool} failed on drift.amend_report: malformed adjustment ({detail})`;
  `hook {name} of tool {tool} failed on drift.amend_entry at {kind} {cell}: {reason}`;
  `tool {tool} failed on drift.amend_entry at {kind} {cell}: structurally malformed contribution ({detail})`.
  Every failure is `ValueError(... , from reason)` — `str(reason)`, never a raw
  traceback.
- Boundary fixtures live once in `tests/conftest.py`
  (`pin_package_environment`, `install_tool_package`) and are re-exported by
  `tests/hooks/conftest.py`; the zone shim precedent is
  `tests/schema/hooks/conftest.py` (a docstring + one re-export line). Shared
  helpers: `cwd` context manager and `is_kw_only_dataclass` in `tests/conftest.py`.
- Planted-project helpers exist in `tests/drift/conftest.py`:
  `_write_config`, `_write_package`, `_write_codemanifest`,
  `_plant_four_kinds`, `_plant_healthy_plus`, `_plant_stale_importer`,
  `_plant_root_manifest`, `_plant_nested_depth`, `_plant_locationless` — plus the
  autouse `_empty_package_environment` pinning every drift-suite test.
- The broken-package test precedent is
  `test_build_once_broken_import_is_fatal_through_the_real_import` in
  `tests/hooks/registry/test_state.py`: a `tmp_path` package dir whose
  `__init__.py` imports a missing dependency + `syspath_prepend` + pinned
  environment — the platform raises
  `ImportError("package goga_tool_broken failed to import: ...")`.
- The golden CLI byte-identity net already exists:
  `TestCodegraphCliByteIdentity` in `tests/commands/codegraph/test_codegraph.py`
  pins the full run + `cells` filter + `--max-depth` + `--depends-on` + the empty
  project byte for byte (captured from the live CLI by the drift-command topic).
  The `_project_node` projection must keep it green untouched.
- `tests/integration/test_codegraph_cli_integration.py` invokes the codegraph CLI
  over planted projects WITHOUT pinning the package environment (safe today —
  codegraph fires no checkpoints); once the routine delivers, that suite needs
  the autouse `_empty_package_environment` fixture (the
  `test_schema_walk_gate_integration.py` pattern — adapted in Task 12).
- Frozen-dataclass semantics: `FrozenInstanceError` subclasses `AttributeError`,
  so the registering-hooks promise "attribute assignment is blocked" is
  satisfied by frozen `kw_only` dataclasses.
- The current `.venv` is broken (foreign-platform binaries: `bin/python` resolves
  to nothing, `bin/ruff` raises `Exec format error`); the system interpreter is
  `/opt/goga/bin/python` (3.12.15). Task 1 recreates the virtualenv.
- Live-verified rendering fact (design remark C1): `goga codegraph` renders
  `"dependencies": {}` for dependency-less cells — an empty dict DOES appear for
  `dependencies`; only the `tools` key is conditional (written iff non-empty).
  The CODEMANIFEST phrase "never an empty object" is scoped to the tools area.

## Gap Analysis

- Missing contract entities: the entire zone implementations —
  `goga/codegraph/hooks/{__init__,facts,amendments,contexts,overlay,events}.py`
  and `goga/drift/hooks/{__init__,facts,amendments,overlay,events}.py` do not
  exist (only CODEMANIFEST + `.usages/` on disk).
- Missing facade exposure: neither `goga.codegraph.hooks` nor `goga.drift.hooks`
  is an importable package yet (`__init__.py` absent).
- Missing catalog records: `_DECLARED_ACTIONS` carries 28 records; the contract
  requires 34.
- Behavioral mismatches:
  - `CodegraphNode` and `DriftEntry` lack the `tools` field;
  - `codegraph()` delivers no checkpoint, gates nothing, and always returns the
    unfiltered-children render as-is (no overlays, no gate);
  - `drift()` has no moments, no amendments, no failure-path completion;
  - the codegraph CLI serializes via `asdict` — with `tools` present it would
    print `"tools": {}` on every node (byte-identity torn); must become
    `_project_node`;
  - the drift CLI `_project_entry` never writes `tools`; the help documents
    neither the conditional key nor the amendment failure semantics.
- Existing code that can be reused: all analysis stages, `render_graph`,
  `compare_views`, `scope_entries` (unchanged — the design forbids modifying
  them); the platform facade `goga.hooks`; the schema zone as the structural
  mirror; the pipeline moments precedent; the boundary fixtures and their
  conftest re-exports; the planted-project helpers of `tests/drift/conftest.py`;
  the golden CLI net.
- Test coverage gaps: no `tests/codegraph/hooks/` or `tests/drift/hooks/`
  suites; catalog count pins at 28 (five sites);
  `tests/codegraph/test_codegraph.py` and `tests/commands/*/test_*.py` have no
  delivery / gate / amendment tests; `tests/drift/test_drift.py` has no moment or
  amendment tests; `tests/integration/test_codegraph_cli_integration.py` lacks
  the environment pin.
- Missing visibility in workspace or git: none — the contract and usage files
  are already in the working tree of this topic branch (untracked/modified files
  per `git status`); commit them with the implementation per the commit policy.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before
> starting the next. Within each coding task, contract tests are written first
> (TDD workflow). Package order: `goga/hooks/catalog` → `goga/codegraph/facts` →
> `goga/codegraph/hooks` (facts → views → overlay → events) → `goga/drift/hooks`
> (facts → amendments → overlay → events) → `goga/codegraph` → `goga/drift` →
> `goga/commands/codegraph` → `goga/commands/drift` → integration. Only ONE task
> is executed per ralphex iteration.
>
> **Mandatory Rules apply to every task** (style, tests, lint/format gates, REPL
> cycle, commit policy). Each task's gates checkbox restates them; the rules
> section is authoritative.
>
> **Facade assembly note**: per-zone `__init__.py` facades are created by the
> first task that lands an entity of the zone and extended by each subsequent
> task (final state documented per task). This keeps every task independently
> green — no skeleton modules and no facade importing non-existent names.

### Task 1: Development environment and zone test scaffolding (infrastructure)

Prepare the execution environment and the test scaffolding of both zones BEFORE
any entity lands. Three outcomes: (a) a working virtualenv (the current `.venv`
is broken — foreign-platform binaries), (b) the baseline verified green (full
battery, goldens, `goga lint`), and (c) the two zone test packages
`tests/codegraph/hooks/` and `tests/drift/hooks/` with their conftest shims, so
Tasks 4–11 land module by module. No production code changes in this task.

**Usages relevant to this task:**
- `convention`: virtualenv execution rule ("create it if missing" — here:
  recreate the broken one); test structure rules (mirroring, `__init__.py` per
  directory, conftest placement); validation command table.
- REPL cycle rule 2 (probe before writing): the live-output probe below grounds
  the byte-identity expectations of Tasks 12–15 — the `"dependencies": {}`
  rendering is observed, never recalled.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Environment**: recreate the virtualenv — `python -m venv .venv --clear`
      (system interpreter: `/opt/goga/bin/python`, 3.12.15; the current `.venv`
      binaries are foreign-platform and unusable), then
      `.venv/bin/pip install -e ".[test]"`; verify `.venv/bin/python --version`,
      `.venv/bin/pytest --version`, `.venv/bin/ruff --version`, and
      `.venv/bin/python -m goga --help` all work.
- [x] **Baseline**: in the fresh virtualenv run `pytest tests/ -x` (full battery
      green — the pre-extension state), `pytest
      tests/commands/codegraph/test_codegraph.py -k ByteIdentity` (the golden net
      green), `ruff check goga/ tests/` + `ruff format --check goga/ tests/`
      (zero findings), and `goga lint` (91 cells, 0 errors — a sporadic
      external-URL network probe in unrelated `goga/ast/factory` may fail once;
      a re-run is the documented remedy).
- [x] **REPL probe — ground the rendering facts**: in the virtualenv REPL
      (`python -` heredoc or a scratch script under `tmp_path`), plant a minimal
      project (`.goga/config.yml` with `language: python` + one package) and
      capture the live `goga codegraph` stdout; confirm (a) `"dependencies": {}`
      DOES render for a dependency-less cell (the C1 evidence — only `tools` is
  conditional) and (b) no `"tools"` substring appears anywhere (the field does
      not exist yet). Record the observation in the task notes; Tasks 12–15
      assert against this behavior.
- [x] **Code**: create `tests/codegraph/hooks/__init__.py` (empty package
      marker) and `tests/codegraph/hooks/conftest.py` mirroring
      `tests/schema/hooks/conftest.py`: a docstring explaining the re-export,
      then `from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401`
- [x] **Code**: create `tests/drift/hooks/__init__.py` (empty package marker)
      and `tests/drift/hooks/conftest.py` with the same re-export shape
- [x] Verify test scaffolding: `pytest tests/codegraph/hooks tests/drift/hooks
      --collect-only -q` collects no tests and reports no collection errors —
      exit code 5 is the expected outcome at this point (any exit other than 5,
      or an `error` line, is a failure)
- [x] Lint: `ruff check tests/codegraph/hooks tests/drift/hooks` and
      `ruff format --check` over the same paths (run `ruff format` on diffs)
- [x] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 2: Add the six codegraph and drift records to the action catalog (TDD coding)

The catalog is the single source of known subscription addresses; both zones
resolve their addresses against it at every checkpoint, so the records land
first. This task touches exactly one data constant and its test file. The
CODEMANIFEST Requirements already carry the six record bullets — the manifest is
read-only.

**Usages relevant to this task:**
- `convention`: maintained data only — no mocks in catalog tests; test naming
  `test_<what>_<scenario>`; class grouping `Test<Component>`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests**: in `tests/hooks/catalog/test_catalog.py`, add
      `test_declared_actions_carries_the_codegraph_and_drift_records` (the
      design's scenario, transfer verbatim): input `declared_actions()`; build
      `{(a.domain, a.name): a.error_class for a in actions}`; assert
      `("codegraph", "amend_node") == "hard"`,
      `("codegraph", "validate_graph") == "hard"`,
      `("drift", "run_started") == "soft"`,
      `("drift", "run_completed") == "soft"`,
      `("drift", "amend_report") == "hard"`,
      `("drift", "amend_entry") == "hard"`, `len(actions) == 34`, and the
      `(domain, name)` pairs are unique (expected to fail — the records are
      absent)
- [x] **Code**: append the six records to `_DECLARED_ACTIONS` in
      `goga/hooks/catalog/catalog.py` at the end of the list, after the
      `usages` block (domain-addition order continues — new domains append at
      the end; the sorted position is irrelevant to behavior but keep the list
      tidy) — exact literals:
      `Action(domain="codegraph", name="amend_node", error_class="hard")`,
      `Action(domain="codegraph", name="validate_graph", error_class="hard")`,
      `Action(domain="drift", name="run_started", error_class="soft")`,
      `Action(domain="drift", name="run_completed", error_class="soft")`,
      `Action(domain="drift", name="amend_report", error_class="hard")`,
      `Action(domain="drift", name="amend_entry", error_class="hard")`; no other
      line changes
- [x] **Interface verification**: `pytest tests/hooks/catalog/test_catalog.py -k
      codegraph_and_drift_records -x` — the new record test passes
- [x] **Logic tests**: update the stale pins in
      `tests/hooks/catalog/test_catalog.py`: the five `== 28` assertions → `34`
      (in `test_schema_amend_cell_record_present`,
      `test_declared_actions_carries_the_nine_topics_records`,
      `test_declared_actions_carries_the_four_usages_records`,
      `test_catalog_carries_the_three_pipeline_records`,
      `test_config_amend_config_record_present`); insert the six triples into
      the frozen full-catalog `expected` list of
      `test_catalog_carries_the_five_build_records` in sorted position
      (`codegraph` rows between the `build` and `config` rows, `drift` rows
      between `contract` and `onboarding` — exact equality, so the insertion
      is mandatory) and into the `pre_existing` lists of
      `test_schema_amend_cell_record_present` (`len(pre_existing) + 2` then
      holds: 32 + 2 = 34) and `test_config_amend_config_record_present`
      (`+ 1` then holds: 33 + 1 = 34); the block tests without count pins
      (`test_declared_actions_carries_the_five_build_records`,
      `test_catalog_declares_both_new_actions`) and the generic
      well-formedness tests (`test_declared_actions_is_deterministic_and_complete`,
      `test_declared_actions_records_are_well_formed`) need no change
- [x] **Debugging**: `pytest tests/hooks/catalog -x` — all pass (fix
      implementation code, not test code, if the record test and the pins
      disagree)
- [x] **Contract re-verification**: `Action` / `declared_actions` still
      importable from `goga.hooks.catalog`; no published record rewritten; the
      pairs come back sorted and unique
- [x] Lint: `ruff check goga/hooks/catalog tests/hooks/catalog` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [x] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 3: `CodegraphNode.tools` — the committed-overlay field of the output record (TDD coding)

Add the `tools` field to the shared output record of the code analysis. The
field defaults empty; the amendment checkpoint alone places non-empty overlays
(Task 7 delivers them, Task 12 places them); every pre-checkpoint consumer
(`render_graph`, the analysis) never populates it. Mirrors `SchemaNode.tools`
exactly — including leaving `__post_init__` without defensive copying of the
field (the committed overlays are owned deep copies from the delivery).

**Usages relevant to this task:**
- `convention`: `kw_only` frozen dataclass rules; empty defaults via
  `default_factory`; Google docstrings (Attributes section for dataclass
  fields).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/codegraph/facts/test_facts.py` (extended):
      `dataclasses.fields(CodegraphNode)` gains exactly one field named `tools`
      with annotation `dict[str, dict[str, object]]` and a default equal to
      `{}`; the record stays frozen and `kw_only` (expected to fail — the field
      is absent)
- [ ] **Code**: in `goga/codegraph/facts/facts.py`, add
      `tools: dict[str, dict[str, object]] = field(default_factory=dict)` to
      `CodegraphNode` after `children`; add the Attributes docstring line
      ("tools: The committed tools overlay of the node; empty when no tool
      contributed."); leave `__post_init__` unchanged
- [ ] **Interface verification**: `pytest tests/codegraph/facts -x` — all pass
- [ ] **Logic tests**: the codegraph half of the design's
      `test_codegraph_node_and_drift_entry_carry_the_tools_default` —
      `CodegraphNode(cell="a").tools == {}`; the record is frozen
      (`dataclasses.FrozenInstanceError` on `node.tools = {}` assignment);
      construction with an explicit overlay keeps it verbatim
      (`CodegraphNode(cell="a", tools={"t": {"f": 1}}).tools ==
      {"t": {"f": 1}}`)
- [ ] **Debugging**: `pytest tests/codegraph -x` — all pass (the render and
      discovery suites prove the new default breaks no existing construction)
- [ ] **Contract re-verification**: `from goga.codegraph.facts import
      CodegraphNode` importable; the facade `__all__` unchanged; node fields are
      exactly cell, types, dependencies, children, tools
- [ ] Lint: `ruff check goga/codegraph/facts tests/codegraph/facts` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 4: Codegraph zone `facts.py` — `NodeFacts`, `Violation`, `GateVerdict` (TDD coding)

The immutable fact records of the codegraph zone: the per-node read view, the
collected veto, and the verdict. All three share `location: facts.py` → one
task. This task also creates the zone package and its facade seed. Mirror
`goga/schema/hooks/facts.py` shapes; frozen `kw_only` dataclasses,
`from __future__ import annotations`, Google docstrings.

**Usages relevant to this task:**
- `convention`: frozen `kw_only` dataclasses for the facts records; relative
  imports inside the zone; Google docstrings; tests mirror as
  `tests/codegraph/hooks/test_facts.py`; use `is_kw_only_dataclass` from
  `tests/conftest` for the kw_only assertion.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/codegraph/hooks/test_facts.py`: the
      three names importable from the facade `goga.codegraph.hooks`; all three
      are frozen `kw_only` dataclasses (`dataclasses.is_dataclass`,
      `__dataclass_params__.frozen`, `is_kw_only_dataclass`; positional
      construction raises `TypeError`); exact field sets — `NodeFacts` fields
      are exactly `cell, types, dependencies, children`; `Violation` fields are
      exactly `tool, hook, reason`; `GateVerdict` fields exactly `violations`
      (via `dataclasses.fields`); `GateVerdict.approved` is a property
      (expected to fail — the package has no implementation)
- [ ] **Code**: create `goga/codegraph/hooks/__init__.py` — a module docstring
      naming the zone ("Hooks zone of the codegraph domain — the node-amendment
      and validation-gate checkpoint surface.") with the note that the zone is
      built incrementally and each entity task adds its module, plus
      `__all__: list[str] = []`
- [ ] **Code**: create `goga/codegraph/hooks/facts.py` with a module docstring
      in the schema-zone style:
      `NodeFacts(cell: str, types: list[str], dependencies: dict[str,
      list[str]], children: list[str])` — `@dataclass(frozen=True, kw_only=True)`,
      `__post_init__` copies `types`, `dependencies` (each value list), and
      `children` into fresh containers;
      `Violation(tool: str, hook: str, reason: str)` and
      `GateVerdict(violations: list[Violation])` — frozen `kw_only`;
      `GateVerdict.approved` property returning `not self.violations`;
      docstrings carry the contract property descriptions and the pure-facts /
      code-derived-projection / filters-prune-delivery-never-the-facts
      requirements
- [ ] **Code**: update `goga/codegraph/hooks/__init__.py` —
      `from .facts import GateVerdict, NodeFacts, Violation` and extend `__all__`
      (keep it sorted)
- [ ] **Interface verification**: `pytest tests/codegraph/hooks/test_facts.py
      -x` — all contract tests pass
- [ ] **Logic tests**: fields hold the passed values verbatim (pure facts);
      `__post_init__` isolation — mutating the caller's `types` list after
      construction leaves `facts.types` unchanged (fresh containers at every
      level incl. each `dependencies` value); edge cases — `types == []`,
      `dependencies == {}`, `children == []` all construct and compare equal
      (children may name pruned cells — the facts never prune);
      `GateVerdict(violations=[]).approved is True`;
      `GateVerdict(violations=[Violation(tool="t", hook="h", reason="r")]).approved
      is False` and the violation reads back verbatim;
      `facts.cell = "x"` raises `dataclasses.FrozenInstanceError` (also assert
      it surfaces as `AttributeError`)
- [ ] **Debugging**: `pytest tests/codegraph/hooks -x` — all pass
- [ ] **Contract re-verification**: the three names importable from
      `goga.codegraph.hooks`; no extra public names on the facade beyond them
- [ ] Lint: `ruff check goga/codegraph/hooks tests/codegraph/hooks` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 5: Codegraph zone `amendments.py` + `contexts.py` — the two delivered views (TDD coding)

The two per-tool views of the zone: `NodeAmendment` (the read-and-contribute
view of the amendment checkpoint) and `GraphValidation` (the gate's
observe-and-veto view). Both are `kw_only` mutable dataclasses owning private
buffers — the shape of `goga/schema/hooks/{amendments,contexts}.py`. Two small
single-class modules of one lifecycle → one task; tests mirror as two files.

**Usages relevant to this task:**
- `convention`: `kw_only` dataclasses; relative imports
  (`from .facts import NodeFacts`, `from ..facts import CodegraphNode`);
  Google docstrings; tests mirror as `tests/codegraph/hooks/test_amendments.py`
  and `tests/codegraph/hooks/test_contexts.py`.
- `registering-hooks` (from Imports, `goga/hooks`): the hook signature that
  receives these views — a hook declares `context` and reads/calls freely;
  attribute assignment on the delivered object is blocked by the platform
  proxy (lands in Task 7); the views themselves just carry the facts and the
  buffer.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/codegraph/hooks/test_amendments.py`:
      `NodeAmendment` importable from the facade; `kw_only` dataclass (not
      frozen — the buffer is delivery state); field set is exactly `node` plus
      the internal `_pending` (`init=False`, `repr=False` — absent from the
      constructor signature and from `repr`); `contribute` exists with the
      signature `(facts: dict[str, object]) -> None`. Create
      `tests/codegraph/hooks/test_contexts.py`: `GraphValidation` importable;
      `kw_only` dataclass (not frozen); field set exactly `tree` plus the
      internal `_veto` (`init=False`, `default=None`, `repr=False`); `veto`
      exists with the signature `(reason: str) -> None` (expected to fail)
- [ ] **Code**: create `goga/codegraph/hooks/amendments.py` (module docstring
      in the schema-zone style): `@dataclass(kw_only=True) class
      NodeAmendment` with `node: NodeFacts` and
      `_pending: list = field(init=False, default_factory=list, repr=False)`;
      `contribute(facts)` appends `facts` verbatim to `self._pending` and
      returns `None`; docstrings carry the contract Requirements (buffers into
      this tool's buffer alone; changes nothing until the delivery commits it;
      merges key-wise later-wins; an empty mapping contributes nothing) and the
      Constraint (do not cancel, redirect, or defer the operation)
- [ ] **Code**: create `goga/codegraph/hooks/contexts.py`:
      `@dataclass(kw_only=True) class GraphValidation` with
      `tree: list[CodegraphNode]` and
      `_veto: str | None = field(init=False, default=None, repr=False)`;
      `veto(reason)` replaces `self._veto` whole and returns `None`; docstrings
      carry the Requirements (one fresh view per tool; the reads deliver the
      final tree read-only; the buffer belongs to this tool alone; the
      replacement is whole — a later call replaces the earlier reason; the view
      records no hook identity; an empty or whitespace-only reason is stored as
      given) and the Constraint (a veto stops the generation through the
      collected verdict only)
- [ ] **Code**: update `goga/codegraph/hooks/__init__.py` —
      `from .amendments import NodeAmendment` and
      `from .contexts import GraphValidation`; extend sorted `__all__`
- [ ] **Interface verification**: `pytest tests/codegraph/hooks/test_amendments.py
      tests/codegraph/hooks/test_contexts.py -x` — all contract tests pass
- [ ] **Logic tests** (`test_amendments.py`): `contribute` buffers verbatim —
      `contribute({"a": 1, "b": 2})` then `contribute({"a": 3})` leaves
      `_pending == [{"a": 1, "b": 2}, {"a": 3}]`; `contribute({})` buffers
      `[{}]` (buffering changes nothing outside the view — validation is not
      here); a non-dict payload is stored verbatim (the delivery's guard lands
      in Task 7); `contribute` returns `None`; `view.node` returns the passed
      `NodeFacts`
- [ ] **Logic tests** (`test_contexts.py`): `veto("broken")` sets
      `_veto == "broken"`; a second `veto("worse")` replaces it whole
      (`_veto == "worse"`); `veto("   ")` stores the whitespace verbatim;
      `veto` returns `None`; fresh view starts `_veto is None`; `view.tree`
      returns the passed list verbatim
- [ ] **Debugging**: `pytest tests/codegraph/hooks -x` — all pass
- [ ] **Contract re-verification**: facade exposes `NodeAmendment` and
      `GraphValidation` alongside the earlier names; signatures and field sets
      match the contract
- [ ] Lint: `ruff check goga/codegraph/hooks tests/codegraph/hooks` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 6: Codegraph zone `overlay.py` — `ToolContribution` and `merge_node_contributions` (TDD coding)

The overlay layer: one committed contribution (frozen `kw_only` pairing of the
tool identity with its merged fact mapping — constructed by the delivery alone)
and the deterministic pure routine composing the `tools` mapping. Both share
`location: overlay.py` → one task. Structural validation is NOT here — it
happens at the tool commit point of the delivery (Task 7).

**Usages relevant to this task:**
- `convention`: frozen `kw_only` dataclass for the record; Google docstrings
  with Args/Returns; pure routine (no filesystem, no mutation); tests mirror as
  `tests/codegraph/hooks/test_overlay.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/codegraph/hooks/test_overlay.py`: both
      names importable from the facade; `ToolContribution` is a frozen
      `kw_only` dataclass with exactly the fields `tool, facts` (positional
      construction raises `TypeError`); `merge_node_contributions` is a
      module-level function with the signature
      `(contributions: list[ToolContribution]) -> dict` (expected to fail)
- [ ] **Code**: create `goga/codegraph/hooks/overlay.py` (module docstring in
      the schema-zone style): `@dataclass(frozen=True, kw_only=True) class
      ToolContribution` with `tool: str` and `facts: dict[str, object]`;
      `merge_node_contributions(contributions)` implemented as the composition
      `{c.tool: c.facts for c in contributions if c.facts}` with the contract's
      four-step algorithm in the docstring (enumeration order; skip empty — a
      tool's key exists iff that tool wrote at least one fact; place under the
      tool identity key; return `{}` when nothing committed)
- [ ] **Code**: update `goga/codegraph/hooks/__init__.py` —
      `from .overlay import ToolContribution, merge_node_contributions`;
      extend sorted `__all__`
- [ ] **Interface verification**: `pytest tests/codegraph/hooks/test_overlay.py
      -x` — all contract tests pass
- [ ] **Logic tests**: composition in enumeration order — with
      `ToolContribution(tool="alpha", facts={"x": 1})`,
      `ToolContribution(tool="beta", facts={"y": 2})`,
      `ToolContribution(tool="gamma", facts={})`: result `== {"alpha": {"x": 1},
      "beta": {"y": 2}}` and `list(result) == ["alpha", "beta"]`; purity — the
      inputs stay unmutated after the call (the list and each mapping);
      `merge_node_contributions([]) == {}`; every contribution empty → `{}`
- [ ] **Debugging**: `pytest tests/codegraph/hooks -x` — all pass
- [ ] **Contract re-verification**: facade exposes both names; the routine is
      pure (no filesystem access, no input mutation)
- [ ] Lint: `ruff check goga/codegraph/hooks tests/codegraph/hooks` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 7: Codegraph zone `events.py` — `CodegraphHooks` (amend_node + validate_graph); facade completion (TDD coding)

The core delivery task of the codegraph zone. `CodegraphHooks` owns the
lazily-built run registry, drives the hard `codegraph / amend_node` delivery per
tool, commits each passing tool as one `ToolContribution`, and drives the
`codegraph / validate_graph` walk-to-completion gate. This task also completes
the zone facade (all eight contract names), writes
`tests/codegraph/hooks/test_events.py` — the largest suite of the zone — and the
facade suite `tests/codegraph/hooks/test_facade.py` (the
`tests/schema/hooks/test_facade.py` precedent).

Delivery algorithm (verbatim from the design; mirror of `SchemaHooks`,
codegraph naming):

```
1. __init__: _registry = None                     # cheap construction
2. _ensure_registry(): build_once() on first use; reuse afterwards
3. amend_node(node):
     resolve codegraph/amend_node in declared_actions
     groups = subscriptions_for(...) grouped per tool (enumeration order)
     for tool, subs in groups:
         view = NodeAmendment(node=_read_only_view(node))   # fresh containers
         proxy = wrap_context(view)
         for sub in subs:
             try: sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))
             except Exception as reason:
                 raise ValueError(f"hook {sub.name} of tool {tool} failed on "
                                  f"codegraph.amend_node at {node.cell}: {reason}") from reason
         merged = _commit_tool_buffer(tool, node.cell, view._pending)
         if merged: contributions.append(ToolContribution(tool, merged))
     return merge_node_contributions(contributions)
4. validate_graph(tree):
     resolve codegraph/validate_graph
     for tool, subs in groups:
         view = GraphValidation(tree=_copy_tree(tree))      # fresh nodes + overlay copies
         attributed_hook = ""; crash = None
         for sub in subs:
             before = view._veto
             try: sub.hook(**build_hook_arguments(...))
             except Exception as reason: crash = (sub.name, str(reason)); break
             if view._veto != before: attributed_hook = sub.name
         if crash is not None:      violations.append(Violation(tool, crash[0], crash[1]))
         elif view._veto is not None: violations.append(Violation(tool, attributed_hook, view._veto))
     return GateVerdict(violations=violations)
```

Module-private helpers in `events.py` (schema-zone precedents):
`_read_only_view(node: NodeFacts) -> NodeFacts` (fresh lists at every level —
closes the in-place-write channel between tools); `_copy_json(value)` (dicts and
lists recursively, tuples → lists, scalars as-is); `_copy_tree(nodes)` (rebuilt
`CodegraphNode`s incl. `tools` via `_copy_json`); `_nested_scope(value, where,
ancestors)` (cycle guard); `_check_json_map(value, where, ancestors)` (JSON-map
shape: non-empty mappings, string keys, serializable scalars, finite floats, no
cycles); `_commit_tool_buffer(tool, cell_path, pending)` (strict
`collections.abc.Mapping` guard per payload BEFORE `dict.update` → key-wise
merge → `_check_json_map` on the merged buffer → `copy.deepcopy` ownership cut;
`ValueError(f"tool {tool} failed on codegraph.amend_node at {cell_path}:
structurally malformed contribution ({reason})")`). The empty merged buffer
itself is not an error — it commits nothing silently (`if merged:` guard).

Implementation notes (mandatory, from the design's Additional Instructions):
the structural check is an explicit recursive validator — NOT a `json.dumps`
try/except (dumps coerces non-string keys and accepts NaN/Infinity; both must
fail); `ImportError` from `build_once` is the single fatal platform case (it
propagates, naming the package); the zone never logs and never prints.

**Usages relevant to this task:**
- `convention`: Google docstrings; relative imports; tests mirror as
  `tests/codegraph/hooks/test_events.py`; the platform boundary fixtures
  (`pin_package_environment`, `install_tool_package` from the zone conftest)
  pin the two outside-world points — the platform code runs for real, no mocks
  inside it.
- `per-tool-delivery` (from Imports, `goga/hooks`): the staged delivery loop
  applies as written — registry + `build_once`, group
  `subscriptions_for(domain, action)` by `sub.tool` into an insertion-ordered
  dict, `wrap_context` / `build_hook_arguments` projection, tool-granular
  commit, one registry per run, deliver to every subscriber — with the hard
  semantics of `amend_node` (stop at the first failure) and the recorded
  `validate_graph` refinement (walk to completion, collect one violation per
  tool, no commit).
- `registering-hooks` (from Imports, `goga/hooks`): a hook receives values only
  for the parameters it declares by the offered names `context` / `self`
  (`build_hook_arguments` is the single projection — never deliver an
  undeclared value); a broken package import is the only fatal platform case.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/codegraph/hooks/test_events.py`:
      `CodegraphHooks` importable from the facade; the constructor takes no
      arguments; `amend_node` signature is `(node: NodeFacts) -> dict`;
      `validate_graph` signature is `(tree: list[CodegraphNode]) -> GateVerdict`
      (expected to fail)
- [ ] **REPL probe**: in the virtualenv REPL, exercise the live schema-zone
      delivery once (`from goga.schema.hooks import SchemaHooks` over a pinned
      environment with an installed fake tool) and observe the helper behaviors
      this task mirrors — the per-tool fresh view, the buffered commit, the
      structural failure text shape; confirm the enumeration identity
      `goga_tool_docs` → `docs` live. Grounds the assertions below.
- [ ] **Code**: create `goga/codegraph/hooks/events.py` — module docstring in
      the schema-zone style; the six module-private helpers;
      `CodegraphHooks` with `__init__`, `_ensure_registry`, `amend_node`, and
      `validate_graph` implementing the algorithm above; the pinned failure
      formats exactly as specified; imports
      `from ...hooks import HookRegistry, build_hook_arguments, declared_actions, wrap_context`
      (three dots up — no import cycle),
      `from ..facts import CodegraphNode`,
      `from .amendments import NodeAmendment`,
      `from .contexts import GraphValidation`,
      `from .facts import GateVerdict, NodeFacts, Violation`,
      `from .overlay import ToolContribution, merge_node_contributions`
- [ ] **Code**: complete the facade — `goga/codegraph/hooks/__init__.py`
      re-exports all eight contract names from the five modules with the final
      zone docstring;
      `sorted(__all__) == ["CodegraphHooks", "GateVerdict", "GraphValidation",
      "NodeAmendment", "NodeFacts", "ToolContribution", "Violation",
      "merge_node_contributions"]`
- [ ] **Code**: create `tests/codegraph/hooks/test_facade.py` mirroring
      `tests/schema/hooks/test_facade.py` — the facade suite of the assembled
      zone (the `_IMPLEMENTING` name-to-entity map, the exact alphabetical
      `__all__`, cheap construction)
- [ ] **Interface verification**: `pytest tests/codegraph/hooks/test_events.py
      -x` — the contract tests above pass (the logic tests are not written yet
      at this step)
- [ ] **Logic tests (positive)** — transfer the design scenarios verbatim:
      `test_amend_node_commits_buffered_facts` (pin
      `{"goga_tool_docs": ["docs-dist"]}` + install `goga_tool_docs`
      subscribing `("codegraph", "amend_node", "cover", cover)` with
      `cover(context)` calling `context.contribute({"coverage": 3})`;
      `NodeFacts(cell="goga/config", types=["ProjectConfig"],
      dependencies={}, children=["goga/config/hooks"])`;
      `CodegraphHooks().amend_node(node=facts) == {"docs": {"coverage": 3}}`);
      `test_amend_node_empty_contribute_commits_nothing` (a hook contributing
      `{}` → result `{}`; the delivered view's `_pending == [{}]` — buffered,
      merged to nothing); `test_contribute_merges_key_wise_later_wins` (one
      hook contributing `{"coverage": 3, "owner": "a"}` then
      `{"coverage": 9}` → `{"docs": {"coverage": 9, "owner": "a"}}`);
      `test_amend_node_builds_registry_once_per_run` (the tool subscribes to
      both actions with a counter hook; `hooks.amend_node(n1)` then
      `hooks.validate_graph([node])` → `boundary.call_count == 1`, both
      checkpoints delivered);
      `test_amend_node_committed_area_is_owned` (the hook stashes its
      contribution dict on `self.sink`, contributes `{"coverage": 3}`, and
      mutates `self.sink["coverage"] = 99` in place before every later
      contribute; two nodes `a` and `b` → `t1 == {"docs": {"coverage": 3}}`
      and STILL `== {"docs": {"coverage": 3}}` after the second node, `t2 ==
      {"docs": {"coverage": 99}}` — the ownership cut of
      `_commit_tool_buffer`)
- [ ] **Logic tests (positive, gate)** —
      `test_validate_graph_collects_one_violation_per_tool_and_walks_to_completion`
      (two tools — `goga_tool_gate` vetoes `context.veto("broken")`,
      `goga_tool_docs` only records `len(context.tree)`; a `CodegraphNode` with
      `tools={"docs": {"a": 1}}` → `verdict.approved is False`;
      `[(v.tool, v.reason) for v in verdict.violations] == [("gate",
      "broken")]`; the docs hook ran (its recording list is non-empty); the
      caller's `tree` objects untouched);
      `test_validate_graph_crash_overrides_veto_and_continues` (tool A's hook
      vetoes then a second hook of the same tool raises `RuntimeError("boom")`;
      tool B observes → `verdict.violations[0].reason == "boom"`;
      `"Traceback" not in ...`; B's hook ran);
      `test_validate_graph_delivers_fresh_tree_copy_per_tool` (the first hook
      of tool A appends `"X"` to `context.tree[0].types` in place; tool B
      records `list(context.tree[0].types)` → `["Thing"]`; the caller's
      `tree[0].types == ["Thing"]`; `verdict.approved is True`)
- [ ] **Logic tests (negative)**:
      `test_amend_node_crashed_hook_is_a_hard_failure_naming_the_subject` (a
      hook raising `RuntimeError("kaboom")` over
      `NodeFacts(cell="goga/codegraph")` →
      `pytest.raises(ValueError, match=r"hook boom of tool docs failed on
      codegraph\.amend_node at goga/codegraph: kaboom")`;
      `"Traceback" not in str(excinfo.value)`);
      `test_amend_node_structurally_malformed_contribution_fails_the_same_way`
      (parametrized payloads: `[("a", 1)]` — a non-mapping payload, `{"k": {}}`
      — an empty nested mapping, `{1: "x"}` — a non-string key,
      `{"k": {object()}}` — non-serializable, `{"k": float("nan")}` —
      non-finite, a self-referencing dict — a cycle; every payload →
      `pytest.raises(ValueError, match=r"tool docs failed on
      codegraph\.amend_node at goga/config: structurally malformed
      contribution")`)
- [ ] **Logic tests (edge)**:
      `test_amend_node_fresh_view_per_tool_keeps_writes_local` (two tools; the
      first mutates `context.node.types` in place
      (`context.node.types.append("X")` — a private copy); the second records
      `list(context.node.types)` → `["ProjectConfig"]`; the caller's original
      `NodeFacts.types` unchanged); the codegraph cases of
      `test_zone_checkpoints_without_subscriptions_are_inert` (parametrized:
      environment empty — `amend_node(node=_node_facts())` → `{}`;
      `validate_graph([_final_node()])` → `verdict.approved is True and
      verdict.violations == []`); construction enumerates nothing (a pinned
      environment with a subscribed scratch tool; after `CodegraphHooks()`
      alone, `boundary.call_count == 0`)
- [ ] **Logic tests (facade)**: `test_zone_facade_reexports_the_contract_names`
      in `tests/codegraph/hooks/test_facade.py` — all eight names import from
      `goga.codegraph.hooks`; the alphabetical `__all__` equals exactly the
      eight names; each name resolves to the implementing class or function of
      its declaring module (`facts` / `amendments` / `contexts` / `overlay` /
      `events`, the schema-precedent `_IMPLEMENTING` map); `CodegraphHooks()`
      constructs without enumerating packages
- [ ] **Debugging**: `pytest tests/codegraph/hooks -x` — all pass
- [ ] **Contract re-verification**: all eight names importable from
      `goga.codegraph.hooks`; `amend_node` / `validate_graph` shapes and the
      pinned failure formats match the contract; no printing, no logging in
      the zone
- [ ] Lint: `ruff check goga/codegraph/hooks tests/codegraph/hooks` and
      `ruff format --check` over the same paths — fix formatting, apply
      decomposition if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 8: Drift zone `facts.py` — the moment and entry fact records (TDD coding)

The fact vocabulary of the drift zone: the start-moment filters, the delivered
entry view, the completion-moment entry projection, the outcome `Enum`, and the
completion facts. All five share `location: facts.py` → one task. This task
also creates the drift zone package and its facade seed. Mirror
`goga/usages/hooks/facts.py` for `RunOutcome` (plain `Enum` with string member
values) and the frozen-record family for the rest.

**Usages relevant to this task:**
- `convention`: frozen `kw_only` dataclasses for the records; `enum.Enum` for
  the fixed value set; empty defaults (`ReportEntry.tools` defaults `{}` via
  `default_factory`); `None` only for explicit absence (`EntryFacts.types`,
  `RunCompletion.report`); relative imports; Google docstrings; tests mirror
  as `tests/drift/hooks/test_facts.py`; use `is_kw_only_dataclass` from
  `tests/conftest`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/drift/hooks/test_facts.py`: the five
      names importable from the facade `goga.drift.hooks`; the four dataclasses
      are frozen `kw_only` (positional construction raises `TypeError`); exact
      field sets — `DriftFilters`: `cells, max_depth, depends_on`; `EntryFacts`:
      `kind, cell, types`; `ReportEntry`: `kind, cell, types, tools` (with
      `tools` defaulted `{}`); `RunCompletion`: `report, outcome, reason`;
      `RunOutcome` is an `Enum` with exactly the members `finished` and
      `crashed` (expected to fail — the package has no implementation)
- [ ] **Code**: create `goga/drift/hooks/__init__.py` — a module docstring
      naming the zone ("Hooks zone of the drift domain — the run moments, the
      report amendment, the entry-facts amendment, and the checkpoint surface
      over the hooks platform.") with the incremental-build note, plus
      `__all__: list[str] = []`
- [ ] **Code**: create `goga/drift/hooks/facts.py` (module docstring in the
      zone style): `DriftFilters` (frozen `kw_only`; `__post_init__` copies
      `cells`, `depends_on`), `EntryFacts` (frozen; copies `types`),
      `ReportEntry` (frozen; copies `types`; `tools:
      dict[str, dict[str, object]] = field(default_factory=dict)`),
      `RunOutcome(Enum)` with `finished = "finished"` and
      `crashed = "crashed"`, `RunCompletion` (frozen; `report:
      list[ReportEntry] | None`, `outcome: RunOutcome`, `reason: str`);
      docstrings carry the contract property descriptions — pure facts, the
      delivered read views never carry contributions, the credential-free
      reason requirement
- [ ] **Code**: update `goga/drift/hooks/__init__.py` —
      `from .facts import DriftFilters, EntryFacts, ReportEntry, RunCompletion,
      RunOutcome` and extend `__all__` (keep it sorted)
- [ ] **Interface verification**: `pytest tests/drift/hooks/test_facts.py -x`
      — all contract tests pass
- [ ] **Logic tests**: the design's
      `test_run_outcome_members_and_run_completion_none_report` verbatim —
      `RunOutcome.finished.value == "finished"`,
      `RunOutcome.crashed.value == "crashed"`,
      `list(RunOutcome) == [RunOutcome.finished, RunOutcome.crashed]`;
      `RunCompletion(report=None, outcome=RunOutcome.crashed, reason="x")`
      constructs and reads back verbatim (the record is frozen and kw_only —
      `is_kw_only_dataclass`); field isolation — mutating the caller's
      `cells`/`depends_on`/`types` lists after construction leaves the records
      unchanged; `ReportEntry(kind="schema_only", cell="a")` defaults
      `tools == {}` and `types is None`; edge —
      `DriftFilters(cells=[], max_depth=None, depends_on=[])` constructs and
      compares equal
- [ ] **Debugging**: `pytest tests/drift/hooks -x` — all pass
- [ ] **Contract re-verification**: the five names importable from
      `goga.drift.hooks`; no extra public names on the facade beyond them
- [ ] Lint: `ruff check goga/drift/hooks tests/drift/hooks` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 9: Drift zone `amendments.py` — `ReportAmendment` and `EntryAmendment` (TDD coding)

The two amendment views: the whole-list adjuster of the report and the per-entry
contributor. Both are `kw_only` mutable dataclasses owning private buffers —
`ReportAmendment._adjustment` (sentinel `None`) and `EntryAmendment._pending`.
One `location` → one task.

**Usages relevant to this task:**
- `convention`: `kw_only` dataclasses; relative imports
  (`from .facts import EntryFacts`); Google docstrings; tests mirror as
  `tests/drift/hooks/test_amendments.py`.
- `registering-hooks` (from Imports, `goga/hooks`): the hook signature that
  receives these views — `context` declared and read/called freely; assignment
  blocked by the platform proxy (Task 11); the no-provenance constraint of
  `adjust` (no marker, annotation, or flag of the adjustment appears anywhere
  in the output).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/drift/hooks/test_amendments.py`: both
      names importable from the facade; both `kw_only` dataclasses (not
      frozen); `ReportAmendment` field set exactly `report` plus the internal
      `_adjustment` (`init=False`, `default=None`, `repr=False`); `adjust`
      exists with the signature `(entries: list[dict[str, object]]) -> None`;
      `EntryAmendment` field set exactly `entry` plus the internal `_pending`;
      `contribute` exists with the signature
      `(facts: dict[str, object]) -> None` (expected to fail)
- [ ] **Code**: create `goga/drift/hooks/amendments.py` (module docstring in
      the zone style): `@dataclass(kw_only=True) class ReportAmendment` with
      `report: list[EntryFacts]` and `_adjustment: list | None =
      field(init=False, default=None, repr=False)`; `adjust(entries)` buffers
      the replacement verbatim and returns `None` (a later call replaces the
      earlier). `@dataclass(kw_only=True) class EntryAmendment` with
      `entry: EntryFacts` and the `_pending` buffer;
      `contribute(facts)` appends verbatim. Docstrings carry the contract
      Requirements (buffers into this tool's buffer alone; changes nothing
      until the delivery validates and adopts/commits it; whole replacement;
      the view records no hook identity; an adjusted list may be empty) and
      the Constraints (do not cancel, redirect, or defer; do not emit
      provenance)
- [ ] **Code**: update `goga/drift/hooks/__init__.py` —
      `from .amendments import EntryAmendment, ReportAmendment`; extend sorted
      `__all__`
- [ ] **Interface verification**: `pytest tests/drift/hooks/test_amendments.py
      -x` — all contract tests pass
- [ ] **Logic tests**: `adjust` buffers verbatim —
      `adjust([{"kind": "schema_only", "cell": "a"}])` sets
      `_adjustment == [{"kind": "schema_only", "cell": "a"}]`; a second
      `adjust([])` replaces it whole (`_adjustment == []` — clearing is a
      valid adjustment); a non-list payload is stored verbatim (validation is
      the delivery's, Task 11); `adjust` returns `None`; fresh view starts
      `_adjustment is None`; `contribute` buffers verbatim (the Task 5
      mirror assertions over `_pending`); `view.report` / `view.entry` return
      the passed values
- [ ] **Debugging**: `pytest tests/drift/hooks -x` — all pass
- [ ] **Contract re-verification**: facade exposes both names alongside the
      earlier five; signatures and field sets match the contract
- [ ] Lint: `ruff check goga/drift/hooks tests/drift/hooks` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 10: Drift zone `overlay.py` — `ToolContribution` and `merge_entry_contributions` (TDD coding)

The overlay layer of the drift zone — the same composition as the codegraph
zone (Task 6), over entries. Both entities share `location: overlay.py` → one
task. Structural validation is NOT here.

**Usages relevant to this task:**
- `convention`: frozen `kw_only` dataclass; Google docstrings with
  Args/Returns; pure routine; tests mirror as
  `tests/drift/hooks/test_overlay.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/drift/hooks/test_overlay.py`: both
      names importable from the facade; `ToolContribution` (drift zone's own)
      is a frozen `kw_only` dataclass with exactly the fields `tool, facts`;
      `merge_entry_contributions` is a module-level function with the
      signature `(contributions: list[ToolContribution]) -> dict` (expected to
      fail)
- [ ] **Code**: create `goga/drift/hooks/overlay.py` (module docstring in the
      zone style): `@dataclass(frozen=True, kw_only=True) class
      ToolContribution` with `tool: str` and `facts: dict[str, object]`;
      `merge_entry_contributions(contributions)` implemented as
      `{c.tool: c.facts for c in contributions if c.facts}` with the same
      four-step algorithm docstring as the codegraph zone
- [ ] **Code**: update `goga/drift/hooks/__init__.py` —
      `from .overlay import ToolContribution, merge_entry_contributions`;
      extend sorted `__all__`
- [ ] **Interface verification**: `pytest tests/drift/hooks/test_overlay.py
      -x` — all contract tests pass
- [ ] **Logic tests**: composition in enumeration order, empty skipped
      (the Task 6 mirror: alpha/beta/gamma inputs →
      `{"alpha": {"x": 1}, "beta": {"y": 2}}`, `list(result) == ["alpha",
      "beta"]`); purity — inputs unmutated; `merge_entry_contributions([]) ==
      {}`; every contribution empty → `{}`
- [ ] **Debugging**: `pytest tests/drift/hooks -x` — all pass
- [ ] **Contract re-verification**: facade exposes both names; the routine is
      pure
- [ ] Lint: `ruff check goga/drift/hooks tests/drift/hooks` and
      `ruff format --check` over the same paths — fix formatting if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 11: Drift zone `events.py` — `DriftHooks` (moments + amendments); facade completion (TDD coding)

The core delivery task of the drift zone. `DriftHooks` owns the lazily-built
run registry shared by the moments and the amendments, emits the two soft
moments through the platform `emit_hook_event`, drives the hard
`drift / amend_report` whole-list adjustment walk and the hard
`drift / amend_entry` per-tool contribution walk. This task also completes the
zone facade (all ten contract names) and writes
`tests/drift/hooks/test_events.py` plus `tests/drift/hooks/test_facade.py`.

Delivery algorithm (verbatim from the design):

```
1. __init__: _registry = None
2. _ensure_registry(): build_once() on first use; reuse across moments and amendments
3. emit_run_started(filters):
     context = _RunStarted(filters=filters)          # private frozen wrapper
     emit_hook_event(registry, "drift", "run_started", context_for=lambda _tool: context)
4. amend_report(report):
     resolve drift/amend_report; groups per tool
     current = [EntryFacts copy for e in report]     # working list; input never mutated
     for tool, subs in groups:
         view = ReportAmendment(report=[fresh EntryFacts copies of the ORIGINAL report])
         proxy = wrap_context(view); attributed = ""
         for sub in subs:
             before = view._adjustment
             try: call hook
             except Exception as reason:
                 raise ValueError(f"hook {sub.name} of tool {tool} failed on "
                                  f"drift.amend_report: {reason}") from reason
             if view._adjustment is not before: attributed = sub.name
         if view._adjustment is not None:
             entries = _validate_adjustment(view._adjustment)   # closed shape or hard failure
             current = [EntryFacts(kind=e["kind"], cell=e["cell"],
                                   types=list(e["types"]) if "types" in e else None)
                        for e in entries]
     return current
5. amend_entry(entry): per-tool walk identical to amend_node with
   drift.amend_entry addressing and "at {entry.kind} {entry.cell}" subjects;
   compose via merge_entry_contributions
6. emit_run_completed(completion):
     context = _RunCompleted(completion=completion)  # private frozen wrapper
     emit_hook_event(registry, "drift", "run_completed", context_for=lambda _tool: context)
```

`_validate_adjustment(entries)` — the closed-shape check (hard failure
`ValueError(f"hook {attributed} of tool {tool} failed on drift.amend_report:
malformed adjustment ({detail})")`):

```
- entries must be exactly a list                     (a tuple/str/None is malformed)
- each entry must be a strict Mapping                (not an iterable of pairs)
- keys ⊆ {kind, cell, types}
- kind present, one of "schema_only" / "codegraph_only"
- cell  present, a str, non-empty as given — no sanitation (a whitespace-only
  cell is carried verbatim like a whitespace veto reason)
- types absent, or a list whose every element is a str (an empty list is carried
  verbatim — the contract admits "a list of strings"; never sanitized)
```

The two private wrapper records (delivery shape, not contract surface — the
consumer doc commits to the attributes):

```python
@dataclass(frozen=True, kw_only=True)
class _RunStarted:
    filters: DriftFilters

@dataclass(frozen=True, kw_only=True)
class _RunCompleted:
    completion: RunCompletion
```

Module-private helpers in `events.py`: `_read_only_view` over `EntryFacts`
(fresh `types` list), `_copy_json`, `_nested_scope`, `_check_json_map`,
`_commit_tool_buffer(tool, entry_subject, pending)` with the
`drift.amend_entry` failure formats — the schema-zone precedents with drift
naming. `amend_entry` mirrors `CodegraphHooks.amend_node` steps 2, 4–10 with:
address `drift/amend_entry`, view `EntryAmendment(entry=EntryFacts copy)`,
crash format `"hook {name} of tool {tool} failed on drift.amend_entry at
{kind} {cell}: {reason}"`, structural format `"tool {tool} failed on
drift.amend_entry at {kind} {cell}: structurally malformed contribution
({detail})"`, composition via `merge_entry_contributions`. The moments are
soft — a failing hook logs `WARNING` via the platform
(`logger.warning("hook %s of tool %s failed on %s.%s: %s", …)`) and the
sequence continues; no raise path for hook failures.

**Usages relevant to this task:**
- `convention`: Google docstrings; relative imports; tests mirror as
  `tests/drift/hooks/test_events.py`; the boundary fixtures pin the two
  outside-world points — the platform runs for real.
- `per-tool-delivery` (from Imports, `goga/hooks`): the staged delivery loop
  for both amendments as written — grouping, fresh view per tool, projection,
  tool-granular commit — with the list-control refinement of `amend_report`
  (whole replacement over the ORIGINAL, last adjusting tool wins) and the
  entry mirror of `amend_entry`.
- `declaring-actions` (from Imports, `goga/hooks`): the emission contract of
  the two moments — `emit_hook_event(self._ensure_registry(), "drift",
  "<action>", context_for=lambda _tool: context)`; soft semantics (failing
  hook → warning, continue).
- `registering-hooks` (from Imports, `goga/hooks`): the registration contract
  behind every checkpoint — `context` / `self` projection; a broken package
  import is the only fatal platform case.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: create `tests/drift/hooks/test_events.py`:
      `DriftHooks` importable from the facade; the constructor takes no
      arguments; the four method signatures — `emit_run_started(filters:
      DriftFilters) -> None`, `amend_report(report: list[EntryFacts]) ->
      list[EntryFacts]`, `amend_entry(entry: EntryFacts) -> dict`,
      `emit_run_completed(completion: RunCompletion) -> None` (expected to
      fail)
- [ ] **REPL probe**: in the virtualenv REPL, observe the live platform
      `emit_hook_event` soft path once (a fake tool whose hook raises; `caplog`
      or `logging` captured) confirming the warning text shape
      `hook {name} of tool {tool} failed on {domain}.{action}: {reason}` and
      the continue-past-failure behavior; confirm the shared-context delivery
      (`context_for=lambda _tool: context` hands every tool the same frozen
      instance) against the pipeline-zone precedent. Grounds the moment
      assertions below.
- [ ] **Code**: create `goga/drift/hooks/events.py` — module docstring in the
      zone style; the module-private helpers; `_RunStarted` / `_RunCompleted`;
      `_validate_adjustment`; `DriftHooks` with `__init__`,
      `_ensure_registry`, `emit_run_started`, `amend_report`, `amend_entry`,
      `emit_run_completed` implementing the algorithm above; the pinned
      failure formats exactly as specified; imports
      `from ...hooks import HookRegistry, build_hook_arguments, declared_actions, emit_hook_event, wrap_context`
      and the zone-internal modules
- [ ] **Code**: complete the facade — `goga/drift/hooks/__init__.py` re-exports
      all ten contract names with the final zone docstring;
      `sorted(__all__) == ["DriftFilters", "DriftHooks", "EntryAmendment",
      "EntryFacts", "ReportAmendment", "ReportEntry", "RunCompletion",
      "RunOutcome", "ToolContribution", "merge_entry_contributions"]`
- [ ] **Code**: create `tests/drift/hooks/test_facade.py` mirroring
      `tests/schema/hooks/test_facade.py`
- [ ] **Interface verification**: `pytest tests/drift/hooks/test_events.py -x`
      — the contract tests above pass
- [ ] **Logic tests (moments, positive)** — transfer the design scenarios
      verbatim: `test_emit_run_started_is_soft_and_delivers_the_filters` (pin
      `{"goga_tool_watch": ["watch-dist"]}`; two hooks in one tool — the
      first records `(context.filters.cells, context.filters.max_depth)`, the
      second raises `RuntimeError("nope")`;
      `DriftHooks().emit_run_started(DriftFilters(cells=["goga/config"],
      max_depth=2, depends_on=[]))` → no raise; recorder `==
      (["goga/config"], 2)`; `caplog` contains the warning (level WARNING,
      names tool and action));
      `test_emit_run_completed_delivers_the_terminal_facts` (one observing
      tool recording `context.completion.outcome`,
      `len(context.completion.report or [])`, `context.completion.reason`;
      `emit_run_completed(RunCompletion(report=[ReportEntry(kind="schema_only",
      cell="a", types=None, tools={})], outcome=RunOutcome.finished,
      reason=""))` → recorder `== ("finished", 1, "")`; no raise)
- [ ] **Logic tests (report amendment, positive)**:
      `test_amend_report_last_adjusting_tool_wins_and_tools_are_blind`
      (environment with two tools — enumeration order `goga_tool_alpha`, then
      `goga_tool_beta`; alpha adjusts `[{"kind": "schema_only", "cell": "a"}]`;
      beta reads `context.report` into a recorder and adjusts nothing; input
      `[EntryFacts(kind="codegraph_only", cell="z", types=None)]` → settled
      `== [EntryFacts(kind="schema_only", cell="a", types=None)]`; the
      recorder saw the original entry only — `z`, never `a`);
      `test_amend_report_two_adjusting_tools_last_wins_over_the_original`
      (alpha adjusts `[{"kind": "schema_only", "cell": "from-alpha"}]`; beta
      adjusts `[{"kind": "codegraph_only", "cell": "from-beta"}]`; input
      `[EntryFacts(kind="schema_only", cell="orig", types=None)]` → settled
      `== [EntryFacts(kind="codegraph_only", cell="from-beta", types=None)]`;
      `"from-alpha"` appears nowhere in the result — whole replacement over
      the original, never a chained merge);
      `test_amend_report_empty_adjustment_clears_and_adds_entries` (scenario
      A: one tool adjusting `[]` over a one-entry scoped list → `[]`;
      scenario B on a fresh surface: adjusting
      `[{"kind": "codegraph_only", "cell": "extra", "types": ["thing"]}]` →
      kind/cell/types as adjusted);
      `test_amend_report_carries_empty_types_list_and_cell_level_added_entry`
      (one tool adjusting `[{"kind": "schema_only", "cell": "leaf", "types":
      []}, {"kind": "codegraph_only", "cell": "whole"}]` over
      `[EntryFacts(kind="schema_only", cell="orig", types=None)]` → settled
      `== [EntryFacts(kind="schema_only", cell="leaf", types=[]),
      EntryFacts(kind="codegraph_only", cell="whole", types=None)]` — `[]` is
      a list of strings, an omitted `types` is a cell-level entry)
- [ ] **Logic tests (entry amendment, positive)**:
      `test_amend_entry_commits_facts_per_entry` (one contributing tool —
      `context.contribute({"ticket": "GOGA-1"})` — over
      `EntryFacts(kind="schema_only", cell="mix", types=["stale"])` → result
      `== {"<platform identity>": {"ticket": "GOGA-1"}}`)
- [ ] **Logic tests (negative)**:
      `test_amend_report_malformed_adjustment_is_never_adopted`
      (parametrized adjustments: `[{"kind": "wrong", "cell": "a"}]`,
      `[{"kind": "schema_only"}]`, `[{"kind": "schema_only", "cell": ""}]`,
      `[{"kind": "schema_only", "cell": "a", "extra": 1}]`,
      `[{"kind": "schema_only", "cell": "a", "types": "b"}]`,
      `("not", "a list")`, `[["kind", "cell"]]`; every payload →
      `pytest.raises(ValueError, match=r"hook .* of tool .* failed on
      drift\.amend_report: malformed adjustment")`);
      `test_amend_report_crashed_hook_stops_and_adopts_nothing` (two tools
      installed so the crashing `alpha` enumerates first — its hook raises
      `RuntimeError("boom")`; beta (later) adjusts validly →
      `pytest.raises(ValueError, match=r"failed on drift\.amend_report")`;
      beta's recorder is empty — first-failure stop);
      `test_amend_entry_hard_failure_names_the_entry` (a hook raising on one
      specific entry over `EntryFacts(kind="codegraph_only", cell="extra",
      types=["helper"])` →
      `pytest.raises(ValueError, match=r"failed on drift\.amend_entry at
      codegraph_only extra")`);
      `test_amend_entry_structurally_malformed_contribution_names_the_entry`
      (a hook calling `context.contribute({"k": {}})` over
      `EntryFacts(kind="schema_only", cell="mix", types=None)` → the merge
      hits the empty-nested-mapping check
      (`ValueError("empty mapping at the merged contribution.k")`) wrapped at
      the tool commit point →
      `pytest.raises(ValueError, match=r"tool docs failed on
      drift\.amend_entry at schema_only mix: structurally malformed
      contribution")`)
- [ ] **Logic tests (edge)**:
      `test_amend_report_returns_input_values_unchanged_without_subscriptions`
      (environment empty; input
      `[EntryFacts(kind="schema_only", cell="a", types=None),
      EntryFacts(kind="codegraph_only", cell="b", types=["x"])]` → settled
      `== report` by value equality; the input list object unmutated — still
      length 2); the drift case of
      `test_zone_checkpoints_without_subscriptions_are_inert`
      (`DriftHooks().amend_entry(EntryFacts(kind="schema_only", cell="a",
      types=None))` → `{}`); construction enumerates nothing (the Task 7
      mirror); ownership — the Task 7 `test_amend_node_committed_area_is_owned`
      mirror over `amend_entry` (the design notes the same mechanics)
- [ ] **Logic tests (facade)**: `test_zone_facade_reexports_the_contract_names`
      in `tests/drift/hooks/test_facade.py` — all ten names import from
      `goga.drift.hooks`; the alphabetical `__all__` equals exactly the ten
      names; the `_IMPLEMENTING` map resolves each name to its declaring
      module; `DriftHooks()` constructs without enumerating packages
- [ ] **Debugging**: `pytest tests/drift/hooks -x` — all pass
- [ ] **Contract re-verification**: all ten names importable from
      `goga.drift.hooks`; the four method shapes and the pinned failure
      formats match the contract; no printing, no logging in the zone (the
      soft-moment warning comes from the platform)
- [ ] Lint: `ruff check goga/drift/hooks tests/drift/hooks` and
      `ruff format --check` over the same paths — fix formatting, apply
      decomposition if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 12: The `codegraph` routine — checkpoint-aware assembly and the validation gate (TDD coding)

Rewrite `codegraph()` in `goga/codegraph/codegraph.py` per the contract's
10-step algorithm: the existing steps 1–5 (config → language whitelist →
ignore → discovery → analysis stages) are unchanged; the render, the
checkpoint walk, the overlay rebuild, and the gate follow. The routine
verbatim from the design:

```
def codegraph(cells, max_depth, depends_on):
    config → language → ignore → files → facts → units → links      # unchanged steps 1-5
    tree = render_graph(units, links, cells, max_depth, depends_on)
    filters_active = bool(cells) or max_depth is not None or bool(depends_on)
    complete_index = ({n.cell: n for n in _walk_nodes(render_graph(units, links, [], None, []))}
                      if filters_active else
                      {n.cell: n for n in _walk_nodes(tree)})
    if not tree:
        return []                                                   # before any checkpoint
    hooks = CodegraphHooks()
    overlays: dict[str, dict] = {}
    for node in _walk_nodes(tree):                                  # pre-order, tree order
        full = complete_index[node.cell]
        facts = NodeFacts(cell=node.cell, types=node.types,
                          dependencies=node.dependencies,
                          children=[c.cell for c in full.children])
        tools = hooks.amend_node(node=facts)
        if tools:
            overlays[node.cell] = tools
    final = _apply_overlays(tree, overlays)                         # recursive replace
    verdict = hooks.validate_graph(final)
    if not verdict.approved:
        details = "\n".join(f"- tool {v.tool} / hook {v.hook}: {v.reason}" for v in verdict.violations)
        raise ValueError(f"codegraph validation failed:\n{details}")
    return final

def _apply_overlays(nodes, overlays):
    return [dataclasses.replace(n, tools=overlays.get(n.cell, {}),
                                children=_apply_overlays(n.children, overlays))
            for n in nodes]
```

`_walk_nodes` is a pre-order generator mirroring
`goga/schema/schema.py::_walk_nodes` (over `CodegraphNode` records: yield the
node, then recurse into `children`). `render_graph` is pure/deterministic —
the complete index equals the unfiltered assembly; a node's own
`types`/`dependencies` are filter-independent (render builds nodes before
filters) — only `children` differ. Docstring `Raises` gains: checkpoint hard
failures (naming tool/action/cell), the merged veto error, and the
register-facade `ImportError`.

This task also creates `tests/codegraph/conftest.py` (the autouse empty
environment — the `tests/drift/conftest.py` pattern) because from now on every
non-empty tree the suite builds delivers the checkpoint through the real
registry, and adapts `tests/integration/test_codegraph_cli_integration.py`
(the same autouse pin, the `test_schema_walk_gate_integration.py` pattern).

**Usages relevant to this task:**
- `checkpoints` (from Imports, `goga/codegraph/hooks`): the consumer recipes —
  build `NodeFacts`, call `hooks.amend_node(node=facts)`, place the returned
  area iff non-empty, rebuild, gate before return; its snippets are the
  reference of the walk steps.
- `records` (from Imports, `goga/codegraph/facts`), `stages` (from Imports,
  `goga/codegraph/analysis`), `project-configuration` (from Imports,
  `goga/config`): the unchanged producer contracts of steps 1–5.
- `convention`: walk tests plant projects under `tmp_path` (the
  `tests/codegraph/test_codegraph.py` fixture style) with the autouse CWD
  isolation of `tests/conftest.py`; no mocks inside business logic.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/codegraph/test_codegraph.py` (extended):
      `from goga.codegraph import codegraph` still imports; over a `tmp_path`
      project with a contributing scratch tool (pinned environment +
      installed facade) `codegraph([], None, [])` returns
      `list[CodegraphNode]` records whose `tools == {"<tool>": {...}}` and
      whose `cell`/`types`/`dependencies`/`children` are unchanged (expected
      to fail — no delivery exists yet)
- [ ] **REPL probe**: plant the golden-tree fixture layout of
      `tests/commands/codegraph/test_codegraph.py`
      (`_write_golden_tree_project`) in a scratch `tmp_path`, `cd` there, and
      run the live `codegraph([], None, [])` in the REPL — confirm the
      returned node fields entry for entry against the golden JSON (types,
      dependencies incl. the empty `{}` of dependency-less cells, children);
      re-run with filters (`["greeting"]`, `max_depth=0`) and observe which
      nodes survive. Grounds the walk assertions below.
- [ ] **Code**: create `tests/codegraph/conftest.py` mirroring the autouse
      `_empty_package_environment` of `tests/drift/conftest.py` (docstring:
      every non-empty tree the routine builds now delivers the checkpoint
      through the real registry; tests that install a tool pin their own
      environment on top — the later pin wins)
- [ ] **Code**: modify `codegraph()` in `goga/codegraph/codegraph.py` per the
      algorithm above — the early `return []` on the empty tree (before
      `CodegraphHooks()` is ever constructed), `filters_active` /
      `complete_index`, the pre-order walk building `NodeFacts` and calling
      `hooks.amend_node(node=facts)`, `_apply_overlays`, the gate with the
      merged veto error; add the module-private `_walk_nodes` and
      `_apply_overlays`; imports `from .hooks import CodegraphHooks,
      GateVerdict, NodeFacts`
- [ ] **Code**: update the `codegraph()` docstring — extended purpose
      (amend the surviving nodes, validate the final tree), and `Raises:
      ValueError` (unsupported language; unparseable source; checkpoint hard
      failures naming the tool, the action, and the failing node cell path;
      the merged veto error listing every violation) and `ImportError`
      (register-facade import failure naming the package)
- [ ] **Code**: adapt `tests/integration/test_codegraph_cli_integration.py` —
      add the autouse `_empty_package_environment` fixture (the
      `test_schema_walk_gate_integration.py` pattern; the suite's planted
      projects are non-empty and the routine now delivers)
- [ ] **Interface verification**: the contract test above passes;
      `pytest tests/codegraph/test_codegraph.py -x` stays green (the
      pre-existing behavior — golden output, failures, lint-ignore, empty
      project, read-only — unchanged)
- [ ] **Logic tests (positive)** — transfer the design scenarios verbatim:
      `test_codegraph_delivers_every_surviving_node_in_tree_order_with_complete_children`
      (plant a nested project — root `CWD` with `.goga/config.yml`, packages
      `lib` (declared+coded) and `lib/inner` (declared+coded); environment
      with a tool recording `context.node.cell` and `context.node.children`
      on `amend_node`; `codegraph(["lib"], None, [])` → the recorder cells
      `== ["lib"]`; the recorded children `== ["lib/inner"]` — a pruned cell
      named in the facts, identical in every run; the returned tree nodes
      have `tools == {}` — the recorder contributed nothing);
      `test_codegraph_places_overlays_and_returns_the_gated_tree` (the
      planted project; a tool contributing `{"coverage": 3}` on every node;
      no gate subscriptions; `codegraph([], None, [])` → every node's
      `tools == {"<tool>": {"coverage": 3}}`; node fields otherwise
      unchanged)
- [ ] **Logic tests (negative)**:
      `test_codegraph_vetoed_gate_raises_one_merged_error_and_returns_no_tree`
      (planted project; a gate tool vetoing `"shape broken"`; an
      `amend_node` contributor also installed — to prove the tree was
      assembled first; `pytest.raises(ValueError)` around
      `codegraph([], None, [])` →
      `match=r"codegraph validation failed:"` and
      `"- tool gate / hook vetoer: shape broken" in str(excinfo.value)`);
      `test_codegraph_hard_amendment_failure_propagates_from_the_routine`
      (planted project; an `amend_node` hook raising on the first delivered
      node → `pytest.raises(ValueError, match=r"failed on
      codegraph\.amend_node at ")` — the failing node cell path present)
- [ ] **Logic tests (edge)**:
      `test_codegraph_empty_project_returns_empty_before_any_checkpoint`
      (`.goga/config.yml` planted, no packages; an observer tool subscribing
      to both actions recording every call; `codegraph([], None, [])` →
      result `== []`; the observer recorded nothing — no enumeration side
      effects observable through delivery)
- [ ] **Debugging**: `pytest tests/codegraph tests/integration/test_codegraph_cli_integration.py -x`
      — all pass (fix implementation code, not test code)
- [ ] **Contract re-verification**: `from goga.codegraph import codegraph`
      importable; filters prune delivery exactly as output; every error of
      steps 1–5 still propagates unchanged; no partial tree on gate veto
- [ ] Lint: `ruff check goga/codegraph tests/codegraph` and
      `ruff format --check` over the same paths — fix formatting, apply
      decomposition if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 13: The `drift` routine — moments, amendments, and the failure paths; `DriftEntry.tools` (TDD coding)

Two files of the `goga/drift` cell: `compare.py` gains the `DriftEntry.tools`
field (the Task 3 mirror — default `{}`, the comparison never populates it,
`__post_init__` unchanged), and `drift.py` becomes the moments-and-amendments
orchestrator. The routine verbatim from the design:

```
def drift(cells, max_depth, depends_on):
    hooks = DriftHooks()
    hooks.emit_run_started(DriftFilters(cells=cells, max_depth=max_depth, depends_on=depends_on))
    carried: list[ReportEntry] | None = None
    try:
        complete_schema = schema([], None, [])
        complete_codegraph = codegraph([], None, [])
        filtered_schema = schema(cells, max_depth, depends_on)
        filtered_codegraph = codegraph(cells, max_depth, depends_on)
        entries = compare_views(complete_schema, complete_codegraph)
        scoped = scope_entries(entries, filtered_schema, filtered_codegraph)
        carried = [ReportEntry(kind=e.kind, cell=e.cell, types=e.types, tools={}) for e in scoped]
        settled = hooks.amend_report([EntryFacts(kind=e.kind, cell=e.cell, types=e.types) for e in scoped])
        final: list[DriftEntry] = []
        for facts in settled:
            tools = hooks.amend_entry(facts)
            final.append(DriftEntry(kind=facts.kind, cell=facts.cell, types=facts.types, tools=tools))
        carried = [ReportEntry(kind=e.kind, cell=e.cell, types=e.types, tools=e.tools) for e in final]
        hooks.emit_run_completed(RunCompletion(report=carried, outcome=RunOutcome.finished, reason=""))
        return final
    except Exception as reason:
        hooks.emit_run_completed(RunCompletion(report=carried, outcome=RunOutcome.crashed, reason=str(reason)))
        raise
```

Implementation notes (mandatory, from the design's Additional Instructions):
the start moment fires BEFORE the failure wrap — a register-facade `ImportError`
there propagates without any completion moment (the run never started);
`carried` is set to the scoped pre-amendment projection BEFORE
`amend_report` and replaced by the final projection ONLY after the entry loop
completes — a step-5 failure carries the scoped stage, never a half-enriched
list; `reason=str(reason)` — do not invent a scrubber; the producers'
clean-error convention is the credential guarantee; never catch
`BaseException`. Docstring: `Raises` gains the drift amendment hard failures,
the in-run codegraph veto / hard checkpoint failures, the register-facade
`ImportError`; `Returns` documents the settled post-amendment list.

**Usages relevant to this task:**
- `checkpoints` (from Imports, `goga/drift/hooks`): the moments/failure-path
  wrap recipes and the two amendment loops; its snippets are the reference of
  the routine steps.
- `schema-usage` (from Imports, `goga/schema`) and `codegraph-usage` (from
  Imports, `goga/codegraph`): the producer contracts of the four view calls —
  their checkpoint behavior (schema checkpoints existing; codegraph
  checkpoints from Task 12) is the established platform behavior inside the
  run.
- `convention`: routine tests plant projects via the `tests/drift/conftest.py`
  helpers (`_plant_four_kinds`, `_plant_healthy_plus`) under the autouse
  empty-environment pin of that conftest; tests that install tools pin their
  own environment on top.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/drift/test_compare.py` (extended): the
      `DriftEntry` field set gains exactly `tools` with the default `{}` (the
      Task 3 mirror). In `tests/drift/test_drift.py` (extended): over
      `_plant_four_kinds` with a subscribing-but-silent tool (pinned
      environment) `drift([], None, [])` still returns the four-kinds report
      with every `tools == {}` (the existing expectations of
      `test_drift_reports_planted_discrepancies_all_four_kinds` unchanged)
      (expected to fail — no moments/amendments exist yet)
- [ ] **REPL probe**: plant `_plant_four_kinds` in a scratch `tmp_path`, `cd`
      there, and run the live `drift([], None, [])` in the REPL — confirm the
      scoped report entry for entry (the four kinds) and that every
      `DriftEntry.tools == {}`; then plant `_plant_healthy_plus` and confirm
      the empty scoped list. Grounds the routine assertions below.
- [ ] **Code**: in `goga/drift/compare.py`, add the `tools` field to
      `DriftEntry` after `types` with `field(default_factory=dict)`, the
      Attributes docstring line, and `__post_init__` unchanged
- [ ] **Code**: rewrite `drift()` in `goga/drift/drift.py` per the algorithm
      above; imports `from .hooks import DriftFilters, DriftHooks, EntryFacts,
      ReportEntry, RunCompletion, RunOutcome` (plus the existing
      `from ..codegraph import codegraph`, `from ..schema import schema`,
      `from .compare import DriftEntry, compare_views, scope_entries`)
- [ ] **Code**: update the `drift()` docstring — extended purpose (observed
      and adjusted by the installed tool packages), `Returns` (the final
      post-amendment list), and `Raises` (drift amendment hard failures
      naming hook/tool/action/reason; in-run codegraph veto / hard checkpoint
      failure; register-facade `ImportError`)
- [ ] **Interface verification**: the contract tests above pass;
      `pytest tests/drift/test_drift.py tests/drift/test_compare.py -x` stays
      green (the pre-existing report/failure behavior unchanged — the moments
      and amendments are unobservable without subscriptions)
- [ ] **Logic tests (positive)** — transfer the design scenarios verbatim:
      `test_drift_runs_the_full_checkpoint_order` (`_plant_four_kinds`; a
      tool subscribing to all four drift actions recording
      `(action, subject)` per call and adjusting nothing;
      `drift([], None, [])` → the recorded order starts with `run_started`,
      ends with `run_completed`; `amend_report` precedes every
      `amend_entry`; the count of `amend_entry` deliveries equals the settled
      report length; the returned report equals the scoped four-kinds
      report);
      `test_drift_completion_carries_the_final_report_on_finished_runs`
      (`_plant_four_kinds`; a tool recording `context.completion.report` as
      `(kind, cell)` tuples and contributing `{"ticket": "GOGA-9"}` on
      `amend_entry`; `drift([], None, [])` → the recorded completion stage
      equals the returned report projected `(kind, cell)`; every returned
      `DriftEntry.tools == {"<tool>": {"ticket": "GOGA-9"}}`; outcome
      `RunOutcome.finished`; reason `""`)
- [ ] **Logic tests (negative)**:
      `test_drift_producer_failure_emits_crashed_completion_and_reraises`
      (no `.goga/config.yml` planted — the `tmp_path` CWD is empty; a moment
      observer recording the completion payload;
      `pytest.raises(FileNotFoundError)` around `drift([], None, [])` → the
      recorder saw `(None, "crashed", reason-containing-".goga/config.yml")`
      — `report is None`; the original exception type propagates);
      `test_drift_amendment_failure_carries_the_scoped_pre_amendment_stage`
      (two scenarios over `_plant_four_kinds`: S1 — an `amend_report` hook
      raising; S2 — an `amend_entry` hook raising; a completion observer
      records the carried stage; `pytest.raises(ValueError)` → the recorded
      stage equals the scoped `(kind, cell)` projection with every
      `tools == {}`; outcome `crashed`; the raise matches the checkpoint
      error)
- [ ] **Logic tests (edge)**:
      `test_amend_report_empty_scoped_list_still_delivers`
      (`_plant_healthy_plus` — agreeing views → empty scoped report; a tool
      adjusting to one added entry; `drift([], None, [])` → the returned
      report has exactly the adjusted entry; an `amend_entry` delivery was
      recorded for it);
      `test_amend_entry_empty_settled_list_fires_nothing` (a clean project;
      an `amend_entry` observer; `drift([], None, [])` — scoped `[]`, no
      adjusters → no `amend_entry` delivery recorded);
      `test_drift_start_moment_import_failure_propagates_without_completion`
      (`pin_package_environment({"goga_tool_broken": ["broken-dist"]})` + a
      genuinely broken package: a `goga_tool_broken/` directory under
      `tmp_path` whose `__init__.py` imports a missing dependency, put on
      the path via `syspath_prepend` — the
      `test_build_once_broken_import_is_fatal_through_the_real_import`
      precedent in `tests/hooks/registry/test_state.py`; `install_tool_package`
      cannot produce this case — a facade without `register_hooks` is the
      documented quiet skip and a raising callback is downgraded to a
      warning; the failing import makes the platform raise the fatal
      `ImportError("package goga_tool_broken failed to import: ...")`, which
      the start moment propagates before the failure wrap begins; on a
      planted project `pytest.raises(ImportError)` around `drift([], None,
      [])` → the `ImportError` raised (message names the package); no
      completion recorded by any observer — none could register);
      `test_drift_determinism_with_tools_installed` (planted project; a
      contributing tool with deterministic facts; `drift([], None, [])`
      twice on fresh surfaces → the two reports equal, including the `tools`
      mappings); the drift half of
      `test_codegraph_node_and_drift_entry_carry_the_tools_default`
      (`DriftEntry(kind="schema_only", cell="a").tools == {}`; the record
      stays frozen)
- [ ] **Debugging**: `pytest tests/drift -x` — all pass
- [ ] **Contract re-verification**: `from goga.drift import drift,
      DriftEntry` importable; the facade `__all__` unchanged; run ordering
      fixed; every producer error propagates unchanged (the completion never
      masks a failure)
- [ ] Lint: `ruff check goga/drift tests/drift` and `ruff format --check`
      over the same paths — fix formatting, apply decomposition if necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 14: CLI `codegraph` — the `_project_node` projection and extended help (TDD coding)

Replace the `asdict` serialization in `goga/commands/codegraph/codegraph.py`
with the projection serializer (the schema-command reference) and extend the
help. The projection verbatim from the design:

```python
def _project_node(node: CodegraphNode) -> dict:
    """Project one read-only codegraph node onto the family JSON output shape."""
    projected = {
        "cell": node.cell,
        "types": list(node.types),
        "dependencies": {path: list(types) for path, types in node.dependencies.items()},
        "children": [_project_node(child) for child in node.children],
    }
    if node.tools:
        projected["tools"] = node.tools
    return projected
```

Serialized via `json.dumps([_project_node(n) for n in result], indent=4,
sort_keys=True, ensure_ascii=False)`; the `asdict` import leaves the module.
The current `asdict` path would print `"tools": {}` on every node the moment
the field exists — this task removes that channel in the same session (the
golden net must stay green untouched). The click surface and the
`except Exception` → stderr + `ctx.exit(1)` envelope are unchanged.

**Usages relevant to this task:**
- `click` (from Usages): unchanged decorators; `click.echo(result)` for
  stdout; `click.echo(str(e), err=True)` + `ctx.exit(1)` for failures;
  CliRunner drives the command in tests (the `_run_codegraph` helper).
- `beautiful_json` (from Usages): `json.dumps(..., indent=4, sort_keys=True,
  ensure_ascii=False)`.
- `codegraph-usage` (from Imports, `goga/codegraph`) and `registering-hooks`
  (from Imports, `goga/codegraph`): the output and failure contract — the
  conditional `tools` row, the extended exit-1 causes (amendment hard
  failure, vetoed gate, register-facade import failure), the byte-identical
  no-subscription statement; the tool-author surface behind the checkpoints.
- `checkpoints` (from Imports, `goga/codegraph/hooks`): every checkpoint
  failure surfaces as a clean command failure — exit 1, nothing on stdout.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/commands/codegraph/test_codegraph.py`
      (extended): over the golden-tree fixture with a contributing tool
      (pinned environment) `runner.invoke(app, ["codegraph"])` → exit 0;
      the parsed JSON round-trips; only contributed nodes carry
      `"tools": {"<tool>": {...}}`; `"tools" not in` every uncontributed
      node; `indent=4` / `sort_keys` preserved (expected to fail — the
      `asdict` path prints `"tools": {}` everywhere)
- [ ] **REPL probe**: in the virtualenv REPL, run the live command twice over
      the golden fixture — once with the environment pinned empty, once with
      a silent subscribed tool (reads `context.node.cell`, contributes
      nothing) — and diff the two stdout documents byte for byte in the REPL
      (they must be equal; no `"tools"` substring). Grounds the byte-identity
      test below.
- [ ] **Code**: add the module-level private `_project_node` (verbatim above,
      full Google docstring) to `goga/commands/codegraph/codegraph.py`;
      replace the `click.echo(json.dumps([asdict(n) for n in result], …))`
      line with `click.echo(json.dumps([_project_node(n) for n in result],
      indent=4, sort_keys=True, ensure_ascii=False))`; drop the `asdict`
      import
- [ ] **Code**: extend the command docstring's `\b` JSON structure block —
      after `children` add the `tools` line ("tool contributions of the
      node-amendment checkpoint, present iff at least one tool wrote at
      least one fact") and a failure note ("a failing or vetoing hook stops
      the run as a clean error before any output"), mirroring the schema
      command help
- [ ] **Interface verification**: the contract test above passes;
      `pytest tests/commands/codegraph -x` stays green — critically
      `TestCodegraphCliByteIdentity` passes UNTOUCHED (the projection is
      byte-identical to the pre-extension `asdict` output when every overlay
      is empty; a golden mismatch is a defect in the projection, never a
      reason to adjust a golden)
- [ ] **Logic tests (positive)** — transfer the design scenario verbatim:
      `test_codegraph_command_writes_the_conditional_tools_key`
      (environment A empty; environment B with a contributing tool;
      `runner.invoke(app, ["codegraph"])` under both → A: `"tools" not in`
      the JSON for every node AND the output equals the pre-extension golden
      bytes; B: only contributed nodes carry the key; the JSON round-trips;
      indent=4, sort_keys)
- [ ] **Logic tests (negative)**:
      `test_codegraph_command_exit_1_with_clean_stderr_on_checkpoint_failure`
      (planted project; a vetoing gate tool; `runner.invoke(app,
      ["codegraph"])` → `result.exit_code == 1`; stdout empty; the merged
      error text on stderr; no `"Traceback"` in the output)
- [ ] **Logic tests (edge)**:
      `test_codegraph_no_subscriptions_output_is_byte_identical` (the
      `_plant_healthy_plus`-style planted project; run A with the
      environment pinned empty, run B with a subscribed-but-silent tool; the
      two CLI outputs byte-identical; no `"tools"` substring anywhere)
- [ ] **Debugging**: `pytest tests/commands/codegraph -x` — all pass
- [ ] **Contract re-verification**: stdout carries the JSON document only;
      exit 0 only on a complete generation; `--help` documents the
      conditional `tools` key and the checkpoint failure semantics
- [ ] Lint: `ruff check goga/commands/codegraph tests/commands/codegraph`
      and `ruff format --check` over the same paths — fix formatting if
      necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 15: CLI `drift` — conditional `tools` key, post-amendment grading, help (TDD coding)

Extend `goga/commands/drift/drift.py`: `_project_entry` gains the conditional
`tools` key and the help documents the post-amendment grading and the
amendment failure semantics. The grading stays `ctx.exit(1) if report else
ctx.exit(0)` — the returned list is already post-amendment (Task 13); facts
areas never affect the grading. The `except Exception` → stderr +
`ctx.exit(2)` envelope is unchanged — its cause list is now realized by the
drift amendments and the in-run codegraph checkpoints.

**Usages relevant to this task:**
- `click` (from Usages) and `beautiful_json` (from Usages): the family
  serialization and echo rules (unchanged).
- `drift-usage` (from Imports, `goga/drift`) and `registering-hooks` (from
  Imports, `goga/drift`): the report and failure contract — the post-amendment
  exit codes, the conditional `tools` row, the extended exit-2 causes, the
  no-provenance statement; the tool-author surface behind the run's
  checkpoints.
- `checkpoints` (from Imports, `goga/drift/hooks`): every hard checkpoint
  failure surfaces as a clean command failure (exit 2); soft moment failures
  surface as stderr warnings only.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests**: in `tests/commands/drift/test_drift.py` (extended):
      over `_plant_four_kinds` with a contributing tool (pinned environment)
      `runner.invoke(app, ["drift"])` → exit 1; every parsed entry carries
      `"tools": {"<tool>": {...}}`; the kind/cell/types fields unchanged
      (expected to fail — `_project_entry` never writes `tools`)
- [ ] **REPL probe**: in the virtualenv REPL, drive a scratch CliRunner
      invocation over `_plant_four_kinds` with a tool adjusting `[]` —
      observe `result.exit_code == 0` and the printed `[]`; then with a tool
      adding one entry over `_plant_healthy_plus` — observe exit 1 and the
      printed adjusted entry. Confirms the grading is decided by the final
      post-amendment list alone.
- [ ] **Code**: in `_project_entry`, add `if entry.tools:
      projected["tools"] = entry.tools` before the return (the family
      conditional-key pattern)
- [ ] **Code**: extend the command docstring — the JSON report block gains
      the `tools` line ("present iff at least one tool contributed; never
      affects the exit code"); the Exit codes block documents the
      post-amendment grading ("decided by the final post-amendment entry
      list alone — a cleared report grades 0, a tool-added entry grades 1")
      and the amendment failure note under exit 2 (drift amendment hard
      failures naming hook/tool/action/reason; in-run codegraph veto or hard
      checkpoint failure; register-facade import failure)
- [ ] **Interface verification**: the contract test above passes;
      `pytest tests/commands/drift -x` stays green (the existing report,
      agreement, uninitialized, AST-error, and repeated-runs tests unchanged
      — byte-identical without subscriptions)
- [ ] **Logic tests (positive)** — transfer the design scenario verbatim:
      `test_drift_command_grades_the_post_amendment_list` (scenario A over
      `_plant_four_kinds`: a tool adjusting `[]` → `result.exit_code == 0`
      and `json.loads(result.output) == []`; scenario B on a fresh
      environment over `_plant_healthy_plus`: a tool adjusting to add one
      entry → `result.exit_code == 1`, one entry with the adjusted
      kind/cell)
- [ ] **Logic tests (negative)**:
      `test_drift_command_exit_2_on_amendment_failure` (`_plant_four_kinds`;
      an `amend_report` hook raising; `runner.invoke(app, ["drift"])` →
      `result.exit_code == 2`; stdout empty; stderr names
      hook/tool/action/reason)
- [ ] **Logic tests (edge)**:
      `test_drift_in_run_codegraph_veto_surfaces_as_exit_2`
      (`_plant_four_kinds`; a codegraph gate tool vetoing;
      `runner.invoke(app, ["drift"])` → the drift failure path (completion
      `crashed`, stage `None`) → re-raise → `result.exit_code == 2`; stdout
      empty; stderr contains `codegraph validation failed`)
- [ ] **Debugging**: `pytest tests/commands/drift -x` — all pass
- [ ] **Contract re-verification**: stdout carries the JSON report only;
      exit 0/1/2 exactly per the three-outcome contract; no adjustment
      provenance anywhere in the output; `--help` documents the conditional
      `tools` key and the completion statuses
- [ ] Lint: `ruff check goga/commands/drift tests/commands/drift` and
      `ruff format --check` over the same paths — fix formatting if
      necessary
- [ ] **Commit gate**: full `pytest tests/ -x` green; commit only with all gates
      green and no `Co-Authored-By:` trailers

### Task 16: Integration tests — the full checkpoint family; final verification battery (integration tests)

The cross-cell end-to-end scenarios of the extension: routine and CLI agree on
the extended tree/report, the base fields stay identical with and without tool
contributions, and the local usage files match the landed implementation. This
task adds no production code; it pins the topic's end-to-end guarantees and
runs the full validation battery (the design's Additional Instructions:
re-run `goga lint`, `goga schema` — both zones present, no cycles — and the
full test suite).

**Usages relevant to this task:**
- `checkpoints` (from both zones): the output shape —
  `tools -> {tool identity -> {fact -> value}}`; base fields and extensions
  stay structurally separated; with no subscriptions the output is
  byte-identical to the run without the extension.
- `convention`: integration scenarios live in their mirrored suites (the
  planted-project runs and the CliRunner runs); test naming and the
  `tmp_path` style.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create the routine↔CLI agreement test in
      `tests/commands/codegraph/test_codegraph.py` (it already imports the
      CliRunner and the app; add `from goga.codegraph import codegraph as
      codegraph_logic`): over the golden-tree fixture with the contributing
      scratch tool, the direct `codegraph([], None, [])` call and the
      `_run_codegraph()` invocation produce identical parsed trees (both
      carry the same `tools == {"<tool>": {"score": 3}}` overlays); a second
      run of the same project with the environment pinned empty yields nodes
      whose base fields (`cell`/`types`/`dependencies`/`children`) are
      identical to the tooled run and carry no `tools` key
- [ ] Create the routine↔CLI agreement test in
      `tests/commands/drift/test_drift.py`: over `_plant_four_kinds` with a
      contributing tool, the direct `drift([], None, [])` call and
      `_run_drift()` agree entry for entry (kind/cell/types and the `tools`
      overlays); the exit code follows the returned list's emptiness
- [ ] Test edge case: determinism across the whole family — repeated
      `drift([], None, [])` runs with tools installed produce identical
      reports (the domain half landed in Task 13; here assert the CLI echo
      of two fresh invocations is byte-identical, `sort_keys` included)
- [ ] Verify the local usage files are consistent with the landed
      implementation: `goga/codegraph/hooks/.usages/checkpoints.md`,
      `goga/drift/hooks/.usages/checkpoints.md`,
      `goga/codegraph/.usages/registering-hooks.md`,
      `goga/drift/.usages/registering-hooks.md`,
      `goga/codegraph/.usages/codegraph-usage.md`,
      `goga/drift/.usages/drift-usage.md`,
      `goga/codegraph/facts/.usages/records.md`,
      `goga/commands/codegraph/.usages/codegraph.md`,
      `goga/commands/drift/.usages/drift.md` exist and their names, loop
      shapes, failure naming, and output shapes match the landed code
      (documentation-only check; fix nothing in CODEMANIFEST; a
      documentation mismatch is reported, not silently patched)
- [ ] Run the targeted battery: `pytest tests/hooks/catalog
      tests/codegraph tests/drift tests/commands/codegraph
      tests/commands/drift tests/integration/test_codegraph_cli_integration.py
      -x`
- [ ] Run the full suite: `pytest tests/ -x`
- [ ] Run validation: `goga lint` — 91 cells, 0 errors (a sporadic
      external-URL network probe in unrelated `goga/ast/factory` may fail
      once; re-run)
- [ ] Run validation: `goga schema` — both zones present
      (`goga/codegraph/hooks`, `goga/drift/hooks`), the `RunOutcome` import
      edge registered, no cycles
- [ ] Run facade checks: `python -c "from goga.codegraph.hooks import
      CodegraphHooks, GateVerdict, GraphValidation, NodeAmendment, NodeFacts,
      ToolContribution, Violation, merge_node_contributions"` and
      `python -c "from goga.drift.hooks import DriftFilters, DriftHooks,
      EntryAmendment, EntryFacts, ReportAmendment, ReportEntry,
      RunCompletion, RunOutcome, ToolContribution,
      merge_entry_contributions"`
- [ ] Run the repo-level byte-identity check: from the repository root,
      `goga codegraph` output contains no `"tools"` key anywhere and
      `goga drift` output and exit codes are unchanged (no `goga_tool_*`
      packages installed here — combined with the Tasks 14–15 byte-identity
      tests this proves byte-identity for real consumers)
- [ ] **Commit gate**: all gates green; commit only without `Co-Authored-By:`
      trailers

---

## Validation Commands

- `pytest tests/ -x`: run all tests (the full battery)
- `pytest tests/hooks/catalog tests/codegraph tests/drift
  tests/commands/codegraph tests/commands/drift
  tests/integration/test_codegraph_cli_integration.py -x`: the topic's
  targeted battery (catalog records, both zones, both domains, both commands)
- `ruff check goga/ tests/`: lint — zero violations (CI gate)
- `ruff format --check goga/ tests/`: formatting — zero reformattings (CI
  gate; run `ruff format goga/ tests/` on diffs)
- `goga lint`: cell-level lint — 91 cells, 0 errors
- `goga schema`: both zones present, the `RunOutcome` import edge registered,
  no cycles
- `python -c "from goga.codegraph.hooks import CodegraphHooks, GateVerdict,
  GraphValidation, NodeAmendment, NodeFacts, ToolContribution, Violation,
  merge_node_contributions"`: codegraph zone facade check — all eight names
  importable
- `python -c "from goga.drift.hooks import DriftFilters, DriftHooks,
  EntryAmendment, EntryFacts, ReportAmendment, ReportEntry, RunCompletion,
  RunOutcome, ToolContribution, merge_entry_contributions"`: drift zone
  facade check — all ten names importable
- `goga codegraph` and `goga drift` from the repository root: no `"tools"`
  key in the output, exit codes unchanged (byte-identity for real consumers)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
  (`catalog.py`, `goga/codegraph/facts/facts.py`, the codegraph zone's
  `facts.py`/`amendments.py`/`contexts.py`/`overlay.py`/`events.py`, the
  drift zone's `facts.py`/`amendments.py`/`overlay.py`/`events.py`,
  `goga/codegraph/codegraph.py`, `goga/drift/{compare,drift}.py`,
  `goga/commands/codegraph/codegraph.py`,
  `goga/commands/drift/drift.py`)
- [ ] Every contract entity is accessible from the facade
  (`goga.codegraph.hooks` exposes the eight names; `goga.drift.hooks` exposes
  the ten names; every existing facade unchanged)
- [ ] Properties and methods match the declared API
- [ ] Descriptions are reflected in behavior (mutual blindness, fresh views
  per tool, tool-granular commit, key-wise merge, the ownership cut, the
  whole-list replacement semantics, the closed adjustment shape, the
  walk-to-completion gate, the pinned failure formats, the fixed run
  ordering, the carried-stage rule, byte-identity)
- [ ] Contract dependencies are met (the `goga.hooks` platform primitives;
  zone-internal imports; `RunOutcome` imported by the drift domain)
- [ ] Re-exports are accessible from the facade (both zone `__all__` lists
  exact)
- [ ] Every coding task followed the TDD workflow (contract tests → REPL
  probe → code → verification → logic tests → debugging → re-verification →
  lint/format → commit gate)
- [ ] Contract tests and logic tests cover facade, API, and behavior within
  each coding task (all 46 design test scenarios landed: 21 positive, 12
  negative, 13 edge)
- [ ] Integration tests exist where cross-entity scenarios require them
  (Task 16 + the planted-project and CliRunner scenarios of Tasks 12–15)
- [ ] No package boundary was expanded (no new cells beyond the contract's
  two zones; `render_graph`, `compare_views`, `scope_entries`, the analysis
  stages, and the platform cells untouched)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (full battery, ruff check, ruff format,
  `goga lint` 91 cells / 0 errors, `goga schema` both zones / no cycles, both
  facade checks, repo-level byte-identity)
- [ ] Every Usages entry is mentioned in at least one task (`convention`,
  `click`, `beautiful_json`, `per-tool-delivery`, `registering-hooks`,
  `declaring-actions`, `checkpoints` ×2, `codegraph-usage`, `drift-usage`,
  `records`, `stages`, `project-configuration`, `schema-usage`)
