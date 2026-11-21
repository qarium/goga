# pipeline — amending workflows and emitting run checkpoints

How the pipeline flows consume the hooks zone of the pipeline domain:
delivering the workflow amendment before compilation and emitting the two
run notifications around the runner launch. For the run coordination and
the card over the pipeline facade.

## The checkpoint surface

One `PipelineHooks` object serves every checkpoint of a command — the
surface shares one registry per run, so a command that reaches several
checkpoints enumerates the tool packages once.

```python
from goga.pipeline.hooks import PipelineHooks

hooks = PipelineHooks()
```

## Resolve the facts in the operation

Every context is built from the values the caller passes — the checkpoint
reads no repository. Resolve the facts before the delivery:

- `PipelineIdentity` — the discovered pipeline name, the authored header
  name and description, and the source (`project` or `user`).
- `WorkflowDecision` — the outcome of the workflow resolution: `disabled`,
  `explicit`, `auto-match`, or `silent-miss`, with the resolved workflow
  name when applicable.
- `WorkIdentity` — the current branch with the topic slug and year when
  the branch hosts a topic; the branch-only form otherwise.
- `loaded.profile` — the operation's already-resolved active contributor
  profile (the profile that rendered the authored workflow-file), or
  `None`; the delivery receives it as operation data — the checkpoint
  never reads or re-resolves it.

## Amend before compilation

Deliver the amendment after the runner-skip merge and before
`compile_flow`; compile the effective workflow the delivery returns.

```python
overlay = hooks.amend_workflow(
    pipeline=identity,
    decision=decision,
    workflow=merged_workflow,  # None is valid — a silent miss keeps the layer active
    work=work,
    profile=loaded.profile,  # the resolved profile or None — every tool's view and the rendering use it
)
compile_flow(overlay.workflow, ...)
```

- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, the repeat
  block is whole, the gates settings block is whole, stage fields fill only
  what the author left unset (an authored per-stage check-step list is
  never overwritten), extend entries add; the workflow-global run settings
  (`agent`, `env`) ride the authored workflow verbatim — a tool can
  neither supply nor override them; the assistant catalog merges
  with field-level overrides — the winning tool-delivered entry of a name
  is the base and the authored entry replaces exactly the fields it
  specifies (agent, env, delegate, prompt, skills; an explicit empty
  skills/env clears), omitted fields flow from the tool, a delivered name
  with no authored entry adds fresh (tool inline declarations under an
  authored name stay dropped); the delegation block is whole, and stage
  assistant maps append with name deduplication — an appended entry may
  carry any authored form (a reference, a full inline declaration, a
  when-less extension, a `{skip: true}` veto): entries addressing names
  the workflow-file does not declare (pipeline-file declarations) pass
  through undistorted, and the origin classification plus the
  effective-namespace uniqueness are compilation checks.
- Every tool's view carries the same read-only profile fact (`profile` —
  name, content, source, or `None` without activation); the card and the
  run form deliver the same fact.
- At each tool's commit the buffered contribution renders field-level
  with the active profile's content (workflow rendering semantics; an
  empty context without activation) — before the unchanged
  presence-based empty-contribution check and the authored-wins merge.
- A render failure in any contributed string is hard: the command stops
  pre-run with the amendment-failure error (tool, action) carrying the
  template cause (error class, message, document path); the tool's
  contribution is discarded and later tools' hooks never run.
- A contribution without template syntax composes byte-identically, with
  or without an active profile.
- The amendment action is hard: the first failing tool stops the command
  with a clean error naming the tool and the action; the tool's whole
  contribution is discarded.
- An address without subscriptions returns the passthrough overlay — the
  workflow stays what was passed, the provenance is empty. With no tool
  packages installed every run composes exactly what was passed.

## Emit around the launch

Emit the creation immediately before the runner launch (after compilation
and prompt materialization) and the completion on every launch-attempt
return — zero, non-zero, and spawn failures alike.

```python
hooks.emit_run_created(
    pipeline=identity,
    decision=decision,
    overlay=overlay,
    composition=stages,
    work=work,
    statuses=statuses,
    runtime_dir=runtime_dir,
)
exit_code = run_flow(...)
statuses = resolve_topic_status(topic_dir, scale)  # recompute at the moment
hooks.emit_run_completed(
    pipeline=identity,
    decision=decision,
    overlay=overlay,
    composition=stages,
    work=work,
    statuses=statuses,
    runtime_dir=runtime_dir,
    exit_code=exit_code,
)
```

- Both notifications are fire-and-forget: a failing hook warns naming the
  tool, the action, and the reason; the run's exit code is unaffected.
- `composition` carries the ordered stages as the card shows them; build
  it from the compiled stages of the same compilation the run executes.

## The card form

The card composes through the same amendment with the same precedence and
reports `overlay.provenance` as the contributing tools. No run events fire
in card form.

## Emit the bridged run-interior events

How the bridge command of a run feeds one lifecycle event into the zone —
for the in-container hook entry of the run interior.

The lifecycle mechanism spawns a fresh short-lived process per event: the
event arrives as a JSON object on stdin with the event facts in the process
environment. Each process is its own command — build the surface, emit once,
exit.

```python
from goga.pipeline.hooks import (
    PipelineHooks,
    RunEvent,
    RunIdentity,
    StageEvent,
    StageTransition,
)

hooks = PipelineHooks()

# run-level event
hooks.emit_run_event(
    action="run_resumed",
    context=RunEvent(
        pipeline=pipeline_name,
        run=RunIdentity(run_id=..., run_dir=..., root_dir=..., resumed=...),
        event_id=...,
        occurred_at=...,
    ),
)

# stage-level event
hooks.emit_stage_event(
    action="stage_execution_started",
    context=StageEvent(
        pipeline=pipeline_name,
        run=run_identity,
        stage=StageTransition(id=..., name=..., from_status=..., to_status=..., phase=...),
        event_id=...,
        occurred_at=...,
    ),
)
```

- Resolve the event name to the action name before touching the platform —
  an event outside the curated vocabulary emits nothing; the process exits
  0 without building the registry.
- The contexts are pure passthrough facts — carry the payload values under
  the idiomatic names, never the raw payload; `reason` defaults to an empty
  string when the source names none.
- One `PipelineHooks` object per event process — the registry builds once
  per process, at the first emission.
- Both emissions are fire-and-forget: a failing hook warns naming the tool
  and the action; nothing is collected and the exit code never changes.
- Delivery is live best-effort with no replay — an event not delivered
  before a crash is gone; subscribers are documented to tolerate gaps.
