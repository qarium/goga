# Image acquisition — goga/docker

## Domain

Building and pulling the Docker image the goga commands run in, and the
`--update` decision that picks between them. This practice covers the
image-acquisition entry points on the goga/docker facade:
`docker_update`, `docker_build_if_not_exist`, `DockerBuilder`, and `docker_pull`.

Target audience: host-side command launchers (`goga build`, `goga pipeline`)
that implement the `--update`/`-u` flag and need to refresh or first-build the
container image before launch.

## Public API

    from goga.docker import docker_update, docker_build_if_not_exist, DockerBuilder, docker_pull

- `docker_update(image: str, dockerfile: str | None, extra_args: list[str] | None = None) -> None` — the `--update`
  entry point. When `dockerfile` is set, build the image locally from that
  Dockerfile (fatal on failure); when `dockerfile` is None, pull `image` from the
  registry (warning on failure, non-fatal). `extra_args` are forwarded verbatim
  to the build branch only (appended before `-f`); the pull branch ignores them.
- `docker_build_if_not_exist(image: str, dockerfile: str | None, extra_args: list[str] | None = None) -> None` — the
  first-run safety net. When `image` is absent locally AND `dockerfile` is set,
  build it (fatal on failure, same semantics as the `docker_update` build branch);
  otherwise no-op. Never pulls — a registry image is left to `docker run` /
  `--update`. Runs UNCONDITIONALLY at launch entry, complementing `docker_update`
  (which is gated by `--update`). `extra_args` are forwarded to the build branch
  only; the no-op branches ignore them.
- `DockerBuilder(image, dockerfile='Dockerfile', context='.')` — stateful builder.
  `.build(extra_args: list[str] | None = None, **params)` runs docker build, tagging the
  result as `image` so the locally built image shadows the registry tag consumed
  by docker run. `extra_args` are appended verbatim after the translated params
  flags and before `-f`.
- `docker_pull(image: str) -> bool` — standalone registry pull. Returns False and
  logs a WARNING on failure (never raises).

## Raw extra tokens (extra_args channel)

`extra_args` is a separate channel from the `params` dict. `params` are
translated to docker flags by the shared param→flag rule (1-char → short flag,
snake_case → long flag, etc.). `extra_args` are raw docker tokens appended
**verbatim** — no translation, no validation beyond the structural `list[str]`
check. This lets a caller pass free-form docker CLI tokens (e.g. `--network`,
`--gpus`, `--shm-size`) without inventing a param key for each.

Ordering:

    docker build <params-flags> <extra_args> -f <dockerfile> -t <image> <context>

`docker_update` and `docker_build_if_not_exist` forward `extra_args` to
`DockerBuilder.build` in their **build branch only** — their pull branch
(`docker_update`) and no-op branches (`docker_build_if_not_exist`) ignore
`extra_args`, because extra tokens apply to image BUILD, not to a registry pull
or an absent build. The cell stays a leaf with respect to configuration: `extra_args`
is a primitive (`list[str]`), so adding it introduces no configuration Imports (the
cell's only Imports are the version-check routines).

## Typical usage

### The --update flag (force refresh — the common path)

A command launcher resolves the validated `config.image` and `config.dockerfile`
and forwards them as primitives. `docker_update` owns the build-vs-pull branch and
the error semantics, so all three call sites (build, pipeline discovery, pipeline
run) share one decision:

    from goga.docker import docker_update

    if update:
        docker_update(config.image, config.dockerfile)

Behavior, by `dockerfile`:

- `dockerfile` set → `docker build --pull -f <dockerfile> -t <image> .`. The
  `--pull` flag refreshes base images declared via `FROM` from the registry
  instead of the local cache, so an `--update` always reflects the current
  upstream base images. Build failure is fatal: it raises, the caller maps it
  to exit 1, and the container never launches.
- `dockerfile` None → `docker pull <image>`. Pull failure is recoverable: a WARNING
  is logged and the caller continues on the local image (the launch may still fail
  later if the image is genuinely absent, but that surfaces from docker run itself).

### First-run auto-build (the safety net — unconditional)

`docker_update` is gated by `--update` (force refresh). But when a project
declares a `dockerfile` and the local image has never been built, a bare
`docker run` would fail with "No such image" — even without `--update`. The
`docker_build_if_not_exist` routine closes that corner case: the launcher calls
it UNCONDITIONALLY before `docker_update`, and it builds only when the image is
absent AND `dockerfile` is declared:

    from goga.docker import docker_build_if_not_exist, docker_update

    # First-run safety net: builds only if the image is absent + a Dockerfile
    # is declared. No-op otherwise (image present, or no Dockerfile set). Never
    # pulls — that stays `docker_update`'s job under `--update`.
    docker_build_if_not_exist(config.image, config.dockerfile)

    if update:
        docker_update(config.image, config.dockerfile)

Behavior matrix of `docker_build_if_not_exist`:

| image state | `dockerfile` | action |
|-------------|--------------|--------|
| present locally | set OR None | no-op (do not refresh — that is `docker_update`'s job under `--update`) |
| absent | set | `docker build --pull -f <dockerfile> -t <image> .` (fatal on failure). The `--pull` flag refreshes base images declared via `FROM` so a first-run build always picks up the current upstream base images. |
| absent | None | no-op (NEVER pulls — a registry image is pulled by `docker run` itself or by `--update`) |

The safety net probes the local image store via a silent `docker image inspect`
and tolerates a missing docker binary (returns "absent" — the caller has already
verified docker availability via its own `_check_docker`).

### Direct build with extra CLI options

Callers that need custom build flags beyond `--pull` (extra hosts, build args,
platform, etc.) construct `DockerBuilder` themselves and pass the options as
`params`. `docker_update` and `docker_build_if_not_exist` already emit `--pull`
for every build; this escape hatch is for the other flags they do not cover:

    from goga.docker import DockerBuilder

    DockerBuilder(
        image=config.image,
        dockerfile=config.dockerfile,
        context=".",
    ).build(add_host="127.0.0.1:localhost", pull=True)
    # → docker build --add-host 127.0.0.1:localhost --pull \
    #     -f <dockerfile> -t <image> .

Raw tokens that do not fit the param→flag rule (unusual flags, `--build-arg`
repeats, experimental options) go through the `extra_args` channel instead —
they are appended verbatim before `-f`:

    from goga.docker import DockerBuilder

    DockerBuilder(
        image=config.image,
        dockerfile=config.dockerfile,
        context=".",
    ).build(extra_args=["--network=host", "--squash"], pull=True)
    # → docker build --pull --network=host --squash \
    #     -f <dockerfile> -t <image> .

### Direct pull

Callers that want to pull unconditionally (independent of `--update`) call the
routine directly and branch on the boolean:

    from goga.docker import docker_pull

    ok = docker_pull(config.image)
    if not ok:
        # network / auth / not-found — log and continue on the local image

## Param → flag mapping (build)

`DockerBuilder.build(**params)` maps `params` to docker-build CLI flags by a rule
shared with the runner:

- 1-character key → short flag
- multi-char snake_case key → long flag
- str value → `flag value`
- `True` → boolean flag
- `False` → flag omitted
- list value → flag repeated once per element

These params are raw docker options. They are orthogonal to goga's `--update`
flag, which only decides whether `docker_update` runs at all.

## Preconditions

- `image` MUST be non-None. Callers validate `config.image` before calling
  `docker_update` / constructing `DockerBuilder` / calling `docker_pull`. The
  `image: str` signature makes this an explicit precondition, not a runtime check
  inside the cell.
- The build context (`context`, default "." = project root) and the Dockerfile
  path (relative to the context) must point at real files; docker itself reports
  a missing Dockerfile.

## Side effects

- `docker build` writes the locally tagged image into the local image store,
  shadowing the registry tag of the same name.
- `docker pull` writes the registry image into the local image store.
- Both stream the docker CLI's own stdout/stderr to the host.

## Failure modes

- Build failure → fatal: the exception propagates so the caller exits non-zero.
  This is intentional — a half-built image must not silently launch.
- Pull failure → non-fatal: `docker_pull` returns False and logs a WARNING. The
  caller decides whether to continue (typical) or abort.

## Anti-patterns

- Do NOT catch the exception from `DockerBuilder.build` to "continue anyway" — a
  failed build means the image is wrong; continuing hides the failure.
- Do NOT call `docker_pull` and then raise on a False return — pull failure is
  recoverable by design; the local image may already be present.
- Do NOT pass a `ProjectConfig` object to `docker_update`. It takes primitives
  (`image`, `dockerfile`, `extra_args`) so the docker cell stays free of
  configuration Imports (the cell's only Imports are the version-check
  routines).
