# Run Pipeline — goga/pipeline

## Overview

`run_pipeline` resolves a pipeline name to an absolute file path across two
source directories, compiles the file from goga DSL into an afm flow-file at
runtime, then launches afm to run the compiled flow. Use this routine to
launch a pipeline by name. The `port` argument is forwarded to the afm
dashboard.

## Usage

```python
from pathlib import Path
from goga.pipeline import run_pipeline

project_dir = Path("/workspace/.goga/pipelines")
user_dir = Path("/home/goga/.goga/pipelines")
port = 50321

exit_code = run_pipeline("deploy", project_dir, user_dir, port)
```

## Parameters

- `name: str` — pipeline name without extension (the `.yml` suffix is added
  internally during path resolution).
- `project_dir: Path` — project pipelines directory (absolute; same meaning
  as in `list_pipelines`).
- `user_dir: Path` — user pipelines directory (absolute; same meaning as in
  `list_pipelines`).
- `port: int` — TCP port forwarded to the afm dashboard. Allocated by the
  caller; `run_pipeline` does not allocate ports.

## Return Values

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | afm ran the compiled pipeline successfully                     |
| non-zero  | pipeline not found in either source                            |
| non-zero  | structural DSL error — an exception with a readable message propagates out of `run_pipeline` (missing `---` separator, missing header fields, body neither list nor dict, empty body) |
| 127       | `afm` not in `$PATH` inside the container (propagated)         |
| non-zero  | afm itself returned a non-zero exit code (propagated)          |

## Side Effects

`run_pipeline` writes the compiled flow-file to the runtime directory (the
directory pointed to by AFM_DIR). It launches afm as a subprocess and
inherits all its side effects, as defined by the compiled flow-file itself.

A repeat call with the same pipeline name overwrites the previous
flow-file. The compiler is deterministic, so the content is identical.

## Preconditions

- `project_dir` and `user_dir` must already be absolute when passed in.
- `port` must be allocated by the caller and free at bind time.
- The pipeline name must exist in one of the two source directories (after
  project-priority resolution).
- AFM_DIR must be set in the container environment.
- The input pipeline file must be a goga DSL file: a header (`name`,
  `description`) followed by a `---` separator, then a body (YAML list for
  phases, YAML dict for stages). Already-afm-format files are not supported
  and will raise a structural error.

## Anti-patterns

- Do not pass a bare pipeline name to afm — `run_pipeline` resolves the
  path, compiles, and passes the absolute compiled flow-file path.
- Do not allocate a port inside `run_pipeline` — `port` is a required
  argument supplied by the caller.
- Do not pass `port=0` — afm needs a concrete port to bind its dashboard.
- Do not pass a relative `project_dir` or `user_dir`.
- Do not expect `run_pipeline` to handle an already-afm-format file as
  input — only goga DSL files are supported; everything else raises a
  structural error.
