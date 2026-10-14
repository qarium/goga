# Plan: `drift-command`

<!-- Topic: `drift-command` — the `goga drift` command: declared-vs-code structural drift
     visibility, built on the object-returning refactor of the two view domains.
     Source: `.goga/history/2026/drift-command/design.md` (design-review completed — 3 fixes
     applied; see its "Applied Fixes" and the review execution summary). This plan compiles
     the design into ralphex-executable tasks. -->

## Purpose

Implement the `drift-command` feature end-to-end: the `goga drift` CLI command reporting
structural drift between declared contracts (`goga schema`) and actual code
(`goga codegraph`), built on the object-returning refactor of the two view domains.

After implementation the project provides:

- `goga.schema` — `schema()` returns the assembled `list[SchemaNode]` tree (was: JSON
  string); serialization moves to the caller;
- `goga.codegraph` — `codegraph()` and `render_graph()` return `list[CodegraphNode]`
  (was: JSON string);
- `goga.commands.schema` / `goga.commands.codegraph` — the wrappers take over projection
  and serialization, byte-identical to the pre-refactor CLI output (C2);
- `goga.drift` — the new comparison cell: `DriftEntry`, `compare_views`, `scope_entries`,
  and the `drift()` routine (complete-view comparison + union-survival scoping);
- `goga.commands.drift` — the CLI wrapper with the three-outcome exit contract 0/1/2,
  re-exported through `goga.commands` and registered in `goga/cli.py` after `codegraph`;
- documentation collateral `docs/features/drift/`.

The most important gaps between contract and code: the two view domains still return JSON
strings (`json.dumps` tails live in `goga/schema/schema.py` and
`goga/codegraph/render.py`); the two wrappers echo the domain string directly; the drift
cells have CODEMANIFEST + `.usages/` files but **zero implementation files**; the facade
and root registration wiring is absent; six existing test suites pin the JSON-string
domain return and break the moment it changes.

Strategy: goldens first (the byte-identity net is captured from the **live** CLI before
any domain is touched), then leaves-first TDD — schema domain+wrapper → codegraph
domain+wrapper → drift cell → drift CLI+registration → docs → full-stack gates. Every
task is gated by the Mandatory Rules below.

## Mandatory Rules

<!-- Extracted verbatim from the project convention `.goga/usages/conventions.md`
     (the `convention` practice wired into every cell of this feature — for working with
     the codebase, organizing the REPL development cycle, debugging and testing, and the
     test infrastructure), the language rules (`goga-cell-python`), the ruff configuration
     (`pyproject.toml`), and the repo gates (`.github/workflows/lint.yml`, `.githooks/`).
     These rules are MANDATORY for every task in this plan. Where a task restates a rule,
     the restatement is a reminder, not a replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`.
- **Imports**: relative imports for ALL intra-package references inside `goga/`
  (`from ..schema import schema`, `from ...drift import DriftEntry`); absolute imports
  only for stdlib and third-party. Exception — tests: cross-directory references inside
  `tests/` use absolute imports rooted at the `tests` package
  (`from tests.conftest import helper`).
- **Data models**: stdlib `dataclasses` only; model classes use `kw_only=True` and, for
  records, `frozen=True`; empty defaults for all fields (`""`, `False`, `[]`/`{}` via
  `default_factory`); `None` only for fields that represent the explicit absence of a
  value (`DriftEntry.types=None` is the recorded cell-level absence).
- **Docstrings**: Google style, MANDATORY for every public function, method, and class.
  First line starts with a capital letter and ends with a period. Include `Args` when the
  function accepts parameters, `Returns` when it returns a value, `Raises` when it raises
  beyond built-in types.
- **CLI command docstrings** (click callbacks): user-facing help rendered verbatim by
  `--help` — omit `Args`, `Returns`, `Raises` (Click auto-generates the options block;
  exit codes are Click's; internal exception types stay hidden); keep the concise summary
  line (Click lists it); use `\b` blocks to preserve paragraph formatting in help; use
  the `\f` marker to hide developer-facing notes from `--help`. Google-style docstrings
  still apply unchanged to every OTHER public function in a command module (helpers,
  projectors, logic functions).
- **Code formatting**: inside function and method bodies, separate logical blocks by ONE
  blank line (initialization / conditions and loops / data preparation / processing /
  return).
- **Type hints**: mandatory everywhere (drives facade signature extraction). Allowed
  shapes: `str`, `int`, `float`, `bool`, `list[T]`, `dict[str, T]`, `T | None`.
  Forbidden: `*args`, `**kwargs`, bare `dict`, bare `list`. Mutable contract defaults
  (`cells=[], depends_on=[]`) carry `# noqa: B006` with the family comment (the
  CODEMANIFEST contract default; never mutated) — mirror `codegraph()`.
- **Naming**: PascalCase classes, snake_case functions/methods/properties/modules.
- **Facade**: each cell's `__init__.py` exposes the contract API via `__all__`; only
  identifiers in `__all__` constitute the facade. **Never place a cross-unit import in a
  test fixture package `__init__.py`** — an imported name becomes a public binding, leaks
  into the unit facade, and fabricates a `codegraph_only` entry (verified live by the
  design review; put cross-unit imports in a sibling module such as `mix/impl.py`).
- **Dependencies**: no new third-party dependencies in this feature — `click`, `pyyaml`,
  `tree-sitter*` are already pinned in `pyproject.toml`; any hypothetical new library MUST
  go into `pyproject.toml` with a minimum version.
- **Logging**: none is added anywhere in this feature — the family is silent on
  stdout-data paths and speaks only through stderr diagnostics.

### Test Writing Rules (strictly per `conventions.md` — Testing)

- **Tools**: pytest (runner), ruff (lint + format of test code), pytest-cov (coverage).
  Test libraries live in `pyproject.toml` `[project.optional-dependencies]` under `test`.
- **Structure mirrors source directly**:
  `goga/drift/compare.py` → `tests/drift/test_compare.py`;
  `goga/commands/drift/drift.py` → `tests/commands/drift/test_drift.py`. Every test
  directory MUST contain an `__init__.py`.
- **Fixtures**: local fixtures in `tests/<package>/conftest.py`, shared fixtures in
  `tests/conftest.py`. Available shared infrastructure: the `cwd` CWD-pinning fixture of
  `tests/conftest.py`; `pin_package_environment` / `empty_package_environment` of the
  hooks platform tests — every module testing `schema()` (including `tests/drift/*`) uses
  the autouse `_empty_package_environment` pattern of `tests/schema/test_schema.py`;
  `empty_package_environment` of `tests/commands/conftest.py` for CliRunner tests.
  Planted projects live in `tmp_path` and carry `.goga/config.yml` with `language:
  python`; `_write_codemanifest` of `tests/schema/conftest.py` is reused or mirrored
  locally in `tests/drift/conftest.py`.
- **Integration tests** covering multiple packages go to `tests/integration/`
  (`test_<scenario>.py`). The CLI-stdout integration suites
  (`test_codegraph_cli_integration.py`, and the stdout-pinned tests of
  `test_integration_split.py`) need **no changes** — the CLI output is byte-identical
  by construction (C2). Exception: the three `schema_logic`-mocked tests of
  `test_integration_split.py` (lines 63, 75, 274) pin the JSON-string domain return
  through their mock values and are adapted in Task 2.
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`
  (e.g. `test_compare_views_with_agreeing_views`); grouping `class Test<Component>:`
  with docstrings; self-documenting test names; keep comments minimal.
- **Test types**: Unit — every public function/method/class, main scenario and typical
  data. Edge cases — empty inputs (`None`, `""`, `[]`, `{}`), boundary values (`0`,
  negative, very large), invalid types, expected exceptions via `pytest.raises`.
  Integration — only for interaction between modules/packages (the planted-project drift
  runs and the CliRunner runs are the integration scenarios of this feature and live in
  their mirrored suites per the design registry).
- **Boundary tests**: for thresholds, ranges, state transitions use
  `@pytest.mark.parametrize` with a table of values including each boundary
  (`max_depth=0` is the pinned depth boundary).
- **Mocks**: pure logic — NO mocks (`compare_views`/`scope_entries` suites are mock-free
  record tests); file I/O — the `tmp_path` fixture exclusively; external dependencies —
  `mock.patch` at the import point. Mock only at external boundaries; business-logic
  tests stay mock-free.
- **CLI testing**: invoke the command through the registered `app` via `click.testing`
  `CliRunner` (direct Python call — no subprocess), as the existing command tests do.
  click ≥ 8.2 semantics (verified live against the pinned click 8.5.0): `result.output`
  is the **combined** stdout+stderr stream — assert clean-stdout cases on the dedicated
  `result.stdout`, not on `result.output`.
- **Expected values are grounded, never recalled**: every fixture expectation in this
  plan was validated by the design's dry-runs against the live producers; if an
  assertion disagrees with a live run during implementation, the live run wins and the
  disagreement is reported — never silently "aligned".

### Linter and Formatter Enforcement (all development stages and local commits)

The following gates are MANDATORY at the end of EVERY task and BEFORE EVERY local commit,
across all development stages. A failing gate is an actionable defect, never acceptable
noise. Local git hooks do NOT enforce formatting (only the commit-msg/pre-push
Co-Authored-By policy does) — the author runs the formatter deliberately:

1. `ruff check goga/ tests/` — zero violations (CI gate, `.github/workflows/lint.yml`).
2. `ruff format --check goga/ tests/` — zero reformattings; run `ruff format goga/ tests/`
   when it reports diffs. Formatting coverage extends to the Python examples embedded in
   usage documents.
3. `goga lint` — cell-level lint, **0 errors over 89 cells**.
4. Focused tests green, then `pytest tests/ -x` green (the full battery — the string-pinned
   adaptations exist precisely so the battery stays green through the refactor).
5. Facade import checks green
   (`python -c "from goga.drift import drift"`,
   `python -c "from goga.commands import drift"`).
6. **Commit policy**: commit only with all gates green; commit messages MUST NOT contain
   `Co-Authored-By:` trailers (`.githooks/commit-msg` and `pre-push` reject them).
7. `CODEMANIFEST` files are READ-ONLY for the implementer — the contract changes are
   already applied in the working tree; if code does not match the contract, fix the
   code, never the contract.

### REPL Cycle Rules (continuous interactive evaluation, hot reloading, migration to source)

The `convention` practice is wired into every cell of this feature for "Organizing the
REPL development cycle". Every coding task in this plan follows the same loop:

1. **Virtualenv first**: all code executes inside the virtualenv — create it if missing.
   The current `.venv` is BROKEN (its `python` symlinks point to a nonexistent
   `/opt/homebrew/opt/python@3.14` macOS path); Task 1 recreates it
   (`python -m venv .venv --clear` + `pip install -e ".[test]"`) and every subsequent
   probe, test run, and lint run executes inside it.
2. **Probe before writing**: verify each non-trivial behavior interactively against real
   inputs BEFORE the verified snippet is written into a source file. The probes of this
   feature: capture the golden CLI stdout strings from the live pre-refactor CLI (Task 1
   — they are the C2 net); confirm the frozen/kw-only record pattern and the set
   arithmetic of `compare_views` over inline records (Task 4); plant the four-kinds
   project in a scratch `tmp_path` and run the live `schema()`/`codegraph()` producers
   over it to confirm the asserted views entry for entry (Task 5); confirm
   `ctx.exit(2)`/`result.stdout` semantics through a scratch CliRunner invocation
   (Task 6). Expected values in tests are grounded in live probe runs, never in
   recollection.
3. **Hot feedback after every edit**: immediately re-run the focused test file and the
   facade import check in the same virtualenv; iterate in small steps. A long-lived REPL
   session re-imports edited modules (`importlib.reload` or a fresh `python -c`) — never
   trust stale module state as evidence.
4. **Migrate verified code to source files**: REPL-verified snippets are migrated into
   the target `location` file with type hints, Google docstrings, relative imports, and
   convention formatting; REPL scratch never ships and is never referenced by source.
5. **Close the loop per task**: probe → implement (migrate) → focused tests → full
   battery → lint/format gates → commit (gates green).

## Context

### Contract Surface

**Routine: `schema(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> tree: list[SchemaNode]`**
(cell `goga/schema` — CHANGED return)
- Declared `location`: `schema.py`
- Facade obligation: importable from `goga.schema`
- Semantic requirements: generation unchanged — AST load (`ValueError` on AST errors),
  dict-tree build, filters in order `cells` → `depends_on` → `max_depth`,
  empty tree → `return []` **before** any checkpoint delivery, `hooks.amend_cell` per
  surviving cell (tools overlay iff non-empty), then
  `nodes = [_to_schema_node(node) for node in result]`, `hooks.validate_schema(nodes)`
  (not-approved `GateVerdict` → one merged `ValueError`; no tree returned), and
  `return nodes`. The `json.dumps` tail, the `json` import, and the `-> str` annotation
  are deleted; the docstring documents `list[SchemaNode]` and the caller-owns-
  serialization rule. Serialization leaves the cell — the caller owns it.
- Node content fields: `SchemaNode.path`, `.description`, `.types`, `.usages`,
  `.dependencies` (as `DependencyFacts` records), `.children`, `.tools`.
- Imported dependencies: `AST` from `goga/ast`; `SchemaHooks`, `CellFacts`,
  `DependencyFacts`, `SchemaNode`, `GateVerdict` + `checkpoints` usage from
  `goga/schema/hooks`.
- Annotation context: header practice `beautiful_json` deleted; global Annotations carry
  the caller-owns-serialization clause.

**Routine: `codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> tree: list[CodegraphNode]`**
(cell `goga/codegraph` — CHANGED return)
- Declared `location`: `codegraph.py`
- Facade obligation: importable from `goga.codegraph`
- Semantic requirements: orchestration unchanged — `load_project_config()` (absent
  config → `FileNotFoundError(".goga/config.yml not found in project root")`; language
  outside `python/golang/javascript/kotlin/swift` → `ValueError` naming the expected
  set; absent `lint` → no exclusions), `discover_sources`, the three analysis stages,
  `render_graph`; the single `return render_graph(...)` line flows the new type through.
  Docstring/annotations updated to the object contract.
- Imported dependencies: `Unit`, `CellLink`, `CodegraphNode` + `records` usage from
  `goga/codegraph/facts`; `collect_facts`, `derive_units`, `resolve_links` + `stages`
  usage from `goga/codegraph/analysis`; config loader + `project-configuration` usage
  from `goga/config`.

**Routine: `render_graph(units: list[Unit], links: list[CellLink], cells: list[str], max_depth: int | None, depends_on: list[str]) -> tree: list[CodegraphNode]`**
(cell `goga/codegraph` — CHANGED return)
- Declared `location`: `render.py`
- Facade obligation: importable from `goga.codegraph`
- Semantic requirements: `_build_forest` nesting with structural compression, then
  `_filter_cells` → `_filter_by_depends_on` → `_prune_depth`, each rebuilding fresh
  frozen nodes (input records never mutated); **`return roots`** — the
  `if not roots: return "[]"` early exit, `asdict`, and `json.dumps` are deleted (an
  empty forest returns `[]` naturally); the `json`/`asdict` imports leave; the module
  docstring drops the serialization sentence.

**Routine: `schema(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])`**
(cell `goga/commands/schema` — CHANGED: takes over projection + serialization)
- Declared `location`: `schema.py`
- Facade obligation: importable from `goga.commands.schema`, re-exported by
  `goga.commands`
- Semantic requirements: click surface unchanged (`CELLS` variadic,
  `--max-depth` int, repeatable `--depends-on`, `ctx` for exits);
  `schema_logic(list(cells), max_depth, list(depends_on))`; any `Exception` →
  `click.echo(str(e), err=True)` + `ctx.exit(1)`; **new step 3** — project the returned
  tree via the module-level private `_project_node` (`path → "cell"`, `description`,
  `types`, `usages`, `dependencies` → `{record.path: {"types": [...], "usages": [...]}}`
  over the `DependencyFacts` records, `children` recursively, `"tools"` only when the
  overlay is non-empty); **step 4** — serialize via `beautiful_json` and `click.echo`.
  Byte-identical to the pre-refactor CLI output (C2), including `"[]"` for the empty
  tree; the help docstring is unchanged.
- Imported dependencies: `schema AS schema_logic` + `registering-hooks` usage from
  `goga/schema`; `SchemaNode`, `DependencyFacts` + `checkpoints` usage from
  `goga/schema/hooks`. New header practice: `beautiful_json`.

**Routine: `codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])`**
(cell `goga/commands/codegraph` — CHANGED: takes over serialization)
- Declared `location`: `codegraph.py`
- Facade obligation: importable from `goga.commands.codegraph`, re-exported by
  `goga.commands`
- Semantic requirements: click surface and failure contract unchanged (exception →
  stderr + `ctx.exit(1)`); **new step 3** — `document = [asdict(node) for node in tree]`
  (`dataclasses.asdict` recurses into children and the dependencies dict — the very
  transformation the old `render_graph` performed) + `beautiful_json` + `click.echo`.
  Byte-identity by construction; help docstring unchanged.
- Imported dependencies: `codegraph AS codegraph_logic` + `codegraph-usage` from
  `goga/codegraph`; `CodegraphNode` from `goga/codegraph/facts`. New header practice:
  `beautiful_json`.

**Entity: `DriftEntry(kind: str, cell: str, types: list[str] | None)`** (cell `goga/drift` — NEW)
- Type: class (record; Entity with properties only)
- Declared `location`: `compare.py`
- Facade obligation: importable from `goga.drift`
- Properties: `kind -> str` (direction — `schema_only` or `codegraph_only`),
  `cell -> str` (normalized cell path of the discrepancy subject),
  `types -> list[str] | None` (sorted type names missing from the other view; `None`
  marks a cell-level discrepancy)
- Semantic requirements: frozen `kw_only=True` dataclass per `convention`;
  `__post_init__` copies the caller-owned `types` list (the family pattern of the facts
  records); the kind literals are module-level constants `SCHEMA_ONLY` /
  `CODEGRAPH_ONLY` (the literal values `"schema_only"` / `"codegraph_only"` are the
  serialized contract and never change).

**Routine: `compare_views(schema_tree: list[SchemaNode], codegraph_tree: list[CodegraphNode]) -> entries: list[DriftEntry]`**
(cell `goga/drift` — NEW)
- Declared `location`: `compare.py`
- Facade obligation: importable from `goga.drift`
- Semantic requirements: index each view by a recursive walk
  (`{SchemaNode.path: set(SchemaNode.types)}`, `{CodegraphNode.cell:
  set(CodegraphNode.types)}` — descending `children`); cell-level entries for paths in
  exactly one view (`types=None`); type-level entries for shared paths
  (`sorted(declared − code)` → one `schema_only` entry, `sorted(code − declared)` → one
  `codegraph_only` entry, only when non-empty); sort by `(cell, kind)`. Pure; identity
  is name-level; a cell-level entry never coexists with type-level entries of the same
  cell; type lists sorted and duplicate-free by construction; agreeing views → `[]`.
- Imported dependencies: `schema` + `schema-usage` from `goga/schema`; `SchemaNode` from
  `goga/schema/hooks`; `codegraph` + `codegraph-usage` from `goga/codegraph`;
  `CodegraphNode` from `goga/codegraph/facts`.

**Routine: `scope_entries(entries: list[DriftEntry], schema_tree: list[SchemaNode], codegraph_tree: list[CodegraphNode]) -> report: list[DriftEntry]`**
(cell `goga/drift` — NEW)
- Declared `location`: `compare.py`
- Facade obligation: importable from `goga.drift`
- Semantic requirements: collect surviving paths — the **union** of every
  `SchemaNode.path` walk of `schema_tree` and every `CodegraphNode.cell` walk of
  `codegraph_tree`; keep an entry iff its cell is in the union; order preserved. Pure;
  no fabrication, alteration, or reordering — survival is the only effect. This union is
  the guard that makes the `depends_on` asymmetry unable to fabricate entries.
- Imported dependencies: same as `compare_views`.

**Routine: `drift(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> report: list[DriftEntry]`**
(cell `goga/drift` — NEW)
- Declared `location`: `drift.py`
- Facade obligation: importable from `goga.drift`
- Semantic requirements: `complete_schema = schema([], None, [])`;
  `complete_codegraph = codegraph([], None, [])`;
  `filtered_schema = schema(cells, max_depth, depends_on)`;
  `filtered_codegraph = codegraph(cells, max_depth, depends_on)`;
  `entries = compare_views(complete_schema, complete_codegraph)`;
  `report = scope_entries(entries, filtered_schema, filtered_codegraph)`; return
  `report`. The comparison always runs on the complete views; the filters scope the
  report only. Deterministic, idempotent, read-only; every producer error propagates
  unchanged (no try/except in the domain routine); the mutable defaults carry
  `# noqa: B006` per the family precedent. Does not read manifests or sources itself.
- Imported dependencies: `schema`, `codegraph` producers (relatively imported:
  `from ..schema import schema`, `from ..codegraph import codegraph`).

**Routine: `drift(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])`**
(cell `goga/commands/drift` — NEW CLI wrapper)
- Declared `location`: `drift.py`
- Facade obligation: importable from `goga.commands.drift`, re-exported by
  `goga.commands`, registered in the `goga` root group
- Semantic requirements: family click surface (`CELLS` variadic argument,
  `--max-depth`, repeatable `--depends-on`, `@click.pass_context`);
  `drift_logic(list(cells), max_depth, list(depends_on))`; any `Exception` →
  `click.echo(str(e), err=True)` + `ctx.exit(2)` (nothing on stdout, no traceback);
  project each `DriftEntry` to `{"kind": ..., "cell": ...}` plus
  `"types": list(entry.types)` only when `entry.types is not None`;
  `beautiful_json` + `click.echo`; `if report: ctx.exit(1)` else fall through → exit 0.
  Exits via `ctx.exit(...)` — never `sys.exit`, never `click.ClickException`. The
  exit-2 deviation from the family exit-1 failure convention is deliberate and
  PERMANENT (ADR). The command docstring is user-facing help documenting the report
  structure and the three statuses (verbatim docstring in Task 6).
- Imported dependencies: `drift AS drift_logic`, `DriftEntry` + `drift-usage` from
  `goga/drift`. Practices: `click`, `beautiful_json`, `convention`.

### Interaction and Data Flow

Interaction diagram (verbatim from the design):

```
                     ┌───────────────────────── goga drift (CLI) ─────────────────────────┐
                     │  exit 0 []  │  exit 1 report  │  exit 2 stderr                     │
                     └───────────────────────────────┬────────────────────────────────────┘
                                                     │ drift_logic(cells, max_depth, depends_on)
                                                     ▼
                                              goga/drift::drift
                complete views (no filters)          │          filtered views (filters)
        ┌───────────────────────────────────────────┼───────────────────────────────────┐
        ▼                                           ▼                                   ▼
 goga/schema::schema                      goga/schema::schema            compare_views(complete)
 -> list[SchemaNode]                      -> list[SchemaNode]            + scope_entries(filtered)
        │                                           │                                   ▲
        │ hooks: amend_cell + validate_schema       │                                   │
        ▼                                           ▼                                   ▼
 goga/codegraph::codegraph                goga/codegraph::codegraph
 -> list[CodegraphNode]                   -> list[CodegraphNode]

 goga/commands/schema  ── schema_logic -> list[SchemaNode] ── project ── beautiful_json ── click.echo
 goga/commands/codegraph ── codegraph_logic -> list[CodegraphNode] ── asdict ── beautiful_json ── click.echo
 goga/commands/drift ── drift_logic -> list[DriftEntry] ── project ── beautiful_json ── click.echo
 goga/commands (facade) ── re-export drift;  goga.app ── add_command(drift)
```

Data flows (verbatim from the design):

1. **Drift report** — `drift()` calls `schema()` and `codegraph()` twice each
   (complete: `([], None, [])`; filtered: `(cells, max_depth, depends_on)`). The complete
   views feed `compare_views` (facts); the filtered views feed `scope_entries`
   (survival). The report flows to the CLI wrapper, which projects each `DriftEntry` to
   `{kind, cell[, types]}` and serializes.
2. **Schema CLI output** — `schema()` returns `list[SchemaNode]`; the wrapper projects
   each node to the seven output keys (`cell` from `path`, `dependencies` regrouped from
   `DependencyFacts` records, `tools` only when non-empty) and serializes via
   `beautiful_json`. Byte-identical to the pre-refactor domain serialization.
3. **Codegraph CLI output** — `codegraph()` returns `list[CodegraphNode]`; the wrapper
   maps records via `dataclasses.asdict` (fields map one-to-one to output keys) and
   serializes via `beautiful_json`. Byte-identical to the pre-refactor `render_graph`
   serialization.
4. **Registration** — `goga/commands/drift` re-exports the command; the facade
   `goga/commands` re-exports it in turn; `goga/cli.py` imports it from the facade and
   registers it in the `app()` group after `codegraph`.

Entity dependencies (verbatim from the design — fixed, one-way):
`goga/drift` → `goga/schema` (`schema`), `goga/schema/hooks` (`SchemaNode`),
`goga/codegraph` (`codegraph`), `goga/codegraph/facts` (`CodegraphNode`);
`goga/commands/schema` → `goga/schema`, `goga/schema/hooks`;
`goga/commands/codegraph` → `goga/codegraph`, `goga/codegraph/facts`;
`goga/commands/drift` → `goga/drift`; `goga/commands` → `goga/commands/drift`;
`goga` → `goga/commands`. The two view producers stay mutually blind.

Verified chains (design Code Stack Trace — the checkpoints every task preserves):
schema — AST error gate unchanged; filters and their order identical (byte-identity of
CLI output depends on it); empty-tree early return **before** checkpoint delivery
(`return []`); delivery pruning equals output pruning; the gate runs over the very list
that is returned; serialization leaves the domain. codegraph — producer failure modes
unchanged (drift propagates them; the drift CLI maps them to exit 2); pass-through
return; purity (`_with_children` rebuilds; empty forest → `[]` naturally). drift —
no-double-reporting (mutually exclusive branches); union survival (never both views
required); order preservation; error pass-through. commands — byte-identity mechanisms
(projection rebuilds the exact legacy dict shape, `tools` key iff non-empty; `asdict` is
the very transformation the old tail performed); three-outcome exit contract; facade
re-export chain (drift.py → subcell `__init__` → facade → root).

### Re-exports

- `->drift: {}` in `goga/commands/CODEMANIFEST`
  - Name: `drift`
  - Source: `Imports` entry `drift` from `goga/commands/drift`
  - Facade obligation: `from goga.commands import drift` binds the same click command
    object; `"drift"` in `goga.commands.__all__` (alphabetical position: after
    `contract`… per the design wiring: the import line lands after
    `from .contract import contract` and before `history`, same position in `__all__`)
  - Hierarchy constraint: `goga/commands/drift` is a subcell — satisfied
- Root `goga/CODEMANIFEST`: `drift` added to the `goga/commands` import block and to the
  `Commands:` list of `app()` (after `codegraph`, before `contract`) — mirrored by
  `app.add_command(drift)` directly after `app.add_command(codegraph)` in `goga/cli.py`.

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — mandatory engineering/testing
  conventions for all Python code: relative imports, frozen `kw_only` dataclasses,
  Google docstrings, CLI docstring exceptions, formatting, test structure, validation
  commands. Fully transcribed into **Mandatory Rules** above; relevant to every task.
- `click` (`.goga/usages/cooks/click.md`) — the CLI framework patterns: decorators,
  variadic arguments, repeatable options, `ctx.exit`, echo conventions. Used by the
  drift wrapper (Task 6); unchanged in the two sibling wrappers.
- `beautiful_json` (`.goga/usages/cooks/beautiful_json.md`) — the family serialization:
  `json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`. Used by the three
  command wrappers (Tasks 2, 3, 6); header practice of the three command cells.
- `documents` (inline, `goga/schema`) — AST loading contract (`AST(".")`, `.load()`,
  `.tree`, `.errors`). Used by `schema()` step 1 (unchanged; Task 2 context).

### Imported Usages

- `schema-usage` from `goga/schema` — how to call `schema()` and consume
  `list[SchemaNode]` (tree walk, field semantics, caller-owned serialization).
  Source: `goga/schema/.usages/schema-usage.md`. Used in Tasks 4–5 (the drift domain
  consumes both producers).
- `codegraph-usage` from `goga/codegraph` — how to call `codegraph()` and consume
  `list[CodegraphNode]`. Source: `goga/codegraph/.usages/codegraph-usage.md`. Used in
  Tasks 4–5.
- `checkpoints` from `goga/schema/hooks` — the amend/gate delivery contract the schema
  routine fulfills internally. Source: `goga/schema/hooks/.usages/checkpoints.md`. Used
  in Task 2 (implementation) and Task 2's failure-handling context.
- `registering-hooks` from `goga/schema` — tool-package subscription surface; context
  for the command's stderr behavior. Source:
  `goga/schema/.usages/registering-hooks.md`. Used in Task 2.
- `records` from `goga/codegraph/facts` — the record vocabulary (`CodegraphNode`
  construction rules) used by `render_graph`. Source:
  `goga/codegraph/facts/.usages/records.md`. Used in Task 3.
- `stages` from `goga/codegraph/analysis` — the three-stage pipeline order used by the
  orchestrator. Source: `goga/codegraph/analysis/.usages/stages.md`. Used in Task 3.
- `project-configuration` from `goga/config` — `load_project_config` semantics
  (language, lint exclusions). Source: `goga/config/.usages/project-configuration.md`.
  Used in Tasks 3 and 5 (failure modes).
- `drift-usage` from `goga/drift` — the report and failure contract behind the command.
  Source: `goga/drift/.usages/drift-usage.md`. Used in Task 6.
- `cli-commands` from `goga/commands` — the registration reference (18 commands, import
  lines, add_command wiring, command table). Source:
  `goga/commands/.usages/cli-commands.md`. Used in Task 6.

### Local Usages

All cell-level practice files already exist on this branch (apply stage) and the design
review confirmed them current — **no creation or update tasks**:

- `goga/schema/.usages/schema-usage.md` — status: current (rewritten to the object
  contract: return `list[SchemaNode]`, the field table, the caller-owned family
  serialization recipe).
- `goga/schema/.usages/registering-hooks.md` — status: current, untouched.
- `goga/codegraph/.usages/codegraph-usage.md` — status: current (object-tree contract,
  field table, one-to-one serialization note, drift named as a consumer).
- `goga/drift/.usages/drift-usage.md` — status: created (domain statement, import line,
  filter semantics, entry table with the four semantic kinds, serialization recipe,
  guarantees, failure behavior; self-contained).
- `goga/commands/drift/.usages/drift.md` — status: created (syntax, argument/option
  tables, the three exit codes, output field table, examples).
- `goga/commands/.usages/cli-commands.md` — status: current (18 commands; `drift` in
  all four lists).
- `goga/commands/schema`, `goga/commands/codegraph` `.usages/` files — intentionally
  unchanged (they document CLI-level behavior, byte-identical before and after).

### External Dependencies

- `click>=8.0` (pinned 8.5.0 — `CliRunner` stream semantics verified live by the design
  review) — already in `pyproject.toml`.
- `pyyaml`, `tree-sitter*` — consumed through the existing producers; already pinned.
- Tools: pytest, pytest-cov, ruff (`test` extra); `goga lint` and `goga schema` (the
  project's own gates).
- **No new dependencies are introduced by this plan.**

## Facts

- The contract layer is DONE and read-only: all CODEMANIFEST changes are applied in the
  working tree (`goga/schema`, `goga/codegraph`, `goga/commands/schema`,
  `goga/commands/codegraph`, `goga/commands`, `goga` modified; `goga/drift`,
  `goga/commands/drift` new with manifests + `.usages/`); `goga lint` reports
  `cells: 89 errors: 0`.
- The drift cells contain CODEMANIFEST + `.usages/` files only — no `__init__.py`, no
  implementation files.
- The current `schema()` tail is `return json.dumps(result, indent=4, sort_keys=True,
  ensure_ascii=False)` with `return "[]"` for the empty tree; the gate already runs over
  `[_to_schema_node(node) for node in result]` — the projection exists and becomes the
  return value.
- The current `render_graph()` tail is `document = [asdict(root) for root in roots]`
  + `json.dumps(...)` with `return "[]"` for the empty forest — the wrapper's
  `[asdict(n) for n in tree]` + `beautiful_json` reproduces it byte for byte.
- The current wrappers echo the domain string directly (`click.echo(result)`); the
  wrappers' try/except `Exception` → stderr + `ctx.exit(1)` blocks are the family
  pattern and stay unchanged.
- click 8.5.0 `CliRunner` semantics (verified live): `result.output` = combined
  stdout+stderr; `result.stdout` / `result.stderr` are the dedicated streams —
  clean-stdout assertions must use `result.stdout`.
- The four-kinds fixture expectations, the `depends_on` asymmetry views, the
  `max_depth=0` behavior, and the `__init__.py` facade-leak constraint were all
  validated by dry-running the live producers over the exact planted layouts
  (design "General Setup").
- The two golden CLI outputs must be captured from the **current** CLI before any
  domain is touched — they are the C2 net and must pass untouched after the refactor.
  Never weaken a golden to make a gate pass — a golden mismatch is a defect in the
  refactor.
- Six existing suites pin the JSON-string domain return and break at `pytest tests/ -x`
  the moment it changes: `tests/schema/test_schema.py`,
  `tests/schema/test_contract.py` (`test_schema_returns_str`),
  `tests/commands/schema/test_schema.py` (`json.loads(routine_output)`;
  `set(routine_outputs)` — unhashable list of records),
  `tests/integration/test_schema_walk_gate_integration.py` (`json.loads(result)` ×3;
  `result == GATE_GOLDEN`), `tests/codegraph/test_codegraph.py`
  (`isinstance(result, str)`; `== GOLDEN_OUTPUT`; `== "[]"`), and
  `tests/codegraph/test_render.py` (`test_render_graph_returns_json_string`).
- CLI-level suites that pin only `json.loads(result.output)` of command stdout need no
  changes (byte-identity by construction). Exception: `tests/integration/
  test_integration_split.py` mocks `schema_logic` with JSON-string return values in
  three tests (lines 63, 75, 274) — those mocks are adapted to object trees in
  Task 2; the suite's stdout-pinned tests stay untouched.
- The `.venv` is broken — `python`/`python3`/`python3.14` symlinks point to
  `/opt/homebrew/opt/python@3.14/bin/python3.14`, which does not exist on this host;
  the system interpreter is `/opt/goga/bin/python` (3.12.15). Task 1 recreates the venv.
- CI gates: `ruff check goga/ tests/`, `ruff format --check goga/ tests/`, pytest
  matrix. Local gates add `goga lint` and the facade import checks.
- The exit-2 deviation is permanent (ADR) — do not "align" it later; exit 1 is reserved
  for discrepancies found.
- `goga/drift/`, `goga/commands/drift/`, and `.goga/history/2026/drift-command/` are
  untracked (`??` in git status) — they must be committed with the implementation.
- Implementation order (design, leaves first): schema domain → codegraph domain →
  drift domain → command wrappers → facade → root CLI → tests/docs collateral. This
  plan pairs each domain with its wrapper (see Tasks note) to keep every task's full
  battery green.

## Gap Analysis

- **Missing contract entities**: five — `DriftEntry`, `compare_views`, `scope_entries`
  (`goga/drift/compare.py`), `drift` (`goga/drift/drift.py`), the CLI `drift`
  (`goga/commands/drift/drift.py`); plus the facades `goga/drift/__init__.py` and
  `goga/commands/drift/__init__.py` (none exist).
- **Missing facade exposure**: `goga/commands/__init__.py` lacks
  `from .drift import drift` and the `"drift"` `__all__` entry; `goga/cli.py` lacks the
  facade import and `app.add_command(drift)`.
- **API mismatches (live code vs contract)**: `goga/schema/schema.py` returns
  `json.dumps(...)` (contract: `list[SchemaNode]`); `goga/codegraph/render.py` returns
  the serialized document (contract: `list[CodegraphNode]`);
  `goga/codegraph/codegraph.py` docstring/annotations still describe the JSON string;
  the two wrappers echo the domain string (contract: projection + `beautiful_json`).
- **Behavioral mismatches**: none beyond the return contract — filters, gates,
  checkpoint delivery, click surfaces, and failure contracts are unchanged and verified
  against the live code by the design review.
- **Existing code that can be reused**: the dict-tree internals and `_to_schema_node`
  projection of `goga/schema/schema.py`; the `_build_forest`/`_filter_cells`/
  `_filter_by_depends_on`/`_prune_depth` helpers of `goga/codegraph/render.py`; the
  wrappers' try/except blocks and click surface decorators; the family command
  docstring style of the two sibling wrappers; the test scaffolding
  (`tests/schema/conftest.py` `_write_walk_project`/`_write_codemanifest`, the autouse
  `_empty_package_environment` pattern, `tests/commands/conftest.py`
  `empty_package_environment`).
- **Test coverage gaps**: no `tests/drift/**`, no `tests/commands/drift/`; the six
  string-pinned suites need adaptation; `tests/commands/test_commands_facade.py` lacks
  the drift re-export tests; `tests/test_cli.py` lacks the drift registration row.
- **Missing visibility in workspace or git**: `goga/drift/`, `goga/commands/drift/`
  untracked — commit with the implementation.
- **Docs gaps**: no `docs/features/drift/`; `docs/features/index.md` and
  `docs/cli/index.md` lack the drift rows.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting
> the next. Within each coding task, contract tests are written first (TDD workflow).
> Order: goldens (infrastructure) → `goga/schema` + `goga/commands/schema` →
> `goga/codegraph` + `goga/commands/codegraph` → `goga/drift` (`compare` → `drift`) →
> `goga/commands/drift` (+ facade + root) → docs → full-stack verification.
>
> **Domain+wrapper pairing note**: the design's arch-plan order is domains first, then
> the three wrappers. This plan pairs each refactored domain with its wrapper
> (Tasks 2 and 3) because after the return-type change the wrapper is the sole
> serialization owner — a domain landed without its wrapper (or vice versa) leaves the
> CLI printing Python reprs and the full battery red, violating the per-task green
> requirement. The pairing changes nothing semantically; both files of each pair carry
> exactly the design's deltas.
>
> **Facade assembly note**: per-cell `__init__.py` facades are created by the first task
> that lands an entity of the cell and extended by each subsequent task (final state
> documented per task). This keeps every task independently green — no skeleton modules
> and no facade importing non-existent names.
>
> **Mandatory Rules apply to every task** (style, tests, lint/format gates, REPL cycle,
> commit policy). Each task's gates checkbox restates them; the rules section is
> authoritative.

### Task 1: Golden byte-identity nets and the development environment (infrastructure)

Prepare the execution environment and lay the C2 regression net BEFORE any domain is
touched. Two outcomes: (a) a working virtualenv (the current `.venv` is broken — its
python symlinks target a nonexistent macOS homebrew path), and (b) golden CLI tests for
the `schema` and `codegraph` commands that pin the CURRENT stdout byte for byte — full
run plus every filter form plus the empty tree — so the Tasks 2–3 refactors prove
byte-identity. These golden tests pass against the current implementation (that is what
makes them a valid net) and must pass untouched after the refactor. No production code
changes in this task.

**Usages relevant to this task:**
- `convention`: virtualenv execution rule ("create it if missing" — here: recreate the
  broken one); test structure rules; validation command table.
- REPL cycle rule 2 (probe before writing): the goldens are captured from the LIVE CLI
  in the REPL, never typed from memory.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **Environment**: recreate the virtualenv — `python -m venv .venv --clear` (system
      interpreter: `/opt/goga/bin/python`, 3.12.15; the broken symlinks point to
      `/opt/homebrew/opt/python@3.14` which does not exist on this host), then
      `.venv/bin/pip install -e ".[test]"`; verify `.venv/bin/python --version`,
      `.venv/bin/pytest --version`, `.venv/bin/ruff --version`, and
      `.venv/bin/python -m goga --help` all work.
- [x] **REPL probe — capture goldens**: in the virtualenv REPL (`python -` heredoc or a
      scratch script under `tmp_path`), plant the walk-project fixture layout (mirror
      `_write_walk_project` of `tests/schema/conftest.py`) in a scratch directory with
      `.goga/config.yml` (`language: python`), `cd` there, and capture the stdout of
      `goga schema` and `goga codegraph` for every form: the full run, a `cells`
      filter, `--max-depth`, `--depends-on`, and the empty-tree case (config-only
      project). Embed the captured strings verbatim as module constants — never
      hand-type them.
- [x] **Code**: add `TestSchemaCliByteIdentity` (or extend the existing equivalence
      class) in `tests/commands/schema/test_schema.py` with
      `test_schema_cli_output_byte_identical_golden` — plants the same fixture layout
      via the existing helpers, invokes `runner.invoke(app, ["schema", ...])` per form,
      asserts `result.output == GOLDEN_FULL` etc. for every form, exit 0, and the
      empty-tree form asserting the exact `"[]"` document.
- [x] **Code**: add `test_codegraph_cli_output_byte_identical_golden` to
      `tests/commands/codegraph/test_codegraph.py` — identical construction over the
      codegraph fixture project (full run + filter forms; the `"[]"` empty-project case
      included).
- [x] **Verify**: `pytest tests/commands/schema/ tests/commands/codegraph/ -v` — the
      golden tests PASS against the current implementation (a failing golden here means
      the capture is wrong — recapture, never adjust the implementation).
- [x] Lint: `ruff check tests/` and `ruff format --check tests/` (run `ruff format`
      on diffs); `goga lint` — 0 errors.
- [x] **Commit gate**: full `pytest tests/ -x` green; commit without `Co-Authored-By:`
      trailers.

### Task 2: `goga/schema` object-return refactor + `goga/commands/schema` projection wrapper + string-pinned suite adaptations (TDD)

One atomic refactor pair: the domain returns the assembled `list[SchemaNode]` tree and
the wrapper takes over projection + serialization, so the CLI output stays byte-identical
(Task 1's goldens prove it). Contract entities: `goga/schema` `schema` (changed return)
and `goga/commands/schema` `schema` (algorithm steps 3–4). The design's verified delta
for `goga/schema/schema.py` (nothing else in the file changes):

```
6. nodes = [_to_schema_node(node) for node in result]   # built once
7. verdict = hooks.validate_schema(nodes)
   IF not verdict.approved → raise merged ValueError
8. return nodes                                          # was: json.dumps(result)
```

Step 4's early return becomes `if not result: return []`. The `json` import and the
`-> str` annotation leave; the docstring documents `list[SchemaNode]` and the
caller-owns-serialization rule. The wrapper gains the module-level private projector
(verbatim from the design):

```python
def _project_node(node: SchemaNode) -> dict:
    """Project one read-only schema node onto the family JSON output shape."""
    projected = {
        "cell": node.path,
        "description": node.description,
        "types": list(node.types),
        "usages": list(node.usages),
        "dependencies": {
            dep.path: {"types": list(dep.types), "usages": list(dep.usages)}
            for dep in node.dependencies
        },
        "children": [_project_node(child) for child in node.children],
    }

    if node.tools:
        projected["tools"] = node.tools

    return projected
```

Callback tail: `click.echo(json.dumps([_project_node(n) for n in result], indent=4,
sort_keys=True, ensure_ascii=False))` (the `beautiful_json` practice). The wrapper's
`from ...schema.hooks import SchemaNode` import lands per the manifest Imports. The help
docstring is unchanged. Keep the domain internals (the dict tree, `_to_schema_node`, the
filter helpers) — only the return tail changes; do not rewrite working filter logic.

**Usages relevant to this task:**
- `convention`: relative imports; Google docstrings; the domain docstring documents the
  object contract; test adaptation rules.
- `beautiful_json`: `json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)` —
  exactly this call, once, over the fully projected list.
- `documents`: the AST loading contract — unchanged step 1.
- `checkpoints` (from `goga/schema/hooks`): the amend/gate delivery contract — the gate
  now runs over the very list that is returned; hard-failure behavior unchanged.
- `registering-hooks` (from `goga/schema`): tool-package subscription surface — context
  for the command's stderr behavior.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 2 — schema object-return
      refactor + projection wrapper`) in the session log.
- [x] **Contract tests** (expected to fail now): in `tests/schema/test_contract.py`
      rename `test_schema_returns_str` → `test_schema_returns_schema_node_list` and pin
      `typing.get_type_hints(schema)["return"]` as `list[SchemaNode]` (the parameter
      checks stay unchanged); in `tests/schema/test_schema.py` add
      `test_schema_domain_returns_schema_node_tree` — `schema([], None, [])` returns a
      `list[SchemaNode]` whose `result[0].path`, `.types`, `.children[0]...` match the
      previous JSON expectations, and `schema([...], 0, [])` returns `[]` for the
      max-depth-0 empty case.
- [x] **Code**: refactor `goga/schema/schema.py` per the delta above — `return nodes`,
      early `return []`, delete the `json.dumps` tail and the `json` import, update the
      docstring and `-> list[SchemaNode]` annotation. Preserve the empty-tree early
      return BEFORE checkpoint delivery; delete (not keep) the `"[]"` string exit.
- [x] **Code**: refactor `goga/commands/schema/schema.py` — add `_project_node` and the
      import of `SchemaNode` from `...schema.hooks`; replace `click.echo(result)` with
      the projection + `beautiful_json` tail. The try/except block and the click surface
      stay unchanged.
- [x] **Interface verification**: `python -c "from goga.schema import schema"` and
      `python -c "from goga.commands.schema import schema"`; run the new contract tests
      — `pytest tests/schema/test_contract.py tests/schema/test_schema.py -v` — green.
- [x] **Logic tests — string-pinned suite adaptations** (expectation-preserving, per the
      design's adaptation block):
      - `tests/commands/schema/test_schema.py` routine-vs-CLI equivalence:
        `routine_output = schema_logic([], None, [])` is now the object tree; the
        assertion becomes
        `json.loads(cli_result.output) == [_project_node(n) for n in routine_output]`
        importing the wrapper's projector — the tested fact (routine and CLI produce
        the same extended tree) is unchanged.
      - same file, determinism: `set(routine_outputs)` over frozen records is
        unhashable — compare object trees directly
        (`routine_outputs[0] == routine_outputs[1] == routine_outputs[2]`,
        frozen-dataclass equality); keep the CLI-side `set(cli_outputs)` string check
        as is.
      - `tests/integration/test_schema_walk_gate_integration.py`: the `json.loads(result)`
        sites become direct `SchemaNode` attribute checks
        (`result[0].tools == {"docs": {"score": 3}}`,
        `result[0].children[0].tools == ...`) plus a seven-field check over
        `dataclasses.fields(result[0])` replacing the key-set assertion; the
        `result == GATE_GOLDEN` comparison serializes the object tree through the
        wrapper projection + `beautiful_json` and compares against the same golden —
        byte-for-byte expectation preserved.
      - `tests/schema/test_schema.py`: the existing `json.loads(result)` sites
        (~13, lines 504–945) become direct `SchemaNode` attribute checks
        (`result[0].path`, `.types`, `.children[0]...`; a key-set assertion
        becomes a field-set check over `dataclasses.fields`); the
        `result == "[]"` sites become `== []`; the domain-level format test
        (the `json.loads(json.dumps(parsed, ...))` round-trip) is deleted —
        serialization no longer lives in the domain (the byte format is pinned
        by the Task 1 CLI goldens); expectation-preserving per the design's rule.
      - `tests/integration/test_integration_split.py`: the three `schema_logic`
        mock return values (lines 63, 75, 274) become real object trees —
        `[SchemaNode(path=".", ...)]`, `[SchemaNode(path="pkg_a", ...)]`, `[]`
        (records imported from `goga.schema.hooks`); the stdout assertions
        (`'"cell": "."' in result.output`, `"[]" in result.output`) stay valid
        through the wrapper projection; the `mock_logic.assert_called_once_with(...)`
        checks are unchanged.
- [x] **REPL probe — byte-identity**: after the refactor, re-run the Task 1 scratch
      probe forms in the REPL and diff against the captured goldens — zero diff
      expected; then run the golden tests.
- [x] **Debugging**: `pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code; do NOT weaken a golden — a golden mismatch is a defect in
      the refactor).
- [x] **Contract re-verification**: `schema` returns `list[SchemaNode]`; gate-before-
      return ordering intact; empty-tree early return before delivery; wrapper emits
      stdout JSON only, exit 0/1 contract unchanged.
- [x] **Lint** (STEP 7): `ruff check goga/schema goga/commands/schema tests/schema
      tests/commands/schema tests/integration` then `ruff format --check` over the same
      set (run `ruff format` on diffs); `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: full `pytest tests/ -x` green (goldens included, untouched);
      `ruff check goga/ tests/` and `ruff format --check goga/ tests/` clean; commit
      without `Co-Authored-By:` trailers.

### Task 3: `goga/codegraph` object-return refactor + `goga/commands/codegraph` asdict wrapper + domain suite adaptations (TDD)

The second atomic pair: `render_graph` returns the filtered `CodegraphNode` forest and
the orchestrator flows it through; the wrapper takes over serialization via `asdict` —
the very transformation the old tail performed, so the CLI output stays byte-identical
(Task 1's codegraph goldens prove it). Contract entities: `goga/codegraph` `codegraph`
and `render_graph` (changed returns), `goga/commands/codegraph` `codegraph` (step 3).
Design deltas: in `goga/codegraph/render.py` delete the empty-forest early exit
(`if not roots: return "[]"`) and the `asdict`/`json.dumps` tail; `return roots`; the
`json`/`asdict` imports leave; the module docstring drops the serialization sentence.
In `goga/codegraph/codegraph.py` only the docstring/return annotations change (the
single `return render_graph(...)` line flows the new type through). In
`goga/commands/codegraph/codegraph.py` the callback tail becomes
`click.echo(json.dumps([asdict(n) for n in result], indent=4, sort_keys=True,
ensure_ascii=False))` with `from dataclasses import asdict`; the help docstring is
unchanged. Producer failure modes (`FileNotFoundError`, language `ValueError`,
unparseable-file error) stay unchanged.

**Usages relevant to this task:**
- `convention`: relative imports; Google docstrings; test adaptation rules.
- `beautiful_json`: exactly the family call, once, over the fully mapped list.
- `records` (from `goga/codegraph/facts`): `CodegraphNode` construction — the forest
  builders are unchanged; only the tail changes.
- `stages` (from `goga/codegraph/analysis`): the three-stage pipeline order — unchanged.
- `project-configuration` (from `goga/config`): `load_project_config` failure modes —
  unchanged, they propagate to exit codes as today.
- `codegraph-usage` (from `goga/codegraph`): the object-tree consumption contract.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] **STEP 0 — Declaration**: declare this task (`Task 3 — codegraph object-return
      refactor + asdict wrapper`).
- [ ] **Contract tests** (expected to fail now): in `tests/codegraph/test_codegraph.py`
      adapt `test_codegraph_callable_no_arguments` to assert `list[CodegraphNode]`
      (was `isinstance(result, str)`); in `tests/codegraph/test_render.py` rename
      `test_render_graph_returns_json_string` →
      `test_render_graph_returns_unserialized_object_tree` asserting the elements are
      `CodegraphNode` and the empty case `== []` (was `== "[]"`); filter-parity
      expected values unchanged — the JSON-string consumption sites become direct
      record access (see the Logic tests bullet).
- [ ] **Code**: refactor `goga/codegraph/render.py` per the delta — `return roots`,
      delete the `"[]"` early exit and the serialization tail, drop the
      `json`/`asdict` imports, trim the docstring.
- [ ] **Code**: update `goga/codegraph/codegraph.py` docstring and return annotations
      to `list[CodegraphNode]` (orchestration unchanged).
- [ ] **Code**: refactor `goga/commands/codegraph/codegraph.py` — the `asdict` mapping
      + `beautiful_json` tail; click surface and try/except unchanged.
- [ ] **Interface verification**: `python -c "from goga.codegraph import codegraph,
      render_graph"` and `python -c "from goga.commands.codegraph import codegraph"`;
      `pytest tests/codegraph/ -v` — green.
- [ ] **Logic tests — remaining domain adaptations** (`tests/codegraph/test_codegraph.py`):
      the end-to-end golden `codegraph() == GOLDEN_OUTPUT` becomes the object-tree
      comparison `[asdict(n) for n in codegraph()] == json.loads(GOLDEN_OUTPUT)`
      (expectation preserved through the same mapping the wrapper performs); the
      empty-project `codegraph() == "[]"` becomes `== []`; the iterated
      `node["cell"]` sites become attribute access (`.cell`).
      - `tests/codegraph/test_render.py`: in the nesting test,
        `doc = json.loads(json_text)` becomes direct record access (`node.cell`,
        `child.dependencies`, `.children`); the `set(doc[0].keys())` check becomes
        a field-set check over `dataclasses.fields`; in the filter-parity test, the
        `cells_in_tree` helper walks `.cell`/`.children` attributes instead of
        `json.loads` dicts, and the `_find_root(json.loads(...))` sites become
        attribute access on `CodegraphNode` records; expected values unchanged;
        the determinism re-comparison (`render_graph(...) == json_text`) compares
        object trees — still valid.
- [ ] **REPL probe — byte-identity**: re-run the Task 1 codegraph scratch forms and
      diff against the captured goldens — zero diff expected; the CLI-stdout
      integration suite `tests/integration/test_codegraph_cli_integration.py` needs
      no changes and must stay green untouched (the `test_integration_split.py`
      schema mocks were adapted in Task 2; its remaining stdout tests are
      untouched).
- [ ] **Debugging**: `pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT weaken a golden).
- [ ] **Contract re-verification**: `render_graph` returns the filtered forest
      (`[]` naturally when empty); purity (fresh frozen nodes, inputs unmutated);
      producer error surface unchanged; wrapper stdout JSON only.
- [ ] **Lint** (STEP 7): `ruff check goga/codegraph goga/commands/codegraph
      tests/codegraph` then `ruff format --check` over the same set; `goga lint` —
      0 errors.
- [ ] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [ ] **Commit gate**: full `pytest tests/ -x` green (goldens untouched);
      `ruff check goga/ tests/` and `ruff format --check goga/ tests/` clean; commit
      without `Co-Authored-By:` trailers.

### Task 4: `goga/drift` comparison core — `DriftEntry`, `compare_views`, `scope_entries`, and the cell facade (TDD)

The leaf of the new cell: the drift record vocabulary and the pure comparison core in
`goga/drift/compare.py` (new), plus the cell facade `goga/drift/__init__.py` re-exporting
`DriftEntry`, `compare_views`, `scope_entries` (Task 5 appends `drift`; final state
re-exports all four). No I/O, no filters, no producers. The module plan (docstring,
imports, constants, record) is verbatim in the design:

```python
"""Comparison core — the drift entries of the two complete views and their scoping.

The module owns the flat report record and the two pure steps over the view
trees: the name-level comparison of the complete views and the survival
scoping over the filtered views. No filters are applied here — the entries
are facts of the views passed in.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..codegraph.facts import CodegraphNode
from ..schema.hooks import SchemaNode

SCHEMA_ONLY = "schema_only"
CODEGRAPH_ONLY = "codegraph_only"


@dataclass(frozen=True, kw_only=True)
class DriftEntry:
    """One flat entry of the drift report.

    Args:
        kind: Direction of the discrepancy — ``schema_only`` or
            ``codegraph_only``.
        cell: Normalized cell path of the discrepancy subject.
        types: Sorted type names of the cell missing from the other view;
            ``None`` marks a cell-level discrepancy.
    """

    kind: str
    cell: str
    types: list[str] | None = None

    def __post_init__(self) -> None:
        """Copy the caller-owned type list into a fresh list."""
        if self.types is not None:
            object.__setattr__(self, "types", list(self.types))
```

`compare_views` algorithm (verbatim from the design):

```
1. build schema_index: walk schema_tree recursively (node + children)
   → {SchemaNode.path: set(SchemaNode.types)}
2. build codegraph_index: walk codegraph_tree recursively
   → {CodegraphNode.cell: set(CodegraphNode.types)}
3. FOR path IN schema_index.keys() - codegraph_index.keys():
   - append DriftEntry(kind=SCHEMA_ONLY, cell=path, types=None)
4. FOR path IN codegraph_index.keys() - schema_index.keys():
   - append DriftEntry(kind=CODEGRAPH_ONLY, cell=path, types=None)
5. FOR path IN schema_index.keys() & codegraph_index.keys():
   - declared_only = sorted(schema_index[path] - codegraph_index[path])
   - code_only = sorted(codegraph_index[path] - schema_index[path])
   - IF declared_only: append DriftEntry(SCHEMA_ONLY, path, declared_only)
   - IF code_only: append DriftEntry(CODEGRAPH_ONLY, path, code_only)
6. entries.sort(key=(cell, kind))
   → return entries
```

`scope_entries` algorithm (verbatim): collect surviving paths — the union of the
recursive `SchemaNode.path` walk and the recursive `CodegraphNode.cell` walk; return
`[entry for entry in entries if entry.cell in surviving]`. Internal walk helpers
(e.g. `_index_schema` / `_index_codegraph` or equivalents) are private module functions.

**Usages relevant to this task:**
- `convention`: data-model rules (frozen, `kw_only`, container copy, `None` as recorded
  absence); relative imports (`from ..codegraph.facts import CodegraphNode`,
  `from ..schema.hooks import SchemaNode`); Google docstrings; test mirroring
  (`tests/drift/test_compare.py`); no mocks for pure logic.
- `schema-usage` / `codegraph-usage` (imported): the field semantics of the two view
  records (`SchemaNode.path/.types/.children`, `CodegraphNode.cell/.types/.children`)
  the walks rely on.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] **STEP 0 — Declaration**: declare this task (`Task 4 — drift comparison core`).
- [ ] **Contract tests** (expected to fail now): create `tests/drift/__init__.py` and
      `tests/drift/test_compare.py` with `class TestCompareCore:` asserting —
      `DriftEntry`, `compare_views`, `scope_entries` importable from `goga.drift`;
      `goga.drift.__all__` (final state) equals the sorted four names — for this task
      assert the three landed names are exposed; `compare_views` and `scope_entries`
      callable with the declared signatures.
- [ ] **REPL probe**: in the virtualenv REPL construct the four-kinds record sets
      inline and verify the set arithmetic (`{run, stale} − {run, helper2}` etc.) and
      the `(cell, kind)` sort order (`codegraph_only` < `schema_only` lexicographically,
      both directions of one cell adjacent) — then migrate the verified walk/index code
      into `compare.py`.
- [ ] **Code**: create `goga/drift/compare.py` per the module plan above — constants,
      `DriftEntry`, the two index walks, `compare_views`, `scope_entries`; Google
      docstrings on every public name.
- [ ] **Code**: create `goga/drift/__init__.py` — the facade docstring plus
      `from .compare import DriftEntry, compare_views, scope_entries` and the matching
      `__all__` (extended by Task 5 with `drift`).
- [ ] **Interface verification**: `python -c "from goga.drift import DriftEntry,
      compare_views, scope_entries"`; `pytest tests/drift/test_compare.py -v` — green.
- [ ] **Logic tests** (design scenarios, verbatim expectations):
      - `test_compare_views_reports_all_four_discrepancy_kinds` — schema tree
        `lib/thing`, `mix/run+stale`, `ghost/phantom` vs codegraph tree `lib/thing`,
        `mix/run+helper2`, `extra/helper` → exactly
        `[("codegraph_only", "extra", None), ("schema_only", "ghost", None),
        ("codegraph_only", "mix", ["helper2"]), ("schema_only", "mix", ["stale"])]`.
      - `test_compare_views_agreeing_views_yield_empty_list` — identical single-cell
        views → `[]`.
      - `test_compare_views_empty_views_yield_empty_list` — `compare_views([], [])`
        → `[]`.
      - `test_compare_views_collects_nested_children` — drift only on nested `a/b` →
        exactly one entry, `cell == "a/b"` (root-only indexing would miss it).
      - `test_compare_views_pure_inputs_unmutated` — deep-copied views; run; trees
        equal the copies.
      - `test_compare_views_cell_level_never_coexists_with_type_level` — `ghost` only
        in the schema view with types `["phantom"]` → exactly one entry,
        `types is None`.
      - `test_scope_entries_keeps_entry_surviving_in_one_view_only` — entry for `mix`,
        `schema_tree=[]`, codegraph view with `mix` → the entry survives (union).
      - `test_scope_entries_preserves_input_order` — deliberately unsorted entries,
        all surviving → output order equals input order (no re-sorting).
      - `test_scope_entries_empty_filtered_views_drop_everything` —
        `scope_entries(entries, [], [])` → `[]`.
      - `test_drift_entry_is_frozen_kw_only_record` — positional construction raises
        `TypeError`; attribute assignment raises `FrozenInstanceError`; mutating the
        source list does not change the entry (the construction copy).
- [ ] **Debugging**: `pytest tests/drift/ -x` — fix implementation code until all
      tests pass (do NOT fix test code).
- [ ] **Contract re-verification**: no-double-reporting (cell-level never with
      type-level of the same cell — mutually exclusive branches); both-directions-
      two-entries; type lists sorted and duplicate-free by construction; purity; the
      kind literals are the constants, never inline strings at call sites.
- [ ] **Lint** (STEP 7): `ruff check goga/drift tests/drift` then
      `ruff format --check goga/drift tests/drift`; `goga lint` — 0 errors (89 cells
      — the drift manifests already exist and are counted).
- [ ] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [ ] **Commit gate**: full `pytest tests/ -x` green; `ruff check goga/ tests/` and
      `ruff format --check goga/ tests/` clean; commit without `Co-Authored-By:`
      trailers (commit the untracked `goga/drift/` with this task).

### Task 5: `goga/drift` entry routine — `drift()` and the planted-project suites (TDD)

The entry routine of the cell: `goga/drift/drift.py` (new) producing the scoped report
via the four producer calls, the conftest with the planted projects, and the
filesystem-level test scenarios. Contract entity: `drift(cells, max_depth=None,
depends_on=[]) -> report: list[DriftEntry]`. Algorithm (verbatim from the design):

```
1. complete_schema = schema([], None, [])
   complete_codegraph = codegraph([], None, [])
2. filtered_schema = schema(cells, max_depth, depends_on)
   filtered_codegraph = codegraph(cells, max_depth, depends_on)
3. entries = compare_views(complete_schema, complete_codegraph)
4. report = scope_entries(entries, filtered_schema, filtered_codegraph)
   → return report
```

Imports: `from ..codegraph import codegraph` and `from ..schema import schema`
(relative, per the `convention` import rules); the mutable defaults `cells=[]`,
`depends_on=[]` carry `# noqa: B006` with the family comment (the CODEMANIFEST contract
default; never mutated) — mirror `codegraph()`. Every producer error propagates
unchanged — no try/except in the domain routine. Facade: extend
`goga/drift/__init__.py` with `from .drift import drift` and `"drift"` in `__all__`
(final facade state):

```python
"""Facade of the drift cell — the structural drift report between the declared and code-derived views."""

from .compare import DriftEntry, compare_views, scope_entries
from .drift import drift

__all__ = [
    "DriftEntry",
    "compare_views",
    "drift",
    "scope_entries",
]
```

Test scaffolding (`tests/drift/conftest.py`): mirror `_write_codemanifest` locally or
reuse; the autouse `_empty_package_environment` pattern of `tests/schema/test_schema.py`
(schema-hooks registry isolation — every module testing `schema()` uses it); planted
projects in `tmp_path` with `.goga/config.yml` (`language: python`). **Never place a
cross-unit import in a fixture package `__init__.py`** — the imported name leaks into
the unit facade and fabricates a `codegraph_only` entry; cross-unit imports that must
resolve as links go in a sibling module (e.g. `mix/impl.py`).

The four-kinds planted project (verbatim from the design):

```
.goga/config.yml   → "language: python"
lib/__init__.py    → "def thing() -> None: ..."
lib/CODEMANIFEST   → declares routine thing
mix/__init__.py    → "def run() -> None: ..." + "def helper2() -> None: ..."
mix/CODEMANIFEST   → declares routines run, stale
extra/__init__.py  → "def helper() -> None: ..."
ghost/CODEMANIFEST → declares routine phantom        # no .py files
```

**Usages relevant to this task:**
- `convention`: relative imports; `# noqa: B006` family precedent; test structure;
  tmp_path fixtures; `pytest.raises` for the error-propagation scenarios.
- `schema-usage` / `codegraph-usage` (imported): how to call the two producers and
  consume the object trees; the four-call pattern (one run per call, per the
  `checkpoints` practice — each call builds its own `SchemaHooks` registry).
- `project-configuration` (from `goga/config`): the failure modes that must propagate
  (absent config `FileNotFoundError`; unsupported language `ValueError`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] **STEP 0 — Declaration**: declare this task (`Task 5 — drift entry routine`).
- [ ] **Contract tests** (expected to fail now): create `tests/drift/conftest.py` and
      `tests/drift/test_drift.py` with `class TestDriftRoutine:` asserting — `drift`
      importable from `goga.drift`; `goga.drift.__all__` equals the four sorted names;
      the signature defaults (`max_depth=None`, `depends_on=[]`) via
      `typing.get_type_hints` / `inspect.signature`.
- [ ] **REPL probe**: plant the four-kinds project in a scratch `tmp_path`, run the
      live `schema([], None, [])` and `codegraph([], None, [])` over it in the REPL,
      and confirm the asserted views entry for entry
      (`{lib: {thing}, mix: {run, stale}, ghost: {phantom}}` vs
      `{lib: {thing}, mix: {run, helper2}, extra: {helper}}`) — the design dry-ran
      exactly this; re-confirm before pinning.
- [ ] **Code**: create `goga/drift/drift.py` per the algorithm above; extend
      `goga/drift/__init__.py` to the final facade state.
- [ ] **Interface verification**: `python -c "from goga.drift import drift"`;
      `pytest tests/drift/test_drift.py -v` — green.
- [ ] **Logic tests** (design scenarios, verbatim):
      - `test_drift_reports_planted_discrepancies_all_four_kinds` — four-kinds project,
        `drift([], None, [])` → exactly the four entries
        `[("codegraph_only", "extra", None), ("schema_only", "ghost", None),
        ("codegraph_only", "mix", ["helper2"]), ("schema_only", "mix", ["stale"])]`.
      - `test_drift_cells_filter_scopes_report_only` — `drift(["ghost"], None, [])` →
        exactly `[("schema_only", "ghost", None)]` (the complete views are still
        compared; only the ghost entry survives the union).
      - `test_drift_depends_on_asymmetry_never_fabricates_entries` — healthy-plus
        project: `lib` declared+code `thing`; `mix` declared `run`, `mix/__init__.py`
        defines `run` only, `mix/impl.py` does `from lib import thing` (sibling module
        so nothing leaks into the facade); no cell declares a manifest dependency on
        `lib`; `drift([], None, ["lib"])` → `[]` (schema filtered to `[]`, codegraph
        keeps `mix`; direct filtered-tree comparison would fabricate
        `"mix schema_only"` — the union guard must not).
      - `test_drift_max_depth_scopes_report` — `a` agrees; `a/b` nested in both views
        with `schema_only ["stale"]` drift (`a/b/CODEMANIFEST` declares `run, stale`;
        `a/b/__init__.py` defines `run`; `a/__init__.py` defines its declared name) →
        `drift([], None, [])` has the `a/b` entry; `drift([], 0, []) == []`.
      - `test_drift_deterministic_and_read_only` — two consecutive runs equal; a
        pre-run tree snapshot (paths + contents) equals the post-run snapshot.
      - `test_drift_propagates_ast_parse_error` — config + one invalid-YAML
        CODEMANIFEST → `pytest.raises(ValueError, match="AST parsing failed with 1
        error")` through `drift`.
      - `test_drift_propagates_unsupported_language_error` — config with
        `language: rust` → `pytest.raises(ValueError, match="unsupported language")`.
- [ ] **Debugging**: `pytest tests/drift/ -x` — fix implementation code until all
      tests pass (do NOT fix test code).
- [ ] **Contract re-verification**: complete-view comparison + filter scoping (the
      four producer calls — the accepted cost of the precision contract); error
      pass-through (no interception, no wrapping, no added failures); read-only;
      deterministic.
- [ ] **Lint** (STEP 7): `ruff check goga/drift tests/drift` then
      `ruff format --check goga/drift tests/drift`; `goga lint` — 0 errors.
- [ ] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [ ] **Commit gate**: full `pytest tests/ -x` green; `ruff check goga/ tests/` and
      `ruff format --check goga/ tests/` clean; commit without `Co-Authored-By:`
      trailers.

### Task 6: `goga/commands/drift` CLI wrapper + facade re-export + root registration (TDD)

The CLI layer: the new wrapper with the three-outcome exit contract, the facade
re-export, and the root registration — one atomic chain (a broken link anywhere leaves
the command unreachable). Contract entities: the CLI `drift` in
`goga/commands/drift/drift.py` (new), the `->drift: {}` embedding in
`goga/commands`, and the root `Commands:` entry. The command docstring (verbatim from
the design — user-facing help, family style, `\b` blocks):

```python
"""Report contract drift between declared manifests and actual code.

Compares the declared contract view (goga schema) with the code-derived
view (goga codegraph) and prints the flat JSON report of their
structural discrepancies to stdout. Discrepancies are computed on the
complete views; the filters scope the report only.

Every diagnostic goes to stderr; stdout carries the JSON report only.

\b
JSON report entries (sorted by cell path then kind):
  kind   - "schema_only" or "codegraph_only"
  cell   - normalized path of the discrepancy subject
  types  - sorted type names missing from the other view; present
           only on type-level entries — its absence marks a
           cell-level discrepancy

\b
Exit codes:
  0 - comparison completed, no discrepancies
  1 - comparison completed, discrepancies found
  2 - comparison could not be performed
"""
```

Algorithm (verbatim): `report = drift_logic(list(cells), max_depth, list(depends_on))`;
on any `Exception` — `click.echo(str(e), err=True); ctx.exit(2)`;
`projected = [_project_entry(entry) for entry in report]`;
`click.echo(json.dumps(projected, indent=4, sort_keys=True, ensure_ascii=False))`;
`if report: ctx.exit(1)` else return (exit 0). The projector:

```python
def _project_entry(entry: DriftEntry) -> dict:
    """Project one drift entry onto the family JSON output shape."""
    projected = {"kind": entry.kind, "cell": entry.cell}

    if entry.types is not None:
        projected["types"] = list(entry.types)

    return projected
```

Wiring (verbatim from the design): `goga/commands/drift/__init__.py` —

```python
from .drift import drift

__all__ = ["drift"]
```

`goga/commands/__init__.py`: `from .drift import drift` (after
`from .contract import contract`), `"drift"` in `__all__` (same position).
`goga/cli.py`: `drift` in the `from .commands import (...)` block (alphabetical) and
`app.add_command(drift)` directly after `app.add_command(codegraph)` — matching the
root manifest's `Commands:` order (schema, codegraph, drift, contract, …). Exits via
`ctx.exit(...)` — never `sys.exit`, never `click.ClickException` (the family catches
`Exception` broadly and echoes `str(e)` to stderr; keep that pattern). Import in the
wrapper: `from ...drift import DriftEntry, drift as drift_logic`.

**Usages relevant to this task:**
- `click`: `@click.command()`, `@click.argument("cells", nargs=-1)`,
  `@click.option("--max-depth", type=int, default=None)`,
  `@click.option("--depends-on", multiple=True, help=...)`, `@click.pass_context`;
  diagnostics via `click.echo(..., err=True)`; exits via `ctx.exit(code)`.
- `beautiful_json`: exactly the family call, once, over the fully projected list.
- `convention`: CLI docstring rules (this docstring IS the help — no Args/Returns/
  Raises; `\b` blocks; summary line in the command listing); relative imports.
- `drift-usage` (from `goga/drift`): the report and failure contract behind the command.
- `cli-commands` (from `goga/commands`): the registration reference — the facade import
  line, the add_command wiring, the 18-command table.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.
If implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] **STEP 0 — Declaration**: declare this task (`Task 6 — drift CLI wrapper +
      registration`).
- [ ] **Contract tests** (expected to fail now): create `tests/commands/drift/__init__.py`
      and `tests/commands/drift/test_drift.py` with `class TestDriftCommand:` asserting —
      `drift` importable from `goga.commands.drift` and from `goga.commands`;
      `isinstance(drift, click.Command)`; in `tests/commands/test_commands_facade.py`
      add `class TestDriftFacade:` with `test_drift_reexported_from_facade`
      (`facade_drift is goga.commands.drift.drift`), `test_drift_listed_in_all`,
      `test_drift_is_a_click_command_via_facade`; in `tests/test_cli.py` extend the
      registered-commands assertions with `"drift" in app.commands`
      (`test_drift_command_registered`).
- [ ] **REPL probe**: in the virtualenv REPL verify the exit semantics once through a
      scratch `CliRunner` invocation (`runner.invoke(app, ["drift"])` over a scratch
      project — confirm `result.exit_code` values and that `result.stdout` is the
      dedicated stream while `result.output` merges stderr on the pinned click 8.5.0).
- [ ] **Code**: create `goga/commands/drift/drift.py` — the docstring, the click
      surface, the try/except with `ctx.exit(2)`, `_project_entry`, the
      `beautiful_json` echo, and the `if report: ctx.exit(1)` tail.
- [ ] **Code**: create `goga/commands/drift/__init__.py`; wire
      `goga/commands/__init__.py` and `goga/cli.py` per the wiring above.
- [ ] **Interface verification**: `python -c "from goga.commands import drift"` and
      `python -m goga drift --help`; `pytest tests/commands/drift/
      tests/commands/test_commands_facade.py tests/test_cli.py -v` — green.
- [ ] **Logic tests** (design scenarios, verbatim):
      - `test_drift_cli_discrepancies_exit_1_and_print_full_report` — four-kinds
        project; `runner.invoke(app, ["drift"])` → `exit_code == 1`;
        `json.loads(result.output) == [{"cell": "extra", "kind": "codegraph_only"},
        {"cell": "ghost", "kind": "schema_only"}, {"cell": "mix", "kind":
        "codegraph_only", "types": ["helper2"]}, {"cell": "mix", "kind":
        "schema_only", "types": ["stale"]}]`; `result.output.endswith("\n")`.
      - `test_drift_cli_agreement_exit_0_prints_empty_list` — healthy project
        (config + `pkg/__init__.py` `def run() -> None: ...` + `pkg/CODEMANIFEST`
        declaring `run`) → `exit_code == 0`, `json.loads(result.output) == []`.
      - `test_drift_cli_uninitialized_project_exit_2_clean_stderr` — four-kinds project
        minus `.goga/config.yml` → `exit_code == 2`; `result.stdout == ""` (click ≥ 8.2:
        `result.output` merges stderr — assert the dedicated stream);
        `".goga/config.yml" in (result.stderr or "")`.
      - `test_drift_cli_ast_error_exit_2` — config + invalid-YAML CODEMANIFEST → exit 2,
        `result.stdout == ""`, stderr naming the parse failure.
      - `test_drift_cli_repeated_runs_byte_identical` — two invocations →
        `result1.output == result2.output`; both exit 1.
      - `test_drift_cli_help_documents_surface_report_and_statuses` —
        `runner.invoke(app, ["drift", "--help"])` → exit 0; asserts `"CELLS"`,
        `"--max-depth"`, `"--depends-on"`, `"kind"`, `"cell"`, `"types"`,
        `"schema_only"`, `"codegraph_only"`, and the three exit-code lines `"0"`,
        `"1"`, `"2"` in `result.output` (mirrors the codegraph help test — family
        convention).
- [ ] **Debugging**: `pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code; the exit-2 deviation is deliberate and permanent — do not
      "align" it to exit 1).
- [ ] **Contract re-verification**: three-outcome contract (0 completed+empty printing
      `[]`; 1 completed+discrepancies printing the full report; 2 could-not-perform
      with clean stdout and the reason on stderr); `types` key present only on
      type-level entries; facade chain drift.py → subcell `__init__` → facade → root
      group after `codegraph`.
- [ ] **Lint** (STEP 7): `ruff check goga/commands tests/commands` then
      `ruff format --check goga/commands tests/commands`; `goga lint` — 0 errors
      (89 cells).
- [ ] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [ ] **Commit gate**: full `pytest tests/ -x` green; `ruff check goga/ tests/` and
      `ruff format --check goga/ tests/` clean; commit without `Co-Authored-By:`
      trailers (commit the untracked `goga/commands/drift/` with this task).

### Task 7: Documentation collateral — the `drift` family pages (infrastructure)

The docs family page model for the new command (all content in English, family voice —
mirror the `docs/features/codegraph/` page set). No code changes. Pages per the design's
Additional Instructions:

- `docs/features/drift/index.md` — the two-view comparison model: complete-view
  comparison, the four semantic kinds (cell-level `schema_only`/`codegraph_only`,
  type-level both directions), scope-gating (filters select what is reported, never
  what is compared).
- `docs/features/drift/cli.md` — normative synopsis, argument/option tables, the three
  exit codes, the output field table (`kind`, `cell`, `types` presence rule), examples.
- `docs/features/drift/configuration.md` — reads no section of its own; documents the
  `language` and `lint.ignore` consumption of the underlying domains.
- `docs/features/drift/hooks.md` — no hook actions of its own; declared-view hooks
  failures are execution failures (exit 2).
- `docs/features/drift/api.md` — the facade signatures: `drift`, `compare_views`,
  `scope_entries`, `DriftEntry` (import line `from goga.drift import ...`).
- `docs/features/index.md` — the Drift row between Codegraph and Contract.
- `docs/cli/index.md` — the `goga drift` row (same position).

**Usages relevant to this task:**
- `convention`: formatting coverage extends to Python examples embedded in usage/docs —
  keep every code block ruff-clean.
- `drift-usage` / the `drift.md` command page: source material for the semantics and
  the CLI tables (self-contained pages; no cross-page dangling references).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.**

- [ ] **Code**: create the five `docs/features/drift/*.md` pages per the bullets above,
      mirroring the codegraph family page structure.
- [ ] **Code**: add the Drift row to `docs/features/index.md` (between Codegraph and
      Contract) and the `goga drift` row to `docs/cli/index.md`.
- [ ] **Verify**: every internal link resolves (the two index rows point at the new
      pages); the documented exit codes, field table, and synopsis match the
      implemented command (`python -m goga drift --help` diff against `cli.md`).
- [ ] Lint: `ruff format --check` unaffected (docs only); `goga lint` — 0 errors.
- [ ] **Commit gate**: full `pytest tests/ -x` green (docs cannot break it — verify
      anyway per policy); commit without `Co-Authored-By:` trailers.

### Task 8: Integration verification — the full-stack gate run (integration tests)

Final cross-entity verification over everything landed by Tasks 1–7: the registration
chain, the byte-identity guarantees, the three-outcome contract, and the complete
validation battery. No new production code — this task produces evidence and fixes
defects the evidence exposes (in the artifacts proven defective only).

**Usages relevant to this task:**
- `convention`: the validation-command table (all commands in the virtualenv).
- `cli-commands`: the 18-command registration reference — the final cross-check.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them.**

- [ ] **Live end-to-end smoke (REPL)**: in a scratch `tmp_path` project plant the
      four-kinds layout; run `.venv/bin/python -m goga drift` → exit 1 with the exact
      four-entry report; `goga drift --max-depth 0` → `[]`, exit 0; delete
      `.goga/config.yml` → exit 2 with the clean stderr line. Then run `goga drift`
      over the goga repository itself → the command completes; the report parses as
      JSON; the exit code is 0 or 1 (either is legitimate for the repo's own state —
      assert only completion, the valid JSON, and the code being in `{0, 1}`).
- [ ] **Facade checks**: `python -c "from goga.drift import DriftEntry, compare_views,
      drift, scope_entries"` and `python -c "from goga.commands import drift"` — both
      clean; `python -m goga drift --help` renders the documented surface.
- [ ] **Full battery**: `pytest tests/ -x` — green, including the untouched Task 1
      goldens (C2 proven end-to-end) and the adapted string-pinned suites.
- [ ] **Lint gates**: `ruff check goga/ tests/` and `ruff format --check goga/ tests/`
      — zero violations; `goga lint` — `cells: 89 errors: 0`.
- [ ] **Registry check**: `git status --short` — no untracked source left
      (`goga/drift/`, `goga/commands/drift/` committed; only intended modifications
      remain); the working tree contains no REPL scratch files.
- [ ] **Completion audit**: walk the plan's Completion Criteria checkbox by checkbox;
      any unmet criterion is a defect to fix now, not a note for later.
- [ ] **Commit gate**: commit the verification evidence/fixes (if any) with all gates
      green; no `Co-Authored-By:` trailers.

---

## Validation Commands

All commands run inside the virtualenv (Task 1 recreates it; system interpreter
`/opt/goga/bin/python` if the venv must be rebuilt ad hoc).

- `pytest tests/ -x`: Run all tests — the full battery; green at every commit gate.
- `pytest tests/drift/ tests/commands/drift/ -v`: The focused drift suites.
- `ruff check goga/ tests/`: Lint check — zero violations (CI gate).
- `ruff format --check goga/ tests/`: Format check — zero reformattings (CI gate).
- `goga lint`: Cell-level lint — 0 errors (89 cells — both drift manifests pre-exist
  and are already counted).
- `python -c "from goga.drift import DriftEntry, compare_views, drift, scope_entries"`:
  Verify the drift cell facade.
- `python -c "from goga.commands import drift"`: Verify the facade re-export chain.
- `python -m goga drift --help`: Verify the root registration and the documented
  surface.
- `git status --short`: Verify visibility — no untracked source, no REPL scratch.

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`schema.py`,
      `codegraph.py`, `render.py`, the wrapper `schema.py`/`codegraph.py`/`drift.py`,
      `goga/drift/{compare,drift}.py`, `goga/commands/drift/drift.py`).
- [ ] Every contract entity is accessible from its facade (`goga.schema`,
      `goga.codegraph`, `goga.commands.{schema,codegraph,drift}`, `goga.drift` with
      the four-name `__all__`).
- [ ] Properties and methods match the declared API (`DriftEntry` fields and kinds;
      the routine signatures including the `# noqa: B006` contract defaults).
- [ ] Descriptions are reflected in behavior — the complete-view comparison +
      union-survival scoping, the no-double-reporting rule, purity, determinism,
      read-only, error pass-through.
- [ ] Contract dependencies are met (the drift cell imports the two producers and the
      two record types exactly as declared; the two view producers stay mutually
      blind).
- [ ] Re-exports are accessible from the facade (`from goga.commands import drift`;
      `"drift"` in `goga.commands.__all__`; `app.add_command(drift)` after
      `codegraph`).
- [ ] The schema and codegraph CLI outputs are byte-identical to the pre-refactor
      outputs — the Task 1 goldens pass untouched (C2).
- [ ] The three-outcome exit contract holds (0/1/2) and the exit-2 deviation remains
      un-"aligned" (permanent per the ADR).
- [ ] Every coding task followed the TDD workflow (contract tests → code →
      verification → logic tests → debugging → re-verification → lint).
- [ ] Contract tests and logic tests cover facade, API, and behavior within each
      coding task; all 31 design test scenarios plus the string-pinned adaptation
      block are implemented.
- [ ] Integration verification (Task 8) ran the live end-to-end smoke and the full
      battery green.
- [ ] No package boundary was expanded; no new dependencies were added.
- [ ] `CODEMANIFEST` files were not modified (contract is read-only).
- [ ] All validation commands pass (`pytest tests/ -x`, both ruff gates,
      `goga lint` 0 errors, facade checks).
- [ ] Every Usages entry is mentioned in at least one task (`convention`, `click`,
      `beautiful_json`, `documents`; imported: `schema-usage`, `codegraph-usage`,
      `checkpoints`, `registering-hooks`, `records`, `stages`,
      `project-configuration`, `drift-usage`, `cli-commands`).
- [ ] Documentation collateral exists (`docs/features/drift/` five pages + the two
      index rows).
