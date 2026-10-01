# Contract domain hooks zone — per-cell read-and-contribute checkpoint (`amend_contract`)

## Current State

The hooks platform (`goga/hooks`: catalog, tools, registry, dispatch) is complete and consumed as
is. The action catalog (`goga/hooks/catalog`) contains records for the onboarding, pipeline,
statuses, topics, build, config, schema, and usages domains — and **no contract-domain record**:
the contract domain exposes no subscription address, so an installed tool package cannot subscribe
to the contract workflow at all.

The precedent zone exists end to end: `goga/schema/hooks` owns the per-cell facts view, the
per-tool contribution model with its key-wise merge, and the checkpoint entry over the platform
facade; `goga/commands/schema` integrates it. The zone imports types and practices from
`goga/hooks` only and does not import the domain it extends.

The `goga contract` command (`goga/commands/contract`) builds the comparison itself: it loads the
configuration through the config amendment checkpoint (`ConfigHooks`/`ConfigOverlay`), resolves the
language, walks the requested cell paths, extracts the declared types from the CODEMANIFEST via
the AST, obtains the implemented contracts through the contract dispatcher (`goga/contract`), and
pairs the declared and implemented forms — CODEMANIFEST is primary — into the JSON output
(`{normalized path: {TypeName: {signature, properties, methods}}}` with `codemanifest` /
`implementation` pairs) via the `beautiful_json` practice. The contract domain itself (dispatcher,
five tree-sitter extractors, `goga/contract/data` model) is not involved in delivery and does not
change.

The documentation states the gap directly: `docs/features/contract/hooks.md` says the contract
domain exposes no hook actions of its own for tool packages today; the declared-actions
enumerations live in `docs/features/hooks/index.md` and `docs/features/tools/hooks.md`; the
response structure is documented in `docs/features/contract/cli.md` and the command help.

## Description

Open the contract domain extension surface on the hooks platform following the accepted ADR
(`.goga/history/2026/add-hooks-to-contract/adr.md`) — the schema precedent with one settled
deviation: the delivery event is per cell, but a tool's contribution is addressed per declared
type and lands as the `tools` area on the **type node** of the command's JSON output (the
command's fixed-key node), next to `signature`/`properties`/`methods`.

1. **Catalog record.** Exactly one additive action-catalog record — domain `contract`, action name
   `amend_contract`, error class hard — published once and never rewritten.
2. **Contract domain hooks zone** — a new product surface with a per-cell read-and-contribute
   checkpoint:
   - the read view carries the cell's normalized path and its comparison facts exactly as the
     output composes them — for every declared type and member, the declared (codemanifest) form
     and the extracted (implementation) counterpart as pairs, including absent counterparts — one
     language-agnostic shape of string pairs, read-only, identical for every tool;
   - the contribution is per tool, addressed per declared type (a mapping from type name to the
     tool's fact mapping), and commits as one unit only after every hook of that tool returned
     without failing and the buffered facts are structurally representable in the output;
   - a contribution addressed to a type the cell does not declare is the hard structural failure;
   - committed contributions compose deterministically as a tools area on each addressed type's
     node, under each contributing tool's identity; inside one tool's contribution for one type,
     repeated writes to the same fact name resolve to the last write.
3. **Command integration** (`goga/commands/contract`):
   - the built-in comparison of every requested cell completes before any hook runs — existing
     failures keep today's precedence; delivery then walks the requested cells deduplicated by
     normalized path, in first-request order;
   - the tools area is present on a type node exactly when at least one tool contributed at least
     one fact for that type — absent, never an empty object, otherwise;
   - with no tool packages installed, none subscribed, or subscriptions that contribute nothing,
     the output is identical to the same invocation before the extension;
   - a hook hard failure stops the command through its existing error path with a clean error
     naming the tool, the action, and the failing cell path — and, for a bad address, the
     offending type name — no raw traceback, no output for the run;
   - the command help explains the response structure including the tools-area semantics.
4. **One delivered-facts shape** working uniformly for all five supported implementation languages
   (python, golang, javascript, kotlin, swift).
5. **Documentation** of the new surface: the contract hooks page replaces the "no hook actions
   today" statement with the address, error class, what a hook reads, what it may contribute,
   where contributions appear, and the failure treatment; the declared-actions enumerations and
   the response-structure description are updated accordingly.

The zone's placement and internal structure (cell boundaries, module layout, names and signatures
of the facts view, the contribute surface, the checkpoint entry, CODEMANIFEST structure and
Imports/Usages wiring) and the exact error-message wording remain open for the design stage — the
ADR lists them as unresolved; this task does not fix them.

## Scope

**In scope:**

- The contract domain's subscription address in the platform action catalog (domain `contract`,
  action `amend_contract`, hard failure class), published once.
- The contract domain hooks zone as a product surface: the per-cell read view over the cell's
  comparison facts, the per-tool unit-commit type-addressed contribution model, and the
  deterministic composition of committed contributions onto the type nodes.
- Integration of the per-cell checkpoint into the contract comparison command: delivery over the
  requested cells after the built-in comparison, the tools area on each type node of the JSON
  output, and the unchanged baseline when nothing contributes.
- Hard-failure behavior of the checkpoint wired into the command's documented error path, with
  existing failure behavior preserved (unknown cell; implementation package not importable;
  extraction failure; configuration load failure).
- One language-agnostic shape of the delivered facts, working uniformly for all five supported
  implementation languages.
- Documentation of the new surface: the contract hooks documentation page, the command help's
  response-structure description, and the declared-actions enumerations.
- Tests mirroring the new zone and the updated command per the project conventions.

**Out of scope:**

- Notification moments of the contract workflow (started/completed events) — the recorded
  decision is the amendment-only schema precedent; no run-event facts are added.
- Any change to the built-in comparison itself — new checks, verdicts, diff semantics, or letting
  tools alter the comparison; tools extend the output only.
- Platform changes — new error classes, delivery styles, registry or enumeration behavior; the
  platform is consumed as is.
- Rewriting or extending other domains' published catalog records.
- Authoring or shipping any concrete tool package contributions — the ecosystem content belongs
  to tool authors.
- Persisting contributions or introducing cross-run state.
- New operator controls — no flags to disable or configure tool participation.
- Extending other commands or future contract-domain consumers — the checkpoint is delivered
  where the comparison runs.

## Acceptance Criteria

- **Subscribable address.** The action catalog contains exactly one new contract-domain record
  (`contract` / `amend_contract`, hard). A tool package can register a hook at the address, the
  registration is visible through the hook registration inspection (`goga hooks`), and the hook is
  invoked when the contract comparison runs.
- **Tool context surfaced.** With a subscribed tool contributing facts, the comparison output
  carries those facts under that tool's identity on the contributed type's node; the built-in
  comparison stands unchanged alongside them; the same delivered-facts shape is observed for each
  of the five supported implementation languages.
- **Multiple tools.** Contributions of several subscribed tools all appear in one run, each under
  its own identity, in the platform's enumeration order.
- **Unchanged baseline.** With no tool packages installed, no subscriptions, or empty
  contributions, the command's output is byte-identical to the output of the same invocation
  before the extension.
- **Clean hard failure.** A crashing hook, a structurally unrepresentable contribution, or a
  contribution addressed to an undeclared type stops the command with a clean stderr error naming
  the tool, the action, and the failing cell path (and the offending type name for a bad address);
  the command exits through its error path and produces no result output for that run; after the
  tool is fixed or uninstalled, a re-run completes cleanly.
- **Pure and repeatable.** Running the command with contributing tools changes no project or
  authored file, and repeated identical invocations produce identical output.
- **Failure precedence and single delivery.** An existing failure of the built-in
  comparison (unknown cell; package not importable; extraction failure; configuration
  load failure) fires before any hook runs — no hook is invoked for the run. Requesting
  the same cell more than once (directly or via paths that normalize to one) delivers
  the checkpoint exactly once, in first-request order.
- **Documented surface.** The documentation describes the contract hook action — address, error
  class, what a hook reads, what it may contribute, where contributions appear, and the failure
  treatment — replacing the current "no hook actions today" statement; the command help explains
  the tools-area semantics of the response structure.
- **Validation gates.** `pytest tests/ -x` passes and `ruff check` is clean for all touched code,
  per the project conventions.

## Stack

- **Frameworks:** click (>=8.0, per `pyproject.toml`) — the `goga contract` command
  (existing command, existing usage file).
- **Libraries:** Python stdlib `dataclasses` (`kw_only=True`) for the zone's facts/contribution
  model; the existing internal hooks platform APIs (`declared_actions`; the staged per-tool
  delivery primitives: registry assembly once per run, per-address subscriptions, per-tool
  contexts, context wrapping, call-argument projection); `beautiful_json` for the command's JSON
  output; configuration via `load_project_config` with the `ConfigHooks`/`ConfigOverlay` amendment
  (existing integration, unchanged).
- **Infrastructure:** none — everything lives in memory for the current run; no database, broker,
  or queue.
- **Language and environment:** Python 3.10+, virtualenv, `pyproject.toml` configuration.
- **Tests and quality:** pytest, ruff, pytest-cov per the `conventions` practice (tests mirror the
  source structure; CLI tested by direct handler call; mocks only at external boundaries).

## External Dependencies

| Component | Usage file | Status |
|-----------|----------------------------------------|------------------------------|
| click | `.goga/usages/cooks/click.md` | existing |
| beautiful_json | `.goga/usages/cooks/beautiful_json.md` | existing |
| conventions (base) | `.goga/usages/conventions.md` | existing (base usages of `.goga/config.yml`) |
| hooks platform practices (`declaring-actions`, `per-tool-delivery`, `registering-hooks`) | `goga/hooks/.usages/*.md` (cell-level) | existing — read-only references connected via the zone's Imports |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or
update them in the task.

No new external dependencies are introduced. No `.goga/usages/cooks/` file is created or updated
by this task: the existing project-level practices cover every new usage pattern. The new zone
cell authors its own cell-level usage (the analog of `goga/schema/hooks/.usages/checkpoints.md`)
as part of its own deliverable — that is a cell artifact, not a project cooks file.

## Risks and Constraints

- **Platform only.** The extension is built exclusively on the existing hooks platform; package
  enumeration, delivery, envelope validation, error classes, and diagnostics belong to the
  platform. No parallel extension mechanism.
- **Catalog additivity.** The catalog record is published once; its domain, name, and error class
  are never rewritten — the contract address is durable.
- **Published output surface.** The command's JSON output structure is documented in the command
  help for AI agents: the base comparison fields cannot change; the tools area may only be added,
  and is absent when nothing contributed. The cell node is a mapping keyed by arbitrary type
  names — this is why the tools area lands on the type node (the fixed-key node); a declared type
  literally named `tools` must keep working unchanged.
- **Read-only domain.** Authored and project files are never modified; contributions exist in
  memory for the current run only.
- **Command conventions.** stdout carries only the JSON result; all errors go to stderr as clean
  messages without tracebacks; success exits 0, failures exit through the error path.
- **Caller-supplied context.** The zone performs no configuration reads, git access, or file
  reads, and does not import the domain it extends — the delivered context is built only from the
  values the caller passes.
- **One registry per run.** Delivering the checkpoint over many cells must not multiply the tool
  package enumeration.
- **Language-uniform view.** One language-agnostic facts shape for python, golang, javascript,
  kotlin, and swift — no per-language projection.
- **Failure precedence.** Existing failures fire before any hook runs: the built-in comparison of
  every requested cell completes first; delivery then walks cells in first-request order after
  deduplication by normalized path.
- **Determinism.** The same invocation with the same inputs and tools produces the same output.

## Scope Estimate

Single task — no decomposition. Approved with the user: every candidate split (catalog record /
zone / command integration / documentation) delivers no independent value alone — a record without
a zone is dead data, a zone without integration is unreachable, documentation without the surface
is false. The scale is comparable to the schema-domain precedent, delivered as one change. No
additional topics were created.

## Existing Architecture

Affected cells and their link connections:

- `goga/hooks/catalog` — additive data change: one new action record in the catalog. The catalog
  cell's declared types do not change; a published record is never rewritten.
- **New zone cell** (placement and internal structure decided at the design stage; the precedent
  places the schema zone at `goga/schema/hooks`) — connects to `goga/hooks` through Imports of the
  platform types and practices (the precedent imports `HookRegistry`, `wrap_context`,
  `build_hook_arguments`, `declared_actions` and the `per-tool-delivery` / `registering-hooks`
  practices). The zone does **not** import `goga/contract` or any extractor — all delivered facts
  are built from the values the caller passes. It owns the read view, the contribution model, the
  type-addressed composition, and the checkpoint entry; one zone object serves every checkpoint of
  a run over one shared registry.
- `goga/commands/contract` — new Imports/Usages entries toward the zone (the precedent command
  `goga/commands/schema` wires its zone through the zone's practices); the command builds the
  per-cell facts view from its own comparison data, delivers the checkpoint after the built-in
  comparison of every requested cell, and composes the tools area onto the type nodes. Its
  existing dependencies (`goga/ast`, `goga/config`, `goga/config/hooks`, `goga/contract`) stay
  unchanged.
- `goga/hooks` facade and `goga/contract` (dispatcher, extractors, `goga/contract/data`) — no
  changes.
- Documentation pages: `docs/features/contract/hooks.md` (rewrite), `docs/features/hooks/index.md`
  and `docs/features/tools/hooks.md` (declared-actions enumerations), `docs/features/contract/cli.md`
  (response structure), and the command help text.

## Notes

- Inputs: the accepted ADR (`.goga/history/2026/add-hooks-to-contract/adr.md`, accepted
  2026-09-29) and the revised PRD (`.goga/history/2026/add-hooks-to-contract/prd.md`). The decided
  shape: per-cell delivery with per-type addressed landing on the type node; the generalization
  left behind: the tools area lives on the fixed-key node of a command's output — the cell node in
  `schema`, the type node in `contract`.
- A requested cell with no declared types has no landing zone: the checkpoint is delivered over
  empty facts, and any non-empty contribution for it is the unknown-address hard failure.
- There is deliberately no cell-level landing: a tool's cell-level context lives inside its
  per-type facts; addressing deeper than the type is the tool's own fact vocabulary.
- Interview decisions (2026-09-29): formulation approved as presented; stack approved with no new
  external dependencies; single task without decomposition.
- Per the stage constraints, this task contains no code examples and makes no architecture
  decisions — zone placement, internal structure, names and signatures, CODEMANIFEST and
  Imports/Usages wiring, and exact error-message wording belong to the design stage.
