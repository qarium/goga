# pipeline_cli — in-container CLI for python -m goga.pipeline

`pipeline_cli` parses argv via argparse and dispatches to the flat listing
(`list_pipelines`), the overview (`describe_pipelines`), the card
(`describe_pipeline`), or run coordination (`run_pipeline`). Invoked by the
host-side docker launcher through the runpy entrypoint in `__main__.py`.

## Subcommands

### list

`list [--info]`

- Without `--info`: prints the flat list — one bullet line per pipeline:
  `* <name>` (with the " (project)" suffix for project source entries); no
  header line.
- With `--info`/`-i`: prints the overview — one bullet block per pipeline:
  the marker line `* <name>` (with the " (project)" suffix for project source
  entries) followed by `name:` and `description:` field lines indented by
  four spaces; `name:` carries the authored header name, `description:` the
  header description.
- An empty discovery prints nothing (flat list and overview alike); exit
  code 0.

### run

`run NAME [--info] [-w WORKFLOW | --no-workflow] [--port PORT] [--parallel N]`

- NAME (positional, required) — pipeline name without extension.
- `--info`/`-i` (flag) — print the card instead of running: `name:` and
  `description:` field lines, a blank line, a `---` separator, a blank line,
  then one bullet block per stage in execution order — the marker line
  `* <id>:` and a `title:` field line indented by four spaces.
  `-w WORKFLOW` applies a
  workflow to the card composition; `--no-workflow` reports the raw DSL
  composition; neither flag resolves the basename auto-match. Both flags are
  card-mode only — a run (no `--info`) picks its workflow decision up from
  the `GOGA_WORKFLOW_*` env vars set by the host launcher.
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
