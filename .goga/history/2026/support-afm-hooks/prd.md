# afm Lifecycle Hooks Support in goga

Support the afm lifecycle-hooks mechanism from the goga side: goga registers its
own observer hook with afm on every pipeline run and bridges afm's per-stage
lifecycle events onto goga's internal extension platform, so tools can react to
a run while it executes.

## Problem

A goga pipeline run launches `afm` as a blocking subprocess and treats it as a
black box. goga's extension platform speaks only at the run boundaries —
`run_created` fires right before the launch and `run_completed` fires after
afm exits, carrying the exit code and recomputed artifact statuses. Between
those two moments goga sees nothing of what happens inside the run.

Who experiences this and how:

- **goga tool authors** cannot build stage-granular reactions (notifications,
  metrics, external status mirrors, automation): the platform has no event
  vocabulary for stage transitions, approval waits, questions, failures, or
  retries. Anything they build today can only react after the entire flow ends.
- **goga pipeline users** are affected indirectly: the ecosystem around them
  cannot react while their long runs execute (tens of minutes, approval
  pauses, failures, interruptions), so mid-run awareness requires watching the
  afm dashboard directly.

afm already emits exactly the missing information: a lifecycle-hooks mechanism
that delivers a JSON event for every flow and stage transition. goga consumes
none of it. Worse, goga rewrites the whole in-container `~/.afm/config.yaml` on
every launch, so even a manually placed global-layer hook cannot survive a
goga-run launch — the mechanism stays out of reach for goga-launched runs
entirely.

## Users

**Primary beneficiary — goga tool author (extension developer).**

- Writes goga tools that subscribe to platform events through the existing
  tool-declaration mechanics (`declared_actions`, tool packages, registry).
- Wants to subscribe to per-stage run lifecycle events through the same
  mechanics and receive enough context in each event — flow identity, stage
  identity, transition, outcome, reason — to react without reading afm
  internals.
- Needs reactions to be fast (afm enforces a per-hook timeout, 30s by default)
  and tolerant of missed events (delivery is live best-effort, no replay).
- Expects observer semantics: a failing subscriber hook must never affect the
  run, other subscribers, or the bridge — the same soft, warn-only contract
  the platform's notification events already use.

**Secondary — goga pipeline user (developer running pipelines).**

- Starts runs exactly as today; no new flags, commands, or configuration.
- Benefits indirectly: tools reacting mid-run (e.g. a messenger notification
  when a stage fails or a question is asked) instead of after the whole flow.

**Excluded** — the afm stage approver: their interaction surface is the afm
dashboard, which this change does not touch.

## Goals

1. **Stage-granular run lifecycle events on the goga extension platform.**
   Tool authors can subscribe — through the tool-declaration mechanics they
   already use — to live flow- and stage-level run events carrying enough
   context to react without reading afm internals.

2. **Observation the run can trust.** Watching a run — event delivery to tools
   included — never changes its outcome and never blocks it beyond bounded
   best-effort waits. afm's observer-only hook semantics are preserved
   end-to-end on the goga side.

3. **A deliberate place for user-authored hooks.** The integration between
   goga and the afm hooks mechanism is shaped and documented so that future
   user-facing hooks authoring (workflow/config → flow-file) lands without
   reworking the mechanism.

## User Experience

**Entry point — unchanged for everyone.**

- The pipeline user starts a run exactly as today. goga's observer hook is
  registered automatically by the run coordination on every launch; nothing
  new to learn, enable, or configure.
- The tool author declares a tool and its event subscriptions exactly as
  today. The new run-lifecycle actions simply appear in the platform's
  declared-actions catalog.

**Primary scenario.**

1. The user starts a long pipeline run and walks away.
2. While the run executes, subscribed tools receive live stage events —
   `stage_execution_started`, `stage_question_asked` / `stage_question_answered`,
   `stage_failed`, `stage_retry_scheduled` / `stage_retry_started`,
   `stage_paused` / `stage_resumed`, `stage_finished`, `stage_plan_ready`,
   `stage_approved`, and the rest of the curated vocabulary — each carrying
   flow identity, stage identity, the transition, and the reason where afm
   provides one.
3. Reactions fire mid-run: a notifier messages the user when a stage asks a
   question or fails; a mirror updates an external system as stages finish —
   no one waits for the whole flow to end.
4. When the run ends, the existing boundary events fire exactly as before;
   artifacts, statuses, and exit-code propagation are unchanged.

**Alternative paths.**

- Approval and question waits arrive as events; answers and approvals arrive
  as events.
- A stage failure and its scheduled/started retry are observable as they
  happen.
- An interrupted run arrives as an event; the run boundaries still fire as
  they do today.

**Observation-channel failures.**

- If goga's hook command itself errors, hangs, or receives damaged input, the
  run is never affected: afm's observer semantics guarantee a hook failure
  never changes a stage result or the flow outcome. The failure is visible in
  the per-hook log (`.afm/runs/<run-id>/hooks/<hook-id>.log`) and as an afm
  dashboard warning. The bridge simply misses that one event.
- Events can be missed: delivery is live best-effort with no replay after a
  crash. The subscriber contract states this explicitly; the afm dashboard and
  run directory remain the authoritative record.

**Consequences.**

- Observation is passive: it approves nothing, changes nothing, resets
  nothing. Existing flows, artifacts, statuses, and exit codes behave exactly
  as before the change.

**Future place.**

- The afm integration contract (`.goga/usages/cooks/afm.md`) documents the
  afm hooks mechanism, goga's stance, and the considered place for
  user-authored hooks, so a later authoring task extends the mechanism instead
  of reworking it.

## Requirements

**R1 — Automatic registration.** On every pipeline run, the afm config that
goga writes declares goga's own hook entry: id `goga`, command
`python3 -m goga.pipeline hook` (the in-container CLI precedent), `events:
all`, `inherit_env: true`, afm-default timeout and retries — declared in the
global layer, always on. No user action or configuration is involved. All
config fields goga writes today remain intact — the resolved `client.command`
and the four non-configurable statics.

**R2 — Event reception.** goga's hook command receives every public afm
lifecycle event of the run — the full JSON payload on stdin plus the `AFM_*`
environment afm provides. Damaged, truncated, or unexpected input is handled
without ever affecting the run.

**R3 — Curated bridge vocabulary.** afm's stage-level transitions map to new
platform actions in the `pipeline` domain: `stage_planning_started`,
`stage_plan_ready`, `stage_approved`, `stage_revision_started`,
`stage_execution_started`, `stage_question_asked`, `stage_question_answered`,
`stage_retry_scheduled`, `stage_retry_started`, `stage_paused`,
`stage_resumed`, `stage_finished`, `stage_failed` (afm names unchanged — goga
has stages), plus `run_resumed` and `run_interrupted` — the normalized
goga-side names of afm's `flow_resumed` and `flow_interrupted` (goga has no
"flow"; no existing platform analogs). afm events outside the curated set —
script events, internal high-frequency events, and the flow boundaries —
produce no new platform actions; run boundaries stay with the unchanged
`run_created` / `run_completed`.

**R4 — Event context.** Every bridged event carries pipeline identity
(`name`), run identity (`run_id`, `run_dir`, `root_dir`, `resumed`), stage
identity (`id`, `name`, `from_status`, `to_status`, `phase`), `event_id` (the
idempotency key), `occurred_at`, and the `reason` when afm provides one —
passthrough values under goga-idiomatic names, sufficient for a tool to
react without knowing afm's internals; the raw payload is not exposed
(`from_status` / `to_status` normalize afm's `from` / `to`, which are Python
keywords and cannot be attribute names).

**R5 — Subscription mechanics.** Tool authors subscribe through the existing
tool-declaration mechanics; the new actions appear in the declared-actions
catalog. The events are soft, warn-only: a subscriber failure never affects
the run, other subscribers, or the bridge itself.

**R6 — Observer trust.** The bridge never changes flow or stage outcomes. The
hook command completes fast — well within afm's default 30s per-hook timeout —
so stage transitions are never delayed beyond afm's bounded waits.

**R7 — Missed-event tolerance.** The subscriber-facing contract documents that
delivery is live best-effort with no replay after a crash, so tools are built
tolerant of gaps.

**R8 — Diagnosability.** Bridge failures are observable — per-hook log entries
and warnings — while the run continues.

**R9 — Contract documentation.** The afm integration usage
(`.goga/usages/cooks/afm.md`) is extended with:

- the afm lifecycle-hooks mechanism: the four declaration layers with
  id-override semantics, the event catalog, the JSON payload and `AFM_*`
  environment, the `sh -c` execution model with CWD = the flow's `root_dir`,
  the observer-only failure semantics, per-hook logs, and the live best-effort
  delivery guarantees;
- goga's stance: its own hooks are always-on via the global layer, which goga
  fully authors — manual global-layer hooks do not survive a goga launch;
  user-authored hooks belong in the project layer (`.afm/config.yaml` in the
  project root) today, which goga never touches and afm unions natively; the
  flow-file layers are the future authoring surface for the compiler. The
  overridable-id consequence is stated: a more specific layer can replace
  goga's hook by id — afm's designed control point;
- the deliberate future place for user-authored hooks, including the
  context-formation considerations, so a later authoring task extends the
  mechanism instead of reworking it.

**R10 — Non-goals.** No topics board or history live statuses. No user-facing
hooks authoring. No modifications to afm. No new user-facing CLI flags,
commands, or configuration surface.

## Constraints

- **C1.** afm is external and unmodifiable; goga adapts to its contract only.
- **C2.** afm hooks are observer-only: a hook error never changes the FSM, a
  stage result, or the flow outcome.
- **C3.** afm's execution model binds the hook command: `sh -c`, CWD = the
  flow's `root_dir`, the full JSON event on stdin, `AFM_*` environment
  variables; events for one hook are delivered sequentially, different hooks
  run in parallel; the queue drains within a bounded wait on clean exit, with
  the terminal `flow_finished` / `flow_failed` event emitted before the flush.
- **C4.** Delivery is live best-effort with no replay after a crash; the
  per-hook timeout defaults to 30s and retries to 0.
- **C5.** `events: all` covers the public lifecycle catalog only — internal
  high-frequency events are not delivered.
- **C6.** Layer id rules: ids are unique per layer; a more specific layer
  replaces the same id (`global < project < flow < stage`). goga's hook id can
  be overridden or replaced by the user in more specific layers — this is
  afm's designed control point and is documented as such.
- **C7.** goga rewrites the whole in-container `~/.afm/config.yaml` on every
  launch; registration is part of that write, and the existing fields and
  non-configurable statics are preserved.
- **C8.** The platform's semantics are preserved: the registry is built once
  per command, soft events warn only, and the existing action contracts
  (`amend_workflow`, `run_created`, `run_completed`) are unchanged.
- **C9.** Run boundaries are not duplicated as new actions.
- **C10.** The hook command must be resolvable in-container, following the
  `python -m goga.*` entrypoint precedent (host-side invocations fail loudly).
- **C11.** No new user-facing surface of any kind.
- **C12.** `.goga/usages/cooks/afm.md` is the single integration contract
  document for everything afm-facing.
- **C13.** The two "hooks" vocabularies stay distinct in product language:
  goga's internal tool-extension hooks platform vs afm's lifecycle hooks
  (external observer commands). Documentation keeps them unambiguous.
- **C14.** Topics board / history live statuses are out of scope (explicit
  user decision).
- **C15.** User-facing hooks authoring is documented only, not implemented
  (explicit user decision).
- **C16.** The bridge declares no secret `env` map of its own (afm hook `env`
  values are `file:` / `env:` references; goga's bridge needs none), but it
  registers with `inherit_env: true` (ADR decision, amending the original
  no-carriage wording; risk explicitly accepted): the hook process — and the
  subscriber hooks running inside it — inherits the afm process environment,
  including the launch env layers (env-file layers, the `pipeline.env` task
  layer, CLI `-e` entries). This carriage is deliberate; the subscriber env
  visibility is documented explicitly in the subscription docs and `afm.md`.

## Scope

### In Scope

1. **goga's afm hook command** — an in-container CLI module invocation (the
   `python -m goga.*` precedent) that receives public afm lifecycle events,
   tolerates damaged input, maps them to the curated vocabulary, and emits
   soft events on the internal hooks platform with a never-block failure
   discipline.
2. **Automatic registration** of that hook entry in the afm config write on
   every pipeline run.
3. **The curated stage-event vocabulary with its contexts** as subscribable
   platform actions, plus the tool-facing subscription documentation.
4. **The afm.md contract extension** covering the afm hooks mechanism, goga's
   always-on stance (including the overridable-id and global-layer-ownership
   consequences), and the deliberate future place for user-authored hooks with
   context-formation considerations.

### Out of Scope

- Topics board / history live statuses.
- User-facing hooks authoring (workflow/config → flow-file compilation).
- Any modification of afm.
- New user-facing CLI flags, commands, or configuration surface.
- Changes to the existing event contracts (`amend_workflow`, `run_created`,
  `run_completed`).
- Durable / at-least-once event delivery or replay (an afm-side planned
  feature; goga builds no queue of its own).
- First-party consumer tools (notifications, metrics, mirrors) — the
  ecosystem's job, not goga's.

## Success Criteria

1. **Live mid-run delivery.** During a real pipeline run, a tool subscribed to
   a stage-level action receives the event while the stage is still executing
   — before the run completes — with the full context: pipeline name,
   `run_id`, `run_dir`, `root_dir`, `resumed`; stage id, name, `from_status`,
   `to_status`, `phase`; `event_id`; `occurred_at`; and `reason` when present.
2. **Existing mechanics only.** The subscription works purely through the
   existing tool-declaration mechanics; the new actions appear in the declared
   catalog; no new registration mechanism exists.
3. **Exact vocabulary.** Every curated-vocabulary afm event is bridged; afm
   events outside the set (script events, internals, flow boundaries) produce
   no new platform actions; `run_created` / `run_completed` fire exactly as
   before with unchanged contexts.
4. **Failures never leak into the run.** A failing hook command (exception,
   malformed stdin, hang) leaves the run identical — same stages, same
   statuses, same exit code as a run without the bridge — and the failure is
   visible in the per-hook log.
5. **Speed.** The hook command completes far inside afm's default 30s timeout
   for every event; stage transitions are never delayed beyond afm's bounded
   hook waits.
6. **Always-on registration.** Every pipeline run's written afm config carries
   goga's hook entry automatically — stable id, global layer, all existing
   fields intact — with zero user action and zero new configuration.
7. **Honest contract.** The delivery guarantees (live best-effort, no replay)
   and observer semantics are documented for tool authors in the subscription
   docs — learnable without reading code.
8. **The future place is real.** afm.md documents the afm hooks mechanism,
   goga's stance (always-on global-layer hooks, the overridable-id
   consequence, global-layer ownership), and the future user-hooks place
   (including context-formation considerations) well enough to plan future
   authoring without redoing the mechanism.
9. **Zero regressions.** For the pipeline user everything behaves as today:
   identical launch flow, flow-file, exit-code propagation, and existing
   events.

## Dependencies and Assumptions

- The integration image ships an afm binary with lifecycle-hooks support.
  With an older binary the hooks config key is silently ignored and the bridge
  is simply absent — no run impact either way.
- afm delivers events to a single hook sequentially, so the bridge observes
  event order.
