# Run Pipeline — goga/pipeline

## Overview

`run_pipeline` resolves a pipeline name to an absolute file path across two
source directories, optionally resolves and parses a workflow-file per the
workflow environment contract, compiles the file (optionally extended by
the workflow) from goga DSL into an afm flow-file at runtime, materializes
the four agent prompt files (defaults plus inline overrides) into the
runtime prompts directory, then launches afm to run the compiled flow. Use
this routine to launch a pipeline by name. The `port` argument is forwarded
to the afm dashboard.

## Usage

### Without a workflow

```python
from pathlib import Path
from goga.pipeline import run_pipeline

project_dir = Path("/workspace/.goga/pipelines")
user_dir = Path("/home/goga/.goga/pipelines")
port = 50321

exit_code = run_pipeline("deploy", project_dir, user_dir, port)
```

### With a workflow (auto-match basename fallback)

When the host-side launcher does NOT pass any `--workflow` / `--no-workflow`
flag, `run_pipeline` checks for `/workspace/.goga/workflows/<name>.yml`
(where `<name>` matches the pipeline name). If present, it is applied
silently.

### With a workflow (explicit override via env)

When the host-side launcher passes `--workflow custom`, it sets
`GOGA_WORKFLOW_NAME=custom` in the container env-file. `run_pipeline`
resolves `/workspace/.goga/workflows/custom.yml` and applies it.

```python
# Inside the container, with GOGA_WORKFLOW_NAME=custom in the environment:
from pathlib import Path
from goga.pipeline import run_pipeline

# The host-side launcher already validated /workspace/.goga/workflows/custom.yml
# exists before launching the container; run_pipeline re-resolves the path
# in-container and parses it.
exit_code = run_pipeline("deploy", Path("/workspace/.goga/pipelines"),
                         Path("/home/goga/.goga/pipelines"), 50321)
```

### With workflow disabled

When the host-side launcher passes `--no-workflow`, it sets
`GOGA_WORKFLOW_DISABLED=1` in the container env-file. `run_pipeline` skips
workflow resolution entirely.

## Parameters

- `name: str` — pipeline name without extension (the `.yml` suffix is added
  internally during path resolution).
- `project_dir: Path` — project pipelines directory (absolute; same meaning
  as in `list_pipelines`).
- `user_dir: Path` — user pipelines directory (absolute; same meaning as in
  `list_pipelines`).
- `port: int` — TCP port forwarded to the afm dashboard. Allocated by the
  caller; `run_pipeline` does not allocate ports.

## Workflow environment contract

`run_pipeline` reads these environment variables in the following precedence:

1. `GOGA_WORKFLOW_DISABLED` — when set to `"1"`, workflow = None (forced
   disable). Takes precedence over `GOGA_WORKFLOW_NAME` even when both are
   set.
2. `GOGA_WORKFLOW_NAME` — when set (and `GOGA_WORKFLOW_DISABLED != "1"`),
   the workflow-file path resolves to
   `Path.cwd() / ".goga" / "workflows" / "{GOGA_WORKFLOW_NAME}.yml"`
   (= `/workspace/.goga/workflows/<wf-name>.yml` inside the container). The
   path is CWD-based, NOT `project_dir.parent`-based: `project_dir` itself
   is `/workspace/.goga/pipelines`, so `project_dir.parent` is
   `/workspace/.goga` and a parent-based composition would produce a double
   `.goga`. Workflows are project-only by design. The host-side launcher
   validates file existence BEFORE launching the container when this env var
   is set via the `--workflow` flag; if the file is missing inside the
   container, `run_pipeline` treats it as a silent miss (workflow = None) —
   this is a defensive fallback, not an error.
3. Otherwise (neither env var set) — the workflow-file path resolves to
   `Path.cwd() / ".goga" / "workflows" / "<name>.yml"` (basename fallback —
   same name as the pipeline; `Path.cwd()` = `/workspace` in-container).
   When that file does not exist, workflow = None (silent miss, NOT an
   error — workflow is opt-in).

When a resolved workflow-file exists, `run_pipeline` calls `parse_workflow`
to obtain a `WorkflowDocument`, which is forwarded to `compile_flow` as the
optional `workflow` argument. Structural errors from `parse_workflow`
propagate unchanged with their readable messages.

## Return Values

| Exit code | Condition                                                      |
|-----------|----------------------------------------------------------------|
| 0         | afm ran the compiled pipeline successfully                     |
| non-zero  | pipeline not found in either source                            |
| non-zero  | structural DSL error — an exception with a readable message propagates out of `run_pipeline` (missing `---` separator, missing header fields, unknown agent in header.agents, non-str agent value, body neither list nor dict, empty body) |
| non-zero  | structural workflow error — an exception with a readable message propagates out of `run_pipeline` when a resolved workflow-file fails `parse_workflow` (unknown keys, non-str/non-int values, `loop < 1`) |
| non-zero  | materialization error — a default prompt file is missing from the installed package AND no inline override is supplied for that key (readable message, no partial prompts/ directory) |
| 127       | `afm` not in `$PATH` inside the container (propagated)         |
| non-zero  | afm itself returned a non-zero exit code (propagated)          |

## Side Effects

`run_pipeline` writes the compiled flow-file to the runtime directory (the
directory pointed to by AFM_DIR). When a workflow is applied, the
flow-file reflects the workflow-applied extensions: top-level `prompt:`
directive (when present), per-stage `command:` and `description:` fields,
loop-expanded stages with rewritten depends_on. It materializes exactly
four agent prompt files into `<AFM_DIR>/prompts/` — one per fixed agent
key. For each key, the file is either a copy of the corresponding default
prompt from the installed goga package
(`goga/assets/afm/prompts/<key>.md`) or, when an inline override is
present in the pipeline-file header's `agents:` block, the inline prompt
text (full file replacement, no merge). Finally, `run_pipeline` launches afm
as a subprocess and inherits all its side effects, as defined by the
compiled flow-file itself.

A repeat call with the same pipeline name overwrites both the compiled
flow-file and the four prompt files. Both the compiler and the prompt
materialization are deterministic, so the content is identical across
runs.

## Preconditions

- `project_dir` and `user_dir` must already be absolute when passed in.
- `port` must be allocated by the caller and free at bind time.
- The pipeline name must exist in one of the two source directories (after
  project-priority resolution).
- AFM_DIR must be set in the container environment.
- The input pipeline file must be a goga DSL file: a header (`name`,
  `description`, optional `agents` block) followed by a `---` separator,
  then a body (YAML list for phases, YAML dict for stages). Already-afm-format
  files are not supported and will raise a structural error.
- The installed goga package must contain `goga/assets/afm/prompts/` with the
  four default files (`planning.md`, `implementation.md`, `review.md`,
  `summary.md`). A missing default for a key without an inline override is a
  fatal materialization error before `run_flow` is invoked.
- When `GOGA_WORKFLOW_NAME` is set, the resolved workflow-file
  (`/workspace/.goga/workflows/<name>.yml`) is expected to exist — the
  host-side launcher validates this before launch. A missing file is a
  silent miss inside the container (defensive fallback, not an error).

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
- Do not re-invoke `parse_dsl` to read inline prompt overrides — read them
  from the `PipelineDocument` returned by `compile_flow`.
- Do not expect partial prompt materialization on failure — when a default
  is missing and no override is supplied for a key, `run_pipeline` raises
  before any prompt file is written for that or subsequent keys.
- Do not expect inline prompt overrides to be merged or concatenated with
  the default prompt — overrides are full file replacements.
- Do not parse the workflow-file on the host — workflow resolution happens
  inside the container only; the host-side launcher performs explicit
  `--workflow` existence validation before launch.
- Do not expect a missing workflow-file (basename fallback miss) to be an
  error — it is opt-in; `run_pipeline` silently sets `workflow = None`.
- Do not expect `GOGA_WORKFLOW_NAME` and `GOGA_WORKFLOW_DISABLED=1` to both
  apply — `GOGA_WORKFLOW_DISABLED=1` always wins.
- Do not mutate the `WorkflowDocument` returned by `parse_workflow` —
  forward it as-is to `compile_flow`.
