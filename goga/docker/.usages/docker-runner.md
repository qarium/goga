# Container launching — goga/docker

## Domain

Launching and managing the lifecycle of the goga Docker container — assembling
the docker run command, streaming its output, and guaranteeing teardown. This
practice covers the `DockerRunner` entry point on the goga/docker facade.

Target audience: host-side command launchers (`goga build`, `goga pipeline`) that
build a docker run command from resolved inputs (image, mounts, hosts, env-file,
entrypoint, command args) and must ensure the container is killed under every exit
path.

## Public API

    from goga.docker import DockerRunner

- `DockerRunner(image)` — stateful runner. The image to run is concrete, so it is
  supplied to the constructor.
- `DockerRunner(image).run(args, **params) -> int` — assemble and run
  `docker run <params-flags> <image> <args>`, manage the lifecycle, and return the
  container exit code.

## Typical usage

### Launch a container and wait for its exit code

The caller resolves every per-command input (mounts, hosts, env-file path,
entrypoint, container name, the post-image command) and passes them as `args` and
`params`. The runner is a thin executor — it assembles the command and owns the
lifecycle, nothing more:

    from goga.docker import DockerRunner

    exit_code = DockerRunner(config.image).run(
        args=["-m", "goga.build", plan],
        name=container_name,      # REQUIRED — see below
        rm=True,
        entrypoint="python3",
        v=["./project:/workspace", f"{runtime_dir}:/workspace/.ralphex"],
        add_host="127.0.0.1:localhost",
        env_file=env_file_path,
    )
    # → docker run --rm --name <container_name> --entrypoint python3 \
    #     -v ./project:/workspace -v <runtime_dir>:/workspace/.ralphex \
    #     --add-host 127.0.0.1:localhost --env-file <env_file_path> \
    #     <image> -m goga.build <plan>

The return value is the container exit code; propagate it to the caller.

### The name param is required and special

`name` is the one param that is REQUIRED by `run` and has a dual role:

1. It is emitted as the `--name <name>` flag (the uniform param→flag rule).
2. It is captured as the target for the guaranteed `docker kill <name>` in the
   runner's `finally`.

Because the runner kills by name, every caller MUST pass a unique `name`.

## Param → flag mapping (run)

`run(args, **params)` maps `params` to docker-run CLI flags by a rule shared with
the builder:

- 1-character key → short flag (e.g. `v`, `p`)
- multi-char snake_case key → long flag (e.g. `add_host` → --add-host,
  `env_file` → --env-file)
- str value → `flag value`
- `True` → boolean flag (e.g. `rm=True` → --rm)
- `False` → flag omitted
- list value → flag repeated once per element (multiple mounts / hosts)

`args` is the positional command after the image — typically the module invocation
(`-m goga.build ...`, `-m goga.pipeline ...`) plus its flags. It is positional
because a docker run needs a command, which cannot be a flag.

## Lifecycle

`run` installs a SIGTERM/SIGINT handler before launch and restores the previous
handler in its `finally`:

- SIGINT → exit code 130 (128 + SIGINT)
- SIGTERM → exit code 143 (128 + SIGTERM)
- On every exit path (normal, signal, exception): `docker kill <name>` runs
  (errors suppressed — the container may already be gone), then the previous
  signal handler is restored.

## Host-side cleanup belongs to the caller

The runner does NOT delete the env-file, does NOT delete tmpfiles, and does NOT
remove `.ralphex/` from the project directory. Those are host-side concerns that
are not docker flags, so they cannot be `params`. The caller performs them in its
own `finally`:

    try:
        exit_code = DockerRunner(config.image).run(args=args, **params)
    finally:
        # caller finally — runs AFTER the runner finally (docker kill + handler restore)
        env_file.unlink(missing_ok=True)
        _cleanup_ralphex_in_project(project_dir)

Run order is preserved: the runner's `finally` (docker kill + handler restore)
runs before the caller's `finally` (file / directory cleanup).

## Preconditions

- `image` MUST be non-None. Callers validate `config.image` before constructing
  `DockerRunner`.
- `name` MUST be present in `params` (the runner kills by name).
- Every mount, host, and the env-file path passed as `params` must already be
  resolved by the caller — the runner does no resolution.

## Side effects

- Launches a docker container and streams its stdout/stderr to the host.
- Installs a process-level SIGTERM/SIGINT handler for the duration of `run`
  (restored in `finally`).
- Runs `docker kill <name>` in `finally`.

## Failure modes

- Non-zero container exit → returned as `exit_code`; the caller decides how to
  propagate (e.g. through a click context).
- SIGTERM/SIGINT → process exits with 128 + signum after the container is killed.
- `docker kill` failure in `finally` → suppressed (container already gone).

## Anti-patterns

- Do NOT resolve mounts / hosts / env-file / runtime-dir inside the runner — pass
  already-resolved values as `params`. The runner is a thin executor.
- Do NOT delete the env-file or tmpfile or remove `.ralphex/` from the runner —
  that is the caller's `finally` job.
- Do NOT omit `name` — the guaranteed `docker kill` needs a target, and a
  nameless container cannot be killed by name.
- Do NOT catch the runner's signal exit to "clean up" the container yourself — the
  runner already kills it in `finally`.
