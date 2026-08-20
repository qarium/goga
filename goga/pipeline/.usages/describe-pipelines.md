# describe_pipelines — pipeline overview with descriptions

`describe_pipelines` composes the informational overview of every discovered
pipeline: each pipeline paired with the description from its DSL header. Use
this when you need to show users what each available pipeline does — without
running anything. Inside the goga Docker image, the source directories resolve
to `/workspace/.goga/pipelines/` and `/home/goga/.goga/pipelines/`.

## Usage

```python
from pathlib import Path
from goga.pipeline import describe_pipelines

summaries = describe_pipelines(
    project_dir=Path("/workspace/.goga/pipelines"),
    user_dir=Path("/home/goga/.goga/pipelines"),
)
for s in summaries:
    marker = " (project)" if s.source.value == "project" else ""
    print(f"{s.name}{marker} — {s.description}")
```

## Parameters

- `project_dir: Path` — project pipelines directory (absolute; scanned flat)
- `user_dir: Path` — user pipelines directory (absolute; scanned flat)

Returns `list[PipelineSummary]` — one per discovered pipeline, in discovery
order (project source wins on name conflicts).

## The PipelineSummary model

`PipelineSummary` is a `@dataclass(kw_only=True)` with three fields:

- `name: str` — pipeline name without extension
- `source: PipelineSource` — `PipelineSource.PROJECT` or `PipelineSource.USER`
- `description: str` — description from the pipeline-file header

## Side effects

- Reads the filesystem only (every discovered pipeline-file is read and
  parsed). Writes nothing.

## Preconditions

- Both directories must be absolute.
- Every discovered pipeline-file must be readable and structurally valid: the
  first damaged file aborts the whole overview with a readable error — there
  are no partial lists, silent skips, or placeholder markers.

## Anti-patterns

- Do not compile pipeline files to build an overview — headers are enough;
  compilation belongs to the card and run paths.
- Do not sort or reorder the returned list when rendering — discovery order
  is part of the contract.
