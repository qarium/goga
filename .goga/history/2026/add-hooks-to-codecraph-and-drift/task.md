# Hook Events for Codegraph and Drift

## Current State

The hooks platform is complete and uniform: the action catalog (`goga/hooks/catalog` — 28 actions, each with a soft/hard error class), the run registry, the dispatch with per-tool fresh views, and the tool-package registration contract. Domains open extension surfaces through zone cells over the platform facade — `goga/schema/hooks` is the reference: the per-cell amendment `schema/amend_cell` (hard; JSON facts land on the node under the tool identity inside the `tools` area) and the whole-tree veto gate `schema/validate_schema` (hard; walk-to-completion, one violation per tool, vetoes merge into one clean error).

The two remaining views are extension-free:

- `goga codegraph` (`goga/codegraph` with `goga/codegraph/analysis` and `goga/codegraph/facts`; CLI `goga/commands/codegraph`) exposes no hook actions. Its documentation (`docs/features/codegraph/hooks.md`) states the domain is hook-free. A tool-package author can attach facts to, and enforce policy over, the declared view (`goga schema`) but has no lever on the code-derived view.
- `goga drift` (`goga/drift` with `DriftEntry`, `compare_views`, `scope_entries`, `drift`; CLI `goga/commands/drift` with the exit 0/1/2 contract) exposes no hook actions of its own. Only the schema checkpoints fire inside it (via the declared-view producer). The exit code reflects the raw comparison alone: accepted drift cannot be suppressed, tool-known discrepancies cannot be added — the drift gate is unusable in CI without rebuilding it outside goga.

The example observer package `example/goga-tool-events` subscribes to every catalog action (28 today), and every hooks-enabled feature documents its actions on a per-feature page (`docs/features/<feature>/hooks.md`, pattern set by `docs/features/schema/hooks.md`).

## Description

Extend the single action catalog with six actions delivered entirely by the existing hooks platform — no new registration, dispatch, or extension mechanism:

- **`codegraph.amend_node` (hard)** — per-node facts amendment. For each node surviving the filters, each subscribed tool receives the node's code-derived facts (cell path, types, resolved dependencies, children) as a fresh read-only view and contributes JSON facts that land on the node under the tool's platform-assigned identity inside the `tools` area of the output. Fires wherever the codegraph routine runs — in `goga codegraph` and inside every codegraph producer call of a drift run. Mutually blind tools; contributions merge per the established schema rules.
- **`codegraph.validate_graph` (hard)** — whole-tree validation gate delivered after assembly and filters, before serialization. Each subscribed tool receives the final tree — the committed tools overlay included — as a read-only view and may veto. Vetoes and crashes (recorded as vetoes with the crash reason) merge into one clean error naming tool, hook, and reason; the command stops before any output. A veto exits `goga codegraph` with code 1; when the gate fires inside a drift run's producer call, the drift command exits 2 (the existing schema-gate precedent). An empty graph fires nothing.
- **`drift.run_started` (soft)** — moment at the beginning of every drift run carrying the requested filters (cells, max_depth, depends_on).
- **`drift.run_completed` (soft)** — moment on every terminal state of the run, failed ones included, carrying the last computed report stage — the final report (list settled, facts areas included) on finished runs, the scoped pre-amendment report when a later stage failed, nothing when the run failed before the report was computed — and the run outcome: a terminal finished/crashed marker plus, on crashed runs, a credential-free reason (no tokens, keys, passwords, or other secrets; paths and tool names permitted). Moment failures are soft: logged as warnings, never affecting the report or the exit code.
- **`drift.amend_report` (hard)** — report list control delivered after the scoped report is computed. Each amending tool receives the finished scoped report as a read-only view and produces an adjusted report by removing and/or adding entries — down to clearing the report entirely or surfacing discrepancies in an otherwise clean report. Every entry of an adjusted report must be well-formed: exactly the fields kind (one of the comparison's entry kinds), cell (a non-empty string), and types (a list of strings, or omitted for a cell-level entry); any other key or shape is a hard failure. Amending tools are mutually blind — each reads the same finished scoped report; the last adjusting tool in enumeration order wins; a tool that adjusts nothing leaves the report unchanged. No adjustment provenance appears anywhere in the output.
- **`drift.amend_entry` (hard)** — per-entry facts amendment delivered after the report amendment settles the final list. Every surviving entry — comparison-produced and tool-added alike — is delivered to each subscribed tool as a fresh read-only view of the entry facts (kind, cell, types); the tool contributes JSON facts that land on the entry under the tool's platform-assigned identity inside the `tools` area, merged per the established schema rules (key-wise later-wins within a tool, JSON-map shape enforced, empty commits nothing, `tools` appears iff at least one tool wrote at least one fact). Facts never affect the exit code; an empty final list fires nothing.

Run ordering within a drift run: start moment → view production, comparison, scoping → report amendment → entry facts amendment → completion moment.

Exit codes keep their meanings: `goga drift` exits 0 (no entries in the final report), 1 (entries in the final report), 2 (the run could not be performed), with 0 vs 1 decided by the final post-amendment entry list alone. Inside a drift run, hard failures of either drift amendment or the codegraph actions exit 2 with a clean error naming the hook, the tool, the action, and the reason — nothing on stdout. In the standalone `goga codegraph` run, every hard failure of a codegraph action — a crashed or malformed-amending hook, or a veto — is the command's ordinary error path: a clean stderr error, exit 1, nothing on stdout. The `tools` facts areas are the established goga-wide contribution idiom (as in `goga schema` output) and appear iff tools contribute facts; adjustment provenance — markers, annotations, or flags signaling that an entry was removed, added, or adjusted — is explicitly rejected.

## Scope

**In scope:**

- Six new catalog records: `codegraph.amend_node`, `codegraph.validate_graph`, `drift.run_started`, `drift.amend_report`, `drift.amend_entry`, `drift.run_completed` — subscribable through the existing registration contract.
- The codegraph hooks surface: the per-node amendment action and the whole-tree validation action, both hard, firing wherever the codegraph routine runs.
- The drift hooks surface: the soft start and completion moments, the hard report amendment action, and the hard per-entry facts amendment action.
- User-visible surfaces: the `tools` area in `goga codegraph` output nodes, the `tools` areas on `goga drift` report entries, drift exit codes decided by the final report.
- Documentation: the codegraph and drift hooks pages rewritten per the established per-feature pattern, complete for a tool author who has not read the goga source; the api and cli pages of both features updated with the checkpoint flow, the `tools` output key, and the failure semantics per the schema precedent; catalog-level documentation updated.
- The example observer package extended to the six new actions.
- Tests covering both zones, the integrations, and the no-tools invariants.

**Out of scope:**

- Any change to the hooks platform core (registry, dispatch, catalog mechanics, delivery semantics, error-class model).
- Any change to the drift comparison semantics (entry kinds, complete-view comparison, scoping rules) — the amendments are post-comparison steps only.
- A veto gate for drift (explicitly rejected).
- Adjustment provenance for the drift report — markers, annotations, or flags signaling that an entry was removed, added, or adjusted (explicitly rejected; the `tools` facts areas are contribution, not provenance, and stay in scope).
- Changes to the schema, contract, config, usages, build, pipeline, topics, or onboarding zones.
- New CLI commands, flags, or output formats beyond the `tools` area following the schema precedent.
- Baseline persistence or management tooling — baselining is a tool-package concern built on the new actions, not part of goga.
- Changes to codegraph language analysis (stages, supported languages).

## Acceptance Criteria

- A subscribed tool can attach JSON facts to `goga codegraph` output nodes under its tool identity, and the same subscription fires inside drift runs — the extension model is symmetric with `goga schema`.
- A subscribed tool can veto the final codegraph tree; the veto stops `goga codegraph` with a clean error naming tool, hook, and reason, exit 1, nothing on stdout.
- A raising or malformed node-amendment hook stops `goga codegraph` with a clean error, exit 1, nothing on stdout.
- A subscribed tool receives the drift start moment (filters) and completion moment (last computed report stage, outcome) on every drift run — including failed runs (crashed marker with a credential-free reason); a failing observer changes neither report nor exit code.
- A subscribed tool can clear a non-empty drift report → stdout prints `[]`, exit 0; and can add entries to a clean report → the entries print, exit 1.
- With two adjusting tools, the final report is the last adjusting tool's output in enumeration order.
- A subscribed tool can attach JSON facts to entries of the final drift report under its tool identity; the facts print inside the entry's `tools` area merged per the established rules, on comparison-produced and tool-added entries alike; the exit code still follows the entry list alone.
- A raising or malformed drift-amendment or entry-facts hook yields exit 2, a clean error naming hook, tool, action, and reason, and nothing on stdout.
- With no tools installed or subscribed, `goga codegraph` and `goga drift` outputs and exit codes are byte-identical to before the change.
- All new actions are declared in the single catalog, subscribable through the existing registration contract, documented in the per-feature hooks pages, and covered by the example observer package.

## Stack

- **Frameworks:** none new — Python 3.10+ (hard project constraint); the existing `click` CLI surface for both commands.
- **Libraries:** stdlib only for the new code — `dataclasses` (frozen, kw_only records and views per the project convention), `json` (serialization per the `beautiful_json` practice), `logging` (soft-failure warnings to stderr). Existing `click` usage continues unchanged.
- **Infrastructure:** none — no databases, brokers, or services; the runs stay read-only.

## External Dependencies

| Component | Usage file | Status |
|-----------|-----------|--------|
| click | `.goga/usages/cooks/click.md` | existing — covers the task's CLI patterns |
| beautiful_json | `.goga/usages/cooks/beautiful_json.md` | existing — covers the task's serialization patterns |

No new external dependencies. No new usage files in `.goga/usages/cooks/` are required; the existing files cover all usage patterns of this task. The platform practices `per-tool-delivery` and `registering-hooks` (cell-level usages of `goga/hooks`) are imported by the new zones as-is, never created or updated here.

## Risks and Constraints

- The existing hooks platform is the only delivery mechanism: per-tool fresh views, mutual blindness, hard/soft error classes, enumeration-order delivery, one registry per run. No parallel mechanism may be introduced.
- The action catalog is the single source of known subscription addresses; new addresses extend it additively, published records are never rewritten.
- Byte-identical baseline: with no tool packages installed or subscribed, `goga codegraph` and `goga drift` output and exit codes must be byte-identical to the behavior before this change.
- Determinism and idempotence must hold with tools present, including the last-wins report amendment under a deterministic tool enumeration order.
- The exit-code contract of both commands is stable in meaning; only which report decides 0 vs 1 changes (`goga drift`), and facts areas never affect it.
- The drift comparison stays pure: filters scope only, and both amendment actions operate solely on the finished scoped report — they never feed back into the views or the comparison.
- Codegraph analysis boundaries stay fixed: supported languages, no environment reads, no project code execution; runs create or modify no files.
- The crash reason of the completion moment is credential-free — no tokens, keys, passwords, or other secrets; paths and tool names are permitted.
- Each domain owns its hooks surface (its hooks zone); the platform and other domains do not own it.
- Constraint of the closed report-entry shape (exactly kind/cell/types) is a hard validation — a malformed adjustment is a hard failure, not a sanitization.

## Scope Estimate

Single task. The two surfaces are one extension model delivered on one platform: the codegraph checkpoints fire inside every drift run's producer calls, the drift completion moment carries report stages of the same run, and the acceptance criteria (view symmetry, tool-adjustable gate) interlock across both domains. Decomposition by domain would cut through these connections. The scale — six actions, two zones, a handful of integrations — fits one prototype-and-build cycle; the `goga-prototype` pipeline distributes the work across cells.

## Existing Architecture

Affected cells and integration requirements (connections examined against the live schema):

- `goga/hooks/catalog` — six new action records (four hard: `codegraph.amend_node`, `codegraph.validate_graph`, `drift.amend_report`, `drift.amend_entry`; two soft: `drift.run_started`, `drift.run_completed`), plus the catalog CODEMANIFEST requirements describing each record's error-class semantics. The catalog is data only; the zones own delivery.
- New hooks zone of the codegraph domain (owned by the codegraph domain, mirroring `goga/schema/hooks`): imports the platform facade types from `goga/hooks` (`HookRegistry`, `build_hook_arguments`, `declared_actions`, `wrap_context`) and the practices `per-tool-delivery` / `registering-hooks`; owns the node facts read view, the delivered amendment view with its contribution buffer, the read-only tree view of the gate with its veto buffer, the committed-contribution records and the deterministic tools-area composition, and the checkpoint surface (one registry per run). The zone does not import the codegraph domain — views are built from the facts the caller passes.
- New hooks zone of the drift domain (owned by the drift domain, same platform imports): owns the start-moment facts (requested filters), the completion-moment facts (last computed report stage, finished/crashed outcome, credential-free reason), the report-amendment delivered view with its list control (mutual blindness, last-adjusting-wins), the entry-facts delivered view with its contribution buffer, and the checkpoint surface.
- `goga/codegraph` — the `codegraph` routine delivers the per-node amendment for every node surviving the filters, places the returned tools area on the node iff non-empty, and delivers the validation gate over the final read-only tree before returning; the veto raises one merged error (the caller maps it to exit 1). Fires identically inside drift producer calls.
- `goga/codegraph/facts` — the node record carries the committed tools overlay (empty when no tool contributed) so the output and the gate view share one record shape; node fields stay exactly cell, types, dependencies, children, plus tools.
- `goga/drift` — the `drift` routine wraps its pipeline with the start moment, delivers the report amendment over the finished scoped report, then the entry-facts amendment over every surviving entry of the settled list, and fires the completion moment on every terminal state — including propagated producer failures and hard amendment failures — with the last computed report stage and the outcome.
- `goga/commands/codegraph` — serializes the tools area (the key is written only when non-empty) and maps the gate veto to a clean stderr error with exit 1, nothing on stdout.
- `goga/commands/drift` — serializes the `tools` areas on report entries, decides exit 0/1 by the final entry list alone, maps hard amendment failures (and in-run codegraph vetoes) to exit 2 with nothing on stdout; soft moment failures surface as stderr warnings only.
- Documentation — `docs/features/codegraph/hooks.md` and `docs/features/drift/hooks.md` rewritten per the schema pattern (events table, contexts, subscribe, merge rules, integration scenarios, failure treatment, run output, API, fact records); the api and cli pages of both features (`docs/features/codegraph/api.md`, `docs/features/codegraph/cli.md`, `docs/features/drift/api.md`, `docs/features/drift/cli.md`) updated with the checkpoint flow, the `tools` output key, and the failure semantics per the schema precedent; catalog-level hooks documentation updated with the six addresses.
- `example/goga-tool-events` — the six new addresses added to the subscription list and the context read surface, keeping the package a complete observer of the catalog.
- Tests — mirroring the source structure per the project convention: zone unit tests, routine integration tests, CLI tests, and the no-subscription byte-identical invariant.

Cross-domain connections to respect: `goga/drift` imports `schema` and `codegraph` as view producers and `SchemaNode` from `goga/schema/hooks` as a read type — the drift zone adds its own surface without touching these; the codegraph checkpoints must not multiply the package enumeration (one registry per run shared with any other checkpoints of the same run).

## Notes

- The task is grounded in the topic's PRD (requirements 1–20) and ADR — the discovery stage closed the full decision tree, including the sixth action `drift.amend_entry`, the narrowed silence principle (an adjustment-provenance ban with `tools` facts areas as the contribution idiom), the strict entry shape, and the run ordering. Implementation stages must not drift from these decisions.
- The `tools` facts areas never affect the drift exit code and never signal provenance; the report stays silent about which tool adjusted it.
- The completion moment's payload on failure: the scoped pre-amendment report when a later stage failed, nothing when the run failed before the report was computed — the moment still fires with the crashed marker and the credential-free reason.
- No code examples are included in this task by stage constraint; the CODEMANIFEST-level contracts are designed in the downstream prototype/design stages.
