# `codegraph` Command — Prospective Cell Graph for Existing Code

## Problem

Bringing an existing codebase under goga's contract-oriented workflow today means inventing the cell decomposition by hand. A developer with working code (python, golang, javascript, kotlin, or swift) must decide — unaided — which public types form each cell's facade and how cells link through imports, and then author every CODEMANIFEST manually.

The existing product cannot help with this:

- `goga schema` reads CODEMANIFEST files that do not exist yet.
- `goga init` onboards new projects (survey and templates); it does not analyze existing code.
- The per-language contract extractors operate on a single already-known cell path; they cannot produce a project-wide view.

This makes adoption of existing code slow and error-prone, and it blocks automated bootstrap: without a machine-readable map of the prospective cells (facades and import-based cell links), no later stage can generate CODEMANIFEST files automatically. `codegraph` is the first step of that bootstrap pipeline — in this version it shows the schema; its output is designed to be consumed by the next (human or automated) stage.

## Users

**Primary — developer adopting goga on an existing codebase.**
Runs the adoption/bootstrap flow on a project that already has working code but no cells. Knows goga's cell model (facades, imports, CODEMANIFEST). Wants the prospective structure as the starting point for bootstrap instead of manual decomposition.

Expectations:

- the output is consistent with goga's cell rules (only CODEMANIFEST-representable types);
- cell links reflect real imports between cells, not just co-listed types;
- the analysis is fast, read-only, and repeatable;
- the output is machine-readable and usable as the input of the next bootstrap stage.

**Secondary — AI agent executing later bootstrap stages.**
Consumes the `codegraph` output programmatically to draft CODEMANIFEST files and cell scaffolding. Needs a complete, unambiguous, deterministic map of prospective cells, their facade types, and their import-based links.

## Goals

1. **Make the prospective cell structure visible before any CODEMANIFEST exists.** A developer can see how the existing codebase maps to prospective goga cells — which public types form each cell's facade and how cells are linked through actual imports — without authoring anything by hand.
2. **Provide a bootstrap-ready, machine-readable draft.** The prospective structure is produced as a stable, structured output that later bootstrap stages (human or automated) can consume directly when authoring cells and CODEMANIFEST files.
3. **Keep the draft rule-consistent and language-uniform.** The proposed structure obeys goga's structural cell-building rules and is available uniformly for all supported languages (python, golang, javascript, kotlin, swift) — the adoption experience and the quality of the draft do not depend on the language.

## User Experience

### Entry point

The user runs `goga codegraph` from the root of a goga-initialized project (`.goga/config.yml` present) whose code exists but whose cells do not (or only partially). The command is non-interactive: it asks nothing, writes nothing, and is safe to run in automated pipelines.

### Primary flow

1. The user runs `goga codegraph`.
2. The command reads the project's configured language.
3. It scans the project for source files of that language, collecting facades (public types) and name usages/imports across the whole project.
4. It resolves each used or imported name to its exact defining file under the project root (by the language's own resolution rules) and derives cell-to-cell links.
5. It prints a hierarchical JSON tree to stdout — structurally similar to `goga schema` — where each node is a prospective cell carrying its facade types and its links to other cells.
6. The user reviews the tree, or pipes it to the next bootstrap stage that authors the CODEMANIFEST files.

The view is derived from the code only: existing CODEMANIFEST files are neither required nor read, and do not affect the result.

### Alternative flows

- **Narrowing the view.** The user can restrict the output to specific cell paths and limit nesting depth, consistent with the `goga schema` filtering behavior.
- **Repeated runs.** The command is stateless and idempotent: identical code and config always produce identical output.

### Failure behavior

- **Uninitialized project** (no `.goga/config.yml`): non-zero exit with a message pointing the user to project initialization first.
- **Configured language outside the supported set**: non-zero exit with a clear message.
- **A source file that cannot be parsed**: non-zero exit with an error naming the file; nothing is printed to stdout.
- **No analyzable source files**: an empty tree (`[]`), exit code 0.
- **Imports of standard-library or third-party packages**: never become cell links and are never errors.

### Consequences

The command is read-only: it never modifies the project. It is purely descriptive: existing code that violates cell-building rules (for example, import cycles between prospective cells) is shown as it is — links in both directions, no validation verdicts, no warnings — and the command still exits 0. Rule violations are resolved during later CODEMANIFEST authoring, not by `codegraph`.

## Requirements

### Command and preconditions

- **R1.1** The product must provide a `goga codegraph` CLI command that prints the prospective cell structure of the project's existing code to stdout as a JSON document.
- **R1.2** The command must run only in an initialized goga project; otherwise it must exit non-zero with an actionable message directing the user to initialize the project first.
- **R1.3** The command must analyze exactly the single language configured in `.goga/config.yml`.
- **R1.4** The command must support each of the five supported languages — python, golang, javascript, kotlin, swift — in that configured role. A configured language outside this set must produce a non-zero exit with a clear message.

### Analysis scope

- **R2.1** The command must discover all source files of the configured language in the project.
- **R2.2** The scan must reuse the project's existing exclusion mechanism — the `lint.ignore` key of `.goga/config.yml` (exact relative paths, same mechanics as lint) — and must not introduce command-specific exclusion settings or built-in exclusion lists of its own.
- **R2.3** The analysis must be read-only: no files are created or modified.
- **R2.4** Idiomatic test files (`test_*.py`, `*_test.go`, `*.test.js`, `*Test.kt`, `*Tests.swift`) must be excluded from the analysis entirely — they contribute neither facades nor links.
- **R2.5** Only the primary source extensions are analyzed: `.py`, `.go`, `.js`, `.kt`, `.swift`.

### Prospective cells

- **R3.1** The command must derive prospective cells structurally from the project's package/directory structure of the configured language — the unit is the language's own package/module: Python — a directory containing `__init__.py`; Go — a directory containing `.go` files; JavaScript — a directory containing `index.js`; Kotlin — a directory containing `.kt` files; Swift — a directory containing `.swift` files. Nested units become children — mirroring the directory-path addressing of CODEMANIFEST cells.
- **R3.2** Each prospective cell must expose only the types that would be represented in a CODEMANIFEST — the unit's public API per the product's per-language contract rules: Python — identifiers in `__all__` of `__init__.py` (when `__all__` is absent, the non-underscore top-level names bound in `__init__.py`); Go — exported identifiers; JavaScript — the exports of `index.js` (named `export default` included, anonymous excluded); Kotlin — `public` declarations; Swift — only `public`/`open` declarations.
- **R3.3** A directory unit with no facade types must not become a prospective cell; it is preserved only as a structural ancestor when it contains nested prospective cells. Its imports create no cell links and are not errors.

### Cell links

- **R4.1** Links between prospective cells must be derived with exact origin: a link from cell A to cell B (carrying type T) exists whenever a name used in A's code resolves, by the language's own import/reference semantics, to a facade type T whose defining file lies under the project root — the target cell B being the cell at that file's path relative to the project root. This holds regardless of whether T appears in A's own facade list.
- **R4.2** Import resolution must be performed against the complete set of facades collected across the whole project (all facades and all imports are collected first, then resolved) — never cell-locally.
- **R4.3** Each link must carry the specific facade types of the target cell that the importing cell actually imports.
- **R4.4** Names whose origin resolves outside the project tree (standard library, third-party packages, environment-provided paths) must not create cell links and must not be reported as errors. No environment variables (`PYTHONPATH`, `GOPATH`, …) are read.
- **R4.5** The graph must be purely descriptive: cyclic or otherwise rule-violating structures in the existing code are shown as they are (links in both directions) without validation verdicts or warnings, and a successful analysis always exits 0.
- **R4.6** Per-language origin rules: Python — absolute imports resolve against the candidate roots `<project root>` and `<project root>/src` (priority order; covers flat and src layouts), relative imports resolve against the importing file; Go — module mode via the module path from `go.mod` (without `go.mod`, imports are external); JavaScript — only relative specifiers, Node-style (`x.js` or `x/index.js`), bare specifiers (including workspace packages) are external; Kotlin — via the `package` declarations of files under the project root; Swift — type usages resolved by unique name within the project (module imports carry no type names). Wildcard imports resolve to the actually used names.

### Output

- **R5.1** The output must be a hierarchical JSON tree on stdout, structurally similar to `goga schema`: each node carries the cell path, its facade types, its links to other cells (with the imported types per link), and its nested children.
- **R5.2** The output must be deterministic: identical code and configuration produce byte-identical output (stable ordering).
- **R5.3** A project with no analyzable source files must produce an empty tree (`[]`) and exit 0.
- **R5.4** The user must be able to narrow the output with the same set of filters as the schema command — filter to specific cell paths, limit nesting depth, and keep only cells depending on the specified paths (`--depends-on`) — identical filtering behavior.

### Failures and diagnostics

- **R6.1** A source file is unparseable iff its tree-sitter parse contains any `ERROR` or `MISSING` node; such a file must fail the command: non-zero exit, the error names the file, and no partial JSON is printed to stdout.
- **R6.2** Diagnostics go to stderr; stdout carries only the JSON document (or nothing on failure).

## Constraints

1. **Structural cell rules.** The prospective structure must obey goga's structural cell-building rules: cells are directory-based units, a cell's surface is its facade of public types, nesting mirrors the directory tree. Responsibility-zone sizing ("one responsibility zone — one cell", not too fine, not too coarse) is an authoring concern of the downstream CODEMANIFEST stages, not of `codegraph`.
2. **Facade consistency.** The set of types shown per cell must be exactly the types the product's per-language contract semantics would represent in a CODEMANIFEST — no more, no fewer — so that CODEMANIFESTs authored from the draft match the code.
3. **Link semantics.** Cell links must be grounded in exact origin resolution: each linked type's defining file is determined under the project root by the language's own semantics (collect-then-resolve over the project-wide facade set); links are never inferred from name co-location alone.
4. **Single configured language.** A project declares exactly one language today; the command analyzes that language only.
5. **Supported language set.** Exactly python, golang, javascript, kotlin, swift — the same set as the product's contract domain.
6. **Read-only, static analysis.** The command must not modify the project and must not execute project code; the analysis is purely static and reads no environment variables (`PYTHONPATH`, `GOPATH`, …).
7. **Non-interactive.** No prompts; usable by agents in automated pipelines; stdout carries only the JSON document.
8. **Output compatibility.** The output must remain structurally comparable to `goga schema` (a hierarchical cell tree with types and dependencies) so both views can be consumed uniformly downstream.
9. **CLI conventions.** The command must follow existing goga CLI conventions: thin CLI wrapper over a domain cell, exit code 0 on success and non-zero on failure, diagnostics on stderr, no partial stdout on hard failure.
10. **Pre-cell operability.** The command must work on a project with no CODEMANIFEST files at all; it must not depend on existing cells.

## Scope

### In Scope

- The `goga codegraph` CLI command, registered in the product's command set.
- Reading the configured language from the project configuration and analyzing existing source code of that language.
- Project-wide source discovery reusing the `lint.ignore` exclusions, for each of the five supported languages; idiomatic test files excluded.
- Structural derivation of prospective cells (per-language package units) with facade types only.
- Exact-origin name resolution (collect-then-resolve) and cell-to-cell links carrying the resolved facade types.
- The schema-like hierarchical JSON output with the schema command's full filter set (cell paths, depth limit, depends-on).
- The defined failure behavior: uninitialized project, unsupported configured language, unparseable files, empty project.
- The user-facing usage documentation for the command, following the product's command documentation conventions.

### Out of Scope

- Generating, writing, or modifying CODEMANIFEST files or cell scaffolding — the later bootstrap stages are separate future work.
- Analyzing more than one language in a run, language auto-detection, or changing the single-language configuration model.
- Validating or linting the derived structure, marking rule violations, or enforcing the no-cross-imports rule on the output.
- Merging with or reading existing CODEMANIFEST data (`goga schema` remains the tool for the manifest view; `codegraph` is the code-derived view).
- Refactoring code, creating directories, moving or renaming types.
- Support for languages beyond the five supported ones.
- Resolution via environment variables (`PYTHONPATH`/`GOPATH`), GOPATH-mode Go projects, and JavaScript bare/workspace-specifier resolution (workspace packages are external in v1).
- Interactive flows of any kind.
- Authoring cell descriptions or practices — manifest-time content that does not exist yet.

## Success Criteria

1. **Prospective structure without manifests.** Running `goga codegraph` in an initialized project that contains code but no CODEMANIFEST files prints a hierarchical JSON tree of prospective cells — each node with its cell path, facade types, and links.
2. **Facade-only types.** Every type listed for a cell is public under the language's contract visibility rules; non-public definitions never appear in the output.
3. **Exact-origin links.** Given code where cell A imports a type provided by cell B, the output shows a link A→B carrying that type — including when the imported type does not appear in A's own facade list, and, for Swift, when cell A's code uses a facade type of cell B by name. Imports of standard-library and third-party packages produce no links and no errors.
4. **Bootstrap-ready output.** The output is valid JSON alone on stdout, byte-identical across repeated runs over unchanged code and configuration, and structurally comparable to `goga schema` output so an agent can consume both uniformly.
5. **Language uniformity.** The same command behavior and output semantics hold for each of the five supported languages: for each language, a small project yields a correct prospective-cell graph.
6. **Failure behavior.** An uninitialized project and an unparseable source file each produce a non-zero exit with an actionable error (the parse error names the file) and nothing on stdout; a project with no analyzable sources prints `[]` and exits 0.
7. **Descriptive only.** Code with import cycles between two prospective cells yields both directions of the link in the output, exit code 0, and no warnings.
8. **Read-only.** After running the command, the project tree is unchanged — no files created or modified.
