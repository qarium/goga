# run_flow — launch an afm flow inside the container

`run_flow` is the goga-side entry point to the external `afm` binary. It invokes
`afm run` with an absolute flow-file path and a dashboard port, optionally
capping concurrency and applying an environment layer for the subprocess, and
propagates the subprocess exit code. It performs no discovery, path resolution,
or port allocation — those live in other cells.

## Signature

run_flow(flow_path: Path, port: int, max_parallel: int | None = None, env: dict[str, str] | None = None) -> exit_code: int

## Parameters

- `flow_path` — absolute path to the compiled afm flow-file. Passed verbatim as
  the positional argument to `afm run`.
- `port` — TCP port forwarded to `afm run --port`. Allocated by the host-side
  launcher (goga/commands/pipeline).
- `max_parallel` — optional cap on the number of concurrently executing stages.
  When not None, forwarded as `afm run --max-parallel <max_parallel>`. When None
  (default), the `--max-parallel` flag is OMITTED and afm applies its own
  default. Decided by the caller; `run_flow` only forwards
  it.
- `env` — optional environment layer applied on top of the inherited process
  environment for the afm subprocess only. Composed by the caller (the
  in-container run coordination): the effective task env layer (`pipeline.env`)
  with the CLI `-e` entries applied above it. `None` and an empty mapping both
  mean "inherited environment unchanged". Secret-safe: never logged, never
  printed.

## Returns

The subprocess exit code: 0 success; 127 afm missing from PATH; 126 afm present
but not executable; otherwise afm's own exit code.

## Concurrency-limit contract

The `--max-parallel` flag is emitted **only** when `max_parallel` is not None.
Absence (None) propagates from the host CLI (no `-p/--parallel`) all the way to
`run_flow`, where it becomes the omission of `--max-parallel` — afm then runs
unbounded (its default). Never substitute a default value for None.

## Environment layer contract

The optional `env` layer is applied on top of the inherited process
environment for the afm subprocess only — never to the caller's own
environment. The caller (the in-container run coordination) composes the
layer: the effective task env layer (`pipeline.env`) with the CLI `-e` entries
applied above it, engine-variable keys dropped. `None` and an empty mapping
both mean "inherited environment unchanged". The layer values are
secret-safe: never logged, never printed, never included in any diagnostic
output.

## Error handling

`FileNotFoundError` ⇒ exit code 127 (afm missing from PATH); other `OSError` ⇒
126 (present but not executable); otherwise afm's own exit code is returned
unchanged.

## Anti-patterns

- Do not pass a flow name instead of an absolute path — afm treats the argument
  as a path.
- Do not default `max_parallel` to 0 or any value — None means "omit the flag".
- Do not compose the layer here — the caller owns the composition; `run_flow`
  only applies what it receives.
- Do not resolve paths or allocate ports here — those are the caller's jobs.
