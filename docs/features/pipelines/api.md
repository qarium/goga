# Pipelines — API

The facade of the domain package **`goga.pipeline`** — discovery and run coordination of goga pipeline files. The DSL parsing and flow compilation live in the nested cells `goga.pipeline.workflow` and `goga.pipeline.compiler`, and the hooks zone of the domain (the workflow amendment and the run notifications) in `goga.pipeline.hooks`; this facade carries the discovery, description, and run surfaces.

The signatures below are the CODEMANIFEST contract of the cell.

## Discovery and description

```python
list_pipelines(project_dir: Path, user_dir: Path) -> list[PipelineEntry]
describe_pipelines(project_dir: Path, user_dir: Path) -> list[PipelineSummary]
describe_pipeline(name: str, project_dir: Path, user_dir: Path,
                  workflow: str | None, no_workflow: bool,
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
                 no_workflow: bool) -> WorkflowDocument | None
apply_skip_stages(workflow: WorkflowDocument | None, skip_stages: list[str]) -> WorkflowDocument | None
order_stages(stages: list[FlowStage]) -> list[FlowStage]
```

`resolve_workflow` applies the three invocation modes — auto-match, explicit `--workflow`, `--no-workflow`. `apply_skip_stages` removes skipped stages and reconnects their dependents. `order_stages` topologically orders the compiled stages for execution.

## Execution

```python
run_pipeline(name: str, project_dir: Path, user_dir: Path, port: int,
             workflow: str | None = None, no_workflow: bool = False,
             skip: list[str] | None = None, parallel: int | None = None) -> int
pipeline_cli(argv: list[str]) -> int
```

`run_pipeline` is the in-container execution: resolve the workflow decision from the explicit parameters (`no_workflow` > `workflow` > basename auto-match), merge the `skip` names onto it, deliver the `pipeline.amend_workflow` checkpoint over the merged workflow (see [Hooks](hooks.md)), compile the pipeline-file with the overlay the amendment returned, materialize the agent prompts, emit the `run_created` notification, execute the pipeline, and emit `run_completed` with the actual exit code on every launch-attempt return path — the container exit code is returned. `parallel` caps the number of stages executed concurrently (`None` — unbounded). `pipeline_cli` is the in-container argparse entry point behind `goga pipeline` (the host-side launcher is the [Install/CLI layer](cli.md)).

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
