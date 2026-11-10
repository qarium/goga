# Pipelines — API

The facade of the domain package **`goga.pipeline`** — discovery and run coordination of goga pipeline files. The DSL parsing and flow compilation live in the nested cells `goga.pipeline.workflow` and `goga.pipeline.compiler`, and the hooks zone of the domain (the workflow amendment, the run notifications, and the bridged mid-run lifecycle events) in `goga.pipeline.hooks`; this facade carries the discovery, description, run, and lifecycle-event-bridge surfaces.

The signatures below are the CODEMANIFEST contract of the cell.

## Discovery and description

```python
list_pipelines(project_dir: Path, user_dir: Path) -> list[PipelineEntry]
describe_pipelines(project_dir: Path, user_dir: Path) -> list[PipelineSummary]
describe_pipeline(name: str, project_dir: Path, user_dir: Path,
                  workflow: str | None, no_workflow: bool,
                  profile: str | None = None,
                  skip: list[str] | None = None) -> PipelineCard
```

`list_pipelines` enumerates the flat `*.yml` files of the two sources (project wins on name conflict); `describe_pipelines` adds each pipeline's header fields; `describe_pipeline` compiles the pipeline with the same workflow rule set and the same `skip` merge as a run and returns its card — the stages in execution order.

```python
PipelineEntry(name: str, source: PipelineSource)
PipelineSummary(name: str, source: PipelineSource, description: str, display_name: str = "")
PipelineCard(name: str, description: str, stages: list[CardStage], provenance: list[str] = [])
CardStage(id: str, title: str)
```

The discovery and description result types. `PipelineSource` distinguishes the project and user origins. `PipelineCard.provenance` carries the tools whose workflow contributions committed into the composition, in enumeration order — empty when none contributed (see [Hooks](hooks.md)).

## Workflow resolution and stage ordering

```python
resolve_workflow(pipeline_name: str, workflow_name: str | None,
                 no_workflow: bool,
                 cli_profile: str | None = None, env_profile: str | None = None,
                 home_profiles: dict[str, dict[str, Any]] | None = None) -> LoadedWorkflow | None
apply_skip_stages(workflow: WorkflowDocument | None, skip_stages: list[str]) -> WorkflowDocument | None
order_stages(stages: list[FlowStage]) -> list[FlowStage]
apply_stage_env_wrappers(stages: list[FlowStage], workflow: WorkflowDocument | None,
                         global_agent: str | None, flow_path: Path) -> list[FlowStage]
apply_gate_env_wrappers(stages: list[FlowStage], workflow: WorkflowDocument | None,
                        flow_path: Path) -> list[FlowStage]
```

`resolve_workflow` applies the three invocation modes — auto-match, explicit `--workflow`, `--no-workflow` — and runs the whole loading chain (peek the `profile:` default, resolve activation from `cli_profile`/`env_profile`/the default, resolve the profile against the project profiles dir and the decoded `home_profiles` bundle, render the file as a Jinja2 template with the profile content as context, parse the rendered text); it returns the `LoadedWorkflow` (document plus active profile) or `None`. `apply_skip_stages` removes skipped stages and reconnects their dependents. `order_stages` topologically orders the compiled stages for execution. `apply_stage_env_wrappers` generates one sh closure per env-declaring stage and patches those stages' `command` fields — or the `script` field on a script stage — in the already-written flow-file. `apply_gate_env_wrappers` is the gate-step counterpart: one sh closure per gate check step declaring `env`, patching its compiled `run` (a script step) or `command` (an agent step) field (both exported from the `goga.pipeline` facade).

## Execution

```python
run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int,
             workflow: str | None = None, no_workflow: bool = False,
             profile: str | None = None, skip: list[str] | None = None,
             parallel: int | None = None, fail_on_error: bool = False) -> int
pipeline_cli(argv: list[str]) -> int
```

`run_pipeline` is the in-container execution: load and amend the project configuration (the in-container `config/amend_config` delivery — see [Configuration — Hooks](../../configuration/hooks.md)), resolve the workflow decision from the explicit parameters (`no_workflow` > `workflow` > basename auto-match), merge the `skip` names onto it, deliver the `pipeline.amend_workflow` checkpoint over the merged workflow (see [Hooks](hooks.md)), compile the pipeline-file with the overlay the amendment returned, materialize the agent prompts, write the afm configuration file with the effective `pipeline.agent` and goga's always-on observer hook entry (the afm lifecycle-hooks registration — see [Hooks — The mid-run bridge](hooks.md#the-mid-run-bridge)) — the write also threads the compiled flow and the effective workflow, always emitting the collaboration section headed by `runtime_context: wrapper` and, when the workflow declares assistants, the `goga-<name>` collaboration profiles (env assistants behind owner-only closures) and the `delegation` task budget — materialize the goga dashboard skin into `~/.afm/skins/goga/` from the installed package, compose the afm launch env layer (the effective `pipeline.env` with the decoded CLI `-e` entries applied above it; the effective profile is additionally exported as `GOGA_PROFILE`), generate the per-stage env wrappers of env-declaring workflow stages and the gate-step env wrappers of env-declaring gate steps, emit the `run_created` notification, execute the pipeline, and emit `run_completed` with the actual exit code on every launch-attempt return path — the container exit code is returned. `parallel` caps the number of stages executed concurrently (`None` — unbounded). `fail_on_error` stops the run at the first failed stage and fails the launch (`False` — a failed stage does not fail the exit code; forwarded to the engine as its explicit `--exit-on-fail` argv flag). `pipeline_cli` is the in-container argparse entry point behind `goga pipeline` (the host-side launcher is the [Install/CLI layer](cli.md)).

## The lifecycle-event bridge

```python
run_hook() -> int
map_event_action(event: str) -> str | None
build_run_event(payload: dict[str, Any]) -> RunEvent
build_stage_event(payload: dict[str, Any]) -> StageEvent
```

`run_hook` is the process entry behind `python3 -m goga.pipeline hook` — the observer command afm launches once per lifecycle event (the always-on registration `run_pipeline` writes; see [Hooks — The mid-run bridge](hooks.md#the-mid-run-bridge)). The curated filter runs first — a non-curated event exits 0 before any platform import and without reading stdin; a curated event parses the JSON payload from stdin, composes the context, and emits it as one soft delivery — 0 on success, on ignored events, and on subscriber soft failures; 1 with `Error: ...` on stderr on a bridge-internal failure. `map_event_action` resolves one afm event name to its bridged pipeline action (`None` outside the curated fifteen); `build_run_event` / `build_stage_event` compose the `RunEvent` / `StageEvent` contexts of the hooks zone from the parsed payload.

## Example

```python
from pathlib import Path
from goga.pipeline import describe_pipeline, list_pipelines

project = Path(".goga/pipelines")
user = Path.home() / ".goga/pipelines"

for entry in list_pipelines(project, user):
    print(entry.name, entry.source)

card = describe_pipeline("development", project, user, None, False)
for stage in card.stages:
    print(stage.id, "—", stage.title)
```
