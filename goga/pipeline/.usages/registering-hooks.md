# pipeline — registering hooks

How a `goga_tool_*` package subscribes its hooks to the pipeline domain
actions. For tool package authors; no goga code changes are needed.

The domain opens three actions. One is an amendment — a read-and-contribute
view over the workflow a run is about to execute, delivered before
compilation; it is the platform's first hard action. Two are notifications —
the read-only facts of the run, delivered immediately before the runner
launch and on every launch-attempt return.

## The events

| Address | Error class | Fires |
|---|---|---|
| `pipeline / amend_workflow` | hard | After the workflow resolution and the runner-skip merge, before compilation — in the run form and in the card form alike. |
| `pipeline / run_created` | soft | Immediately before the runner launch — after compilation and prompt materialization. |
| `pipeline / run_completed` | soft | On every launch-attempt return — zero, non-zero, and spawn failures (126/127) alike. |

A failing moment fires nothing: a missing pipeline and a structural
composition error return before any checkpoint.

## Subscribe

```python
# inside the goga_tool_<tool> package
def register_hooks(hooks):
    hooks.subscribe("pipeline", "amend_workflow", "hardening", add_hardening)
    hooks.subscribe("pipeline", "run_completed", "reporter", report_run)
```

- `domain` — always `"pipeline"`.
- `action` — the event name from the table above.
- `name` — the hook name, unique per tool per address.
- `hook` — the callable executed when the event fires.

A hook receives values only for the parameters it declares by the fixed
offered names: `context` — the delivered object of the event, read
attributes and call methods freely, attribute assignment is blocked;
`self` — the isolated context of your tool. The declaration order does not
matter; names you did not declare receive nothing.

## The amendment view

`amend_workflow` delivers a `WorkflowAmendment` view per tool. The
reads: `pipeline` — the identity of the running pipeline; `decision` —
the workflow decision (disabled / explicit / auto-match / silent-miss,
with the resolved name); `workflow` — the original authored workflow
after the decision and the runner-skip merge, read-only and identical
for every tool (None when no workflow resolved); `work` — the current
work identity.

```python
def add_hardening(context):
    context.contribute(hardening_workflow)
```

- `contribute(document)` buffers one declarative `WorkflowDocument`-shaped
  contribution — the same instruction vocabulary an authored
  workflow-file uses (prompt, stages, extend, memory).
- Your tool's contribution commits only after every hook of your tool
  returns without raising; a repeat call replaces your buffer whole.
- Authored intent wins per slot: the prompt appends (authored first, tool
  texts in enumeration order), the memory block is whole (an authored
  block is unbeatable), stage fields fill only what the author left
  unset, extend entries add under fresh names. `skip` is an ordinary
  field — an authored skip is unbeatable, an unset skip is yours to set,
  including removing a pipeline-file stage the author did not protect.
- A failing hook of the amendment stops the command with a clean error
  naming your tool and the action; your whole contribution is discarded.
- The merged workflow passes the same compilation validation as an
  authored one — a contribution naming an unknown stage surfaces as the
  compiler's structural error.

## The run notifications

Both notifications deliver read-only facts; a failing hook warns naming
your tool, the action, and the reason — the run's exit code is never
affected.

- `run_created` — `RunCreated`: `pipeline`, `decision`, `workflow` (the
  final effective workflow — authored instructions plus the committed
  tool contributions), `composition` (the ordered stages as the card
  shows them), `provenance` (the tools whose contributions committed),
  `work`, `statuses` (the maximal present topic statuses at the moment),
  `runtime_dir`.
- `run_completed` — `RunCompleted`: the same facts recomputed at the
  completion moment, plus `exit_code` — the actual exit code of the
  launch attempt. Completion is a fact, not a success claim.

## Integration scenarios

- **Artifact → status on completion** — subscribe to `run_completed`,
  read `work` and `exit_code`, register your status on the statuses
  domain keyed by your artifact.
- **Run reporting and automation** — subscribe to `run_created` and
  `run_completed`, read the facts, keep state in your `self` context.
- **Workflow personalization** — subscribe to `amend_workflow`, read
  `workflow`, contribute your declarative adjustments.
- **On-the-fly composition add-ons** — contribute `extend` entries with
  fresh stage names; authored names always win.
