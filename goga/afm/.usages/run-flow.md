# Run Flow — goga/afm

## Overview

`run_flow` is a thin subprocess-wrapper over the external `flowmanager` binary.
It launches `flowmanager` with a given absolute pipeline-file path and
propagates the subprocess exit code. `run_flow` performs no discovery or path
resolution — the caller (typically `run_pipeline` in `goga/pipeline`) resolves
the absolute path before calling.

## Usage

```python
from pathlib import Path
from goga.afm import run_flow

flow_path = Path("/Users/me/.goga/pipelines/deploy.yml")  # absolute path

exit_code = run_flow(flow_path)
```

## Parameters

- `flow_path: Path` — absolute path to the pipeline file to run. Passed to
  `flowmanager run` as the positional argument.

## Return Values

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | flowmanager ran the pipeline successfully                      |
| 126       | `flowmanager` binary cannot be invoked (e.g. present but not executable) |
| 127       | `flowmanager` binary not in PATH (clear message, no traceback) |
| non-zero  | flowmanager itself returned a non-zero exit code               |

## Side Effects

`run_flow` invokes `flowmanager` as a subprocess and inherits all its side
effects (the pipeline may create files, run commands, etc., as defined by the
pipeline file itself).

## Preconditions

- The `flowmanager` binary must be in `PATH` (invoked via subprocess; missing binary raises `FileNotFoundError`, mapped to exit code 127).
- `flow_path` must be an absolute path resolved by the caller; `run_flow` does not validate or construct paths.

## Anti-patterns

- Do not pass a bare pipeline name — `run_flow` expects an absolute path. Use `goga/pipeline`'s `run_pipeline` for name resolution.
- Do not expect `run_flow` to discover files in pipeline directories — discovery lives in `goga/pipeline`'s `list_pipelines`.
- Do not copy pipeline files into `.flowManager/flows/` just to run them — `run_flow` passes the absolute path directly.
- Do not parse or validate pipeline-file contents — that is outside this cell's responsibility.
