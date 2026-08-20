# pipeline_cli — in-container CLI for python -m goga.pipeline

`pipeline_cli` parses argv via argparse and dispatches to the flat listing
(`list_pipelines`), the overview (`describe_pipelines`), the card
(`describe_pipeline`), or run coordination (`run_pipeline`). Invoked by the
host-side docker launcher through the runpy entrypoint in `__main__.py`.

## Subcommands

### list

`list [--info]`

- Without `--info`: prints the "Available pipelines:" header followed by one
  entry per line (project source entries suffixed with " (project)") — the
  flat list.
- With `--info`/`-i`: prints the overview — one line per pipeline: the name,
  the " (project)" suffix for project source entries, then " — " and the
  description.
- An empty discovery prints the header only (flat list) / nothing (overview);
  exit code 0.

### run

`run NAME [--info] [-w WORKFLOW | --no-workflow] [--port PORT] [--parallel N]`

- NAME (positional, required) — pipeline name without extension.
- `--info`/`-i` (flag) — print the card instead of running: one line with the
  name, one line with the description, then one line per stage as "id: title"
  in execution order. `-w WORKFLOW` applies a
  workflow to the composition; `--no-workflow` reports the raw DSL
  composition; neither flag resolves the basename auto-match.
- `--port PORT` (int) — dashboard port, allocated by the host launcher.
  Required only when `--info` is absent; ignored in info mode.
- `--parallel N` (int, optional) — max concurrently executing stages; run
  mode only.

Dispatch: run without `--info` → `run_pipeline(NAME, project_dir, user_dir,
PORT, parallel=<N or None>)`; run with `--info` → `describe_pipeline(NAME,
project_dir, user_dir, workflow=<WF or None>, no_workflow=<bool>)`.

## Exit codes

0 success; 2 argparse error (including a missing `--port` without `--info`);
non-zero operation failure, rendered as a clean stderr message without a
traceback.
