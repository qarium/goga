# Pipelines — Hooks

The pipelines domain exposes **three hook actions** for tool packages — the checkpoints of the two pipeline forms. One is the platform's first **hard** action: the workflow amendment `pipeline/amend_workflow`, delivered by both the run and the card form before compilation. Two are **soft** notifications bracketing a run's launch. With no tool packages installed the amendment layer is the passthrough — every form behaves exactly as before (byte-identical output, unchanged exit codes).

## The actions

| Address | Error class | Fires |
|---|---|---|
| `pipeline / amend_workflow` | **hard** | After the workflow resolution and the runner-skip merge, before compilation — in both `goga pipeline <name>` (run) and `goga pipeline <name> --info` (card). Not delivered when the workflow decision is disabled (`--no-workflow`); a silent auto-match miss keeps it active onto the empty base. |
| `pipeline / run_created` | soft | After the four agent prompts materialize, immediately before the launch (run form only). |
| `pipeline / run_completed` | soft | On every launch-attempt return path of the run form — success, non-zero, and spawn failures (126/127) alike. |

A tool subscribes inside its `register_hooks` callback:

```python
# inside the goga_tool_<tool> package
from goga.pipeline.workflow import WorkflowDocument


def register_hooks(hooks):
    hooks.subscribe("pipeline", "amend_workflow", "harden", harden_workflow)
    hooks.subscribe("pipeline", "run_completed", "record", record_completion)


def harden_workflow(context):
    context.contribute(WorkflowDocument(prompt="Prefer the pinned toolchain."))


def record_completion(context):
    tools = ", ".join(context.provenance) or "none"
    report(f"{context.pipeline.name} on {context.work.branch}: exit {context.exit_code}, workflow tools: {tools}")
```

A failing moment fires nothing: a run that stops before the amendment (a missing pipeline, a malformed workflow-file) reaches no checkpoint; a structural compile error stops the run after the amendment — the checkpoint has fired and the committed contributions stand, but no notification follows; and no completion fires when the launch attempt itself raises.

## The contexts

### `amend_workflow` — `WorkflowAmendment` (hard)

One fresh view per tool — a failing hook's buffer dies with it.

| Read | Type | Meaning |
|---|---|---|
| `pipeline` | `PipelineIdentity` | the pipeline about to run |
| `decision` | `WorkflowDecision` | how the workflow was chosen |
| `workflow` | `WorkflowDocument | None` | the authored workflow — post decision, post runner-skip merge, pre-layer; read-only and identical for every tool |
| `work` | `WorkIdentity` | the branch/topic identity of the run |

| Method | Effect |
|---|---|
| `contribute(document)` | buffers one `WorkflowDocument`; a later call replaces the earlier whole; an empty document (no prompt, no stages, no extend, no memory) is discarded with a warning — the tool identity rides the warning record as a structured field |

The amendment contract:

- **Mutually blind tools** — every tool reads the same original workflow through its own view; no tool ever sees another tool's contribution.
- **Commit per tool** — a tool's buffer commits as one contribution only after every hook of the tool returned without raising.
- **Hard failure** — the first failing hook stops the command at the first failure with a clean error naming the hook, the tool, and the action — before any compile, write, or launch: `Error: pipeline '<name>' was not amended: hook <name> of tool <tool> failed on pipeline.amend_workflow: <reason>`. A buffer the walk cannot process (a value of an out-of-contract type) fails its hook the same way; a broken tool-package import is the other fatal case.
- **Content only** — an amendment shapes the effective workflow; it cannot cancel, redirect, or defer the run.

The committed contributions merge onto the authored workflow **authored-wins, per slot**:

- `prompt` — the non-empty texts joined with a single blank line, authored first, then the tools in enumeration order.
- Stage fields — an authored-set field never yields; an unset field takes the later contributing tool's value; a stage the author never named is fully tool-defined. `manual` is three-state (`True` and `False` are both authored intent); `skip: false` overrides nothing.
- `extend` — authored names win; among tools the later entry wins per name.
- `memory` — whole-block: the authored block is unbeatable; otherwise the later tool's block wins.

The merged workflow is what `compile_flow` receives in both forms. The card reports the committed tools as its `tools:` line; the run events carry them as `provenance`.

### `run_created` — `RunCreated` (soft)

One shared read-only instance for every tool — a hook observes and cannot alter.

| Read | Type | Meaning |
|---|---|---|
| `pipeline` | `PipelineIdentity` | the identity of the running pipeline |
| `decision` | `WorkflowDecision` | how the workflow was chosen |
| `workflow` | `WorkflowDocument | None` | the effective merged workflow — authored instructions plus the committed tool contributions; `None` when no effective workflow exists |
| `composition` | `list[CompositionStage]` | the compiled stage sequence — one row per compiled stage, as the card shows them |
| `provenance` | `list[str]` | the tools whose contributions merged in, in enumeration order |
| `work` | `WorkIdentity` | the branch/topic identity of the run |
| `statuses` | `list[str]` | the hosting topic's statuses at the moment — both axes, built-in and tool; empty in the branch-only form |
| `runtime_dir` | `str` | the run's runtime directory as a posix string |

Read-only facts; no methods.

### `run_completed` — `RunCompleted` (soft)

One shared read-only instance for every tool — the `RunCreated` reads recomputed at the completion moment, plus the outcome of the launch attempt.

| Read | Type | Meaning |
|---|---|---|
| `exit_code` | `int` | the actual exit code of the launch attempt — zero, non-zero, or a spawn failure 126/127 |

Read-only facts; no methods.

Both notifications are fire-and-forget: a failing hook is skipped with a warning naming the tool, the action, and the reason; the launch proceeds and the run's exit code is never affected.

## No-tools guarantee

With no tool packages installed the registry builds empty and the overlay is the passthrough — the run and the card behave exactly as before this layer existed: byte-identical CLI output and unchanged exit codes.

## The fact records

| Record | Fields |
|---|---|
| `PipelineIdentity` | `name`, `display_name`, `description`, `source` (`project`/`user`) |
| `WorkflowDecision` | `kind` (`disabled`/`explicit`/`auto-match`/`silent-miss`), `workflow_name` |
| `WorkIdentity` | `branch`, `slug`, `year` |
| `CompositionStage` | `id`, `title` |
| `WorkflowDocument` | `prompt`, `stages`, `extend`, `memory` — the contribute vocabulary, covered in [Pipeline File](pipeline-file.md) |

`name` is the discovered file stem; `display_name`/`description` are the authored header values. `workflow_name` is present for `explicit` and `auto-match`. `branch` is the literal `unknown` when git resolves none; `slug`/`year` belong to the hosting topic when the branch hosts one.

The platform mechanism behind the actions (enumeration, the registry, delivery, inspection with `goga hooks`) is the [Hooks](../hooks/index.md) domain; the registration contract for tool authors is covered in [Hooks — The registration contract](../hooks/hooks.md); the flows that fire the checkpoints are covered in [CLI](cli.md) and the facade in [API](api.md).
