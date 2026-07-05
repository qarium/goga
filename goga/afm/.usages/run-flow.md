# Run Flow — goga/afm

## Overview

`run_flow` is a thin subprocess-wrapper over the external `afm` binary.
It launches `afm run` with a given absolute pipeline-file path and a
dashboard `port`, then propagates the subprocess exit code. `run_flow`
performs no discovery, path resolution, or port allocation — the caller
(typically `run_pipeline` in `goga/pipeline`) resolves the absolute path,
and `goga/commands/pipeline` allocates the port before calling.

## Usage

```python
from pathlib import Path
from goga.afm import run_flow

flow_path = Path("/workspace/.goga/pipelines/deploy.yml")  # absolute path
port = 50321  # allocated by the caller (goga/commands/pipeline)

exit_code = run_flow(flow_path, port)
```

## Parameters

- `flow_path: Path` — absolute path to the pipeline file to run. Passed to
  `afm run` as the positional argument.
- `port: int` — TCP port forwarded to `afm run --port`. Allocated by the
  caller; `run_flow` does not allocate ports.

## Return Values

| Exit code | Condition                                                        |
|-----------|------------------------------------------------------------------|
| 0         | afm ran the pipeline successfully                                |
| 126       | `afm` binary present but not executable                          |
| 127       | `afm` not in `$PATH` inside the container (clear message)        |
| non-zero  | afm itself returned a non-zero exit code                         |

## Side Effects

`run_flow` invokes `afm` as a subprocess and inherits all its side effects
(the pipeline may create files, run commands, expose a web UI on `port`,
etc., as defined by the pipeline file itself).

## Preconditions

- The `afm` binary must be on `$PATH` inside the container (invoked via
  subprocess; missing binary raises `FileNotFoundError`, mapped to exit
  code 127). `run_flow` must not hard-code `/srv/afm`.
- `flow_path` must be an absolute path resolved by the caller; `run_flow`
  does not validate or construct paths.
- `port` must be allocated by the caller (typically `goga/commands/pipeline`);
  `run_flow` only forwards it to `--port`.
- The host-side afm config (`~/.afm/config.yaml`) is generated and mounted
  by `goga/commands/pipeline`; `run_flow` does not touch it.

## Anti-patterns

- Do not pass a bare pipeline name — `run_flow` expects an absolute path. Use `goga/pipeline`'s `run_pipeline` for name resolution.
- Do not pass `port=0` or omit `--port` — `afm` needs a concrete port to bind its dashboard.
- Do not hard-code `/srv/afm` inside `run_flow` — invoke `afm` via `$PATH` so the container layout can change without breaking this cell.
- Do not expect `run_flow` to discover files in pipeline directories — discovery lives in `goga/pipeline`'s `list_pipelines`.
- Do not allocate the port inside `run_flow` — that responsibility belongs to `goga/commands/pipeline`.
- Do not modify or parse pipeline-file contents — that is outside this cell's responsibility.
