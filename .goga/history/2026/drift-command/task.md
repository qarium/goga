# Contract Drift Visibility: the `goga drift` Command

## Current State

The project provides two structural views of a goga-managed repository:

- The declared contract view, produced by the `goga/schema` domain: the
  routine `schema(cells, max_depth, depends_on)` builds the cell tree from the
  loaded AST, applies the filters and the tools overlay delivered through the
  schema hooks checkpoints, and returns a serialized JSON string —
  serialization lives inside the domain.
- The code-derived view, produced by the `goga/codegraph` domain: the routine
  `codegraph(cells, max_depth, depends_on)` orchestrates the analysis
  pipeline (`collect_facts`, `derive_units`, `resolve_links` from
  `goga/codegraph/analysis`) and renders the tree; the renderer already
  assembles object records (`CodegraphNode` from `goga/codegraph/facts`) but
  serializes them to a JSON string inside the domain.

The CLI wrappers `goga/commands/schema` and `goga/commands/codegraph` are the
only production callers of the two domain routines; they print the domain
string via click and exit 1 on any domain failure. The `goga/commands` facade
re-exports every command; user-facing command documentation follows the
`docs/features/<command>/` convention (index, cli, api, configuration,
hooks).
Existing test suites cover both domains (`tests/schema/`, `tests/codegraph/`,
and integration tests).

No existing capability compares the two views: `lint` validates the internal
correctness of manifest documents, `usages status` tracks external dependency
usage drift. Structural divergence between contracts and code — cells and
types declared but absent, present but undeclared — is invisible today except
by manually diffing two large JSON trees.

## Description

Implement the `goga drift` console command that compares the declared
contract view with the code-derived view and reports their structural
discrepancies — at cell and type level — as one flat, deterministic JSON
report on stdout.

The comparison runs in-process on Python object trees: the `schema` and
`codegraph` domains are refactored to return clean Python objects instead of
JSON strings, and JSON serialization moves to the command layer; the
user-visible behavior and output of the existing `schema` and `codegraph`
commands stay byte-identical.

Discrepancies are facts of the complete views: the comparison always runs on
full, unfiltered representations, and the filters scope the report only — an
entry is reported when its cell survives the filters in at least one of the
two filtered views; the `--depends-on` asymmetry (declared manifest
dependencies vs resolved code imports) must never surface as fabricated
cell-level entries.

Exactly four discrepancy kinds are reported (cell only in the declared view,
cell only in the code-derived view, type only in the declared view, type only
in the code-derived view), encoded as two directions — `schema_only` /
`codegraph_only` — with a grouped, sorted `types` list per cell; the absence
of `types` marks a cell-level discrepancy. Type-level entries exist only for
cells present in both views — no double reporting. Entry order is stable:
sorted by cell path, then direction; the report uses the family JSON style.

Completion statuses: `0` — comparison completed, no discrepancies; `1` —
comparison completed, discrepancies found (the full report is printed); `2` —
execution failure (one clean error message on stderr, nothing on stdout).
Exit `2` is a deliberate, permanent deviation from the installed family
convention (`schema`, `codegraph`, `usages status` fail with `1`), reserved
for the three-outcome contract — it must not be "aligned" later.

The command is read-only and deterministic: identical project state,
configuration, and filters produce byte-identical output; the project tree
remains unchanged after a run.

Authoritative inputs: the ADR at `.goga/history/2026/drift-command/adr.md`
and the PRD at `.goga/history/2026/drift-command/prd.md`; this task follows
them.

## Scope

**In scope:**
- The `drift` console command in the goga CLI: runnable from the project root
  without required arguments, with the same filters as `schema` and
  `codegraph` (positional cell paths, `--max-depth`, `--depends-on`) applied
  to both compared views to scope the report.
- Internal refactor of the `schema` and `codegraph` domains: return clean
  Python objects; serialization moves to the command layer; CLI behavior and
  output of `schema` and `codegraph` remain byte-identical.
- The comparison logic: the four discrepancy kinds at cell and type level
  with the no-double-reporting rule; identity by normalized cell path and
  type name; computed on complete views with scope-gating filter semantics.
- The flat JSON report on stdout (direction, cell path, grouped sorted type
  names) in deterministic order, in the family JSON style.
- Completion statuses `0` / `1` / `2` with failure diagnostics on stderr
  only.
- Command help documenting the arguments, options, the JSON report structure,
  and the completion statuses — consistent with `schema` and `codegraph`.
- Registration of the command in the `goga/commands` facade.
- User-facing documentation under `docs/features/drift/` in the family
  convention.
- Tests per the `convention` practice: unit tests for every public
  function/class (main scenarios and edge cases), CLI tests invoking the
  command handler directly.

**Out of scope:**
- Any change to the behavior or output of the existing `goga schema` and
  `goga codegraph` commands.
- Auto-fixing or generation: no manifest or code edits, no drafted
  CODEMANIFEST updates.
- Deeper comparison semantics: dependency-edge drift, signatures,
  annotations; external-dependency usage drift remains owned by
  `goga usages status`.
- Multiple languages within one run beyond the configured project language.
- Strictness configuration: ignore lists, thresholds, mode flags — the
  "discrepancy is a defect" rule is fixed.
- CI integration artifacts (workflow definitions, pre-commit hooks), history
  tracking, caching, watch modes.

## Acceptance Criteria

- In a project with planted discrepancies of all four kinds, `goga drift`
  reports exactly those discrepancies — each entry identifies the direction,
  the cell path, and (for type-level entries) the sorted list of type names
  missing from the other view; nothing extra, nothing missing.
- The output is a flat JSON array, parseable as-is, with no nested trees or
  summary objects.
- When the declared and code-derived views agree, the command prints an
  empty list and exits `0`.
- Repeated runs on an unchanged tree produce byte-identical output, and the
  project files remain unchanged.
- A run that finds discrepancies prints the full JSON report and exits `1`;
  an execution failure (for example, an uninitialized project) prints
  nothing to stdout, states the reason on stderr, and exits `2`.
- With filters applied, the report covers only the selected scope, and the
  `--depends-on` asymmetry never produces fabricated cell-level entries.
- The command is available in the CLI with help documentation covering the
  arguments, options, the JSON report structure, and the completion statuses.
- `goga schema` and `goga codegraph` outputs are byte-identical before and
  after the domain refactor, verified by the CLI-level tests (existing and
  new golden runs); the existing domain tests that pin the JSON-string
  return are adapted to the object-returning contract with their
  expectations preserved.
- All tests pass (`pytest tests/ -x`); `ruff` reports no findings for the
  touched code.

## Stack

- **Frameworks:** click — the existing CLI framework of the command family
  (existing project dependency, covered by the `click` cook usage)
- **Libraries:** Python 3.10+ standard library only — `json` for
  serialization in the family style (the `beautiful_json` practice),
  `dataclasses` for clean object records (frozen, keyword-only per the
  `convention` practice)
- **Infrastructure:** none — a pure in-process, read-only console command;
  no databases, brokers, or new runtime components
- **Testing:** pytest, ruff, pytest-cov per the `convention` practice

## External Dependencies

| Component             | Usage file                            | Status    |
|-----------------------|---------------------------------------|-----------|
| click                 | `.goga/usages/cooks/click.md`         | existing  |
| json family style     | `.goga/usages/cooks/beautiful_json.md`| existing  |
| project conventions   | `.goga/usages/conventions.md`         | existing (base) |

No new external dependencies; all usage files are current — nothing to
create or update.

## Risks and Constraints

- **C2 — compared sources stay unchanged:** the domain refactor must keep
  the user-visible behavior and output of `schema` and `codegraph`
  byte-identical; only the internal return contract (objects instead of a
  JSON string) and the placement of serialization change. This is the
  highest-risk area of the task and must be regression-verified against the
  existing domain test suites — the suites that pin the JSON-string return
  adapt to the object contract with their expectations preserved, while
  golden CLI-level tests carry the byte-identical guarantee.
- **Filter semantics:** the scope-gating rule (compute on complete views,
  report on filtered survival in at least one view) is subtle; comparing the
  filtered trees directly would fabricate cell-level entries out of the
  `--depends-on` asymmetry — the PRD precision contract forbids it.
- **Exit-code deviation:** exit `2` for execution failure is deliberate and
  permanent; a later "alignment" to the family's exit `1` would break the
  three-outcome contract.
- **C1 — family conventions:** invocation from the project root, options
  consistent with `schema` and `codegraph`, help documenting the JSON report
  structure.
- **C3 — single configured language:** an unsupported configured language is
  an execution failure (exit `2`), never an empty report.
- **C4 — name-level comparison only:** normalized cell paths and type names;
  no signature or annotation semantics are claimed.
- **C5, R10 — determinism and read-only:** established family guarantees;
  the command holds no state between runs.
- **Hooks interaction:** the declared view carries the tools overlay
  delivered via the schema hooks checkpoints; drift consumes the schema view
  as it is, and hook failures remain execution failures.

## Scope Estimate

Single task — no decomposition. The parts (two domain refactors, the
comparison logic, the CLI wrapper, the facade registration, documentation,
tests) deliver user value only together and share one integration point; the
refactors are user-invisible by design (C2).

## Existing Architecture

Affected cells (modification):

- `goga/schema` — the domain returns objects instead of a JSON string
- `goga/codegraph` — the same internal refactor for the code-derived view
- `goga/commands/schema` — the wrapper takes over JSON serialization of
  the object result via the `beautiful_json` practice; CLI output stays
  byte-identical
- `goga/commands/codegraph` — the same serialization takeover for the
  code-derived view
- `goga/commands` — the facade re-exports the new command

Affected cells (creation; working names — the design phase fixes the final
structure):

- the drift comparison domain cell (working name `goga/drift`)
- the drift CLI wrapper cell (working name `goga/commands/drift`)

Integration notes:

- The comparison domain consumes the two refactored domain APIs in-process;
  per the ADR it owns no traversal of its own.
- The object records of `goga/codegraph/facts` (for example `CodegraphNode`)
  already model the code-derived view; reuse the existing vocabulary instead
  of inventing a parallel one — the design phase decides the exact shapes.
- The declared view carries the tools overlay; the code-derived view carries
  manifest-only fields nowhere — the two views expose different field sets,
  and the comparison works on cell paths and type names only.
- The only production callers of the refactored domain routines are the two
  existing CLI wrappers; the existing test suites of the domains are the
  regression net for the domain behavior, and golden CLI-level tests carry
  the byte-identical guarantee.
- Documentation lands in `docs/features/drift/` following the family layout.

## Notes

- Authoritative inputs: `.goga/history/2026/drift-command/adr.md`
  (architecture decisions) and `.goga/history/2026/drift-command/prd.md`
  (requirements R1–R11, constraints C1–C6, success criteria SC1–SC7).
- By stage constraints, this document intentionally contains no code
  examples and no architecture design: internal module layout, object
  shapes, and final cell boundaries are design-phase decisions.
- Decisions already fixed by the ADR and binding for the implementation:
  in-process object comparison (no JSON parsing, no subprocesses, no
  private walkers), scope-gating filters, the grouped two-direction report
  encoding, the `(cell, kind)` sort order, the family JSON style, exit `2`
  for execution failure, and help documenting the JSON report structure.
