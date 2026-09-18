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
    ...  # read-only facts of the finished attempt
```

A failing moment fires nothing: a run that stops before the amendment (a missing pipeline, a malformed workflow-file, a structural compile error) reaches no checkpoint, and no completion fires when the launch attempt itself raises.

## The amendment view (`amend_workflow`)

Each tool receives a **fresh `WorkflowAmendment` view** — the read-and-contribute surface of one tool:

- `pipeline` — the discovered identity: `name` (the file stem), `display_name`/`description` (the authored header values), `source` (`project` or `user`).
- `decision` — the workflow decision: `kind` exactly one of `disabled`, `explicit`, `auto-match`, `silent-miss`, plus the `workflow_name` when one applied.
- `workflow` — the original authored workflow (post decision, post runner-skip merge, pre-layer), **read-only and identical for every tool**.
- `work` — the current work identity: `branch` (the literal `unknown` when git resolves none), and the hosting topic's `slug`/`year` when the branch hosts one.
- `contribute(document)` — buffer one declarative `WorkflowDocument` contribution.

The amendment contract:

- **Whole replacement** — a later `contribute` call replaces the earlier buffered document whole; the buffer belongs to this tool alone.
- **Mutually blind tools** — every tool reads the same original workflow through its own view; no tool ever sees another tool's contribution.
- **Commit per tool** — a tool's buffer commits as one contribution only after every hook of the tool returned without raising.
- **Hard failure** — the first failing hook stops the command at the first failure with a clean error naming the hook, the tool, and the action — before any compile, write, or launch: `Error: pipeline '<name>' was not amended: hook <name> of tool <tool> failed on pipeline.amend_workflow: <reason>`. A buffer the walk cannot process (a value of an out-of-contract type) fails its hook the same way; a broken tool-package import is the other fatal case. An empty document (no prompt, no stages, no extend, no memory) is discarded with a warning naming the tool.
- **Content only** — an amendment shapes the effective workflow; it cannot cancel, redirect, or defer the run.

The committed contributions merge onto the authored workflow **authored-wins, per slot**:

- `prompt` — the non-empty texts joined with a single blank line, authored first, then the tools in enumeration order.
- stage fields — an authored-set field never yields; an unset field takes the later contributing tool's value; a stage the author never named is fully tool-defined. `manual` is three-state (`True` and `False` are both authored intent); `skip: false` overrides nothing.
- `extend` — authored names win; among tools the later entry wins per name.
- `memory` — whole-block: the authored block is unbeatable; otherwise the later tool's block wins.

The merged workflow is what `compile_flow` receives in both forms. The card reports the committed tools as its `tools:` line; the run events carry them as `provenance`.

## The notification contexts

Each notification delivers **the same read-only context instance** to every subscribed tool — a hook observes and cannot alter:

- `run_created` — `RunCreated`: `pipeline`, `decision`, `workflow` (the effective merged workflow), `composition` (the ordered stages of the final composition), `provenance` (the committed tools), `work`, `statuses` (the hosting topic's statuses at the moment; empty in the branch-only form), `runtime_dir` (the run's runtime directory as a posix string).
- `run_completed` — `RunCompleted`: the same facts recomputed at the completion moment, plus `exit_code` — the actual exit code of the launch attempt, zero, non-zero, or a spawn-failure 126/127.

Both are fire-and-forget: a failing hook is skipped with a warning naming the tool, the action, and the reason; the launch proceeds and the run's exit code is never affected.

## No-tools guarantee

With no tool packages installed the registry builds empty and the overlay is the passthrough — the run and the card behave exactly as before this layer existed: byte-identical CLI output and unchanged exit codes.

The platform mechanism behind the actions (enumeration, the registry, delivery, inspection with `goga hooks`) is the [Hooks](../hooks/index.md) domain; the registration contract for tool authors is covered in [Hooks — The registration contract](../hooks/hooks.md); the flows that fire the checkpoints are covered in [CLI](cli.md) and the facade in [API](api.md).
