# Design Document: `codegraph`

Topic: `codegraph` — prospective cell graph for existing code.
Plan path: `.goga/history/2026/codegraph/design.md`.
Source contracts: the CODEMANIFEST changes on this branch (created by apply-architecture from `.goga/history/2026/codegraph/arch.md`, amended during this design pass — see [Applied Fixes](#applied-fixes)).
Reference decisions: `.goga/history/2026/codegraph/adr.md` (accepted), `.goga/history/2026/codegraph/task.md`.

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/codegraph/facts/CODEMANIFEST`: **new** — 6 entities (Declaration, ImportRef, FileFacts, Unit, CellLink, CodegraphNode), no Imports (leaf cell).
- `goga/codegraph/analysis/CODEMANIFEST`: **new** — 3 routines (collect_facts, derive_units, resolve_links); imports 5 fact types + `records` from `goga/codegraph/facts`.
- `goga/codegraph/CODEMANIFEST`: **new** — 3 routines (codegraph, discover_sources, render_graph); imports from `goga/codegraph/facts`, `goga/codegraph/analysis`, `goga/config`.
- `goga/commands/codegraph/CODEMANIFEST`: **new** — 1 routine (CLI wrapper `codegraph`); imports `codegraph AS codegraph_logic` + `codegraph-usage` from `goga/codegraph`.
- `goga/commands/CODEMANIFEST`: **modified** — new Imports block (`codegraph` from `goga/commands/codegraph`) and new embedding `->codegraph: {}`.
- `goga/CODEMANIFEST`: **modified** — `codegraph` added to the `goga/commands` Types import and to the `app()` Commands annotation list (after `schema`).

### New Entities

- `Declaration(path: Path, name: str, is_public: bool)` — one named code declaration; `location: facts.py`.
- `ImportRef(source: Path, specifier: str, names: list[str], is_relative: bool, is_wildcard: bool)` — one import statement or name usage; `location: facts.py`.
- `FileFacts(path: Path, declarations: list[Declaration], imports: list[ImportRef], exports: list[str], module: str)` — analysis result of one source file; `location: facts.py`.
- `Unit(path: Path, files: list[Path], facade: list[str], is_cell: bool)` — one language unit (candidate prospective cell); `location: facts.py`.
- `CellLink(source: Path, target: Path, types: list[str])` — one resolved unit-to-unit reference; `location: facts.py`.
- `CodegraphNode(cell: str, types: list[str], dependencies: dict[str, list[str]], children: list[CodegraphNode])` — one output tree node; `location: facts.py`.
- `collect_facts(files: list[Path], language: str) -> facts: list[FileFacts]` — parse and extract per file; `location: collect.py`.
- `derive_units(facts: list[FileFacts], language: str) -> units: list[Unit]` — group files into units with facades; `location: units.py`.
- `resolve_links(units: list[Unit], facts: list[FileFacts], language: str, root: Path) -> links: list[CellLink]` — exact-origin name resolution; `location: resolve.py`.
- `codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = []) -> json: str` — orchestrator; `location: codegraph.py`.
- `discover_sources(language: str, ignore: list[str]) -> files: list[Path]` — deterministic source walk; `location: discovery.py`.
- `render_graph(units: list[Unit], links: list[CellLink], cells: list[str], max_depth: int | None, depends_on: list[str]) -> json: str` — tree assembly, filters, serialization; `location: render.py`.
- `codegraph(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [])` — CLI wrapper; `location: goga/commands/codegraph/codegraph.py`.

### Changed Entities

None — all pre-existing cells (`goga/config`, `goga/commands`, `goga`) are consumed or extended as-is; no existing signature changed.

### Deleted Entities

None.

### Usages and Annotations Changes

- New project-level Usages wired into the new cells: `convention` (all four cells), `tree-sitter-python`/`tree-sitter-go`/`tree-sitter-js`/`tree-sitter-kotlin`/`tree-sitter-swift` (analysis), `beautiful_json` (goga/codegraph), `click` (commands/codegraph).
- New imported usages: `records` and `stages` and `codegraph-usage` (cross-cell, tracked via Imports), `project-configuration` from `goga/config`.
- New cell-level practice files: `goga/codegraph/facts/.usages/records.md`, `goga/codegraph/analysis/.usages/stages.md`, `goga/codegraph/.usages/codegraph-usage.md`.
- `goga/commands/.usages/cli-commands.md` updated: 17 commands, import lists, registration line, table row.
- Context (branch, pre-design): `.goga/usages/cooks/tree-sitter-{python,go,js}.md` enriched with import-node documentation — required by the new `collect_facts` import extraction.

## Applied Fixes

Three contract defects found during code-stack tracing, fixed after user approval (choice "1A 2A 3A — all recommendations"), plus the consumer-doc sync (approval q2). All edits are annotation-level; no signature or record shape changed. `goga lint` re-run after each edit: 87 cells, 0 errors.

### Fixed CODEMANIFEST Defects

- `goga/codegraph/facts/CODEMANIFEST` (`ImportRef.names`, type + property annotations): before — "empty for wildcard imports" only; after — "empty for wildcard imports **and Python plain imports; the literal `default` marks a JavaScript default import**". Reason: interface↔interface consistency — a JS default import carries a local alias, not an origin name; recording the alias made exact-origin resolution impossible (silent link loss), violating the ADR exactness invariant.
- `goga/codegraph/facts/CODEMANIFEST` (`FileFacts.exports`, type + property annotations): before — "Explicit export list (Python `__all__`)"; after — "**JavaScript the exported names of export clauses plus the name declared by a named default export**". Reason: type↔type consistency — the JS facade ("exports of index.js") was not derivable from `Declaration` records alone (`export { b as c }` renames and default-export names were lost), so facade derivation and named-import resolution were inexact.
- `goga/codegraph/analysis/CODEMANIFEST` (`collect_facts` step 4): added "a plain import records no names" — pins the `names=[]` convention for Python plain imports that resolution later expands via member access.
- `goga/codegraph/analysis/CODEMANIFEST` (`collect_facts` step 5): before — "python `__all__`"; after — "python `__all__`; javascript — the exported names of export clauses plus the name declared by a named default export" (consumer side of the `exports` amendment).
- `goga/codegraph/analysis/CODEMANIFEST` (`resolve_links` step 2): added "the `default` pseudo-name resolves to the default-exported name of the resolved file" to the javascript origin rule.
- `goga/codegraph/analysis/CODEMANIFEST` (`resolve_links` step 3): before — "Expand wildcard imports…"; after — "Expand wildcard **and plain** imports to the names actually used in the importing file — a plain import expands through member access on the imported path or alias". Reason: Python plain imports and Go/JS namespace-style imports carry no names; without expansion they could never produce links although the contract explicitly captures them.

### Fixed Usage-File Defects

- `goga/codegraph/facts/.usages/records.md` (Preconditions): synced with the amended `names` conventions — "a Python plain import carries no `names`; a JavaScript default import carries the literal name `default`". Approved by the user (q2).

## Applied Fixes — Design Review Pass

Fixes applied during the design-review verification pass (code-stack and test-stack tracing). Each was approved by the user via the review dialog.

### R1 — Expansion inputs for `resolve_links` (Critical, CODEMANIFEST + design)

- Defect: `resolve_links` step 3 requires expanding wildcard/plain/namespace imports to "the names actually used in the importing file", but no record carried those names (or attribute chains / aliases), and the cross-cutting once-per-run parse contract forbade re-reading files — expansion was impossible; every such import would silently yield zero links.
- Fix: `collect_facts` now additionally records one usage `ImportRef` per wildcard/plain/namespace import (same specifier and flags as the base import, `names` = member names accessed through the import's local binding; wildcard/plain usage refs collect every used identifier of the file — generous collection, resolution filters by the facade). Applied to: `goga/codegraph/analysis/CODEMANIFEST` (collect_facts step 4), `goga/codegraph/facts/.usages/records.md` (Preconditions), and this document (collect extractors, resolve algorithm steps 2.3–2.4, per-language origin rules). Swift's usage ref remains as designed. Aliased plain imports still record no usage ref (known v1 limitation, unchanged).

### R2 — Kotlin extractor node inventory (Critical, design + cook)

- Defect: the kotlin extractor referenced node types that do not exist in the pinned `tree-sitter-kotlin>=1.1.0` grammar — `import_header`, `wildcard_import`, `import_alias`, `simple_identifier`/`type_identifier` name children, `package_header` → bare `identifier` children. Verified empirically (parse-tree dumps against 1.1.0): top-level import nodes are `import` (wildcard = trailing anonymous `*`; alias = `as` + `identifier`); declaration names are plain `identifier` children; `package_header` wraps a `qualified_identifier`. Following the old text verbatim yields zero declarations/imports for every Kotlin file → empty facades → `[]` for every Kotlin project.
- Fix: rewrote the kotlin bullet of the design's per-language extractors to the actual 1.1.0 inventory, and corrected `.goga/usages/cooks/tree-sitter-kotlin.md` (Declarations names, Names and identifiers, Import and package, enum entries, traversal patterns) so future implementations are not misled. Test semantics unchanged (`test_collect_facts_kotlin_package_and_visibility` remains valid).

### R3 — Relative-import specifier keeps the level dots (High, design)

- Defect: the python extractor said `specifier = remaining dotted text, "" for bare dots` — stripping the leading dots loses the relative level (`from .util import x` and `from ..util import x` become indistinguishable; `ImportRef` has no level field), contradicting the design's own test assertion `("..util", ("helper",), True, False)`, the CODEMANIFEST (`specifier` — "raw origin string as written"), and the resolver's level derivation ("level L → go up L-1 directories").
- Fix: the specifier keeps the leading dots exactly as written — `..util`; `.` for a bare `from . import x`. The resolver derives the level from the leading dots (origin rule unchanged). No test or CODEMANIFEST change needed — the algorithm now matches them.

### R4 — Element-wise `default` mapping in JS resolution (High, design)

- Defect: resolve step 2.5 triggered only on exact `r.names == ["default"]`, so mixed clauses (`import c, { query } from ...` → `names=["default", "query"]`) never triggered the mapping and "default" was silently dropped at the facade filter — the default-imported type was lost for the most common JS import form, contradicting the design's own test trace (which maps "default" element-wise and expects `["conn", "query"]`).
- Fix: step 2.5 maps each `"default"` entry element-wise to the resolved file's default-exported name (from its exports); files with no named default export map to nothing. CODEMANIFEST wording already correct ("the default pseudo-name resolves to the default-exported name of the resolved file").

### R5 — Non-cell sources in the Go and JS resolve fixtures (High, design tests)

- Defect: both fixtures made the importing unit a non-cell, so the link they assert is impossible — Go: `main.go` declared nothing exported (plus `store.NewUser()` written at top level is not valid Go — an ERROR node would abort the run); JS: the mid-design "correction" (`svc/index.js` re-exporting nothing) still yields an empty facade. The step-2.7 skip rule (and the CODEMANIFEST requirement "a link is produced only when the importing unit is a cell") would drop the asserted links; both tests would fail.
- Fix: Go — `main.go` gains `func Run() { store.NewUser() }` (exported → the root unit is a cell); `import "fmt"` kept for the external-drop check. JS — `svc/index.js` becomes `export { run } from "./a.js";` (facade `["run"]` → a cell) and `svc/a.js` holds the import plus `export function run() { c(); query(); }`. Assertions unchanged.

### R6 — `max_depth=1` filter case asserted `max_depth=0` behavior (High, design test)

- Defect: the parity test's case3 fed `max_depth=1` but asserted `doc[0]["children"] == []` — that is the `max_depth=0` result. Schema `_prune_depth` keeps one level at depth 1 (root at depth 0 keeps children; nodes at depth >= max_depth are emptied). The design's own Edge Cases section already stated "`max_depth=0` empties every root's children". The wrong expectation would either fail against a correct implementation or induce a parity-breaking "fix".
- Fix: case3 now asserts `len(doc[0]["children"]) == 1 and doc[0]["children"][0]["children"] == []` (one level survives, leaf pruned) and a new case4 covers `max_depth=0` → `doc[0]["children"] == []`. Algorithm and CODEMANIFEST unchanged (the transcription already matched `_prune_depth`).

### R7 — Medium/Low bundle (design tests and text)

- **Test gap (Medium)**: added `test_resolve_links_non_cell_source_no_link` — the CODEMANIFEST requirement "a link is produced only when the importing unit is a cell" had no coverage (all positive fixtures had cell sources by construction).
- **Mixed-language test (Medium)**: `test_resolve_links_external_and_ambiguous_names_silent` mixed a python setup and a swift setup in one `resolve_links` call (one language per run); split into `test_resolve_links_python_external_names_silent` and `test_resolve_links_swift_ambiguous_name_no_link`, with the swift using unit made a cell so ambiguity is the only drop reason.
- **JS trace (Low)**: removed the phantom `hidden (is_public False)` Declaration — `hidden` is undeclared in the fixture (export-clause specifier only).
- **Wording (Low)**: "six kinds" → "five kinds" (the JS declaration list has five entries, matching the cook); the frozen-record trace no longer claims list mutation is "guarded" (frozen forbids reassignment; list contents are immutable by convention; the copy guards aliasing only).
- **Cosmetics (Low)**: fixed the `declarments` typo and the garbled Go assertions; cleaned the swift trace's inline self-correction; named the actual python field `module_name`; renamed `test_collect_facts_python_declarations_imports_and_all` → `..._and_init_bindings` (the fixture has no `__all__`); documented that cwd pinning comes from the autouse `_isolate_cwd` fixture.


## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

- **Config flow**: `load_project_config()` reads `.goga/config.yml` from cwd → `ProjectConfig.language: str` and `ProjectConfig.lint: LintConfig | None` (`.ignore: list[str]`, `[]` when the key is absent). Passed as scalars downstream; the config object does not travel past the orchestrator.
- **Discovery flow**: `files: list[Path]` — relative paths, sorted deterministic walk order; produced from paths only (no file reads).
- **Facts flow**: one `FileFacts` per input file, input order preserved; `Declaration`/`ImportRef` nested inside; `exports` per the amended semantics; `module` non-empty only for Kotlin (package).
- **Units flow**: flat `list[Unit]` sorted by path; nesting is derivable from paths and is rebuilt by the renderer.
- **Links flow**: one `CellLink` per (importing unit, defining unit) pair, `types` sorted unique facade names.
- **Output flow**: `render_graph` builds `CodegraphNode` trees, applies filters, serializes with `json.dumps(indent=4, sort_keys=True, ensure_ascii=False)`; the CLI echoes the document to stdout.

### Entity Dependencies

Initialization/design order (leaves → root, matches the arch plan):

1. `goga/codegraph/facts` (leaf) — records only.
2. `goga/codegraph/analysis` — consumes facts records.
3. `goga/codegraph` — consumes facts + analysis + `goga/config` (existing, as-is).
4. `goga/commands/codegraph` — consumes the `codegraph` routine.
5. `goga/commands` — re-export (`->codegraph: {}`).
6. `goga` — root group registration (`cli.py` wiring).

No cross-imports; the chain is acyclic (`goga schema` confirms).

## Code Stack Trace

All traces verified against the actual implementation of the consumed cells (`goga/config/project/loader.py` via `project-configuration.md`, `goga/schema/schema.py`, `goga/ast/ast.py`, `goga/commands/schema/schema.py`, `goga/contract/*/` idiom references).

### Trace: `codegraph` (goga/codegraph, orchestrator)

#### Chain

1. **Input**: CLI wrapper call `codegraph_logic(list(cells), max_depth, list(depends_on))`; cwd = project root (the click group makes no directory changes; the command runs where invoked).
2. `load_project_config()` → checkpoint: absent `.goga/config.yml` raises `FileNotFoundError` — the uninitialized-project error propagates to the CLI (matches `codegraph-usage.md` failure list) → **passed** (verified in `goga/config/project/loader.py` semantics via `project-configuration.md`).
3. `config.language` validated against `{python, golang, javascript, kotlin, swift}` → checkpoint: outside the set raises `ValueError` with a message naming the offending language and the supported set → **passed** (config strings match `goga-lang-disp` naming: `python`, `golang`, `javascript`, `kotlin`, `swift`).
4. `ignore = config.lint.ignore if config.lint is not None else []` → checkpoint: absent `lint` section yields `None` per `project-configuration.md` ("Absence of the `lint` section ⇒ `config.lint is None`") → **passed**; `LintConfig.ignore` is `list[str]`, `[]` when absent/empty.
5. `files = discover_sources(language, ignore)` → checkpoint: `list[str] → list[Path]` type match → **passed**.
6. `root = Path.cwd()` (per the `stages` practice) → checkpoint: consistent with step 2 — the config was loaded from cwd, so the same root governs module resolution → **passed**.
7. `facts = collect_facts(files, language)`; `units = derive_units(facts, language)`; `links = resolve_links(units, facts, language, root)` → checkpoint: stage arities/types match the analysis contract (`list[FileFacts]`, `list[Unit]`, `list[CellLink]`) → **passed**; unparseable input raises here and aborts the run (fail closed).
8. `json = render_graph(units, links, cells, max_depth, depends_on)` → checkpoint: `-> json: str` returned to the wrapper → **passed**.
9. **Output**: the JSON document string; the wrapper echoes it to stdout.

#### Checkpoint Summary

- Config boundary (absent config, absent lint) — passed.
- Language naming parity (`golang`, `javascript` — not `go`/`js`) — passed; pinned in Algorithm Design.
- Stage type flow — passed.
- Error propagation contract (three failure modes of `codegraph-usage.md`) — passed.

### Trace: `collect_facts`

1. **Input**: `files: list[Path]` (relative), `language: str` (validated upstream).
2. Per file (input order): read bytes once; parse with the language grammar → checkpoint: exactly one read + one parse per file (requirement) → **passed** (single `Path.read_bytes()` + single `parser.parse()`).
3. Parse validation: any `ERROR`-typed node or `node.is_missing` in the tree → raise an error naming the file → checkpoint: fail-closed, message carries the relative path → **passed**.
4. Declaration extraction per language rules (see Algorithm Design) → checkpoint: `Declaration(path, name, is_public)` construction, `is_public` decided before construction (records precondition) → **passed**.
5. Import extraction per language rules → checkpoint: amended `names` conventions honored (wildcard/plain → `[]`, JS default → `["default"]`, named imports record origin names, Swift pure usages carry `specifier=""`); every wildcard/plain/namespace import additionally records one usage `ImportRef` carrying the member names accessed through its local binding (same specifier and flags; wildcard/plain usage refs collect every used identifier of the file) — without the usage refs the resolution stage has no expansion input → **passed** (after review fix R1).
6. `exports` extraction (python `__all__`; javascript clause + default names) → checkpoint: `list[str]`, as-written order, deduplicated → **passed** (after fix).
7. **Output**: `FileFacts` built in input order → checkpoint: order preservation requirement → **passed**.

### Trace: `derive_units`

1. **Input**: `facts: list[FileFacts]`, `language: str`.
2. Group by parent directory; a directory is a unit iff the language rule holds over its analyzed files → checkpoint: "a unit owns exactly the source files of its own directory"; files in non-unit directories belong to no unit → **passed**.
3. Facade derivation per language rule (python from `__init__.py` only; go across all files; js from `index.js` facts ∪ `exports`; kotlin/swift across all files) → checkpoint: facade ⊆ public declarations, sorted unique → **passed**.
4. `is_cell = facade != []` → checkpoint: non-cell units retained as structural ancestors (not dropped) → **passed**.
5. **Output**: flat `list[Unit]` sorted by path → checkpoint: deterministic path order requirement; nesting deferred to the renderer (Unit carries no children field — consistent with the record shape) → **passed**.

### Trace: `resolve_links`

1. **Input**: `units`, `facts`, `language`, `root: Path` (absolute).
2. Build the project-wide index first (unit path ↔ language identity; facade name → defining units; kotlin package → units; python module string → unit) → checkpoint: collect-then-resolve, never unit-locally → **passed**.
3. Per import, resolve the origin per the language rule (see Algorithm Design) → checkpoint: origin exactness (module resolution against `<root>`/`<root>/src`, go.mod module mode, Node-style relative resolution, kotlin package map, swift unique name) → **passed**.
4. Expand wildcard/plain/namespace imports to actually-used names → checkpoint: expansion reads the usage `ImportRef`s recorded by `collect_facts` (same file, same specifier and flags as the base import) — no file re-reading, no re-parsing (the once-per-run parse contract holds); `default` mapped to the resolved file's default-exported name → **passed** (after review fix R1).
5. Keep only resolutions landing on a facade type of a unit cell; drop self-links, non-cell sources, external origins silently → checkpoint: "no link and no error" requirement → **passed**.
6. **Output**: aggregate per unit pair, `types` sorted unique → checkpoint: one `CellLink` per pair requirement → **passed**.

### Trace: `discover_sources`

1. **Input**: `language: str`, `ignore: list[str]` (exact relative paths).
2. `os.walk(".")` top-down with `dirnames.sort()` in place → checkpoint: deterministic order requirement → **passed**.
3. Prune directories whose `normpath(relpath(dir)) ∈ {normpath(x) for x in ignore}`; skip files likewise → checkpoint: same mechanics as lint (`goga/ast/ast.py:92-108` — normpath, trailing slash insignificant, no glob) → **passed**.
4. Skip idiomatic test files per language; keep primary extension → checkpoint: pattern table and extension table match the contract → **passed**.
5. **Output**: `list[Path]` relative to root → checkpoint: consumed by `collect_facts(files, ...)` which resolves them against cwd → **passed**.

### Trace: `render_graph`

1. **Input**: `units`, `links`, `cells`, `max_depth`, `depends_on`.
2. Nest units by path (nearest ancestor unit), then emit nodes for cell units only, attaching each to its nearest cell-unit ancestor → checkpoint: "only units that are cells carry output nodes; non-cell units survive only as structural ancestors" → **passed** (compression semantics — see Algorithm Design).
3. Aggregate links per source cell into `dependencies: dict[str, list[str]]` (target path → sorted unique types; `{}` when no outgoing links) → checkpoint: node fields exactly `cell, types, dependencies, children` → **passed**.
4. Filters in order `cells` → `depends_on` → `max_depth`, mirroring `goga/schema/schema.py` `_filter_tree`/`_filter_by_depends_on`/`_prune_depth` → checkpoint: parity verified line-by-line against the schema implementation, including the ancestor-skeleton behavior and root depth 0 → **passed**.
5. Serialize via `beautiful_json`; empty tree → `"[]"` → checkpoint: matches schema's early `"[]"` return → **passed**.
6. **Output**: JSON document string.

#### Checkpoint Summary (render)

- Filter parity with the schema command — passed (semantics transcribed in Algorithm Design).
- Determinism (sorted roots, sorted children, sorted dependency keys via `sort_keys`) — passed.

### Trace: `codegraph` (goga/commands/codegraph, CLI wrapper)

1. **Input**: click invocation; `cells: tuple[str, ...]` (CELLS variadic), `max_depth: int | None` (`--max-depth`), `depends_on: tuple[str, ...]` (`--depends-on`, repeatable) → checkpoint: surface identical to `goga/commands/schema/schema.py:8-17` → **passed**.
2. `codegraph_logic(list(cells), max_depth, list(depends_on))` inside `try` → checkpoint: tuple→list conversion mirrors the schema wrapper → **passed**.
3. `except Exception as e:` → `click.echo(str(e), err=True)`; `ctx.exit(1)` → checkpoint: stdout untouched on failure, no traceback → **passed** (mirrors schema wrapper; covers `FileNotFoundError`, `ValueError`, parse errors).
4. `click.echo(result)` → **Output**: JSON document on stdout, exit 0.

## Algorithm Design

Conventions for all implementations: relative imports inside the `goga` package (per `convention`); Google-style docstrings; `from __future__ import annotations`; frozen `kw_only=True` dataclasses with empty defaults (`""`, `[]` via `default_factory`, `False`) per the conventions' data-model rules; no mutation of caller-owned lists (copy on construction); no environment reads.

### `Declaration`, `ImportRef`, `FileFacts`, `Unit`, `CellLink`, `CodegraphNode`

**Responsibility**: the immutable data vocabulary of the analysis (records carry data only).

**Algorithm** (construction rules, shared):

```
1. Construct via keyword-only arguments only.
2. Copy every sequence argument into a fresh list (no aliasing of caller data).
3. No post-construction mutation — frozen; derive new records instead.
4. Defaults per the conventions: str fields "", list fields [], bool fields False,
   CodegraphNode.children [], dependencies {}.
```

**Errors**: mutation raises `dataclasses.FrozenInstanceError`; unexpected keyword raises `TypeError`.

**Edge Cases**: empty collections are valid and meaningful (empty facade = non-cell; empty names = wildcard/plain import).

---

### `discover_sources`

**Responsibility**: deterministic, path-only discovery of analyzable source files.

**Algorithm**:

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

**Errors**: none (an unknown language cannot reach here — validated upstream; a defensive `KeyError` is acceptable and surfaces as a command failure).

**Edge Cases**: `ignore` entry with trailing slash matches the directory (`normpath` semantics, same as `goga lint`); ignored directory prunes its whole subtree; unlike the AST walk, `.project` is NOT skipped — the exclusion list is exactly the given list; a file named like a test pattern is skipped even when also excluded (idempotent skip).

---

### `collect_facts`

**Responsibility**: single-pass per-file parsing and fact extraction.

**Algorithm**:

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

**Per-language extractors** (top-level = direct children of `root_node`; unwrap `decorated_definition` (python) to its inner definition):

- **python**
  - Declarations: `function_definition` / `class_definition` → name via `child_by_field_name("name")`; `is_public = not name.startswith("_")`.
  - In a package `__init__.py` additionally every top-level bound name: import bindings (`import a.b` → `a`; `import a.b as c` → `c`; `from m import x, y as z` → `x`, `z`), and assignment targets (`assignment.left` → identifier, or each identifier of a tuple target). Each bound name not already recorded → `Declaration(is_public = not name.startswith("_"))`.
  - Imports: `import_statement` → per child `dotted_name`/`aliased_import`: `ImportRef(specifier=<full dotted text>, names=[], is_relative=False, is_wildcard=False)`. `import_from_statement` → `module_name` field: `dotted_name` (absolute) or `relative_import` — for a relative import the specifier keeps the leading dots exactly as written (`..util`; `.` for a bare `from . import x`), `is_relative=True`; the resolver derives the level from the leading dots (review fix R3); names field: per `dotted_name` the imported (pre-`as`) name, per `aliased_import` the original name; `wildcard_import` → `names=[], is_wildcard=True`.
  - Exports: top-level `assignment` with left identifier `__all__` and right a string list → decoded elements, as-written order, deduplicated. (Augmented `__all__ += [...]` is not read in v1.)
  - Usage refs (review fix R1): one per plain import — `ImportRef(specifier=<the import's specifier>, names=<member names accessed through the import's root binding>, is_relative=False, is_wildcard=False)` (maximal attribute chains whose first segment is the root binding; the first segment after the prefix is the used name); one per wildcard import — `names` = every used identifier of the file outside import statements (generous collection). The base import keeps `names=[]`; only the usage ref carries names. An aliased plain import records no usage ref (known v1 limitation).
- **golang**
  - Declarations (package scope only): `function_declaration` (name); `type_spec` inside each `type_declaration` (name); `var_spec` inside `var_declaration` and `const_spec` inside `const_declaration` (name). `is_public = name[:1].isupper()`. `method_declaration` is NOT recorded — a method name is receiver-scoped, not a package-level identifier (per `goga-cell-go`: methods associate with their struct; the facade is the package's exported identifiers).
  - Imports: `import_declaration` → per `import_spec`: path = `interpreted_string_literal` text without quotes → `ImportRef(specifier=path, names=[], is_relative=False, is_wildcard=False)`.
  - Usage refs (review fix R1): one per import — `ImportRef(specifier=path, names=<member names accessed through the implicit local binding — the last path segment>, is_relative=False, is_wildcard=False)`, from `selector_expression` chains rooted at the binding. An aliased import records no usage ref (known v1 limitation).
  - Exports: none — `[]`.
- **javascript** (ESM only)
  - Declarations: top-level declarations of the five kinds (`function_declaration`, `class_declaration`, `generator_function_declaration`, `lexical_declaration`, `variable_declaration`); name via `name` field / first `variable_declarator` identifier. `is_public = True` iff exported: `export_statement` wrapping the declaration, or the name appears as an exported specifier in an `export_clause`. Anonymous default exports record nothing.
  - Imports: `import_statement` → source string without quotes; `is_relative = specifier.startswith(".") or specifier.startswith("/")`. Clause: default identifier → `names=["default"]`; named imports → the imported (pre-`as`) names; `namespace_import` → `names=[], is_wildcard=True`. Mixed clauses (`import d, { a } from ...`) → one `ImportRef`, `names=["default", "a"]`.
  - Exports: `export_clause` → the exported (post-`as`) specifier names; `export default <named declaration>` → that declaration's name; both appended in source order, deduplicated.
  - Usage refs (review fix R1): one per namespace import — `ImportRef(specifier=<the import's specifier>, names=<member names accessed through the namespace alias>, is_relative=True|False as the base, is_wildcard=True)` from `member_expression` chains rooted at the alias.
- **kotlin** (node inventory per the amended cook — grammar 1.1.0; review fix R2)
  - Declarations: top-level `function_declaration`, `class_declaration`, `object_declaration`, `type_alias`, `property_declaration`; name from the direct `identifier` child (positional — the pinned tree-sitter-kotlin 1.1.0 exposes plain `identifier` name children and most nodes have no named fields; a `property_declaration`'s name is the `identifier` inside its `variable_declaration`). `is_public = True` iff the `modifiers` container child carries no `visibility_modifier` or the modifier is `public` (implicit-or-explicit public).
  - Imports: top-level `import` nodes — specifier = the `qualified_identifier` text; a trailing anonymous `*` sibling (after the final `.`) marks `is_wildcard=True, names=[]`; otherwise `names=[last segment of the qualified identifier]` (an `as <identifier>` suffix — an import alias — does not change the origin). `is_relative=False`. `package_header` → `module` = its `qualified_identifier` text.
  - Usage refs (review fix R1): one per wildcard import — `ImportRef(specifier=<the import's specifier>, names=<every used identifier of the file>, is_relative=False, is_wildcard=True)` (generous collection).
- **swift**
  - Declarations: top-level `function_declaration`, `class_declaration` (kinds actor/class/enum/struct — an `extension` declares no new name and is not recorded, nor are its members), `protocol_declaration`, `init_declaration`, `property_declaration`, `typealias_declaration`; name via `name` field. `is_public = True` iff a `visibility_modifier` child is `public` or `open`.
  - Imports: `import_declaration` → `ImportRef(specifier=<module identifier text>, names=[], is_relative=False, is_wildcard=False)`. Additionally one usage ref per file: `ImportRef(specifier="", names=sorted unique texts of every type_identifier outside import declarations, is_relative=False, is_wildcard=False)` — generous collection is safe: declaration names resolve to the own unit (self-link dropped), external names never resolve, ambiguous names are dropped by the uniqueness rule.
  - Exports: none — `[]`.

**Errors**: `ValueError` naming the file on any `ERROR`/`MISSING` node.

**Edge Cases**: empty file → valid parse, all-empty facts; file order preserved regardless of walk grouping; a wildcard import never records names; `__init__.py` bindings include imported names (they are facade candidates).

---

### `derive_units`

**Responsibility**: pure grouping of facts into language units with facades; no file reads.

**Algorithm**:

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

**Per-language facade rules**:

- **python**: from the `__init__.py` facts only — `exports` (`__all__`) when non-empty, otherwise the names of its `is_public` declarations (the non-underscore top-level bound names).
- **golang**: union over all unit files of `is_public` declaration names (exported package-level identifiers: functions, types, vars, consts).
- **javascript**: from the `index.js` facts — `{declaration names with is_public} ∪ exports` (export-clause names and the named default export).
- **kotlin**: union over all unit files of `is_public` declaration names.
- **swift**: union over all unit files of `is_public` declaration names (public/open only).

**Errors**: none.

**Edge Cases**: a directory with sources but failing the unit rule (python without `__init__.py`, javascript without `index.js`) contributes no unit — its files are analyzed yet never grouped (per contract); nested unit dirs form their own units (own-directory files only); a unit whose facade is empty is kept with `is_cell=False` (structural ancestor).

---

### `resolve_links`

**Responsibility**: project-wide, exact-origin resolution of imports/usages into unit-pair links.

**Algorithm**:

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

**Per-language origin rules**:

- **python (absolute)**: module `m` → try in order: `<root>/m` package dir (unit), `<root>/m.py` file (its directory's unit), `<root>/src/m` package dir, `<root>/src/m.py` file. First hit wins; none → external.
- **python (relative)**: base = the importing file's directory (for `__init__.py` the directory itself, i.e. its own package); level `L` → go up `L-1` directories from base; append the module part when present. `from . import x` → target = that directory as unit; `from .m import x` → `base/m` package dir, else `base/m.py` file → its directory's unit.
- **python (plain `import a.b.c`)**: resolve the module as above, then expand via the usage ref recorded at collect — maximal attribute chains rooted at the import's first segment, the segment after the prefix being the used name (`import a.b.c as d` records no usage ref — the alias is not carried by the record; known v1 limitation).
- **python (wildcard `from m import *`)**: expand via the wildcard usage ref recorded at collect (every used identifier of the file) ∩ the resolved unit's facade.
- **golang**: import path `p`: `p == M` → unit `<root>`; `p` starts with `M + "/"` → unit `<root>/<suffix>`; else external (also external when `go.mod` is absent). Expansion: the usage ref recorded at collect — `selector_expression` chains `binding.X` rooted at the implicit local binding (the last segment of `p`; an aliased import records no usage ref — known v1 limitation).
- **javascript**: relative specifier `s` against the importing file's directory: `s` ends with `.js` → file `s`; else file `s + ".js"`, then directory `s` → its `index.js`. Directory-form specifiers (`./x/`) → `x/index.js`. The resolved file's unit = the file's directory (if it is a unit). Bare specifiers → external. `default` → mapped per algorithm step 2.5. Namespace wildcard expands via the usage ref recorded at collect (member accesses on the alias, `ns.X`).
- **kotlin**: import `pkg.Name` → units whose files declare `package pkg`, keeping those whose facade contains `Name` (link each such unit; normally exactly one). Wildcard `pkg.*` → expand via the usage ref recorded at collect (the file's used simple identifiers) ∩ the facades of `pkg`'s units.
- **swift**: for each used type name `n` in the usage ref: the units whose facade contains `n`; exactly one → link it; zero or ≥2 → no link (uniqueness rule; compiler guarantees per-module uniqueness, project-wide duplicates are treated as ambiguous).

**Errors**: none — every unresolvable name is silently dropped (contract: "no link and no error").

**Edge Cases**: self-imports produce no link; imports by non-cell units produce no link; cycles pass through as two opposite links; stdlib/third-party names never resolve (no `PYTHONPATH`/`GOPATH`/env reads — deterministic); a facade name re-exported through `__init__.py` links to the declaring unit only when the import's resolved module lands there.

---

### `render_graph`

**Responsibility**: node-tree assembly, schema-parity filtering, serialization.

**Algorithm**:

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

**Errors**: none.

**Edge Cases**: non-cell ancestors vanish from the output while keeping the skeleton (a nested cell surfaces under its nearest cell ancestor or as a root); a cell with no outgoing links carries `dependencies: {}`; `max_depth=0` empties every root's children; determinism — identical inputs produce byte-identical output.

---

### `codegraph` (orchestrator)

**Responsibility**: wire config → discovery → analysis → rendering; own the failure contract.

**Algorithm**:

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

**Errors**: `FileNotFoundError` (uninitialized project), `ValueError` (unsupported language; unparseable file — message names the file), config loader errors (`KeyError`, `ValueError`, `yaml.YAMLError`) — all propagate to the CLI wrapper, which renders them as clean stderr failures.

**Edge Cases**: no analyzable sources → empty units/links → `"[]"`; read-only — nothing is written; the default `depends_on=[]`/`max_depth=None` are never mutated (iterate only).

---

### `codegraph` (CLI wrapper)

**Responsibility**: click surface, delegation, clean failure rendering; no domain knowledge.

**Algorithm**:

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

**Errors**: any exception → stderr message, exit 1, empty stdout, no traceback.

**Edge Cases**: zero CELLS arguments → all cells; repeated `--depends-on` → tuple in passing order, converted to list; `--max-depth` absent → `None`.

**Wiring** (per the `cli-commands` practice): `goga/commands/codegraph/__init__.py` re-exports `codegraph`; `goga/commands/__init__.py` gains `from .codegraph import codegraph` and `"codegraph"` in `__all__`; `goga/cli.py` imports it and calls `app.add_command(codegraph)` right after `schema`.

## Cross-cutting Concerns

- **Error handling**: fail closed at the single parse boundary (any `ERROR`/`MISSING` node aborts the run naming the file); unsupported language and uninitialized project abort before any walk; every unresolvable name is silent (no link, no error); the CLI wrapper converts any exception into a clean stderr message + exit 1; nothing but the JSON document ever reaches stdout; no validation verdicts on the derived graph (purely descriptive — cycles pass through).
- **Validation**: language whitelist at the orchestrator; config structural validation is owned by `goga/config` (untouched); parse validation owned by `collect_facts`; no graph validation anywhere (per scope).
- **Logging**: none in v1 — the command's output contract is stdout-JSON-only and diagnostics are the error channel; matches the existing `schema` command (which logs nothing).
- **Caching**: within a run, each file is read and parsed exactly once and every record is reused by all later stages; no cross-run caching (determinism contract: identical inputs must re-produce byte-identical output without stale state).
- **Concurrency**: single-threaded, no shared mutable state; all records immutable; determinism does not depend on scheduling.
- **Determinism (overarching)**: sorted walk (`dirnames.sort()`, sorted filenames), input-order fact preservation, path-sorted units and node ordering, sorted unique facades/dependency types, `sort_keys=True` serialization; no environment variables, no clocks, no randomness.

## Usages Analysis

### `convention`

- **What it provides**: mandatory engineering/testing conventions for all Python code in the repo (relative imports, frozen `kw_only` dataclasses, docstring style, test structure, CLI docstring rules).
- **Where used**: global Annotations of all four new cells.
- **Why chosen**: project-wide mandatory baseline.
- **How exactly**: dataclasses with `kw_only=True` + empty defaults for the records; relative intra-package imports; Google docstrings everywhere except the click callback; tests mirror `goga/codegraph/...` under `tests/codegraph/...`.

### `tree-sitter-python` / `tree-sitter-go` / `tree-sitter-js` / `tree-sitter-kotlin` / `tree-sitter-swift`

- **What they provide**: parser setup (`Language(pkg.language())` + `Parser`) and the node-type inventory per grammar.
- **Where used**: `collect_facts` (global Annotations of `goga/codegraph/analysis`).
- **Why chosen**: tree-sitter is the project's shipped parsing stack (`pyproject.toml` already pins `tree-sitter>=0.25.2` and all five grammars); no new dependencies.
- **How exactly**: node-type traversal (`node.children`, `child_by_field_name`, `node.text.decode("utf-8")`) exactly along the documented node inventories — declarations per the Declarations sections, imports per the (branch-enriched) Imports sections; kotlin names extracted positionally (no named fields per the cook's IMPORTANT note).

### `beautiful_json`

- **What it provides**: the canonical JSON serialization form.
- **Where used**: `render_graph` (algorithm step 6).
- **Why chosen**: byte-parity with the `schema` command output conventions.
- **How exactly**: `json.dumps(nodes, indent=4, sort_keys=True, ensure_ascii=False)`; empty forest short-circuits to `"[]"`.

### `click`

- **What it provides**: command surface construction and clean error rendering.
- **Where used**: CLI wrapper `codegraph` (type-level annotation + global Annotations of `goga/commands/codegraph`).
- **Why chosen**: the CLI framework of the product; the schema command is the declared reference surface.
- **How exactly**: `@click.command()`, CELLS variadic `nargs=-1`, `--max-depth` int option, `--depends-on` repeatable (`multiple=True` — the value is a tuple, emptiness tested, never `None`); `click.echo` for output; `click.echo(..., err=True)` + `ctx.exit(1)` for failures (no `sys.exit` inside commands per the anti-patterns).

### Imported Usages

- `records` from `goga/codegraph/facts` — construction conventions for every fact record; path: `goga/codegraph/facts/.usages/records.md`. Referenced by `collect_facts`/`derive_units`/`resolve_links`/`render_graph` annotations.
- `stages` from `goga/codegraph/analysis` — stage order, completeness requirement, `root = Path.cwd()`, failure behavior for the caller; path: `goga/codegraph/analysis/.usages/stages.md`. Referenced by the `codegraph` orchestrator annotation.
- `project-configuration` from `goga/config` — loader semantics (mandatory `.goga/config.yml`, `FileNotFoundError` when absent; `lint` absent → `None`; `LintConfig.ignore` exact-path list); path: `goga/config/.usages/project-configuration.md`. Referenced by the orchestrator annotation.
- `codegraph-usage` from `goga/codegraph` — output node format, guarantees, failure modes behind the CLI; path: `goga/codegraph/.usages/codegraph-usage.md`. Referenced by the CLI wrapper annotations.

## `.usages/` Update

### Cell: `goga/codegraph/facts`

#### Existing Files — Consistency

- **`records.md`** → `goga/codegraph/facts/.usages/records.md`
  - Status: current after this design pass.
  - Additions applied (user-approved q2): Preconditions now state that a Python plain import carries no `names` and a JavaScript default import carries the literal name `default`.
  - Updates needed: none.

### Cell: `goga/codegraph/analysis`

#### Existing Files — Consistency

- **`stages.md`** → `goga/codegraph/analysis/.usages/stages.md`
  - Status: current — stage order, caller-owned discovery, and failure behavior are unaffected by the annotation amendments.
  - Additions needed: none. Updates needed: none.

### Cell: `goga/codegraph`

#### Existing Files — Consistency

- **`codegraph-usage.md`** → `goga/codegraph/.usages/codegraph-usage.md`
  - Status: current — node format, guarantees, and failure modes match the amended contract (the amendments improved link precision without changing the output shape).
  - Additions needed: none. Updates needed: none.

### Cell: `goga/commands/codegraph`

No `.usages/` directory — consumer documentation lives in the provider practice `codegraph-usage` (same pattern as `goga/commands/schema`).

### Cell: `goga/commands`

- **`cli-commands.md`** — current (17 commands; import lists, subcell import, registration, and table row updated by apply-architecture; verified row count and no stale "16 CLI" references).

## Test Stack Trace

### General Setup

- Structure mirrors source per `convention`: `tests/codegraph/facts/test_facts.py`, `tests/codegraph/analysis/test_collect.py|test_units.py|test_resolve.py`, `tests/codegraph/test_codegraph.py|test_discovery.py|test_render.py`, `tests/commands/codegraph/test_codegraph.py`; `__init__.py` in each directory.
- Shared fixtures: `tmp_path` for all filesystem state; the process cwd is pinned to `tmp_path` by the autouse `_isolate_cwd` fixture of `tests/conftest.py` (the `cwd` symbol there is a context manager for explicit re-pinning, not a fixture); `empty_package_environment` (tests/commands/conftest.py) for CliRunner tests. No mocks (pure logic + real files).
- Per-language fixtures build tiny in-memory projects on `tmp_path` and invoke the stage functions directly; CLI tests invoke the registered `app` via `CliRunner`.

### Source File Registry

- `goga/codegraph/facts/facts.py` (+ `__init__.py` facade)
- `goga/codegraph/analysis/collect.py`, `units.py`, `resolve.py` (+ facade)
- `goga/codegraph/codegraph.py`, `discovery.py`, `render.py` (+ facade)
- `goga/commands/codegraph/codegraph.py` (+ facade)
- Modified: `goga/commands/__init__.py`, `goga/cli.py`, `tests/commands/test_commands_facade.py`

---

### Positive Tests

#### `test_facts_records_frozen_kw_only`

**Setup**: import all six record classes from `goga.codegraph.facts`.

**Input**: `Unit(path=Path("a"), files=[], facade=["X"], is_cell=True)`; then `unit.facade.append("Y")`.

**Trace**:
```
Unit(path=..., files=[], facade=["X"], is_cell=True)   # kw-only construction
  → returns record
unit.facade.append("Y")
  → not blocked mechanically: frozen forbids field reassignment, not list
    mutation; list-field contents are immutable by convention (build new
    records); the construction-time copy guards caller-list aliasing only
    (review fix R7)
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

**Sufficiency**: pins the immutability contract every stage relies on (no stage may mutate shared records); prevents a mutable-default or aliased-list regression.

---

#### `test_collect_facts_python_declarations_imports_and_init_bindings`

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

**Input**: `collect_facts([Path("pkg/__init__.py")], "python")` (cwd pinned to `tmp_path`).

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

**Sufficiency**: pins the python extractor's three fact families — definitions, `__init__` bound names (definitions + imported names + assignment targets), and the plain/from/relative import forms — the base of every downstream unit and link.

---

#### `test_collect_facts_golang_exported_package_scope_only`

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

**Sufficiency**: pins the goga-cell-go facade semantics — facade is exported package-level identifiers; a method name must never leak into a facade.

---

#### `test_collect_facts_javascript_default_pseudo_and_clause_exports`

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

**Sufficiency**: pins the approved 1A/2A semantics — the `default` pseudo-name, origin (pre-`as`) names for named imports, and export-clause/default names in `exports`; without it the exactness invariant silently regresses.

---

#### `test_collect_facts_kotlin_package_and_visibility`

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

**Sufficiency**: pins the implicit-public rule and the package→module capture that kotlin resolution is built on.

---

#### `test_collect_facts_swift_public_open_only_and_used_names`

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

**Sufficiency**: pins the swift facade rule (public/open only) and the usage-ref form that the unique-name resolution consumes.

---

#### `test_collect_facts_preserves_input_order`

**Setup**: files `b.py`, `a.py`, `c.py` (each `def x(): pass`) created in any order; input list `[Path("b.py"), Path("a.py"), Path("c.py")]`.

**Input**: `collect_facts([b, a, c], "python")`.

**Trace**: `facts[i].path == input[i]` for each i.

**Assertions**: `[f.path for f in facts] == [Path("b.py"), Path("a.py"), Path("c.py")]`.

**Sufficiency**: the order-preservation requirement feeds deterministic unit derivation; a sorted-inside-collect regression would reorder downstream output.

---

#### `test_derive_units_python_package_rule_and_facade`

**Setup**: `tmp_path` tree —
```
app/__init__.py            → __all__ = ["Service", "run"]
app/core.py                → class Service; def run
app/sub/__init__.py        → (empty)
app/sub/deep.py            → def helper
loose/mod.py               → def anything
```

**Input**: `facts = collect_facts(discover_sources("python", []), "python")`; `derive_units(facts, "python")`.

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

**Sufficiency**: pins the python unit rule (dirs with `__init__.py`), `__all__`-over-fallback facade, own-directory file ownership, and non-cell structural survival.

---

#### `test_derive_units_python_facade_fallback_bindings`

**Setup**: `app/__init__.py` with no `__all__`: `from .core import Engine`, `VERSION = 2`, `def boot(): ...`, `_priv = 1`.

**Input**: `derive_units(collect_facts([Path("app/__init__.py")], "python"), "python")`.

**Trace**: facade = non-underscore bound names → `["Engine", "VERSION", "boot"]` sorted.

**Assertions**: `app.facade == ["Engine", "VERSION", "boot"]` and `is_cell is True`.

**Sufficiency**: pins the fallback branch (bound names from imported names + assignments + definitions) — the `__all__`-less majority of real packages.

---

#### `test_resolve_links_python_absolute_and_relative_and_plain`

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

**Input**: `units`, `facts` over `src/...`; `resolve_links(units, facts, "python", root=tmp_path)`.

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

**Sufficiency**: pins the src-layout candidate-root priority, file-module→unit mapping, plain-import member-access expansion, and self-link suppression in one scenario.

---

#### `test_resolve_links_golang_module_mode`

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

**Sufficiency**: pins module-mode origin (go.mod prefix stripping), implicit-binding expansion, and external dropping; a go.mod-less variant asserts the all-external branch.

---

#### `test_resolve_links_javascript_relative_default_and_directory`

**Setup**: `tmp_path` —
```
db/index.js                → export function query() {}; export default function conn() {}
svc/index.js               → export { run } from "./a.js";          # facade(svc) = ["run"] → a cell
svc/a.js                   → import c, { query } from "../db/index.js";
                             export function run() { c(); query(); }
```
Unit membership is per directory: `a.js` and `index.js` both belong to unit `svc` (the directory contains `index.js`); the facade comes from the `index.js` facts — `["run"]` makes `svc` a cell (review fix R5 — a non-cell source would drop the link at step 2.7).

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

**Sufficiency**: pins the approved default-pseudo-name mapping end to end and Node-style relative file resolution.

---

#### `test_render_graph_nesting_compression_and_dependencies`

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

**Sufficiency**: pins the structural-compression rule, dependency aggregation, exact node field set, and root ordering — the output contract of the whole feature.

---

#### `test_render_graph_filter_parity_cells_depends_on_depth`

**Setup**: a three-level unit tree `root → root/mid → root/mid/leaf` with links `leaf → ext` (`ext` a root-level cell).

**Input** (four subcases, one test each or parametrized):
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

**Sufficiency**: locks the schema-parity filter semantics (matched cells + ancestor chain; dependency-keep with ancestor skeleton; depth prune at root 0) — the contract explicitly promises "the same behavior as the schema output".

---

#### `test_codegraph_end_to_end_golden_output`

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

**Sufficiency**: the acceptance-level golden — serialization form (indent 4, sorted keys), facade correctness, determinism/idempotency in one shot.

---

#### `test_cli_codegraph_success_and_registration`

**Setup**: same project as above; `empty_package_environment`.

**Input**: `CliRunner().invoke(app, ["codegraph"])`; also `["codegraph", "--help"]`.

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

**Sufficiency**: proves registration wiring (facade + cli.py + click surface) and the stdout-only success contract.

---

### Negative Tests

#### `test_codegraph_uninitialized_project`

**Setup**: empty `tmp_path` (no `.goga/config.yml`), cwd pinned.

**Input**: `codegraph()`.

**Trace**:
```
load_project_config() → FileNotFoundError (no .goga/config.yml)
  → propagates (no swallow — contrast with lint)
```

**Assertions**: `pytest.raises(FileNotFoundError): codegraph()`.

**Sufficiency**: the uninitialized-project failure mode of `codegraph-usage.md`; guarantees no partial/empty output masquerades as success.

---

#### `test_codegraph_unsupported_language`

**Setup**: `.goga/config.yml` → `language: rust`.

**Input**: `codegraph()`.

**Trace**: language check fails before any walk → `ValueError` naming `rust`.

**Assertions**: `pytest.raises(ValueError, match="rust"): codegraph()`.

**Sufficiency**: the second documented failure mode; ensures no silent empty graph for a misconfigured project.

---

#### `test_collect_facts_unparseable_file_fails_closed`

**Setup**: `broken.py` = `def f(:`  (syntax error).

**Input**: `collect_facts([Path("broken.py")], "python")`.

**Trace**: parse tree contains an `ERROR` node → `ValueError("unparseable source file: broken.py")`.

**Assertions**: `pytest.raises(ValueError, match="broken.py")`.

**Sufficiency**: the fail-closed contract — a parse defect must abort naming the file, never skip-and-continue.

---

#### `test_cli_codegraph_failure_stderr_only`

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

**Sufficiency**: the CLI failure contract — stdout carries the JSON document only; exit 0 only on complete generation.

---

### Edge Case Tests

#### `test_discover_sources_ignore_and_tests_and_order`

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

**Sufficiency**: pins exact-path exclusion (dir + file, trailing-slash-insensitive), idiomatic test skipping, and deterministic ordering — the exclusion-mechanics parity with `goga lint`.

---

#### `test_resolve_links_python_external_names_silent`

**Setup**: python cell `app` (`app/__init__.py` → `from .impl import S`; `app/impl.py` → `class S: ...`) whose `impl.py` also contains `import os.path` and `from collections import OrderedDict`.

**Input**: `resolve_links(units, facts, "python", root=tmp_path)`.

**Trace**:
```
os.path / collections resolve to no unit under <root> or <root>/src → external → dropped
from .impl import S → resolves to app itself → self → dropped
no exception raised
```

**Assertions**:
```
links == [] and no exception
```

**Sufficiency**: the "no link and no error" contract for external origins — stdlib names never fail the run.

---

#### `test_resolve_links_swift_ambiguous_name_no_link`

**Setup**: three swift units — `ui` (`main.swift` → `public struct App {}` plus a usage of `Client`), `core1` (`public struct Client {}`), `core2` (`public struct Client {}`).

**Input**: `resolve_links(units, facts, "swift", root=tmp_path)`.

**Trace**:
```
ui is a cell (facade ["App"]); its usage ref names App (resolves to ui itself
  → self → dropped) and Client → facade_index["Client"] has 2 units
  → uniqueness fails → no link
no exception raised
```

**Assertions**:
```
links == [] and no exception
```

**Sufficiency**: the swift uniqueness rule in isolation — `ui` is a cell and `Client` exists in facades, so the ONLY drop reason is ambiguity (review fix R7; one language per call — the python half lives in its own test).

---

#### `test_resolve_links_non_cell_source_no_link`

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

**Assertions**:
```
links == [] and no exception
```

**Sufficiency**: pins the CODEMANIFEST requirement "a link is produced only when the importing unit is a cell — imports of a unit with an empty facade produce no link and no error" — the only test that distinguishes the non-cell drop from the external drop (review fix R7; guards the resolver's most silent rule).

---

#### `test_render_graph_empty_project_renders_empty_list`

**Setup**: `tmp_path` with only `.goga/config.yml` (`language: python`) and one non-unit loose file.

**Input**: `codegraph()`.

**Trace**: discover → [loose file]; derive → no units; render → empty forest → `"[]"`.

**Assertions**: `codegraph() == "[]"`.

**Sufficiency**: the documented empty-output contract (exit 0 with `[]`, honest signal).

---

#### `test_codegraph_read_only`

**Setup**: snapshot the project tree (relative paths + file hashes) before the run.

**Input**: `codegraph()`.

**Trace**: full pipeline; assertion re-walks and re-hashes.

**Assertions**: tree snapshot after == snapshot before.

**Sufficiency**: the read-only guarantee (no file created or modified) — a bootstrap-stage consumer prerequisite.

---

#### `test_commands_facade_reexports_codegraph`

**Setup**: import `goga.commands` and `goga.commands.codegraph`.

**Input**: `commands.codegraph`, `commands.__all__`.

**Trace**: facade import binds the same click command object as the source module.

**Assertions**:
```
commands.codegraph is codegraph_source
"codegraph" in commands.__all__
isinstance(commands.codegraph, click.Command)
```

**Sufficiency**: extends `tests/commands/test_commands_facade.py` — proves the `->codegraph: {}` embedding corresponds to a real re-export.

## Additional Instructions for the Implementation Agent

- **No new dependencies**: `tree-sitter` and all five grammars are already pinned in `pyproject.toml` (`tree-sitter>=0.25.2`, `tree-sitter-python>=0.25.0`, `tree-sitter-go>=0.25.0`, `tree-sitter-javascript>=0.25.0`, `tree-sitter-kotlin>=1.1.0`, `tree-sitter-swift>=0.7.2`); `click` and the config loader are existing.
- **Facade exports**: `goga/codegraph/facts/__init__.py` re-exports all six records (the import block in `records.md` is the reference); `goga/codegraph/analysis/__init__.py` re-exports the three stages; `goga/codegraph/__init__.py` re-exports `codegraph` (plus `discover_sources`, `render_graph` per the non-underscore facade rule); `goga/commands/codegraph/__init__.py` re-exports the command.
- **Parser lifecycle**: lazy per-language singleton (dict keyed by language) inside `collect.py` — one grammar loaded per process; follow the module-level `Language(...)`/`Parser(...)` idiom of `goga/contract/<lang>` modules.
- **Language names**: the five accepted config strings are exactly `python`, `golang`, `javascript`, `kotlin`, `swift` — never `go`/`js`.
- **Never mutate** the `cells`/`depends_on`/`ignore` parameters (default `[]` is shared per signature; iterate only).
- **Known v1 limitations to keep documented, not fix**: aliased plain imports (`import a.b as c`, `import x "path"`) do not expand (the alias is not carried by `ImportRef`); JavaScript bare/workspace specifiers and CommonJS are external/out of scope; GOPATH-mode Go is external; augmented `__all__ +=` is not read.
- **Wiring order**: implement leaves first (facts → analysis → orchestrator → wrapper → facades → `cli.py` registration); after each cell run `goga lint` and the facade import check (`python -c "from goga.codegraph import codegraph"` etc.).
- **Verification gates** (from the arch plan checklist): determinism (byte-identical double run), filter parity against `goga schema` behavior, read-only run, `goga --help` lists `codegraph`, `goga lint` + `goga schema` unchanged.
- **Documentation deliverables** (implementation stage, out of this design's scope): `docs/features/codegraph/index.md`, `docs/features/codegraph/cli.md`, the `goga codegraph` row in `docs/cli/index.md`, the Codegraph row in `docs/features/index.md`.
