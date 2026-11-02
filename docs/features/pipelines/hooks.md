# Pipelines — Hooks

The pipelines domain exposes **eighteen hook actions** for tool packages — the checkpoints of the two pipeline forms plus the live events of the run interior. One is the platform's first **hard** action: the workflow amendment `pipeline/amend_workflow`, delivered by both the run and the card form before compilation. Two are **soft** notifications bracketing a run's launch. Fifteen are **soft** bridged mid-run events — the thirteen stage transitions and the run-level resume/interrupt — delivered live while the run still executes. With no tool packages installed the amendment layer is the passthrough — every form behaves exactly as before (byte-identical output, unchanged exit codes).

## The actions

| Address | Error class | Fires |
|---|---|---|
| `pipeline / amend_workflow` | **hard** | After the workflow resolution and the runner-skip merge, before compilation — in both `goga pipeline <name>` (run) and `goga pipeline <name> --info` (card). Not delivered when the workflow decision is disabled (`--no-workflow`); a silent auto-match miss keeps it active onto the empty base. |
| `pipeline / run_created` | soft | After the four agent prompts materialize, immediately before the launch (run form only). |
| `pipeline / run_completed` | soft | On every launch-attempt return path of the run form — success, non-zero, and spawn failures (126/127) alike. |

Alongside the three composition-time actions, fifteen **soft** mid-run actions deliver the run interior live — one event per lifecycle transition, while the stages still execute:

| Class | Actions | Context |
|---|---|---|
| Stage transitions (13) | `stage_planning_started`, `stage_plan_ready`, `stage_approved`, `stage_revision_started`, `stage_execution_started`, `stage_question_asked`, `stage_question_answered`, `stage_retry_scheduled`, `stage_retry_started`, `stage_paused`, `stage_resumed`, `stage_finished`, `stage_failed` | `StageEvent` |
| Run-level (2) | `run_resumed`, `run_interrupted` | `RunEvent` |

A tool subscribes inside its `register_hooks` callback:

```python
# inside the goga_tool_<tool> package
from goga.pipeline.workflow import WorkflowDocument


def register_hooks(hooks):
    hooks.subscribe("pipeline", "amend_workflow", "harden", harden_workflow)
    hooks.subscribe("pipeline", "run_completed", "record", record_completion)
    hooks.subscribe("pipeline", "stage_execution_started", "notify", on_stage_start)


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
| `contribute(document)` | buffers one `WorkflowDocument`; a later call replaces the earlier whole; an empty document (no prompt, no stages, no extend, no memory, no assistants, no delegation, no repeat) is discarded with a warning — the tool identity rides the warning record as a structured field |

The amendment contract:

- **Mutually blind tools** — every tool reads the same original workflow through its own view; no tool ever sees another tool's contribution.
- **Commit per tool** — a tool's buffer commits as one contribution only after every hook of the tool returned without raising.
- **Hard failure** — the first failing hook stops the command at the first failure with a clean error naming the hook, the tool, and the action — before any compile, write, or launch: `Error: pipeline '<name>' was not amended: hook <name> of tool <tool> failed on pipeline.amend_workflow: <reason>`. A buffer the walk cannot process (a value of an out-of-contract type) fails its hook the same way; a broken tool-package import is the other fatal case.
- **Content only** — an amendment shapes the effective workflow; it cannot cancel, redirect, or defer the run.

The committed contributions merge onto the authored workflow **authored-wins, per slot**:

- `prompt` — the non-empty texts joined with a single blank line, authored first, then the tools in enumeration order.
- Stage fields — an authored-set field never yields; an unset field takes the later contributing tool's value; a stage the author never named is fully tool-defined. `manual` is three-state (`True` and `False` are both authored intent); `skip: false` overrides nothing. The one keyed exception is stage `env`: it merges per key — authored entries are unbeatable per key, and a contributing tool fills only the keys the author left unset (a later tool wins per key over an earlier fill).
- `profile` / `build` — never merged: the base workflow's values carry verbatim, and a contribution's `profile` or `build` fields never participate (a document contributing only them counts as empty — no prompt, stages, extend, memory, assistants, delegation, or repeat — and is discarded per the `contribute(document)` rule above).
- `extend` — authored names win; among tools the later entry wins per name.
- `memory` — whole-block: the authored block is unbeatable; otherwise the later tool's block wins.
- `delegation` — whole-block like `memory`: the authored block is unbeatable; otherwise the later tool's block wins.
- `repeat` — whole-block like `delegation`: the authored block is unbeatable; otherwise the later tool's block wins.
- `assistants` (the top-level catalog) — an authored entry overrides the winning delivered entry of the same name **field by field** (authored fields replace whole, omitted fields flow from the tool's delivery — see [Workflows — Assistant overrides](workflows.md#assistant-overrides)); a fresh name takes the later contributing tool's entry verbatim. A delivered name under an authored *inline* declaration never lands in the catalog — the authored surface owns the name, and the stage pass below composes the override in place (the name must live in the namespace exactly once).
- stage `assistants` (the per-stage attachment maps) — an authored declaration overrides the winning delivered entry of the same name **in place** (position preserved, same field-by-field rule); otherwise append-with-dedup: the authored entries first in authored order, then the contribution entries in enumeration order; a name already on the stage is dropped silently, and an appended inline declaration whose name is already in the document-wide assistant namespace is dropped the same way.

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

### The stage transitions — `StageEvent` (soft)

One shared read-only instance for every tool — the run facts plus the transition of one stage.

| Read | Type | Meaning |
|---|---|---|
| `pipeline` | `str` | the pipeline name of the running flow |
| `run` | `RunIdentity` | the run identity of the event |
| `stage` | `StageTransition` | the transition of the stage — `id`, `name`, `from_status`, `to_status`, `phase` |
| `event_id` | `str` | the stable event identity — the idempotency key of the emission |
| `occurred_at` | `str` | the event moment as an ISO-8601 UTC string |
| `reason` | `str` | the free-text cause of the event; empty when the source names none |

### `run_resumed` / `run_interrupted` — `RunEvent` (soft)

One shared read-only instance for every tool — the same reads as `StageEvent` without the `stage` block.

All fifteen mid-run events are fire-and-forget soft notifications: a failing hook warns naming the tool and the action; the event, the run, and the other subscribers are unaffected.

## The mid-run bridge

The fifteen mid-run actions are bridged, not fired by the run coordination. afm (v1.2.17+) ships a **lifecycle-hooks** mechanism — observer commands it launches on every flow and stage transition of a run. The in-container run coordination writes the whole `~/.afm/config.yaml` on every launch, including goga's own observer hook in the global layer (`id: goga`, `command: python3 -m goga.pipeline hook`, `events: all`, afm-default timeout and retries) — always on, no user action or configuration involved. When afm reports a transition, that hook command runs and bridges the event onto the platform actions above.

The delivery contract of the bridged events:

- **One short-lived process per event** — afm spawns the hook command fresh for every lifecycle transition; each process builds the surface, emits one event, and exits. `self` state dies with the event — persist across events in your own storage.
- **Live best-effort, no replay** — an event not delivered before a crash is gone; subscribers are documented to tolerate gaps.
- **Observer semantics end-to-end** — a hook never changes the run: not on the afm side (a hook error never changes the flow outcome) and not on the goga side (a failing subscriber warns and the run continues).
- **Curated vocabulary** — only the fifteen actions above are bridged; the afm script events and the remaining flow boundaries arrive but emit nothing (the process exits 0 without importing the platform).

Environment visibility: the bridge hook entry sets `inherit_env: true` deliberately. The hook process — and the goga subscriber hooks running inside it — inherits the full afm process environment, including the launch env layers (env-file layers, the `pipeline.env` task layer, CLI `-e` entries). Treat the environment as visible to your hooks; the bridge declares no `env` map of its own and no secrets.

Two "hooks" vocabularies exist in this surface and stay distinct: the **goga platform actions** — the subscription addresses a `goga_tool_*` package subscribes to via `hooks.subscribe` — and the **afm lifecycle hooks** — the observer-command mechanism of afm that goga's bridge consumes. Tool packages always target the first; the second is goga-internal machinery, authored only by the run coordination in the global layer (a more specific afm layer may replace goga's entry by id — afm's designed control point).

## No-tools guarantee

With no tool packages installed the registry builds empty and the overlay is the passthrough — the run and the card behave exactly as before this layer existed: byte-identical CLI output and unchanged exit codes. The bridge stays silent the same way: with no subscribers every bridged event emits into an empty registry and the run is unaffected.

## The fact records

| Record | Fields |
|---|---|
| `PipelineIdentity` | `name`, `display_name`, `description`, `source` (`project`/`user`) |
| `WorkflowDecision` | `kind` (`disabled`/`explicit`/`auto-match`/`silent-miss`), `workflow_name` |
| `WorkIdentity` | `branch`, `slug`, `year` |
| `CompositionStage` | `id`, `title` |
| `RunIdentity` | `run_id`, `run_dir`, `root_dir`, `resumed` — the run facts carried by every bridged mid-run event |
| `StageTransition` | `id`, `name`, `from_status`, `to_status`, `phase` — the transition of one stage |
| `WorkflowDocument` | `prompt`, `stages`, `extend`, `memory`, `profile`, `build`, `assistants`, `delegation`, `repeat` — the contribute vocabulary, covered in [Pipeline File](pipeline-file.md); a tool's `profile` / `build` contributions never merge (the base values ride verbatim) |

`name` is the discovered file stem; `display_name`/`description` are the authored header values. `workflow_name` is present for `explicit` and `auto-match`. `branch` is the literal `unknown` when git resolves none; `slug`/`year` belong to the hosting topic when the branch hosts one.

The platform mechanism behind the actions (enumeration, the registry, delivery, inspection with `goga hooks`) is the [Hooks](../hooks/index.md) domain; the registration contract for tool authors is covered in [Hooks — The registration contract](../hooks/hooks.md); the flows that fire the checkpoints are covered in [CLI](cli.md) and the facade in [API](api.md).
