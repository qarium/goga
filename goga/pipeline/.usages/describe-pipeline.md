# describe_pipeline — pipeline card without running

`describe_pipeline` composes the card of a single pipeline: the authored name
and description from the DSL header, plus the stage list (id and title per
stage) in execution order — the composition a run of the same pipeline with
the same workflow flags would execute. Nothing is launched and nothing is
written into the project or runtime directories.

## Usage

```python
from pathlib import Path
from goga.pipeline import describe_pipeline

card = describe_pipeline(
    name="deploy",
    project_dir=Path("/workspace/.goga/pipelines"),
    user_dir=Path("/home/goga/.goga/pipelines"),
    workflow="hardening",   # explicit workflow; None → basename auto-match
    no_workflow=False,
)
print(card.name)
print(card.description)
for stage in card.stages:
    print(f"{stage.id}: {stage.title}")
```

## Parameters

- `name: str` — pipeline name without extension
- `project_dir: Path` — project pipelines directory (absolute)
- `user_dir: Path` — user pipelines directory (absolute)
- `workflow: str | None` — explicit workflow name without the `.yml`
  extension; `None` with `no_workflow=False` resolves the basename auto-match
  (`<name>.yml` in `.goga/workflows/`); a missing file is a silent miss
- `no_workflow: bool` — when True, no workflow is applied and the raw DSL
  composition is reported

Returns `PipelineCard`.

## The models

`PipelineCard` — `@dataclass(kw_only=True)`:

- `name: str` — pipeline name from the DSL header
- `description: str` — pipeline description from the DSL header
- `stages: list[CardStage]` — stage rows in execution order

`CardStage` — `@dataclass(kw_only=True)`:

- `id: str` — stage identifier
- `title: str` — stage display title

## Workflow equivalence

`workflow` / `no_workflow` follow one rule set shared with run coordination:
disabled → raw composition; explicit name → that workflow file; otherwise
basename auto-match; a missing file is a silent miss. The stage composition
is produced by the same compilation machine a run uses, so loop-expanded
copies appear as separate rows with their generated ids.

## Side effects

- Reads the pipeline-file and, when one resolves, the workflow-file.
- Writes one temporary flow-file in the system temporary directory (outside
  the project and runtime directories) and removes it before returning.

## Preconditions

- Both directories must be absolute.
- An unknown `name` raises a readable error naming the pipeline.
- A damaged pipeline-file or workflow-file raises a readable structural
  error.

## Anti-patterns

- Do not feed the run-only skip channel (`GOGA_SKIP_STAGES`, the host `-s`
  option) to the card — the card never reads it. Workflow-file
  `skip: true` directives DO apply through the shared compilation machine
  and are reflected in the stage list, exactly as a run with the same
  workflow flags would execute them.
- Do not treat the card as a launch — no afm invocation, no agents, no state
  changes.
