# pipeline_cli — in-container CLI for python -m goga.pipeline

`pipeline_cli` parses argv via argparse and dispatches to the flat listing (`list_pipelines`),
the overview (`describe_pipelines`), the card (`describe_pipeline`), or run coordination
(`run_pipeline`). Invoked by the host-side docker launcher through the runpy entrypoint in
`__main__.py`.

## Subcommands

### list

`list [--info]`

- Without `--info`: prints the flat list — one bullet line per pipeline: `* <name>` (with the
  " (project)" suffix for project source entries); no header line.
- With `--info`/`-i`: prints the overview — one bullet block per pipeline: the marker line
  `* <name>` (with the " (project)" suffix for project source entries) followed by `name:` and
  `description:` field lines indented by four spaces; `name:` carries the authored header name,
  `description:` the header description.
- An empty discovery prints nothing (flat list and overview alike); exit code 0.

### run

`run NAME [--info] [-w WORKFLOW | --no-workflow] [-s NAME]... [--port PORT] [--parallel N]`

- NAME (positional, required) — pipeline name without extension.
- `--info`/`-i` (flag) — print the card instead of running: `name:` and `description:` field
  lines, a blank line, a `---` separator, a blank line, then one bullet block per stage in
  execution order — the marker line `* <id>:` and a `title:` field line indented by four
  spaces. When the card provenance is non-empty, one blank line and one `tools:` field line
  follow the stage blocks — the contributing tools comma-separated in provenance order; an
  empty provenance adds nothing (byte-identical card).
- `-w WORKFLOW` / `--no-workflow` — the workflow decision, available in BOTH modes: a run and a
  card resolve it through the same shared rule set. `--no-workflow` disables application;
  `-w WORKFLOW` names an explicit workflow; neither flag triggers the basename auto-match.
- `-s NAME` (repeatable) — stage names to skip, available in BOTH modes: a run applies them to
  the execution, a card reflects them in the composition. Forwarding-only — unknown names
  surface as the compiler's structural error during composition.
- `--port PORT` (int) — dashboard port, allocated by the host launcher. Required only when
  `--info` is absent; ignored in info mode.
- `--parallel N` (int, optional) — max concurrently executing stages; run mode only.

Dispatch: run without `--info` → `run_pipeline(NAME, project_dir, user_dir, PORT,
workflow=<WF or None>, no_workflow=<bool>, skip=<names or None>, parallel=<N or None>)`; run
with `--info` → `describe_pipeline(NAME, project_dir, user_dir, workflow=<WF or None>,
no_workflow=<bool>, skip=<names or None>)`.

## Exit codes

0 success; 2 argparse error (including a missing `--port` without `--info`); non-zero operation
failure, rendered as a clean stderr message without a traceback.
