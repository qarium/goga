# Run Pipeline — goga/pipeline

## Overview

`run_pipeline` resolves a pipeline name to an absolute file path across the two
source directories, then launches `flowmanager` to run it via `run_flow` from
`goga/afm`. Use this to launch a pipeline by name.

## Usage

```python
from pathlib import Path
from goga.pipeline import run_pipeline

project_dir = Path.cwd() / ".goga" / "pipelines"
user_dir = Path.home() / ".goga" / "pipelines"

exit_code = run_pipeline("deploy", project_dir, user_dir)
```

## Parameters

- `name: str` — pipeline name without extension (the `.yml` suffix is added internally during path resolution)
- `project_dir: Path` — project pipelines directory (same meaning as in `list_pipelines`)
- `user_dir: Path` — user pipelines directory (same meaning as in `list_pipelines`)

## Return Values

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | flowmanager ran the pipeline successfully                      |
| non-zero  | pipeline not found in either source                            |
| 127       | `flowmanager` binary not in PATH (propagated from `run_flow`)  |
| non-zero  | flowmanager itself returned a non-zero exit code (propagated)  |

## Path Resolution

The pipeline file is resolved via `list_pipelines` semantics — the project
source wins on name conflicts. The absolute path is then passed to `run_flow`
(see the `run-flow` practice from `goga/afm`), which invokes `flowmanager run`
with the path as positional argument.

## Side Effects

`run_pipeline` invokes `flowmanager` (through `run_flow`) as a subprocess and
inherits its side effects (the pipeline may create files, run commands, etc.,
as defined by the pipeline file itself).

## Preconditions

- The `flowmanager` binary must be in `PATH` (invoked via `run_flow`; missing binary raises `FileNotFoundError`, mapped to exit code 127 by `run_flow`).
- The pipeline name must exist in one of the two source directories (after project-priority resolution).

## Anti-patterns

- Do not invoke `flowmanager` directly from this cell — go through `run_flow` from `goga/afm`.
- Do not pass a bare pipeline name to `flowmanager` — `run_pipeline` resolves the path and adds the extension.
- Do not copy pipeline files into `.flowManager/flows/` just to run them — `run_pipeline` resolves and passes the absolute path directly.
