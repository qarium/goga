# Codegraph: schema view of existing project code

## Current State

The project has every ingredient the view needs, but no entry point that
combines them:

- `goga/contract` owns the type truth: the `contract(lang, cell_path)`
  dispatcher routes to five per-language extractors (python, golang,
  javascript, kotlin, swift) and returns per-file contracts carrying type
  names. It is what `goga contract` compares CODEMANIFESTs against.
- `goga/config/project` loads `.goga/config.yml` (`load_project_config()`),
  exposing `lint.ignore` and `language`; an absent config surfaces as a
  FileNotFoundError.
- `goga/ast` fixes the walk semantics used across the product: directories
  are skipped only on an exact normalized relative path match, glob
  characters are literal, `.project` is always skipped, symlinked
  directories are not descended.
- `goga/commands/schema` + `goga/schema` establish the command pattern — a
  thin CLI wrapper over a domain component — and the output node shape
  (`cell`, `types`, `children`) with `beautiful_json` serialization.
- `goga/commands/__init__.py` is the command registry where every new
  command is registered.

What is missing: a way to see an existing, already-written codebase as goga
sees it. `goga init` targets new projects, `goga schema` renders only
already-existing CODEMANIFEST files, `goga contract` requires cells to
exist. Adopting goga on an existing project therefore means hand-authoring
the whole cell structure with no code-derived starting point.

## Description

Deliver `goga codegraph` — a one-shot, read-only command that projects an
existing project's code onto the goga cell model and prints a deterministic
JSON tree on stdout. It is the foundation of the future init pipeline (init
is a pipeline built on codegraph, not a single command); this task delivers
that foundation only.

Behavior, fully fixed by the accepted ADR (`.goga/history/2026/codegraph/
adr.md`):

- **Entry.** Run in the root of any existing project; no goga structures
  (`.goga/`, CODEMANIFEST files) are required. Read-only: nothing on disk
  is created or modified.
- **Language selection.** Priority: `--lang` > `language` from
  `.goga/config.yml` > auto-detect by marker files. Markers are the files
  the extractor of the language actually consumes: python `.py`; golang
  `.go` excluding `_test.go`; javascript `index.js`; kotlin `.kt`; swift
  `.swift`. An unsupported language — from `--lang` or from the config —
  produces one clean stderr error, exit 1, no stdout, no traceback.
- **Scan scope.** The walk starts at the invocation directory and honours
  only `lint.ignore` from `.goga/config.yml` when the config exists; no
  other ignore source. Walk semantics follow `goga/ast` verbatim: exact
  normalized-path directory matches only, globs literal, files never
  matched, `.project` always skipped, no hidden-directory special-casing,
  no descent into symlinked directories.
- **Type selection.** Reuse the `goga/contract` extractors through the
  dispatcher — one call per scanned directory per analyzed language,
  keeping only the names (signatures discarded). This makes the view
  CODEMANIFEST-true by construction: codegraph shows exactly what
  `goga contract` compares. Names are deduplicated per directory and
  sorted lexicographically in byte order.
- **Node mapping.** Every directory containing at least one representable
  type becomes exactly one node; `cell` is the normalized relative POSIX
  path from the invocation directory (root is `.`); nesting mirrors
  directory containment via `children`; directories without representable
  types produce no node and no placeholder — descendants attach to their
  nearest ancestor node. Nodes carry `cell`, `types`, `children` only.
- **Output.** stdout carries exactly one JSON document and nothing else,
  serialized per the `beautiful_json` practice; `children` sorted by `cell`
  so output never depends on filesystem enumeration order. An empty scan
  (no supported-language code, or code with zero representable types) is a
  success: `[]`, exit 0.
- **Failure behavior.** A present-but-invalid `.goga/config.yml` is a clean
  error (exit 1, one stderr message, no stdout, no traceback) — the schema
  error convention, deliberately diverging from `goga lint`'s swallow-all.
  An absent config, a missing `lint` section, or an empty `lint.ignore`
  means no exclusions (success). An exception while reading or extracting
  a file (e.g. permission, broken encoding) is a clean error naming the
  file and the language, exit 1; a syntactically broken but readable file
  is not an error — whatever is extractable is extracted.
- **Help.** The command help explains the output structure for AI agents
  (product convention).

## Scope

**In scope:**

- The new `goga codegraph` CLI command — thin wrapper over a new domain
  component, registered in the command registry.
- Language selection: `--lang` restriction, config `language`
  restriction, auto-detection by marker files; clean failure on
  unsupported values.
- Config consumption: `lint.ignore` exclusions when present; absence
  treated as no exclusions; invalid config as a clean error.
- Tree walk from the invocation directory with the `goga/ast` walk
  semantics.
- Per-directory type-name extraction via the `goga/contract` dispatcher
  (names only, deduplicated, byte-order sorted).
- Directory-to-node mapping with schema-shaped nodes (`cell`, `types`,
  `children`), deterministic JSON output, empty-scan `[]` success.
- Failure and error behavior per the ADR (clean stderr errors, exit 1, no
  traceback; read-only guarantees).
- Agent-oriented command help.

**Out of scope:**

- Any creation or modification of cells, CODEMANIFEST files, or `.usages`
  — that belongs to the future init pipeline.
- The init pipeline itself and any wiring of codegraph into it.
- TypeScript support (rejected for this change; extending
  `goga/contract/javascript` is future work).
- Contract-detail output (signatures, properties, methods) — type names
  only.
- Derivation of description / usages / dependencies fields from code.
- Hooks / tool-package checkpoints and a tools area in the output.
- Any ignore source other than `lint.ignore` (`.gitignore`, vendor
  heuristics); no hardcoded exclusions.
- Languages beyond the five supported by the existing contract tooling.
- Output formats other than the JSON document on stdout.
- Changes to existing commands (schema, contract, init) beyond adding the
  new command.
- The cell layout and CODEMANIFEST wiring of the codegraph component
  itself — an open question deferred to the design stage.

## Acceptance Criteria

- **SC1.** Running `goga codegraph` in the root of an existing project
  that contains no goga structures (no `.goga/`, no CODEMANIFEST files)
  produces the code-derived schema view on stdout and exits 0.
- **SC2.** For a sample project in each of the five supported languages,
  the command produces a non-empty tree containing that project's
  public/exported types.
- **SC3.** The output contains exactly the types a CODEMANIFEST would
  represent — private, internal, and test-only constructs do not appear
  (e.g. `_`-prefixed Python names, unexported Go declarations, `_test.go`
  declarations, unexported JavaScript module members).
- **SC4.** The tree obeys cell-building rules: one node per directory
  containing representable types, nesting mirrors directory containment,
  no placeholder nodes for type-less directories.
- **SC5.** For a directory already governed by a CODEMANIFEST consistent
  with its code (a cell passing the `goga contract` comparison), the types
  codegraph reports for that directory match the names declared in its
  CODEMANIFEST.
- **SC6.** Repeated runs over the same code tree with the same config and
  options produce byte-identical stdout.
- **SC7.** stdout carries a single machine-parseable JSON document and
  nothing else; every genuine failure (unknown `--lang` value, invalid
  config, unreadable source) yields exactly one clean stderr message,
  exit code 1, and no partial stdout; an empty scan yields `[]` and exit
  0.
- **SC8.** Running codegraph leaves the project byte-identical — no file
  is created or modified.
- **SC9.** On a project where the set of type-bearing directories
  coincides with the set of cells — every directory containing
  representable types is governed by a CODEMANIFEST passing the
  `goga contract` comparison, and no CODEMANIFEST governs a type-less
  directory — the `goga codegraph` stdout equals the `goga schema`
  stdout reduced to the code-derivable fields: with `description`,
  `usages`, `dependencies`, and `tools` removed from every schema node,
  the two JSON trees are identical — same nodes, same `cell` paths, same
  nesting, equal `types` lists.
- **SC10.** A mixed-language fixture (two supported languages in one
  tree, at least one directory holding representable types of both)
  yields a single combined tree in one run, that directory producing
  exactly one node aggregating both languages' types; with `language`
  set in `.goga/config.yml`, the output contains exactly that
  language's types and none of the other code present in the tree.

## Stack

- **Frameworks:** click (CLI surface; thin wrapper, clean errors via the
  click error convention).
- **Libraries:** tree-sitter language grammars — consumed only indirectly
  through the `goga/contract` extractors; PyYAML — consumed through
  `goga/config/project`.
- **Infrastructure:** none. Standard library only elsewhere: `json` for
  output serialization (`beautiful_json` practice), `os`/`pathlib` for the
  tree walk, `dataclasses` (`frozen=True, kw_only=True`) for data models.
- **Testing:** pytest, ruff, pytest-cov per project conventions; CLI
  tested via the click test runner against the command handler.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| click | `.goga/usages/cooks/click.md` | existing |
| JSON serialization | `.goga/usages/cooks/beautiful_json.md` | existing |
| tree-sitter (python, go, js, kotlin, swift) | `.goga/usages/cooks/tree-sitter-*.md` | existing — indirect, via `goga/contract` extractors |
| PyYAML | inline `yaml` practice in `goga/config/project/CODEMANIFEST` | existing — indirect, via `goga/config/project` |

No usage files are created or updated by this task — every dependency is
already covered by current practices.

## Risks and Constraints

- **Determinism boundary (PRD C7).** Identical inputs (code tree, config,
  options) must yield byte-identical output; `types` sorted in byte order,
  `children` sorted by `cell` — never filesystem enumeration order.
- **Cell-model authority (PRD C1).** codegraph must not invent its own
  type model; the view is CODEMANIFEST-true only because it reuses the
  contract extractors. A codegraph-owned analyzer duplicating facade rules
  was explicitly rejected in the ADR (rule drift, double maintenance).
- **Ignore-source exclusivity (PRD C3).** `lint.ignore` is the only
  honoured ignore source; the cost of walking e.g. a `.venv` is the user's
  `lint.ignore` responsibility — no hidden-directory special-casing may
  sneak in.
- **Config-error divergence.** A present-but-invalid config must fail
  cleanly (exit 1) rather than run unfiltered — this deliberately diverges
  from `goga lint` and must not "regress" to lint's behavior.
- **Read-only boundary (PRD C5).** No file is created or modified, ever;
  all creation belongs to the future init pipeline.
- **Failure semantics split.** Read/extraction exceptions are errors
  (clean, naming file and language); syntactically broken but readable
  sources are not — graceful degradation is the expected path.
- **Deferred design.** The cell layout and CODEMANIFEST wiring of the
  codegraph component itself is an open question handed to the design
  stage; this task must not pre-commit to it.

## Scope Estimate

Single task, no decomposition. The work is one cohesive read-only pipeline
(language selection → walk → extraction → tree assembly → output) where no
subset delivers independent value; roughly 6–9 contracts in the new domain
component plus one thin command. Topic: `2026/codegraph`.

## Existing Architecture

- **`goga/contract`** — consumed, not modified: the dispatcher is the
  single source of type truth; one call per scanned directory per analyzed
  language; unsupported language already raises the error codegraph wraps
  into a clean CLI failure.
- **`goga/config/project`** — consumed, not modified: config loading
  (`lint.ignore`, `language`); its absent-config signal maps to codegraph's
  no-exclusions success; its invalid-config signals map to codegraph's
  clean error.
- **`goga/ast`** — semantics reference, not a code dependency by
  definition: the walk reproduces its traversal rules verbatim (exact
  directory-path ignores, literal globs, `.project` always skipped, no
  symlink descent).
- **`goga/commands/schema` + `goga/schema`** — pattern precedent: thin CLI
  wrapper over a domain component; codegraph's output node shape mirrors
  the schema node's code-derivable fields (`cell`, `types`, `children`)
  and its serialization practice.
- **`goga/commands/__init__.py`** — modified minimally: registration of
  the new command, following the existing registration convention.
- **`goga` (root cell, `cli.py`)** — modified minimally: the root group
  registers the new command (facade import + `app.add_command`), and the
  `app()` command list in the root CODEMANIFEST gains the `codegraph`
  entry — the existing `cli-commands` registration practice.
- **New components** — a domain component for the codegraph logic and a
  thin command wrapper module; their cell layout and CODEMANIFEST wiring
  are decided at the design stage (ADR open question).

## Notes

- All product decisions are accepted in the ADR
  (`.goga/history/2026/codegraph/adr.md`); the PRD
  (`.goga/history/2026/codegraph/prd.md`) remains the requirements
  authority. This task adds no new decisions beyond them.
- No hooks, checkpoints, or tool-package surfaces in codegraph — the
  command is a plain one-shot analysis by design.
- Per stage constraints this document intentionally contains no code
  examples and no architecture design; both belong to later stages.
