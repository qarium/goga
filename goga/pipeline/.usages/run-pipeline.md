# run_pipeline — in-container run coordination

`run_pipeline` resolves a pipeline name to a file, resolves an optional workflow from the
CLI-provided decision, merges the CLI skip names, delivers the workflow amendment through the
pipeline hooks zone, compiles the pipeline-file to an afm flow-file via `compile_flow`,
materializes the four agent prompt files, emits the run-creation facts, launches afm via
`run_flow`, and emits the run-completion facts on its return.

## Signature

run_pipeline(name, project_dir, user_dir, port, workflow=None, no_workflow=False, skip=None,
parallel=None) -> exit_code

- `name: str` — pipeline name without extension
- `project_dir: Path` / `user_dir: Path` — absolute project / user pipeline directories
- `port: int` — dashboard port, allocated by the host-side launcher
- `workflow: str | None` — explicit workflow name without the `.yml` extension; None falls back
  to the basename auto-match
- `no_workflow: bool` — when True, workflow application is disabled
- `skip: list[str] | None` — stage names to skip; None and empty both mean no skip
- `parallel: int | None` — cap on concurrently executing stages; None means unbounded

## Workflow resolution

The workflow decision arrives as explicit parameters — the in-container CLI parses the
`-w WORKFLOW` / `--no-workflow` flags of the run subcommand. `no_workflow=True` disables
application; `workflow` names an explicit workflow; neither triggers the basename auto-match
(a workflow file named like the pipeline). Resolution follows the shared rule set — the same
rules the info card applies — so a run and a card with the same flags always agree on which
workflow applies. A missing auto-match file is a silent miss.

## Skip

`skip` (the repeatable `-s NAME` names of the run subcommand; None and empty both mean no skip)
is applied in-memory onto the resolved workflow before compilation via `apply_skip_stages`.
Skip applies to a workflow-less pipeline too. Unknown names surface as the compiler's structural
error.

## Workflow amendment

After the skip merge and before compilation, the workflow amendment is delivered through the
pipeline hooks zone (`PipelineHooks.amend_workflow`); `compile_flow` receives the effective
workflow the delivery returns. An explicit workflow disable turns the layer off — the merged
(skip-bearing) workflow composes and no amendment delivers; a silent auto-match miss keeps the
layer active onto the empty base. With no tool packages installed the overlay is the passthrough
— every run composes exactly what was passed. The amendment is a hard action: the first failing
tool stops the command with a clean error, and its whole contribution is discarded.

## Run events

`run_created` fires immediately before the runner launch — after compilation and prompt
materialization. `run_completed` fires on every launch-attempt return — zero, non-zero, and
spawn failures (126/127) alike — with the work statuses recomputed at the completion moment and
the actual exit code. Both notifications are soft: a failing hook warns and the run's exit code
is unaffected. A missing pipeline and a structural composition error fire no events — the
return happens before the checkpoints.

## Environment

The only environment read is `AFM_DIR` — the in-container afm state directory. Run options (the
workflow decision, the skip names, the parallel cap) never travel through the environment; they
arrive as parameters from the CLI.

## Threading chains (host → container)

    goga pipeline NAME -p N
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → pipeline_cli: parallel = N
          → run_pipeline(…, parallel=N)
            → run_flow(…, max_parallel=N)
              → afm run --port PORT --max-parallel N <flow>

    goga pipeline NAME -w hardening -s build -s test
      → docker run … -m goga.pipeline run NAME --port PORT -w hardening -s build -s test
        → pipeline_cli: workflow="hardening", skip=["build", "test"]
          → run_pipeline(…, workflow="hardening", skip=["build", "test"])

Absent flag ⇒ None ⇒ auto-match / no skip / unbounded.
