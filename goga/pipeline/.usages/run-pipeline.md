# run_pipeline — in-container run coordination

`run_pipeline` resolves a pipeline name to a file, resolves an optional workflow,
compiles the pipeline-file to an afm flow-file via `compile_flow`, materializes
the four agent prompt files, then launches afm via `run_flow`.

## Signature

run_pipeline(name, project_dir, user_dir, port, parallel=None) -> exit_code

## Workflow resolution

The workflow decision is environment-driven (set by the host launcher):
GOGA_WORKFLOW_DISABLED=1 disables the workflow; otherwise
GOGA_WORKFLOW_NAME=<wf-name> names an explicit workflow; when neither is set,
the basename auto-match is attempted (a workflow file named like the
pipeline). Resolution follows the shared rule set — the same rules the info
card applies — so a run and a card with the same flags always agree on which
workflow applies. A missing auto-match file is a silent miss.

## Skip

GOGA_SKIP_STAGES=<csv> carries the CLI --skip/-s names; applied in-memory
onto the resolved workflow before compilation. Unset/empty = no skip.
Unknown names surface as the compiler's structural error.

## parallel

parallel (int | None) optionally caps concurrently executing stages. It is
forwarded to run_flow as its max_parallel argument (None ⇒ run_flow omits
--max-parallel ⇒ afm unbounded). Read from the in-container --parallel flag
by pipeline_cli; the host launcher forwards it through the docker run args.
The list/info forms never reach this routine.

The threading chain (host → container):

    goga pipeline NAME -p N   (Click -p/--parallel)
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → pipeline_cli: args.parallel = N
          → run_pipeline(…, parallel=N)
            → run_flow(…, max_parallel=N)
              → afm run --port PORT --max-parallel N <flow>

Absent flag ⇒ parallel=None ⇒ no --max-parallel ⇒ afm unbounded.
