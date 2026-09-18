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
  wins per slot — the prompt appends, the memory block is whole, stage
  fields fill only what the author left unset, extend entries add.
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
