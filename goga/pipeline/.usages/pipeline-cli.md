# Pipeline CLI — goga/pipeline

## Overview

`pipeline_cli` is the in-container CLI entrypoint for
`python -m goga.pipeline`. It is invoked by the host-side docker launcher
(`goga/commands/pipeline`) — never imported by Python from the host side.
The host launches it via `docker run ... python -m goga.pipeline {list|run} ...`.

The CLI exposes two subcommands: `list` (discovery) and `run NAME --port PORT`
(run). Both execute inside the goga Docker image with `/workspace` mounted
from the host project directory.

## Usage

`pipeline_cli` is the programmatic entrypoint used by `__main__.py`. End-users
invoke the CLI through the docker launcher (`goga pipeline [<name>]`), which in
turn runs `python -m goga.pipeline`.

### Discovery (host → container)

```bash
# Host side:
goga pipeline
# Inside the container (run by goga/commands/pipeline):
python -m goga.pipeline list
```

### Run (host → container)

```bash
# Host side:
goga pipeline deploy
# Inside the container (run by goga/commands/pipeline):
python -m goga.pipeline run deploy --port 50321
```

### Programmatic dispatch

```python
from goga.pipeline import pipeline_cli

# Discovery
exit_code = pipeline_cli(["list"])

# Run
exit_code = pipeline_cli(["run", "deploy", "--port", "50321"])
```

## Subcommands

### `list`

Prints available pipelines to stdout:

```
Available pipelines:
  deploy (project)
  rollback
```

Project-source entries are suffixed with ` (project)`; user-source entries have no suffix. The header is always printed, even on empty lists.

### `run NAME --port PORT`

- `NAME` (required positional) — pipeline name without extension.
- `--port PORT` (required integer option) — TCP port forwarded to `afm run --port`. Allocated by the host-side launcher; the CLI does not allocate ports.

Returns afm's exit code (propagated through `run_pipeline` → `run_flow`).

## Return Values

| Exit code | Condition                                          |
|-----------|----------------------------------------------------|
| 0         | discovery succeeded / afm ran the pipeline         |
| 2         | argparse error (missing NAME, missing/invalid --port) |
| 1         | host-side invocation refused by `ensure_in_docker` in `__main__.py` (no GOGA_DOCKER=1) |
| non-zero  | pipeline not found / afm failure (propagated)      |
| 127       | `afm` not in `$PATH` inside the container          |

## Preconditions

- The CLI must be invoked inside the goga Docker image — discovery and run are in-container only.
  The package __main__ module enforces this by calling `ensure_in_docker()` as the first statement
  of its __main__ guard block, before `pipeline_cli` is invoked: host-side invocations exit with a
  stderr message and code 1 before any pipeline work.
- `/workspace` must be mounted from the host project directory by the launcher.
- The host-side launcher (`goga/commands/pipeline`) must allocate `--port` and pass it through.

## Anti-patterns

- Do not import `pipeline_cli` from the host side — invoke it through docker only. The host→container boundary is docker runtime, not Python Imports.
- Do not omit `--port` in `run` mode — argparse will reject the invocation with exit code 2.
- Do not allocate a port inside the CLI — `--port` is required and supplied by the host-side launcher.
- Do not print extra output to stdout in `list` mode beyond the header and the entries — the host may parse the lines.
- Do not try to bypass the `ensure_in_docker` guard in `__main__.py` by catching `SystemExit` —
  the entrypoint is in-container-only by design.
