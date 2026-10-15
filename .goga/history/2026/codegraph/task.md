# codegraph — Prospective Cell Graph Command

## Current State

The project is the goga tool itself: Python 3.10+, click-based CLI, cells under `goga/`. Facts established during task grooming:

- CLI commands are thin wrappers in `goga/commands/*` over domain cells (the reference pattern: `goga/commands/schema` wraps `goga/schema`, which builds the JSON cell tree from CODEMANIFEST via `goga/ast`). Commands are re-exported through the facade `goga/commands/__init__.py` and registered in the root click group in `goga/cli.py` (`app.add_command`); the registration reference — facade import line, add_command wiring, full command table — is the `cli-commands` practice of `goga/commands`.
- The `schema` command emits a hierarchical JSON tree of cells on stdout — node fields `cell`, `description`, `types`, `usages`, `dependencies` (each with `types` and `usages`), `children`, plus an optional `tools` overlay; serialization uses four-space indent, sorted keys, non-ASCII preserved; an empty tree serializes as an empty JSON list. CLI filters: specific cell paths, maximum nesting depth, and keep-only-cells-depending-on-given-paths.
- Per-language contract extractors exist in `goga/contract/{python,golang,javascript,kotlin,swift}`; each operates on a single already-known cell path — none can produce a project-wide view.
- tree-sitter plus all five grammars (python, go, javascript, kotlin, swift) are already shipped runtime dependencies of the project.
- The exclusion mechanism `lint.ignore` exists in the project configuration model (`LintConfig.ignore` in `goga/config/project`, loaded by `load_project_config`) and is reusable without contract changes.
- No `codegraph` command exists: there is no project-wide source scan, no code-derived facade output, and no import-based cell-link resolution anywhere in the project.

## Description

Implement the `goga codegraph` CLI command — a non-interactive, read-only command that derives the prospective cell structure of the project's existing code and prints it to stdout as JSON, per the accepted ADR (`.goga/history/2026/codegraph/adr.md`) and PRD (`.goga/history/2026/codegraph/prd.md`).

The command runs only in an initialized goga project and analyzes exactly the single language configured in `.goga/config.yml` (python, golang, javascript, kotlin, or swift; anything else is a clear non-zero-exit error). For that language it:

- discovers all source files of the configured language (primary extensions `.py`, `.go`, `.js`, `.kt`, `.swift`), excluding paths listed in the existing `lint.ignore` config key (same mechanics as lint, no command-specific settings or built-in lists) and idiomatic test files (`test_*.py`, `*_test.go`, `*.test.js`, `*Test.kt`, `*Tests.swift`) entirely;
- derives prospective cells structurally from the language's own package/module units — Python directory with `__init__.py`, Go directory with `.go` files, JavaScript directory with `index.js`, Kotlin directory with `.kt` files, Swift directory with `.swift` files — with nesting mirroring the directory tree;
- exposes per cell only the facade types defined by the per-language contract rules — Python identifiers in `__all__` of `__init__.py` (fallback: non-underscore top-level names bound there), Go exported identifiers, JavaScript exports of `index.js` (named `export default` included, anonymous excluded), Kotlin `public` declarations, Swift `public`/`open` declarations only;
- resolves every used or imported name to its exact defining file under the project root by the language's own semantics (collect all facades and imports project-wide first, then resolve), deriving cell-to-cell links that carry the specific resolved facade types; per-language origin rules: Python absolute imports against candidate roots `<project root>` and `<project root>/src` in priority order, relative imports against the importing file; Go in module mode via the module path from `go.mod` (without `go.mod`, imports are external); JavaScript relative specifiers only, Node-style file or directory resolution (bare and workspace specifiers are external); Kotlin via `package` declarations of files under the project root; Swift by unique type name within the project. Wildcard imports resolve to the actually used names. Names resolving outside the project tree never produce links and never error. No environment variables are read;
- prints a hierarchical JSON tree on stdout that is a full analogue of the `goga schema` output format — identical structure, field conventions, and serialization (four-space indent, sorted keys, non-ASCII preserved; empty tree is an empty JSON list) — where each node carries exactly the code-derivable fields: `cell` (path relative to the project root), `types` (facade types), `dependencies` (map of target cell path to the imported facade `types`; no `usages` key), `children`. Manifest-only fields (`description`, `usages`, `tools`) are absent entirely;
- supports the same filter set as the schema command, with identical behavior: specific cell paths, maximum nesting depth, and keep-only-cells-depending-on-given-paths;
- fails closed on unparseable input: a file is unparseable iff its tree-sitter parse contains any `ERROR` or `MISSING` node — non-zero exit naming the file, nothing on stdout; stdout carries only the JSON document, diagnostics go to stderr;
- stays purely descriptive: cyclic or otherwise rule-violating structures are shown as they are, no validation verdicts or warnings, exit 0; a project with no analyzable sources prints an empty JSON list and exits 0;
- is documented for users following the product's command documentation conventions.

## Scope

**In scope:**
- The `goga codegraph` CLI command, registered in the product's command set following the thin-wrapper convention.
- Reading the configured language and `lint.ignore` exclusions from the project configuration.
- Project-wide source discovery per language (extensions, test-file exclusion, `lint.ignore` reuse).
- Structural derivation of prospective cells (per-language units) with facade types per the per-language contract rules.
- Exact-origin, collect-then-resolve name resolution and cell-to-cell links carrying the resolved facade types, per the per-language origin rules.
- The schema-analogue hierarchical JSON output (code-derivable fields only) with the schema command's full filter set (cell paths, depth, depends-on).
- The defined failure behavior: uninitialized project, unsupported configured language, unparseable file, empty project.
- User-facing usage documentation for the command.

**Out of scope:**
- Generating, writing, or modifying CODEMANIFEST files or cell scaffolding (later bootstrap stages).
- Analyzing more than one language per run, language auto-detection, or changing the single-language model.
- Validating or linting the derived structure, marking rule violations, enforcing the no-cross-imports rule.
- Merging with or reading existing CODEMANIFEST data (`goga schema` remains the manifest view).
- Refactoring code, creating directories, moving or renaming types.
- Languages beyond the five supported ones.
- Resolution via environment variables (`PYTHONPATH`/`GOPATH`), GOPATH-mode Go imports, JavaScript bare/workspace-specifier resolution (workspace packages are external in v1).
- JavaScript CommonJS modules (`module.exports` facades, `require()` imports) — ESM only in v1.
- Interactive flows of any kind.
- Authoring cell descriptions or practices — manifest-time content that does not exist yet.

## Acceptance Criteria

- Running the command in an initialized project that contains code but no CODEMANIFEST files prints a hierarchical JSON tree of prospective cells — each node with `cell`, `types`, `dependencies` (with imported types per link), `children` — and nothing else on stdout.
- Every listed type is public under the language's contract visibility rules; non-public definitions never appear.
- Given code where cell A imports a type provided by cell B, the output shows a link A→B carrying that type — including when the imported type does not appear in A's own facade list, and, for Swift, when A's code uses a facade type of B by name. Standard-library and third-party imports produce no links and no errors.
- The output is valid JSON alone on stdout, byte-identical across repeated runs over unchanged code and configuration, and structurally comparable to `goga schema` output so downstream consumers can process both uniformly.
- The three schema filters (cell paths, depth, depends-on) behave identically to the schema command's.
- The same command behavior and output semantics hold for each of the five languages: for each, a small project yields a correct prospective-cell graph.
- An uninitialized project, a configured language outside the supported set, and an unparseable source file each produce a non-zero exit with an actionable error (the parse error names the file) and nothing on stdout; a project with no analyzable sources prints an empty JSON list and exits 0.
- Code with import cycles between two prospective cells yields both link directions, exit 0, no warnings.
- After running the command, the project tree is unchanged — no files created or modified.
- User-facing documentation for the command exists and follows the product's command documentation conventions.

## Stack

- **Frameworks:** click (>= 8.0) — CLI command following the project's thin-wrapper convention; project conventions from `.goga/usages/conventions.md` are mandatory (Python 3.10+, relative intra-package imports, virtualenv, pyproject-based configuration).
- **Libraries:** tree-sitter (>= 0.25.2) with tree-sitter-python, tree-sitter-go, tree-sitter-javascript, tree-sitter-kotlin, tree-sitter-swift — the only parsing stack (facade extraction, import/name collection, `ERROR`/`MISSING` detection); pyyaml (>= 6.0) via the existing configuration cell; Python stdlib for file traversal, path resolution, and JSON serialization.
- **Infrastructure:** none — the command is a local, read-only static analysis with no external services.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| click | `.goga/usages/cooks/click.md` | existing |
| pyyaml | `.goga/usages/conventions.md` (project std; no dedicated cook) | existing |
| tree-sitter + tree-sitter-python | `.goga/usages/cooks/tree-sitter-python.md` | updated (Imports section added) |
| tree-sitter-go | `.goga/usages/cooks/tree-sitter-go.md` | updated (Imports section added) |
| tree-sitter-javascript | `.goga/usages/cooks/tree-sitter-js.md` | updated (Imports (ESM) section added) |
| tree-sitter-kotlin | `.goga/usages/cooks/tree-sitter-kotlin.md` | existing (imports and package nodes already covered) |
| tree-sitter-swift | `.goga/usages/cooks/tree-sitter-swift.md` | existing (import and type-name nodes already covered) |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- Read-only, static, non-interactive: the command must not modify the project, must not execute project code, and must read no environment variables — determinism requires identical output for identical code and config.
- Structural cell rules: cells are directory-based language units; a unit with no facade types is not a cell and survives only as a structural ancestor; its imports create no links and no errors.
- Facade consistency constraint: the set of types shown per cell must match exactly what the per-language cell-building rules (`goga-cell-<language>`, as pinned by the ADR) define as the facade — no more, no fewer.
- Output compatibility constraint: the node shape is the schema node minus manifest-only fields (`description`, `usages`, `tools` absent; `dependencies` without a `usages` key); serialization and the three filters mirror `goga schema` exactly.
- Known honest-empty cases: Swift applications with only `internal` declarations yield an empty tree with exit 0; Python namespace packages (no `__init__.py`) and JavaScript directories without `index.js` are not units and produce no cells.
- Known v1 limitations (accepted in the ADR): JavaScript bare/workspace specifiers and GOPATH-mode Go imports are external.
- Performance posture: the scan is linear in the number of discovered files — each file is read and parsed exactly once (collect-then-resolve operates over in-memory results, no re-parsing); no explicit performance budget is set in v1.
- All parsing must use the already-shipped tree-sitter stack — no new parser dependencies.

## Scope Estimate

Single task, no decomposition. The value is delivered only by the command as a whole (one CLI surface, one output format, all five languages required by the same behavioral contract); the per-language adapters are internal parts of one responsibility zone, so splitting them into separate topics would leave each part without independent value. Internal cell structure and boundaries are a `prototype`-stage concern.

## Existing Architecture

- `goga` (root cell, `cli.py`) — the root click group where the new command is registered (`app.add_command`); mechanical wiring change.
- `goga/commands/__init__.py` — facade re-export of the new command (mechanical wrapper change). The `cli-commands` practice (`goga/commands/.usages/cli-commands.md`) holds the registration reference — facade import line, add_command wiring, and the full command table — and gains one entry.
- `goga/config/project` — provides the project configuration model and loader (`load_project_config`, `ProjectConfig`, `LintConfig.ignore`); consumed as-is, no contract change.
- `goga/schema` — the semantic reference for the output format: a full analogue minus manifest-only fields, identical serialization and filters; parity by convention, no code import prescribed.
- Per-language facade semantics are owned by the cell-building rules codified in the `goga-cell-<language>` skills and pinned by the ADR; the consistency requirement is: for a known cell path, the facade types derived by `codegraph` must coincide with what those rules define as the facade.
- `goga/contract/{python,golang,javascript,kotlin,swift}` — related per-language contract extractors, not the semantic authority for this task. Their facade rules coincide with the cell-building rules for golang, kotlin, and swift, but for python the extractor collects all non-underscore top-level definitions across all `.py` files of the cell directory and never consults `__all__`/`__init__.py` — a known divergence in both directions (public helper-submodule definitions the cell rules exclude; an empty `__init__.py` with populated submodules, where the cell rules yield no cell at all). Whether to reuse their code or implement per codegraph needs is a prototype-stage decision, not fixed by this task.
- `goga/ast` — the CODEMANIFEST AST used by `schema`/`lint`; not applicable to `codegraph` (code-derived view, manifest-free), listed to make the non-relationship explicit.

## Notes

- Input for this task: the accepted ADR and the amended PRD in this topic directory; the PRD's R5.4 and In-Scope line were amended during grooming to record the user's decision that the filter set is fully identical to `goga schema` (cell paths, depth, depends-on).
- Node field decision (confirmed by the user): the output node carries only code-derivable fields — `description`, `usages`, and `tools` are absent entirely because they exist only in CODEMANIFEST; `dependencies` entries carry `types` only, without a `usages` key.
- Usage-file updates made during grooming (node shapes verified against the installed grammars): import-statement sections added to the python, go, and javascript tree-sitter recipes; kotlin and swift recipes were already sufficient.
- No new external dependencies; no new usage files.
