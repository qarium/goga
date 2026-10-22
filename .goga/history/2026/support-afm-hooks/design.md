# Design Document: `support-afm-hooks`

<!-- `support-afm-hooks` — the topic directory under `.goga/history/2026/support-afm-hooks/` -->

## Contract Changes

### Changed CODEMANIFEST Files

- `goga/hooks/catalog/CODEMANIFEST`: three `Requirements` bullets added to `declared_actions`
  — the thirteen pipeline stage-transition actions (one grouped bullet), `run_resumed`, and
  `run_interrupted`, all `domain="pipeline"`, `error_class="soft"`. No other change; `Action`
  and the footer are untouched.
- `goga/pipeline/hooks/CODEMANIFEST`: four new types in `contexts.py` (`RunIdentity`,
  `StageTransition`, `RunEvent`, `StageEvent`); two new methods on `PipelineHooks`
  (`emit_run_event`, `emit_stage_event`); the global `Annotations` and the footer
  `Description` extended with the bridged mid-run events; one `PipelineHooks` requirement
  bullet extended (one registry per event process).
- `goga/pipeline/CODEMANIFEST`: `Imports` from `goga/pipeline/hooks` extended with the four
  new types; the inline `argparse` practice amended (two → three subcommands — `hook`); a
  global-`Annotations` paragraph on the bridge; `write_afm_config` extended (observer hook
  entry); four new routines in `hook_bridge.py` (`run_hook`, `map_event_action`,
  `build_run_event`, `build_stage_event`); `pipeline_cli` extended (third subcommand, five
  operations); footer `Description` updated.

### New Entities

- `RunIdentity(run_id, run_dir, root_dir, resumed)` — the run identity carried by every
  bridged event; `goga/pipeline/hooks/contexts.py`.
- `StageTransition(id, name, from_status, to_status, phase)` — the stage facts of one bridged
  stage event; `goga/pipeline/hooks/contexts.py`.
- `RunEvent(pipeline, run, event_id, occurred_at, reason="")` — the read-only context of a
  run-level bridged event; `goga/pipeline/hooks/contexts.py`.
- `StageEvent(pipeline, run, stage, event_id, occurred_at, reason="")` — the read-only
  context of a stage-level bridged event; `goga/pipeline/hooks/contexts.py`.
- `run_hook() -> exit_code: int` — the afm-facing bridge entry; one short-lived process per
  event; `goga/pipeline/hook_bridge.py`.
- `map_event_action(event) -> action: str | None` — the curated filter mapping afm lifecycle
  event names onto platform action names; `goga/pipeline/hook_bridge.py`.
- `build_run_event(payload) -> RunEvent` — composes the run-level context from the parsed
  payload; `goga/pipeline/hook_bridge.py`.
- `build_stage_event(payload) -> StageEvent` — composes the stage-level context from the
  parsed payload; `goga/pipeline/hook_bridge.py`.

### Changed Entities

- `declared_actions()` (`goga/hooks/catalog/catalog.py`) — returns 15 additional pipeline
  records (13 verbatim stage names + `run_resumed` + `run_interrupted`); the return stays
  sorted by `(domain, name)`; no existing record rewritten.
- `PipelineHooks` (`goga/pipeline/hooks/events.py`) — two new soft-emission methods
  delegating to `emit_hook_event` with a shared read-only context instance.
- `write_afm_config(agent)` (`goga/pipeline/afm_config.py`) — the written file additionally
  carries goga's observer hook entry in the global `hooks` layer; signature unchanged.
- `pipeline_cli(argv)` (`goga/pipeline/cli.py`) — third subcommand `hook` (no options)
  dispatching to `run_hook`; five operations total.

### Deleted Entities

- None.

### Usages and Annotations Changes

- `argparse` (inline, `goga/pipeline`) — amended: three subcommands; `hook` has no options
  and receives the event through the process environment and stdin.
- Global `Annotations` (`goga/pipeline`) — new paragraph: the run interior arrives through
  the afm-facing machinery of this cell; the bridging is observer-only; `afm` practice
  referenced for the lifecycle-hooks mechanism.
- Global `Annotations` (`goga/pipeline/hooks`) — the zone description extended with the
  bridged mid-run events (short-lived process composes the contexts; curated filtering and
  vocabulary mapping stay with the caller; one registry per event process).
- `write_afm_config` annotations — the composed content and the `afm` application note
  extended with the observer hook entry; two new requirement bullets and one constraint
  bullet (the entry is fixed; no secret env references of its own).
- `run_hook` / `map_event_action` / `build_run_event` / `build_stage_event` annotations —
  written from scratch per the annotations standard (purpose, `Algorithm:`, `Requirements:`,
  `Constraints:`), referencing `afm` and `convention`.
- `pipeline_cli` annotations — dispatch list extended to five operations; the parser step
  describes the `hook` subparser; one new requirement bullet (the hook subcommand prints
  nothing on the happy path).

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Phase 3 validation found no defects: `goga lint` reports 91 cells, 0 errors; the
  three manifests parse as valid 3-section documents; the four consistency dimensions
  (interface↔type, type↔mutation, interface↔interface, annotations↔entity) were verified
  against the live code and pass. The seven annotation references that motivated lint fixes
  in the apply-architecture stage (`AFM_*`, `event_id`, `occurred_at`, `reason`,
  `from_status`/`to_status`) are already plain text in the current manifests — nothing to
  re-fix.

One `.usages/` supplement was applied with user approval during Phase 4 Step 6 (see
`.usages/` Update below) — a documentation gap, not a manifest defect.

## Entity Interaction and Data Flow

### Interaction Diagram

```
afm (external binary, run by run_flow inside the container)
  │  spawns per lifecycle event: sh -c "python3 -m goga.pipeline hook"
  │  CWD = flow root_dir; JSON payload on stdin; AFM_* in the (inherited) env
  ▼
goga.pipeline.__main__ ── ensure_in_docker() ──► goga.docker
  │ pipeline_cli(argv)
  ▼
goga.pipeline.cli::pipeline_cli  ── parse (argparse, subcommand "hook") ──► dispatch
  │ run_hook()
  ▼
goga.pipeline.hook_bridge::run_hook
  │ 1. AFM_HOOK_EVENT ──► map_event_action ──► action | None
  │        │ None (script events, flow_started/finished/failed, unknown) ──► return 0
  │        │      (fast path: no platform module imported — verified goal)
  │ 2. stdin ──► json parse ──► payload: dict         (damaged ──► Error + exit 1)
  │ 3. action ∈ {run_resumed, run_interrupted}?
  │        ├─ yes ──► build_run_event(payload)  ──► RunEvent
  │        └─ no  ──► build_stage_event(payload) ──► StageEvent
  │ 4. from .hooks import PipelineHooks   (function-local: after the filter)
  │    PipelineHooks().emit_run_event / emit_stage_event(action, context)
  ▼
goga.pipeline.hooks.events::PipelineHooks
  │ _ensure_registry() ──► HookRegistry (built once per event process)
  │ emit_hook_event(registry, "pipeline", action, context_for=lambda _: context)
  ▼
goga.hooks.dispatch.emit::emit_hook_event
  │ resolves domain/action against declared_actions()  ◄── goga.hooks.catalog
  │        (the 15 new soft pipeline records live here)
  │ per subscription: wrap_context (read-only proxy) + build_hook_arguments + call
  │ soft error class: a failing hook ──► logger.warning, sequence continues
  ▼
goga_tool_* subscriber hooks  (context: RunEvent | StageEvent — reads only)

Registration side (once per run, before the launch):
goga.pipeline.run_pipeline ── write_afm_config(agent) ──► ~/.afm/config.yaml
  content: client.command? + theme/open_browser/proxy.enabled/prompts_dir
         + hooks: [{id: goga, events: all, command: python3 -m goga.pipeline hook,
                    inherit_env: true}]          (timeout/retries omitted ── afm defaults)
```

### Data Flows

**Flow 1 — registration (once per run).** `run_pipeline` step 16 calls
`write_afm_config(config.pipeline.agent)`. The routine resolves the agent wrapper
(`resolve_wrapper_path`), composes the content dict — optional `client` block, the four
static fields, and now the `hooks` list with goga's observer entry — and serializes with
`yaml.safe_dump` to the fixed path `/home/goga/.afm/config.yaml`. Nothing is printed. On the
next `afm run`, afm unions the global layer (goga-authored) with project/flow/stage layers
and invokes the hook once per lifecycle event.

**Flow 2 — non-curated event (the fast path).** afm spawns the hook process for an event
outside the curated vocabulary (script events, `flow_started` / `flow_finished` /
`flow_failed`, unknown names). `run_hook` reads `AFM_HOOK_EVENT`, `map_event_action`
returns `None`, the process returns exit 0 — without importing any `goga.hooks` /
`goga.pipeline.hooks` module and without building the registry. stdin is not read.

**Flow 3 — curated stage event.** afm spawns the process with, e.g.,
`AFM_HOOK_EVENT=stage_execution_started` and the full JSON payload on stdin. The curated
filter resolves the verbatim action name; the payload is parsed; `build_stage_event`
composes `StageEvent(pipeline=flow.name, run=RunIdentity(...), stage=StageTransition(id,
name, from_status=stage.from, to_status=stage.to, phase), event_id, occurred_at,
reason=payload.get("reason", ""))`; `PipelineHooks().emit_stage_event(action, context)`
delivers the shared read-only context to every subscriber of
`pipeline / stage_execution_started`; the process returns 0. Subscriber failures warn inside
the platform and do not change the exit code.

**Flow 4 — curated run-level event.** Same as Flow 3 with `AFM_HOOK_EVENT=flow_resumed`
(maps to `run_resumed`) or `flow_interrupted` (maps to `run_interrupted`); the context is
composed by `build_run_event` (no stage block).

**Flow 5 — bridge-internal failure.** Damaged stdin (unparseable JSON, or a JSON value that
is not an object), a missing flow block, a missing required event fact, or a missing stage
block on a stage-level event: the builders raise a clean `ValueError` naming the missing
fact; `run_hook` renders `Error: <reason>` to stderr and returns 1. afm records the
non-zero exit in the per-hook log (`.afm/runs/<run-id>/hooks/goga.log`) and warns on the
dashboard; the run is unaffected either way (observer semantics).

### Entity Dependencies

Cell graph (from `goga schema`; no cycles; the change rides existing edges plus the
type-extension of one):

```
goga/hooks/catalog (leaf)                 [+15 records]
    ▲ declared_actions
goga/hooks (facade) ── goga/hooks/dispatch, goga/hooks/registry, goga/hooks/tools
    ▲ HookRegistry, wrap_context, build_hook_arguments, emit_hook_event, declared_actions
goga/pipeline/hooks                       [+4 types, +2 methods]
    deps: goga/hooks, goga/pipeline/workflow (both unchanged)
    ▲ PipelineHooks, RunIdentity, StageTransition, RunEvent, StageEvent (+checkpoints usage)
goga/pipeline                             [+hook_bridge.py; write_afm_config, pipeline_cli modified]
    deps: goga/pipeline/hooks (edge strengthened with the 4 new types), + unchanged others
```

Initialization order for a bridged emission (one process): `run_hook` → `map_event_action`
(pure, no imports) → parse → build context (zone dataclasses) → `PipelineHooks()` (cheap —
no enumeration at construction) → first emission builds the `HookRegistry` once
(`build_once`) → delivery. The zone surface instance is created per event process and dies
with it; no cross-event state exists anywhere in the bridge.

Dependents: `goga/hooks`, `goga/hooks/tools`, `goga/hooks/dispatch` consume
`declared_actions` — additive change, signature unchanged. `goga/commands/pipeline`
consumes only the `pipeline-cli` / `registering-hooks` practices of `goga/pipeline` —
additive (its argv composition stays `list`/`run`).

## Code Stack Trace

All traces verified against the live sources (`events.py`, `emit.py`, `delivery.py`,
`catalog.py`, `cli.py`, `afm_config.py`, `__main__.py`, `run_pipeline.py`), the `afm`
practice (`.goga/usages/cooks/afm.md`), and the afm binary itself (`/srv/afm` — YAML/JSON
struct tags recovered via `strings`).

### Trace: `declared_actions` (changed)

#### Chain
1. **Input**: call with no arguments (from `emit_hook_event` address resolution, `goga hooks`
   inspection, or tests).
2. **Step**: return `sorted(_DECLARED_ACTIONS, key=(domain, name))` — the 15 new records
   join the pipeline group; the sort places them as `run_interrupted`, `run_resumed`,
   `stage_approved`, `stage_execution_started`, `stage_failed`, `stage_finished`,
   `stage_paused`, `stage_plan_ready`, `stage_planning_started`,
   `stage_question_answered`, `stage_question_asked`, `stage_retry_scheduled`,
   `stage_retry_started`, `stage_resumed`, `stage_revision_started` after `amend_workflow`,
   `run_completed`, `run_created` → checkpoint: records exist and are unique; the
   `(domain, name)` pairs do not collide with the existing 34 records — verified against the
   current `_DECLARED_ACTIONS` list. **passed**
3. **Step**: consumers — `emit_hook_event` resolves `pipeline / <action>` for the 15 new
   addresses → checkpoint: resolution is data-driven, no code change needed in dispatch.
   **passed**
4. **Output**: `list[Action]`, 49 records total (34 + 15), deterministic order.

#### Checkpoint Summary
- Uniqueness and ordering: passed.
- Additivity (no existing record rewritten): passed — the manifest forbids rewriting
  published records; the diff adds only.

### Trace: `RunIdentity` / `StageTransition` / `RunEvent` / `StageEvent` constructors (new)

#### Chain
1. **Input**: keyword construction from `build_run_event` / `build_stage_event` (the only
   production constructors; tests construct directly).
2. **Step**: `@dataclass(kw_only=True)` field assignment, no validation logic — matches
   `CompositionStage` / `RunCreated` / `RunCompleted` precedent in `contexts.py` →
   checkpoint: the file already imports `dataclass` and uses `from __future__ import
   annotations`; the new classes follow the identical shape. **passed**
3. **Step**: `RunEvent.reason` and `StageEvent.reason` default to `""` — fields with
   defaults sit last in both signatures → checkpoint: dataclass ordering rule satisfied
   (no non-default field after a default field). **passed**
4. **Step**: delivery — the platform's `wrap_context` proxy resolves attribute reads on the
   instance and blocks writes → checkpoint: plain dataclass attributes are readable through
   `_DeliveryProxy.__getattr__` (verified in `delivery.py`); read-only semantics come from
   the platform, not the model. **passed**
5. **Output**: frozen? No — plain (non-frozen) `kw_only` dataclasses like the existing
   contexts; read-only enforcement is the platform's proxy at delivery time.

#### Checkpoint Summary
- Dataclass conventions (`kw_only=True`, Google docstrings, `convention` practice): passed.
- Field/default ordering: passed.
- Facade: the four names must join `goga/pipeline/hooks/__init__.py` (`__all__` 11 → 15)
  — required by `checkpoints.md`, whose examples import them from the zone facade.

### Trace: `PipelineHooks.emit_run_event` (new)

#### Chain
1. **Input**: `action: str` (a curated run-level action name), `context: RunEvent` (built by
   the bridge; the shared read-only instance).
2. **Step**: `self._ensure_registry()` — builds the `HookRegistry` once per surface (per
   event process) → checkpoint: existing lazy pattern reused; construction of `PipelineHooks`
   stays cheap. **passed**
3. **Step**: `emit_hook_event(registry, "pipeline", action, context_for=lambda _tool:
   context)` → checkpoint: `emit_hook_event` resolves `pipeline / action` against
   `declared_actions()` — the address exists once the catalog carries the 15 records
   (implementation dependency: catalog first). `context_for` returning the same instance for
   every tool satisfies "one shared read-only context instance" — `emit_hook_event` builds
   one view per distinct tool, all wrapping the same object. **passed**
4. **Step**: per subscription — `wrap_context(view)` (read-only proxy),
   `build_hook_arguments(hook, view, registry.self_context(tool))` (the hook receives only
   the parameters it declares: `context`, `self`), call → checkpoint: verified in
   `delivery.py` / `emit.py`; nothing collected, nothing returned. **passed**
5. **Step**: failure handling — the record's `error_class` is `soft`: a raising hook logs
   `WARNING` ("hook %s of tool %s failed on pipeline.%s: %s") and the sequence continues;
   the method returns `None` normally → checkpoint: matches the manifest Requirements
   (fire-and-forget; nothing outside the emission affected). **passed**
6. **Output**: `None`; side effects — subscriber hooks ran, warnings logged.

#### Checkpoint Summary
- Address resolution against the extended catalog: passed (catalog lands first in the
  implementation order).
- Shared-context / soft-failure semantics: passed — identical mechanics to
  `emit_run_created`, minus context construction (the caller-built context is the point of
  the bridged methods).

### Trace: `PipelineHooks.emit_stage_event` (new)

Identical chain to `emit_run_event` with `context: StageEvent` and the stage-level action
names. All checkpoints pass for the same reasons; the two methods are intentionally
symmetric (one per context type — the signatures stay typed, no union parameter).

### Trace: `map_event_action` (new)

#### Chain
1. **Input**: `event: str` — the value of `AFM_HOOK_EVENT` as delivered by afm.
2. **Step**: dictionary lookup in a module-level frozen mapping: the thirteen stage names
   map to themselves; `flow_resumed → run_resumed`; `flow_interrupted → run_interrupted`
   → checkpoint: the mapping is a pure literal — deterministic, no environment or filesystem
   access, callable before any platform import (module top of `hook_bridge.py` stays
   stdlib-only). **passed**
3. **Step**: every other name returns `None` → checkpoint: the afm event catalog
   (`afm.md` "Event catalog", confirmed by the binary's event-name strings) enumerates
   flow (5), stage (13), script (9) events; the curated set is exactly 15; the non-curated
   set (`flow_started`, `flow_finished`, `flow_failed`, the 9 script events, internal and
   unknown names) all fall through to `None`. **passed**
4. **Output**: `str | None` — the platform action name or `None`.

#### Checkpoint Summary
- Purity/determinism: passed (dict literal lookup).
- Vocabulary coverage: passed — 13 verbatim + 2 normalized = 15 = the catalog records = the
  `registering-hooks.md` table.

### Trace: `build_run_event` (new)

#### Chain
1. **Input**: `payload: dict[str, Any]` — `json.loads` of stdin, already shape-checked to be
   a dict by `run_hook`.
2. **Step**: read the `flow` block (`payload["flow"]`) — a missing or non-dict block raises
   `ValueError("lifecycle event payload carries no flow block")` → checkpoint: the binary's
   JSON tags (`json:"flow"`, `json:"run_id"`, `json:"resumed"`, `json:"run_dir"`,
   `json:"root_dir"`, `json:"name"`) confirm the block shape `{name, run_id, resumed,
   run_dir, root_dir}`. **passed**
3. **Step**: compose `RunIdentity(run_id=flow["run_id"], run_dir=flow["run_dir"],
   root_dir=flow["root_dir"], resumed=flow["resumed"])` → checkpoint: `resumed` is a JSON
   bool; `run_dir` / `root_dir` are absolute posix path strings (afm guarantees when set) —
   passthrough under idiomatic names, no transformation. **passed**
4. **Step**: read the event facts — `event_id`, `occurred_at` (required; a missing fact
   raises `ValueError` naming it), `reason` (optional; `payload.get("reason", "")`) →
   checkpoint: `json:"event_id"`, `json:"occurred_at"`, `json:"reason"` tags confirmed;
   `event_id` is the documented idempotency key; `occurred_at` an ISO-8601 UTC string —
   carried verbatim, never re-parsed. **passed**
5. **Step**: return `RunEvent(pipeline=flow["name"], run=<identity>, event_id=…,
   occurred_at=…, reason=…)` → checkpoint: the raw payload never attaches to the context —
   only the curated fields are copied. **passed**
6. **Output**: `RunEvent` — pure; no I/O, no mutation of `payload`.

#### Checkpoint Summary
- Payload shape conformance (binary-verified): passed.
- Missing-fact errors: passed — clean `ValueError` naming the fact; nothing invented,
  nothing defaulted except the documented `reason` empty-string default.

### Trace: `build_stage_event` (new)

#### Chain
1. **Input**: `payload: dict[str, Any]`.
2. **Step**: read the flow block and the event facts exactly as `build_run_event` (shared
   private helpers — `_flow_block`, `_run_identity`, `_event_facts` — keep the two builders
   in step) → checkpoint: single source for the shared reading logic; a divergence between
   the builders is structurally impossible. **passed**
3. **Step**: read the `stage` block (`payload["stage"]`) — absent on flow-level events; for
   a stage-level action a missing block raises `ValueError("stage-level lifecycle event
   payload carries no stage block")` → checkpoint: `json:"stage"` + `json:"from"` /
   `json:"to"` / `json:"phase"` tags confirmed; block shape `{id, name, from, to, phase}`.
   **passed**
4. **Step**: compose `StageTransition(id=stage["id"], name=stage["name"],
   from_status=stage["from"], to_status=stage["to"], phase=stage["phase"])` → checkpoint:
   the `from` / `to` renames are the documented keyword workaround (manifest requirement);
   values passthrough verbatim. **passed**
5. **Output**: `StageEvent(pipeline=…, run=…, stage=<transition>, event_id=…,
   occurred_at=…, reason=…)`.

#### Checkpoint Summary
- Shared flow/event reading: passed.
- Stage-block requirement and rename: passed.

### Trace: `run_hook` (new — the central entry)

#### Chain
1. **Input**: nothing — the process environment (`AFM_HOOK_EVENT`) and stdin carry the
   event. Entry: afm `sh -c "python3 -m goga.pipeline hook"`, CWD = the flow's `root_dir`.
2. **Step**: `map_event_action(os.environ.get("AFM_HOOK_EVENT", ""))` → `None` returns 0
   immediately → checkpoint: unset or empty env resolves as non-curated (manifest
   requirement); on this path no platform module has been imported by this function —
   `hook_bridge.py` keeps every `goga` import inside function bodies (see Additional
   Instructions for the process-level lazy-import design that makes this true for the whole
   process). **passed**
3. **Step**: read stdin (`sys.stdin.read()`), `json.loads` → a non-JSON body or a JSON
   value that is not an object is a bridge-internal failure: print `Error: …` to stderr,
   return 1 → checkpoint: `JSONDecodeError` ⊂ `ValueError`; afm writes the non-zero exit
   to the per-hook log — the run is unaffected (observer semantics end-to-end). **passed**
4. **Step**: choose the builder — `action in {"run_resumed", "run_interrupted"}` →
   `build_run_event`, else `build_stage_event` → checkpoint: the curated vocabulary has
   exactly two run-level names (both produced by `map_event_action`); every other curated
   name is a `stage_*` name whose payload always carries the stage block. **passed**
5. **Step**: `from .hooks import PipelineHooks` (function-local — after the filter), then
   `PipelineHooks().emit_run_event(action, context)` / `.emit_stage_event(action, context)`
   → checkpoint: one surface per process; the registry builds at the first emission
   (once per event process — manifest requirement); subscriber soft failures warn inside
   the platform and never change the exit code; an `ImportError` from a broken tool facade
   is a bridge-internal failure → `Error: …` + exit 1 (the `run_pipeline` CLI precedent).
   **passed**
6. **Step**: return 0 → checkpoint: happy path prints nothing (the CLI requirement); the
   whole run fits far inside the 30s default timeout (measured: ~0.5s worst-case import
   chain + registry build + subscriber calls). **passed**
7. **Output**: process exit code — 0 on success, ignored events, and subscriber soft
   failures; 1 on bridge-internal failures.

#### Checkpoint Summary
- Fast-path ordering (filter before any platform import): passed at the function level;
  process-level guarantee secured by the lazy-import design (D1 below).
- Error discipline (0 / 0 / 0 vs non-zero): passed — matches the ADR's failure discipline.
- Boundary exclusion: passed — `flow_started` / `flow_finished` / `flow_failed` are
  non-curated, so the bridge can never emit the run boundaries (they belong to
  `run_created` / `run_completed` of the run coordination).

### Trace: `write_afm_config` (changed)

#### Chain
1. **Input**: `agent: str | None` — the effective pipeline agent (call site:
   `run_pipeline` step 16, unchanged).
2. **Step**: `resolve_wrapper_path(agent)` when an agent resolved → checkpoint: unchanged
   behavior; the hook entry does not depend on the agent. **passed**
3. **Step**: compose `content` — optional `client` block, the four static fields (unchanged),
   plus `content["hooks"] = [{"id": "goga", "events": "all", "command":
   "python3 -m goga.pipeline hook", "inherit_env": True}]` → checkpoint: the enclosing key
   `hooks` and the entry field names are verified against the afm binary (`yaml:"hooks,omitempty"`,
   `yaml:"id"`, `yaml:"events"`, `yaml:"command"`, `yaml:"inherit_env,omitempty"`);
   `timeout` / `retries` are intentionally omitted — both are `omitempty` in afm, so their
   absence means the afm defaults (30s / 0), exactly the "afm default timeout and retries"
   the manifest and ADR fix. No `env` map is declared (the bridge has no secret references
   of its own). **passed**
4. **Step**: `yaml.safe_dump(content, default_flow_style=False, sort_keys=False)` → whole
   file rewritten at `/home/goga/.afm/config.yaml` (path constant unchanged, redirected in
   tests by the existing `_AFM_CONFIG_PATH` patch point) → checkpoint: programmatic
   serialization, no hand-escaped strings; repeated invocation stays safe (the entry is a
   constant, not appended). **passed**
5. **Output**: the written `Path`; side effect — the next `afm run` spawns the bridge per
   lifecycle event.

#### Checkpoint Summary
- YAML key/field conformance (binary-verified): passed.
- Idempotence and constancy (never configurable): passed — the entry joins the four static
  constants.

### Trace: `pipeline_cli` (changed)

#### Chain
1. **Input**: `argv: list[str]` — e.g. `["hook"]` from `python -m goga.pipeline hook`.
2. **Step**: parser build — a third subparser `hook` with no arguments → checkpoint: any
   option or positional extra is an argparse error (exit 2) — the "no options" requirement
   falls out of declaring none; `--help` lists the subcommand. **passed**
3. **Step**: parse; `args.command == "hook"` → dispatch `return run_hook()` → checkpoint:
   pure delegation; the exit code is `run_hook`'s result (0/1); the happy path prints
   nothing (errors, if any, were already rendered by `run_hook` to stderr). **passed**
4. **Step**: import structure — `cli.py` imports `run_hook` from `.hook_bridge` (the module
   top is stdlib-only, so the import is cheap); the dispatch branches for the card and the
   run import `describe_pipeline` / `run_pipeline` function-locally so the `hook` fast path
   never loads them → checkpoint: verified by measurement — the current static chain costs
   ~450 ms per process, split ~390 ms root facade (`goga/__init__.py` → `.cli` →
   `goga.commands.*`, which statically imports the platform into every
   `python -m goga.pipeline` process before `__main__` runs) + ~86 ms in-container chain;
   with the lazy design (D1 items 2–4) the non-curated process imports no `goga.hooks` /
   `goga.pipeline.hooks` module at all (the plan's checklist verification — "no platform
   modules in `sys.modules`" — becomes achievable). **passed**
5. **Output**: exit code; stdout empty on the hook path.

#### Checkpoint Summary
- Subparser shape: passed.
- Fast-path import discipline: passed — with design decision D1 applied (below).

## Algorithm Design

### `Action` catalog extension (`goga/hooks/catalog/catalog.py`)

**Responsibility**: data-only source of known addresses; the 15 additions make the bridged
emissions resolvable.

**Algorithm:**
```
1. Append to _DECLARED_ACTIONS, in the pipeline group (after run_completed):
   - Action(pipeline, run_resumed, soft)
   - Action(pipeline, run_interrupted, soft)
   - Action(pipeline, stage_planning_started, soft)
   ... all thirteen stage names, afm catalog order ...
   → list membership; the public sort in declared_actions() places them by name
```

**Errors:** none (data).

**Edge Cases:** none — uniqueness holds; ordering is derived, not stored.

### `RunIdentity`, `StageTransition`, `RunEvent`, `StageEvent` (`contexts.py`)

**Responsibility**: pure passthrough fact bundles; the read-and-observe surface a subscriber
hook sees.

**Algorithm (all four):**
```
1. @dataclass(kw_only=True) with the declared fields, in the declared order
2. No methods, no validation, no defaults except reason="" (last field)
   → construction is assignment; delivery-time read-only enforcement is the
     platform proxy's job
```

**Errors:** none at construction (bad types surface as attribute errors downstream — the
same stance as the existing contexts).

**Edge Cases:**
- `reason` absent in the source → `""` (the only default).
- `from_status` / `to_status` — the raw `from` / `to` keywords never become attribute
  names.

### `PipelineHooks.emit_run_event` / `emit_stage_event` (`events.py`)

**Responsibility**: the soft emission of one bridged event over the platform facade.

**Algorithm:**
```
1. registry ← self._ensure_registry()          # once per event process
2. emit_hook_event(registry, "pipeline", action,
                   context_for=lambda _tool: context)
   → the platform resolves the address (ValueError if unknown — caller error),
     wraps the shared context read-only per subscription, projects the declared
     parameters (context / self), calls each hook, and applies the soft error
     class: a failing hook warns and the walk continues
```

**Errors:**
- `ValueError` (unknown action) → raised to `run_hook` → bridge-internal failure → exit 1.
- Subscriber exception → `WARNING` log inside the platform → never surfaces as a raise.

**Edge Cases:**
- Address without subscriptions → nothing emits, exit 0 (a run with no tool packages
  installed stays byte-identical in behavior).
- Multiple hooks of one tool → one shared view per tool (platform rule), same context
  instance for every tool.

### `map_event_action` (`hook_bridge.py`)

**Responsibility**: the curated filter — one place mapping the afm event vocabulary onto the
platform action vocabulary.

**Algorithm:**
```
_EVENT_ACTION_MAP: dict[str, str] = {           # module-level literal
    "flow_resumed": "run_resumed",
    "flow_interrupted": "run_interrupted",
    "stage_planning_started": "stage_planning_started",
    ... the thirteen stage names, verbatim ...
}
1. return _EVENT_ACTION_MAP.get(event)
   → None for everything else (flow_started/finished/failed, the nine script
     events, internal names, unknown names, "")
```

**Errors:** none.

**Edge Cases:**
- Unset/empty env value → `.get("") → None` → the caller exits 0.
- A future afm event name → `None` (forward-compatible by design — the ADR's reason for
  `events: all` over an explicit list).

### `build_run_event` / `build_stage_event` (`hook_bridge.py`)

**Responsibility**: compose the curated context from the parsed payload under idiomatic
names; the single translation point of the raw vocabulary.

**Algorithm (shared skeleton):**
```
1. flow ← payload["flow"]                        # ValueError naming "flow block" if absent/non-dict
2. identity ← RunIdentity(run_id=flow["run_id"], run_dir=flow["run_dir"],
                          root_dir=flow["root_dir"], resumed=flow["resumed"])
3. facts ← event_id=payload["event_id"],         # ValueError naming the fact if absent
           occurred_at=payload["occurred_at"],
           reason=payload.get("reason", "")
4. stage event only:
   stage ← payload["stage"]                      # ValueError naming "stage block" if absent
   transition ← StageTransition(id=stage["id"], name=stage["name"],
                                from_status=stage["from"], to_status=stage["to"],
                                phase=stage["phase"])
5. return RunEvent(pipeline=flow["name"], run=identity, **facts)
       / StageEvent(pipeline=flow["name"], run=identity, stage=transition, **facts)
```

**Errors:**
- Missing/malformed `flow` block, missing `event_id` / `occurred_at`, missing `stage` block
  on a stage-level event → clean `ValueError` naming the missing fact → exit 1. Nothing is
  invented or defaulted (except `reason`).

**Edge Cases:**
- Extra payload fields (e.g. `schema_version`, `event`) → ignored by construction (only the
  curated keys are read) — no raw-payload exposure.
- `reason: null` in JSON → `payload.get("reason", "")` yields `None`, not `""` — the reader
  uses `payload.get("reason") or ""` so a JSON null also lands as the empty string.

### `run_hook` (`hook_bridge.py`)

**Responsibility**: the bridge entry — one lifecycle event in, one platform emission out,
one process per event.

**Algorithm:**
```
1. action ← map_event_action(os.environ.get("AFM_HOOK_EVENT", ""))
   IF action is None: return 0                   # before any platform import; stdin unread
2. TRY
     payload ← json.loads(sys.stdin.read())
     IF not isinstance(payload, dict): raise ValueError(
         "lifecycle event payload is not a JSON object")
     context ← build_stage_event(payload) if action not in _RUN_LEVEL_ACTIONS
               else build_run_event(payload)     # {"run_resumed", "run_interrupted"}
     from .hooks import PipelineHooks            # function-local — after the filter
     hooks ← PipelineHooks()
     hooks.emit_stage_event(action, context) / hooks.emit_run_event(action, context)
     return 0
   EXCEPT (ValueError, ImportError, OSError) as reason:
     print(f"Error: {reason}", file=sys.stderr)  # the afm per-hook log carries it
     return 1
```

**Errors:**
- Bridge-internal failures (damaged stdin, non-object JSON, missing payload facts, broken
  tool facade) → one stderr line + exit 1 → afm logs it, warns on the dashboard, the run
  continues.
- Subscriber soft failures → warned inside the platform → exit 0.

**Edge Cases:**
- Unset `AFM_HOOK_EVENT` → exit 0 (non-curated).
- Empty stdin on a curated event → `json.loads("")` raises → exit 1 (a manual invocation
  error surfaces loudly).
- No tool packages installed → the registry is empty → emissions are no-ops → exit 0.

### `write_afm_config` (`afm_config.py`)

**Responsibility**: whole-file authorship of the afm configuration, now including goga's
always-on observer registration.

**Algorithm:**
```
1. wrapper ← resolve_wrapper_path(agent)         # only when agent is not None
2. content ← {}
   IF wrapper is not None: content["client"] = {"command": wrapper}
   content.update(theme="goga", open_browser=False,
                  proxy={"enabled": False}, prompts_dir="/home/goga/pipeline/prompts")
   content["hooks"] = [{                          # the observer registration
       "id": "goga",
       "events": "all",
       "command": "python3 -m goga.pipeline hook",
       "inherit_env": True,                       # timeout/retries omitted → afm defaults
   }]
3. write yaml.safe_dump(content, default_flow_style=False, sort_keys=False)
   to the fixed home path                          # _AFM_CONFIG_PATH unchanged
4. return the path
```

**Errors:** `OSError` (unwritable home) propagates unchanged — the run stops before any run
event fires (existing semantics, unchanged).

**Edge Cases:**
- `agent=None` → the `client` block is omitted; the hook entry still registers (the bridge
  is agent-independent).
- Repeated invocation → whole-file rewrite; the entry never duplicates.

### `pipeline_cli` (`cli.py`)

**Responsibility**: parse-and-dispatch of the in-container CLI; the third subcommand is pure
machinery delegation.

**Algorithm (delta only):**
```
parser:
  subparsers.add_parser("hook", help="afm-facing machinery: bridge one lifecycle event")
    # no arguments — extra tokens are argparse errors (exit 2)
dispatch:
  IF args.command == "hook": return run_hook()
  # the hook branch binds on args.command BEFORE any read of args.info —
  # the hook subparser declares no --info, so its Namespace carries no `info`
  # attribute; a branch placed after the unconditional `if args.info:` read
  # would raise AttributeError on every hook invocation
  # run/card branches unchanged except: their operation modules are imported
  # inside the branch functions (see D1)
```

**Errors:** argparse errors → 2; `run_hook` failures self-render (stderr + 1) and the branch
returns the code.

**Edge Cases:** `hook --anything` / `hook extra` → exit 2 with usage — the machinery surface
stays option-free.

### Design decisions (binding for the implementation)

- **D1 — platform-free fast path (lazy imports).** afm spawns one process per event and
  runs one hook's invocations sequentially; the measured static import chain costs
  ~450 ms — ~390 ms of it the root package facade (`goga/__init__.py` imports `app` from
  `.cli`, and `goga.cli` aggregates every `goga.commands.*` module), ~86 ms the
  in-container chain of `goga.pipeline.cli` (jinja2+yaml ~44 ms of that share). Script
  events (up to 9 per script stage) and flow boundaries are non-curated and
  high-frequency, so the plan's verification — "no platform modules in `sys.modules`"
  for a non-curated event — is a performance requirement, not a nicety. The
  interpreter always imports the parent packages before `goga.pipeline.__main__`
  runs, so the root facade must go lazy together with the cell facade. Four
  coordinated changes deliver it:
  1. `hook_bridge.py`: module top imports stdlib only (`json`, `os`, `sys`,
     `typing.Any`); every `goga` import lives inside function bodies. Annotations use
     `from __future__ import annotations` + a `TYPE_CHECKING` block.
  2. `cli.py`: `from .describe_pipeline import describe_pipeline` and
     `from .run_pipeline import run_pipeline` move into the branch functions that use
     them (`_run_card`, `_run_execution`); the remaining top-level imports
     (`argparse`, `sys`, `pathlib`, `yaml`, `jinja2`, `.compiler`,
     `.describe_pipelines`, `.list_pipelines`, `.pipeline_entry`, `.workflow`,
     `.hook_bridge`) are platform-free — verified by import-trace. `run_hook` may stay
     top-level (its module is stdlib-only).
  3. `goga/pipeline/__init__.py`: the two platform-carrying re-exports
     (`describe_pipeline`, `run_pipeline`) become lazy via a PEP 562 module
     `__getattr__` that `importlib.import_module`s the submodule on first attribute
     access; every other facade import stays static. The facade surface (`__all__`,
     nineteen names) is unchanged — `from goga.pipeline import run_pipeline` still
     works; the import system sets the attribute on first submodule import, so
     `__getattr__` fires at most once per name.
  4. `goga/__init__.py`: the root facade is the dominant carrier (measured: all 17
     platform modules, ~0.39 s, present in `sys.modules` after a bare `import goga`).
     Both root re-exports (`AST` from `.ast`, `app` from `.cli`) become lazy via the
     same PEP 562 mechanism; `__all__ = ["AST", "app"]` is unchanged. Verified:
     the console script `goga = "goga.cli:app"` imports `goga.cli` directly and is
     unaffected; `from goga import app, commands` keeps working (when the attribute
     lookup raises, the import system falls back to importing the submodule); no
     goga-internal module reads `goga.app`/`goga.AST` at import time.
- **D2 — hook entry shape (binary-verified).** `hooks: [{id: goga, events: all, command:
  python3 -m goga.pipeline hook, inherit_env: true}]`; `timeout` / `retries` omitted
  (`omitempty` in afm → defaults 30s / 0); no `env` map (no secret references).
- **D3 — run-level split.** `_RUN_LEVEL_ACTIONS: frozenset[str] = frozenset({"run_resumed",
  "run_interrupted"})` in `hook_bridge.py`; membership picks the builder after mapping.
- **D4 — failure rendering.** `run_hook` itself renders bridge-internal failures
  (`Error: <reason>` to stderr) and returns 1 — the manifest's "return a non-zero exit"
  wording, and the afm per-hook log stays informative; `pipeline_cli`'s hook branch is pure
  delegation.
- **D5 — facades.** `goga/pipeline/hooks/__init__.py`: `__all__` grows 11 → 15 (+
  `RunEvent`, `RunIdentity`, `StageEvent`, `StageTransition`; import from `.contexts`).
  `goga/pipeline/__init__.py`: `__all__` grows 15 → 19 (+ `build_run_event`,
  `build_stage_event`, `map_event_action`, `run_hook`; static import from
  `.hook_bridge`). Test scaffolding mirrors: `ZONE_ALL` (zone conftest) 11 → 15;
  `test_pipeline_contract.py` fifteen → nineteen.
- **D6 — catalog placement.** The 15 records join the existing pipeline group of
  `_DECLARED_ACTIONS` after `run_completed`; the public ordering stays derived by the
  existing `sorted()`.

## Cross-cutting Concerns

- **Error handling**: the bridge adds no new error channel. Bridge-internal failures are
  one clean stderr line + exit 1 (afm logs it; observer semantics keep the run unaffected);
  subscriber failures are the platform's soft warnings; everything else in the cell keeps
  its existing error discipline (`write_afm_config` propagates `OSError` before any event
  fires; the CLI renders operation failures without tracebacks).
- **Logging**: no new log points in the bridge itself — subscriber failures are logged by
  the platform (`logger.warning` naming the hook, tool, address, reason). The bridge stays
  silent on the happy path by contract.
- **Validation**: payload validation is structural-only at the bridge (JSON object; flow
  block; required facts; stage block for stage-level actions) with clean errors naming the
  missing fact — no schema framework, no coercion, `reason`'s JSON-null lands as `""`. The
  curated filter is the vocabulary validation. The catalog addition is validated by the
  platform's address resolution on first emission.
- **Caching**: none beyond the existing once-per-surface registry (`_ensure_registry`) —
  one registry per event process, by construction. `map_event_action`'s mapping is a
  module-level literal (immutable in practice).
- **Concurrency**: afm runs one hook's invocations sequentially (one consumer, in order) —
  no concurrent bridge processes of the same hook; different hooks run in parallel but the
  bridge registers a single hook (`id: goga`). No shared mutable state exists: every event
  is a fresh process with fresh module state; the subscriber `self` contexts die with the
  event (documented in `registering-hooks.md`). No locks, no threads introduced.
- **Performance**: the fast path (non-curated) imports stdlib only (~tens of ms vs ~500 ms
  measured for the full chain); the curated path additionally pays the platform import +
  registry build once per event — comfortably inside the 30s per-hook default, and the
  sequential queue drains without the import tax dominating script-heavy runs.
- **Security**: the entry declares no `env` secret references; `inherit_env: true` exposes
  the afm process environment to subscriber hooks — an accepted, documented decision
  (ADR "C16 amendment"); the bridge itself reads only stdin and the `AFM_*` variables and
  writes nothing.

## Usages Analysis

### `convention` (`.goga/usages/conventions.md`) — both modified cells + catalog
- **What it provides**: code style — relative intra-package imports, `kw_only` dataclasses,
  Google docstrings, log levels, REPL/test infrastructure rules.
- **Where used**: every new/changed entity (all four context models, both emission methods,
  all four bridge routines, the catalog records, the facade updates).
- **Why chosen**: the project-wide mandatory practice, referenced by the manifests'
  global annotations.
- **How exactly**: `@dataclass(kw_only=True)` for the four contexts; module-level
  docstrings + Google-style `Args`/`Returns`/`Raises` everywhere; relative imports
  (`.hooks`, `.contexts`) inside `goga.pipeline`; stdlib/third-party absolute.

### `afm` (`.goga/usages/cooks/afm.md`) — `goga/pipeline`
- **What it provides**: the external afm CLI contract — configuration file fields, the
  lifecycle-hooks mechanism (declaration layers, entry fields, event catalog, JSON payload,
  `AFM_*` env, execution model, failure semantics), and goga's registration stance.
- **Where used**: `write_afm_config` (the hook entry), `run_hook` (execution model, payload,
  env, failure semantics), `map_event_action` (the event catalog), `build_run_event` /
  `build_stage_event` (the payload shape), the global annotations (the bridging paragraph).
- **Why chosen**: the single authoritative description of the external binary; every fact
  the bridge relies on was additionally re-verified against the binary itself
  (`hooks` key, entry fields, payload JSON tags, `AFM_HOOK_EVENT`).
- **How exactly**: registration per "goga's stance" (global layer, whole-file rewrite);
  parsing per "JSON payload (stdin)"; env per "`AFM_*` environment"; exit semantics per
  "Failure semantics and delivery guarantees".

### `argparse` (inline) — `goga/pipeline`
- **What it provides**: the CLI parsing rules — now three subcommands.
- **Where used**: `pipeline_cli` (parser construction, dispatch).
- **Why chosen**: the established inline practice of the cell (short, cell-specific).
- **How exactly**: a third subparser `hook` with no arguments; dispatch table extended by
  one pure-delegation branch.

### `cli_entrypoint` (inline) — `goga/pipeline`
- **What it provides**: the thin `__main__` delegation with the docker guard.
- **Where used**: `pipeline_cli` (unchanged mechanics); the hook entry rides the same
  entrypoint, so `ensure_in_docker` covers it (the ADR's reason to reject a dedicated
  module).
- **Why chosen / how**: unchanged — the guard runs before any dispatch, host-side
  invocations fail loudly.

### `resolve-wrapper-path` (imported, `goga/agents`) — `write_afm_config`
- Unchanged consumer — the agent command resolution the hook entry does not touch.

### Imported Usages

- `checkpoints` from `goga/pipeline/hooks` — path
  `goga/pipeline/hooks/.usages/checkpoints.md`; the checkpoint-surface practice `goga/pipeline`
  already imports; the new "Emit the bridged run-interior events" section documents exactly
  the consumption shape the bridge implements (build the surface per event process, emit
  once, exit). Traceable cross-cell link; no new contractual obligation.
- `declaring-actions` from `goga/hooks` (imported by `goga/pipeline/hooks`) — path
  `goga/hooks/.usages/declaring-actions.md`; the emission contract both new methods
  reference ("Emit at the checkpoint" — `emit_hook_event` with the shared `context_for`);
  the catalog record addition is the practice's "Declare the action" step, `soft` class.
- `registering-hooks` from `goga/hooks` (imported by `goga/pipeline/hooks`) — the hook
  signature and failure handling behind every checkpoint; unchanged application.
- `per-tool-delivery` from `goga/hooks` — the amendment loop only; unchanged application,
  not used by the bridged emissions (fire-and-forget, no staged commit).

## `.usages/` Update

### Cell: `goga/pipeline/hooks`

#### Existing Files — Consistency
- **`checkpoints.md`** → `goga/pipeline/hooks/.usages/checkpoints.md`
  - Status: current (extended by the apply-architecture stage).
  - Additions needed: none — the "Emit the bridged run-interior events" section matches the
    implemented-to-be surface (imports from the zone facade, both emission calls, the
    early-exit rule, the per-process surface, best-effort delivery).
  - Updates needed: none.

### Cell: `goga/pipeline`

#### Existing Files — Consistency
- **`pipeline-cli.md`** → `goga/pipeline/.usages/pipeline-cli.md`
  - Status: current — the `hook` subcommand section (no options, machinery entry,
    dispatch `run_hook()`, exit-code semantics) matches the contract.
  - Additions/Updates: none.
- **`registering-hooks.md`** → `goga/pipeline/.usages/registering-hooks.md`
  - Status: current — eighteen actions, the 15 mid-run events with the `StageEvent` /
    `RunEvent` read tables, the short-lived-process and env-visibility notes all match the
    manifests.
  - Additions/Updates: none.
- **`run-pipeline.md`** → `goga/pipeline/.usages/run-pipeline.md`
  - Status: was outdated — the "afm configuration" section predated the observer-hook
    registration.
  - Applied supplement (user-approved during this design): one paragraph recording the
    always-on global-layer registration (`id: goga`, `command: python3 -m goga.pipeline
    hook`, `events: all`, `inherit_env: true`, afm-default timeout/retries), the
    fifteen-action bridging, the boundary split (`run_created` / `run_completed` stay with
    the run coordination), and the authored-global-layer consequence. Self-contained — no
    cross-references to other practices, per the cookbook isolation rule.

#### New Files (if any)
- None — the bridged events belong to the existing functional domains of the two cells
  (checkpoint surface; CLI surface), so the existing files were supplemented, not split.

## Test Stack Trace

### General Setup

- Platform boundary fixtures (existing, reused): `pin_package_environment` (pins the
  `packages_distributions` mapping the enumeration reads) and `install_tool_package`
  (installs a fake `goga_tool_*` package with a `register_hooks` facade into
  `sys.modules`) — re-exported by `tests/pipeline/conftest.py` and
  `tests/pipeline/hooks/conftest.py`. The platform code under test runs for real.
- `tests/pipeline/conftest.py::_in_container_run_context` (autouse) already redirects
  `_AFM_CONFIG_PATH` into the tmp tree and pins the package environment empty — the afm
  config tests inherit it.
- Bridge tests manipulate the two process inputs directly: `monkeypatch.setenv
  ("AFM_HOOK_EVENT", …)` and `monkeypatch.setattr("sys.stdin", io.StringIO(json_text))`
  (or `stdin=DEVNULL` semantics via empty string).
- The process-level fast-path test spawns `sys.executable` with `PYTHONPATH` pointing at
  the repo root, `GOGA_DOCKER=1` (the `ensure_in_docker` guard), and runs
  `runpy.run_module("goga.pipeline", run_name="__main__")` inside the child, catching
  `SystemExit` and reporting `sys.modules` membership — mirroring the plan's checklist
  verification.
- Helpers: `is_kw_only_dataclass` (tests/conftest), `ZONE_ALL` /
  `field_defaults` (tests/pipeline/hooks/conftest) — extended per D5.

### Source File Registry

Files under test (implementation to come): `goga/hooks/catalog/catalog.py`,
`goga/pipeline/hooks/contexts.py`, `goga/pipeline/hooks/events.py`,
`goga/pipeline/hooks/__init__.py`, `goga/pipeline/hook_bridge.py`,
`goga/pipeline/afm_config.py`, `goga/pipeline/cli.py`, `goga/pipeline/__init__.py`.
Test homes: `tests/hooks/catalog/test_catalog.py` (extend),
`tests/pipeline/hooks/test_bridged_events.py` (new),
`tests/pipeline/test_hook_bridge.py` (new), `tests/pipeline/test_afm_config.py` (extend),
`tests/pipeline/test_pipeline_cli.py` (extend), `tests/pipeline/test_pipeline_contract.py`
(extend), `tests/pipeline/hooks/conftest.py` (ZONE_ALL 11 → 15).

---

### Positive Tests

#### `test_declared_actions_carries_the_fifteen_bridge_records`

**Setup**: none (catalog is static data).

**Input**: `declared_actions()`.

**Trace**:
```
declared_actions()
  → sorted(_DECLARED_ACTIONS, key=(domain, name))   # entry point
    returns: 49 Action records
  → pipeline_records = [a for a in actions if a.domain == "pipeline"]
  → assert membership
```

**Assertions**:
```
pipeline_records has exactly 18 elements
("pipeline", "run_resumed", "soft") in pipeline_records
("pipeline", "run_interrupted", "soft") in pipeline_records
for each of the thirteen stage names (stage_planning_started, stage_plan_ready,
  stage_approved, stage_revision_started, stage_execution_started,
  stage_question_asked, stage_question_answered, stage_retry_scheduled,
  stage_retry_started, stage_paused, stage_resumed, stage_finished, stage_failed):
  ("pipeline", <name>, "soft") in pipeline_records
the three pre-existing records (amend_workflow hard, run_created soft,
  run_completed soft) are unchanged and present
pipeline_records == sorted(pipeline_records, key=lambda a: a.name)   # derived order
```

**Sufficiency**: the emissions resolve addresses through this catalog — a missing record
turns every bridged emission into a bridge-internal failure; this test pins the exact
fifteen names and classes (and the untouched three) so a typo cannot pass silently.

---

#### `test_map_event_action_resolves_the_curated_vocabulary`

**Setup**: none (pure function).

**Input** (parametrized): `("stage_plan_ready", "stage_plan_ready")`,
`("stage_failed", "stage_failed")`, … all thirteen; `("flow_resumed", "run_resumed")`,
`("flow_interrupted", "run_interrupted")`.

**Trace**:
```
map_event_action(event)
  → _EVENT_ACTION_MAP.get(event)                    # entry point
    returns: action
  → assert action == expected
```

**Assertions**: `map_event_action(event) == expected` for every parametrized pair.

**Sufficiency**: the curated filter is the single vocabulary mapping — a wrong mapping
means events emit under wrong addresses (subscribers never fire) or boundary events leak
into the bridge; the table test pins all fifteen pairs.

---

#### `test_build_stage_event_composes_the_transition_context`

**Setup**: a full afm-shaped payload dict:
`{"schema_version": 1, "event_id": "run-42:transition:7:stage_execution_started",
"event": "stage_execution_started", "occurred_at": "2026-10-21T12:00:00Z",
"flow": {"name": "deploy", "run_id": "run-42", "resumed": False,
"run_dir": "/home/goga/pipeline/runs/run-42", "root_dir": "/workspace"},
"stage": {"id": "build", "name": "Build", "from": "approved", "to": "executing",
"phase": "execution"}}`.

**Input**: the payload dict.

**Trace**:
```
build_stage_event(payload)
  → _flow_block(payload)                            # step 1
    returns: the flow dict
  → RunIdentity(run_id="run-42", run_dir=..., root_dir=..., resumed=False)   # step 2
  → _event_facts → event_id, occurred_at, reason ""                       # step 3
  → StageTransition(id="build", name="Build", from_status="approved",
                    to_status="executing", phase="execution")               # step 4
  → StageEvent(pipeline="deploy", run=..., stage=..., ...)                  # step 5
  → assert field-by-field
```

**Assertions**:
```
context.pipeline == "deploy"
context.run == RunIdentity(run_id="run-42", run_dir="/home/goga/pipeline/runs/run-42",
                           root_dir="/workspace", resumed=False)
context.stage.from_status == "approved" and context.stage.to_status == "executing"
context.stage.id == "build" and context.stage.name == "Build" and context.stage.phase == "execution"
context.event_id == "run-42:transition:7:stage_execution_started"
context.occurred_at == "2026-10-21T12:00:00Z"
context.reason == ""                      # absent in the payload
not hasattr(context, "schema_version") and not hasattr(context, "event")
```

**Sufficiency**: pins the idiomatic rename (`from`→`from_status`, `to`→`to_status`), the
curated no-raw-payload rule, and the `reason` default — the exact translation contract
between the afm vocabulary and the zone contexts.

---

#### `test_emit_stage_event_delivers_shared_read_only_context`

**Setup** (zone suite): `pin_package_environment({"goga_tool_reporter":
["goga-tool-reporter"], "goga_tool_mirror": ["goga-tool-mirror"]})`; two installed
tools, each whose `register_hooks` subscribes `("pipeline",
"stage_execution_started", "notify", hook)`; each hook captures its own `context`
parameter and probes a DIRECT assignment (`try: context.reason = "x"` → capture
`AttributeError`) — a nested write such as `context.stage.name = "x"` would resolve
`stage` through the proxy onto the raw dataclass and mutate it silently, so the probe
must assign on the delivered view itself.

**Input**: `hooks = PipelineHooks()`; a `StageEvent` built like the previous test;
`hooks.emit_stage_event("stage_execution_started", context)`.

**Trace**:
```
emit_stage_event(action, context)
  → _ensure_registry()                              # builds once; enumerates the pinned env
  → emit_hook_event(registry, "pipeline", "stage_execution_started",
                    context_for=lambda _tool: context)
    → context_for(tool) returns the SAME context instance for every distinct tool
    → per subscription: wrap_context(view) — a fresh read-only proxy per subscription
    → build_hook_arguments(hook, proxy, self_context) → {"context": proxy}
    → hook(context=proxy)                           # each subscriber runs
      side effect: captured its proxy; direct-assignment probe raised AttributeError
    returns: None
  → assert captures
```

**Assertions**:
```
reporter_ctx.stage is context.stage          # nested facts read through the proxy
mirror_ctx.stage is context.stage            # are the very same objects — one shared
                                             # context behind the per-subscription proxies
reporter_ctx.stage is mirror_ctx.stage       # both tools read the same facts
reporter_ctx.stage.name == "Build"           # reads pass through the proxy
mirror_ctx.event_id == "run-42:transition:7:stage_execution_started"
write_error is AttributeError                # direct assignment on the view is blocked
emit returned None; no exception raised
```

(`captured is context` is asserted nowhere on purpose: the subscriber receives the
`_DeliveryProxy`, never the raw instance — the platform builds a new proxy per
subscription, and the shared-instance rule of `declaring-actions` lives at the
`context_for` level, observable through the nested-fact identity above.)

**Sufficiency**: proves the soft emission mechanics (registry → proxy → declared-parameter
call), the read-only delivery, and the shared-facts rule across tools — the
subscriber-visible contract of every bridged event.

---

#### `test_run_hook_bridges_a_curated_stage_event_end_to_end`

**Setup**: env `AFM_HOOK_EVENT=stage_execution_started`; `sys.stdin` monkeypatched to the
full payload JSON of the builder test; a subscribed fake tool capturing the delivered
context (as above).

**Input**: `run_hook()` (no arguments).

**Trace**:
```
run_hook()
  → map_event_action("stage_execution_started") → "stage_execution_started"   # step 1
  → json.loads(sys.stdin.read()) → payload dict                               # step 2
  → build_stage_event(payload) → StageEvent                                   # step 3
  → from .hooks import PipelineHooks (function-local)                          # step 4
  → PipelineHooks().emit_stage_event("stage_execution_started", context)
    → registry build (first emission) → delivery → subscriber captures
  → return 0                                                                  # step 5
  → assert exit code and captured facts
```

**Assertions**:
```
result == 0
captured.pipeline == "deploy" and captured.stage.to_status == "executing"
capsys.readouterr().out == ""                # happy path prints nothing
```

**Sufficiency**: the full bridge chain — env → filter → stdin → builder → emission — in one
process-shaped test; the regression it prevents is any reordering that breaks the curated
path (e.g. importing the platform before the filter, or mis-wiring the builder split).

---

#### `test_write_afm_config_registers_the_observer_hook`

**Setup**: `config_path` fixture (redirects `_AFM_CONFIG_PATH` into tmp); an agentless
call is also covered by the existing with/without-agent tests.

**Input**: `write_afm_config("codex")`.

**Trace**:
```
write_afm_config("codex")
  → resolve_wrapper_path("codex") → "/home/goga/bin/codex-as-claude.sh"
  → content = {client: {command: …}, theme, open_browser, proxy, prompts_dir,
               hooks: [{id: goga, events: all, command: python3 -m goga.pipeline hook,
                        inherit_env: True}]}
  → yaml.safe_dump → write → return path
  → yaml.safe_load(path.read_text())         # test re-reads
```

**Assertions**:
```
parsed["hooks"] == [{"id": "goga", "events": "all",
                     "command": "python3 -m goga.pipeline hook",
                     "inherit_env": True}]
set(parsed["hooks"][0]) == {"id", "events", "command", "inherit_env"}   # no timeout/retries/env
parsed["client"]["command"] == "/home/goga/bin/codex-as-claude.sh"      # unchanged fields intact
parsed["theme"] == "goga" and parsed["open_browser"] is False
parsed["proxy"] == {"enabled": False}
parsed["prompts_dir"] == "/home/goga/pipeline/prompts"
```

**Sufficiency**: the registration is the feature's enablement — a wrong key name or a
stray field silently disables or mis-configures the bridge on every launch; the exact-dict
assertion pins the binary-verified shape.

---

#### `test_pipeline_cli_hook_dispatches_and_returns_the_code`

**Setup**: `mock.patch("goga.pipeline.cli.run_hook", return_value=0)`.

**Input**: `pipeline_cli(["hook"])`.

**Trace**:
```
pipeline_cli(["hook"])
  → _build_parser() — three subparsers                       # step 1
  → parse_args(["hook"]) → Namespace(command="hook")         # step 2
  → dispatch: run_hook() mock called once                    # step 4
  → return 0
```

**Assertions**:
```
result == 0; mock.assert_called_once_with()
capsys.readouterr() == ("", "")                              # prints nothing
```

**Sufficiency**: the CLI is the registered command's entry — this pins the pure-delegation
branch and the silent happy path (the "machinery, not user surface" requirement).

---

### Negative Tests

#### `test_map_event_action_returns_none_outside_the_curated_vocabulary`

**Setup**: none.

**Input** (parametrized): `"flow_started"`, `"flow_finished"`, `"flow_failed"`,
`"stage_script_started"`, `"stage_script_after_finished"`, `"agent_action"`,
`"script_output"`, `""`, `"not_an_event"`.

**Trace**:
```
map_event_action(event)
  → _EVENT_ACTION_MAP.get(event) → None
  → assert result is None
```

**Assertions**: `map_event_action(event) is None` for every parametrized name.

**Sufficiency**: the boundary discipline — the run boundaries belong to the run
coordination's checkpoints and the script/internal events are noise; any of these mapping
to an action would double-emit or leak high-frequency events onto the platform.

---

#### `test_run_hook_non_curated_event_exits_zero_without_reading_stdin`

**Setup**: env `AFM_HOOK_EVENT=stage_script_started`; `sys.stdin` monkeypatched to an
object whose `read` raises `AssertionError` if called; package environment pinned empty
with the enumeration boundary mocked and its call count asserted.

**Input**: `run_hook()`.

**Trace**:
```
run_hook()
  → map_event_action("stage_script_started") → None          # step 1
  → return 0                                                 # immediately
  → assert stdin untouched, enumeration boundary not called
```

**Assertions**:
```
result == 0
stdin_read_mock.not_called
enumeration_boundary.not_called              # the registry never built
```

**Sufficiency**: the fast path is a contract ("returns 0 immediately, before any platform
import") — this proves the early return happens before stdin and before any enumeration,
the property that keeps script-heavy runs cheap.

---

#### `test_run_hook_damaged_stdin_returns_nonzero_with_clean_message`

**Setup**: env `AFM_HOOK_EVENT=flow_resumed`; `sys.stdin` = `io.StringIO("{not json")`
(parametrized with `io.StringIO("")` — empty stdin travels the same `JSONDecodeError`
path); `capsys`.

**Input**: `run_hook()`.

**Trace**:
```
run_hook()
  → map_event_action("flow_resumed") → "run_resumed"          # step 1 (curated)
  → json.loads("{not json") → JSONDecodeError (⊂ ValueError)   # step 2
  → except: print("Error: …") to stderr; return 1
```

**Assertions**:
```
result == 1
"Error:" in capsys.readouterr().err and "Traceback" not in err
```

---

#### `test_run_hook_missing_flow_block_returns_nonzero`

**Setup**: env `AFM_HOOK_EVENT=stage_finished`; parametrized stdin — (a) a payload
with the event facts and a `stage` block but no `flow` key, (b) a payload with
`"flow": "not-a-dict"`; `capsys`.

**Input**: `run_hook()`.

**Trace**:
```
run_hook()
  → map_event_action("stage_finished") → "stage_finished"   # step 1 (curated)
  → json.loads → payload dict                               # step 2
  → build_stage_event(payload) → _flow_block finds no dict
    → ValueError("lifecycle event payload carries no flow block")
  → except: stderr line; return 1
```

**Assertions**:
```
result == 1
"flow block" in capsys.readouterr().err and "Traceback" not in err
```

**Sufficiency**: the `flow` block is the first required fact of both builders; without
this test the `_flow_block` branch carries no negative coverage, and a payload-key typo
or an afm tag change would surface as a raw `KeyError`/`TypeError` traceback instead of
the clean named error the manifest requires.

**Sufficiency**: damaged input is the canonical bridge-internal failure — the test pins the
non-zero exit and the no-traceback rendering the afm per-hook log depends on.

---

#### `test_run_hook_missing_stage_block_returns_nonzero`

**Setup**: env `AFM_HOOK_EVENT=stage_paused`; stdin = a payload with the flow block and
event facts but no `stage` key.

**Input**: `run_hook()`.

**Trace**:
```
run_hook()
  → map_event_action("stage_paused") → "stage_paused"
  → json.loads → payload
  → build_stage_event(payload) → _stage_block raises
    ValueError("stage-level lifecycle event payload carries no stage block")
  → except: stderr line; return 1
```

**Assertions**:
```
result == 1
"stage block" in capsys.readouterr().err
```

**Sufficiency**: a stage-level event without a stage block is an afm contract violation —
the bridge must fail loudly (not invent a stage), and the error must name the missing fact
per the manifest requirement.

---

#### `test_run_hook_missing_event_fact_names_the_fact`

**Setup**: env `AFM_HOOK_EVENT=flow_interrupted`; stdin = a payload whose top level lacks
`occurred_at`.

**Input**: `run_hook()`.

**Trace**:
```
run_hook() → action "run_interrupted" → payload parsed
  → build_run_event(payload) → _event_fact raises ValueError naming "occurred_at"
  → stderr; return 1
```

**Assertions**: `result == 1`; `"occurred_at" in capsys.readouterr().err`.

**Sufficiency**: pins the do-not-invent rule — a missing required fact is a named error,
never a defaulted value that would silently corrupt the context contract.

---

#### `test_emit_run_event_unknown_action_raises_clean_error`

**Setup**: package environment pinned empty.

**Input**: `PipelineHooks().emit_run_event("not_an_action", RunEvent(...))`.

**Trace**:
```
emit_run_event("not_an_action", context)
  → _ensure_registry()
  → emit_hook_event resolves pipeline/not_an_action against declared_actions
    → raises ValueError("unknown hook action: pipeline.not_an_action")
```

**Assertions**: `pytest.raises(ValueError, match="unknown hook action")`.

**Sufficiency**: the methods accept any `action: str` — the catalog remains the validation
point; the test pins that a caller error surfaces as a clean ValueError (→ bridge-internal
failure → exit 1), not a silent no-op.

---

#### `test_pipeline_cli_hook_rejects_options`

**Setup**: none.

**Input**: `pipeline_cli(["hook", "--port", "1"])` (and `["hook", "extra"]`).

**Trace**:
```
pipeline_cli([...])
  → parse_args → argparse error (unrecognized arguments)
  → parser.error prints usage to stderr → SystemExit(2)   # not a returned code —
    pipeline_cli does not intercept argparse errors (existing CLI-test precedent)
```

**Assertions**: for both inputs — `with pytest.raises(SystemExit) as exc_info:
pipeline_cli(argv)`; `exc_info.value.code == 2`; `"usage:" in
capsys.readouterr().err`.

**Sufficiency**: the hook subcommand is option-free machinery — an accidental option must
be an argparse error, never a silently ignored token.

---

### Edge Case Tests

#### `test_run_hook_platform_free_fast_path` (subprocess)

**Setup**: `subprocess.run([sys.executable, "-c", child_code], env={**os.environ,
"GOGA_DOCKER": "1", "AFM_HOOK_EVENT": "stage_script_started", "PYTHONPATH": <repo root>},
stdin=DEVNULL, capture_output=True)` where `child_code` runs
`runpy.run_module("goga.pipeline", run_name="__main__")` with
`sys.argv = ["goga.pipeline", "hook"]`, catches `SystemExit`, and prints the exit code plus
`sorted(m for m in sys.modules if m == "goga.hooks" or m.startswith("goga.hooks.") or
m == "goga.pipeline.hooks" or m.startswith("goga.pipeline.hooks."))`.

**Input**: the child process (non-curated event, empty stdin).

**Trace**:
```
child: runpy → goga.pipeline.__main__ → ensure_in_docker (GOGA_DOCKER=1 passes)
  → pipeline_cli(["hook"]) → run_hook() → map_event_action → None → 0
  → SystemExit(0) caught → prints "0" and the platform-module list
  → assert
```

**Assertions**:
```
first stdout line == "0"
second stdout line == "[]"                    # no platform modules in sys.modules
```

**Sufficiency**: this is the plan's checklist verification verbatim — the process-level
proof that the curated filter precedes any platform import; it fails if any static import
chain (cli, the package facade) reintroduces the platform, which is exactly the regression
class D1 guards against.

---

#### `test_run_hook_null_reason_lands_as_empty_string`

**Setup**: env `AFM_HOOK_EVENT=flow_resumed`; stdin payload with `"reason": None`; a
capturing subscriber.

**Input**: `run_hook()`.

**Trace**:
```
run_hook() → action "run_resumed" → payload → build_run_event
  → reason reader: payload.get("reason") or "" → ""          # JSON null → ""
  → emit_run_event → subscriber captures
```

**Assertions**: `result == 0`; `captured.reason == ""`.

**Sufficiency**: the context contract says `reason` is "empty when the source names none" —
a JSON null must not leak `None` into a `str`-typed fact.

---

#### `test_run_hook_non_object_json_is_a_bridge_failure`

**Setup**: env `AFM_HOOK_EVENT=stage_finished`; stdin = `"[1, 2, 3]"`.

**Input**: `run_hook()`.

**Trace**:
```
run_hook() → payload parses as list → isinstance check fails
  → ValueError("lifecycle event payload is not a JSON object") → stderr; return 1
```

**Assertions**: `result == 1`; `"not a JSON object" in err`.

**Sufficiency**: valid-JSON-but-wrong-shape is the easy-to-miss neighbor of damaged JSON —
without the isinstance check it would surface as an `AttributeError` deep in a builder.

---

#### `test_run_hook_subscriber_failure_and_empty_registry_exit_zero`

**Setup**: two scenarios. (a) `pin_package_environment({"goga_tool_boom":
["goga-tool-boom"]})` with a tool subscribed to `pipeline / stage_paused` whose hook
raises `RuntimeError("boom")`; `caplog` at the platform logger level. (b)
`pin_package_environment({})` — an empty registry. Both: env
`AFM_HOOK_EVENT=stage_paused`, stdin = a full valid stage payload, `capsys`.

**Input**: `run_hook()` in each scenario.

**Trace**:
```
(a) run_hook() → map_event_action("stage_paused") → "stage_paused"
  → parse → build_stage_event → PipelineHooks().emit_stage_event
    → emit_hook_event: subscription found → hook(**{"context": proxy})
      → RuntimeError("boom") → error_class "soft"
      → logger.warning("hook … of tool … failed on pipeline.stage_paused: boom")
    → walk continues → return 0
(b) run_hook() → curated → parse → build → emit: no subscriptions → nothing called
  → return 0
```

**Assertions**:
```
(a) result == 0; "Error:" not in capsys.readouterr().err
    one WARNING record in caplog carrying "stage_paused" and "boom"
(b) result == 0; capsys.readouterr() == ("", "")
```

**Sufficiency**: the ADR's cornerstone observer guarantee — a subscriber failure never
changes the bridge outcome, and a run with no tool packages stays behaviorally
identical. The regression class (a greedy catch dragging subscriber failures into the
bridge-failure branch, or a warning promoted to an error) is caught by no other
specified test.

---

#### `test_bridged_surface_registry_built_once_per_process`

**Setup**: package environment with one subscribed tool; the enumeration boundary mocked
with a call counter.

**Input**: one `PipelineHooks` surface; `emit_run_event("run_resumed", ctx1)` then
`emit_stage_event("stage_paused", ctx2)` on it.

**Trace**:
```
emit_run_event → _ensure_registry → build_once (boundary call #1)
emit_stage_event → _ensure_registry → cached (no boundary call)
  → assert boundary.call_count == 1
```

**Assertions**: enumeration boundary called exactly once across both emissions.

**Sufficiency**: the "one registry per event process" requirement — a rebuild per emission
would re-enumerate packages per event and multiply the per-run cost the zone exists to
avoid.

---

#### `test_zone_and_cell_facades_export_the_new_names`

**Setup/Trace**: import surfaces and assert membership.

**Input**: `goga.pipeline.hooks.__all__`, `goga.pipeline.__all__`, `ZONE_ALL`.

**Assertions**:
```
sorted(goga.pipeline.hooks.__all__) == ZONE_ALL (15 names, incl. the four new)
"run_hook", "map_event_action", "build_run_event", "build_stage_event"
  in goga.pipeline.__all__                      # 19 names total
from goga.pipeline import run_pipeline still resolves (lazy pair) — hasattr True
```

**Sufficiency**: the consumer documents import the new names from the facades
(`checkpoints.md` imports the four zone types); the lazy pair must remain importable — this
pins both the additions and the no-regression of the facade contract.

---

## Additional Instructions for the Implementation Agent

- Implement strictly in the plan's order: catalog records → zone (contexts, events,
  facade) → bridge module + `afm_config` + `cli` (+ package facade laziness) → tests. The
  bridged emissions fail address resolution until the catalog records exist.
- `hook_bridge.py` module top: stdlib only (`json`, `os`, `sys`, `typing.Any`,
  `__future__` annotations, `TYPE_CHECKING` block for the zone types). Every `goga`
  import lives inside a function body. Never hoist them "for cleanliness" — the fast-path
  test fails the moment one rises to the top.
- Apply D1 exactly: move only the two platform-carrying imports in `cli.py` into their
  branch functions; make the two corresponding `goga/pipeline/__init__.py` re-exports AND
  the two `goga/__init__.py` re-exports (`AST`, `app`) lazy via PEP 562 `__getattr__`
  (keep both `__all__` lists complete — the cell facade alphabetical with nineteen names,
  the root facade `["AST", "app"]`). Do not restructure other imports; the rest are
  verified platform-free. The root-facade laziness is what keeps the platform out of
  the process: the interpreter imports `goga` before `goga.pipeline.__main__` runs,
  so without item 4 the fast-path test cannot pass.
- Keep `write_afm_config` field order and the exact hook-entry dict of D2; do not write
  `timeout` / `retries` / `env` — their absence is the contract (afm `omitempty` defaults).
- `run_hook` renders its own failures (`Error: …` to stderr, return 1) and catches exactly
  `(ValueError, ImportError, OSError)` — `JSONDecodeError` and `UnicodeDecodeError` arrive
  as `ValueError` subclasses; do not add a CLI-side catch for the hook branch.
- Extend the test scaffolding in lockstep (`ZONE_ALL` 11 → 15; `test_pipeline_contract`
  fifteen → nineteen names; catalog test counts 34 → 49 total / 18 pipeline).
- Update nothing else: `run_pipeline`, `describe_*`, the compiler, the workflow layer, and
  the host-side launcher are untouched by this topic (the sole exception: the mechanical
  lazy-`__getattr__` change of `goga/__init__.py` per D1 item 4 — facade mechanics only,
  no behavior and no surface change); the flow-file bytes and CLI outputs
  of a no-tool-packages run stay identical (the plan's cross-cutting checklist).
- Live-run and older-afm-binary checks from the plan's checklist (items under "Docs" and
  "Cross-cutting") are post-implementation verifications, not unit tests — schedule them
  after the unit suite is green.
