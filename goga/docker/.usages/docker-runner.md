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
- `DockerRunner(image).run(args, extra_args: list[str] | None = None, **params) -> int` — assemble and run
  `docker run <params-flags> <extra_args> <image> <args>`, manage the lifecycle, and return the
  container exit code. `extra_args` are raw docker tokens appended verbatim after
  the translated params flags and before the image (structural-only; docker
  surfaces conflicts). Defaults to `None` (normalized to `[]`).

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
    # → docker run --name <container_name> --rm --entrypoint python3 \
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

`extra_args` is a separate raw-token channel: unlike `params` (translated to
flags by the shared rule), `extra_args` are docker tokens appended **verbatim**
after the translated params flags and before the image. Use it for flags that do
not fit the param→flag rule (e.g. `--network`, `--gpus`, `--shm-size`). Only the
structural `list[str]` shape is checked; docker itself surfaces flag conflicts.
Ordering in the assembled argv:

    ["docker", "run", *flags, *extra_args, image, *args]

## Lifecycle

`run` installs a SIGTERM/SIGINT handler before launch and restores the previous
handler in its `finally`:

- SIGINT → exit code 130 (128 + SIGINT)
- SIGTERM → exit code 143 (128 + SIGTERM)
- On every exit path (normal, signal, exception): `docker kill <name>` runs
  (errors suppressed — the container may already be gone), then the previous
  signal handler is restored.

## Pre-launch version check

Before the work container starts, `run` applies the host–image version
consistency check:

1. When the check is disabled (the exact environment value
   `GOGA_SKIP_VERSION_CHECK=1`), skip both the probe and the comparison —
   behavior is identical to an unchecked launch.
2. Otherwise `run` reads the goga version inside the constructor image with
   a short-lived probe container (`docker_image_goga_version`) and hands
   the version string to `ensure_version_match`, which owns the outcome
   matrix: silent continue on (major, minor) agreement; stderr warning and
   continue on the `0.0.0` placeholder; process exit code 1 before the work
   container starts on a mismatch, a failed probe, or an undeterminable
   host version.

The check has no `run` parameter — the only escape is the environment
variable. The probe is minimal: no mounts, no env-file, no `extra_args`, no
`params`; it never receives the runner's flags or credential material. The
exit code of the work container remains the only return value; a check
refusal is an exceptional exit that happens before params translation,
handler installation, and the runner's try/finally — nothing was started
and no handler was replaced, so there is no runner teardown to perform;
the caller's cleanup blocks still run during the unwind.

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
- Runs one short-lived probe container per launch when the version check is
  enabled (captured output, nothing streamed).

## Failure modes

- Missing `name` param → `ValueError` raised before the version gate and the
  launch (fail-fast: a call without a kill target must not launch even the
  probe container).
- Non-zero container exit → returned as `exit_code`; the caller decides how to
  propagate (e.g. through a click context).
- SIGTERM/SIGINT → process exits with 128 + signum after the container is killed.
- `docker kill` failure in `finally` → suppressed (container already gone).
- Version check refusal → process exits with code 1 before the work container
  starts (message on stderr); the refusal precedes the runner's try/finally,
  so no runner teardown is due — the caller's cleanup blocks still run.

## Anti-patterns

- Do NOT resolve mounts / hosts / env-file / runtime-dir inside the runner — pass
  already-resolved values as `params`. The runner is a thin executor.
- Do NOT delete the env-file or tmpfile or remove `.ralphex/` from the runner —
  that is the caller's `finally` job.
- Do NOT omit `name` — the guaranteed `docker kill` needs a target, and a
  nameless container cannot be killed by name.
- Do NOT catch the runner's signal exit to "clean up" the container yourself — the
  runner already kills it in `finally`.
- Do NOT bypass or wrap the version check around `run` — the gate is part of the
  launch; its only escape is `GOGA_SKIP_VERSION_CHECK=1`.
