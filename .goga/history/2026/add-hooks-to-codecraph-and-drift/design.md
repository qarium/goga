# Design Document: `add-hooks-to-codecraph-and-drift`

Topic directory: `.goga/history/2026/add-hooks-to-codecraph-and-drift/`.
Base ref: `release/2.1.0` (per `.goga/config.yml`). All changes live in the working tree of branch `add-hooks-to-codecraph-and-drift`.

This document is the architectural specification derived from the CODEMANIFEST changes — what to implement and how. The implementation order stays with the planning stage. Language: Python (`goga-lang-disp` → `goga-cell-python`).

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST` — six new action records in `declared_actions` Requirements: `codegraph/amend_node` (hard), `codegraph/validate_graph` (hard), `drift/run_started` (soft), `drift/run_completed` (soft), `drift/amend_report` (hard), `drift/amend_entry` (hard).
- `goga/codegraph/facts/CODEMANIFEST` — `CodegraphNode` gains `tools: dict[str, dict[str, object]] = {}` (field, property, requirements).
- `goga/codegraph/hooks/CODEMANIFEST` — **new zone cell** (NodeFacts, Violation, GateVerdict, NodeAmendment, GraphValidation, ToolContribution, merge_node_contributions, CodegraphHooks).
- `goga/drift/hooks/CODEMANIFEST` — **new zone cell** (DriftFilters, EntryFacts, ReportEntry, RunOutcome, RunCompletion, ReportAmendment, EntryAmendment, ToolContribution, merge_entry_contributions, DriftHooks).
- `goga/codegraph/CODEMANIFEST` — Imports += zone entry (`CodegraphHooks`, `NodeFacts`, `GateVerdict`; usage `checkpoints`); global Annotations += checkpoints paragraph; `codegraph` routine rewritten to the checkpoint-aware 10-step algorithm; `render_graph` first Requirement updated.
- `goga/drift/CODEMANIFEST` — Imports += zone entry (`DriftHooks`, `DriftFilters`, `EntryFacts`, `ReportEntry`, `RunOutcome`, `RunCompletion`; usage `checkpoints`); global Annotations += checkpoints paragraph; `DriftEntry` gains `tools`; `drift` routine rewritten to the moments-and-amendments algorithm with failure paths.
- `goga/commands/codegraph/CODEMANIFEST` — Imports += `registering-hooks` (from `goga/codegraph`) and `checkpoints` (from `goga/codegraph/hooks`); Annotations += two paragraphs; routine algorithm/requirements extended (checkpoint failure semantics, conditional `tools` key, byte-identical invariant).
- `goga/commands/drift/CODEMANIFEST` — Imports += `registering-hooks` and `checkpoints`; Annotations += two paragraphs; routine algorithm/requirements extended (amendment failure semantics, conditional `tools` key, post-amendment grading).

### New Entities

- `NodeFacts` — code-derived facts of one node, the per-node read view (`goga/codegraph/hooks`, facts.py).
- `Violation` — one collected veto of the validation walk (`goga/codegraph/hooks`, facts.py).
- `GateVerdict` — collected verdict with `approved` (`goga/codegraph/hooks`, facts.py).
- `NodeAmendment` — read-and-contribute view per tool per node with `contribute(facts)` (`goga/codegraph/hooks`, amendments.py).
- `GraphValidation` — gate view per tool with `veto(reason)` (`goga/codegraph/hooks`, contexts.py).
- `ToolContribution` (codegraph) — committed contribution pairing (`goga/codegraph/hooks`, overlay.py).
- `merge_node_contributions` — deterministic tools-area composition (`goga/codegraph/hooks`, overlay.py).
- `CodegraphHooks` — checkpoint surface: `amend_node`, `validate_graph` (`goga/codegraph/hooks`, events.py).
- `DriftFilters` — start-moment facts (`goga/drift/hooks`, facts.py).
- `EntryFacts` — delivered read view of one report entry (`goga/drift/hooks`, facts.py).
- `ReportEntry` — completion-moment report entry projection (`goga/drift/hooks`, facts.py).
- `RunOutcome` — fixed value set `finished` / `crashed` (`goga/drift/hooks`, facts.py).
- `RunCompletion` — completion-moment facts (`goga/drift/hooks`, facts.py).
- `ReportAmendment` — read-and-adjust view per tool with `adjust(entries)` (`goga/drift/hooks`, amendments.py).
- `EntryAmendment` — read-and-contribute view per tool per entry with `contribute(facts)` (`goga/drift/hooks`, amendments.py).
- `ToolContribution` (drift) — committed contribution pairing (`goga/drift/hooks`, overlay.py).
- `merge_entry_contributions` — deterministic tools-area composition (`goga/drift/hooks`, overlay.py).
- `DriftHooks` — checkpoint surface: `emit_run_started`, `amend_report`, `amend_entry`, `emit_run_completed` (`goga/drift/hooks`, events.py).

### Changed Entities

- `declared_actions` — catalog extended by six records (28 → 34).
- `CodegraphNode` — new `tools` field (empty default; amendment checkpoint alone places non-empty overlays).
- `DriftEntry` — new `tools` field (empty default; entry-facts amendment alone places non-empty overlays).
- `codegraph` — checkpoint-aware assembly (amend surviving nodes, gate the final tree).
- `drift` — run wrapped by moments; scoped report passes through the two amendments; failure paths emit the completion moment and re-raise.
- CLI `codegraph` / CLI `drift` — extended error envelopes, conditional `tools` key in output, post-amendment grading (drift), help updates.

### Deleted Entities

None.

### Usages and Annotations Changes

- New usage files: `goga/codegraph/hooks/.usages/checkpoints.md`, `goga/drift/hooks/.usages/checkpoints.md`, `goga/codegraph/.usages/registering-hooks.md`, `goga/drift/.usages/registering-hooks.md`.
- Updated usage files: `goga/codegraph/.usages/codegraph-usage.md` (tools row, hook-extension bullet, checkpoint failure bullet), `goga/drift/.usages/drift-usage.md` (tools row, post-amendment paragraph, hook-extension bullet, checkpoint failure bullet), `goga/codegraph/facts/.usages/records.md` (tools in flow diagram and constraints — fixed during this design), `goga/commands/codegraph/.usages/codegraph.md` and `goga/commands/drift/.usages/drift.md` (conditional tools key, extended exit-code causes, post-amendment grading — fixed during this design).
- Annotation changes per manifest are listed under Changed CODEMANIFEST Files above.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga/drift/CODEMANIFEST` (Interface↔Type consistency): the `drift` routine constructs the outcome marker of the `RunCompletion` it emits, but `RunOutcome` was not imported from `goga/drift/hooks` — the implementation could not build the value and annotations could not reference it (build-domain precedent imports every zone type it constructs). Fix: `RunOutcome` added to the zone `Imports`; the routine's step 6 now reads "the `RunOutcome` finished marker" and every failure path reads "the `RunOutcome` crashed marker" (satisfies `import_is_used`). Validated: `goga lint` 0 errors; `goga schema` shows the import edge.

### Fixed `.usages/` Defects (outdated consumer documentation)

- `goga/codegraph/facts/.usages/records.md`: flow diagram now `CodegraphNode (cell, types, dependencies, children, tools)`; the constraint bullet no longer lists `tools` as manifest-only and states the overlay rule (empty unless the codegraph amendment checkpoint placed it); the composing example notes the omitted `tools` default.
- `goga/commands/codegraph/.usages/codegraph.md`: Output section — four base fields plus the conditional `tools` key (never an empty object); exit-1 causes extended with the amendment hard failure, the vetoed gate (merged error), and the register-facade import failure; byte-identical no-subscription statement.
- `goga/commands/drift/.usages/drift.md`: exit codes rephrased over the final post-amendment list; exit-2 causes extended with the drift amendment hard failures, the in-run codegraph veto / hard checkpoint failure, and the register-facade import failure; Output table gains the conditional `tools` row; post-amendment and no-provenance statements added.

All four fixes were approved by the user (design dialog q1: "apply all four").

## Entity Interaction and Data Flow

### Interaction Diagram

```
                          goga/hooks (platform facade)
   ┌──────────────────────────┼─────────────────────────────────────────┐
   │ HookRegistry.build_once() │ subscriptions_for(domain, action)      │
   │ self_context(tool)        │ wrap_context(view)                      │
   │ build_hook_arguments(...) │ emit_hook_event(registry, d, a, ctx)   │
   │ declared_actions()  (goga/hooks/catalog)                            │
   └──────────────────────────┬─────────────────────────────────────────┘
                              │ imported by both zones
      ┌───────────────────────┴───────────────────────┐
      │                                               │
goga/codegraph/hooks                          goga/drift/hooks
  CodegraphHooks                                DriftHooks
   ├─ amend_node(NodeFacts) -> tools             ├─ emit_run_started(DriftFilters)
   │    └─ NodeAmendment.contribute              ├─ amend_report([EntryFacts]) -> [EntryFacts]
   │       merge_node_contributions              │    └─ ReportAmendment.adjust
   └─ validate_graph(tree) -> GateVerdict        ├─ amend_entry(EntryFacts) -> tools
        └─ GraphValidation.veto                  │    └─ EntryAmendment.contribute
                                                │       merge_entry_contributions
      ▲ reads CodegraphNode                     └─ emit_run_completed(RunCompletion)
      │ (from goga/codegraph/facts)
      │
goga/codegraph (domain routine)                goga/drift (domain routine)
  codegraph(cells, max_depth, depends_on)        drift(cells, max_depth, depends_on)
   ├─ render_graph (filtered + complete)          ├─ schema() ×2  (declared view; fires schema checkpoints)
   ├─ per surviving node: amend_node              ├─ codegraph() ×2 (code view; fires codegraph checkpoints)
   ├─ rebuild tree with overlays                  ├─ compare_views + scope_entries
   └─ validate_graph → merged veto error          ├─ amend_report → settled list
      ▼                                           ├─ per entry: amend_entry → DriftEntry(tools)
      ▼                                           └─ emit_run_completed(finished)
goga/commands/codegraph                          ▼
  CLI: JSON tree, conditional tools key        goga/commands/drift
  exit 0 / 1                                     CLI: JSON report, conditional tools key
                                                 exit 0 / 1 / 2
```

### Data Flows

**Flow A — `goga codegraph` (and every codegraph producer call inside a drift run)**

1. CLI (click) parses `CELLS`, `--max-depth`, `--depends-on` → calls `codegraph(cells, max_depth, depends_on)`.
2. `load_project_config()` → `ProjectConfig` (`FileNotFoundError` = uninitialized project); language whitelist check (`ValueError`); `LintConfig.ignore` → `discover_sources` → `collect_facts` → `derive_units` → `resolve_links`.
3. `render_graph(units, links, cells, max_depth, depends_on)` → filtered tree (`list[CodegraphNode]`, `tools == {}` everywhere). When filters are active, a second `render_graph(units, links, [], None, [])` produces the complete tree.
4. Empty filtered tree → return `[]` before any checkpoint.
5. Pre-order walk of the filtered tree: per node build `NodeFacts` (own `cell`/`types`/`dependencies` + `children` cell paths from the matching complete node) → `CodegraphHooks.amend_node(node=facts)` → per-node tools mapping (empty iff nothing contributed).
6. Recursive rebuild of the filtered tree with the committed overlays (`dataclasses.replace`).
7. `CodegraphHooks.validate_graph(final_tree)` → `GateVerdict`; not approved → one merged `ValueError`; approved → return the final tree.
8. CLI projects nodes to JSON (conditional `tools` key) → `click.echo` → exit 0; any error → stderr + exit 1.

**Flow B — `goga drift`**

1. CLI parses filters → `drift(cells, max_depth, depends_on)`.
2. `DriftHooks.emit_run_started(DriftFilters(...))` — soft moment (hook failures warn).
3. Producer stage inside the failure wrap: `schema([], None, [])`, `codegraph([], None, [])`, `schema(cells, ...)`, `codegraph(cells, ...)` — the codegraph calls fire Flow A's checkpoints; the schema calls fire the schema checkpoints (existing behavior).
4. `compare_views(complete…)` → entries; `scope_entries(entries, filtered…)` → scoped report (all `DriftEntry.tools == {}`).
5. Projection to `EntryFacts` → `DriftHooks.amend_report(facts)` → settled list (last adjusting tool wins; hard failure on crash/malformed adjustment).
6. Per settled entry: `DriftHooks.amend_entry(facts)` → tools → final `DriftEntry` records.
7. `DriftHooks.emit_run_completed(RunCompletion(final projected to ReportEntry, RunOutcome.finished, ""))` → return the final report.
8. Any failure in steps 3–6: `emit_run_completed(RunCompletion(last computed stage, RunOutcome.crashed, credential-free reason))` then re-raise. CLI: error → stderr + exit 2; report printed → exit 1 iff the final list is non-empty, else exit 0.

### Entity Dependencies

Implementation order (leaves → root; matches the arch plan):

1. `goga/hooks/catalog` (data only; records must exist before zones resolve addresses)
2. `goga/codegraph/facts` (`CodegraphNode.tools` before the gate view delivers the record)
3. `goga/codegraph/hooks` (imports `goga/hooks` + `goga/codegraph/facts`)
4. `goga/drift/hooks` (imports `goga/hooks`)
5. `goga/codegraph` (imports its zone + facts + analysis + config)
6. `goga/drift` (imports its zone + `goga/schema` + `goga/codegraph` + facts)
7. `goga/commands/codegraph`
8. `goga/commands/drift`

No import cycles: zones never import their domains; `goga/codegraph/facts` imports nothing from the zones; the platform imports neither domains nor zones.

## Code Stack Trace

### Trace: `CodegraphHooks.amend_node`

#### Chain

1. **Input**: `node: NodeFacts` — operation data built by the calling walk (`goga/codegraph` routine step 8); pure resolved values, no reads.
2. `_ensure_registry()` → `HookRegistry().build_once()` on first checkpoint of the surface → checkpoint: enumeration runs once per surface; a broken package facade raises `ImportError` naming the package (the single fatal case; later surface instances re-enumerate — one registry per surface instance, per run).
3. Resolve `domain="codegraph", action="amend_node"` against `declared_actions()` → checkpoint: record exists (catalog fix #1); unknown address would be an emitting-side `ValueError` — unreachable once catalog and zone ship together.
4. `registry.subscriptions_for("codegraph", "amend_node")` grouped per tool, enumeration order preserved → `groups: dict[tool, list[Subscription]]`.
5. Per tool: fresh `NodeAmendment(node=_read_only_view(node))` — every list rebuilt so an in-place write stays local → checkpoint: mutual blindness holds (every tool reads the same code-derived values; the caller's `NodeFacts` is never shared). `wrap_context(amendment)` blocks attribute assignment; `build_hook_arguments(sub.hook, proxy, registry.self_context(tool))` projects only `context`/`self`; hook called.
6. A raising hook → hard failure: `ValueError("hook {sub.name} of tool {tool} failed on codegraph.amend_node at {node.cell}: {reason}")` → checkpoint: message names hook, tool, action, failing node cell path — matches the catalog record and the domain requirement; walk stops at first failure; the view (and its buffer) dies with the tool.
7. After the tool's hooks: merge buffered payloads key-wise with a strict `Mapping` guard (`dict.update` would silently coerce an iterable of pairs); `_check_json_map` on the merged buffer (non-mapping payload, non-string keys, non-JSON-serializable values, non-finite floats, empty mapping at any nesting level, circular references) → same hard failure naming tool/action/cell ("structurally malformed contribution ({detail})") → checkpoint: structural rule set identical to the schema zone precedent (`_commit_tool_buffer`).
8. Owned deep copy of the validated buffer (the ownership cut — a container the tool retains and mutates at a later node never reaches the committed area); empty merged buffer commits nothing.
9. `ToolContribution(tool, facts)` per committing tool → `merge_node_contributions(contributions)` → tools area (`{tool: facts}`, empty mappings skipped).
10. **Output**: `dict[str, dict[str, object]]` — `{}` when the address has no subscriptions or no tool packages are installed → checkpoint: the caller places no `tools` key; byte-identical output invariant holds.

#### Checkpoint Summary

- Registry single-build per surface: passed (pipeline/schema precedent `_ensure_registry`).
- Error naming (hook/tool/action/cell): passed — format mirrors `goga/schema/hooks/events.py`.
- Type flow: `NodeFacts` in, tools mapping out — matches the domain routine step 8 and `CodegraphNode.tools`.

### Trace: `CodegraphHooks.validate_graph`

#### Chain

1. **Input**: `tree: list[CodegraphNode]` — the final assembled tree, overlays included (the recorded exception to code-derived-facts-only delivery).
2. `_ensure_registry()` (shared with `amend_node` — one enumeration for both checkpoints of a run) → resolve `codegraph/validate_graph` against the catalog.
3. Per tool: fresh `GraphValidation(tree=_copy_tree(tree))` — every node rebuilt, overlay values deep-copied (`_copy_json`) → checkpoint: the caller's tree is never aliased; a write stays local to the tool's view.
4. Per hook: snapshot `view._veto` before the call; call the hook; a buffer change attributes the veto to that hook's subscription name; a raising hook records one crash violation `(sub.name, str(reason))` and stops that tool's remaining hooks → checkpoint: exactly one violation per tool; crash overrides the buffered veto.
5. Walk continues to the next tool whatever happened (walk-to-completion deviation) → checkpoint: "no early stop between tools" holds; a non-vetoing subscriber still runs after another tool vetoed.
6. `Violation(tool, hook, reason)` per vetoing/crashing tool → `GateVerdict(violations)`.
7. **Output**: `GateVerdict`; `approved` is `not violations` — acting on it (merged error, exit code) belongs to the domain routine.

#### Checkpoint Summary

- Fresh view per tool: passed. Attribution snapshot: passed (schema precedent mechanics).
- The gate modifies nothing: passed — delivery is read-only by construction.

### Trace: `DriftHooks.emit_run_started` / `emit_run_completed`

#### Chain

1. **Input**: `filters: DriftFilters` (the run's arguments verbatim) / `completion: RunCompletion` (last computed stage, outcome, reason).
2. `_ensure_registry()` → the platform `emit_hook_event(registry, "drift", "run_started" | "run_completed", context_for=…)`.
3. The delivered context wraps the facts: a private frozen record exposing `.filters` / `.completion` (see *Algorithm Design — DriftHooks*; the consumer doc `goga/drift/.usages/registering-hooks.md` commits to `context.filters` / `context.completion`) → checkpoint: wrapper attributes match the published consumer documentation; `context_for=lambda _tool: context` shares one instance (pipeline precedent — read-only facts, frozen records).
4. `emit_hook_event` resolves the address, wraps, projects, calls; both actions are **soft** → a failing hook logs `WARNING` ("hook {name} of tool {tool} failed on drift.{action}: {reason}") and the sequence continues → checkpoint: the moment never changes the report or the exit code; no raise path for hook failures.
5. **Output**: none. An address without subscriptions emits nothing.

#### Checkpoint Summary

- Soft semantics vs catalog records: passed (both `drift` moments are `soft`).
- No configuration/repository/file reads at the checkpoint: passed — contexts are built from caller values only.

### Trace: `DriftHooks.amend_report`

#### Chain

1. **Input**: `report: list[EntryFacts]` — the finished scoped report as computed by the comparison pipeline.
2. `_ensure_registry()`; resolve `drift/amend_report`.
3. `current = list(report)` — the working list; the input list is never mutated.
4. Per tool: fresh `ReportAmendment(report=[EntryFacts(…, fresh lists) …])` built from the **original** scoped entries — never from `current` → checkpoint: mutual blindness holds (the last adjusting tool wins *over the original*, not over an accumulating chain); fresh containers keep a tool's in-place list mutation local.
5. Per hook: snapshot `view._adjustment` (sentinel `None`) before the call; a change attributes the adjustment to that hook's subscription name; call the hook.
6. A raising hook → hard failure `ValueError("hook {sub.name} of tool {tool} failed on drift.amend_report: {reason}")` → checkpoint: names hook, tool, action, reason — matches the catalog record; walk stops; nothing is adopted.
7. After the tool's hooks: a buffered adjustment passes the closed-shape validation — `entries` is exactly a `list`; every entry a strict `Mapping`; keys ⊆ {kind, cell, types}; `kind` present and one of `schema_only` / `codegraph_only`; `cell` present and a non-empty `str`; `types` absent (cell-level) or a `list` of `str` (carried verbatim — never sanitized, an empty list included). Malformed → hard failure `ValueError("hook {attributed} of tool {tool} failed on drift.amend_report: malformed adjustment ({detail})")` → checkpoint: the error names the hook, tool, action, reason as the catalog requires; the adjustment is discarded, never coerced.
8. A validated adjustment replaces `current` whole: `current = [EntryFacts(kind=e["kind"], cell=e["cell"], types=list(e["types"]) if "types" in e else None) for e in entries]` — fresh owned records (the ownership cut over the tool's mappings).
9. **Output**: the settled `list[EntryFacts]`; an address without subscriptions returns the input values unchanged (fresh copies of the same values) → checkpoint: byte-identical behavior with no subscriptions.

#### Checkpoint Summary

- List-control semantics (whole replacement, last-wins, adjust-nothing = unchanged): passed.
- Closed shape enforced as hard failure: passed — no sanitation path exists.

### Trace: `DriftHooks.amend_entry`

Identical mechanics to `CodegraphHooks.amend_node` (steps 2, 4–10 of that trace) with: address `drift/amend_entry`, view `EntryAmendment(entry=EntryFacts copy)`, error subjects naming the failing entry — crash: `"hook {name} of tool {tool} failed on drift.amend_entry at {kind} {cell}: {reason}"`; structural: `"tool {tool} failed on drift.amend_entry at {kind} {cell}: structurally malformed contribution ({detail})"`; composition via `merge_entry_contributions`. Checkpoint: the failure names the tool, the action, and the failing entry (its kind and cell path) — matches catalog + domain contract.

### Trace: `codegraph` (domain routine)

#### Chain

1. **Input**: `(cells=[], max_depth=None, depends_on=[])` — from the CLI (`list(cells)`, `max_depth`, `list(depends_on)`) or from `drift` (`([], None, [])` complete and `(cells, max_depth, depends_on)` filtered).
2. Steps 1–5 unchanged (config → language whitelist → ignore → discovery → analysis stages) → checkpoint: existing behavior preserved; every existing error (`FileNotFoundError`, `ValueError`) still propagates unchanged.
3. `render_graph(units, links, cells, max_depth, depends_on)` → output tree. `filters_active = bool(cells) or max_depth is not None or bool(depends_on)`; when active, `complete = render_graph(units, links, [], None, [])` and `complete_index = {node.cell: node for node in _walk_nodes(complete)}`; when inactive the output tree is the complete tree → checkpoint: `render_graph` is pure/deterministic (existing contract), so the complete index equals the unfiltered assembly; a node's own `types`/`dependencies` are filter-independent (render builds nodes before filters) — only `children` differ.
4. `if not tree: return []` → checkpoint: an empty graph fires nothing — no `CodegraphHooks` delivery, no registry build, no package enumeration, no `ImportError` on an empty project.
5. `hooks = CodegraphHooks()` (cheap). Pre-order walk of the output tree; per node: `full = complete_index[node.cell]`; `facts = NodeFacts(cell=node.cell, types=node.types, dependencies=node.dependencies, children=[c.cell for c in full.children])`; `tools = hooks.amend_node(node=facts)`; `if tools: overlays[node.cell] = tools` → checkpoint: delivery is node-major, tree order; delivered facts identical in every run of the same code (children from the complete subtree may name pruned cells — verified against `NodeFacts.children` requirement).
6. `final = _apply_overlays(tree, overlays)` — recursive rebuild placing committed overlays (`dataclasses.replace(node, tools=overlays.get(node.cell, {}))`; default stays `{}`) → checkpoint: frozen records — rebuild, never mutation; children rebuilt recursively.
7. `verdict = hooks.validate_graph(final)`; `if not verdict.approved: raise ValueError("codegraph validation failed:\n" + "\n".join(f"- tool {v.tool} / hook {v.hook}: {v.reason}" for v in verdict.violations))` → checkpoint: one merged error listing every violation (tool, hook, reason); no tree is returned; message format mirrors the schema routine's gate error.
8. **Output**: `final: list[CodegraphNode]` — deterministic; with no subscriptions every `tools` is `{}` and the serialized output is byte-identical to the pre-extension run.

#### Checkpoint Summary

- Checkpoints fire wherever the routine runs (command + both drift producer calls): passed — delivery lives inside the routine, not the CLI.
- Hard failures propagate as errors naming tool/action/cell (amendment) and every violation (veto): passed.

### Trace: `drift` (domain routine)

#### Chain

1. **Input**: `(cells=[], max_depth=None, depends_on=[])`.
2. `hooks = DriftHooks()`; `hooks.emit_run_started(DriftFilters(cells=cells, max_depth=max_depth, depends_on=depends_on))` — the filters exactly as received → checkpoint: soft; fires before any producer; a register-facade `ImportError` here propagates (the run never started — no completion moment), surfacing as command exit 2.
3. Failure wrap begins. `carried: list[ReportEntry] | None = None` — the last computed report stage.
4. Producer + comparison stage: `schema([], None, [])`, `codegraph([], None, [])`, `schema(cells, max_depth, depends_on)`, `codegraph(cells, max_depth, depends_on)`, `compare_views(complete…)`, `scope_entries(entries, filtered…)` → `scoped: list[DriftEntry]` → checkpoint: any producer error (including an in-run codegraph veto or amendment hard failure) jumps to the failure path with `carried is None`; the schema/codegraph checkpoints of the producer calls are the existing platform behavior.
5. `carried = [ReportEntry(kind=e.kind, cell=e.cell, types=e.types, tools={}) for e in scoped]` (the scoped pre-amendment stage; empty tools — no facts areas were computed) → `settled = hooks.amend_report([EntryFacts(kind=e.kind, cell=e.cell, types=e.types) for e in scoped])` → checkpoint: amendment failure jumps to the failure path carrying the scoped pre-amendment stage.
6. `final: list[DriftEntry] = []`; per `facts` of `settled`: `tools = hooks.amend_entry(facts)`; `final.append(DriftEntry(kind=facts.kind, cell=facts.cell, types=facts.types, tools=tools))` → checkpoint: comparison-produced and tool-added entries alike are delivered; an empty settled list runs no delivery; an `amend_entry` hard failure jumps to the failure path still carrying the scoped pre-amendment stage (partial overlays are discarded — the run fails).
7. `hooks.emit_run_completed(RunCompletion(report=[ReportEntry(…, tools=e.tools) for e in final], outcome=RunOutcome.finished, reason=""))` → **Output**: `final` → checkpoint: the finished stage carries the facts areas; the grading list (what the caller counts) is the post-amendment list.
8. **Failure path** (`except Exception as reason:`): `hooks.emit_run_completed(RunCompletion(report=carried, outcome=RunOutcome.crashed, reason=str(reason)))`; `raise` → checkpoint: fires on producer, comparison, and amendment failures alike; `carried` is `None` / the scoped pre-amendment stage / — never a half-settled list; the moment never masks the failure (re-raise); `str(reason)` is credential-free by construction (the producers' clean-error convention — messages name files, cells, tools; never tokens or tracebacks).

#### Checkpoint Summary

- Fixed run ordering (start → producers/comparison/scoping → report amendment → entry amendment → completion): passed.
- Completion on every terminal state with the correct carried stage: passed (`None` before the report, scoped pre-amendment on later failures, final with tools on success).

### Trace: CLI `codegraph`

1. click surface unchanged (`CELLS` variadic, `--max-depth`, repeatable `--depends-on`).
2. `try: result = codegraph_logic(list(cells), max_depth, list(depends_on))` / `except Exception as e: click.echo(str(e), err=True); ctx.exit(1)` → checkpoint: covers `FileNotFoundError`, `ValueError` (language, unparseable file, amendment hard failure, merged veto error), `ImportError` (register facade) — every checkpoint failure is the command's ordinary error path; nothing on stdout; no raw traceback.
3. Serialization: `_project_node` (mirror of the schema command) — `cell`, `types`, `dependencies`, `children` always; `tools` **only when non-empty** → `json.dumps(..., indent=4, sort_keys=True, ensure_ascii=False)` per `beautiful_json` → checkpoint: the current `asdict`-based serialization would print `"tools": {}` on every node — **must be replaced** by the projection; empty objects can never appear (the JSON-map validation rejects empty mappings at any level, and the key is written only when non-empty).
4. Help: add the `tools` line and the checkpoint failure semantics, mirroring the schema command help.

### Trace: CLI `drift`

1. click surface unchanged.
2. `try: report = drift_logic(...)` / `except Exception as e: stderr; ctx.exit(2)` → checkpoint: extended error envelope (drift amendment hard failures naming hook/tool/action/reason; in-run codegraph veto / hard checkpoint failure; register-facade `ImportError`).
3. `_project_entry` gains the conditional `tools` key (iff `entry.tools` non-empty).
4. `click.echo(json…)`; `ctx.exit(1) if report else ctx.exit(0)` → checkpoint: the grading list is the returned post-amendment list — a tool-cleared report prints `[]` and exits 0; a tool-added entry prints and exits 1; facts areas never affect the grading.

## Algorithm Design

### `goga/hooks/catalog` — `declared_actions`

**Responsibility**: single source of known subscription addresses.

**Algorithm**: append six records to `_DECLARED_ACTIONS` (data, not discovery):

```
Action(domain="codegraph", name="amend_node",     error_class="hard")
Action(domain="codegraph", name="validate_graph", error_class="hard")
Action(domain="drift",     name="run_started",    error_class="soft")
Action(domain="drift",     name="run_completed",  error_class="soft")
Action(domain="drift",     name="amend_report",   error_class="hard")
Action(domain="drift",     name="amend_entry",    error_class="hard")
```

`declared_actions()` already sorts by `(domain, name)` per call. No other change.

**Errors**: none (data only). **Edge cases**: none.

### `goga/codegraph/facts` — `CodegraphNode`

**Responsibility**: one node of the output tree.

**Algorithm**: add the field `tools: dict[str, dict[str, object]] = field(default_factory=dict)` after `children`; document in the docstring Attributes; leave `__post_init__` as is (the committed overlays are owned deep copies from the delivery — no defensive copying, mirroring `SchemaNode`).

**Errors**: none. **Edge cases**: `{}` default — render and every pre-checkpoint consumer never populate it.

### `goga/codegraph/hooks` — zone package

**Files** (`location` values, all flat in the zone directory):

- `__init__.py` — facade; docstring "Hooks zone of the codegraph domain — the node-amendment and validation-gate checkpoint surface."; re-exports `NodeAmendment`, `GraphValidation`, `CodegraphHooks`, `NodeFacts`, `Violation`, `GateVerdict`, `ToolContribution`, `merge_node_contributions`; sorted `__all__`.
- `facts.py` — `NodeFacts` (frozen, kw_only; `__post_init__` copies `types`, `dependencies` (each value list), `children`), `Violation` (frozen, kw_only), `GateVerdict` (frozen, kw_only; `approved` property `not self.violations`). Mirror `goga/schema/hooks/facts.py` shapes.
- `amendments.py` — `NodeAmendment` (kw_only, **not frozen** — the buffer is delivery state): `node: NodeFacts`, `_pending: list = field(init=False, default_factory=list, repr=False)`, `contribute(facts)` appends verbatim.
- `contexts.py` — `GraphValidation` (kw_only): `tree: list[CodegraphNode]`, `_veto: str | None = field(init=False, default=None, repr=False)`, `veto(reason)` replaces `_veto` whole.
- `overlay.py` — `ToolContribution` (frozen, kw_only: `tool`, `facts`); `merge_node_contributions(contributions)` → `{c.tool: c.facts for c in contributions if c.facts}`.
- `events.py` — module-private helpers + `CodegraphHooks` (below).

**`CodegraphHooks` algorithm** (mirror of `SchemaHooks`, codegraph naming):

```
1. __init__: _registry = None                     # cheap construction
2. _ensure_registry(): build_once() on first use; reuse afterwards
3. amend_node(node):
     resolve codegraph/amend_node in declared_actions
     groups = subscriptions_for(...) grouped per tool (enumeration order)
     for tool, subs in groups:
         view = NodeAmendment(node=_read_only_view(node))   # fresh containers
         proxy = wrap_context(view)
         for sub in subs:
             try: sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))
             except Exception as reason:
                 raise ValueError(f"hook {sub.name} of tool {tool} failed on "
                                  f"codegraph.amend_node at {node.cell}: {reason}") from reason
         merged = _commit_tool_buffer(tool, node.cell, view._pending)
         if merged: contributions.append(ToolContribution(tool, merged))
     return merge_node_contributions(contributions)
4. validate_graph(tree):
     resolve codegraph/validate_graph
     for tool, subs in groups:
         view = GraphValidation(tree=_copy_tree(tree))      # fresh nodes + overlay copies
         attributed_hook = ""; crash = None
         for sub in subs:
             before = view._veto
             try: sub.hook(**build_hook_arguments(...))
             except Exception as reason: crash = (sub.name, str(reason)); break
             if view._veto != before: attributed_hook = sub.name
         if crash is not None:      violations.append(Violation(tool, crash[0], crash[1]))
         elif view._veto is not None: violations.append(Violation(tool, attributed_hook, view._veto))
     return GateVerdict(violations=violations)
```

Module-private helpers in `events.py` (schema-zone precedents): `_read_only_view(node: NodeFacts) -> NodeFacts`; `_copy_json(value)` (dicts/lists recursively, tuples → lists, scalars as-is); `_copy_tree(nodes)` (rebuilt `CodegraphNode`s incl. `tools` via `_copy_json`); `_nested_scope(value, where, ancestors)` (cycle guard); `_check_json_map(value, where, ancestors)` (JSON-map shape: non-empty mappings, string keys, serializable scalars, finite floats, no cycles); `_commit_tool_buffer(tool, cell_path, pending)` (strict `Mapping` guard → key-wise merge → shape check → `copy.deepcopy` ownership cut; `ValueError` → "tool {tool} failed on codegraph.amend_node at {cell_path}: structurally malformed contribution ({reason})").

**Errors**: `ValueError` (hard failures, unknown address — the latter unreachable in practice); `ImportError` propagates from `build_once` (names the package).

**Edge cases**: address without subscriptions → `{}` / approved verdict; no tool packages installed → same; empty contribution buffers commit nothing silently.

### `goga/drift/hooks` — zone package

**Files**:

- `__init__.py` — facade; re-exports `DriftFilters`, `DriftHooks`, `EntryAmendment`, `EntryFacts`, `ReportAmendment`, `ReportEntry`, `RunCompletion`, `RunOutcome`, `ToolContribution`, `merge_entry_contributions`; sorted `__all__`.
- `facts.py` — `DriftFilters` (frozen, kw_only; copies `cells`, `depends_on`), `EntryFacts` (frozen; copies `types`), `ReportEntry` (frozen; copies `types`; `tools` default `{}`), `RunOutcome(Enum)` with members `finished = "finished"`, `crashed = "crashed"` (precedent: `goga/usages/hooks/facts.py::SyncOutcome`), `RunCompletion` (frozen; `report: list[ReportEntry] | None`, `outcome: RunOutcome`, `reason: str`).
- `amendments.py` — `ReportAmendment` (kw_only): `report: list[EntryFacts]`, `_adjustment: list | None = field(init=False, default=None, repr=False)`, `adjust(entries)` buffers the replacement verbatim (later call replaces the earlier). `EntryAmendment` (kw_only): `entry: EntryFacts`, `_pending`, `contribute(facts)`.
- `overlay.py` — `ToolContribution`, `merge_entry_contributions` (same composition as the codegraph zone).
- `events.py` — module-private delivery helpers + `DriftHooks` (below).

**`DriftHooks` algorithm**:

```
1. __init__: _registry = None
2. _ensure_registry(): build_once() on first use; reuse across moments and amendments
3. emit_run_started(filters):
     context = _RunStarted(filters=filters)          # private frozen wrapper
     emit_hook_event(registry, "drift", "run_started", context_for=lambda _tool: context)
4. amend_report(report):
     resolve drift/amend_report; groups per tool
     current = [EntryFacts copy for e in report]     # working list; input never mutated
     for tool, subs in groups:
         view = ReportAmendment(report=[fresh EntryFacts copies of the ORIGINAL report])
         proxy = wrap_context(view); attributed = ""
         for sub in subs:
             before = view._adjustment
             try: call hook
             except Exception as reason:
                 raise ValueError(f"hook {sub.name} of tool {tool} failed on "
                                  f"drift.amend_report: {reason}") from reason
             if view._adjustment is not before: attributed = sub.name
         if view._adjustment is not None:
             entries = _validate_adjustment(view._adjustment)   # closed shape or hard failure
             current = [EntryFacts(kind=e["kind"], cell=e["cell"],
                                   types=list(e["types"]) if "types" in e else None)
                        for e in entries]
     return current
5. amend_entry(entry): per-tool walk identical to amend_node with
   drift.amend_entry addressing and "at {entry.kind} {entry.cell}" subjects;
   compose via merge_entry_contributions
6. emit_run_completed(completion):
     context = _RunCompleted(completion=completion)  # private frozen wrapper
     emit_hook_event(registry, "drift", "run_completed", context_for=lambda _tool: context)
```

`_validate_adjustment(entries)` — the closed-shape check (hard failure `ValueError(f"hook {attributed} of tool {tool} failed on drift.amend_report: malformed adjustment ({detail})")`):

```
- entries must be exactly a list                     (a tuple/str/None is malformed)
- each entry must be a strict Mapping                (not an iterable of pairs)
- keys ⊆ {kind, cell, types}
- kind present, one of "schema_only" / "codegraph_only"
- cell  present, a str, non-empty as given — no sanitation (a whitespace-only
  cell is carried verbatim like a whitespace veto reason)
- types absent, or a list whose every element is a str (an empty list is carried
  verbatim — the contract admits "a list of strings"; never sanitized)
```

The two private wrapper records (delivery shape, not contract surface — the consumer doc commits to the attributes):

```python
@dataclass(frozen=True, kw_only=True)
class _RunStarted:
    filters: DriftFilters

@dataclass(frozen=True, kw_only=True)
class _RunCompleted:
    completion: RunCompletion
```

**Errors**: `ValueError` for the two hard amendments (naming hook/tool/action/subject/reason); soft moments only warn (platform `emit_hook_event`); `ImportError` from `build_once`.

**Edge cases**: empty scoped list still passes through `amend_report` (a tool may add entries to an otherwise clean report); empty settled list fires no `amend_entry`; `adjust([])` clears the report; adjust-nothing leaves the list unchanged; `RunCompletion.report is None` on early failures.

### `goga/codegraph` — routine rewrite

```
def codegraph(cells, max_depth, depends_on):
    config → language → ignore → files → facts → units → links      # unchanged steps 1-5
    tree = render_graph(units, links, cells, max_depth, depends_on)
    filters_active = bool(cells) or max_depth is not None or bool(depends_on)
    complete_index = ({n.cell: n for n in _walk_nodes(render_graph(units, links, [], None, []))}
                      if filters_active else
                      {n.cell: n for n in _walk_nodes(tree)})
    if not tree:
        return []                                                   # before any checkpoint
    hooks = CodegraphHooks()
    overlays: dict[str, dict] = {}
    for node in _walk_nodes(tree):                                  # pre-order, tree order
        full = complete_index[node.cell]
        facts = NodeFacts(cell=node.cell, types=node.types,
                          dependencies=node.dependencies,
                          children=[c.cell for c in full.children])
        tools = hooks.amend_node(node=facts)
        if tools:
            overlays[node.cell] = tools
    final = _apply_overlays(tree, overlays)                         # recursive replace
    verdict = hooks.validate_graph(final)
    if not verdict.approved:
        details = "\n".join(f"- tool {v.tool} / hook {v.hook}: {v.reason}" for v in verdict.violations)
        raise ValueError(f"codegraph validation failed:\n{details}")
    return final

def _apply_overlays(nodes, overlays):
    return [dataclasses.replace(n, tools=overlays.get(n.cell, {}),
                                children=_apply_overlays(n.children, overlays))
            for n in nodes]
```

`_walk_nodes` (pre-order generator) mirrors `goga/schema/schema.py::_walk_nodes`. Docstring Raises gains: checkpoint hard failures (naming tool/action/cell), the merged veto error, and the register-facade `ImportError`.

### `goga/drift` — routine rewrite

```
def drift(cells, max_depth, depends_on):
    hooks = DriftHooks()
    hooks.emit_run_started(DriftFilters(cells=cells, max_depth=max_depth, depends_on=depends_on))
    carried: list[ReportEntry] | None = None
    try:
        complete_schema = schema([], None, [])
        complete_codegraph = codegraph([], None, [])
        filtered_schema = schema(cells, max_depth, depends_on)
        filtered_codegraph = codegraph(cells, max_depth, depends_on)
        entries = compare_views(complete_schema, complete_codegraph)
        scoped = scope_entries(entries, filtered_schema, filtered_codegraph)
        carried = [ReportEntry(kind=e.kind, cell=e.cell, types=e.types, tools={}) for e in scoped]
        settled = hooks.amend_report([EntryFacts(kind=e.kind, cell=e.cell, types=e.types) for e in scoped])
        final: list[DriftEntry] = []
        for facts in settled:
            tools = hooks.amend_entry(facts)
            final.append(DriftEntry(kind=facts.kind, cell=facts.cell, types=facts.types, tools=tools))
        carried = [ReportEntry(kind=e.kind, cell=e.cell, types=e.types, tools=e.tools) for e in final]
        hooks.emit_run_completed(RunCompletion(report=carried, outcome=RunOutcome.finished, reason=""))
        return final
    except Exception as reason:
        hooks.emit_run_completed(RunCompletion(report=carried, outcome=RunOutcome.crashed, reason=str(reason)))
        raise
```

Docstring Raises gains: drift amendment hard failures, in-run codegraph veto / hard checkpoint failures, register-facade `ImportError`; Returns documents the post-amendment list.

### `goga/commands/codegraph` — projection + help

```python
def _project_node(node: CodegraphNode) -> dict:
    projected = {
        "cell": node.cell,
        "types": list(node.types),
        "dependencies": {path: list(types) for path, types in node.dependencies.items()},
        "children": [_project_node(child) for child in node.children],
    }
    if node.tools:
        projected["tools"] = node.tools
    return projected
```

Replace `asdict` serialization with `json.dumps([_project_node(n) for n in result], indent=4, sort_keys=True, ensure_ascii=False)`. Help (schema-command mirror): add `tools - tool contributions of the node-amendment checkpoint, present iff at least one tool wrote at least one fact` and a failure note ("a failing or vetoing hook stops the run as a clean error before any output").

### `goga/commands/drift` — projection + grading + help

`_project_entry` gains `if entry.tools: projected["tools"] = entry.tools`. Grading stays `ctx.exit(1) if report else ctx.exit(0)` — the returned list is already post-amendment. Help: add the `tools` line ("present iff at least one tool contributed; never affects the exit code") and the amendment failure note under exit 2.

## Cross-cutting Concerns

- **Error handling**: hard actions stop at the first failure inside a tool with a clean `ValueError` naming the hook (where attributable), the tool, the action, the subject (node cell path / entry kind+cell), and the reason — never a raw traceback (`str(reason)`, `from reason`). The validation gates run to completion and raise **one merged error** listing every violation. Soft moments only warn. `ImportError` from `build_once` is the single fatal platform case (names the package). Domain routines re-raise producer errors unchanged (drift emits the completion moment first). Commands catch `Exception` → stderr message + exit 1 (codegraph) / exit 2 (drift); stdout stays empty on failure; no partial output.
- **Logging**: soft-action hook failures — platform `logger.warning("hook %s of tool %s failed on %s.%s: %s", …)` (stderr-visible, never stdout). No other new logging; the zones never print (`Constraints: Do not print — the caller owns all output`).
- **Validation**: (a) contribution buffers — strict `Mapping` guard, key-wise merge, JSON-map shape (non-empty mappings, string keys, serializable scalars, finite floats, cycle guard), ownership deep copy; (b) report adjustments — the closed kind/cell/types shape, hard failure, never sanitized; (c) address resolution against `declared_actions` at every checkpoint. Validation lives at the tool commit point, not in the merge routines.
- **Caching**: one `HookRegistry` per surface instance, built lazily on the first checkpoint (`build_once`) — the moments and amendments of one `DriftHooks` share one enumeration; `CodegraphHooks.amend_node` + `validate_graph` share one. Each `schema()`/`codegraph()` call inside a drift run builds its own surface (established producer semantics — "the checkpoints fire wherever the routine runs").
- **Concurrency**: single-threaded sequential walks; no thread-safety requirements. Determinism: enumeration order everywhere; node-major pre-order delivery; identical inputs → identical outputs.
- **Credential hygiene**: `RunCompletion.reason` reuses the propagated error's message — producer errors are clean by construction (files, cells, tool names; no tokens/keys/passwords); no raw tracebacks cross the boundary.

## Usages Analysis

### `convention` (project-level, `.goga/usages/conventions.md`)
- **What it provides**: Python engineering rules — relative imports, `kw_only` dataclasses with empty defaults, Google docstrings, logging levels, test structure (`tests/` mirrors source; fixtures in `conftest.py`; `test_<what>_<scenario>` naming), CLI docstring rules (Click help), validation commands.
- **Where used**: every changed cell (global Annotations) and every entity ("Apply the `convention` practice…").
- **Why chosen**: project-wide mandate.
- **How exactly**: frozen `kw_only=True` dataclasses for facts; mutable kw_only dataclasses for amendment views; `Enum` for `RunOutcome`; module `logger = logging.getLogger(__name__)`; relative intra-package imports (`from ...hooks import …` in the zones); Google docstrings with Args/Returns/Raises; command docstrings as Click help with `\b` blocks.

### `per-tool-delivery` (imported from `goga/hooks`)
- **What it provides**: the staged delivery loop when the domain must know each tool's outcome — registry primitives (`subscriptions_for`, `self_context`), per-tool grouping, commit-after-success, error-class handling.
- **Where used**: `CodegraphHooks.amend_node` / `validate_graph`; `DriftHooks.amend_report` / `amend_entry` (all four annotated "Use the `per-tool-delivery` practice for the delivery loop").
- **Why chosen**: amendments commit per tool only after every hook of the tool succeeds — unreachable through plain `emit_hook_event`.
- **How exactly**: group subscriptions per tool in enumeration order; fresh view per tool; `wrap_context` + `build_hook_arguments` projection; hard failure stops the walk (amendments) / walk-to-completion collects violations (`validate_graph` — the recorded refinement); commit via `ToolContribution` + merge.

### `registering-hooks` (imported from `goga/hooks`; re-authored per domain)
- **What it provides**: the tool-package author surface — `register_hooks(hooks)` facade callback, `hooks.subscribe(domain, action, name, hook)`, hook signature (`context`, `self`), failure behavior.
- **Where used**: referenced by both zones (hook signature, failure handling) and both domains' consumer docs (`goga/codegraph/.usages/registering-hooks.md`, `goga/drift/.usages/registering-hooks.md` — imported by the command cells).
- **Why chosen**: the single authoring contract for `goga_tool_*` packages.
- **How exactly**: hooks declare only `context`/`self`; the identity is assigned by the platform; the domain-scoped re-authored docs list the events table, the views, merge rules, failure treatment, and integration scenarios.

### `declaring-actions` (imported from `goga/hooks`, drift zone only)
- **What it provides**: how a domain opens an action — catalog record, context contract, `emit_hook_event` at the checkpoint.
- **Where used**: `DriftHooks.emit_run_started` / `emit_run_completed`.
- **Why chosen**: the moments are fire-and-forget — the plain emission is the right primitive.
- **How exactly**: `emit_hook_event(self._ensure_registry(), "drift", "<action>", context_for=lambda _tool: context)`.

### `checkpoints` (zone-level, exported by both zones; imported by the domains and commands)
- **What it provides**: the consumer-side delivery recipes — build facts, call the zone entry, place the returned area iff non-empty, gate before return, moments/failure-path wrapping, the output shape (`tools -> {tool -> {fact -> value}}`).
- **Where used**: `goga/codegraph` (routine steps), `goga/drift` (routine steps + failure paths), `goga/commands/codegraph`, `goga/commands/drift` (failure handling).
- **Why chosen**: one document per domain tying the checkpoint surface to every entry path.
- **How exactly**: the code snippets in `goga/codegraph/hooks/.usages/checkpoints.md` and `goga/drift/hooks/.usages/checkpoints.md` are the reference implementations of the domain routines' steps.

### `codegraph-usage` / `drift-usage` (imported by the commands and the drift domain)
- **What they provide**: the output and failure contract behind each command — node/entry shapes with the conditional `tools` row, hook-extension guarantees, failure causes.
- **Where used**: `goga/commands/codegraph`, `goga/commands/drift` (annotations), `goga/drift` (codegraph-usage for the producer contract).
- **Why chosen / how**: the family usage docs — the updated rows and bullets are normative for the CLI projections and exit codes.

### Imported Usages (traceable cross-cell links)
- `per-tool-delivery`, `registering-hooks`, `declaring-actions` from `goga/hooks` — platform delivery and authoring contracts (paths `goga/hooks/.usages/*.md`).
- `checkpoints` from `goga/codegraph/hooks` and `goga/drift/hooks` — domain-side checkpoint recipes (paths `{zone}/.usages/checkpoints.md`).
- `codegraph-usage`, `registering-hooks` from `goga/codegraph`; `drift-usage`, `registering-hooks` from `goga/drift`; `checkpoints` from both zones — command-side links.
- `records` from `goga/codegraph/facts`, `stages` from `goga/codegraph/analysis`, `project-configuration` from `goga/config`, `schema-usage` from `goga/schema` — unchanged links consumed by the domain routines.

## `.usages/` Update

### Cell: `goga/hooks/catalog`
No `.usages/` directory — nothing to update.

### Cell: `goga/codegraph/facts`
- **`records`** → `goga/codegraph/facts/.usages/records.md` — Status: **current** (fixed in this design: `tools` in the flow diagram, the overlay constraint bullet, the example comment).

### Cell: `goga/codegraph/hooks`
- **`checkpoints`** → `goga/codegraph/hooks/.usages/checkpoints.md` — Status: current (new; matches the CODEMANIFEST surface and delivery rules).

### Cell: `goga/drift/hooks`
- **`checkpoints`** → `goga/drift/hooks/.usages/checkpoints.md` — Status: current (new; matches the moments/amendments contracts, including the failure-path wrap).

### Cell: `goga/codegraph`
- **`codegraph-usage`** → current (tools row, hook-extension and checkpoint-failure bullets applied by the apply stage).
- **`registering-hooks`** → current (new; events table, views, merge rules, failure treatment, drift symmetry scenario).

### Cell: `goga/drift`
- **`drift-usage`** → current (tools row, post-amendment paragraph, hook-extension and checkpoint-failure bullets).
- **`registering-hooks`** → current (new; four-action table, moment/report/entry views, failure treatment, integration scenarios).

### Cell: `goga/commands/codegraph`
- **`codegraph`** → `goga/commands/codegraph/.usages/codegraph.md` — Status: **current** (fixed in this design: conditional `tools` key, extended exit-1 causes, byte-identical statement).

### Cell: `goga/commands/drift`
- **`drift`** → `goga/commands/drift/.usages/drift.md` — Status: **current** (fixed in this design: post-amendment exit codes, extended exit-2 causes, `tools` row, no-provenance statement).

No cell points `Usages` at its own `.usages/` files (consumer documentation, not contractual requirements) — verified for every affected cell.

## Test Stack Trace

### General Setup

- Shared boundary fixtures (`tests/conftest.py`): `pin_package_environment(mapping)` — pins `packages_distributions()` (module name → distributions); `install_tool_package(module_name, register_hooks)` — installs a fake `goga_tool_*` into `sys.modules` (undone on teardown). Autouse `_isolate_cwd` / `_isolate_home` pin the process to `tmp_path`.
- Zone conftests re-export the two boundary fixtures (pattern of `tests/schema/hooks/conftest.py`); domain/CLI suites that plant projects pin the environment empty autouse (pattern of `tests/drift/conftest.py`) unless a test installs a tool.
- Tool identity derivation: package `goga_tool_docs` → tool `docs`; `goga_tool_gate` → `gate`; `goga_tool_baseline` → `baseline`.
- Planted projects (reuse `tests/drift/conftest.py` helpers): `_write_config`, `_write_package`, `_write_codemanifest`, `_plant_four_kinds` (lib declared+coded; mix with a stale declared type and an undeclared helper; extra code-only; ghost manifest-only), `_plant_healthy_plus`, `_plant_nested_depth`.

### Source File Registry

Files under test (new suites mirror the source layout per `convention`):

- `goga/hooks/catalog/catalog.py` → `tests/hooks/catalog/test_catalog.py` (extend)
- `goga/codegraph/facts/facts.py` → `tests/codegraph/facts/` (extend)
- `goga/codegraph/hooks/{__init__,facts,amendments,contexts,overlay,events}.py` → `tests/codegraph/hooks/` (new package: `conftest.py`, `test_facts.py`, `test_amendments.py`, `test_contexts.py`, `test_overlay.py`, `test_events.py`, `test_facade.py`)
- `goga/drift/hooks/{__init__,facts,amendments,overlay,events}.py` → `tests/drift/hooks/` (new package: `conftest.py`, `test_facts.py`, `test_amendments.py`, `test_overlay.py`, `test_events.py`, `test_facade.py`)
- `goga/codegraph/codegraph.py` → `tests/codegraph/test_codegraph.py` (extend)
- `goga/drift/{compare,drift}.py` → `tests/drift/` (extend)
- `goga/commands/codegraph/codegraph.py` → `tests/commands/codegraph/` (extend)
- `goga/commands/drift/drift.py` → `tests/commands/drift/` (extend)

---

### Positive Tests

#### `test_declared_actions_carries_the_codegraph_and_drift_records`

**Setup**: none (pure data call).

**Input**: `declared_actions()`.

**Trace**:
```
declared_actions()
  → sorted(_DECLARED_ACTIONS, key=(domain, name))
    returns: 34 records
  → {(a.domain, a.name): a.error_class for a in actions}
```

**Assertions**:
```
("codegraph", "amend_node")     == "hard"
("codegraph", "validate_graph") == "hard"
("drift", "run_started")        == "soft"
("drift", "run_completed")      == "soft"
("drift", "amend_report")       == "hard"
("drift", "amend_entry")        == "hard"
len(actions) == 34; the (domain, name) pairs are unique
```

**Sufficiency**: the zones resolve their addresses against the catalog at every checkpoint — a missing or mis-classed record breaks delivery (unknown address / wrong error semantics).

---

#### `test_amend_node_commits_buffered_facts`

**Setup**: `pin_package_environment({"goga_tool_docs": ["docs-dist"]})`; a hook subscribing `("codegraph", "amend_node", "cover", cover)` where `cover(context)` calls `context.contribute({"coverage": 3})`.

**Input**: `CodegraphHooks().amend_node(node=_node_facts())` where `_node_facts()` builds `NodeFacts(cell="goga/config", types=["ProjectConfig"], dependencies={}, children=["goga/config/hooks"])`.

**Trace**:
```
amend_node(node=facts)
  → _ensure_registry() → build_once() enumerates [goga_tool_docs]
  → subscriptions_for("codegraph", "amend_node") → [Subscription(tool="docs", name="cover")]
  → groups {"docs": [sub]}
  → view = NodeAmendment(node=_read_only_view(facts)); proxy = wrap_context(view)
  → sub.hook(context=proxy) → contribute({"coverage": 3}) → view._pending == [{"coverage": 3}]
  → _commit_tool_buffer("docs", "goga/config", pending)
      merged = {"coverage": 3}; _check_json_map passes; deepcopy
  → contributions [ToolContribution(tool="docs", facts={"coverage": 3})]
  → merge_node_contributions → {"docs": {"coverage": 3}}
```

**Assertions**: result `== {"docs": {"coverage": 3}}`.

**Sufficiency**: the core contribution pipeline — buffer, merge, commit, compose — under the real platform boundary.

---

#### `test_amend_node_empty_contribute_commits_nothing`

**Setup**: one tool whose hook calls `context.contribute({})`.

**Input**: `amend_node(node=_node_facts())`.

**Trace**: buffer `[{}]` → merged `{}` → commits nothing → `merge_node_contributions([])` → `{}`.

**Assertions**: result `== {}`; the delivered view's `_pending == [{}]` (buffered, merged to nothing).

**Sufficiency**: the "tools key exists iff at least one fact was written" invariant — the byte-identical output guarantee rests on it.

---

#### `test_contribute_merges_key_wise_later_wins`

**Setup**: one tool whose hook calls `context.contribute({"coverage": 3, "owner": "a"})` then `context.contribute({"coverage": 9})` (one hook, two calls).

**Input**: `amend_node(node=_node_facts())`.

**Trace**: buffer `[{"coverage": 3, "owner": "a"}, {"coverage": 9}]` → key-wise merge → `{"coverage": 9, "owner": "a"}` (the later write replaces the earlier one on key conflict) → validated → committed.

**Assertions**: result `== {"docs": {"coverage": 9, "owner": "a"}}`.

**Sufficiency**: the `contribute` merge rule — a regression that appends or nests payloads instead of merging key-wise fails here (schema precedent: `test_contribute_merges_key_wise_later_wins`).

---

#### `test_amend_node_builds_registry_once_per_run`

**Setup**: `boundary = pin_package_environment({"goga_tool_docs": ["docs-dist"]})`; the tool subscribes to both `amend_node` and `validate_graph`; a counter hook.

**Input**: `hooks = CodegraphHooks()`; `hooks.amend_node(n1)`; `hooks.validate_graph([node])`.

**Trace**: first checkpoint runs `build_once` (boundary called once); the second reuses `_registry`.

**Assertions**: `boundary.call_count == 1`; both checkpoints delivered.

**Sufficiency**: "One `HookRegistry` per run carries every checkpoint" — the enumeration (and its `ImportError` surface) must not multiply per checkpoint.

---

#### `test_amend_node_committed_area_is_owned`

**Setup**: `pin_package_environment({"goga_tool_docs": ["docs-dist"]})`; the hook stashes its contribution dict on `self.sink`, calls `context.contribute(self.sink)` with `{"coverage": 3}`, and mutates `self.sink["coverage"] = 99` in place before every later contribute.

**Input**: `hooks = CodegraphHooks()`; `t1 = hooks.amend_node(node=_node_facts(cell="a"))`; `t2 = hooks.amend_node(node=_node_facts(cell="b"))`.

**Trace**: node a: buffer `[sink]` → merged `{"coverage": 3}` → validated → owned deep copy commits `{"docs": {"coverage": 3}}`; between nodes the hook mutates `sink`; node b: the mutated mapping contributes → commits `{"docs": {"coverage": 99}}`.

**Assertions**: `t1 == {"docs": {"coverage": 3}}` and still `== {"docs": {"coverage": 3}}` after the second node (never 99); `t2 == {"docs": {"coverage": 99}}`.

**Sufficiency**: the ownership cut of `_commit_tool_buffer` — a container the tool retains and mutates at a later node never reaches an already-committed area; prevents a regression that drops the deep copy (same mechanics for the drift zone's `amend_entry`).

---

#### `test_validate_graph_collects_one_violation_per_tool_and_walks_to_completion`

**Setup**: two tools — `goga_tool_gate` vetoes (`context.veto("broken")`), `goga_tool_docs` only records `len(context.tree)`; subscriptions in that enumeration order.

**Input**: `verdict = CodegraphHooks().validate_graph([_final_node()])` (a `CodegraphNode` with `tools={"docs": {"a": 1}}`).

**Trace**:
```
validate_graph(tree)
  → tool "gate": view = GraphValidation(_copy_tree(tree)); hook vetoes → _veto = "broken"
  → tool "docs": hook runs (no early stop) → records tree length 1
  → violations [Violation("gate", "vetoer", "broken")]
  → GateVerdict(violations=[…])
```

**Assertions**: `verdict.approved is False`; `[(v.tool, v.reason) for v in verdict.violations] == [("gate", "broken")]`; the docs hook ran (its recording list is non-empty); the caller's `tree` objects are untouched (ids unchanged where nothing rebuilt).

**Sufficiency**: the walk-to-completion deviation — every subscribed tool runs, exactly one violation per tool.

---

#### `test_validate_graph_crash_overrides_veto_and_continues`

**Setup**: tool A's hook vetoes then a second hook of the same tool raises `RuntimeError("boom")`; tool B observes.

**Input**: `validate_graph(tree)`.

**Trace**: tool A: first hook sets `_veto`; second hook raises → `crash = (name, "boom")`, tool A's remaining hooks stop; tool B still runs → one violation for A with the crash reason.

**Assertions**: `verdict.violations[0].reason == "boom"`; `"Traceback" not in verdict.violations[0].reason`; B's hook ran.

**Sufficiency**: the crash-overrides-veto rule and the never-a-raw-traceback rule.

---

#### `test_validate_graph_delivers_fresh_tree_copy_per_tool`

**Setup**: two tools; the first hook of tool A appends `"X"` to `context.tree[0].types` in place (the delivered view is a fresh copy, so the write stays local to A's view); tool B records `list(context.tree[0].types)`.

**Input**: `validate_graph([_final_node(types=["Thing"])])`.

**Trace**: tool A: view = `_copy_tree(tree)` → in-place write lands on the copy; tool B: another fresh copy → records the untouched `["Thing"]`; no veto → approved.

**Assertions**: the recorded list `== ["Thing"]`; the caller's `tree[0].types == ["Thing"]`; `verdict.approved is True`.

**Sufficiency**: the fresh-tree-per-tool isolation of the gate — an in-place write never reaches another tool's view or the caller's tree (schema precedent: `test_validate_schema_delivers_fresh_tree_copy_per_tool`).

---

#### `test_emit_run_started_is_soft_and_delivers_the_filters`

**Setup**: `pin_package_environment({"goga_tool_watch": ["watch-dist"]})`; two hooks in one tool — the first records `(context.filters.cells, context.filters.max_depth)` to a recorder, the second raises `RuntimeError("nope")`.

**Input**: `DriftHooks().emit_run_started(DriftFilters(cells=["goga/config"], max_depth=2, depends_on=[]))`.

**Trace**: `emit_hook_event(registry, "drift", "run_started", …)` — the failing hook hits the soft branch → `logger.warning("hook … failed on drift.run_started: nope")`; the sequence continues; no exception.

**Assertions**: no raise (`emit_run_started` returns `None`); recorder `== (["goga/config"], 2)`; `caplog` contains the warning (level WARNING, names tool and action).

**Sufficiency**: the moments never change the run — a failing observer is a warning only; the delivered view exposes `.filters` per the consumer doc.

---

#### `test_amend_report_last_adjusting_tool_wins_and_tools_are_blind`

**Setup**: environment with two tools (enumeration order: `goga_tool_alpha`, `goga_tool_beta`); alpha adjusts `[{"kind": "schema_only", "cell": "a"}]`; beta reads `context.report` into a recorder and adjusts nothing.

**Input**: `amend_report([EntryFacts(kind="codegraph_only", cell="z", types=None)])`.

**Trace**: alpha's view over the original list → adjustment validated → `current` replaced; beta's view over the **original** list (recorder sees `z`, never `a`) → no adjustment → `current` unchanged by beta.

**Assertions**: settled `== [EntryFacts(kind="schema_only", cell="a", types=None)]`; recorder saw the original entry only.

**Sufficiency**: list-control semantics — whole replacement, last-wins, mutual blindness over the finished scoped report.

---

#### `test_amend_report_two_adjusting_tools_last_wins_over_the_original`

**Setup**: `pin_package_environment({"goga_tool_alpha": ["a-dist"], "goga_tool_beta": ["b-dist"]})` (enumeration order alpha, then beta); alpha adjusts `[{"kind": "schema_only", "cell": "from-alpha"}]`; beta adjusts `[{"kind": "codegraph_only", "cell": "from-beta"}]`; both installed via `install_tool_package`.

**Input**: `amend_report([EntryFacts(kind="schema_only", cell="orig", types=None)])`.

**Trace**: alpha's view over the original `[orig]` → adjustment validated → `current = [from-alpha]`; beta's view built from the **original** (`[orig]`, never `[from-alpha]`) → adjustment validated → `current = [from-beta]` — a whole replacement, never a merge with alpha's result.

**Assertions**: settled `== [EntryFacts(kind="codegraph_only", cell="from-beta", types=None)]`; `"from-alpha"` appears nowhere in the result.

**Sufficiency**: the list-control semantics with two adjusters — whole replacement over the original, the later adjusting tool in enumeration order wins; prevents a chained-merge regression (current = previous adjustment + own).

---

#### `test_amend_report_empty_adjustment_clears_and_adds_entries`

**Setup**: one tool; scenario A adjusts `[]`; scenario B (fresh surface) adjusts `[{"kind": "codegraph_only", "cell": "extra", "types": ["thing"]}]`.

**Input**: `amend_report(scoped)` with a one-entry scoped list.

**Trace**: A: validated empty list → `current = []`. B: validated → `current = [EntryFacts(kind="codegraph_only", cell="extra", types=["thing"])]`.

**Assertions**: A → `[]`; B → kind/cell/types as adjusted.

**Sufficiency**: a cleared report grades 0 and a tool-added entry grades 1 — the grading list is the post-amendment list.

---

#### `test_amend_entry_commits_facts_per_entry`

**Setup**: one contributing tool (`context.contribute({"ticket": "GOGA-1"})`).

**Input**: `amend_entry(EntryFacts(kind="schema_only", cell="mix", types=["stale"]))`.

**Trace**: per-tool walk → merged `{"ticket": "GOGA-1"}` → `merge_entry_contributions`.

**Assertions**: result `== {"docs-like-tool": {"ticket": "GOGA-1"}}` (the platform identity of the installed package).

**Sufficiency**: the entry-facts amendment mirrors the node amendment — same commit granularity and merge rules.

---

#### `test_emit_run_completed_delivers_the_terminal_facts`

**Setup**: one observing tool recording `context.completion.outcome`, `len(context.completion.report or [])`, `context.completion.reason`.

**Input**: `emit_run_completed(RunCompletion(report=[ReportEntry(kind="schema_only", cell="a", types=None, tools={})], outcome=RunOutcome.finished, reason=""))`.

**Trace**: soft emission; the shared frozen wrapper delivered.

**Assertions**: recorder `== ("finished", 1, "")`; no raise.

**Sufficiency**: the completion moment's payload contract (stage, outcome, reason) as the consumer doc publishes it.

---

#### `test_codegraph_delivers_every_surviving_node_in_tree_order_with_complete_children`

**Setup**: plant a nested project (root `CWD` with `.goga/config.yml`, packages `lib` (declared+coded), `lib/inner` (declared+coded)); environment with a tool recording `context.node.cell` and `context.node.children` on `amend_node`.

**Input**: `codegraph(["lib"], None, [])`.

**Trace**:
```
codegraph(cells=["lib"])
  → render filtered: [lib (children pruned? no — cells filter keeps matches + ancestors;
     lib/inner survives as it matches? ["lib"] matches lib only; inner pruned)]
  → filters active → complete tree rendered: lib with child inner
  → walk output tree: node lib
  → NodeFacts(cell="lib", children=["lib/inner"])   # from the complete tree
  → amend_node delivered once; no delivery for lib/inner (pruned)
```

**Assertions**: recorder cells `== ["lib"]`; the recorded children `== ["lib/inner"]` (a pruned cell named in the facts — identical in every run); returned tree nodes have `tools == {}` (the recorder contributed nothing).

**Sufficiency**: filters prune delivery exactly as they prune output, and never prune the facts — the two core delivery requirements.

---

#### `test_codegraph_places_overlays_and_returns_the_gated_tree`

**Setup**: the planted project; a tool contributing `{"coverage": 3}` on every node; no gate subscriptions.

**Input**: `tree = codegraph([], None, [])`.

**Trace**: every node delivered → `overlays` per cell → `_apply_overlays` rebuilds → gate approves → tree returned.

**Assertions**: every node's `tools == {"<tool>": {"coverage": 3}}`; node fields otherwise unchanged (`cell`/`types`/`dependencies`/`children`).

**Sufficiency**: the committed overlay lands on the returned record — the output surface of the extension.

---

#### `test_drift_runs_the_full_checkpoint_order`

**Setup**: plant `_plant_four_kinds`; a tool subscribing to all four drift actions, recording `(action, subject)` per call, and adjusting nothing.

**Input**: `drift([], None, [])`.

**Trace**:
```
drift()
  → emit_run_started(filters=([]))                     # recorded first
  → schema/codegraph producers (complete + filtered)   # codegraph checkpoints fire inside
  → compare + scope → scoped report (mix/… entries)
  → amend_report over the scoped EntryFacts            # recorded once
  → amend_entry per settled entry                      # recorded per entry
  → emit_run_completed(finished, final stage)          # recorded last
```

**Assertions**: the recorded order starts with `run_started`, ends with `run_completed`; `amend_report` precedes every `amend_entry`; the count of `amend_entry` deliveries equals the settled report length; the returned report equals the scoped four-kinds report (`test_drift`'s existing expectations unchanged — no adjustment, no facts).

**Sufficiency**: the fixed run ordering and the no-subscription invariance of the domain routine.

---

#### `test_drift_completion_carries_the_final_report_on_finished_runs`

**Setup**: `_plant_four_kinds`; a tool recording `context.completion.report` (as `(kind, cell)` tuples) and contributing `{"ticket": "GOGA-9"}` on `amend_entry`.

**Input**: `report = drift([], None, [])`.

**Trace**: finished run → completion carries `[ReportEntry(…, tools={"<tool>": {"ticket": "GOGA-9"}})]`.

**Assertions**: recorded completion stage equals the returned report projected `(kind, cell)`; every returned `DriftEntry.tools == {"<tool>": {"ticket": "GOGA-9"}}`; outcome `RunOutcome.finished`; reason `""`.

**Sufficiency**: the finished-run completion payload includes the facts areas — the recorded stage semantics.

---

#### `test_codegraph_command_writes_the_conditional_tools_key`

**Setup**: `CliRunner`; a planted project; environment A empty; environment B with a contributing tool.

**Input**: `runner.invoke(app, ["codegraph"])` under A and B.

**Trace**: routine → projection → JSON. A: no node has `tools`. B: contributed nodes carry `"tools": {"<tool>": {...}}`.

**Assertions**:
```
A: "tools" not in json for every node; output equals the pre-extension golden bytes
B: only contributed nodes carry the key; json round-trips; indent=4, sort_keys
```

**Sufficiency**: the CLI projection (not `asdict`) — an empty `tools` object must never appear; the byte-identical invariant without subscriptions.

---

#### `test_drift_command_grades_the_post_amendment_list`

**Setup**: `_plant_four_kinds`; scenario A — a tool adjusting `[]`; scenario B (fresh env) — a tool adjusting a clean project (`_plant_healthy_plus`) to add one entry.

**Input**: `runner.invoke(app, ["drift"])`.

**Trace**: A: report cleared → `[]` printed → exit 0. B: tool-added entry printed → exit 1.

**Assertions**: A: `result.exit_code == 0`, `json.loads(result.output) == []`; B: `result.exit_code == 1`, one entry with the adjusted kind/cell.

**Sufficiency**: the three-outcome contract over the final post-amendment list — the grading rule the catalog and command docs commit to.

---

### Negative Tests

#### `test_amend_node_crashed_hook_is_a_hard_failure_naming_the_subject`

**Setup**: one tool whose hook raises `RuntimeError("kaboom")`.

**Input**: `CodegraphHooks().amend_node(node=_node_facts(cell="goga/codegraph"))`.

**Trace**: hook raises → `ValueError` chained (`from reason`).

**Assertions**:
```
pytest.raises(ValueError, match=r"hook boom of tool docs failed on codegraph\.amend_node at goga/codegraph: kaboom")
"Traceback" not in str(excinfo.value)
```

**Sufficiency**: the amendment error envelope (hook, tool, action, failing node cell path) — the command's clean stderr message depends on it.

---

#### `test_amend_node_structurally_malformed_contribution_fails_the_same_way`

**Setup (parametrized payloads)**: hooks contributing `[("a", 1)]` (a non-mapping payload — an iterable of pairs), `{"k": {}}` (empty nested mapping), `{1: "x"}` (non-string key), `{"k": {object()}}` (non-serializable), `{"k": float("nan")}` (non-finite), a self-referencing dict (cycle).

**Input**: `amend_node(node=_node_facts())`.

**Trace**: merge → `_check_json_map` raises `ValueError(detail)` → wrapped as the tool-commit failure.

**Assertions**: `pytest.raises(ValueError, match=r"tool docs failed on codegraph\.amend_node at goga/config: structurally malformed contribution")` for every payload.

**Sufficiency**: the JSON-map shape is the output's serialization guarantee — every malformed shape must fail loudly, never coerce.

---

#### `test_amend_report_malformed_adjustment_is_never_adopted`

**Setup (parametrized adjustments)**: `[{"kind": "wrong", "cell": "a"}]` (bad kind), `[{"kind": "schema_only"}]` (missing cell), `[{"kind": "schema_only", "cell": ""}]` (empty cell), `[{"kind": "schema_only", "cell": "a", "extra": 1}]` (extra key), `[{"kind": "schema_only", "cell": "a", "types": "b"}]` (types not a list), `("not", "a list")` (tuple), `[["kind", "cell"]]` (entry not a mapping).

**Input**: `amend_report([EntryFacts(kind="schema_only", cell="orig", types=None)])`.

**Trace**: buffer changed → closed-shape validation raises → wrapped naming the attributed hook.

**Assertions**: `pytest.raises(ValueError, match=r"hook .* of tool .* failed on drift\.amend_report: malformed adjustment")`; on the matching no-raise checks (none here), the original list stays.

**Sufficiency**: "never sanitized, never adopted" — the closed report-entry shape is a hard gate.

---

#### `test_amend_report_crashed_hook_stops_and_adopts_nothing`

**Setup**: two tools installed so the crashing tool (`alpha`) enumerates first — alpha's hook raises `RuntimeError("boom")`; beta (later in enumeration) adjusts validly.

**Input**: `amend_report(scoped)`.

**Trace**: first tool's hook raises → walk stops at the first failure → the later adjuster never runs.

**Assertions**: `pytest.raises(ValueError, match=r"failed on drift\.amend_report")`; the adjuster's recorder is empty.

**Sufficiency**: first-failure stop — no partial adoption of a later tool after an earlier crash.

---

#### `test_amend_entry_hard_failure_names_the_entry`

**Setup**: a tool whose hook raises on one specific cell.

**Input**: `amend_entry(EntryFacts(kind="codegraph_only", cell="extra", types=["helper"]))`.

**Assertions**: `pytest.raises(ValueError, match=r"failed on drift\.amend_entry at codegraph_only extra")`.

**Sufficiency**: the failing entry (kind + cell path) is named — the contract's subject requirement.

---

#### `test_amend_entry_structurally_malformed_contribution_names_the_entry`

**Setup**: one tool whose hook calls `context.contribute({"k": {}})` (an empty nested mapping — structurally malformed).

**Input**: `amend_entry(EntryFacts(kind="schema_only", cell="mix", types=None))`.

**Trace**: buffer merges to `{"k": {}}` → `_check_json_map` raises `ValueError("empty mapping at the merged contribution.k")` → wrapped at the tool commit point with the entry subject.

**Assertions**: `pytest.raises(ValueError, match=r"tool docs failed on drift\.amend_entry at schema_only mix: structurally malformed contribution")`.

**Sufficiency**: the structural path of the entry amendment — the same hard failure as a crash, with the distinct entry subject (`kind cell`) in the message, never a coercion.

---

#### `test_codegraph_vetoed_gate_raises_one_merged_error_and_returns_no_tree`

**Setup**: planted project; a gate tool vetoing `"shape broken"`; an `amend_node` contributor also installed (to prove the tree was assembled first).

**Input**: `pytest.raises(ValueError)` around `codegraph([], None, [])`.

**Trace**: amendments commit → gate walks → verdict not approved → merged error raised before return.

**Assertions**:
```
match=r"codegraph validation failed:"
"- tool gate / hook vetoer: shape broken" in str(excinfo.value)
```

**Sufficiency**: the gate is the last checkpoint — no partial tree escapes; one error lists every violation.

---

#### `test_codegraph_hard_amendment_failure_propagates_from_the_routine`

**Setup**: planted project; an `amend_node` hook raising on the first delivered node.

**Input**: `pytest.raises(ValueError)` around `codegraph([], None, [])`.

**Assertions**: `match=r"failed on codegraph\.amend_node at "` (the failing node cell path present).

**Sufficiency**: the domain propagates checkpoint errors unchanged — the command's exit-1 path depends on it.

---

#### `test_drift_producer_failure_emits_crashed_completion_and_reraises`

**Setup**: no `.goga/config.yml` planted (uninitialized project — `tmp_path` CWD is empty); a moment observer recording the completion payload.

**Input**: `pytest.raises(FileNotFoundError)` around `drift([], None, [])`.

**Trace**: start moment fires → `schema()` raises `FileNotFoundError` → failure path: completion `(report=None, crashed, reason=str(err))` → re-raise.

**Assertions**: recorder `== (None, "crashed", reason-containing-".goga/config.yml")` — `report is None` (nothing computed); the original exception type propagates.

**Sufficiency**: the completion fires on producer failures carrying **no** report stage, and never masks the failure.

---

#### `test_drift_amendment_failure_carries_the_scoped_pre_amendment_stage`

**Setup (two scenarios)**: `_plant_four_kinds`; S1 — an `amend_report` hook raising; S2 — an `amend_entry` hook raising. A completion observer records the carried stage.

**Input**: `pytest.raises(ValueError)` around `drift([], None, [])`.

**Trace**: S1: scoped computed (`carried` set) → report amendment raises → completion with the scoped entries (empty tools) → re-raise. S2: settled list → first `amend_entry` raises → completion with the scoped stage (not the half-enriched list) → re-raise.

**Assertions**: S1/S2: the recorded stage equals the scoped `(kind, cell)` projection with every `tools == {}`; outcome `crashed`; the raise matches the checkpoint error.

**Sufficiency**: the carried-stage rule for late failures — facts areas never carry failure semantics.

---

#### `test_codegraph_command_exit_1_with_clean_stderr_on_checkpoint_failure`

**Setup**: planted project; a vetoing gate tool; `CliRunner`.

**Input**: `runner.invoke(app, ["codegraph"])`.

**Trace**: routine raises the merged error → `except Exception` → `click.echo(str(e), err=True)` → `ctx.exit(1)`.

**Assertions**: `result.exit_code == 1`; `result.output == ""` (stdout empty); the merged error text in stderr; no `"Traceback"` in stderr.

**Sufficiency**: checkpoint failures are the command's ordinary error path — exit 1, nothing on stdout.

---

#### `test_drift_command_exit_2_on_amendment_failure`

**Setup**: `_plant_four_kinds`; an `amend_report` hook raising.

**Input**: `runner.invoke(app, ["drift"])`.

**Assertions**: `result.exit_code == 2`; `result.output == ""`; stderr names hook/tool/action/reason.

**Sufficiency**: the exit-2 envelope extended with the drift amendment hard failures.

---

### Edge Case Tests

#### `test_codegraph_empty_project_returns_empty_before_any_checkpoint`

**Setup**: `.goga/config.yml` planted, no packages; an observer tool subscribing to both actions (records every call).

**Input**: `codegraph([], None, [])`.

**Trace**: render → `[]` → early return.

**Assertions**: result `== []`; the observer recorded nothing (no enumeration side effects observable through delivery).

**Sufficiency**: "an empty graph fires nothing" — the early return precedes any registry use.

---

#### `test_codegraph_no_subscriptions_output_is_byte_identical`

**Setup**: planted `_plant_healthy_plus`-style project; environment empty; capture `goga codegraph` output (or the routine's serialization) as golden; then install a tool that subscribes but contributes nothing; re-run.

**Input**: CLI run under both environments.

**Assertions**: the two outputs are byte-identical; no `"tools"` substring anywhere.

**Sufficiency**: the extension's zero-footprint guarantee — the family's compatibility contract.

---

#### `test_amend_node_fresh_view_per_tool_keeps_writes_local`

**Setup**: two tools; the first mutates `context.node.types` in place (`context.node.types.append("X")` — the delivered facts are fresh per tool, so this writes a private copy); the second records `list(context.node.types)`.

**Input**: `amend_node(node=_node_facts(types=["ProjectConfig"]))`.

**Assertions**: the second tool saw `["ProjectConfig"]`; the caller's original `NodeFacts.types` unchanged.

**Sufficiency**: mutual blindness extends to in-place writes — fresh containers per view.

---

#### `test_amend_report_returns_input_values_unchanged_without_subscriptions`

**Setup**: environment empty.

**Input**: `settled = amend_report([EntryFacts(kind="schema_only", cell="a", types=None), EntryFacts(kind="codegraph_only", cell="b", types=["x"])])`.

**Assertions**: `settled == report` (value equality); the input list object unmutated (`report` still length 2).

**Sufficiency**: the byte-identical passthrough — the amendment is unobservable without subscriptions.

---

#### `test_amend_report_empty_scoped_list_still_delivers`

**Setup**: `_plant_healthy_plus` (agreeing views → empty scoped report); a tool adjusting to one added entry.

**Input**: `report = drift([], None, [])`.

**Trace**: scoped `[]` → `amend_report([])` delivered → adjustment adopts one entry → `amend_entry` fires for it → completion carries it.

**Assertions**: the returned report has exactly the adjusted entry; an `amend_entry` delivery was recorded for it.

**Sufficiency**: tool-detected discrepancies in an otherwise clean report — the empty-list delivery is required by the integration scenario, unlike the per-entry amendment.

---

#### `test_zone_checkpoints_without_subscriptions_are_inert`

**Setup (parametrized)**: environment empty (no tool packages). Cases: `CodegraphHooks().amend_node(node=_node_facts())`; `CodegraphHooks().validate_graph([_final_node()])`; `DriftHooks().amend_entry(EntryFacts(kind="schema_only", cell="a", types=None))`.

**Input**: each checkpoint call listed above.

**Trace**: `build_once` enumerates nothing → `subscriptions_for` returns `[]` → no groups → no contributions/violations → `merge_*_contributions([])` / empty verdict.

**Assertions**: `amend_node` → `{}`; `validate_graph` → `verdict.approved is True and verdict.violations == []`; `amend_entry` → `{}`.

**Sufficiency**: the zone-level no-subscription invariants — the delivery is unobservable (schema precedents: `test_amend_cell_without_subscriptions_returns_empty_mapping`, `test_validate_schema_approved_with_no_subscriptions`).

---

#### `test_amend_report_carries_empty_types_list_and_cell_level_added_entry`

**Setup**: one tool adjusting `[{"kind": "schema_only", "cell": "leaf", "types": []}, {"kind": "codegraph_only", "cell": "whole"}]` — an empty `types` list (carried verbatim, never sanitized) and a cell-level entry (types omitted).

**Input**: `settled = amend_report([EntryFacts(kind="schema_only", cell="orig", types=None)])`.

**Trace**: buffer changed → closed-shape validation passes (an empty `types` list is a list of strings; a missing `types` is a cell-level entry) → whole replacement with fresh owned records.

**Assertions**: settled `== [EntryFacts(kind="schema_only", cell="leaf", types=[]), EntryFacts(kind="codegraph_only", cell="whole", types=None)]`.

**Sufficiency**: the two acceptance decisions of `_validate_adjustment` the negative tests do not reach — `types: []` is adopted as given and an omitted `types` yields a cell-level entry.

---

#### `test_amend_entry_empty_settled_list_fires_nothing`

**Setup**: a clean project; an `amend_entry` observer.

**Input**: `drift([], None, [])` (scoped `[]`, no adjusters).

**Assertions**: no `amend_entry` delivery recorded.

**Sufficiency**: the per-entry amendment's empty-list short-circuit (explicit in the routine step 5).

---

#### `test_run_outcome_members_and_run_completion_none_report`

**Setup**: none (pure records).

**Input**: `RunOutcome.finished.value`, `RunOutcome.crashed.value`, `RunCompletion(report=None, outcome=RunOutcome.crashed, reason="x")`.

**Assertions**: values `("finished", "crashed")`; `list(RunOutcome) == [RunOutcome.finished, RunOutcome.crashed]`; the record is frozen and kw_only (`is_kw_only_dataclass` helper).

**Sufficiency**: the outcome markers are the completion facts' contract; `report=None` is the early-failure stage.

---

#### `test_codegraph_node_and_drift_entry_carry_the_tools_default`

**Setup**: none.

**Input**: `CodegraphNode(cell="a")`, `DriftEntry(kind="schema_only", cell="a")`.

**Trace**: dataclass defaults.

**Assertions**: `node.tools == {}`; `entry.tools == {}`; both records frozen (`dataclasses.FrozenInstanceError` on assignment).

**Sufficiency**: the empty-default invariant — pre-checkpoint consumers never populate `tools`.

---

#### `test_drift_start_moment_import_failure_propagates_without_completion`

**Setup**: `pin_package_environment({"goga_tool_broken": ["broken-dist"]})`; `install_tool_package("goga_tool_broken", register_hooks=None)` — a facade whose import the platform wrapper turns into the fatal `ImportError` (or a `register_hooks` raising on import — use the broken-import shape the platform names).

**Input**: `pytest.raises(ImportError)` around `drift([], None, [])` on a planted project.

**Trace**: start moment → `build_once` → the package import fails → `ImportError("package … failed to import: …")` propagates before the wrap's try (the run never started).

**Assertions**: `ImportError` raised; no completion recorded by any observer (none could register — the enumeration failed); message names the package.

**Sufficiency**: the single fatal platform case and its exit-2 envelope; the completion moment fires only for started runs.

---

#### `test_drift_in_run_codegraph_veto_surfaces_as_exit_2`

**Setup**: `_plant_four_kinds`; a codegraph gate tool vetoing.

**Input**: `runner.invoke(app, ["drift"])`.

**Trace**: drift → `codegraph([], None, [])` (complete view) → gate veto → merged error → drift failure path (completion `crashed`, stage `None`) → re-raise → command exit 2.

**Assertions**: `result.exit_code == 2`; stdout empty; stderr contains `codegraph validation failed`.

**Sufficiency**: the in-run veto path — the drift command's exit-2 cause list includes it.

---

#### `test_drift_determinism_with_tools_installed`

**Setup**: planted project; a contributing tool (deterministic facts).

**Input**: `drift([], None, [])` twice (fresh surfaces).

**Assertions**: the two reports are equal (`==`), including the `tools` mappings and their order (dict equality per entry).

**Sufficiency**: "identical project state, configuration, and installed tools produce identical reports".

---

## Additional Instructions for the Implementation Agent

- Implement strictly in the dependency order of *Entity Dependencies* (catalog → facts → codegraph zone → drift zone → codegraph domain → drift domain → commands). `goga lint` must stay at 0 errors after every cell.
- Mirror `goga/schema/hooks` (contract, Python, tests) for the codegraph zone — it is the recorded precedent; the drift zone mixes that precedent (amendments) with the pipeline moments precedent (`emit_hook_event` + shared frozen context).
- The drift moment contexts are **private wrapper records** (`_RunStarted(filters)`, `_RunCompleted(completion)`) in `events.py` — delivery shape only, not contract surface; the consumer doc commits to `context.filters` / `context.completion`.
- Replace the codegraph command's `asdict` serialization with the `_project_node` projection (the schema command is the reference); an empty `tools` object must never appear at any level.
- `RunOutcome` is a plain `Enum` with string member values (precedent `SyncOutcome`); never accept a raw string where `RunOutcome` is declared.
- `reason=str(reason)` for the crashed completion — do not invent a scrubber; the producers' clean-error convention is the credential guarantee. Never let a traceback string cross the boundary.
- The drift routine's `carried` stage is set to the scoped pre-amendment projection **before** `amend_report` and replaced by the final projection **only after** the entry loop completes — a step-5 failure must carry the scoped stage, never a half-enriched list.
- `filters_active = bool(cells) or max_depth is not None or bool(depends_on)` — when inactive, the output tree serves as the complete tree (single render); when active, render twice.
- Tests: zone suites run the real platform over the two boundary fixtures (no mocking inside the platform); domain/CLI suites plant real projects on `tmp_path`; never leave the package environment unpinned in a suite that builds a non-empty tree.
- Do not modify `render_graph`, `compare_views`, `scope_entries`, the analysis stages, or the platform cells — the extension touches only the eight cells listed in *Contract Changes*.
- After implementation, re-run `goga lint`, `goga schema` (both zones present, no cycles), and the full test suite (`pytest tests/ -x`).
