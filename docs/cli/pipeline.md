# goga pipeline

Run a goga pipeline by name, or list available pipelines when no name is given.

`goga pipeline` is a host-side launcher: it assembles a `docker run` invocation and delegates all in-container work to `python -m goga.pipeline`. The `afm` binary runs inside the container — it is not required on the host.

## Synopsis

```bash
goga pipeline           # discovery mode: list available pipelines (in-container)
goga pipeline <name>    # run mode: run a pipeline by name (in-container)
```

## Description

The `pipeline` command is a single Click command (not a group). Its behavior depends on whether a name is given:

- **Without `name` (discovery mode):** launches the goga Docker image running `python -m goga.pipeline list`, which prints the `Available pipelines:` header followed by one pipeline per line. Project pipelines are annotated with `(project)`; user pipelines are printed bare.
- **With `name` (run mode):** allocates a free localhost port, writes a private afm-config tmpfile (`client.command: <resolved wrapper path>` — the absolute `resolve_wrapper_path(config.pipeline.agent)` value, never a bare agent name) mounted read-only at the fixed path `/home/goga/.afm/config.yaml`, ensures a persistent afm state host directory exists (wiping it first when `--clean` is set) and mounts it read-write at `/home/goga/pipeline`, writes a private env-file combining `config.pipeline.env` with git identity, `extra_env`, `AFM_DIR=/home/goga/pipeline`, and — when a proxy is set — the proxy env vars, prints the Web UI URL, and launches the goga Docker image running `python -m goga.pipeline run <name> --port <port>`. Credential files for claude/codex/opencode are detected on the host and bind-mounted read-only into the container automatically. Inside the container `goga.pipeline` resolves the pipeline to its absolute path and invokes `afm run --port <port> <path>`. The container's exit code is propagated via `ctx.exit`.

Pipelines are flat `*.yml` files (one per pipeline) resolved from two directories, with the project source winning on name conflicts:

| Source   | Directory                | Origin                                                     |
|---------|--------------------------|------------------------------------------------------------|
| project | `<cwd>/.goga/pipelines/` | Checked into / authored for the current project            |
| user    | `~/.goga/pipelines/`     | Installed centrally by `goga connect` (see [connect](connect.md)) |

Only top-level `*.yml` is scanned — subdirectories are ignored, and `.yaml` files are excluded. Pipeline path resolution and discovery happen **inside** the container (the host does not resolve pipeline paths).

## Prerequisites

Both modes launch a Docker container via the host **`docker`** CLI:

```bash
docker info
```

The top-level `image` field in `.goga/config.yml` must be set (the command exits with an error mentioning `image` when it is unset). The `afm` binary is provided by the container image and is invoked via `PATH` inside the container — it is not required on the host.

## Discovery Mode (`goga pipeline`)

List available pipeline names by running `-m goga.pipeline list` in the container. The `Available pipelines:` header is always printed, even when the list is empty.

```bash
goga pipeline
```

Example output:

```
Available pipelines:
  deploy (project)
  build
  test
```

Project pipelines are annotated with `(project)`; user pipelines are printed bare.

## Run Mode (`goga pipeline <name>`)

Run a pipeline by name. Pass the bare name only (no `.yml` extension); the container resolves the absolute path internally and forwards it to `afm run`. A free port is allocated automatically and published on both sides (`-p <port>:<port>`); `afm` listens on that port inside the container. The Web UI URL is printed to stdout.

```bash
goga pipeline deploy
```

```
Web UI: http://localhost:<port>
```

If the name exists in both sources, the project source wins. The container exit code is propagated as the command's exit code.

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `name` (positional) | string | — | Pipeline name without extension. When omitted, runs discovery mode |
| `-e`, `--env` | string (repeatable) | — | Additional environment variable (`KEY=VALUE`) forwarded into the container env-file. Run mode only (ignored in discovery) |
| `--proxy` | string | config | HTTP/HTTPS proxy URL; overrides `pipeline.proxy`. Adds `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` to the container env-file. Run mode only |
| `--add-host` | string (repeatable) | -- | Add a `docker run --add-host HOST:IP` entry; merges on top of `pipeline.hosts` (CLI wins on key conflict). Effective in both modes |
| `--clean` | flag | off | Wipe the persistent afm state directory before launch. Run mode only (no-op in discovery) |
| `--update`, `-u` | flag | off | Pull the image before launching the container (default skips the pull). Effective in both modes |

### Persistent afm state

Run mode mounts a host directory at `/home/goga/pipeline` inside the container and sets `AFM_DIR=/home/goga/pipeline` in the env-file, so afm state (flows, run-state) survives across runs of the same pipeline in the same project on the same branch. The host directory is computed as:

```
~/.goga/runtime/pipelines/<normalized-project-path>/<git-branch>/<name>/
```

It is created before launch and is **not** deleted on exit. Use `--clean` to wipe it before launch when you want a fresh run.

### Proxy and hosts

`--proxy URL` (and `pipeline.proxy` in `.goga/config.yml`) route the container's traffic through a corporate proxy. When a proxy is resolved, three variables are written to the container env-file: `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY=localhost,127.0.0.1` (fixed; cannot be overridden). `--add-host HOST:IP` (and `pipeline.hosts` in `.goga/config.yml`) translate to `docker run --add-host HOST:IP` flags; CLI entries merge on top of config with the CLI winning on key conflict.

### Credential mounts

Credential files for claude (`~/.claude/.credentials.json`), codex (`~/.codex/auth.json`), and opencode (`~/.local/share/opencode/auth.json`) are detected on the host and bind-mounted read-only into the container automatically (no flag). Detection is agent-agnostic; only files that exist are mounted.

### Examples

Pull the latest image, then run (default skips the pull):

```bash
goga pipeline deploy --update
```

Route container traffic through a corporate proxy and add a local host entry:

```bash
goga pipeline deploy --proxy http://corp:3128 --add-host foo.local:127.0.0.1
```

Wipe persistent afm state for this pipeline/branch before launch:

```bash
goga pipeline deploy --clean
```

## Exit Codes (run mode)

| Code | Meaning                                                                  |
|------|--------------------------------------------------------------------------|
| `0`  | The pipeline ran successfully                                            |
| `1`  | The named pipeline was not found in either source directory              |
| `126`| `afm` was present but could not be invoked (e.g. not executable)         |
| `127`| The `afm` binary is missing inside the container                         |
| `130`| Interrupted by SIGINT (`128 + 2`)                                        |
| `143`| Interrupted by SIGTERM (`128 + 15`)                                      |
| other| The container / `afm` exit code, propagated unchanged                    |

On SIGTERM/SIGINT during run mode the running container is killed and the process exits with `128 + signum`.

## Exit Codes (discovery mode)

| Code | Meaning                                   |
|------|-------------------------------------------|
| `0`  | Always (even when the pipeline list is empty) |

## Notes

- Do not expect `ls` or `run` subcommands — `goga pipeline` is a single command.
- Do not expect auto-`--help` when no name is given — discovery mode prints the `Available pipelines:` header + list instead.
- Do not pass a file path or a name ending in `.yml` in run mode — pass the bare pipeline name only.
- The host does not import any code from `goga/pipeline`; the runtime boundary to `goga/pipeline` is Docker.
