# Support afm lifecycle hooks in goga

Bridge afm lifecycle hooks onto the goga hooks platform as pipeline-domain run
events.

## Current State

A goga pipeline run treats afm as a black box between two boundary events:

- The run coordination (`run_pipeline`, cell `goga/pipeline`) writes the whole
  in-container `~/.afm/config.yaml` on every launch via `write_afm_config` — the
  resolved `client.command` plus the four non-configurable statics — emits
  `run_created`, launches afm through the thin subprocess wrapper `run_flow`
  (cell `goga/afm`), and emits `run_completed` on every return path.
- The extension platform speaks only at those boundaries. The action catalog
  (`goga/hooks/catalog`) carries three pipeline-domain actions — `amend_workflow`
  (hard), `run_created` and `run_completed` (soft); the pipeline hooks zone
  (`goga/pipeline/hooks`) owns the checkpoint surface `PipelineHooks` and the
  `RunCreated` / `RunCompleted` contexts.
- The in-container CLI entrypoint `python -m goga.pipeline` (argparse practice,
  `cli_entrypoint` practice with the `ensure_in_docker` guard) is the established
  `python -m goga.*` precedent.
- Between the boundaries goga sees nothing of the run interior: the afm
  lifecycle-hooks mechanism is consumed by nothing, and because goga rewrites the
  whole `~/.afm/config.yaml` on every launch, even a manually placed global-layer
  hook cannot survive a goga-run launch.
- The afm lifecycle-hooks mechanism (declaration layers, event catalog, JSON
  payload, `AFM_*` environment, execution model, observer semantics, delivery
  guarantees) is now documented in `.goga/usages/cooks/afm.md`.

## Description

Support the afm lifecycle-hooks mechanism from the goga side. On every pipeline
run goga registers its own observer hook with afm — in the global layer of the
written `~/.afm/config.yaml`, always on — and bridges afm's per-event invocations
(a fresh short-lived process per event: `sh -c`, CWD = the flow's `root_dir`, the
full JSON event on stdin, the `AFM_*` environment) onto the internal hooks
platform as 15 new soft actions of the `pipeline` domain: the 13 `stage_*`
transitions under their afm names plus `run_resumed` (afm `flow_resumed`) and
`run_interrupted` (afm `flow_interrupted`), normalized to goga's vocabulary —
goga has no "flow" concept; the run boundaries stay with the unchanged
`run_created` / `run_completed`. Every bridged event carries passthrough facts
under goga-idiomatic names, sufficient for a tool to react without knowing afm
internals, with no raw-payload exposure. Tool authors subscribe through the
existing tool-declaration mechanics; nothing new is learned, enabled, or
configured by anyone.

## Scope

**In scope:**

- **Registration.** The afm configuration write declares goga's own hook entry on
  every run: id `goga`, command `python3 -m goga.pipeline hook`, `events: all`,
  `inherit_env: true`, afm-default timeout and retries — in the global layer of
  the whole-file write; all fields written today (the resolved `client.command`
  and the four non-configurable statics) remain intact; zero user action or
  configuration.
- **Bridge.** A new `hook` subcommand of the in-container `python -m goga.pipeline`
  CLI: one short-lived process per afm event; reads the full JSON payload from
  stdin (the `AFM_*` environment available); exits early with code 0 on
  non-curated events — by `AFM_HOOK_EVENT` — before importing the platform; maps
  curated events onto the platform vocabulary and emits soft events through the
  hooks platform; keeps no cross-event state; completes well inside afm's default
  30s per-hook timeout.
- **Vocabulary.** 15 new soft actions in the `pipeline` domain:
  `stage_planning_started`, `stage_plan_ready`, `stage_approved`,
  `stage_revision_started`, `stage_execution_started`, `stage_question_asked`,
  `stage_question_answered`, `stage_retry_scheduled`, `stage_retry_started`,
  `stage_paused`, `stage_resumed`, `stage_finished`, `stage_failed` (afm names
  unchanged), plus `run_resumed` and `run_interrupted`. afm events outside the
  curated set — script events, internal high-frequency events, and the flow
  boundaries — produce no new platform actions; the run boundaries stay with the
  unchanged `run_created` / `run_completed`.
- **Contexts.** Every bridged event carries: pipeline identity (`name`); run
  identity (`run_id`, `run_dir`, `root_dir`, `resumed`); `event_id` (the
  idempotency key); `occurred_at`; and `reason` when afm provides one —
  passthrough values under goga-idiomatic names; the raw payload is not
  exposed. The 13 stage events additionally carry stage identity (`id`, `name`,
  `from_status`, `to_status`, `phase`); the two run-level events (`run_resumed`,
  `run_interrupted`) carry no stage facts — afm provides no stage block for
  flow-level events (`from_status` / `to_status` normalize afm's `from` / `to`,
  which are Python keywords and cannot be attribute names).
- **Documentation.** The tool-facing subscription documentation
  (`docs/features/pipelines/hooks.md`) extended with the new actions, their
  contexts, the live best-effort no-replay delivery contract, and the subscriber
  env visibility under `inherit_env: true`; the pipeline hooks cell checkpoints
  usage updated accordingly.
- **CODEMANIFEST updates** for the affected cells, reflecting the new contract
  surface (placement of the bridge code, the context record shapes, the catalog
  wiring, and the manifest amendments are owned by the design stage).

**Out of scope:**

- Topics board or history live statuses.
- User-facing hooks authoring (workflow/config → flow-file compilation) —
  documentation of the future place only.
- Any modification of afm.
- New user-facing CLI flags, commands, or configuration surface.
- Changes to the existing action contracts (`amend_workflow`, `run_created`,
  `run_completed`).
- Durable / at-least-once event delivery or replay (an afm-side planned feature;
  goga builds no queue of its own).
- First-party consumer tools (notifications, metrics, mirrors).
- Workflow-layer changes (`goga/pipeline/workflow`, `goga/pipeline/compiler`).

## Acceptance Criteria

- **Live mid-run delivery.** During a real pipeline run, a tool subscribed to a
  stage-level action receives the event while the stage is still executing —
  before the run completes — with the full context: pipeline name; `run_id`,
  `run_dir`, `root_dir`, `resumed`; stage `id`, `name`, `from_status`,
  `to_status`, `phase`; `event_id`; `occurred_at`; and `reason` when present.
- **Existing mechanics only.** Subscription works purely through the existing
  tool-declaration mechanics; the new actions appear in the declared-actions
  catalog; no new registration mechanism exists.
- **Exact vocabulary.** Every curated-vocabulary afm event is bridged; afm events
  outside the set (script events, internals, flow boundaries) produce no new
  platform actions; `run_created` / `run_completed` fire exactly as before with
  unchanged contexts.
- **Failures never leak into the run.** The bridge exits 0 on success, on ignored
  events, and on subscriber soft failures (the platform already warns naming the
  tool and the action); non-zero only on a bridge-internal failure (damaged
  stdin, emission crash) — afm writes it to the per-hook log
  (`.afm/runs/<run-id>/hooks/goga.log`) and warns on the dashboard; a failing or
  hanging hook command leaves the run identical — same stages, same statuses,
  same exit code.
- **Speed.** The hook command completes far inside afm's default 30s timeout for
  every event; stage transitions are never delayed beyond afm's bounded hook
  waits; non-curated events exit before the platform import.
- **Always-on registration.** Every pipeline run's written afm config carries
  goga's hook entry automatically — stable id, global layer, all existing fields
  intact — with zero user action and zero new configuration.
- **Honest contract.** The delivery guarantees (live best-effort, no replay), the
  observer semantics, and the subscriber env visibility under `inherit_env: true`
  are documented for tool authors — learnable without reading code; the two
  "hooks" vocabularies (the goga platform and the afm mechanism) stay unambiguous
  in product language.
- **Contracts updated.** The affected cells' CODEMANIFESTs and the pipeline
  hooks `checkpoints` usage reflect the new surface — the registration, the
  `hook` dispatch, the 15 actions, and the contexts — consistent with the
  implementation (shapes and placement owned by the design stage).
- **The future place is real.** `afm.md` documents the mechanism, goga's stance,
  and the future user-hooks place well enough to plan future authoring without
  redoing the mechanism (already extended at the specify stage).
- **Zero regressions.** For the pipeline user everything behaves as today:
  identical launch flow, flow-file, exit-code propagation, and existing events;
  with no tool packages installed every form behaves exactly as with the layer
  absent.

## Stack

- **Frameworks:** none — no new entries in `pyproject.toml`.
- **Libraries:** `argparse` (in-container CLI parsing, existing practice), `json`
  / `sys` (stdin payload, process exit codes), `dataclasses` with `kw_only=True`
  (context records, per `convention`), `pathlib`, `logging` (per `convention`).
  The bridge code itself is Python 3.10+ standard library only; the registration
  travels through the existing `write_afm_config` whole-file serialization
  (pyyaml — an existing project dependency, no new entry).
- **Infrastructure:** none — no databases, brokers, or queues; the existing goga
  Docker in-container runtime boundary applies unchanged.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| afm (external Go binary; lifecycle-hooks mechanism, v1.2.17+) | `.goga/usages/cooks/afm.md` | updated (specify stage) |

Synced usage files are managed by `goga usages sync` — reference them read-only,
never create or update them in the task. No synced dependency is involved.

## Risks and Constraints

- afm is external and unmodifiable; goga adapts to its contract only (the
  mechanism is now fixed in `.goga/usages/cooks/afm.md`).
- afm hooks are observer-only end-to-end: a hook error never changes the FSM, a
  stage result, or the flow outcome — the bridge preserves this on the goga side.
- The afm execution model binds the bridge: `sh -c`, CWD = the flow's
  `root_dir`, the full JSON event on stdin, the `AFM_*` environment; events for
  one hook are delivered sequentially (the bridge observes event order), different
  hooks run in parallel; the queue drains within a bounded wait on clean exit.
- Delivery is live best-effort with no replay after a crash; the per-hook timeout
  defaults to 30s and retries to 0.
- Layer id rules: goga's hook id can be overridden or replaced by the user in
  more specific layers — afm's designed control point, documented as such.
- The registration travels through the whole-file rewrite of the in-container
  `~/.afm/config.yaml` on every launch; the existing fields and statics are
  preserved.
- The platform semantics are preserved: the registry built once per command maps
  to once-per-event-process for the bridge; soft events warn only; the existing
  action contracts are unchanged; the run boundaries are not duplicated.
- `inherit_env: true` (C16 amendment, risk explicitly accepted at the discover
  stage): the hook process — and the subscriber hooks running inside it —
  inherits the afm process environment, including the launch env layers; the
  subscriber env visibility is documented instead of avoided.
- The hook command must be resolvable in-container, following the
  `python -m goga.*` entrypoint precedent; host-side invocations fail loudly (the
  `ensure_in_docker` guard already covers the entrypoint).
- With an older afm binary in the image the hooks config key is silently ignored
  and the bridge is simply absent — no run impact either way.
- No new user-facing surface of any kind.

## Scope Estimate

Single task — no decomposition. The parts (registration, bridge, vocabulary,
contexts, docs) are tightly coupled and deliver independent value only together:
registration without the bridge is dead configuration, the bridge without the
catalog records cannot emit, the vocabulary without the bridge is dead actions.

## Existing Architecture

Affected cells and integration links (the concrete placement of the bridge code
and the context record shapes are deliberately open for the design stage, per the
ADR):

- `goga/pipeline` — the afm configuration authorship (`write_afm_config`) gains
  the hook-entry registration into the whole-file write; the in-container CLI
  (`pipeline_cli` with the `__main__` delegation) gains the `hook` dispatch; the
  `argparse` and `cli_entrypoint` practices are amended accordingly.
- `goga/pipeline/hooks` — the pipeline domain hooks zone: the bridged-event
  vocabulary and its contexts extend this zone's responsibility (or a sibling
  cell — a design-stage decision); the cell's `checkpoints` usage file documents
  the new emission surface.
- `goga/hooks/catalog` — 15 new soft `Action` records of the `pipeline` domain,
  additive; published records are never rewritten.
- `goga/hooks` (facade) — consumed as-is (`emit_hook_event`, `HookRegistry`,
  `wrap_context`, `build_hook_arguments`, `declared_actions`); no platform
  changes.
- `goga/docker` — untouched; the `ensure_in_docker` guard already covers the
  entrypoint through `__main__`.
- Documentation surfaces: `docs/features/pipelines/hooks.md`,
  `.goga/usages/cooks/afm.md` (already extended at the specify stage).
- The workflow layer (`goga/pipeline/workflow`, `goga/pipeline/compiler`) and the
  host-side launcher (`goga/commands/pipeline`) are untouched — the runtime
  boundary to the in-container pipeline stays docker, no Python imports cross it.

Integration requirements:

- The bridge runs exactly as afm spawns it: `sh -c`, CWD = the flow's
  `root_dir`, JSON on stdin, `AFM_*` env; one process per event.
- The registration is part of the existing whole-file config write — no second
  write, no other file.
- The bridge consumes the hooks platform facade only; the curated filter lives in
  one place — the bridge — which exits early on non-curated events before the
  platform import.

## Notes

- Inputs: the ADR (`.goga/history/2026/support-afm-hooks/adr.md`) and the amended
  PRD (`.goga/history/2026/support-afm-hooks/prd.md`) are the decision record;
  this task follows them verbatim.
- `.goga/usages/cooks/afm.md` was extended at the specify stage with the
  lifecycle-hooks mechanism, goga's stance, and the future user-hooks place.
- Naming decisions: `run_resumed` / `run_interrupted` normalize afm's
  `flow_resumed` / `flow_interrupted` (goga has no "flow" concept);
  `from_status` / `to_status` normalize afm's `from` / `to` (Python keywords).
- Left open for the design stage (per the ADR): cell placement of the bridge
  code, the context record shapes, the catalog wiring, and the CODEMANIFEST
  changes.
