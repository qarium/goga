# Design Document: `add-pipeline-hooks`

<!-- Topic: add-pipeline-hooks — .goga/history/2026/add-pipeline-hooks/ -->

Complete architectural specification for the pipeline domain hooks zone: the
`amend_workflow` amendment action (the platform's first hard action), the
`run_created` / `run_completed` notifications, the authored-wins workflow
overlay, and the wiring of both pipeline flows (run and card) through the
new checkpoint surface.

Contracts are materialized and lint-clean (`goga lint`: 78 cells, 0 errors).
This document specifies **what to implement and how** — module layouts,
algorithms at field level, error channels, and the full test stack. The
implementation order stays with the planning stage.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST`: three action records appended to the
  `declared_actions` requirements — `pipeline/amend_workflow` (hard, the
  platform's first), `pipeline/run_created` (soft),
  `pipeline/run_completed` (soft). Purely additive; `Action` and the
  published records untouched.
- `goga/pipeline/hooks/CODEMANIFEST`: **created** — the hooks zone cell. 11
  types across five modules; Imports from `goga/hooks` (5 types + 3
  practices) and `goga/pipeline/workflow` (`WorkflowDocument`).
- `goga/pipeline/CODEMANIFEST`: two Imports groups appended (hooks zone: 6
  types + `checkpoints`; history: 4 types + `topic-paths` +
  `topic-statuses`); hooks-zone paragraph in the global Annotations;
  `PipelineCard` gains `provenance`; `describe_pipeline` algorithm extended
  to 7 steps; `run_pipeline` algorithm extended to 17 steps;
  `pipeline_cli` card template gains the conditional `tools:` line.

### New Entities

All in the zone `goga/pipeline/hooks` (facade `__init__.py` exposes exactly
these via `__all__`, alphabetical):

- `PipelineIdentity(name, display_name="", description, source)` —
  `identity.py`. The identity vocabulary of every pipeline event.
- `WorkflowDecision(kind, workflow_name)` — `identity.py`. The outcome of
  the workflow resolution: `disabled` / `explicit` / `auto-match` /
  `silent-miss`.
- `WorkIdentity(branch, slug=None, year=None)` — `identity.py`. The
  topics-shaped identity of the current work.
- `CompositionStage(id, title)` — `contexts.py`. One row of the final
  composition as the card shows it.
- `ToolContribution(tool, document)` — `overlay.py`. The committed
  contribution of one tool.
- `WorkflowOverlay(workflow, provenance)` — `overlay.py`. The result of the
  amendment layer.
- `merge_workflow_overlay(base, contributions) -> overlay` — `overlay.py`.
  The authored-wins overlay merge (Routine).
- `WorkflowAmendment(pipeline, decision, workflow, work)` — `amendments.py`.
  The read-and-contribute view of one tool; method `contribute(document)`.
- `RunCreated(...)` / `RunCompleted(...)` — `contexts.py`. The read-only
  run-notification fact bundles.
- `PipelineHooks()` — `events.py`. The checkpoint surface:
  `amend_workflow`, `emit_run_created`, `emit_run_completed`.

### Changed Entities

- `PipelineCard` (`goga/pipeline/pipeline_card.py`) — gains
  `provenance: list[str]` (default `field(default_factory=list)`).
- `describe_pipeline` (`goga/pipeline/describe_pipeline.py`) — resolves the
  amendment facts, delivers the amendment (unless disabled), compiles with
  the overlay workflow, reports `overlay.provenance` on the card.
- `run_pipeline` (`goga/pipeline/run_pipeline.py`) — 17-step coordination:
  fact resolution, amendment delivery between skip merge and compilation,
  composition build, status resolution, emissions around the launch.
- `pipeline_cli` (`goga/pipeline/cli.py`) — the card form renders the
  conditional `tools:` field line; both failure paths also render the hard
  amendment error cleanly.
- `declared_actions` catalog (`goga/hooks/catalog/catalog.py`) — three new
  `Action` records.

### Deleted Entities

None.

### Usages and Annotations Changes

- `goga/pipeline/hooks/.usages/checkpoints.md` — created (checkpoint-surface
  consumption: fact resolution, amend-before-compile, emit-around-launch,
  card form).
- `goga/pipeline/.usages/registering-hooks.md` — created (tool-author guide:
  events table, subscribe, amendment view, run notifications, integration
  scenarios).
- `goga/pipeline/.usages/describe-pipeline.md`, `run-pipeline.md`,
  `pipeline-cli.md` — synced to the new surface (provenance, amendment
  layer, run events, `tools:` line).

---

## Applied Fixes

Three CODEMANIFEST defects surfaced during validation/tracing; each was
proposed to the user via the stage dialog and approved (answers A/A/A).

### Fixed CODEMANIFEST Defects

1. `goga/pipeline/CODEMANIFEST` (`run_pipeline` step 8,
   `describe_pipeline` step 3 + constraint) — **authored header facts had
   no source at fact-resolution time**. Before: "authored header name and
   description" with no mechanism (both operations build the identity
   before `compile_flow` returns the documents tuple). After: the steps
   name the source — "read via `parse_dsl` from the pipeline-file text"
   (the established `describe_pipelines` pattern;
   `describe_pipelines.py:63`) — and the `describe_pipeline` constraint is
   scoped: "Do not re-parse the pipeline-file **for the card fields** ...
   the single early `parse_dsl` read of step 3 serves the amendment facts
   only". (reason: annotation insufficient for implementation)
2. `goga/pipeline/CODEMANIFEST` (same two steps) — **the None branch was
   undefined**. `resolve_current_branch_name() -> str | None` (detached
   HEAD / missing git / non-repo) vs `WorkIdentity(branch: str)`. After:
   "the literal \"unknown\" when it resolves None" — a non-fatal sentinel;
   a hard error would regress detached-HEAD runs even with zero tool
   packages installed, violating "every form behaves exactly as before".
   (reason: interface ↔ interface mismatch)
3. `goga/pipeline/CODEMANIFEST` (Imports + `run_pipeline` step 9 +
   `describe_pipeline` step 3) — **the disabled branch had no overlay
   value**. Step 14 emits "the overlay", but a disabled decision "delivers
   nothing" and `WorkflowOverlay` was not imported. After:
   `WorkflowOverlay` added to the zone Types Imports; both steps state "a
   disabled decision delivers nothing and the overlay is the passthrough
   `WorkflowOverlay` of the merged workflow". (reason: annotation
   reference without a resolvable source)

All edits re-validated: `goga lint` 78 cells / 0 errors; `goga schema`
shows `goga/pipeline → goga/pipeline/hooks` with the six types; no cycles.

---

## Entity Interaction and Data Flow

### Interaction Diagram

```
                    goga/commands/pipeline (host CLI, docker boundary)
                                  │ docker run + env
                                  ▼
                    goga/pipeline (in-container zone)
        ┌──────────────────────────────────────────────────┐
        │ pipeline_cli ── run form ──▶ run_pipeline        │
        │      │ card form ──▶ describe_pipeline           │
        │      │                        │                  │
        │      ▼                        ▼                  │
        │  PipelineCard(+provenance)   (1) fact resolution │
        │        ▲                      │  parse_dsl       │
        │        │                      │  resolve_workflow + apply_skip_stages
        │        │                      │  resolve_current_branch_name /   ──▶ goga/history
        │        │                      │  resolve_topic_dir               (topic-paths,
        │        │                      │  (statuses: assemble_status_scale /  topic-statuses)
        │        │                      │   resolve_topic_status)          │
        │        │                      ▼                                  │
        │        │            goga/pipeline/hooks (the zone)               │
        │        │        PipelineHooks ── amend_workflow ──▶ WorkflowAmendment (per tool)
        │        │        │      │                    contribute()          │
        │        │        │      ▼                                          │
        │        │        │  merge_workflow_overlay ◀─ ToolContribution*    │
        │        │        │      │                                          │
        │        │        │      ▼ WorkflowOverlay                          │
        │        │        │  emit_run_created  ──▶ RunCreated ─┐            │
        │        │        │  emit_run_completed ─▶ RunCompleted ├─▶ goga/hooks
        │        └────────┤                                   │  (emit_hook_event,
        │  compile_flow(overlay.workflow) ◀───────────────────┘   wrap_context,
        │        │        ▲                                      build_hook_arguments,
        │        ▼        │                                      HookRegistry,
        │  order_stages ──┘ CompositionStage[]                   declared_actions)
        │        │                                                ▲
        │        ▼                                                │
        │  run_flow (goga/afm) ── exit_code ──▶ emit_run_completed│
        └──────────────────────────────────────────────────┘  goga/hooks/catalog
                                                              (+3 Action records)
```

### Data Flows

**Flow 1 — run form (the 17 steps of `run_pipeline`):**

1. `list_pipelines` → `PipelineEntry` match → absolute `pipeline_path`;
   missing → stderr message, `return 1` (no events).
2. `AFM_DIR` env → `afm_dir` (unset → `RuntimeError("AFM_DIR not set")`);
   `runtime_dir = afm_dir.as_posix()`.
3. `GOGA_WORKFLOW_DISABLED` / `GOGA_WORKFLOW_NAME` env → decision inputs →
   `resolve_workflow(name, workflow_name, no_workflow)` → `WorkflowDocument | None`.
4. `GOGA_SKIP_STAGES` split → `apply_skip_stages(workflow, skips)` →
   merged `workflow` (None-safe; empty split → unchanged).
5. Facts: `pipeline_path.read_text()` → `parse_dsl(text)[0]` → header
   (`name`, `description`) → `PipelineIdentity`;
   kind-derivation (below) → `WorkflowDecision`;
   `branch = resolve_current_branch_name() or "unknown"` → guarded
   `resolve_topic_dir(branch)` → `WorkIdentity`.
6. `hooks = PipelineHooks()` (one instance for the whole run).
   `decision.kind != "disabled"` →
   `overlay = hooks.amend_workflow(pipeline=..., decision=..., workflow=..., work=...)`;
   else `overlay = WorkflowOverlay(workflow=merged_workflow, provenance=[])`.
7. `resolve_project_name()` → `compile_flow(pipeline_path, flow_path,
   workflow=overlay.workflow, root_dir=str(Path.cwd().resolve()),
   project_name=...)` → `(pipeline_doc, flow_doc)`; structural errors
   propagate (no events).
8. Prompt materialization (unchanged steps: validate-all → wipe → write
   four files into `<AFM_DIR>/prompts/`).
9. `order_stages(flow_doc.stages)` → `composition =
   [CompositionStage(id=s.id, title=s.name) for s in ordered]`.
10. Statuses (hosting form only): `scale = assemble_status_scale()`,
    `statuses = resolve_topic_status(topic_dir, scale)`; branch-only →
    `statuses = []` (no scale assembly).
11. `hooks.emit_run_created(pipeline=identity, decision=decision,
    overlay=overlay, composition=composition, work=work,
    statuses=statuses, runtime_dir=runtime_dir)`.
12. `exit_code = run_flow(flow_path, port, max_parallel=parallel)`
    (spawn failures are return codes 126/127 — returns, not raises).
13. Hosting form: `statuses = resolve_topic_status(topic_dir, scale)`
    recomputed (one scale, two reads); branch-only stays `[]`.
    `hooks.emit_run_completed(..., exit_code=exit_code)`; `return exit_code`.

**Flow 2 — card form (`describe_pipeline`, 7 steps):** discovery →
`resolve_workflow` (CLI flags; no `GOGA_SKIP_STAGES` read) → facts
(`parse_dsl` header + unknown-branch sentinel + guarded topic dir) →
delivery unless disabled (else passthrough overlay) → `compile_flow` into
a temp dir with `overlay.workflow` → `order_stages` → `PipelineCard(...
provenance=overlay.provenance)` → temp dir discarded. **No events, no
statuses, no launch.**

**Flow 3 — the amendment delivery (inside the zone):** see the
`PipelineHooks.amend_workflow` algorithm below.

### Entity Dependencies

Design order (leaves → root, already fixed by the contract):

1. `goga/hooks` platform + `goga/pipeline/workflow` (exist, untouched).
2. Zone data models: `identity.py` → `contexts.py` (imports identity
   types + `WorkflowDocument`) → `overlay.py` (imports
   `WorkflowDocument`) → `amendments.py` (imports identity +
   `WorkflowDocument`).
3. `events.py` (`PipelineHooks`) — imports the platform facade
   (`from ...hooks import HookRegistry, build_hook_arguments, emit_hook_event,
   wrap_context, declared_actions` — three dots: `goga.pipeline.hooks` →
   `goga`), `..workflow` for nothing (contexts carry it), and the local
   models (`from .amendments import WorkflowAmendment`, etc.).
4. Catalog records (`goga/hooks/catalog/catalog.py`) — additive,
   independent.
5. Consumers: `pipeline_card.py` (field), `describe_pipeline.py`,
   `run_pipeline.py` (import `from .hooks import ...`; history via
   `from ..history import ...`), `cli.py` (template + catch).

Import-cycle safety (verified by trace): importing `goga.pipeline.hooks`
first executes `goga/pipeline/__init__.py` (partial), which imports
`.run_pipeline` → `.hooks` → `..workflow`; `goga.pipeline.workflow` and
`goga.hooks` never import back into `goga.pipeline` submodules loaded by
its `__init__`, so the partially-initialized parent is never re-entered —
the same shape as the existing `.compiler → ..workflow` edge. The zone
MUST use relative imports only (contract: "Use relative imports").

---

## Code Stack Trace

### Trace: `PipelineHooks()` (construction)

1. **Input**: module-level or per-operation construction
   (`hooks = PipelineHooks()`).
2. Sets `self._registry: HookRegistry | None = None`. → checkpoint: no
   enumeration, no imports, no repository reads — cheap construction ✓.
3. **Output**: the checkpoint surface of one command; the registry builds
   lazily on the first checkpoint that needs it.

#### Checkpoint Summary
- Cheap construction: passed (mirrors `HookRegistry`'s own lazy build and
  onboarding's `ToolParticipation.__init__`).

### Trace: `PipelineHooks.amend_workflow`

1. **Input**: the operation (run step 9 / card step 3) calls
   `amend_workflow(pipeline: PipelineIdentity, decision: WorkflowDecision,
   workflow: WorkflowDocument | None, work: WorkIdentity)`.
2. `self._ensure_registry()` → `HookRegistry()` + `build_once()` → the
   single build per run; `ImportError` (broken tool package import)
   propagates — the single fatal case. → checkpoint: one registry per
   `PipelineHooks` instance ✓.
3. Resolve the address against `declared_actions()`:
   `Action(domain="pipeline", name="amend_workflow")` → `error_class
   == "hard"`. Unknown address → `ValueError` (unreachable once the
   catalog record exists; the resolution is the contract's step 1).
   → checkpoint: the record exists in `catalog.py` after the build ✓.
4. `registry.subscriptions_for("pipeline", "amend_workflow")` grouped per
   tool (`dict.setdefault(tool, []).append(sub)` — enumeration order
   preserved). Empty → skip to the merge with `[]`. → checkpoint:
   passthrough requirement reachable ✓.
5. Per tool: `amendment = WorkflowAmendment(pipeline=..., decision=...,
   workflow=workflow, work=work)` — every tool reads the SAME original
   `workflow` object; buffer `_contribution = None`.
   `proxy = wrap_context(amendment)`; per subscription of the tool:
   `sub.hook(**build_hook_arguments(sub.hook, proxy,
   registry.self_context(tool)))`. → checkpoint: reads/calls pass through
   the proxy, attribute assignment raises (`delivery.py:61`) — the only
   write channel is `contribute()` ✓.
6. A hook raising → **hard**: `raise ValueError(f"hook {sub.name} of tool
   {tool} failed on pipeline.amend_workflow: {reason}") from reason` —
   the exact message format of the platform (`emit.py:97`); the walk stops
   at the first failure; the tool's view (buffer) is dropped.
   → checkpoint: "clean error naming the tool and the action" ✓.
7. All hooks returned → read `amendment._contribution`:
   `None` → the tool never contributed — silent, no commit, no warning;
   empty document (`prompt is None and not stages and not extend and
   memory is None`) → `logger.warning` naming tool + action + reason,
   discard, walk continues;
   else → commit `ToolContribution(tool=tool, document=...)`.
   → checkpoint: commit granularity is the tool ✓.
8. **Output**: `merge_workflow_overlay(workflow, contributions)` → the
   `WorkflowOverlay` returned to the operation. → checkpoint: types line
   up end-to-end ✓.

#### Checkpoint Summary
- Type flow (facts in → `ToolContribution` list → `WorkflowOverlay` out):
  passed.
- Per-tool-delivery conformance: passed (loop skeleton identical to
  `participation.py:130-139`, failure leg replaced by the hard raise).
- Mutually-blind tools: passed (every view wraps the same unmodified
  `workflow`; buffers are per-view).

### Trace: `PipelineHooks.emit_run_created` / `emit_run_completed`

1. **Input**: the operation (run steps 14/16) passes the fact bundle;
   `overlay: WorkflowOverlay` (from `amend_workflow` or the disabled
   passthrough).
2. `context = RunCreated(pipeline=..., decision=..., workflow=overlay.workflow,
   composition=..., provenance=overlay.provenance, work=..., statuses=...,
   runtime_dir=...)` — one shared instance (`RunCompleted` additionally
   carries `exit_code`).
3. `emit_hook_event(self._ensure_registry(), "pipeline", "run_created",
   context_for=lambda _tool: context)`. → checkpoint: returning the same
   instance shares the read-only context — the `declaring-actions`
   pattern ✓; the emission resolves the address (soft), wraps, projects,
   calls, and converts failures to warnings — nothing for the zone to add
   (`emit.py:81-108`) ✓.
4. **Output**: `None` — fire-and-forget; the run's exit code unaffected.

#### Checkpoint Summary
- Soft failure handling: passed (delegated entirely to `emit_hook_event`).
- Registry sharing: passed (same lazy `_ensure_registry` as
  `amend_workflow` — one build even across amendment + two emissions).
- Boundary note: `assemble_status_scale` (history) builds its own registry
  internally — a run that resolves statuses enumerates tool packages a
  second time through the history cell. Pre-existing platform behavior,
  outside this feature's contracts; recorded, not changed.

### Trace: `merge_workflow_overlay`

1. **Input**: `base: WorkflowDocument | None` (post-decision,
   post-skip-merge), `contributions: list[ToolContribution]` (enumeration
   order).
2. `contributions` empty → short-circuit:
   `WorkflowOverlay(workflow=base, provenance=[])` — the passed workflow
   object itself, zero rebuild. → checkpoint: passthrough + "A None
   workflow with a non-empty provenance never occurs" (`(None, [])`) ✓.
3. prompt: `texts = [t for t in [base.prompt if base else None] +
   [c.document.prompt for c in contributions] if t]` → `"\n\n".join`;
   `None` when no texts. → checkpoint: authored first, enumeration order,
   single blank line between consecutive texts, empty strings drop ✓.
4. memory: `base.memory if base and base.memory is not None else None`;
   then per contribution `if c.document.memory is not None: memory =
   c.document.memory` — the later tool wins, no field-level merge ✓.
5. stages (field table below): authored names first, then fresh
   contribution names; authored-set fields block everything; unset fields
   take the LATER tool's value. New `WorkflowStage` instances — inputs
   never mutated ✓.
6. extend: `merged = dict(base.extend) if base else {}`; per contribution
   entry: under an authored name → dropped; otherwise later entry wins ✓.
7. provenance: `[c.tool for c in contributions]` ✓.
8. **Output**: `WorkflowOverlay(workflow=WorkflowDocument(prompt=...,
   stages=..., extend=..., memory=...), provenance=...)`; workflow `None`
   only when base is `None` and no contribution committed (unreachable
   here — the empty list short-circuited) ✓.

**Field "is set" semantics (the authored-wins table):**

| Field | SET when | Note |
|---|---|---|
| `agent`, `prompt`, `loop`, `skills`, `approve`, `notes`, `reflect`, `memory` | value is not `None` | `None` = unset |
| `manual` | value is not `None` | three-state: `True` (force) and `False` (explicit cancel) are BOTH set; absence = unset |
| `skip` | value is `True` | `skip=False` overrides nothing — only a positive skip is authored intent |

Stage merge (per name):

```
authored = base.stages.get(name) if base else None
values   = {f: getattr(authored, f) for f in FIELDS} if authored
         else {f: DEFAULT[f] for f in FIELDS}          # None / skip=False
authored_set = {f: SET(f, values[f]) for f in FIELDS}
for c in contributions:                                 # enumeration order
    cs = c.document.stages.get(name)
    if cs is None: continue
    for f in FIELDS:
        if SET(f, getattr(cs, f)) and not authored_set[f]:
            values[f] = getattr(cs, f)                  # later tool wins
merged_stages[name] = WorkflowStage(**values)
```

#### Checkpoint Summary
- Purity: passed (new `WorkflowStage`/`WorkflowDocument` instances; field
  values by reference — the repo's shallow-copy convention, as in
  `apply_skip_stages.py:78`; nothing is mutated).
- Declarativeness: passed (the result uses only `WorkflowDocument`-shaped
  values — it compiles through the unchanged `compile_flow`).
- Determinism: passed (pure function of the inputs; enumeration order is
  the only ordering input).

### Trace: `WorkflowAmendment.contribute`

1. **Input**: a tool hook calls `context.contribute(document)` through the
   delivery proxy (`registering-hooks` example: `context.contribute(hardening_workflow)`).
2. `self._contribution = document` — whole replacement; a later call
   replaces the earlier buffered document ✓.
3. **Output**: `None`. The buffer commits only when the delivery reads it
   after every hook of the tool returned (trace above, step 7).
   → checkpoint: `contribute` is reachable through the proxy (method
   call passes through `__getattr__`), and it is the ONLY write channel ✓.

### Trace: `run_pipeline` / `describe_pipeline` / `pipeline_cli`

Covered by Data Flows 1-2 and the entity algorithms below. Additional
checkpoints verified during tracing:

- `apply_skip_stages(None, skips)` constructs a skip-only document;
  `apply_skip_stages(x, [])` returns `x` unchanged (`apply_skip_stages.py:73-75,
  78-82`) — the card's skip-blindness and the run's merge order hold ✓.
- `WorkflowDecision` kind derivation (the operation recomputes what
  `resolve_workflow` does not report):
  `no_workflow` → `("disabled", None)`;
  else explicit name given (`workflow_name not in (None, "")`) and a
  document resolved → `("explicit", workflow_name)`;
  no explicit name and a document resolved → `("auto-match", name)`;
  document `None` (explicit-missing / auto-miss / containment escape) →
  `("silent-miss", None)`. Matches the contract's four fixed values and
  "workflow_name present for explicit and auto-match" ✓.
- `resolve_topic_dir` raising `ValueError` (a fully non-ASCII branch name
  normalizes to an empty slug, `paths.py:60-61`) — the operation guards:
  `except ValueError: topic_dir = None` → branch-only form. "The
  branch-only form otherwise" covers it semantically ✓.
- Emission ordering: `run_created` fires after prompts materialize and
  before `run_flow`; `run_completed` fires on every return path of
  `run_flow` — 126/127 spawn failures are return codes
  (`run_pipeline.py` docstring contract), so a sequential flow suffices;
  an exception escaping `run_flow` has no exit code to report and
  propagates without a completion emission (boundary, documented) ✓.
- No-events guarantees: missing pipeline returns at step 1; structural
  errors propagate at step 7 (compile) — both before any checkpoint ✓.

---

## Algorithm Design

### `PipelineHooks` (events.py)

**Responsibility**: the checkpoint surface of the pipeline domain — the
amendment delivery and the two run notifications over the platform facade,
sharing one lazily-built registry per instance.

**Algorithm:**
```
_ensure_registry():
1. IF self._registry is None:
   - registry = HookRegistry(); registry.build_once(); self._registry = registry
2. RETURN self._registry                       # ImportError propagates (single fatal case)

amend_workflow(pipeline, decision, workflow, work):
1. record = the declared_actions() entry (domain="pipeline", action="amend_workflow")
   → absent: raise ValueError("unknown hook action: pipeline.amend_workflow")
2. groups = subscriptions_for("pipeline", "amend_workflow") grouped per tool
   (enumeration order)
3. IF groups empty: RETURN merge_workflow_overlay(workflow, [])   # passthrough
4. FOR tool, subs in groups.items():
   a. amendment = WorkflowAmendment(pipeline=pipeline, decision=decision,
                                    workflow=workflow, work=work)  # fresh view, fresh buffer
   b. proxy = wrap_context(amendment)
   c. FOR sub in subs:
      - sub.hook(**build_hook_arguments(sub.hook, proxy, registry.self_context(tool)))
      - ON Exception AS reason:
        raise ValueError(f"hook {sub.name} of tool {tool} failed on "
                         f"pipeline.amend_workflow: {reason}") from reason
        # hard: stop at the first failure; the tool's buffer dies with its view
   d. IF amendment._contribution is None: continue        # never contributed — silent
   e. IF empty(amendment._contribution):                  # prompt None ∧ stages {} ∧ extend {} ∧ memory None
      - logger.warning("tool %s contributed an empty document to "
                       "pipeline.amend_workflow: discarded", tool)
      - continue
   f. contributions.append(ToolContribution(tool=tool, document=amendment._contribution))
5. RETURN merge_workflow_overlay(workflow, contributions)
```

**Errors:**
- `ValueError` (hard hook failure) → propagates through `run_pipeline` /
  `describe_pipeline` → rendered by `pipeline_cli` as a clean stderr
  message, exit non-zero; nothing has been compiled, written, or launched.
- `ImportError` (broken tool package) → propagates from `build_once` —
  the single fatal platform case; identical treatment — rendered by
  `pipeline_cli` as a clean stderr message, exit non-zero.

**Edge cases:**
- No tool packages installed → registry builds empty → step 3 short-circuit
  → the overlay is the passthrough — output byte-identical to a
  pre-hooks run.
- A tool subscribed but silent → no commit, no warning.
- `BaseException` (e.g. `KeyboardInterrupt`) → not intercepted (the
  platform convention: intercept `Exception` only).

### `merge_workflow_overlay` (overlay.py)

**Responsibility**: compose the effective workflow from the authored base
and the committed contributions — authored intent wins per slot.

**Algorithm:** (see the trace above for the full field table)
```
1. IF contributions empty: RETURN WorkflowOverlay(workflow=base, provenance=[])
2. prompt  = "\n\n".join(non-empty texts: authored first, then contributions in order) or None
3. memory  = authored block when present; else the LATER contributing tool's block
4. stages  = per name (authored names first, then fresh names):
             authored-set fields never overwritten;
             unset fields take the later contributing tool's value;
             no authored entry → fully tool-defined WorkflowStage
5. extend  = authored entries kept; a contribution entry under an authored
             name dropped; among tools the later entry wins per name
6. provenance = [c.tool for c in contributions]
7. RETURN WorkflowOverlay(WorkflowDocument(prompt, stages, extend, memory), provenance)
```

**Errors:** none — pure function; invalid shapes cannot occur (committed
contributions are non-empty by construction; structural validation of the
merged result belongs to `compile_flow`, which raises its
`StructuralError` unchanged, e.g. a contribution naming an unknown stage).

**Edge cases:**
- `base` None + contributions → a document exists (every committed
  contribution is non-empty).
- Authored `skip=True` (from the workflow-file or the merged runner skip)
  → unbeatable; a contributing `skip=False` overrides nothing.
- Authored `manual=False` → SET (explicit cancel) — tools cannot reopen it.
- Prompt of `""` (empty string) → drops out of the concatenation.

### `WorkflowAmendment` (amendments.py)

**Responsibility**: the read-and-contribute view of one tool.

**Algorithm:**
```
contribute(document):
1. self._contribution = document          # whole replacement; no validation here
                                            # (the delivery checks emptiness post-hoc)
```
`_contribution: WorkflowDocument | None` is a private
`field(init=False, default=None, repr=False)` — not contract surface; read
only by the delivery (same package).

**Errors:** none raised; a bad document surfaces at the consumer
(`compile_flow`) or as the empty-contribution warning.

**Edge cases:** repeat calls replace; the buffer is per-tool (per view).

### `run_pipeline` (run_pipeline.py) — changed

**Responsibility**: the run coordination — now 17 steps (Data Flow 1).

**Algorithm:** the existing 11 steps renumbered with four insertions —
new step 8 (facts), new step 9 (delivery), new steps 12-14 (composition,
statuses, creation emission), step 16 (completion emission). Exact texts
live in `goga/pipeline/CODEMANIFEST`; the field-level decisions:

- facts: `header, _, _ = parse_dsl(pipeline_path.read_text())`;
  `PipelineIdentity(name=match.name, display_name=header.name,
  description=header.description, source=match.source.value)`;
- decision: the kind-derivation table in the trace above;
- work: `branch = resolve_current_branch_name() or "unknown"`;
  `try: topic_dir = resolve_topic_dir(branch)` / `except ValueError:
  topic_dir = None`; `topic_dir.is_dir()` → `WorkIdentity(branch=branch,
  slug=topic_dir.name, year=topic_dir.parent.name)` else `WorkIdentity(branch=branch)`;
- disabled: `overlay = WorkflowOverlay(workflow=workflow, provenance=[])`
  (the merged workflow; no delivery, no registry build from the amendment
  side — the first registry build happens at the creation emission);
- statuses: hosting form only — one `assemble_status_scale()`, two
  `resolve_topic_status(topic_dir, scale)` reads (creation moment,
  completion moment).

**Errors:** unchanged channels plus the hard `ValueError` from the
amendment (before any compile/write/launch) and the `ImportError` from the
registry build.

**Edge cases:** detached HEAD / non-repo / missing git → `"unknown"`
branch, branch-only work; non-ASCII branch → `ValueError`-guarded
branch-only form; disabled layer → passthrough overlay; no subscriptions →
byte-identical behavior.

### `describe_pipeline` (describe_pipeline.py) — changed

**Responsibility**: the card composition through the same amendment layer.

**Algorithm:** 7 steps (Data Flow 2); facts identical to the run form
(`parse_dsl` header, kind derivation, unknown-branch sentinel, guarded
topic dir); delivery unless disabled; `compile_flow(...,
workflow=overlay.workflow)` in the temp dir; card
`provenance=overlay.provenance`.

**Errors:** unchanged channels + the hard `ValueError`.

**Edge cases:** disabled → passthrough overlay, `provenance=[]`;
`GOGA_SKIP_STAGES` never read (card answers composition, not a specific
run's skips).

### `PipelineCard` (pipeline_card.py) — changed

Add `provenance: list[str] = field(default_factory=list)` (import
`field`); docstring line for it. Existing constructions compile unchanged
(the default). Two cards never share the list (factory per instance).

### `pipeline_cli` (cli.py) — changed

`_run_card`: after the stage loop —

```python
if card.provenance:
    print()
    print(f"tools: {', '.join(card.provenance)}")
```

Uniform rule: the tools block is one blank line + one field line whenever
provenance is non-empty (with zero stages it follows the separator's
blank line — deterministic, and the empty-provenance output stays
byte-identical in every form).

Failure rendering: add `ValueError` and `ImportError` to the caught
tuples of `_run_card` and `_run_execution` (the hard amendment stops both
forms; the registry build's fatal `ImportError` stops every form —
platform precedent `history.py:114` catches `(ValueError, ImportError)`;
contract step 5: "Render an operation failure as a clean readable message
to stderr (no traceback)").

### `declared_actions` catalog (catalog.py) — changed

Append to `_DECLARED_ACTIONS`:

```python
Action(domain="pipeline", name="amend_workflow", error_class="hard"),
Action(domain="pipeline", name="run_created", error_class="soft"),
Action(domain="pipeline", name="run_completed", error_class="soft"),
```

`declared_actions()` sorts by `(domain, name)` → the pipeline block
orders `amend_workflow`, `run_completed`, `run_created` between
`onboarding` and `statuses`. Purely additive.

### Zone data models (identity.py, contexts.py, overlay.py)

`@dataclass(kw_only=True)` per `convention`; snake_case fields;
type-hinted; docstrings in the repo style (Args sections mirroring the
CODEMANIFEST annotations). No behavior: `PipelineIdentity` /
`WorkflowDecision` / `WorkIdentity` / `CompositionStage` /
`ToolContribution` / `WorkflowOverlay` / `RunCreated` / `RunCompleted` are
pure fact carriers. Contract invariants worth runtime guards (repo
convention `__post_init__`, cf. `PipelineEntry`): `PipelineIdentity` —
`source in ("project", "user")`; `WorkflowDecision` — `kind in
("disabled", "explicit", "auto-match", "silent-miss")`. The zone
`__init__.py` facade exposes the 11 names alphabetically in `__all__`
(the checklist's "facade import check").

---

## Cross-cutting Concerns

- **Error handling**: three channels, never mixed — hard amendment:
  `ValueError` in the platform message format, stops the command before
  any side effect; soft notifications: `logger.warning` naming tool +
  action + reason inside `emit_hook_event`, the run's exit code
  unaffected; structural composition errors (`StructuralError`,
  `WorkflowSyntaxError`, `yaml.YAMLError`): propagate unchanged from the
  unchanged compiler/parser surface. The CLI renders every channel as a
  clean stderr line, exit non-zero.
- **Logging**: `logger = logging.getLogger(__name__)` per module (repo
  convention). Zone warnings: the empty-contribution discard
  (`events.py`); emission failures warn inside the platform. Debug lines
  (`describe_pipeline.py:112` style) may log provenance/composition —
  additive, debug level.
- **Validation**: no validation inside the checkpoints (facts in, facts
  out — "the checkpoints read nothing"); emptiness validation at the
  commit boundary; structural validation of the merged overlay delegated
  to `compile_flow`; identity/decision literals guarded in
  `__post_init__`.
- **Caching**: one `HookRegistry` per `PipelineHooks` instance (lazy
  `build_once`), one `assemble_status_scale()` per run. Nothing cached
  across runs (platform rule).
- **Concurrency**: none introduced — the delivery walk is sequential by
  design (enumeration order is semantic: prompt order, later-wins).
- **Purity**: `merge_workflow_overlay` never mutates its inputs;
  `apply_skip_stages` already copy-on-write; the operations treat the
  documents tuple and the overlay as read-only after construction.

---

## Usages Analysis

### `convention`
- **What it provides**: project code style, docstring style, REPL cycle,
  test infrastructure rules.
- **Where used**: global Annotations of both changed manifests; every
  type annotation of the zone ("Apply the `convention` practice...").
- **Why chosen**: the project-wide baseline practice.
- **How exactly**: `.goga/usages/conventions.md` — kw_only dataclasses,
  relative imports, docstring structure, test placement.

### Imported Usages

- `per-tool-delivery` from `goga/hooks` — the staged delivery loop of
  `amend_workflow`: loop skeleton, primitives, tool-grouped commit.
  Path: `goga/hooks/.usages/per-tool-delivery.md`. Applied as written;
  the soft-discard leg is replaced by the hard raise (the action's
  catalog error class drives it — the practice itself defers to the
  catalog: "Treat a failure per the action's error class").
- `declaring-actions` from `goga/hooks` — the emission contract of the
  two notifications. Path: `goga/hooks/.usages/declaring-actions.md`.
  `emit_hook_event(HookRegistry(), domain, action, context_for=...)`
  with a shared-instance `context_for`.
- `registering-hooks` from `goga/hooks` — the hook signature and failure
  behavior behind every checkpoint (context/self injection, fixed offered
  names). Path: `goga/hooks/.usages/registering-hooks.md`.
- `checkpoints` from `goga/pipeline/hooks` (consumed by `goga/pipeline`)
  — the checkpoint surface consumption patterns (fact resolution,
  amend-before-compile, emit-around-launch). Path:
  `goga/pipeline/hooks/.usages/checkpoints.md`. Referenced by the zone
  paragraph of the global Annotations and by `run_pipeline` /
  `describe_pipeline`.
- `topic-paths` from `goga/history` — the branch read and topic-dir
  resolution behind `WorkIdentity`. Path:
  `goga/history/.usages/topic-paths.md`. Slug/year derive from the
  returned directory (`topic_dir.name`, `topic_dir.parent.name`) — no
  extra import needed.
- `topic-statuses` from `goga/history` — the status facts of the run
  events (`assemble_status_scale` + `resolve_topic_status`, single
  assembly, nested artifacts honored). Path:
  `goga/history/.usages/topic-statuses.md`.

Every connected practice is referenced in at least one annotation
(verified during the audit) — no orphaned practices, no unreferenced
imports.

---

## `.usages/` Update

### Cell: `goga/pipeline/hooks`

- **`checkpoints`** → `goga/pipeline/hooks/.usages/checkpoints.md`
  - Status: current (created at apply stage; verified against this
    design — amend-before-compile, emit-around-launch, passthrough, card
    form all match).
  - Additions needed: none.
  - Updates needed: none.

### Cell: `goga/pipeline`

- **`registering-hooks`** → `goga/pipeline/.usages/registering-hooks.md`
  - Status: current (created at apply stage; events table, hook
    signature, amendment semantics, integration scenarios match the
    contracts and this design).
- **`describe-pipeline`** → current (provenance field, hooks-zone
  composition, no-run-events statement synced).
- **`run-pipeline`** → current (amendment + run-events sections synced;
  hard-action and no-events guarantees match).
- **`pipeline-cli`** → current (`tools:` line spec matches the uniform
  blank+field rule).
- No new files needed — the zone-level consumer documentation lives in
  the zone's own `.usages/` (checkpoints), and the tool-author
  documentation in the domain's (registering-hooks); the category
  structure of both cells is preserved.

---

## Test Stack Trace

### General Setup

- New package `tests/pipeline/hooks/` (`__init__.py` + `conftest.py`),
  mirroring `tests/pipeline/compiler/` and `tests/pipeline/workflow/`.
- `tests/pipeline/hooks/conftest.py` re-exports the platform boundary
  fixtures (cross-package import precedent: `tests/test_cli.py:20`):

```python
from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401
```

- Tool-package simulation: `pin_package_environment({"goga_tool_demo":
  ["demo-dist"]})` + `install_tool_package("goga_tool_demo",
  register_hooks=...)` — the platform code under test runs for real.
- Operation-level tests mock at module boundaries only
  (`mock.patch.object(_run_pipeline_module, "compile_flow"/"run_flow")` —
  the established pattern in `tests/pipeline/test_run_pipeline.py`).
- History facts in operation tests: a real `.goga/history/<year>/<slug>/`
  tree under `tmp_path` + `monkeypatch.chdir(tmp_path)` (the
  `isolated_cwd` fixture); the git branch read is mocked
  (`resolve_current_branch_name`) since tmp dirs are not repos. The tree
  is built under `current_year()` (or with `current_year` mocked to a
  fixed value) — never under a hardcoded year literal; assertions derive
  the expected year the same way, so the suite survives a year boundary.

### Source File Registry

- `goga/pipeline/hooks/__init__.py`, `identity.py`, `contexts.py`,
  `overlay.py`, `amendments.py`, `events.py`
- `goga/hooks/catalog/catalog.py`
- `goga/pipeline/pipeline_card.py`, `describe_pipeline.py`,
  `run_pipeline.py`, `cli.py`
- Tests: `tests/pipeline/hooks/test_{identity,overlay,amendments,events}.py`,
  `tests/pipeline/test_run_pipeline_hooks.py`, and extensions to
  `tests/pipeline/test_{describe_pipeline,pipeline_card,pipeline_cli}.py`
  and `tests/hooks/catalog/test_catalog.py`.

---

### Positive Tests

#### `test_merge_prompt_concatenates_authored_first_then_tools`

**Setup**: `base = WorkflowDocument(prompt="authored")`; contributions:
`[ToolContribution("t1", WorkflowDocument(prompt="one")),
ToolContribution("t2", WorkflowDocument(prompt="two"))]`.

**Input**: `merge_workflow_overlay(base, contributions)`

**Trace**:
```
merge_workflow_overlay(base, contributions)
  → texts = ["authored", "one", "two"]        # step 2, empties dropped
  → prompt = "authored\n\none\n\ntwo"          # single blank line joins
  → WorkflowOverlay(provenance=["t1", "t2"])
```

**Assertions**:
```
overlay.workflow.prompt == "authored\n\none\n\ntwo"
overlay.provenance == ["t1", "t2"]
```

**Sufficiency**: fixes the prompt precedence and separator contract — a
regression here changes every compiled flow-file's top prompt.

#### `test_merge_stage_fields_fill_only_unset_later_tool_wins`

**Setup**:
`base.stages = {"build": WorkflowStage(agent="author-agent", loop=2)}`;
`t1` contributes `WorkflowStage(agent="t1-agent", skills=["s1"])`;
`t2` contributes `WorkflowStage(agent="t2-agent", loop=5)`.

**Input**: `merge_workflow_overlay(base, [tc(t1), tc(t2)])`

**Trace**:
```
stage "build": authored agent set → blocks both tools
  authored loop=2 set → blocks t2
  skills unset → t1 sets ["s1"] (t2 sets none)
→ WorkflowStage(agent="author-agent", loop=2, skills=["s1"])
```

**Assertions**:
```
overlay.workflow.stages["build"].agent == "author-agent"
overlay.workflow.stages["build"].loop == 2
overlay.workflow.stages["build"].skills == ["s1"]
base.stages["build"].skills is None            # purity — input untouched
```

**Sufficiency**: the authored-wins + later-tool-wins rule is the core
merge semantics; this pins both directions at once.

#### `test_merge_skip_false_overrides_nothing_authored_skip_unbeatable`

**Setup**: `base.stages = {"build": WorkflowStage(skip=True)}`;
`t1` contributes `WorkflowStage(skip=False)`; fresh name `"deploy"`:
authored has no entry, `t1` contributes `WorkflowStage(skip=True)`.

**Input**: `merge_workflow_overlay(base, [tc(t1)])`

**Trace**:
```
"build": authored skip=True SET → t1's False blocked
"deploy": no authored entry → t1's skip=True fills
```

**Assertions**:
```
overlay.workflow.stages["build"].skip is True
overlay.workflow.stages["deploy"].skip is True
```

**Sufficiency**: `skip=False` is the merge's sharpest edge (three-state
semantics); prevents a tool "un-skipping" an authored/runner skip.

#### `test_merge_memory_authored_block_unbeatable_and_later_tool_wins`

**Setup**: case A — `base.memory = WorkflowMemory(max_rules=5)`, `t1`
contributes `WorkflowMemory(max_rules=99)`; case B — `base.memory=None`,
`t1` and `t2` both contribute blocks (`max_rules=7` / `max_rules=9`).

**Input**: both merges.

**Trace**:
```
A: authored block present → kept whole (max_rules=5)
B: no authored block → later tool t2 wins (max_rules=9)
```

**Assertions**:
```
A: overlay.workflow.memory.max_rules == 5
B: overlay.workflow.memory.max_rules == 9
```

**Sufficiency**: memory is whole-block, never field-merged — both legs.

#### `test_merge_extend_authored_names_win_and_later_tool_wins`

**Setup**:
`base = WorkflowDocument(extend={"audit": WorkflowExtendStage(
after=["build"], body={"title": "Audit"})})`;
`t1` contributes `extend={"audit": WorkflowExtendStage(before=["build"],
body={"title": "X"}), "notify": WorkflowExtendStage(after=["deploy"],
body={"title": "N1"})}`;
`t2` contributes `extend={"notify": WorkflowExtendStage(after=["audit"],
body={"title": "N2"})}`.

**Input**: `merge_workflow_overlay(base, [tc(t1), tc(t2)])`

**Trace**:
```
"audit": under an authored name → t1's entry dropped, the authored
  after=["build"] entry kept
"notify": fresh name → t1 sets it, t2 replaces (later tool wins)
```

**Assertions**:
```
overlay.workflow.extend["audit"].after == ["build"]
overlay.workflow.extend["notify"].after == ["audit"]
len(overlay.workflow.extend) == 2
base.extend["audit"].after == ["build"]        # purity — input untouched
```

**Sufficiency**: pins the last authored-wins slot — extend; a regression
here silently reorders or drops new stages in every compiled flow with
extend entries.

#### `test_merge_empty_base_tools_build_the_document`

**Setup**: base `None`; `t1` contributes `WorkflowDocument(prompt="one",
stages={"build": WorkflowStage(agent="a")})`; `t2` contributes
`WorkflowDocument(prompt="two")`.

**Input**: `merge_workflow_overlay(None, [tc(t1), tc(t2)])`

**Trace**:
```
contributions non-empty → no passthrough short-circuit
no authored layer → texts ["one", "two"] → prompt "one\n\ntwo"
stage "build": no authored entry → fully tool-defined (agent="a")
provenance ["t1", "t2"]; the document exists (every contribution non-empty)
```

**Assertions**:
```
overlay.workflow is not None
overlay.workflow.prompt == "one\n\ntwo"
overlay.workflow.stages["build"].agent == "a"
overlay.provenance == ["t1", "t2"]
```

**Sufficiency**: the silent-miss + contributing-tool composition — pins
the "first tool text becomes the prompt" rule, the fully tool-defined
stage, and the invariant "a None workflow with a non-empty provenance
never occurs".

#### `test_merge_passthrough_short_circuit_returns_base_object`

**Setup**: `base = WorkflowDocument(prompt="x")`.

**Input**: `merge_workflow_overlay(base, [])` and
`merge_workflow_overlay(None, [])`.

**Trace**:
```
contributions empty → WorkflowOverlay(workflow=base, provenance=[])
```

**Assertions**:
```
overlay.workflow is base            # the passed object itself
overlay.provenance == []
merge(None, []).workflow is None
```

**Sufficiency**: the no-tool-packages guarantee — byte-identical runs.

#### `test_amend_workflow_commits_per_tool_and_merges`

**Setup**: pinned environment with two tool packages. The first
subscribes `("pipeline", "amend_workflow", "hardening", hook)` where
`hook(context)` reads `context.pipeline.name`, `context.decision.kind`,
`context.workflow` (recording `id(context.workflow)` into its `self`
context) and calls `context.contribute(WorkflowDocument(prompt="harden"))`.
The second (`goga_tool_second`) subscribes the same address with a hook
that records `id(context.workflow)` and `context.workflow.prompt` into
its own `self` AFTER contributing `WorkflowDocument(prompt="second")`.

**Input**: `PipelineHooks().amend_workflow(pipeline=PipelineIdentity(
name="deploy", description="d", source="project"), decision=...,
workflow=WorkflowDocument(prompt="authored"), work=WorkIdentity(branch="b"))`

**Trace**:
```
amend_workflow(...)
  → registry.build_once()                     # real enumeration, one build
  → subscriptions_for("pipeline", "amend_workflow") → 2 subscriptions, 2 tools
  → per tool: WorkflowAmendment(view over the SAME workflow) → wrap_context
    → build_hook_arguments → hook(context=proxy)   # only "context" declared
    → contribute(...) sets the tool's own buffer
  → both non-empty → ToolContribution per tool
  → merge → overlay
```

**Assertions**:
```
overlay.workflow.prompt == "authored\n\nharden\n\nsecond"
overlay.provenance == [tool_id_of("goga_tool_demo"), tool_id_of("goga_tool_second")]
first_seen_id == second_seen_id            # the same original workflow object
second_seen_prompt == "authored"           # the first tool's contribution invisible
```

**Sufficiency**: the full delivery path over the real platform — registry,
view, proxy, projection, buffer, commit, merge — plus the mutually-blind
guarantee: every view wraps the same original workflow, no tool sees
another's contribution, buffers are per-view (the guard against the layer
silently becoming staged accumulation).

#### `test_amend_workflow_registry_built_once_across_checkpoints`

**Setup**: pinned environment (boundary mock returned by
`pin_package_environment`); a tool subscribing both `amend_workflow` and
`run_completed`.

**Input**: one `PipelineHooks` instance: `amend_workflow(...)` then
`emit_run_completed(...)`.

**Trace**:
```
amend → _ensure_registry (build #1)
emit_run_completed → _ensure_registry (no rebuild)
```

**Assertions**:
```
boundary.call_count == 1        # packages_distributions read exactly once
```

**Sufficiency**: the "one registry per run" requirement — enumeration is
the expensive side effect.

#### `test_run_pipeline_full_event_sequence_around_launch`

**Setup**: `afm_dir` fixture (AFM_DIR → tmp); a minimal real pipeline file
in `project_dir`; workflow absent (silent-miss); pinned env with a tool
subscribing `run_created` and `run_completed`, recording received facts
into its `self` context; `compile_flow` and `run_flow` mocked
(`run_flow` → `3`); `resolve_current_branch_name` mocked →
`"feature-demo"`; tmp `.goga/history/<current_year()>/feature-demo/`
with `todo.md`.

**Input**: `run_pipeline("deploy", project_dir, user_dir, port=50321)`

**Trace**:
```
run_pipeline(...)
  → facts: identity (parse_dsl header), decision ("silent-miss", None),
    work ("feature-demo", "feature-demo", current_year())
  → amend (silent-miss keeps the layer active) → passthrough (no subs on
    amend_workflow for this tool) → overlay.workflow None
  → compile_flow(workflow=None ...)           # mocked documents tuple
  → order_stages → composition [CompositionStage("build", "Build")]
  → statuses ["todo"]                          # real scale + topic dir
  → emit_run_created (records: composition ids, runtime_dir posix)
  → run_flow → 3
  → statuses recomputed → emit_run_completed (exit_code=3)
  → return 3
```

**Assertions**:
```
result == 3
created_facts["pipeline"].name == "deploy"
created_facts["decision"].kind == "silent-miss"
created_facts["composition"] == [CompositionStage(id="build", title="Build")]
created_facts["statuses"] == ["todo"]
created_facts["runtime_dir"] == afm_dir.as_posix()
completed_facts["exit_code"] == 3
order: created recorded before run_flow called, completed after
```

**Sufficiency**: the feature's headline behavior — the event sequence and
fact fidelity of a real run.

#### `test_describe_pipeline_reports_provenance_through_same_layer`

**Setup**: pinned env with a tool contributing `prompt="tool-text"` via
`amend_workflow`; a workflow file in `.goga/workflows/deploy.yml` with
`prompt: "authored"`.

**Input**: `describe_pipeline("deploy", project_dir, user_dir,
workflow=None, no_workflow=False)` — real `compile_flow` into the temp
dir (no mocks beyond the tool env).

**Trace**:
```
describe_pipeline(...)
  → resolve_workflow → auto-match → WorkflowDocument(prompt="authored")
  → facts → amend → overlay(prompt="authored\n\ntool-text", ["<tool>"])
  → compile_flow(overlay.workflow) → temp flow-file → discarded
  → PipelineCard(provenance=["<tool>"])
```

**Assertions**:
```
card.provenance == ["<tool-id>"]
card.name == <authored header name>
```

**Sufficiency**: card == run composition guarantee with tools installed.

#### `test_cli_card_renders_tools_line_and_stays_byte_identical_without_it`

**Setup**: two `PipelineCard`s — one with `provenance=["t1", "t2"]`, one
default; `capsys`.

**Input**: render both through the card path (factor the rendering via
the `_run_card` flow with a stubbed `describe_pipeline`).

**Trace**:
```
card with provenance → stage blocks, blank, "tools: t1, t2"
card without → stage blocks only
```

**Assertions**:
```
out_with.endswith("\ntools: t1, t2\n")
out_without does not contain "tools:"
out_without == <exact pre-feature expected bytes>   # byte-identical
```

**Sufficiency**: the CLI surface contract — additive only.

#### `test_catalog_carries_the_three_pipeline_records`

**Setup**: none (pure catalog read).

**Input**: `declared_actions()`

**Trace**:
```
_DECLARED_ACTIONS (13 records) → sorted by (domain, name)
```

**Assertions**:
```
[("pipeline", "amend_workflow", "hard"),
 ("pipeline", "run_completed", "soft"),
 ("pipeline", "run_created", "soft")] all present;
pipeline block ordered between onboarding and statuses
```

**Sufficiency**: the address triple must exist exactly once, correctly
classed — the emission resolves against it.

---

### Negative Tests

#### `test_amend_workflow_hard_failure_stops_command_and_discards`

**Setup**: pinned env; tool subscribes `amend_workflow` with
`hook(context)` raising `RuntimeError("boom")` after calling
`context.contribute(WorkflowDocument(prompt="x"))`; a second tool
subscribes the same address with a working hook.

**Input**: `PipelineHooks().amend_workflow(...)` (facts as above).

**Trace**:
```
amend_workflow(...)
  → tool #1 hook raises
  → ValueError("hook ... of tool ... failed on pipeline.amend_workflow: boom")
  → walk stops — tool #2 never called
```

**Assertions**:
```
pytest.raises(ValueError, match="pipeline.amend_workflow: boom")
merge never ran → no overlay returned; tool #2's hook not called
```

**Sufficiency**: the platform's first hard action — failure isolation,
message shape, first-failure stop.

#### `test_run_pipeline_hard_amendment_renders_clean_error_no_launch`

**Setup**: as the positive run test, but the tool's `amend_workflow` hook
raises; `run_flow` mocked with a call recorder.

**Input**: `pipeline_cli` argv `["deploy", "--port", "50321"]` (or
`run_pipeline` directly + the CLI wrapper for the message).

**Trace**:
```
run → step 9 amend → ValueError → propagates
run_flow.assert_not_called(); prompts dir untouched; no events emitted
```

**Assertions**:
```
capsys err contains "pipeline.amend_workflow" and "boom"; no traceback
exit code != 0
```

**Sufficiency**: the hard path must fail before any side effect and
render cleanly (the `ValueError` catch addition).

#### `test_emit_soft_failure_warns_and_never_affects_exit_code`

**Setup**: pinned env; tool's `run_completed` hook raises; `run_flow`
mocked → `0`.

**Input**: full `run_pipeline` flow.

**Trace**:
```
emit_run_completed → emit_hook_event intercepts → logger.warning
run continues → return 0
```

**Assertions**:
```
result == 0
caplog contains a warning naming the tool, "run_completed", "boom"
```

**Sufficiency**: soft class — the run's outcome is never hostage to a
reporter.

#### `test_spawn_failure_still_emits_completion_with_code`

**Setup**: as the positive run test (pinned env, event-recording tool
keeping facts in its `self` context); `compile_flow` mocked;
`run_flow` mocked → `127` (the afm binary missing from PATH).

**Input**: `run_pipeline("deploy", project_dir, user_dir, port=50321)`

**Trace**:
```
run_pipeline(...)
  → facts → amend → compile (mocked) → prompts materialize
  → emit_run_created
  → run_flow → 127                    # a return code, not an exception
  → statuses recomputed → emit_run_completed(exit_code=127)
  → return 127
```

**Assertions**:
```
result == 127
completed_facts["exit_code"] == 127
completed recorded after created; no exception raised
```

**Sufficiency**: pins the requirement's sharpest leg — "every
launch-attempt return path" includes spawn failures; a reporter relying
on `run_completed` must hear about a failed launch too.

#### `test_missing_pipeline_and_structural_error_fire_no_events`

**Setup**: event-recording tool installed; case A — unknown pipeline
name; case B — a malformed workflow file (valid name resolution path).

**Input**: `run_pipeline("nope", ...)`; `run_pipeline("deploy", ...)` with
the malformed workflow.

**Trace**:
```
A: return 1 at discovery — checkpoints unreached
B: WorkflowSyntaxError propagates from resolve_workflow (step 6) — before
   the delivery
```

**Assertions**:
```
A: result == 1; zero events recorded
B: pytest.raises(WorkflowSyntaxError); zero events recorded
```

**Sufficiency**: the no-events guarantee for failing moments.

---

### Edge Case Tests

#### `test_work_identity_unknown_branch_and_empty_slug_guard`

**Setup**: `resolve_current_branch_name` mocked → `None`; then →
`"Ветка"` (fully non-ASCII — every character drops, slug empty).

**Input**: `run_pipeline` fact resolution (observed via the recorded
`work` of `emit_run_created`).

**Trace**:
```
None → branch "unknown" → resolve_topic_dir("unknown") missing → branch-only
"Ветка" → normalize_topic_slug("Ветка") == "" → resolve_topic_dir raises
  ValueError → guarded → branch-only
(a partial-ASCII name such as "Бranched" slugs to "ranched" — it covers the
 missing-directory leg, not the guard)
```

**Assertions**:
```
work.branch == "unknown" / work.slug is None / work.year is None   (case A)
work.branch == "Ветка" / slug is None / year is None               (case B)
no exception; events still fired
```

**Sufficiency**: the two approved defect fixes at their exact seams — no
run ever fails on git identity.

#### `test_empty_contribution_discarded_with_warning_silent_tool_ok`

**Setup**: pinned env with two tools: one contributes
`WorkflowDocument()` (all defaults), one subscribes but never calls
`contribute`.

**Input**: `amend_workflow(...)` with `base=WorkflowDocument(prompt="a")`.

**Trace**:
```
tool #1: buffer set, empty → warning, discard
tool #2: buffer None → silent
merge with [] → passthrough
```

**Assertions**:
```
overlay.workflow.prompt == "a"; overlay.provenance == []
caplog has exactly one discard warning (names tool #1)
```

**Sufficiency**: the empty/silent distinction — warning exactly when a
tool tried and produced nothing.

#### `test_disabled_decision_skips_delivery_compiles_raw_and_still_emits`

**Setup**: env `GOGA_WORKFLOW_DISABLED=1`; event-recording tool with an
amendment hook that would fail loudly if called; `run_flow` → `0`;
`GOGA_SKIP_STAGES` unset.

**Input**: `run_pipeline("deploy", ...)`.

**Trace**:
```
decision ("disabled", None) → no amend call
overlay = WorkflowOverlay(workflow=None, provenance=[])
compile_flow(workflow=None)
emit_run_created(decision.kind == "disabled", overlay.provenance == [])
emit_run_completed(exit_code=0)
```

**Assertions**:
```
amend hook not called
created_facts["decision"].kind == "disabled"
created_facts["provenance"] == []
result == 0
```

**Sufficiency**: the layer-off leg — raw composition, live events.

#### `test_describe_pipeline_disabled_reports_raw_composition`

**Setup**: a workflow file `.goga/workflows/deploy.yml` exists
(`prompt: "authored"`); pinned env with a tool whose `amend_workflow`
hook would fail loudly if called; `isolated_cwd`.

**Input**: `describe_pipeline("deploy", project_dir, user_dir,
workflow=None, no_workflow=True)` — real `compile_flow` into the temp
dir.

**Trace**:
```
step 2: resolve_workflow(..., no_workflow=True) → None
  → decision ("disabled", None)
step 3: disabled → no delivery, overlay is the passthrough
  (workflow=None, provenance=[])
step 4: compile the raw authored DSL → card without the tool layer
```

**Assertions**:
```
amend hook not called
card.provenance == []
card.stages == <raw composition — same as a no-workflow-file compile>
no exception
```

**Sufficiency**: the card-form disabled leg is its own code path in
`describe_pipeline` — pins "card == run composition" with the layer off
and the empty-provenance guarantee.

#### `test_workflow_decision_kind_derivation_matrix`

**Setup**: four env configurations (disabled; explicit+exists; explicit+
missing; no-name auto-match hit and miss).

**Input**: `run_pipeline` fact resolution (observed via recorded facts).

**Trace**:
```
disabled → ("disabled", None)
explicit+exists → ("explicit", "ci")
explicit+missing → ("silent-miss", None)
auto-match hit → ("auto-match", "deploy"); miss → ("silent-miss", None)
```

**Assertions**: each recorded `decision` matches the table exactly.

**Sufficiency**: the kind vocabulary drives tool behavior — a mis-derived
kind silently misinforms every subscriber.

#### `test_pipeline_card_provenance_default_factory_isolated`

**Setup**: two `PipelineCard(name="a", description="d", stages=[])`
constructions (no provenance).

**Input**: mutate `card_a.provenance.append("x")`.

**Trace**:
```
default_factory=list per construction → independent lists
```

**Assertions**:
```
card_b.provenance == []
```

**Sufficiency**: the classic shared-mutable-default regression the field
exists to avoid.

#### `test_zone_facade_exports_exactly_the_contract`

**Setup**: import `goga.pipeline.hooks`.

**Input**: `sorted(goga.pipeline.hooks.__all__)`.

**Assertions**:
```
__all__ == ["CompositionStage", "PipelineHooks", "PipelineIdentity",
            "RunCompleted", "RunCreated", "ToolContribution",
            "WorkIdentity", "WorkflowAmendment", "WorkflowDecision",
            "WorkflowOverlay", "merge_workflow_overlay"]
each name importable from the package root
```

**Sufficiency**: the facade IS the contract surface (Python rules:
only `__all__` names constitute it).

#### `test_statuses_recomputed_at_completion_and_branch_only_stays_empty`

**Setup**: hosting form — `todo.md` present, a `completed/plan.md`
written by a fake "run" (the `run_flow` mock writes it); branch-only —
no topic dir.

**Input**: both runs with an event-recording tool.

**Trace**:
```
hosting: created statuses ["todo"] → completed statuses ["done"]
         (completed/plan.md outranks todo — maximal-present recomputed at
          the completion moment)
branch-only: [] at both moments; assemble_status_scale never called
             (assert via the enumeration boundary)
```

**Assertions**:
```
created_facts["statuses"] == ["todo"]
completed_facts["statuses"] == ["done"]
branch-only: both == [] and boundary call_count == 1  # only the pipeline registry build
```
**Sufficiency**: completion is a fact of the completion moment, not a
replay of the creation snapshot — and the branch-only form costs no scale
assembly.

**Sufficiency**: completion is a fact of the completion moment, not a
replay of the creation snapshot — and the branch-only form costs no scale
assembly.

---

## Additional Instructions for the Implementation Agent

- Implement in dependency order: catalog records → zone data models
  (`identity.py` → `contexts.py` → `overlay.py` → `amendments.py`) →
  `events.py` + facade `__init__.py` → `pipeline_card.py` →
  `describe_pipeline.py` → `run_pipeline.py` → `cli.py`.
- Relative imports only inside the zone (`from ...hooks import` for the
  platform, `from ..workflow import` never needed directly by `events.py`
  beyond type hints, `from .identity import ...` locally).
- Do not touch `goga/pipeline/workflow`, `goga/hooks` platform modules,
  or the compiler — the zone and the two operations are the whole change
  surface (plus catalog records and the card/CLI edits).
- The hard-failure message format must copy the platform's
  (`emit.py:97-99`) verbatim shape: hook name, tool, address, reason.
- `mock.patch.object(<module>, "run_flow"/"compile_flow")` at the
  consumer module — never patch deep modules (per the recorded feedback
  on module-shadowed mocks).
- Deferred from the plan's non-cell deliverables (unchanged):
  `docs/features/pipelines/hooks.md` + mkdocs traceability belong to the
  documentation task items, not the code cells.
