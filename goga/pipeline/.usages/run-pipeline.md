# Run Pipeline — goga/pipeline

## Overview

`run_pipeline` resolves a pipeline name to an absolute file path across the two
source directories, then launches `afm` to run it via `run_flow` from
`goga/afm`. Use this to launch a pipeline by name. The `port` argument is
forwarded to `afm run --port` inside the container.

## Usage

```python
from pathlib import Path
from goga.pipeline import run_pipeline

project_dir = Path("/workspace/.goga/pipelines")
user_dir = Path("/home/goga/.goga/pipelines")
port = 50321  # allocated by the host-side launcher

exit_code = run_pipeline("deploy", project_dir, user_dir, port)
```

## Parameters

- `name: str` — pipeline name without extension (the `.yml` suffix is added internally during path resolution)
- `project_dir: Path` — project pipelines directory (same meaning as in `list_pipelines`)
- `user_dir: Path` — user pipelines directory (same meaning as in `list_pipelines`)
- `port: int` — TCP port forwarded to `afm run --port` via `run_flow`.
  Allocated by the host-side launcher (`goga/commands/pipeline`); `run_pipeline`
  does not allocate ports.

## Return Values

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | afm ran the pipeline successfully                              |
| non-zero  | pipeline not found in either source                            |
| 127       | `afm` not in `$PATH` inside the container (propagated from `run_flow`) |
| non-zero  | afm itself returned a non-zero exit code (propagated)          |

## Path Resolution

The pipeline file is resolved via `list_pipelines` semantics — the project
source wins on name conflicts. The absolute path is then passed to `run_flow`
from `goga/afm`, which invokes `afm run` with the path as positional argument
and `--port <port>` for the dashboard.

## Side Effects

`run_pipeline` invokes `afm` (through `run_flow`) as a subprocess and inherits
its side effects (the pipeline may create files, run commands, expose a web UI
on `port`, etc., as defined by the pipeline file itself).

## Preconditions

- The `afm` binary must be in `$PATH` inside the container (invoked via `run_flow`; missing binary raises `FileNotFoundError`, mapped to exit code 127).
- `port` must be allocated by the caller and free at bind time (the host-side launcher ensures this).
- The pipeline name must exist in one of the two source directories (after project-priority resolution).
- The host-side afm config (`~/.afm/config.yaml`) is generated and mounted by `goga/commands/pipeline`.

## Anti-patterns

- Do not invoke `afm` directly from this cell — go through `run_flow` from `goga/afm`.
- Do not pass a bare pipeline name to `afm` — `run_pipeline` resolves the path and adds the extension.
- Do not allocate a port inside `run_pipeline` — `port` is a required argument supplied by the caller.
- Do not pass `port=0` or omit `--port` — `afm` needs a concrete port to bind its dashboard.
- Do not copy pipeline files into `.flowManager/flows/` just to run them — `run_pipeline` resolves and passes the absolute path directly.
- Do not call `run_pipeline` from the host — it runs inside the container via `python -m goga.pipeline run`.
