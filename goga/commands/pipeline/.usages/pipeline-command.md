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
  at `http://localhost:<port>`.

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
goga pipeline deploy -e ANTHROPIC_API_TOKEN=sk-xxx -e MODEL=claude-sonnet-4-6
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
4. Runs `docker run --rm -v <project_dir>:/workspace -w /workspace --entrypoint python3 <config.image> -m goga.pipeline list` (in-container entrypoint).
5. Propagates the container's exit code.

### Run mode

1. Loads `.goga/config.yml` via `load_config`.
2. Verifies docker availability; checks `config.image`.
3. Allocates a free localhost port (bind to `("", 0)`, read assigned port, close socket).
4. Resolves the agent wrapper path via `resolve_wrapper_path(config.pipeline.agent)`
   and writes a tmpfile containing
   `client.command: <resolved wrapper path>` (mode 0600).
5. Builds an env-file with `config.pipeline.env` + git identity + extra `KEY=VALUE` pairs supplied via `-e/--env` (mode 0600).
6. Installs SIGTERM/SIGINT handlers that `docker kill` the container.
7. Prints `Web UI: http://localhost:<port>` to stdout.
8. Runs `docker run --rm -p <port>:<port> -v <project_dir>:/workspace -w /workspace -v <afm_tmpfile>:/home/goga/.afm/config.yaml:ro --env-file <env_file> [--codex mount] --entrypoint python3 <config.image> -m goga.pipeline run <name> --port <port>` (in-container entrypoint).
9. In `finally`: deletes tmpfiles and `docker kill`s the container.

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
- Do not mount afm state under `/workspace` — afm state belongs in `/home/goga/.afm/` inside the container; `/workspace` is the project directory only.
- Do not write the afm config into the project directory — use a tmpfile + read-only mount instead.
- Do not write a bare agent name into `client.command` — always write the
  resolved absolute wrapper path.
