# Plan: `codegraph`

<!-- Topic: `codegraph` — prospective cell graph for existing code.
     Source: `.goga/history/2026/codegraph/design.md` (reviewed and amended — see its
     "Applied Fixes" sections). This plan compiles the design into ralphex-executable tasks. -->

## Purpose

Implement the `codegraph` feature end-to-end: a prospective-cell-graph analyzer of existing
source code, wired as the `goga codegraph` CLI command.

After implementation the project provides:

- `goga.codegraph.facts` — the immutable record vocabulary (`Declaration`, `ImportRef`,
  `FileFacts`, `Unit`, `CellLink`, `CodegraphNode`);
- `goga.codegraph.analysis` — the three-stage pipeline (`collect_facts`, `derive_units`,
  `resolve_links`) over tree-sitter parses of five languages;
- `goga.codegraph` — the orchestrator `codegraph()`, `discover_sources()`, `render_graph()`
  producing the schema-parity JSON tree;
- `goga.commands.codegraph` — the click wrapper, re-exported through `goga.commands` and
  registered in `goga/cli.py` right after `schema`.

The most important gaps between contract and code: all four cells have CODEMANIFEST and
`.usages/` files but **zero implementation files**; the two modified cells (`goga/commands`,
`goga`) lack the import, embedding, and registration wiring; no tests exist.

Strategy: leaves-first TDD (facts → analysis → orchestrator → CLI wrapper → integration →
docs), one ralphex task per contract location, every task gated by the mandatory rules below.

## Mandatory Rules

<!-- Extracted verbatim from the project convention `.goga/usages/conventions.md`
     (the `convention` practice wired into all four new cells) and the language rules
     (`goga-cell-python`). These rules are MANDATORY for every task in this plan.
     Where a task restates a rule, the restatement is a reminder, not a replacement. -->

### Coding Style (strictly per `conventions.md`)

- **Python 3.10+ only**; all configuration lives in `pyproject.toml`.
- **Imports**: relative imports for ALL intra-package references inside `goga/`
  (`from .facts import Declaration`); absolute imports only for stdlib and third-party.
  Exception — tests: cross-directory references inside `tests/` use absolute imports rooted
  at the `tests` package (`from tests.conftest import helper`).
- **Data models**: stdlib `dataclasses` only; every model class uses `kw_only=True` and
  `frozen=True`; empty defaults for all fields (`""`, `False`, `[]`/`{}` via
  `default_factory`); `None` only for explicit absence of a value.
- **Docstrings**: Google style, MANDATORY for every public function, method, and class.
  First line starts with a capital letter and ends with a period. Include `Args` when the
  function accepts parameters, `Returns` when it returns a value, `Raises` when it raises
  beyond built-in types.
- **CLI command docstrings** (click callbacks): user-facing help — omit `Args`, `Returns`,
  `Raises` (Click auto-generates the options block; exit codes are Click's); keep the
  concise summary line; use the `\f` marker to hide developer notes from `--help`.
  Google-style docstrings still apply unchanged to every OTHER public function in a
  command module.
- **Code formatting**: inside function and method bodies, separate logical blocks by ONE
  blank line (initialization / conditions and loops / data preparation / processing /
  return).
- **Type hints**: mandatory everywhere (drives facade signature extraction). Allowed
  shapes: `str`, `int`, `float`, `bool`, `list[T]`, `dict[str, T]`, `T | None`.
  Forbidden: `*args`, `**kwargs`, bare `dict`, bare `list`.
- **Naming**: PascalCase classes, snake_case functions/methods/properties/modules.
- **Facade**: each cell's `__init__.py` exposes the contract API via `__all__`; only
  identifiers in `__all__` constitute the facade.
- **Dependencies**: no new third-party dependencies in this feature — `tree-sitter`
  (>=0.25.2), the five grammars, and `click` are already pinned in `pyproject.toml`;
  any hypothetical new library MUST go into `pyproject.toml` with a minimum version.
- **Logging**: none in v1 (the command's output contract is stdout-JSON-only); if logging
  is ever introduced, it MUST use `logging` with structured contextual metadata.

### Test Writing Rules (strictly per `conventions.md` — Testing)

- **Tools**: pytest (runner), ruff (lint + format of test code), pytest-cov (coverage).
  Test libraries live in `pyproject.toml` `[project.optional-dependencies]` under `test`.
- **Structure mirrors source directly**:
  `goga/codegraph/analysis/collect.py` → `tests/codegraph/analysis/test_collect.py`;
  every test directory MUST contain an `__init__.py`.
- **Fixtures**: local fixtures in `tests/<package>/conftest.py`, shared fixtures in
  `tests/conftest.py`. Shared fixtures already available: the autouse `_isolate_cwd`
  (pins the process CWD to `tmp_path`) and `_isolate_home` of `tests/conftest.py`, and
  `empty_package_environment` of `tests/commands/conftest.py` for CliRunner tests.
- **Integration tests** covering multiple packages go to `tests/integration/`
  (`test_<scenario>.py`).
- **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`
  (e.g. `test_complexity_with_empty_input`); grouping `class Test<Component>:` with
  docstrings.
- **Test types**: Unit — every public function/method/class, main scenario and typical
  data. Edge cases — empty inputs (`None`, `""`, `[]`, `{}`), boundary values (`0`,
  negative, very large), invalid types, expected exceptions via `pytest.raises`.
  Integration — only for interaction between modules/packages.
- **Boundary tests**: for thresholds, ranges, state transitions use
  `@pytest.mark.parametrize` with a table of values including each boundary.
- **Mocks**: pure logic — NO mocks; file I/O — the `tmp_path` fixture exclusively;
  subprocesses — `mock.patch` the call; external dependencies — `mock.patch` at the
  import point. Mock only at external boundaries; business-logic tests stay mock-free.
- **CLI testing**: invoke the command through the registered `app` via `CliRunner`
  (direct Python call — no subprocess), as the existing command tests do.
- **Self-documenting test names; keep comments minimal.**

### Linter and Formatter Enforcement (all development stages and local commits)

The following gates are MANDATORY at the end of EVERY task and BEFORE EVERY local commit.
A failing gate is an actionable defect, never acceptable noise. Local git hooks do NOT
enforce formatting (only the commit-msg/pre-push Co-Authored-By policy does) — the author
runs the formatter deliberately:

1. `ruff check goga/ tests/` — zero violations (CI gate, `.github/workflows/lint.yml`).
2. `ruff format --check goga/ tests/` — zero reformattings; run `ruff format goga/ tests/`
   when it reports diffs.
3. `goga lint` — cell-level lint, 0 errors over 87 cells.
4. Focused tests green, then `pytest tests/ -x` green (full battery).
5. Facade import checks green (`python -c "from goga.codegraph import codegraph"` etc.).
6. **Commit policy**: commit only with all gates green; commit messages MUST NOT contain
   `Co-Authored-By:` trailers (`.githooks/commit-msg` and `pre-push` reject them).
7. `CODEMANIFEST` files are READ-ONLY for the implementer — if code does not match the
   contract, fix the code, never the contract.

### REPL Cycle Rules (continuous interactive evaluation, hot reloading, migration to source)

The `convention` practice is wired into every cell for "Organizing the REPL development
cycle". Every coding task in this plan follows the same loop:

1. **Virtualenv first**: create the virtualenv if missing; every probe, test run, and lint
   run executes inside it.
2. **Probe before writing**: verify each non-trivial algorithm step interactively against
   real inputs — tree-sitter parse dumps of fixture sources, resolver walks over a
   `tmp_path` project, filter behavior against `goga/schema/schema.py` — BEFORE the
   verified snippet is written into a source file. Expected values in tests are grounded
   in live probe runs, never in recollection.
3. **Hot feedback after every edit**: immediately re-run the focused test file and the
   facade import check in the same virtualenv; iterate in small steps. A long-lived REPL
   session re-imports edited modules (`importlib.reload` or a fresh `python -c`) — never
   trust stale module state as evidence.
4. **Migrate verified code to source files**: REPL-verified snippets are migrated into the
   target `location` file with type hints, Google docstrings, relative imports, and
   convention formatting; REPL scratch never ships and is never referenced by source.
5. **Close the loop per task**: probe → implement (migrate) → focused tests → full battery
   → lint/format gates → commit (gates green).

## Context

### Contract Surface

**Entity: `Declaration`** (cell `goga/codegraph/facts`)
- Type: class (record)
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.codegraph.facts`
- Properties: `path -> Path` (defining file, relative to project root), `name -> str`
  (declaration name as written), `is_public -> bool` (public under language visibility
  rules)
- Semantic requirements: immutable data class per `convention`; frozen, `kw_only=True`
- Annotation context: one named code declaration found in a source file

**Entity: `ImportRef`** (cell `goga/codegraph/facts`)
- Type: class (record)
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.codegraph.facts`
- Properties: `source -> Path`, `specifier -> str` (raw origin string as written; empty
  for pure name usages), `names -> list[str]` (empty for wildcard imports and Python plain
  imports; the literal `default` marks a JavaScript default import), `is_relative -> bool`,
  `is_wildcard -> bool`
- Semantic requirements: immutable data class per `convention`
- Annotation context: one import statement or name usage collected from a source file

**Entity: `FileFacts`** (cell `goga/codegraph/facts`)
- Type: class (record)
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.codegraph.facts`
- Properties: `path -> Path`, `declarations -> list[Declaration]`,
  `imports -> list[ImportRef]`, `exports -> list[str]` (python `__all__`; javascript the
  exported names of export clauses plus the name declared by a named default export;
  empty when absent), `module -> str` (kotlin package; empty when absent)
- Semantic requirements: immutable data class per `convention`

**Entity: `Unit`** (cell `goga/codegraph/facts`)
- Type: class (record)
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.codegraph.facts`
- Properties: `path -> Path` (unit directory), `files -> list[Path]`,
  `facade -> list[str]` (sorted unique public type names), `is_cell -> bool`
- Semantic requirements: immutable data class per `convention`; `facade` sorted and
  duplicate-free

**Entity: `CellLink`** (cell `goga/codegraph/facts`)
- Type: class (record)
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.codegraph.facts`
- Properties: `source -> Path`, `target -> Path`, `types -> list[str]`
- Semantic requirements: immutable data class per `convention`; `types` sorted and
  duplicate-free

**Entity: `CodegraphNode`** (cell `goga/codegraph/facts`)
- Type: class (record)
- Declared `location`: `facts.py`
- Facade obligation: importable from `goga.codegraph.facts`
- Properties: `cell -> str`, `types -> list[str]`,
  `dependencies -> dict[str, list[str]]` (target cell path to imported facade types; no
  usages key), `children -> list[CodegraphNode]`
- Semantic requirements: immutable data class per `convention`; manifest-only fields never
  appear on a node

**Routine: `collect_facts(files: list[Path], language: str) -> facts: list[FileFacts]`**
(cell `goga/codegraph/analysis`)
- Declared `location`: `collect.py`
- Facade obligation: importable from `goga.codegraph.analysis`
- Semantic requirements: parse each file exactly once; fail closed on any ERROR/MISSING
  parse node (error names the file); `facts` order follows `files` order; wildcard import
  records no names; per-language declaration/import/export extraction per the algorithm in
  Task 2; one usage `ImportRef` per wildcard/plain/namespace import (review fix R1)
- Imported dependencies: `Declaration`, `ImportRef`, `FileFacts` from `goga/codegraph/facts`

**Routine: `derive_units(facts: list[FileFacts], language: str) -> units: list[Unit]`**
(cell `goga/codegraph/analysis`)
- Declared `location`: `units.py`
- Facade obligation: importable from `goga.codegraph.analysis`
- Semantic requirements: pure grouping over facts (no file reads); deterministic path
  order; facade exactly per language rules; empty-facade unit survives with
  `is_cell=False`
- Imported dependencies: `Unit` from `goga/codegraph/facts`

**Routine: `resolve_links(units: list[Unit], facts: list[FileFacts], language: str, root: Path) -> links: list[CellLink]`**
(cell `goga/codegraph/analysis`)
- Declared `location`: `resolve.py`
- Facade obligation: importable from `goga.codegraph.analysis`
- Semantic requirements: project-wide index first, then resolve; exact origins per
  language rules; expansion reads usage `ImportRef`s (no re-parsing); unresolvable /
  external / self / non-cell-source names produce no link and no error; one `CellLink`
  per unit pair with sorted unique types
- Imported dependencies: `Unit`, `CellLink`, `FileFacts`, `ImportRef` from
  `goga/codegraph/facts`

**Routine: `codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> json: str`**
(cell `goga/codegraph`)
- Declared `location`: `codegraph.py`
- Facade obligation: importable from `goga.codegraph`
- Semantic requirements: load config → validate language (python/golang/javascript/kotlin/
  swift) → ignore from `lint` section (`[]` when absent) → `discover_sources` → the three
  analysis stages in order → `render_graph`; deterministic and idempotent (byte-identical
  output); read-only; no environment reads; never mutate `cells`/`depends_on`
- Imported dependencies: `Unit`, `CellLink`, `CodegraphNode` + `records` usage from
  `goga/codegraph/facts`; `collect_facts`, `derive_units`, `resolve_links` + `stages`
  usage from `goga/codegraph/analysis`; `load_project_config`, `ProjectConfig`,
  `LintConfig` + `project-configuration` usage from `goga/config`

**Routine: `discover_sources(language: str, ignore: list[str]) -> files: list[Path]`**
(cell `goga/codegraph`)
- Declared `location`: `discovery.py`
- Facade obligation: importable from `goga.codegraph`
- Semantic requirements: deterministic walk from root; skip exact relative ignored paths
  (same mechanics as lint); skip idiomatic test files per language; keep the primary
  extension; paths only — no file content reads; the exclusion list is exactly the given
  list (no built-ins)

**Routine: `render_graph(units: list[Unit], links: list[CellLink], cells: list[str], max_depth: int | None, depends_on: list[str]) -> json: str`**
(cell `goga/codegraph`)
- Declared `location`: `render.py`
- Facade obligation: importable from `goga.codegraph`
- Semantic requirements: nest by path with structural compression (only cell units carry
  nodes; non-cell units survive as ancestors); node fields exactly `cell, types,
  dependencies, children`; filters in order `cells` → `depends_on` → `max_depth` with
  exact `goga schema` parity; serialize via `beautiful_json`; empty forest → `"[]"`

**Routine: `codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])`**
(cell `goga/commands/codegraph` — CLI wrapper)
- Declared `location`: `codegraph.py`
- Facade obligation: importable from `goga.commands.codegraph` and re-exported by
  `goga.commands`
- Semantic requirements: click surface identical to the schema command (CELLS variadic,
  `--max-depth` int, `--depends-on` repeatable); delegates to `codegraph_logic`; any
  exception → stderr message + exit 1, empty stdout, no traceback; success → JSON on
  stdout, exit 0
- Imported dependencies: `codegraph AS codegraph_logic` + `codegraph-usage` from
  `goga/codegraph`

### Interaction and Data Flow

Interaction diagram (verbatim from the design):

```
                        .goga/config.yml
                              │ load_project_config() -> ProjectConfig
                              │   .language, .lint (LintConfig | None)
                              ▼
goga/commands/codegraph ── codegraph_logic(cells, max_depth, depends_on)
  (click wrapper)             │
      │ click.echo(json)      ▼
      │            goga/codegraph (codegraph.py orchestrator)
      │                     │ discover_sources(language, ignore) -> files
      │                     │        (discovery.py)
      │                     ▼
      │            collect_facts(files, language) -> list[FileFacts]
      │                     │        (analysis/collect.py, tree-sitter)
      │                     ▼
      │            derive_units(facts, language) -> list[Unit]
      │                     │        (analysis/units.py)
      │                     ▼
      │            resolve_links(units, facts, language, root) -> list[CellLink]
      │                     │        (analysis/resolve.py)
      │                     ▼
      │            render_graph(units, links, cells, max_depth, depends_on) -> json
      │                     │        (render.py, CodegraphNode, beautiful_json)
      └─────────────────────┘
```

Data flows (verbatim from the design):

- **Config flow**: `load_project_config()` reads `.goga/config.yml` from cwd →
  `ProjectConfig.language: str` and `ProjectConfig.lint: LintConfig | None`
  (`.ignore: list[str]`, `[]` when the key is absent). Passed as scalars downstream;
  the config object does not travel past the orchestrator.
- **Discovery flow**: `files: list[Path]` — relative paths, sorted deterministic walk
  order; produced from paths only (no file reads).
- **Facts flow**: one `FileFacts` per input file, input order preserved; `Declaration`/
  `ImportRef` nested inside; `exports` per the amended semantics; `module` non-empty only
  for Kotlin (package).
- **Units flow**: flat `list[Unit]` sorted by path; nesting is derivable from paths and
  is rebuilt by the renderer.
- **Links flow**: one `CellLink` per (importing unit, defining unit) pair, `types` sorted
  unique facade names.
- **Output flow**: `render_graph` builds `CodegraphNode` trees, applies filters,
  serializes with `json.dumps(indent=4, sort_keys=True, ensure_ascii=False)`; the CLI
  echoes the document to stdout.

Verified chains (design Code Stack Trace — the checkpoints every task preserves):
config boundary (absent config → `FileNotFoundError`; absent `lint` → `None` → `ignore
[]`); language naming parity (`golang`, `javascript` — never `go`/`js`); stage type flow
(`list[FileFacts]` → `list[Unit]` → `list[CellLink]`); error propagation (three failure
modes reach the CLI wrapper, which renders them as clean stderr failures); filter parity
with `goga/schema/schema.py` (`_filter_tree`/`_filter_by_depends_on`/`_prune_depth`,
ancestor skeleton, root depth 0, `"[]"` early return); determinism end-to-end.

### Re-exports

- `->codegraph: {}` in `goga/commands/CODEMANIFEST`
  - Name: `codegraph`
  - Source: `Imports` entry `codegraph` from `goga/commands/codegraph`
  - Facade obligation: `from goga.commands import codegraph` binds the same click command
    object; `"codegraph"` in `goga.commands.__all__`
  - Hierarchy constraint: `goga/commands/codegraph` is a subcell — satisfied

### Usages Context

- `convention` (`.goga/usages/conventions.md`) — mandatory engineering/testing conventions
  for all Python code: relative imports, frozen `kw_only` dataclasses, Google docstrings,
  test structure, CLI docstring rules. Fully transcribed into **Mandatory Rules** above;
  relevant to every task.
- `tree-sitter-python` / `tree-sitter-go` / `tree-sitter-js` / `tree-sitter-kotlin` /
  `tree-sitter-swift` (`.goga/usages/cooks/tree-sitter-*.md`) — parser setup
  (`Language(pkg.language())` + `Parser`) and the per-grammar node-type inventory. Used by
  `collect_facts` (Task 2). Kotlin names are extracted positionally (plain `identifier`
  children — grammar 1.1.0 has no named fields for them).
- `beautiful_json` (`.goga/usages/cooks/beautiful_json.md`) — canonical JSON form:
  `json.dumps(..., indent=4, sort_keys=True, ensure_ascii=False)`. Used by `render_graph`
  (Task 6).
- `click` (`.goga/usages/cooks/click.md`) — command surface construction and clean error
  rendering (`click.echo`, `ctx.exit(1)`, no `sys.exit` inside commands). Used by the CLI
  wrapper (Task 8).

### Imported Usages

- `records` from `goga/codegraph/facts` — construction conventions for every fact record
  (kw-only, immutable, sorted-unique facades/types, usage-ref preconditions).
  Source: `goga/codegraph/facts/.usages/records.md`. Used in Tasks 1–4, 6.
- `stages` from `goga/codegraph/analysis` — stage order, completeness requirement,
  `root = Path.cwd()`, failure behavior for the caller.
  Source: `goga/codegraph/analysis/.usages/stages.md`. Used in Task 7.
- `project-configuration` from `goga/config` — loader semantics: mandatory
  `.goga/config.yml` (`FileNotFoundError` when absent/empty), `lint` absent → `None`,
  `LintConfig.ignore` exact-path list.
  Source: `goga/config/.usages/project-configuration.md`. Used in Task 7.
- `codegraph-usage` from `goga/codegraph` — output node format, guarantees
  (deterministic, read-only, purely descriptive), three failure modes behind the CLI.
  Source: `goga/codegraph/.usages/codegraph-usage.md`. Used in Tasks 7–8.

### Local Usages

All three cell-level practice files already exist on this branch and the design review
confirmed them current — **no creation or update tasks**:

- `goga/codegraph/facts/.usages/records.md` — status: current (includes the amended
  `names` conventions and the usage-ref preconditions of review fixes R1).
- `goga/codegraph/analysis/.usages/stages.md` — status: current.
- `goga/codegraph/.usages/codegraph-usage.md` — status: current.
- `goga/commands/.usages/cli-commands.md` — status: current (17 commands, codegraph row
  and registration present).
- `goga/commands/codegraph` has no `.usages/` directory by design (consumer documentation
  lives in `codegraph-usage`).

### External Dependencies

- `tree-sitter>=0.25.2` and the five pinned grammars (`tree-sitter-python>=0.25.0`,
  `tree-sitter-go>=0.25.0`, `tree-sitter-javascript>=0.25.0`,
  `tree-sitter-kotlin>=1.1.0`, `tree-sitter-swift>=0.7.2`) — already in `pyproject.toml`.
- `click>=8.0` — already pinned.
- `goga/config` loader — consumed as-is via `load_project_config`.
- Tools: pytest, pytest-cov, ruff (test extra); `goga lint` and `goga schema` (project's
  own gates).
- No new dependencies are introduced by this plan.

## Facts

- The four new cells exist with CODEMANIFEST and `.usages/` files only — no `__init__.py`,
  no implementation files.
- Language names accepted by the orchestrator are exactly `python`, `golang`,
  `javascript`, `kotlin`, `swift` — never `go`/`js` (parity with `goga config language`).
- Each file is read and parsed exactly once per run; records are reused by later stages
  (the once-per-run parse contract).
- Determinism contract: sorted walk, input-order facts, path-sorted units and nodes,
  sorted unique facades/types/dependency keys, `sort_keys=True`; no environment variables,
  no clocks, no randomness; identical inputs produce byte-identical output.
- The records are frozen `kw_only=True` dataclasses with empty defaults; sequence
  arguments are copied on construction (no caller-list aliasing).
- Swift usage refs carry `specifier=""`; a JavaScript default import carries the literal
  name `default`; a Python plain import carries no `names` (CODEMANIFEST, amended).
- Kotlin grammar 1.1.0 exposes plain `identifier` name children and `import` /
  `package_header` nodes (review fix R2 — the old node names do not exist).
- Python relative-import specifiers keep the leading dots exactly as written (review fix
  R3); the resolver derives the level from them.
- JavaScript `default` is mapped element-wise to the resolved file's default-exported
  name (review fix R4).
- A link is produced only when the importing unit is a cell (review fixes R5, R7).
- Schema filter parity: `cells` (matched + ancestor chain), `depends_on` (own or
  descendant dependency, ancestor skeleton), `max_depth` (nodes at depth >= max_depth lose
  children; root depth 0; `max_depth=0` empties every root's children) (review fix R6).
- Known v1 limitations (documented, not fixed): aliased plain imports do not expand;
  JS bare/workspace specifiers and CommonJS are external; GOPATH-mode Go is external;
  augmented `__all__ +=` is not read.
- CI gates: `ruff check goga/ tests/`, `ruff format --check goga/ tests/`, pytest matrix
  3.10–3.14. Local gates add `goga lint` and `goga schema`.
- Shared test infrastructure: autouse `_isolate_cwd` / `_isolate_home`
  (`tests/conftest.py`; `cwd` there is a context manager, not a fixture),
  `empty_package_environment` (`tests/commands/conftest.py`).

## Gap Analysis

- **Missing contract entities**: all 13 — six records, three analysis stages, three
  orchestrator-cell routines, one CLI wrapper (implementation files do not exist).
- **Missing facade exposure**: `goga/codegraph/__init__.py`,
  `goga/codegraph/facts/__init__.py`, `goga/codegraph/analysis/__init__.py`,
  `goga/commands/codegraph/__init__.py` — none exist; `goga/commands/__init__.py` lacks
  the `codegraph` import and `__all__` entry.
- **Incorrect `location` placement**: none (nothing implemented yet).
- **API mismatches**: none yet (greenfield).
- **Behavioral mismatches**: none yet (greenfield).
- **Existing code that can be reused**: `goga/contract/<lang>` modules — the module-level
  `Language(pkg.language())` + `Parser(...)` idiom and `node_text` decoding;
  `goga/ast/ast.py:92-108` — the normpath ignore-mechanics reference for
  `discover_sources`; `goga/schema/schema.py` `_filter_tree` / `_filter_by_depends_on` /
  `_prune_depth` — the semantic reference for `render_graph` parity;
  `goga/commands/schema/schema.py` — the reference click surface for the wrapper;
  `goga/config` loader — consumed as-is.
- **Test coverage gaps**: no `tests/codegraph/**`, no `tests/commands/codegraph/`;
  `tests/commands/test_commands_facade.py` lacks the codegraph re-export test.
- **Missing visibility in workspace or git**: `goga/codegraph/` and
  `goga/commands/codegraph/` are untracked (`??` in git status) — they must be committed
  with the implementation.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting
> the next. Within each coding task, contract tests are written first (TDD workflow).
> Order: `goga/codegraph/facts` → `goga/codegraph/analysis` → `goga/codegraph` →
> `goga/commands/codegraph` (+ wiring) → integration → docs.
>
> **Facade assembly note**: per-cell `__init__.py` facades are created by the first task
> that lands an entity of the cell and extended by each subsequent task (final state
> documented per task). This keeps every task independently green — no skeleton modules
> and no facade importing non-existent names.
>
> **Mandatory Rules apply to every task** (style, tests, lint/format gates, REPL cycle,
> commit policy). Each task's gates checkbox restates them; the rules section is
> authoritative.

### Task 1: Facts records — the six dataclasses and the `facts` cell facade (TDD)

Implement the leaf cell `goga/codegraph/facts`: the package, the six immutable records in
`facts.py`, and the facade `__init__.py` re-exporting all six via `__all__`. The records
carry data only — no behavior, no methods beyond the dataclass machinery. Construction
rules (verbatim from the design):

```
1. Construct via keyword-only arguments only.
2. Copy every sequence argument into a fresh list (no aliasing of caller data).
3. No post-construction mutation — frozen; derive new records instead.
4. Defaults per the conventions: str fields "", list fields [], bool fields False,
   CodegraphNode.children [], dependencies {}.
```

Signatures (from `goga/codegraph/facts/CODEMANIFEST`):
`Declaration(path: Path, name: str, is_public: bool)`,
`ImportRef(source: Path, specifier: str, names: list[str], is_relative: bool, is_wildcard: bool)`,
`FileFacts(path: Path, declarations: list[Declaration], imports: list[ImportRef], exports: list[str], module: str)`,
`Unit(path: Path, files: list[Path], facade: list[str], is_cell: bool)`,
`CellLink(source: Path, target: Path, types: list[str])`,
`CodegraphNode(cell: str, types: list[str], dependencies: dict[str, list[str]], children: list[CodegraphNode])`.

All fields get empty defaults per the conventions; `list`/`dict` fields via
`default_factory`. Facade import block (reference form, from `records.md`):

```python
from goga.codegraph.facts import (
    CellLink,
    CodegraphNode,
    Declaration,
    FileFacts,
    ImportRef,
    Unit,
)
```

**Usages relevant to this task:**
- `convention`: data-model rules — stdlib dataclasses, `kw_only=True`, frozen, empty
  defaults; relative imports inside `goga`; Google docstrings; test structure mirroring.
- `records` (imported usage of this very cell): construction preconditions — paths
  relative to project root, `is_public` decided before construction, the `names`
  conventions (wildcard/plain → `[]`; JS default → `["default"]`; pure usage → empty
  `specifier`), sorted-unique `facade`/`types`, immutability.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 1 — facts records`) in the
      session log.
- [x] **Contract tests** (expected to fail now): create
      `tests/codegraph/__init__.py`, `tests/codegraph/facts/__init__.py`, and
      `tests/codegraph/facts/test_facts.py` with a `class TestFactsRecords:` asserting —
      all six names importable from `goga.codegraph.facts`; `goga.codegraph.facts.__all__`
      equals the sorted six names; every class is a frozen dataclass
      (`dataclasses.is_dataclass` + `__dataclass_params__.frozen`); constructing
      `Declaration(path=Path("a"), name="x", is_public=False)` succeeds.
- [x] **REPL probe**: in the virtualenv REPL verify the frozen-kw-only pattern once
      against a scratch dataclass (frozen forbids field reassignment; positional
      construction raises `TypeError`) — then migrate the verified pattern into
      `facts.py`.
- [x] **Code**: create `goga/codegraph/facts/facts.py` with
      `from __future__ import annotations`, relative-safe stdlib imports, and the six
      `@dataclass(frozen=True, kw_only=True)` classes, each with a Google-style class
      docstring; sequence fields copied on construction
      (`self.x = list(x)` in `__post_init__` or equivalent) and `default_factory=list` /
      `default_factory=dict` defaults; empty-string/`False` scalar defaults.
- [x] **Code**: create `goga/codegraph/facts/__init__.py` — relative imports of the six
      records + `__all__` with exactly the six names (final facade state of this cell).
- [x] **Interface verification**: `python -c "from goga.codegraph.facts import CellLink, CodegraphNode, Declaration, FileFacts, ImportRef, Unit"` —
      must pass; `pytest tests/codegraph/facts/test_facts.py -v` — contract tests green.
- [x] **Logic tests**: extend `tests/codegraph/facts/test_facts.py` with
      `test_facts_records_frozen_kw_only` — design scenario, verbatim:

      **Setup**: import all six record classes from `goga.codegraph.facts`.

      **Input**: `Unit(path=Path("a"), files=[], facade=["X"], is_cell=True)`; then
      `unit.facade.append("Y")`.

      **Trace**:
      ```
      Unit(path=..., files=[], facade=["X"], is_cell=True)   # kw-only construction
        → returns record
      unit.facade.append("Y")
        → not blocked mechanically: frozen forbids field reassignment, not list
          mutation; list-field contents are immutable by convention (build new
          records); the construction-time copy guards caller-list aliasing only
      Unit(path=Path("a"))                                    # missing kwargs
        → TypeError (kw_only enforced)
      Declaration(path=Path("a"), name="x", is_public=False).is_public = True
        → dataclasses.FrozenInstanceError
      ```

      **Assertions**:
      ```
      pytest.raises(TypeError): Unit(path=Path("a"))
      pytest.raises(dataclasses.FrozenInstanceError): record.is_public = True
      source_list = []; FileFacts(path=..., declarations=[], imports=source_list, ...);
      source_list.append(x) → len(facts.imports) == 0        # defensive copy
      dataclasses.is_dataclass(Unit) and Unit.__dataclass_params__.frozen is True
      ```
- [x] **Debugging**: `pytest tests/codegraph/facts/ -x` — fix implementation code until
      all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: facade `__all__` exact; signatures match the
      CODEMANIFEST declarations; records carry data only.
- [x] **Lint** (STEP 7): `ruff check goga/codegraph tests/codegraph` then
      `ruff format --check goga/codegraph tests/codegraph` (run `ruff format` on diffs);
      `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: full `pytest tests/ -x` green; `ruff check goga/ tests/` and
      `ruff format --check goga/ tests/` clean; commit without `Co-Authored-By` trailers.

### Task 2: `collect_facts` — single-pass tree-sitter extraction for five languages (TDD)

Implement `collect_facts(files: list[Path], language: str) -> facts: list[FileFacts]` in
`goga/codegraph/analysis/collect.py` (new cell `goga/codegraph/analysis`), plus the cell
facade `goga/codegraph/analysis/__init__.py` re-exporting `collect_facts` (Tasks 3–4
append the other two stages; final state re-exports all three, per `stages.md`).

Core algorithm (verbatim from the design):

```
1. parser := lazy singleton for `language`
   (Language(tree_sitter_<pkg>.language()) + Parser — module-level cache dict,
   one grammar loaded per process; idiom per goga/contract/<lang> modules)
2. FOR file IN files (input order):
   1. source := file.read_bytes()                        # exactly one read
   2. tree := parser.parse(source)                       # exactly one parse
   3. IF tree contains any node with type "ERROR" or node.is_missing:
      raise ValueError(f"unparseable source file: {file}")   # fail closed
   4. declarations, imports, exports, module := <language extractor>(tree, file)
   5. facts.append(FileFacts(path=file, ...))            # fresh lists
```

Per-language extractors (top-level = direct children of `root_node`; unwrap
`decorated_definition` (python) to its inner definition) — verbatim from the design:

- **python**
  - Declarations: `function_definition` / `class_definition` → name via
    `child_by_field_name("name")`; `is_public = not name.startswith("_")`.
  - In a package `__init__.py` additionally every top-level bound name: import bindings
    (`import a.b` → `a`; `import a.b as c` → `c`; `from m import x, y as z` → `x`, `z`),
    and assignment targets (`assignment.left` → identifier, or each identifier of a
    tuple target). Each bound name not already recorded →
    `Declaration(is_public = not name.startswith("_"))`.
  - Imports: `import_statement` → per child `dotted_name`/`aliased_import`:
    `ImportRef(specifier=<full dotted text>, names=[], is_relative=False,
    is_wildcard=False)`. `import_from_statement` → `module_name` field: `dotted_name`
    (absolute) or `relative_import` — for a relative import the specifier keeps the
    leading dots exactly as written (`..util`; `.` for a bare `from . import x`),
    `is_relative=True`; the resolver derives the level from the leading dots (review fix
    R3); names field: per `dotted_name` the imported (pre-`as`) name, per
    `aliased_import` the original name; `wildcard_import` → `names=[], is_wildcard=True`.
  - Exports: top-level `assignment` with left identifier `__all__` and right a string
    list → decoded elements, as-written order, deduplicated. (Augmented `__all__ += [...]`
    is not read in v1.)
  - Usage refs (review fix R1): one per plain import —
    `ImportRef(specifier=<the import's specifier>, names=<member names accessed through
    the import's root binding>, is_relative=False, is_wildcard=False)` (maximal attribute
    chains whose first segment is the root binding; the first segment after the prefix is
    the used name); one per wildcard import — `names` = every used identifier of the file
    outside import statements (generous collection). The base import keeps `names=[]`;
    only the usage ref carries names. An aliased plain import records no usage ref (known
    v1 limitation).
- **golang**
  - Declarations (package scope only): `function_declaration` (name); `type_spec` inside
    each `type_declaration` (name); `var_spec` inside `var_declaration` and `const_spec`
    inside `const_declaration` (name). `is_public = name[:1].isupper()`.
    `method_declaration` is NOT recorded — a method name is receiver-scoped, not a
    package-level identifier.
  - Imports: `import_declaration` → per `import_spec`: path =
    `interpreted_string_literal` text without quotes → `ImportRef(specifier=path,
    names=[], is_relative=False, is_wildcard=False)`.
  - Usage refs (review fix R1): one per import — `ImportRef(specifier=path, names=<member
    names accessed through the implicit local binding — the last path segment>,
    is_relative=False, is_wildcard=False)`, from `selector_expression` chains rooted at
    the binding. An aliased import records no usage ref (known v1 limitation).
  - Exports: none — `[]`.
- **javascript** (ESM only)
  - Declarations: top-level declarations of the five kinds (`function_declaration`,
    `class_declaration`, `generator_function_declaration`, `lexical_declaration`,
    `variable_declaration`); name via `name` field / first `variable_declarator`
    identifier. `is_public = True` iff exported: `export_statement` wrapping the
    declaration, or the name appears as an exported specifier in an `export_clause`.
    Anonymous default exports record nothing.
  - Imports: `import_statement` → source string without quotes; `is_relative =
    specifier.startswith(".") or specifier.startswith("/")`. Clause: default identifier →
    `names=["default"]`; named imports → the imported (pre-`as`) names;
    `namespace_import` → `names=[], is_wildcard=True`. Mixed clauses
    (`import d, { a } from ...`) → one `ImportRef`, `names=["default", "a"]`.
  - Exports: `export_clause` → the exported (post-`as`) specifier names;
    `export default <named declaration>` → that declaration's name; both appended in
    source order, deduplicated.
  - Usage refs (review fix R1): one per namespace import —
    `ImportRef(specifier=<the import's specifier>, names=<member names accessed through
    the namespace alias>, is_relative=True|False as the base, is_wildcard=True)` from
    `member_expression` chains rooted at the alias.
- **kotlin** (node inventory per the amended cook — grammar 1.1.0; review fix R2)
  - Declarations: top-level `function_declaration`, `class_declaration`,
    `object_declaration`, `type_alias`, `property_declaration`; name from the direct
    `identifier` child (positional — the pinned tree-sitter-kotlin 1.1.0 exposes plain
    `identifier` name children and most nodes have no named fields; a
    `property_declaration`'s name is the `identifier` inside its `variable_declaration`).
    `is_public = True` iff the `modifiers` container child carries no
    `visibility_modifier` or the modifier is `public` (implicit-or-explicit public).
  - Imports: top-level `import` nodes — specifier = the `qualified_identifier` text; a
    trailing anonymous `*` sibling (after the final `.`) marks `is_wildcard=True,
    names=[]`; otherwise `names=[last segment of the qualified identifier]` (an
    `as <identifier>` suffix — an import alias — does not change the origin).
    `is_relative=False`. `package_header` → `module` = its `qualified_identifier` text.
  - Usage refs (review fix R1): one per wildcard import —
    `ImportRef(specifier=<the import's specifier>, names=<every used identifier of the
    file>, is_relative=False, is_wildcard=True)` (generous collection).
- **swift**
  - Declarations: top-level `function_declaration`, `class_declaration` (kinds
    actor/class/enum/struct — an `extension` declares no new name and is not recorded,
    nor are its members), `protocol_declaration`, `init_declaration`,
    `property_declaration`, `typealias_declaration`; name via `name` field.
    `is_public = True` iff a `visibility_modifier` child is `public` or `open`.
  - Imports: `import_declaration` → `ImportRef(specifier=<module identifier text>,
    names=[], is_relative=False, is_wildcard=False)`. Additionally one usage ref per
    file: `ImportRef(specifier="", names=sorted unique texts of every type_identifier
    outside import declarations, is_relative=False, is_wildcard=False)` — generous
    collection is safe: declaration names resolve to the own unit (self-link dropped),
    external names never resolve, ambiguous names are dropped by the uniqueness rule.
  - Exports: none — `[]`.

Errors: `ValueError` naming the file on any `ERROR`/`MISSING` node. Edge cases: empty
file → valid parse, all-empty facts; file order preserved regardless of walk grouping; a
wildcard import never records names; `__init__.py` bindings include imported names (they
are facade candidates).

**Usages relevant to this task:**
- `convention`: style rules (relative imports `from ..facts import ...`, Google
  docstrings, type hints); test rules (mirrored test file, `tmp_path` fixtures, no mocks
  for pure logic).
- `tree-sitter-python` / `tree-sitter-go` / `tree-sitter-js` / `tree-sitter-kotlin` /
  `tree-sitter-swift`: parser setup `Language(pkg.language())` + `Parser`, and the exact
  node inventories used above — traversal via `node.children`,
  `child_by_field_name(...)`, `node.text.decode("utf-8")`.
- `records` (from `goga/codegraph/facts`): construct every `Declaration`/`ImportRef`/
  `FileFacts` kw-only with the preconditions above.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 2 — collect_facts`).
- [x] **Contract tests** (expected to fail now): create `tests/codegraph/analysis/__init__.py`
      and `tests/codegraph/analysis/test_collect.py` with a `class TestCollectFacts:`
      asserting — `collect_facts` importable from `goga.codegraph.analysis`; callable as
      `collect_facts(files=[Path(...)], language="python")` returning `list[FileFacts]`.
- [x] **REPL probe (per language, hot loop)**: in the virtualenv REPL, parse each
      fixture source below once with its grammar and dump the node tree
      (`tree.root_node.sexp()` / child walk); confirm the node inventories above before
      writing each extractor — expected extractor outputs are grounded in these dumps,
      not in recollection.
- [x] **Code**: create `goga/codegraph/analysis/collect.py` — lazy per-language parser
      singleton (module-level dict keyed by language; `Language(...)` + `Parser` idiom of
      `goga/contract/<lang>` modules); the parse loop with the fail-closed ERROR/MISSING
      check; one private extractor function per language returning
      `(declarations, imports, exports, module)`; public `collect_facts` with Google
      docstring (`Args`/`Returns`/`Raises`).
- [x] **Code**: create `goga/codegraph/analysis/__init__.py` re-exporting `collect_facts`
      (`__all__ = ["collect_facts"]` — extended by Tasks 3–4).
- [x] **Interface verification**: `python -c "from goga.codegraph.analysis import collect_facts"` —
      must pass; `pytest tests/codegraph/analysis/test_collect.py -v` — contract tests
      green.
- [x] **Logic tests** (design scenarios, verbatim — one test function each, fixtures on
      `tmp_path`, cwd pinned by the autouse `_isolate_cwd`):

      1. `test_collect_facts_python_declarations_imports_and_init_bindings` —
         **Setup**: `tmp_path/pkg/__init__.py` =
         ```python
         from .core import Engine
         from ..util import helper as util_helper
         import os
         import json.path

         VERSION = "1.0"
         _NAME = "hidden"


         def run(task: str) -> int:
             return 0
         ```
         **Input**: `collect_facts([Path("pkg/__init__.py")], "python")` (cwd pinned to
         `tmp_path`).
         **Trace**:
         ```
         collect_facts([...], "python")
           → read+parse once
           → declarations: run (public), Engine (imported binding, public),
             util_helper (public), os (public), json (public), VERSION (public),
             _NAME (private)
           → imports: "..util"→names ["helper"] is_relative True;
             "os"→names [] ; "json.path"→names []
           → exports: []            # no __all__ assignment
           → FileFacts(path=Path("pkg/__init__.py"), ...)
         ```
         **Assertions**:
         ```
         len(facts) == 1 and facts[0].path == Path("pkg/__init__.py")
         names = {d.name: d.is_public for d in facts[0].declarations}
         names["run"] is True and names["_NAME"] is False and names["VERSION"] is True
         imp = {(i.specifier, tuple(i.names), i.is_relative, i.is_wildcard) for i in facts[0].imports}
         ("..util", ("helper",), True, False) in imp and ("os", (), False, False) in imp
         ("json.path", (), False, False) in imp
         facts[0].exports == [] and facts[0].module == ""
         ```
      2. `test_collect_facts_golang_exported_package_scope_only` —
         **Setup**: `tmp_path/store/user.go` =
         ```go
         package store

         type User struct{ Name string }

         func NewUser() *User { return nil }

         func (u *User) Rename() {}

         var Default = 1

         const Limit = 9

         func internal() {}
         ```
         **Input**: `collect_facts([Path("store/user.go")], "golang")`.
         **Trace**:
         ```
         parse → package-scope declarations: type User (exported), func NewUser (exported),
           var Default (exported), const Limit (exported), func internal (private)
           → method Rename NOT recorded (receiver-scoped)
           → imports: none; exports: []; module: ""
         ```
         **Assertions**:
         ```
         public_names = {d.name for d in facts[0].declarations if d.is_public}
         public_names == {"User", "NewUser", "Default", "Limit"}
         all_names = {d.name for d in facts[0].declarations}
         "Rename" not in all_names
         any(d.name == "internal" and d.is_public is False for d in facts[0].declarations)
         ```
      3. `test_collect_facts_javascript_default_pseudo_and_clause_exports` —
         **Setup**: `tmp_path/api/index.js` =
         ```javascript
         import render, { query as q, mutate } from "../db/index.js";
         import * as util from "./util.js";

         export function list() {}
         export default function render2() {}
         export { hidden as public2 };
         ```
         **Input**: `collect_facts([Path("api/index.js")], "javascript")`.
         **Trace**:
         ```
         parse → declarations: list (public), render2 (public)
           # hidden appears only as an export-clause specifier — undeclared, no Declaration
           → imports: "../db/index.js" names ["default", "query", "mutate"], is_relative True;
                      "./util.js" names [] is_wildcard True, is_relative True
           → exports: ["public2", "render2"]          # clause name then default name
         ```
         **Assertions**:
         ```
         default_import = next(i for i in facts[0].imports if i.names and i.names[0] == "default")
         default_import.is_relative is True and "mutate" in default_import.names
         namespace = next(i for i in facts[0].imports if i.is_wildcard)
         namespace.names == [] and namespace.specifier == "./util.js"
         facts[0].exports == ["public2", "render2"]
         {d.name for d in facts[0].declarations if d.is_public} == {"list", "render2"}
         ```
      4. `test_collect_facts_kotlin_package_and_visibility` —
         **Setup**: `tmp_path/com/example/tool.kt` =
         ```kotlin
         package com.example

         import com.other.Thing
         import com.other.*

         public class Tool
         internal class Hidden
         fun helper() {}
         ```
         **Input**: `collect_facts([Path("com/example/tool.kt")], "kotlin")`.
         **Trace**:
         ```
         parse → declarations: Tool (public), Hidden (private-ish: is_public False),
           helper (implicit public → True)
           → imports: "com.other.Thing" names ["Thing"]; "com.other" wildcard
           → module: "com.example"
         ```
         **Assertions**:
         ```
         facts[0].module == "com.example"
         {name for d in facts[0].declarations if d.is_public} == {"Tool", "helper"}
         "Hidden" in {d.name for d in facts[0].declarations if not d.is_public}
         any(i.specifier == "com.other.Thing" and i.names == ["Thing"] for i in facts[0].imports)
         any(i.specifier == "com.other" and i.is_wildcard for i in facts[0].imports)
         ```
      5. `test_collect_facts_swift_public_open_only_and_used_names` —
         **Setup**: `tmp_path/App/main.swift` =
         ```swift
         import Foundation

         public struct Client {}
         open class Base {}
         internal struct Hidden {}
         struct ImplicitInternal {}

         func use(_ c: Client, _ b: Base) {}
         ```
         **Input**: `collect_facts([Path("App/main.swift")], "swift")`.
         **Trace**:
         ```
         parse → declarations: Client (open? public → True), Base (open → True),
           Hidden (False), ImplicitInternal (False)
           → imports: ("Foundation", [], False, False) module ref
                      + ("", ["Base", "Client"], False, False) usage ref (sorted unique)
           → exports: []
         ```
         **Assertions**:
         ```
         {name for d in facts[0].declarations if d.is_public} == {"Client", "Base"}
         module_ref = next(i for i in facts[0].imports if i.specifier == "Foundation")
         module_ref.names == []
         usage = next(i for i in facts[0].imports if i.specifier == "")
         set(usage.names) >= {"Client", "Base"}        # generous usage collection
         ```
      6. `test_collect_facts_preserves_input_order` —
         **Setup**: files `b.py`, `a.py`, `c.py` (each `def x(): pass`) created in any
         order; input list `[Path("b.py"), Path("a.py"), Path("c.py")]`.
         **Input**: `collect_facts([b, a, c], "python")`.
         **Trace**: `facts[i].path == input[i]` for each i.
         **Assertions**: `[f.path for f in facts] == [Path("b.py"), Path("a.py"),
         Path("c.py")]`.
      7. `test_collect_facts_unparseable_file_fails_closed` —
         **Setup**: `broken.py` = `def f(:` (syntax error).
         **Input**: `collect_facts([Path("broken.py")], "python")`.
         **Trace**: parse tree contains an `ERROR` node →
         `ValueError("unparseable source file: broken.py")`.
         **Assertions**: `pytest.raises(ValueError, match="broken.py")`.
- [x] **Debugging**: `pytest tests/codegraph/analysis/test_collect.py -x` — fix
      implementation until green (do NOT fix test code).
- [x] **Contract re-verification**: each file read+parsed exactly once (no re-parse in
      extractors); fail-closed message names the file; `facts` order = `files` order;
      wildcard/plain/base-import `names` conventions per CODEMANIFEST; usage refs share
      the base import's specifier and flags.
- [x] **Lint** (STEP 7): `ruff check goga/codegraph tests/codegraph` +
      `ruff format --check goga/codegraph tests/codegraph`; `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: `pytest tests/ -x` green; ruff gates clean; commit without
      `Co-Authored-By` trailers.

### Task 3: `derive_units` — grouping facts into units with facades (TDD)

Implement `derive_units(facts: list[FileFacts], language: str) -> units: list[Unit]` in
`goga/codegraph/analysis/units.py`; extend the facade. Pure grouping — no file reads.

Algorithm (verbatim from the design):

```
1. by_dir := group facts by fact.path.parent
2. unit_dirs := {d for d in by_dir if <language unit rule>(by_dir[d])}
   python: some fact is "__init__.py"      golang: by_dir[d] non-empty
   javascript: some fact is "index.js"     kotlin: by_dir[d] non-empty
   swift: by_dir[d] non-empty
3. FOR d IN sorted(unit_dirs):                             # deterministic path order
   1. facade := <language facade rule>(by_dir[d])
   2. units.append(Unit(path=d, files=sorted facts paths of d,
                        facade=sorted(set(facade)), is_cell=facade != []))
4. parent of a unit := nearest ancestor directory in unit_dirs (nesting is
   rebuilt from paths by the renderer; Unit carries no children)
```

Per-language facade rules (verbatim):

- **python**: from the `__init__.py` facts only — `exports` (`__all__`) when non-empty,
  otherwise the names of its `is_public` declarations (the non-underscore top-level bound
  names).
- **golang**: union over all unit files of `is_public` declaration names (exported
  package-level identifiers: functions, types, vars, consts).
- **javascript**: from the `index.js` facts — `{declaration names with is_public} ∪
  exports` (export-clause names and the named default export).
- **kotlin**: union over all unit files of `is_public` declaration names.
- **swift**: union over all unit files of `is_public` declaration names (public/open
  only).

Edge cases (verbatim): a directory with sources but failing the unit rule (python without
`__init__.py`, javascript without `index.js`) contributes no unit — its files are analyzed
yet never grouped; nested unit dirs form their own units (own-directory files only); a
unit whose facade is empty is kept with `is_cell=False` (structural ancestor).

**Usages relevant to this task:**
- `convention`: style + test rules as in Task 2.
- `records` (from `goga/codegraph/facts`): construct `Unit` kw-only; facade sorted and
  duplicate-free; `is_cell=False` construction for empty facades.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 3 — derive_units`).
- [x] **Contract tests** (expected to fail now): create
      `tests/codegraph/analysis/test_units.py` with `class TestDeriveUnits:` asserting —
      `derive_units` importable from `goga.codegraph.analysis`; callable as
      `derive_units(facts=[], language="python")` returning `list[Unit]`.
- [x] **REPL probe**: in the REPL, run the Task-2 `collect_facts` over a tiny
      `tmp_path` python package and group by `fact.path.parent` interactively — confirm
      the grouping and facade derivation before migrating into `units.py`.
- [x] **Code**: implement `derive_units` in `goga/codegraph/analysis/units.py` (unit
      rules + facade rules above; Google docstring; no file reads).
- [x] **Code**: extend `goga/codegraph/analysis/__init__.py` — add `derive_units` import
      and `__all__` entry.
- [x] **Interface verification**: `python -c "from goga.codegraph.analysis import derive_units"`;
      `pytest tests/codegraph/analysis/test_units.py -v` — contract tests green.
- [x] **Logic tests** (design scenarios, verbatim):

      1. `test_derive_units_python_package_rule_and_facade` —
         **Setup**: `tmp_path` tree —
         ```
         app/__init__.py            → __all__ = ["Service", "run"]
         app/core.py                → class Service; def run
         app/sub/__init__.py        → (empty)
         app/sub/deep.py            → def helper
         loose/mod.py               → def anything
         ```
         **Input**: `facts = collect_facts(discover_sources("python", []), "python")`;
         `derive_units(facts, "python")` (if `discover_sources` is not yet implemented —
         it lands in Task 5 — pass the explicit file list
         `[Path("app/__init__.py"), Path("app/core.py"), Path("app/sub/__init__.py"),
         Path("app/sub/deep.py"), Path("loose/mod.py")]` to `collect_facts` instead).
         **Trace**:
         ```
         units: app (facade ["Service", "run"], is_cell True),
                app/sub (facade [], is_cell False),
                loose: NOT a unit (no __init__.py) → mod.py belongs to no unit
         order: sorted by path → [app, app/sub]
         ```
         **Assertions**:
         ```
         [unit.path for unit in units] == [Path("app"), Path("app/sub")]
         app_unit.facade == ["Service", "run"] and app_unit.is_cell is True   # __all__ wins
         sub.is_cell is False and sub.facade == []
         not any(u.path == Path("loose") for u in units)
         app_unit.files == [Path("app/__init__.py"), Path("app/core.py")]     # own dir only
         ```
      2. `test_derive_units_python_facade_fallback_bindings` —
         **Setup**: `app/__init__.py` with no `__all__`: `from .core import Engine`,
         `VERSION = 2`, `def boot(): ...`, `_priv = 1`.
         **Input**: `derive_units(collect_facts([Path("app/__init__.py")], "python"),
         "python")`.
         **Trace**: facade = non-underscore bound names → `["Engine", "VERSION",
         "boot"]` sorted.
         **Assertions**: `app.facade == ["Engine", "VERSION", "boot"]` and
         `is_cell is True`.
- [x] **Debugging**: `pytest tests/codegraph/analysis/ -x` — fix implementation until
      green.
- [x] **Contract re-verification**: no file reads inside `derive_units`; deterministic
      path order; facade ⊆ public declarations, sorted unique; non-cell units retained.
- [x] **Lint** (STEP 7): `ruff check goga/codegraph tests/codegraph` +
      `ruff format --check goga/codegraph tests/codegraph`; `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: `pytest tests/ -x` green; ruff gates clean; commit without
      `Co-Authored-By` trailers.

### Task 4: `resolve_links` — exact-origin unit-pair resolution (TDD)

Implement `resolve_links(units: list[Unit], facts: list[FileFacts], language: str,
root: Path) -> links: list[CellLink]` in `goga/codegraph/analysis/resolve.py`; extend the
facade (final analysis facade state: `collect_facts`, `derive_units`, `resolve_links`).

Algorithm (verbatim from the design):

```
1. Build indexes over the COMPLETE units and facts first:
   - cell_by_dir: unit path -> unit (is_cell only)
   - facade_index: facade name -> [unit paths]            # per language scope
   - python: module string -> unit ("a.b" -> path), derived per candidate
     root in priority order: <root> first, then <root>/src; within a root,
     package dir before module file; file-form modules map to their
     directory's unit
   - kotlin: package -> [unit paths]
   - go.mod: module path M (first "module" directive in <root>/go.mod;
     absent -> every import external)
2. FOR each fact f, FOR each ImportRef r in f:
   1. origin := <language origin rule>(r, f, indexes)    # unit path or None
   2. IF origin is None or origin is f's own unit: skip   # external / self
   3. names := r.names
   4. IF r.is_wildcard or r.names == []:
      names := the names of the usage ImportRefs of f that share the
      base import's specifier and flags (recorded by collect_facts —
      review fix R1; no file re-reading, no re-parsing; an aliased
      plain import records no usage ref — known v1 limitation)
   5. IF "default" in names (javascript): element-wise — each "default"
      entry maps to the default-exported name of the RESOLVED FILE (from
      its exports); a file with no named default export maps to nothing
      (review fix R4; mixed clauses like `import d, { a } from ...` keep
      both the mapped name and the named imports; the mapped name still
      passes step 2.6's facade filter)
   6. kept := [n for n in names if n in facade(origin)]
   7. IF f's unit is not a cell (or has no unit): skip    # non-cell source
   8. accumulate kept into pair (f's unit, origin)
3. links := [CellLink(source, target, sorted(set(types))) for each pair]
```

Per-language origin rules (verbatim):

- **python (absolute)**: module `m` → try in order: `<root>/m` package dir (unit),
  `<root>/m.py` file (its directory's unit), `<root>/src/m` package dir,
  `<root>/src/m.py` file. First hit wins; none → external.
- **python (relative)**: base = the importing file's directory (for `__init__.py` the
  directory itself, i.e. its own package); level `L` → go up `L-1` directories from base;
  append the module part when present. `from . import x` → target = that directory as
  unit; `from .m import x` → `base/m` package dir, else `base/m.py` file → its
  directory's unit.
- **python (plain `import a.b.c`)**: resolve the module as above, then expand via the
  usage ref recorded at collect — maximal attribute chains rooted at the import's first
  segment, the segment after the prefix being the used name (`import a.b.c as d` records
  no usage ref — known v1 limitation).
- **python (wildcard `from m import *`)**: expand via the wildcard usage ref recorded at
  collect (every used identifier of the file) ∩ the resolved unit's facade.
- **golang**: import path `p`: `p == M` → unit `<root>`; `p` starts with `M + "/"` →
  unit `<root>/<suffix>`; else external (also external when `go.mod` is absent).
  Expansion: the usage ref recorded at collect — `selector_expression` chains `binding.X`
  rooted at the implicit local binding (the last segment of `p`; an aliased import
  records no usage ref — known v1 limitation).
- **javascript**: relative specifier `s` against the importing file's directory: `s`
  ends with `.js` → file `s`; else file `s + ".js"`, then directory `s` → its
  `index.js`. Directory-form specifiers (`./x/`) → `x/index.js`. The resolved file's
  unit = the file's directory (if it is a unit). Bare specifiers → external. `default` →
  mapped per algorithm step 2.5. Namespace wildcard expands via the usage ref recorded at
  collect (member accesses on the alias, `ns.X`).
- **kotlin**: import `pkg.Name` → units whose files declare `package pkg`, keeping those
  whose facade contains `Name` (link each such unit; normally exactly one). Wildcard
  `pkg.*` → expand via the usage ref recorded at collect (the file's used simple
  identifiers) ∩ the facades of `pkg`'s units.
- **swift**: for each used type name `n` in the usage ref: the units whose facade
  contains `n`; exactly one → link it; zero or ≥2 → no link (uniqueness rule; compiler
  guarantees per-module uniqueness, project-wide duplicates are treated as ambiguous).

Errors: none — every unresolvable name is silently dropped (contract: "no link and no
error"). Edge cases (verbatim): self-imports produce no link; imports by non-cell units
produce no link; cycles pass through as two opposite links; stdlib/third-party names never
resolve (no `PYTHONPATH`/`GOPATH`/env reads — deterministic); a facade name re-exported
through `__init__.py` links to the declaring unit only when the import's resolved module
lands there.

**Usages relevant to this task:**
- `convention`: style + test rules.
- `records` (from `goga/codegraph/facts`): `CellLink` construction — one per pair, types
  sorted unique.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 4 — resolve_links`).
- [x] **Contract tests** (expected to fail now): create
      `tests/codegraph/analysis/test_resolve.py` with `class TestResolveLinks:` asserting
      — `resolve_links` importable from `goga.codegraph.analysis`; callable as
      `resolve_links(units=[], facts=[], language="python", root=Path.cwd())` returning
      `list[CellLink]`.
- [x] **REPL probe**: build the python fixture below on `tmp_path` in the REPL, run
      Tasks 2–3 over it, and walk one import through the index + origin rule
      interactively — confirm the candidate-root priority (`<root>` then `<root>/src`)
      before migrating the resolver.
- [x] **Code**: implement `resolve_links` in `goga/codegraph/analysis/resolve.py` —
      index building, per-language origin rules, expansion via usage refs, facade filter,
      non-cell-source skip, per-pair aggregation; `go.mod` module read (first `module`
      directive); Google docstring.
- [x] **Code**: extend `goga/codegraph/analysis/__init__.py` — add `resolve_links`;
      `__all__ = ["collect_facts", "derive_units", "resolve_links"]` (final state).
- [x] **Interface verification**: `python -c "from goga.codegraph.analysis import collect_facts, derive_units, resolve_links"`;
      `pytest tests/codegraph/analysis/test_resolve.py -v` — contract tests green.
- [x] **Logic tests** (design scenarios, verbatim; build units/facts via the Task 2–3
      functions inside the test):

      1. `test_resolve_links_python_absolute_and_relative_and_plain` —
         **Setup**: `tmp_path` —
         ```
         .goga/config.yml           → language: python
         src/alpha/__init__.py      → from beta import Tool; import gamma.deep; from . import local
         src/beta/__init__.py       → __all__ = ["Tool"]; from .impl import Tool
         src/beta/impl.py           → class Tool: ...
         src/gamma/__init__.py      → ...
         src/gamma/deep.py          → def dive(): ...
         ```
         (`alpha` uses `gamma.deep.dive()` in its body.)
         **Input**: `units`, `facts` over `src/...`;
         `resolve_links(units, facts, "python", root=tmp_path)`.
         **Trace**:
         ```
         index: module "beta" → unit src/beta (via <root>/src candidate root),
                "gamma.deep" → file src/gamma/deep.py → unit src/gamma
         alpha's imports:
           from beta import Tool → origin src/beta; Tool in facade → keep
           import gamma.deep (plain, names []) → origin src/gamma; expansion:
             attribute chain "gamma.deep.dive" prefix matches → name dive;
             dive in src/gamma facade? — only if src/gamma/__init__ binds it; else drop
           from . import local → relative level 1 → base = src/alpha → unit itself → self → drop
         links: (src/alpha → src/beta, ["Tool"])
         ```
         **Assertions**:
         ```
         links == [CellLink(source=Path("src/alpha"), target=Path("src/beta"), types=["Tool"])]
         ```
      2. `test_resolve_links_golang_module_mode` —
         **Setup**: `tmp_path` —
         ```
         go.mod                     → module example.com/app
         store/user.go              → package store; func NewUser() *User; type User struct{}
         main.go                    → package main; import "example.com/app/store"; import "fmt";
                                      func Run() { store.NewUser() }        # exported → root is a cell
         ```
         **Input**: `resolve_links(units, facts, "golang", root=tmp_path)`.
         **Trace**:
         ```
         M = "example.com/app"; import "example.com/app/store" → unit store;
         expansion (usage ref, review fix R1): binding "store" (last segment) .NewUser
           → NewUser in facade → keep
         import "fmt" → external → drop
         root unit: facade ["Run"] → is_cell True (review fix R5 — the importing
           unit must be a cell or the link is dropped at step 2.7)
         links: (root unit → store, ["NewUser"])   # main.go's dir is a unit (has .go files)
         ```
         **Assertions**:
         ```
         len(links) == 1
         links[0].target == Path("store") and links[0].types == ["NewUser"]
         ```
      3. `test_resolve_links_javascript_relative_default_and_directory` —
         **Setup**: `tmp_path` —
         ```
         db/index.js                → export function query() {}; export default function conn() {}
         svc/index.js               → export { run } from "./a.js";          # facade(svc) = ["run"] → a cell
         svc/a.js                   → import c, { query } from "../db/index.js";
                                      export function run() { c(); query(); }
         ```
         Unit membership is per directory: `a.js` and `index.js` both belong to unit
         `svc` (the directory contains `index.js`); the facade comes from the `index.js`
         facts — `["run"]` makes `svc` a cell (review fix R5 — a non-cell source would
         drop the link at step 2.7).
         **Input**: `resolve_links(units, facts, "javascript", root=tmp_path)`.
         **Trace**:
         ```
         "../db/index.js" → file db/index.js → unit db (has index.js)
         names ["default", "query"]:
           "query" in db facade → keep
           "default" → (element-wise, review fix R4) exports of resolved file = ["conn"]
             → conn in db facade → keep
         links: (svc → db, ["conn", "query"]) sorted
         ```
         **Assertions**:
         ```
         links == [CellLink(Path("svc"), Path("db"), ["conn", "query"])]
         ```
      4. `test_resolve_links_python_external_names_silent` —
         **Setup**: python cell `app` (`app/__init__.py` → `from .impl import S`;
         `app/impl.py` → `class S: ...`) whose `impl.py` also contains
         `import os.path` and `from collections import OrderedDict`.
         **Input**: `resolve_links(units, facts, "python", root=tmp_path)`.
         **Trace**:
         ```
         os.path / collections resolve to no unit under <root> or <root>/src → external → dropped
         from .impl import S → resolves to app itself → self → dropped
         no exception raised
         ```
         **Assertions**: `links == [] and no exception`.
      5. `test_resolve_links_swift_ambiguous_name_no_link` —
         **Setup**: three swift units — `ui` (`main.swift` → `public struct App {}` plus
         a usage of `Client`), `core1` (`public struct Client {}`), `core2`
         (`public struct Client {}`).
         **Input**: `resolve_links(units, facts, "swift", root=tmp_path)`.
         **Trace**:
         ```
         ui is a cell (facade ["App"]); its usage ref names App (resolves to ui itself
           → self → dropped) and Client → facade_index["Client"] has 2 units
           → uniqueness fails → no link
         no exception raised
         ```
         **Assertions**: `links == [] and no exception`.
      6. `test_resolve_links_non_cell_source_no_link` —
         **Setup**: `tmp_path` —
         ```
         api/__init__.py   → from .impl import S
         api/impl.py       → class S: ...
         tools/__init__.py → (empty)
         tools/mod.py      → from api import S
         ```
         **Input**: `resolve_links(units, facts, "python", root=tmp_path)`.
         **Trace**:
         ```
         unit api: facade ["S"] (the imported binding S of __init__.py) → is_cell True
         unit tools: empty __init__.py → facade [] → is_cell False (structural only)
         tools/mod.py's `from api import S`: origin = api (module "api" → <root>/api
           package dir); S in api facade → would keep — but step 2.7 drops the pair:
           the importing unit tools is not a cell
         api's own import resolves to itself → self → dropped
         ```
         **Assertions**: `links == [] and no exception`.
- [x] **Debugging**: `pytest tests/codegraph/analysis/ -x` — fix implementation until
      green.
- [x] **Contract re-verification**: index built over the complete set first; no
      environment reads; no file re-parsing (expansion reads usage refs only); one link
      per pair, sorted unique types; silent drops for external/self/non-cell/ambiguous.
- [x] **Lint** (STEP 7): `ruff check goga/codegraph tests/codegraph` +
      `ruff format --check goga/codegraph tests/codegraph`; `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: `pytest tests/ -x` green; ruff gates clean; commit without
      `Co-Authored-By` trailers.

### Task 5: `discover_sources` — deterministic path-only source walk (TDD)

Implement `discover_sources(language: str, ignore: list[str]) -> files: list[Path]` in
`goga/codegraph/discovery.py` (new cell `goga/codegraph`), plus the cell facade
`goga/codegraph/__init__.py` re-exporting `discover_sources` (Tasks 6–7 extend it; final
state re-exports `codegraph`, `discover_sources`, `render_graph`).

Algorithm (verbatim from the design):

```
1. extension    := {python: ".py", golang: ".go", javascript: ".js",
                    kotlin: ".kt", swift: ".swift"}[language]
2. test_pattern := {python: "test_*.py", golang: "*_test.go",
                    javascript: "*.test.js", kotlin: "*Test.kt",
                    swift: "*Tests.swift"}[language]
3. ignore_set := {os.path.normpath(x) for x in ignore}   # exact, no glob
4. FOR dirpath, dirnames, filenames IN os.walk("."):
   1. dirnames.sort()                                    # determinism
   2. dirnames[:] := [d for d in dirnames
                      if normpath(relpath(dirpath/d)) not in ignore_set]
   3. FOR name IN sorted(filenames):
      1. IF normpath(relpath(dirpath/name)) in ignore_set: skip
      2. IF fnmatch(name, test_pattern): skip            # idiomatic tests
      3. IF Path(name).suffix == extension: emit Path(relpath(dirpath/name))
```

Edge cases (verbatim): `ignore` entry with trailing slash matches the directory
(`normpath` semantics, same as `goga lint`); ignored directory prunes its whole subtree;
unlike the AST walk, `.project` is NOT skipped — the exclusion list is exactly the given
list; a file named like a test pattern is skipped even when also excluded (idempotent
skip). Errors: none (unknown language cannot reach here — validated upstream).

**Usages relevant to this task:**
- `convention`: style + test rules; `tmp_path` fixture for filesystem state; no mocks
  (pure logic + real files).
- Reference mechanics: `goga/ast/ast.py:92-108` (normpath, trailing slash insignificant,
  no glob) — read it for parity, do not import from it.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 5 — discover_sources`).
- [x] **Contract tests** (expected to fail now): create `tests/codegraph/__init__.py`
      (if not yet present) and `tests/codegraph/test_discovery.py` with
      `class TestDiscoverSources:` asserting — `discover_sources` importable from
      `goga.codegraph`; callable as `discover_sources(language="python", ignore=[])`
      returning `list[Path]`.
- [x] **REPL probe**: in the REPL, walk the fixture tree below with `os.walk` +
      `dirnames.sort()` and confirm the ignore-set normpath matches (directory with and
      without trailing slash) before migrating into `discovery.py`.
- [x] **Code**: implement `discover_sources` in `goga/codegraph/discovery.py` —
      extension/test-pattern tables, ignore set, sorted walk, relpath emission; Google
      docstring; paths only (no content reads).
- [x] **Code**: create `goga/codegraph/__init__.py` re-exporting `discover_sources`
      (`__all__ = ["discover_sources"]` — extended by Tasks 6–7).
- [x] **Interface verification**: `python -c "from goga.codegraph import discover_sources"`;
      `pytest tests/codegraph/test_discovery.py -v` — contract tests green.
- [x] **Logic tests** (design scenario, verbatim):

      `test_discover_sources_ignore_and_tests_and_order` —
      **Setup**: `tmp_path` —
      ```
      a/m1.py, a/m2.py, b/n.py, b/test_n.py, .venv/lib/x.py, skipped/orphan.py
      lint.ignore: [".venv/", "skipped/orphan.py"]
      ```
      **Input**: `discover_sources("python", [".venv/", "skipped/orphan.py"])`.
      **Trace**:
      ```
      walk sorted: a before b; .venv pruned (normpath ".venv" match, subtree gone);
      skipped/orphan.py skipped (file entry); b/test_n.py skipped (pattern)
      ```
      **Assertions**:
      ```
      files == [Path("a/m1.py"), Path("a/m2.py"), Path("b/n.py")]
      discover_sources("python", ignore) == discover_sources("python", ignore)  # stable
      ```
- [x] **Debugging**: `pytest tests/codegraph/test_discovery.py -x` — fix implementation
      until green.
- [x] **Contract re-verification**: exclusion list is exactly the given list (no
      built-ins); deterministic order; relative paths only.
- [x] **Lint** (STEP 7): `ruff check goga/codegraph tests/codegraph` +
      `ruff format --check goga/codegraph tests/codegraph`; `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: `pytest tests/ -x` green; ruff gates clean; commit without
      `Co-Authored-By` trailers.

### Task 6: `render_graph` — node tree, schema-parity filters, serialization (TDD)

Implement `render_graph(units: list[Unit], links: list[CellLink], cells: list[str],
max_depth: int | None, depends_on: list[str]) -> json: str` in
`goga/codegraph/render.py`; extend the facade.

Algorithm (verbatim from the design):

```
1. cell_units := [u for u in units if u.is_cell]
2. FOR u IN cell_units (sorted by path):
   output parent := nearest ancestor cell unit (walk the directory prefixes,
   skipping non-cell units)                  # structural compression
3. node.dependencies := {normpath(link.target): sorted unique types
                         for links with source == u.path}   # {} when none
4. filters, IN ORDER (exact parity with goga/schema/schema.py):
   1. cells (non-empty): keep node iff normpath(node.cell) in
      {normpath(c) for c in cells} OR it is an ancestor of a kept node
      (schema _filter_tree + _cell_in_set semantics: matched cells plus
      the ancestor chain; siblings and non-matching descendants drop)
   2. depends_on (non-empty): dep := {normpath(p) for p in depends_on};
      keep node iff any key of its dependencies is in dep OR any descendant
      is kept (schema _has_dependency + _prune_by_dependency semantics)
   3. max_depth (not None): empty the children of every node at
      depth >= max_depth, root depth 0     (schema _prune_depth semantics)
5. roots sorted by cell path; children sorted by cell path
6. empty forest -> "[]"; else json.dumps(nodes, indent=4, sort_keys=True,
   ensure_ascii=False)                       # beautiful_json
```

Edge cases (verbatim): non-cell ancestors vanish from the output while keeping the
skeleton (a nested cell surfaces under its nearest cell ancestor or as a root); a cell
with no outgoing links carries `dependencies: {}`; `max_depth=0` empties every root's
children; determinism — identical inputs produce byte-identical output.

**Usages relevant to this task:**
- `convention`: style + test rules; JSON expectations grounded in real runs (design
  traces) — placeholder expectations are forbidden.
- `beautiful_json`: `json.dumps(nodes, indent=4, sort_keys=True, ensure_ascii=False)`;
  empty forest short-circuits to `"[]"`.
- `records` (from `goga/codegraph/facts`): build `CodegraphNode` records kw-only; node
  fields exactly `cell, types, dependencies, children`; never modify input records —
  build fresh nodes.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 6 — render_graph`).
- [x] **Contract tests** (expected to fail now): create `tests/codegraph/test_render.py`
      with `class TestRenderGraph:` asserting — `render_graph` importable from
      `goga.codegraph`; callable with the five parameters returning `str`.
- [x] **REPL probe (parity, hot loop)**: import the schema filter internals
      (`goga/schema/schema.py` `_filter_tree` / `_filter_by_depends_on` / `_prune_depth`)
      in the REPL and run the four filter cases below against small node trees — pin the
      exact keep/prune behavior (including `max_depth=1` keeping one level, review fix
      R6) before implementing the codegraph equivalents.
- [x] **Code**: implement `render_graph` in `goga/codegraph/render.py` — nesting with
      structural compression, dependency aggregation, the three filters in order,
      `beautiful_json` serialization; Google docstring; build only fresh
      `CodegraphNode` records.
- [x] **Code**: extend `goga/codegraph/__init__.py` — add `render_graph`.
- [x] **Interface verification**: `python -c "from goga.codegraph import render_graph"`;
      `pytest tests/codegraph/test_render.py -v` — contract tests green.
- [x] **Logic tests** (design scenarios, verbatim):

      1. `test_render_graph_nesting_compression_and_dependencies` —
         **Setup**: units (python semantics) —
         ```
         app        facade ["Boot"]            cell
         app/lib    facade []                  non-cell (structural only)
         app/lib/db facade ["connect"]         cell
         app/lib/db/x.py imports app.Boot
         standalone facade ["solo"]            cell, separate root
         ```
         **Input**: `render_graph(units, links, [], None, [])`.
         **Trace**:
         ```
         nesting: app/lib → compressed out; app/lib/db attaches to app
         dependencies: app/lib/db node carries {"app": ["Boot"]}
         roots sorted: [app, standalone]
         ```
         **Assertions**:
         ```
         doc = json.loads(json_text)
         [d["cell"] for d in doc] == ["app", "standalone"]
         child = doc[0]["children"][0]
         child["cell"] == "app/lib/db" and child["dependencies"] == {"app": ["Boot"]}
         doc[0]["children" count] == 1            # non-cell ancestor produced no node
         set(doc[0].keys()) == {"cell", "types", "dependencies", "children"}
         ```
      2. `test_render_graph_filter_parity_cells_depends_on_depth` —
         **Setup**: a three-level unit tree `root → root/mid → root/mid/leaf` with links
         `leaf → ext` (`ext` a root-level cell).
         **Input** (four subcases, one test each or parametrized via
         `@pytest.mark.parametrize`):
         ```
         render_graph(units, links, ["root/mid/leaf"], None, [])
         render_graph(units, links, [], None, ["ext"])
         render_graph(units, links, [], 1, [])
         render_graph(units, links, [], 0, [])
         ```
         **Trace**:
         ```
         cells=["root/mid/leaf"] → keep leaf + ancestors root, root/mid (skeleton)
         depends_on=["ext"] → keep leaf (dep key ext) + ancestors; root/mid kept
         max_depth=1 → root keeps one level (mid), mid's children emptied (schema
           _prune_depth: nodes at depth >= max_depth lose children, root depth 0 —
           review fix R6)
         max_depth=0 → every root's children emptied
         ```
         **Assertions**:
         ```
         case1: cells in tree == {"root", "root/mid", "root/mid/leaf"}
         case2: cells in tree == {"root", "root/mid", "root/mid/leaf"} and
                leaf.dependencies == {"ext": [...]}
         case3: len(doc[0]["children"]) == 1 and doc[0]["children"][0]["children"] == []
         case4: doc[0]["children"] == []
         ```
- [x] **Debugging**: `pytest tests/codegraph/test_render.py -x` — fix implementation
      until green.
- [x] **Contract re-verification**: node fields exactly `cell, types, dependencies,
      children`; filters in the order cells → depends_on → max_depth; empty forest →
      `"[]"`; byte-identical output on repeated calls.
- [x] **Lint** (STEP 7): `ruff check goga/codegraph tests/codegraph` +
      `ruff format --check goga/codegraph tests/codegraph`; `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: `pytest tests/ -x` green; ruff gates clean; commit without
      `Co-Authored-By` trailers.

### Task 7: `codegraph` orchestrator — config → discovery → analysis → render (TDD)

Implement `codegraph(cells: list[str], max_depth: int | None = None, depends_on:
list[str] = []) -> json: str` in `goga/codegraph/codegraph.py`; complete the facade
(final state: `codegraph`, `discover_sources`, `render_graph`).

Algorithm (verbatim from the design):

```
1. config := load_project_config()             # FileNotFoundError propagates
2. language := config.language
3. IF language not in {python, golang, javascript, kotlin, swift}:
   raise ValueError(f"unsupported language: {language!r}; expected one of ...")
4. ignore := config.lint.ignore if config.lint is not None else []
5. files := discover_sources(language, ignore)
6. root := Path.cwd()
7. facts := collect_facts(files, language)
8. units := derive_units(facts, language)
9. links := resolve_links(units, facts, language, root)
10. RETURN render_graph(units, links, cells, max_depth, depends_on)
```

Errors: `FileNotFoundError` (uninitialized project), `ValueError` (unsupported language;
unparseable file — message names the file), config loader errors (`KeyError`,
`ValueError`, `yaml.YAMLError`) — all propagate to the CLI wrapper. Edge cases: no
analyzable sources → empty units/links → `"[]"`; read-only — nothing is written; the
default `depends_on=[]`/`max_depth=None` are never mutated (iterate only).

**Usages relevant to this task:**
- `convention`: style + test rules; golden expectations grounded in real runs.
- `stages` (from `goga/codegraph/analysis`): stage order, complete-input requirement,
  `root = Path.cwd()`, failure behavior (only `collect_facts` fails; unparseable file
  aborts naming the file).
- `project-configuration` (from `goga/config`): `load_project_config()` reads
  `.goga/config.yml` from cwd; absent/empty → `FileNotFoundError`; `lint` absent →
  `config.lint is None`; `LintConfig.ignore` is the exact-path list.
- `codegraph-usage` (from `goga/codegraph`): output format, guarantees (deterministic,
  read-only, purely descriptive), the three failure modes.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 7 — codegraph orchestrator`).
- [x] **Contract tests** (expected to fail now): create `tests/codegraph/test_codegraph.py`
      with `class TestCodegraph:` asserting — `codegraph` importable from
      `goga.codegraph`; `goga.codegraph.__all__` == `["codegraph", "discover_sources",
      "render_graph"]`; callable as `codegraph()` returning `str`.
- [x] **REPL probe**: run the full pipeline manually in the REPL over the golden fixture
      below (config → discover → collect → derive → resolve → render) and inspect the
      rendered JSON — the golden expectation below must match the live run byte-for-byte
      before it is pinned in the test.
- [x] **Code**: implement `codegraph` in `goga/codegraph/codegraph.py` — the ten-step
      algorithm; relative import of the config loader (`from ..config import
      load_project_config`); language whitelist `{python, golang, javascript, kotlin,
      swift}`; Google docstring.
- [x] **Code**: extend `goga/codegraph/__init__.py` — add `codegraph`;
      `__all__ = ["codegraph", "discover_sources", "render_graph"]` (final state).
- [x] **Interface verification**: `python -c "from goga.codegraph import codegraph"`;
      `pytest tests/codegraph/test_codegraph.py -v` — contract tests green.
- [x] **Logic tests** (design scenarios, verbatim):

      1. `test_codegraph_end_to_end_golden_output` —
         **Setup**: `tmp_path` python project —
         ```
         .goga/config.yml   → language: python
         greeting/__init__.py → __all__ = ["hello"]; from .impl import hello
         greeting/impl.py     → def hello() -> str: ...
         ```
         **Input**: `codegraph()` (cwd pinned to `tmp_path`).
         **Trace**:
         ```
         load config → python; no lint section → ignore []
         discover → greeting/__init__.py, greeting/impl.py (sorted)
         collect → facts; derive → unit greeting facade ["hello"]
         resolve → no imports outside stdlib → links []
         render → single root node
         ```
         **Assertions**:
         ```
         codegraph() == textwrap.dedent('''\
         [
             {
                 "cell": "greeting",
                 "children": [],
                 "dependencies": {},
                 "types": [
                     "hello"
                 ]
             }
         ]
         ''').strip()
         codegraph() == codegraph()            # byte-identical on re-run
         ```
      2. `test_codegraph_uninitialized_project` —
         **Setup**: empty `tmp_path` (no `.goga/config.yml`), cwd pinned.
         **Input**: `codegraph()`.
         **Trace**:
         ```
         load_project_config() → FileNotFoundError (no .goga/config.yml)
           → propagates (no swallow — contrast with lint)
         ```
         **Assertions**: `pytest.raises(FileNotFoundError): codegraph()`.
      3. `test_codegraph_unsupported_language` —
         **Setup**: `.goga/config.yml` → `language: rust`.
         **Input**: `codegraph()`.
         **Trace**: language check fails before any walk → `ValueError` naming `rust`.
         **Assertions**: `pytest.raises(ValueError, match="rust"): codegraph()`.
      4. `test_render_graph_empty_project_renders_empty_list` —
         **Setup**: `tmp_path` with only `.goga/config.yml` (`language: python`) and one
         non-unit loose file.
         **Input**: `codegraph()`.
         **Trace**: discover → [loose file]; derive → no units; render → empty forest →
         `"[]"`.
         **Assertions**: `codegraph() == "[]"`.
      5. `test_codegraph_read_only` —
         **Setup**: snapshot the project tree (relative paths + file hashes) before the
         run.
         **Input**: `codegraph()`.
         **Trace**: full pipeline; assertion re-walks and re-hashes.
         **Assertions**: tree snapshot after == snapshot before.
- [x] **Debugging**: `pytest tests/codegraph/ -x` — fix implementation until green.
- [x] **Contract re-verification**: deterministic + idempotent; read-only; no
      environment reads; defaults never mutated; the three failure modes propagate.
- [x] **Lint** (STEP 7): `ruff check goga/codegraph tests/codegraph` +
      `ruff format --check goga/codegraph tests/codegraph`; `goga lint` — 0 errors.
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: `pytest tests/ -x` green; ruff gates clean; commit without
      `Co-Authored-By` trailers.

### Task 8: CLI wrapper `goga codegraph` + facade wiring + registration (TDD)

Implement the click wrapper in `goga/commands/codegraph/codegraph.py`, the cell facade
`goga/commands/codegraph/__init__.py`, the re-export through `goga/commands/__init__.py`,
and the registration in `goga/cli.py`. No domain knowledge in the wrapper — everything
delegates to `codegraph_logic`.

Algorithm (verbatim from the design):

```
1. Declare (mirroring goga/commands/schema/schema.py):
   @click.command()
   @click.argument("cells", nargs=-1)
   @click.option("--max-depth", type=int, default=None)
   @click.option("--depends-on", multiple=True,
                 help="Filter cells by dependency on specified cell paths")
   @click.pass_context
2. Docstring: user-facing help (CLI docstring conventions — summary line,
   no Args/Returns/Raises; `\f` before any developer note)
3. try: result := codegraph_logic(list(cells), max_depth, list(depends_on))
   except Exception as e: click.echo(str(e), err=True); ctx.exit(1)
4. click.echo(result)
```

Wiring (verbatim from the design, per the `cli-commands` practice):
`goga/commands/codegraph/__init__.py` re-exports `codegraph`; `goga/commands/__init__.py`
gains `from .codegraph import codegraph` (alphabetical position: after `.build`, before
`.config`) and `"codegraph"` in `__all__` (sorted position after `"build"`); `goga/cli.py`
imports it and calls `app.add_command(codegraph)` right after `schema`.

Edge cases: zero CELLS arguments → all cells; repeated `--depends-on` → tuple in passing
order, converted to list; `--max-depth` absent → `None`. Errors: any exception → stderr
message, exit 1, empty stdout, no traceback.

**Usages relevant to this task:**
- `convention`: CLI docstring rules (no Args/Returns/Raises on the callback; `\f` for
  developer notes); test rules.
- `click`: `@click.command()`, CELLS variadic `nargs=-1`, `--max-depth` int option,
  `--depends-on` repeatable (`multiple=True` — the value is a tuple, emptiness tested,
  never `None`); `click.echo` for output; `click.echo(..., err=True)` + `ctx.exit(1)`
  for failures (no `sys.exit` inside commands per the anti-patterns).
- `codegraph-usage` (from `goga/codegraph`): the output and failure contract behind the
  command.
- `cli-commands` (from `goga/commands` context): registration reference — facade import
  line, add_command wiring, command table row.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [x] **STEP 0 — Declaration**: declare this task (`Task 8 — codegraph CLI wrapper`).
- [x] **Contract tests** (expected to fail now): create `tests/commands/codegraph/__init__.py`
      and `tests/commands/codegraph/test_codegraph.py` with
      `class TestCodegraphCommand:` asserting — `codegraph` importable from
      `goga.commands.codegraph` and from `goga.commands`; `isinstance(..., click.Command)`;
      registered on `app` (`any(cmd.name == "codegraph" for cmd in app.commands.values())`).
- [x] **REPL probe**: read `goga/commands/schema/schema.py` and, in the REPL, invoke the
      reference wrapper's options through `CliRunner --help` once — confirm the surface
      text before writing the mirrored wrapper.
- [x] **Code**: create `goga/commands/codegraph/codegraph.py` — the click command per the
      algorithm; relative import `from ...codegraph import codegraph as codegraph_logic`;
      callback docstring per CLI docstring conventions.
- [x] **Code**: create `goga/commands/codegraph/__init__.py` — `from .codegraph import
      codegraph as codegraph`; `__all__ = ["codegraph"]`.
- [x] **Code**: extend `goga/commands/__init__.py` — `from .codegraph import codegraph`
      (sorted position) + `"codegraph"` in `__all__`.
- [x] **Code**: extend `goga/cli.py` — import `codegraph` (via the `goga.commands`
      facade import block, matching the existing pattern) and call
      `app.add_command(codegraph)` immediately after `app.add_command(schema)`.
- [x] **Interface verification**: `python -c "from goga.commands import codegraph"`;
      `pytest tests/commands/codegraph/test_codegraph.py -v` — contract tests green.
- [x] **Logic tests** (design scenarios, verbatim; `empty_package_environment` for
      CliRunner tests):

      1. `test_cli_codegraph_success_and_registration` —
         **Setup**: the golden project of Task 7 (greeting package + config);
         `empty_package_environment`.
         **Input**: `CliRunner().invoke(app, ["codegraph"])`; also `["codegraph",
         "--help"]`.
         **Trace**:
         ```
         app dispatches to the registered codegraph command
         wrapper → codegraph_logic([], None, []) → json
         click.echo(json) → stdout; exit 0
         ```
         **Assertions**:
         ```
         result.exit_code == 0
         json.loads(result.output)["cell" list root] == "greeting" (parses, one root)
         "--help" output contains "CELLS", "--max-depth", "--depends-on"
         any(cmd.name == "codegraph" for cmd in app.commands.values())
         ```
      2. `test_cli_codegraph_failure_stderr_only` —
         **Setup**: uninitialized `tmp_path`, cwd pinned.
         **Input**: `CliRunner().invoke(app, ["codegraph"])`.
         **Trace**:
         ```
         wrapper catches Exception → click.echo(str(e), err=True) → ctx.exit(1)
         ```
         **Assertions**:
         ```
         result.exit_code == 1
         result.output == ""                    # stdout untouched
         result.stderr != "" and "Traceback" not in result.stderr
         ```
      3. `test_commands_facade_reexports_codegraph` — extend
         `tests/commands/test_commands_facade.py` with a `TestCodegraphFacade` class —
         **Setup**: import `goga.commands` and `goga.commands.codegraph`.
         **Input**: `commands.codegraph`, `commands.__all__`.
         **Trace**: facade import binds the same click command object as the source
         module.
         **Assertions**:
         ```
         commands.codegraph is codegraph_source
         "codegraph" in commands.__all__
         isinstance(commands.codegraph, click.Command)
         ```
- [x] **Debugging**: `pytest tests/commands/ -x` — fix implementation until green.
- [x] **Contract re-verification**: surface identical to the schema command; stdout
      carries the JSON document only; exit 0 only on complete generation; wiring per
      `cli-commands`.
- [x] **Lint** (STEP 7): `ruff check goga/ tests/` + `ruff format --check goga/
      tests/`; `goga lint` — 0 errors; `goga schema` — dependency graph unchanged and
      correct (codegraph cells present, no cycles).
- [x] **STEP 8 — Completion**: mark checkboxes; → REVIEW → APPROVAL → NEXT TASK.
- [x] **Commit gate**: `pytest tests/ -x` green; ruff gates clean; commit without
      `Co-Authored-By` trailers.

### Task 9: Integration tests — the full CLI surface across cells

Cross-package integration: the registered `app` driving config → discovery → analysis →
render through the public facades only, plus the arch-plan verification gates as
executable checks. File: `tests/integration/test_codegraph_cli_integration.py` (mirrors
the `tests/integration/` precedent).

**Usages relevant to this task:**
- `convention`: integration tests belong in `tests/integration/`; `tmp_path` fixtures;
  CliRunner (direct Python call); self-documenting names.
- `codegraph-usage` (from `goga/codegraph`): output node format and guarantees — the
  assertions below check them through the CLI surface.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] Create `tests/integration/test_codegraph_cli_integration.py` with
      `class TestCodegraphCliIntegration:` — synthetic `tmp_path` python project with
      two packages where one imports from the other (e.g. `app/__init__.py` re-exporting
      from `app/core.py`, and `client/__init__.py` doing `from app import Service`), cwd
      pinned.
- [ ] Test CLI filters end-to-end: `CliRunner().invoke(app, ["codegraph", "client"])`
      keeps `client` + ancestors only; `["codegraph", "--max-depth", "0"]` empties
      children; `["codegraph", "--depends-on", "app"]` keeps the dependent cell with the
      ancestor skeleton — asserting against `json.loads(result.output)`.
- [ ] Test determinism through the CLI: two identical invocations produce
      byte-identical `result.output`.
- [ ] Test registration surface: `--help` of the root group lists `codegraph` (the
      arch-plan gate "`goga --help` lists codegraph" as an executable check).
- [ ] Run validation: `pytest tests/integration/test_codegraph_cli_integration.py -v`,
      then the full battery `pytest tests/ -x`.
- [ ] Lint + commit gate: `ruff check goga/ tests/` + `ruff format --check goga/
      tests/`; `goga lint`; commit without `Co-Authored-By` trailers.

### Task 10: Documentation deliverables — `docs/features/codegraph` and index rows

Create the consumer documentation pages and table rows (the design's documentation
deliverables; format mirrors `docs/features/schema/index.md` and
`docs/features/schema/cli.md`).

**Usages relevant to this task:**
- `codegraph-usage` (from `goga/codegraph`): the node format, guarantees, and failure
  modes the docs must describe.
- `click` (surface reference): synopsis, arguments, options tables.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the
contract.**

- [ ] Create `docs/features/codegraph/index.md` — feature page: what `goga codegraph`
      solves (derive the prospective cell graph from existing code), directory links
      (CLI), task bullets mirroring the schema page structure.
- [ ] Create `docs/features/codegraph/cli.md` — full `goga codegraph` command reference:
      Synopsis (`goga codegraph [CELLS]... [--max-depth N] [--depends-on CELL]...`),
      Description, Arguments and Options tables, Output (node JSON with exactly
      `cell`/`types`/`dependencies`/`children` — the schema node minus manifest-only
      fields), Examples, Exit Codes (`0` success; `1` uninitialized project /
      unsupported language / unparseable source file — message names the file).
- [ ] Add the Codegraph row to `docs/features/index.md`:
      `| [Codegraph](codegraph/index.md) | Prospective cell graph from existing code | `goga codegraph` |`
      (position mirroring the command order — after Schema).
- [ ] Add the `goga codegraph` row to `docs/cli/index.md` (link targets
      `../features/codegraph/cli.md` and `../features/codegraph/index.md`), after the
      schema row.
- [ ] Verify: every referenced page exists, tables render (markdown lint by reading the
      neighboring rows), and the pages mention only behavior that Task 7–8 tests pin.
- [ ] Lint + commit gate: `ruff check goga/ tests/` + `ruff format --check goga/
      tests/` (unchanged code — still green); `goga lint`; commit without
      `Co-Authored-By` trailers.

---

## Validation Commands

All commands run in the project virtualenv (create it if missing). These are the global
plan-level gates; task-level gates run the scoped variants after every task and before
every local commit.

- `pytest tests/ -x`: Run all tests (full battery).
- `pytest tests/codegraph tests/commands -v`: Focused suites for this feature.
- `ruff check goga/ tests/`: Lint check — zero violations (CI gate).
- `ruff format --check goga/ tests/`: Formatting gate — zero reformattings; run
  `ruff format goga/ tests/` when diffs are reported (the formatter is the author's
  responsibility; local hooks do not enforce it).
- `goga lint`: Cell-level manifest lint — 0 errors over 87 cells.
- `goga schema`: Dependency graph correct and unchanged — the codegraph cells present,
  no cycles.
- `python -c "from goga.codegraph.facts import CellLink, CodegraphNode, Declaration, FileFacts, ImportRef, Unit"`:
  Facts facade accessibility.
- `python -c "from goga.codegraph.analysis import collect_facts, derive_units, resolve_links"`:
  Analysis facade accessibility.
- `python -c "from goga.codegraph import codegraph, discover_sources, render_graph"`:
  Orchestrator facade accessibility.
- `python -c "from goga.commands import codegraph"`: Re-export accessibility
  (`->codegraph: {}`).
- `goga --help`: `codegraph` listed in the command table.
- `git status --short goga/ | grep CODEMANIFEST` (expect no output): CODEMANIFEST files
  untouched — read-only contract.

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`facts.py`,
      `collect.py`, `units.py`, `resolve.py`, `codegraph.py` ×2, `discovery.py`,
      `render.py`)
- [ ] Every contract entity is accessible from the facade (`__all__`-exact facades;
      `->codegraph: {}` re-export binds the same object; `app.add_command(codegraph)`
      registered after `schema`)
- [ ] Properties and methods match the declared API (record fields, stage signatures,
      wrapper surface identical to `schema`)
- [ ] Descriptions are reflected in behavior (algorithms of the design implemented
      verbatim, including review fixes R1–R7 semantics)
- [ ] Contract dependencies are met (imports from `goga/codegraph/facts`,
      `goga/codegraph/analysis`, `goga/config` resolve; no cross-imports)
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification
      → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding
      task — all 27 design test scenarios implemented, plus the integration scenarios
- [ ] Integration tests exist for the cross-cell CLI scenarios (`tests/integration/`)
- [ ] No package boundary was expanded (no new cells, no `location` deviations,
      internal helpers stay inside their cells)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only; `git status`
      confirms)
- [ ] All validation commands pass (pytest full battery, both ruff gates, `goga lint`,
      `goga schema`, facade checks, `goga --help`)
- [ ] Every Usages entry is mentioned in at least one task (`convention`,
      `tree-sitter-python/go/js/kotlin/swift`, `beautiful_json`, `click`, `records`,
      `stages`, `project-configuration`, `codegraph-usage`, `cli-commands`)
- [ ] The Mandatory Rules were followed in every task: coding style per `convention`,
      test rules per `convention`, lint/format gates green at every stage and before
      every local commit (no `Co-Authored-By` trailers), REPL cycle
      probe→migrate→hot-verify applied in every coding task
- [ ] Documentation deliverables created (`docs/features/codegraph/index.md`,
      `docs/features/codegraph/cli.md`, both index rows)
