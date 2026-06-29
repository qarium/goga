# List Pipelines — goga/pipeline

## Overview

`list_pipelines` discovers pipeline files across two source directories and
returns them as `PipelineEntry`-s. Use this when you need to enumerate available
pipelines (for CLI output, validation, or selection UIs).

## Source Directories

| Parameter      | Typical path              | Meaning                                                  |
|----------------|---------------------------|----------------------------------------------------------|
| `project_dir`  | `<cwd>/.goga/pipelines/`  | Project-level pipelines, user-authored. Priority source. |
| `user_dir`     | `~/.goga/pipelines/`      | User-level pipelines, installed by `goga connect`.       |

When a pipeline name exists in both, the project source wins.

## Usage

```python
from pathlib import Path
from goga.pipeline import PipelineEntry, list_pipelines

project_dir = Path.cwd() / ".goga" / "pipelines"
user_dir = Path.home() / ".goga" / "pipelines"

entries: list[PipelineEntry] = list_pipelines(project_dir, user_dir)
for entry in entries:
    print(f"{entry.name} ({entry.source.value})")
```

## Parameters

- `project_dir: Path` — project pipelines directory (scanned flat, non-recursive)
- `user_dir: Path` — user pipelines directory (scanned flat, non-recursive)

Returns `list[PipelineEntry]` — one entry per unique name; duplicates resolved toward project source.

## The PipelineEntry model

```python
from goga.pipeline import PipelineEntry, PipelineSource

entry = PipelineEntry(name="deploy", source=PipelineSource.PROJECT)
entry.name    # "deploy"
entry.source  # PipelineSource.PROJECT (== "project", str-backed)
```

`PipelineEntry` is a `@dataclass(kw_only=True)` with two fields. The `name` is
validated in `__post_init__`: it must not contain path separators (`/`, `\`),
must not end with `.yml`, and must not be empty. Invalid names raise `ValueError`.

`PipelineSource` is a str-backed enum: `PipelineSource.PROJECT = "project"`,
`PipelineSource.USER = "user"`.

## Side Effects

- Reads the filesystem only (no writes).

## Preconditions

- Pipeline files must reside at the top level of a source directory (subdirectories are not scanned).
- Pipeline file names must use the `.yml` extension; the returned `PipelineEntry.name` omits it.
- Stems that fail `PipelineEntry` validation are silently skipped — they are not pipelines.

## Anti-patterns

- Do not scan subdirectories — only flat `*.yml` is supported.
- Do not assume pipelines from `.flowManager/flows/` will appear — that directory is `flowmanager`'s own and unrelated.
- Do not construct `PipelineEntry` with `name="deploy.yml"` or `name="a/b"` — the validator rejects these.
