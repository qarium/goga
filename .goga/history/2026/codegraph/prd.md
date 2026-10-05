# Codegraph: Schema View of Existing Project Code

## Problem

A developer bringing an already-written project (a python, golang, javascript,
kotlin, or swift codebase) into goga cannot use the goga pipelines — refinement,
development, and the rest of the CODEMANIFEST-based workflow — because every
pipeline operates on cells, and there is no way to derive cells from existing
code.

The current entry points do not help:

- `goga init` (scaffold + onboarding) targets new projects;
- `goga schema` renders only already-existing CODEMANIFEST files;
- `goga contract` requires cells to already exist.

Adopting goga on an existing codebase therefore means hand-authoring the entire
cell structure with no code-derived starting point and no view of the code as
CODEMANIFEST types. The adoption is manual, error-prone, and practically out of
reach, so existing projects are effectively excluded from goga-based development.

Direction established by the product owner: the `codegraph` command is the
foundation of the future init pipeline (init is a pipeline built on codegraph,
not a single command). This change delivers that foundation.

## Users

### Primary user

**A developer adopting an existing project into goga.** They own or maintain an
already-written codebase in one of the supported languages and want to run the
goga pipelines on it. The interaction happens at adoption time — before any goga
pipeline can start, because pipelines operate on cells that do not yet exist for
this code. The developer knows their own code well but is not necessarily fluent
in the goga cell DSL.

They want to:

- see the existing code as goga sees it — projected onto the cell model;
- obtain a trustworthy starting point for creating cells instead of
  hand-authoring CODEMANIFEST files from scratch;
- trust that what is shown matches what CODEMANIFEST will actually represent.

They expect a deterministic, reproducible view that reflects CODEMANIFEST rules
rather than raw language facts, and that merely viewing the code changes nothing.

### Secondary actor

**The AI agent executing the future init pipeline.** The init process is a
pipeline built on codegraph; its stages are executed by AI agents (goga
convention: commands print deterministic JSON to stdout with agent-oriented
help). The agent consumes codegraph's output to reason about cell boundaries and
CODEMANIFEST types, and therefore needs clean machine-readable output.

## Goals

1. **Entry point for existing projects.** A developer of an already-written
   project can obtain the goga view of their code without any goga structures
   pre-existing in the project — making goga pipelines reachable for existing
   codebases.
2. **CODEMANIFEST-true view.** The view shows exactly the types that will be
   represented in CODEMANIFEST (public/exported facade types per the language
   rules), so decisions made on this view are valid for the future cell
   structure — no noise, no false types.
3. **Deterministic machine-consumable foundation.** The same output serves the
   human developer and the AI agent of the future init pipeline; same code →
   same output, providing the stable foundation the init process will be built
   on.

## User Experience

### Entry point

`goga codegraph` run in the root of an existing project — by the developer in a
terminal, or by the AI agent inside the future init pipeline. No goga structures
need to exist in the project.

### Primary flow

1. The developer runs `goga codegraph` in the project root.
2. The command auto-detects the implementation language(s) from present code
   files; an optional `--lang` flag overrides detection; one run analyzes every
   detected language (multi-language project → one output).
3. The command walks the project tree, honouring only `lint.ignore` from
   `.goga/config.yml` when the config exists (no config → no exclusions), plus
   the per-language file conventions (e.g. Go `_test.go` files are skipped).
4. Every directory containing public/exported — CODEMANIFEST-representable —
   types becomes a nested cell in the output tree; directories without such
   types do not appear.
5. The result is printed as a deterministic JSON tree on stdout with nodes
   shaped exactly like `goga schema` nodes (`cell`, `types` as names only,
   `children`, …) — derived from code instead of CODEMANIFEST files.
6. Exit code 0; nothing on disk is modified. Re-running over the same code
   produces identical output.

### Alternative flows

- `--lang` given → analysis is restricted to that single language.
- Project without `.goga/config.yml` → scan proceeds with no exclusions
  (adoption chicken-and-egg stays safe: no goga preconditions).
- Empty scan result — no supported-language code in the scanned tree, or code
  present but zero representable types — is a success: `[]` on stdout, exit 0
  (same behaviour as `goga schema` over an empty world).

### Failure behavior

Genuine failures — unreadable or unparseable source, invalid config,
unsupported `--lang` value — produce exactly one clean error message on stderr
naming the cause (file path or option), exit code 1, no stdout output, and no
traceback. The user can fix the cause and re-run; the command holds no state.

### Feedback and consequences

One-shot read-only command: no persisted state, fully repeatable, reversible by
definition. Warnings and diagnostics go to stderr; stdout carries the
machine-consumed JSON only.

## Requirements

### Command and entry

- **R1.** The product provides a `goga codegraph` command runnable in the root
  of any existing project; no goga structures (`.goga/`, CODEMANIFEST files)
  are required for it to work.
- **R2.** The command help explains the output structure clearly for AI agents
  (established product convention).

### Language handling

- **R3.** Supported languages are python, golang, javascript, kotlin, swift. The
  command auto-detects which of them are present via their source files in the
  scanned tree.
- **R4.** One run analyzes every detected language and produces a single
  combined output tree.
- **R5.** An optional `--lang` option restricts the analysis to exactly one
  named supported language; an unsupported value yields one clean stderr error,
  exit code 1, no stdout.

### Scan scope

- **R6.** The scan starts at the invocation directory.
- **R7.** When `.goga/config.yml` exists and defines `lint.ignore`, exactly
  those patterns are excluded; no other ignore source is honoured. When the
  config is absent or omits `lint.ignore`, nothing is excluded.
- **R8.** Per-language file conventions apply during extraction (e.g. Go
  `_test.go` files are never type sources), as established by the corresponding
  per-language contract rules.

### CODEMANIFEST-true type selection

- **R9.** A type appears in the output iff it is representable in a CODEMANIFEST
  under the established per-language facade rules — public/exported types only
  (python: no `_` prefix; golang: capitalized exported declarations;
  javascript: exported ESM/CommonJS declarations of the module facade;
  kotlin/swift: per their established rules).
- **R10.** Private, internal, and test-only constructs never appear in the
  output.

### Cell mapping

- **R11.** Every directory containing at least one representable type becomes
  exactly one node; its `cell` value is the normalized directory path. A
  directory with representable types of several analyzed languages still yields
  one node aggregating them.
- **R12.** Node nesting mirrors directory containment via `children`;
  directories without representable types produce no node and no placeholder —
  descendants attach to their nearest ancestor node.

### Output

- **R13.** stdout carries exactly one JSON document — the node tree — and
  nothing else.
- **R14.** Nodes mirror `goga schema` node shape for the code-derivable fields:
  `cell`, `types` (sorted type names), `children`. Fields that exist in schema
  only through CODEMANIFEST authoring (description, usages, dependencies,
  tools) are omitted — never fabricated.
- **R15.** Determinism: the same code tree, the same config, and the same
  options produce byte-identical output across runs.
- **R16.** Read-only — the command modifies nothing on disk.

### Failure and empty behaviour

- **R17.** Any genuine failure — unreadable or unparseable source, invalid
  config, unsupported `--lang` value — produces exactly one clean error message
  on stderr naming the cause, exit code 1, no stdout output, no traceback.
- **R18.** An empty scan result — no supported-language code found, or code
  present but zero representable types — is a complete successful output: the
  JSON document `[]` on stdout, exit code 0.

## Constraints

- **C1. Cell-model authority.** The CODEMANIFEST DSL (interpreted by the goga
  AST tooling and the cell DSL specification) is the authoritative definition of
  cells and representable types; codegraph's projection must respect it,
  including the per-language facade rules already established in the existing
  per-language contract components. codegraph must not invent its own type
  model.
- **C2. No goga preconditions.** The command works on projects without `.goga/`
  or CODEMANIFEST files; existing goga structures are never required.
  `.goga/config.yml` is honoured only when present (`lint.ignore`).
- **C3. Ignore-source exclusivity.** `lint.ignore` is the only honoured ignore
  source; `.gitignore`, vendor heuristics, or hardcoded exclusions are not used.
- **C4. Language set.** Exactly python, golang, javascript, kotlin, swift (the
  set supported by the existing contract tooling); no other languages.
- **C5. Read-only boundary.** codegraph never creates or modifies cells,
  CODEMANIFEST files, `.usages`, or any project file; all creation belongs to
  the future init pipeline.
- **C6. Command conventions.** Thin CLI wrapper over a domain component; stdout
  JSON only; diagnostics to stderr; exit 0 only on complete output; clean
  errors without tracebacks; agent-oriented help — established goga conventions
  that must not regress.
- **C7. Determinism boundary.** Identical inputs (code tree, config, options)
  yield byte-identical output; the output is the stable contract for the future
  init pipeline.
- **C8. Scope boundary.** This change delivers the view command only: no
  cell/CODEMANIFEST generation, no init-pipeline wiring, no hooks/tool-package
  checkpoints in the codegraph output (tools area omitted); these remain future
  work.

## Scope

### In Scope

- The new `goga codegraph` CLI command — a read-only view of an existing
  project's code projected onto the goga cell model.
- Auto-detection of the supported languages (python, golang, javascript, kotlin,
  swift) present in the scanned tree.
- The optional `--lang` restriction option with clean failure on unsupported
  values.
- Scanning from the invocation directory honouring only `lint.ignore` from
  `.goga/config.yml` (when present) plus the established per-language file
  conventions.
- CODEMANIFEST-true type selection — only public/exported types representable
  in a CODEMANIFEST, per the established per-language facade rules.
- Directory→cell node mapping: one node per directory containing representable
  types, nesting via `children`, no placeholder nodes.
- Deterministic JSON tree output on stdout with schema-shaped nodes (`cell`,
  `types` as sorted names, `children`).
- Failure and empty behaviour per the requirements: clean stderr errors with
  exit 1 for genuine failures; `[]` with exit 0 for an empty scan.
- Agent-oriented command help explaining the output structure.

### Out of Scope

- Any creation or modification of cells, CODEMANIFEST files, or `.usages` —
  that belongs to the future init pipeline.
- The init pipeline itself (wiring codegraph into goga init / goga pipelines).
- Contract-detail output (signatures, properties, methods) — type names only.
- Derivation of description / usages / dependencies fields from code.
- Hooks / tool-package checkpoints and a tools area in the codegraph output.
- Any ignore source other than `lint.ignore` (`.gitignore`, vendor heuristics).
- Languages beyond the five supported by the existing contract tooling.
- Output formats other than the JSON document on stdout (no text/table
  renderers).
- Changes to existing commands (schema, contract, init) beyond adding the new
  command.

## Success Criteria

- **SC1.** Running `goga codegraph` in the root of an existing project that
  contains no goga structures (no `.goga/`, no CODEMANIFEST files) produces the
  code-derived schema view on stdout and exits 0.
- **SC2.** For a sample project in each of the five supported languages
  (python, golang, javascript, kotlin, swift), the command produces a non-empty
  tree containing that project's public/exported types.
- **SC3.** The output contains exactly the types a CODEMANIFEST would
  represent — private, internal, and test-only constructs of the scanned code
  do not appear (e.g. `_`-prefixed Python names, unexported Go declarations,
  `_test.go` declarations, unexported JavaScript module members).
- **SC4.** The tree obeys cell-building rules: one node per directory containing
  representable types, nesting mirrors directory containment, no placeholder
  nodes for type-less directories.
- **SC5.** For a directory already governed by a CODEMANIFEST that is consistent
  with its code (a cell passing the `goga contract` comparison), the types
  codegraph reports for that directory match the entity and routine names
  declared in its CODEMANIFEST.
- **SC6.** Repeated runs over the same code tree with the same options produce
  byte-identical stdout.
- **SC7.** stdout carries a single machine-parseable JSON document and nothing
  else; every genuine failure (unknown `--lang` value, unparseable source,
  invalid config) yields exactly one clean stderr message, exit code 1, and no
  partial stdout; an empty scan yields `[]` and exit 0.
- **SC8.** Running codegraph leaves the project byte-identical — no file is
  created or modified.
