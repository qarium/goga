# run_pipeline — in-container run coordination

`run_pipeline` resolves a pipeline name to a file, resolves an optional workflow,
compiles the pipeline-file to an afm flow-file via `compile_flow`, materializes
the four agent prompt files, then launches afm via `run_flow`.

## Signature

run_pipeline(name, project_dir, user_dir, port, parallel=None) -> exit_code

## parallel

parallel (int | None) optionally caps concurrently executing stages. It is
forwarded to run_flow as its max_parallel argument (None ⇒ run_flow omits
--max-parallel ⇒ afm unbounded). Read from the in-container --parallel flag by
pipeline_cli; the host launcher forwards it through the docker run args.
Discovery mode does not run afm, so it is a no-op there.

The threading chain (host → container):

    goga pipeline NAME -p N   (Click -p/--parallel)
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → pipeline_cli: args.parallel = N
          → run_pipeline(…, parallel=N)
            → run_flow(…, max_parallel=N)
              → afm run --port PORT --max-parallel N <flow>

Absent flag ⇒ parallel=None ⇒ no --max-parallel ⇒ afm unbounded.
