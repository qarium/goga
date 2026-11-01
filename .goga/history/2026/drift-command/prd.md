# Contract Drift Visibility: the `goga drift` Command

## Problem

A maintainer of a goga-managed project works with two structural views of the same
project: the declared contract view (CODEMANIFEST files, rendered by `goga schema`)
and the code-derived view (`goga codegraph`). During contract maintenance
(refactoring), bootstrapping manifests onto existing code, and accepting newly
delivered functionality, these views silently diverge:

- cells declared in manifests but absent from the code;
- cells present in the code but not covered by a manifest;
- types declared in a manifest but absent from the code;
- types present in the code but not declared by the manifest.

No existing product capability exposes this divergence: `goga lint` validates the
internal correctness of manifest documents, and `goga usages status` tracks the
drift of external dependency usages — neither compares contracts with code.

As a result, stale and missing contracts go unnoticed and mislead the consumers of
`goga schema`, both humans and downstream workflows. Finding the divergence today
requires manually diffing two large JSON trees.

## Users

### Primary user

The project maintainer — a developer who writes and updates CODEMANIFEST files
alongside the code in a goga-managed repository and runs goga console commands in
a terminal:

- during refactoring, to keep contracts aligned with the changing code;
- while bootstrapping, to bring manifests onto existing code;
- during acceptance, to review newly delivered functionality against the declared
  contracts.

Goal: quickly see the exact set of cells and types where the declared and actual
views disagree, without manually comparing two JSON trees. Expects the result to
reflect the current working tree, a flat and predictable JSON report, and
repeatable runs.

### Secondary actor

The automation consumer — a CI job or an AI agent in acceptance and change review
flows — invokes the command non-interactively, reads the report from stdout as
machine-parseable JSON, and uses it to decide whether the delivered functionality
matches the declared contracts.

## Goals

1. **Exact divergence visibility.** The maintainer can see the complete, exact set
   of structural discrepancies between the declared contracts and the actual code —
   at cell and type level — as one flat, machine-readable report, so that every
   discrepancy can be identified and eliminated. The target state of a project is
   zero discrepancies; a discrepancy is always a defect, never an intentional
   state.
2. **Trustworthy contracts.** Contract maintenance, bootstrapping, and acceptance
   use the report as a routine, repeatable health check of contract actuality;
   stale and missing contracts stop going unnoticed.
3. **Automation signal.** CI and acceptance agents can consume the discrepancy
   list programmatically and treat the presence of discrepancies as a
   contract-health failure: zero discrepancies means healthy.

## User Experience

### Entry point

The user runs `goga drift` from the project root. The command optionally accepts
the same filters as `goga schema` and `goga codegraph` (positional cell paths,
`--max-depth`, `--depends-on`). Filters scope the report to the selected part of
the project — for example, the subsystem under acceptance; discrepancies are
computed on the complete views, and a cell is reported when it survives the
filters in at least one of the two views.

### Primary flow

1. The user runs `goga drift` after refactoring, bootstrapping, or receiving new
   functionality.
2. The product compares the declared view with the code-derived view and prints a
   flat JSON list to stdout. Each entry identifies the direction and its subject:
   the cell path for cell-level discrepancies; the cell path and the sorted list
   of the cell's type names missing from the other view for type-level entries.
   The order of entries is stable.
3. If discrepancies were found, the command exits with the dedicated
   discrepancies-found status; the full JSON report is still printed.
4. The user reads the list, fixes the manifests or the code, and re-runs the
   command until the report is empty.

### Healthy state

When the two views agree, the command prints an empty JSON list and exits with
the success status. This is the recognizable healthy state, by glance and by exit
status.

### Automation signal

The completion status clearly distinguishes three outcomes:

- comparison completed, no discrepancies (healthy);
- comparison completed, discrepancies found (the report is printed);
- the comparison could not be performed (execution failure).

### Failure behavior

Execution failures — an uninitialized project, a configured language outside the
supported set, an unparseable source file, manifest validation failures — produce
one clean error message on stderr, nothing on stdout, and the execution-failure
status. The user can fix the cause and retry; the command holds no state between
runs.

### Repeatability and consequences

The command is read-only and deterministic: identical project state,
configuration, and filters produce byte-identical output, and the project files
remain unchanged after a run. Acting on the report is the user's own editing; the
command itself changes nothing.

## Requirements

### Command surface

- **R1.** The product provides a console command `drift` in the goga CLI, runnable
  from the project root with no required arguments.
- **R2.** The command accepts the same filtering options as `schema` and
  `codegraph` — positional cell paths, `--max-depth`, `--depends-on`.
  Discrepancies are always computed on the complete, unfiltered views; the
  filters scope the report only: an entry is reported when its cell survives
  the filters in at least one of the two filtered views. Because
  `--depends-on` selects cells by declared dependencies in the declared view
  and by resolved imports in the code-derived view, this asymmetry must never
  surface as fabricated cell-level entries.

### Comparison semantics

- **R3.** The command compares the declared contract view (cells and their
  declared types) with the code-derived view (cells and their exported facade
  types).
- **R4.** Exactly four discrepancy kinds are reported:
  1. cell present in the code-derived view but absent from the declared view;
  2. cell present in the declared view but absent from the code-derived view;
  3. type present in the declared view but absent from the code-derived view;
  4. type present in the code-derived view but absent from the declared view.
- **R5.** Business rule — no double reporting: type-level discrepancies are
  evaluated only for cells present in both views; a cell-level discrepancy
  implicitly covers all types of that cell and produces no additional type-level
  entries.
- **R6.** Identity: a cell is identified by its normalized cell path; a type is
  identified by its name within its cell.

### Output and completion statuses

- **R7.** The report is a flat JSON array printed to stdout. Each entry carries
  the direction — `schema_only` or `codegraph_only` — and the cell path. An
  entry without `types` is a cell-level discrepancy: its cell exists in only
  one view. An entry with `types` is a type-level discrepancy group: the sorted
  list of type names of that cell missing from the other view; a cell with
  drift in both directions yields two entries. The four semantic discrepancy
  kinds of R4 map onto this encoding by direction and the presence of `types`.
  No nested trees, no summary objects.
- **R8.** The entry order is deterministic and stable — sorted by cell path,
  then direction; identical project state, configuration, and filters produce
  byte-identical output.
- **R9.** Completion statuses:
  - `0` — comparison completed, no discrepancies; the command prints an empty
    JSON list;
  - `1` — comparison completed, discrepancies found; the full JSON report is
    printed;
  - `2` — the comparison could not be performed (execution failure).
- **R10.** The command is read-only: it does not modify the project tree.

### Failure behavior

- **R11.** Execution failures — an uninitialized project, a configured language
  outside the supported set, an unparseable source file, manifest validation
  failures — produce one clean error message on stderr, no stdout output, and
  the execution-failure status `2`.

## Constraints

- **C1. Family conventions.** `drift` is a first-class goga console command and
  follows the established behavior principles of the command family: invocation
  from the project root, readable help, options consistent with `schema` and
  `codegraph`.
- **C2. Compared sources stay unchanged.** The solution must not change the
  user-visible behavior or output format of the existing `goga schema` and
  `goga codegraph` commands; drift consumes them as they are.
- **C3. Single configured language.** The comparison covers only the language
  configured in the project configuration, from the supported set (python, golang,
  javascript, kotlin, swift). Any other configured language is an execution
  failure. Discrepancies outside the configured language are not observable.
- **C4. Name-level comparison.** The comparison is structural and name-level
  only: normalized cell paths and type names. Richer semantics (signatures,
  behavior, annotations) are not available to the comparison and are not claimed.
- **C5. Execution guarantees.** Determinism and read-only behavior are
  established guarantees of the command family; `drift` preserves them.
- **C6. Channel conventions.** The result goes exclusively to stdout; failure
  diagnostics go exclusively to stderr; the completion status distinguishes
  "discrepancies found" from "could not be performed".

## Scope

### In Scope

1. The `goga drift` console command: invocation without arguments and with the
   symmetric filters (cell paths, `--max-depth`, `--depends-on`) applied to both
   compared views to scope the report.
2. The schema-versus-codegraph comparison producing exactly the four discrepancy
   kinds at cell and type level, with the no-double-reporting business rule.
3. The flat JSON report on stdout (kind, cell path, type name) in a
   deterministic, stable order.
4. The completion statuses: `0` — no discrepancies, `1` — discrepancies found,
   `2` — execution failure; failure diagnostics on stderr.
5. Execution-failure behavior inherited from the compared sources.
6. User-facing command documentation in the convention of the command family,
   including the JSON report structure in the command help — as `schema` and
   `codegraph` document theirs.

### Out of Scope

1. Any change to the behavior or output of the existing `goga schema` and
   `goga codegraph` commands.
2. Auto-fixing and generation: the command does not edit manifests or code and
   does not draft CODEMANIFEST updates.
3. Deeper comparison semantics: dependency-level drift (types or usages on cell
   edges), signatures, annotations; external-dependency usage drift remains owned
   by `goga usages status`.
4. Multiple languages within one run, beyond the configured project language.
5. Strictness configuration: ignore lists, thresholds, mode flags — the
   "discrepancy is a defect" rule is fixed.
6. CI integration artifacts (workflow definitions, pre-commit hooks), history
   tracking, caching, or watch modes.

## Success Criteria

- **SC1. Completeness and precision.** In a project with planted discrepancies
  of all four kinds, `goga drift` reports exactly those discrepancies — each
  entry identifies the direction, the cell path, and (for type-level entries)
  the sorted list of type names missing from the other view; nothing extra,
  nothing missing.
- **SC2. Format.** The output is a flat JSON array, parseable as-is, with no
  nested trees or summary objects.
- **SC3. Healthy state.** When the declared and code-derived views agree, the
  command prints an empty list and exits with status `0`.
- **SC4. Repeatability and safety.** Repeated runs on an unchanged tree produce
  byte-identical output, and the project files remain unchanged.
- **SC5. Distinguishable statuses.** A run that finds discrepancies prints the
  full JSON report and exits `1`; an execution failure (for example, an
  uninitialized project) prints nothing to stdout, states the reason on stderr,
  and exits `2`.
- **SC6. Scoping.** With filters applied, the report covers only the selected
  scope; discrepancies outside the scope are not reported.
- **SC7. Family integration.** The command is available in the CLI with help
  documentation covering the arguments, options, the JSON report structure, and
  the completion statuses, consistent with `schema` and `codegraph`.
