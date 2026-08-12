# pipeline — host-side goga pipeline command

`goga pipeline` is a single Click command. Both discovery (no name) and run
(name) modes launch the goga Docker container and invoke
python -m goga.pipeline {list,run} inside it. The host never reads pipeline
files directly — the runtime boundary to goga/pipeline is docker.

## Usage

goga pipeline [NAME] [OPTIONS]

When NAME is omitted → discovery mode. When provided → run mode.

## Options (selection)

| Option | Type | Effect |
|--------|------|--------|
| -p / --parallel N | int (optional) | max concurrently executing stages; forwarded as the in-container --parallel, which threads to afm run --max-parallel N. Absent ⇒ afm unbounded. Run mode only (no-op in discovery). |
| -s / --skip NAME | repeatable | exclude a stage (run mode only) |
| -w / --workflow NAME | str | apply an explicit workflow |
| --no-workflow | flag | disable workflow resolution |
| -c / --clean | flag | wipe persistent afm state before launch (run mode only) |

## -p vs docker -p

The user-facing -p/--parallel is a Click option. The Docker port-publish
-p <port>:<port> is an internal translated docker token assembled by
run_pipeline_container/DockerRunner from the allocated port. They are in
different namespaces (Click CLI vs docker run argv) — no collision. The user
never authors the docker -p.

## Threading chain

    goga pipeline NAME -p N
      → docker run … -m goga.pipeline run NAME --port PORT --parallel N
        → pipeline_cli → run_pipeline(parallel=N) → run_flow(max_parallel=N)
          → afm run --port PORT --max-parallel N <flow>

Absent ⇒ parallel=None ⇒ no in-container --parallel ⇒ afm unbounded.
