# Pipeline Command — goga/commands/pipeline

## Overview

`goga pipeline [<name>]` is a single command. Both modes launch the goga
Docker container — discovery and run are in-container only. The host never
reads pipeline files directly.

- **Without `name` (discovery mode):** launches the container to print the
  `Available pipelines:` header followed by the list of available pipelines
  discovered inside the container across `/workspace/.goga/pipelines/` and
  `/home/goga/.goga/pipelines/`. Read-only from the host's perspective.
- **With `name` (run mode):** launches the container to run the named pipeline
  via the external `afm` binary inside the container. A free localhost port is
  allocated and `-p <port>:<port>` is published so the dashboard is reachable
  at `http://localhost:<port>`. Run mode mounts a persistent afm state host
  directory read-write at `/home/goga/pipeline` inside the container and sets
  `AFM_DIR=/home/goga/pipeline` via the env-file, so afm state (flows,
  run-state) survives across runs of the same pipeline in the same project on
  the same branch. Use `--clean` to wipe this directory before launch.

The boundary between this cell and the in-container pipeline entrypoint is
**docker runtime**, not Python imports. The host-side launcher
(`run_pipeline_container`) assembles a docker command and invokes the
in-container entrypoint inside the goga Docker image.

## Usage — discovery mode (no argument)

```bash
goga pipeline
```

Example output (project pipelines are annotated with `(project)`):

```
Available pipelines:
  deploy (project)
  build
  test
```

The header is always printed, even when the list is empty.

## Usage — run mode (with name)

```bash
goga pipeline deploy
```

The command allocates a free localhost port, prints `Web UI: http://localhost:<port>`
to stdout, and launches afm inside the container with that port forwarded.

To pass extra environment variables into the container (e.g. an agent
authorization token), repeat `-e KEY=VALUE` (or `--env KEY=VALUE`) on the
host-side invocation. The strings are appended to the container env-file
verbatim, with no validation — the same semantics as `goga build -e`:

```bash
goga pipeline deploy -e ANTHROPIC_API_KEY=sk-xxx -e MODEL=claude-sonnet-4-6
```

Pull the latest image before launching (default skips the pull):

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

## Argument

- `name` (positional, optional) — pipeline name without extension. When absent
  → discovery mode. When provided → run mode.

## Options

- `-e` / `--env` `KEY=VALUE` (repeatable) — pass environment variables into the
  container through `--env-file`. Effective only in **run mode**: discovery
  mode never writes an env-file, so `-e` is accepted but ignored when no
  `name` is given. Later duplicates override earlier ones inside the container
  (Docker `--env-file` semantics); strings are forwarded as-is, with no
  validation, mirroring `goga build -e`.
- `--proxy URL` (str) — HTTP/HTTPS proxy URL; overrides `pipeline.proxy` in
  `.goga/config.yml`. When set, the launcher writes `HTTP_PROXY`,
  `HTTPS_PROXY`, and `NO_PROXY=localhost,127.0.0.1` into the container
  env-file. Effective only in **run mode** (discovery mode never writes an
  env-file).
- `--add-host HOST:IP` (repeatable) — add a `docker run --add-host HOST:IP`
  entry. Merges on top of `pipeline.hosts` from config; CLI wins on host-key
  conflict. Effective in both modes.
- `--clean` (flag) — wipe the persistent afm state host directory before
  launch. Run mode only; a no-op in discovery mode. The directory is recreated
  empty before the container starts; `client.command` is still supplied via
  the afm-config tmpfile overlay (independent of `AFM_DIR`).
- `--update` / `-u` (flag) — pull the image before launching the container.
  Default is no pull — the local image is used as-is. On pull failure a
  warning is logged and the run continues with the local image. Effective in
  both modes.

## Agent resolution

`.goga/config.yml` field `pipeline.agent` is the agent name as declared in
the goga image (`claude`, `codex`, `opencode`, or any other name matching
the `/home/goga/bin/<agent>-as-claude.sh` wrapper convention).

`run_pipeline_container` resolves this name through `resolve_wrapper_path`
and writes the resulting absolute path into the afm-config tmpfile as
`client.command`. afm then invokes the wrapper directly.

`resolve_wrapper_path(agent: str) -> str` is a pure string-building routine
— it concatenates the in-container wrappers directory (`/home/goga/bin/`),
the `agent` value verbatim, and the `-as-claude.sh` suffix. It performs no
validation and no filesystem access; absence of the wrapper file is
surfaced by afm at invocation time.

No agent-name validation is performed by the host launcher. If the wrapper
file is missing from the image, afm surfaces the error.

## What the host does

### Discovery mode

1. Loads `.goga/config.yml` via `load_config`.
2. Verifies docker availability.
3. Checks `config.image` is set (ClickException otherwise).
4. Assembles a docker run command including one `--add-host HOST:IP` flag per
   resolved hosts entry (CLI `--add-host` merged on top of `pipeline.hosts`
   from config; CLI wins on conflict).
5. When `--update` is set: pulls the image (warning on failure, non-fatal).
   Default is no pull.
6. Runs `docker run --rm [-v <host_dir>:/workspace -w /workspace] [--add-host HOST:IP ...] --entrypoint python3 <config.image> -m goga.pipeline list` (in-container entrypoint).
7. Propagates the container's exit code.

`extra_env`, `proxy`, and `--clean` have no effect in discovery mode — no
env-file is written, no afm state directory is involved.

### Run mode

1. Loads `.goga/config.yml` via `load_config`.
2. Verifies docker availability; checks `config.image`.
3. Allocates a free localhost port (bind to `("", 0)`, read assigned port, close socket).
4. Resolves the agent wrapper path via `resolve_wrapper_path(config.pipeline.agent)`
   and writes a tmpfile containing
   `client.command: <resolved wrapper path>` (mode 0600).
5. Resolves the persistent afm state host directory via
   `resolve_pipeline_runtime_dir(name)` (= `~/.goga/runtime/pipelines/<normalized_project>/<git-branch>/<name>/`)
   and ensures it exists (`mkdir -p`, idempotent).
6. When `--clean` is set: wipes the directory via `clean_pipeline_runtime_dir`
   (recursive rmtree + recreate) **before** launch.
7. Builds an env-file with `config.pipeline.env` + git identity + extra
   `KEY=VALUE` pairs supplied via `-e/--env` + `AFM_DIR=/home/goga/pipeline` +
   (when proxy is set) `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1`
   (mode 0600).
8. Installs SIGTERM/SIGINT handlers that `docker kill` the container.
9. Prints `Web UI: http://localhost:<port>` to stdout.
10. Assembles the docker run command:
    - `--rm -p <port>:<port>`
    - `-v <project_dir>:/workspace -w /workspace`
    - `-v <pipeline_runtime_dir>:/home/goga/pipeline` (read-write — persistent state)
    - `-v <afm_tmpfile>:/home/goga/.afm/config.yaml:ro` (read-only — `client.command` overlay; this path is independent of `AFM_DIR`)
    - one `--add-host HOST:IP` flag per resolved hosts entry
    - one `-v <host_path>:<container_path>:ro` flag per credential file detected by `resolve_credential_mounts()` (claude/codex/opencode when present on the host)
    - `--env-file <env_file>`
    - `--entrypoint python3 <config.image> -m goga.pipeline run <name> --port <port>`
11. When `--update` is set: pulls the image (warning on failure, non-fatal).
    Default is no pull.
12. Launches the container and waits for its exit code.
13. In `finally`: deletes the `client.command` tmpfile and the env-file,
    `docker kill`s the container. **The persistent afm state host directory
    is NOT deleted** — it survives across runs of the same pipeline.

## Container exit code mapping

| Exit code | Condition                                                                |
|-----------|--------------------------------------------------------------------------|
| 0         | Discovery succeeded / afm ran the pipeline successfully                  |
| 2         | argparse error inside the container (missing NAME, missing/invalid `--port`) |
| 127       | `afm` not in `$PATH` inside the container                                |
| 130       | Container received SIGINT (host SIGINT → `docker kill`)                  |
| non-zero  | Pipeline not found / afm failure (propagated from `run_pipeline`)        |

## Source Directory Resolution (in-container)

| Directory     | In-container path                |
|---------------|----------------------------------|
| `project_dir` | `/workspace/.goga/pipelines/`    |
| `user_dir`    | `/home/goga/.goga/pipelines/`     |

If the name exists in both sources, the project source wins (resolved inside the container by `list_pipelines`).

## Side Effects

- Discovery mode: launches the container; container reads the filesystem only.
- Run mode: allocates a localhost port, creates two tmpfiles (afm config, env-file), launches afm inside the container, prints `Web UI: http://localhost:<port>`. The host installs SIGTERM/SIGINT handlers for the lifetime of the run.
- Run mode: writes a persistent host directory at
  `~/.goga/runtime/pipelines/<normalized_project>/<git-branch>/<pipeline-name>/`
  (created with `mkdir -p`, mounted read-write at `/home/goga/pipeline`). This
  directory survives across runs and is NOT removed in the launcher's `finally`
  block. Use `--clean` to wipe it before launch.

## Preconditions

- Docker must be installed and available in PATH.
- `.goga/config.yml` must have the top-level `image` field set.
- (Run mode) `config.pipeline.agent` is resolved via `resolve_wrapper_path`
  and forwarded as afm `client.command` via the tmpfile mount.

## Anti-patterns

- Do NOT import or call `list_pipelines` or `run_pipeline` on the host — they run inside the container only. The host launches them via docker, never via Python imports.
- Do not expect `ls` or `run` subcommands — this is a single `goga pipeline` command.
- Do not expect auto-`--help` when no name is given — discovery mode runs the container and prints the list.
- Do not pass a file path or a name with `.yml` in run mode — pass the bare pipeline name only.
- Do not mount afm state under `/workspace` — afm state belongs in `/home/goga/.afm/` (config.yaml, mounted read-only via tmpfile) and `/home/goga/pipeline` (persistent state, mounted read-write) inside the container; `/workspace` is the project directory only.
- Do not write the afm config into the project directory — use a tmpfile + read-only mount instead.
- Do not write a bare agent name into `client.command` — always write the
  resolved absolute wrapper path.
- Do NOT delete the persistent afm state host directory in the launcher's
  `finally` block — only the `client.command` tmpfile and env-file are deleted.
  The persistent directory survives across runs; `--clean` wipes it BEFORE
  launch, never after.
- Do NOT call `docker pull` unconditionally — the default behavior is no pull.
  Use `--update`/`-u` to pull before launch.
- Do NOT derive the `client.command` tmpfile mount target from `AFM_DIR` —
  `config.yaml` is always read from `~/.afm/config.yaml` regardless of where
  `AFM_DIR` points. The persistent directory mounted at `/home/goga/pipeline`
  supplies the rest of afm state (flows, run-state).
- Do not filter credential mounts by the configured `pipeline.agent` — detection
  is agent-agnostic (see the `docker-auth-mounts` practice).
