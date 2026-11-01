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

## Amend before compilation

Deliver the amendment after the runner-skip merge and before
`compile_flow`; compile the effective workflow the delivery returns.

```python
overlay = hooks.amend_workflow(
    pipeline=identity,
    decision=decision,
    workflow=merged_workflow,  # None is valid — a silent miss keeps the layer active
    work=work,
)
compile_flow(overlay.workflow, ...)
```

- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, the repeat
  block is whole, stage fields fill only what the author left unset, extend
  entries add; the assistant catalog adds fresh names (authored names win, a
  tool name colliding with any name already in the merged assistant
  namespace is dropped), the delegation block is whole, and stage assistant
  maps append with name deduplication.
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
