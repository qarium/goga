# pipeline_cli — in-container CLI for python -m goga.pipeline

`pipeline_cli` parses argv via argparse and dispatches to `list_pipelines`
(discovery) or `run_pipeline` (run). Invoked by the host-side docker launcher
through the runpy entrypoint in `__main__.py`.

## Subcommands

### list
No arguments. Prints "Available pipelines:" header followed by one entry per line.

### run
run NAME --port PORT [--parallel N]

- NAME (positional, required) — pipeline name without extension.
- --port PORT (int, required) — dashboard port, allocated by the host launcher.
- --parallel N (int, optional) — max concurrently executing stages.
  Forwarded through run_pipeline → run_flow → afm run --max-parallel N.
  Absent ⇒ no limit (afm runs unbounded). Run mode only.

Dispatch: run_pipeline(NAME, project_dir, user_dir, PORT, parallel=<N or None>).

## Exit codes

0 success; 2 argparse error; non-zero pipeline failure (propagated from
run_pipeline / list_pipelines).
