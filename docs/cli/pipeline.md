# goga pipeline

Run a goga pipeline by name, or list available pipelines when no name is given.

`goga pipeline` is a host-side launcher: it assembles a `docker run` invocation and delegates all in-container work to the goga in-container process. The `afm` binary runs inside the container — it is not required on the host.

## Synopsis

```bash
goga pipeline           # discovery mode: list available pipelines (in-container)
goga pipeline <name>    # run mode: run a pipeline by name (in-container)
```

## Description

The `pipeline` command is a single Click command (not a group). Its behavior depends on whether a name is given:

- **Without `name` (discovery mode):** launches the goga Docker image, which prints the `Available pipelines:` header followed by one pipeline per line. Project pipelines are annotated with `(project)`; user pipelines are printed bare.
- **With `name` (run mode):** allocates a free localhost port, writes a private afm-config tmpfile (`client.command: <resolved wrapper path>` — the absolute `resolve_wrapper_path(config.pipeline.agent)` value, never a bare agent name) mounted read-only at the fixed path `/home/goga/.afm/config.yaml`, ensures a persistent afm state host directory exists (wiping it first when `--clean` is set) and mounts it read-write at `/home/goga/pipeline`, writes a private env-file combining the machine-wide `home.env` (lowest-priority base layer, see [Home configuration](../configuration/index.md#home-configuration)) with `config.pipeline.env`, git identity, `extra_env`, `AFM_DIR=/home/goga/pipeline`, the workflow env vars (see [Workflow files](#workflow-files)), `GOGA_SKIP_STAGES=<csv>` when `--skip`/`-s` is passed, and — when a proxy is set — the proxy env vars, prints a workflow log line when a workflow is applied, and launches the goga Docker image. Credential files for claude/codex/opencode are detected on the host and bind-mounted read-only into the container automatically. Inside the container the goga in-container process resolves the pipeline to its absolute path, compiles the goga DSL pipeline-file into an afm flow-file at `<AFM_DIR>/flow.yml`, materializes the four agent prompt files into `<AFM_DIR>/prompts/` (applying any `roles` overrides from the pipeline-file header — see [Custom agent prompts](#custom-agent-prompts)), and invokes `afm run --port <port> [--max-parallel <N>] <compiled-flow-path>` (the `--max-parallel` is forwarded only when `-p/--parallel` is passed; otherwise afm runs unbounded). The container's exit code is propagated via `ctx.exit`.

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

List available pipeline names inside the container. The `Available pipelines:` header is always printed, even when the list is empty.

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

Run a pipeline by name. Pass the bare name only (no `.yml` extension); the container resolves the absolute path internally, compiles the goga DSL pipeline-file into an afm flow-file at `<AFM_DIR>/flow.yml`, materializes the four agent prompt files into `<AFM_DIR>/prompts/`, and runs that via `afm run`. Passing `-p/--parallel N` caps the number of stages afm executes concurrently (it threads through to `afm run --max-parallel <N>`); without it afm runs unbounded. A free port is allocated automatically and published on both sides (`-p <port>:<port>`); `afm` listens on that port inside the container. When a workflow is applied, a single log line naming it is printed to stdout; otherwise the launcher prints no status line.

Pipelines installed from `goga_tool_*` packages are namespaced as `<tool>:<name>.yml` and addressed as `goga pipeline <tool>:<name>` — the colon is part of the bare filename stem, not a separator. Internal pipelines stay un-prefixed.

```bash
goga pipeline feature
goga pipeline acme:deploy
```

```bash
goga pipeline deploy --workflow feature-phases
```

```
Pipeline running with workflow "feature-phases"
```

If the name exists in both sources, the project source wins. The container exit code is propagated as the command's exit code.

### Custom agent prompts

A pipeline-file header may carry an optional `roles` block with three fixed keys — `planner`, `executor`, `reviewer` — each an inline prompt that fully **replaces** (does not merge with) the corresponding shipped default prompt (`goga/assets/afm/prompts/<stem>.md`, where the planner/executor/reviewer keys map to the planning/implementation/review stems). The `summary` prompt is not overridable — it is always the shipped default.

```yaml
name: deploy
description: Deploy pipeline
roles:
  planner: |
    You are the planner for this deploy pipeline.
    Break the work into reviewable steps.
  reviewer: |
    Review each change against the deploy checklist.
---

- name: build
  title: Build
  prompt: Build it
```

Only those three keys are valid; an unknown key (including `summary`), a non-string value, a non-mapping `roles` block, or the legacy `agents` key is rejected as a structural DSL error at compile time (before any prompt file is written). When the block is absent or empty, the three shipped defaults are used unchanged (`summary.md` is always copied from its default). The overrides are a goga-side artifact and are not carried into the compiled flow-file.

At run time the four prompt files are materialized into `<AFM_DIR>/prompts/` (mounted at `/home/goga/pipeline/prompts`) before `afm` starts, and `afm` reads them through the `prompts_dir` field in its config. That `prompts/` directory is wiped and rebuilt from the defaults plus any `roles` overrides on every run, so files manually placed there do not persist.

### Workflow files

A pipeline run can optionally apply a *workflow-file* — a declarative YAML document that layers a top-level prompt, per-stage `agent`/`prompt` overrides, loop-expansion, stage skipping via `skip`, and new stages via `extend` on top of the compiled flow-file. Workflow-files live at `<cwd>/.goga/workflows/<name>.yml` and are project-only (the name must be a bare filename resolved inside that directory; path traversal via `..` or an absolute prefix is rejected).

Three invocation modes (mutually exclusive in the explicit cases):

- `goga pipeline deploy` (no flags) — *auto-match*: if `<cwd>/.goga/workflows/deploy.yml` exists it is applied silently; otherwise no workflow. No host-side validation.
- `goga pipeline deploy --workflow custom` — apply `<cwd>/.goga/workflows/custom.yml`. The host validates the file exists **before** launch (exit 1 if missing).
- `goga pipeline deploy --no-workflow` — disable workflow application entirely (writes `GOGA_WORKFLOW_DISABLED=1` into the container env-file).

When a workflow will actually be applied (explicit `--workflow`, or an auto-match file that exists), the launcher prints `Pipeline running with workflow "<name>"` to stdout. When no workflow applies, the launcher prints no workflow line. The launcher surfaces only the workflow log line and the `docker` output stream.

The workflow name reaches the container via the env-file (`GOGA_WORKFLOW_NAME=<name>` for `--workflow`; `GOGA_WORKFLOW_DISABLED=1` for `--no-workflow`; neither for auto-match). Inside the container the goga in-container process resolves and parses the workflow-file, then forwards it to the compiler, which reconstructs the parsed body: `extend` entries inject new stages positioned via `before`/`after`, per-stage `agent` overrides compose the in-container wrapper path into the stage's `command` slot, per-stage `prompt` overrides fill its `description` slot, `skip: true` removes the stage and reconnects its dependents' `depends_on`, and a `loop: N` (N ≥ 2) expands the stage into `NAME-1`..`NAME-N` copies with chained internal `depends_on` (external references are rewritten to the LAST expanded id).

Example workflow-file:

```yaml
prompt: |
  Top-level prompt injected as the first directive of the flow-file.
stages:
  propose:
    agent: codex
    prompt: |
      Additional per-stage instruction.
  propose-review:
    loop: 2
    agent: claude
```

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `name` (positional) | string | — | Pipeline name without extension. When omitted, runs discovery mode |
| `-e`, `--env` | string (repeatable) | — | Additional environment variable (`KEY=VALUE`) forwarded into the container env-file. Run mode only (ignored in discovery) |
| `--proxy` | string | config | HTTP/HTTPS proxy URL; overrides `pipeline.proxy`. Adds `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` to the container env-file. Run mode only |
| `--add-host` | string (repeatable) | -- | Add a `docker run --add-host HOST:IP` entry; merges on top of `pipeline.hosts` (CLI wins on key conflict). Effective in both modes |
| `-c`, `--clean` | flag | off | Wipe the persistent afm state directory before launch. Run mode only (no-op in discovery) |
| `--update`, `-u` | flag | off | Refresh the image before launch (build if a project Dockerfile is declared, else pull). Effective in both modes |
| `--workflow` | string | — | Apply an explicit workflow at `<cwd>/.goga/workflows/<name>.yml`. The file must exist on the host (exit 1 if missing). Mutually exclusive with `--no-workflow`. Run mode only |
| `--no-workflow` | flag | off | Disable workflow application entirely (writes `GOGA_WORKFLOW_DISABLED=1` into the container env-file). Mutually exclusive with `--workflow`. Run mode only |
| `-s`, `--skip` | string (repeatable) | — | Exclude a stage from the compiled pipeline (one name per invocation). The stage is removed and its dependents' `depends_on` are reconnected. Forwarded into the container env-file as `GOGA_SKIP_STAGES=<name>,...`. Not mutually exclusive with `--workflow`/`--no-workflow`. Run mode only (no-op in discovery); the host performs no name validation — unknown names surface in-container as a structural error |
| `-p`, `--parallel` | int | — | Cap the number of stages afm executes concurrently (run mode only). Threads through the container as `--parallel <N>`, which the in-container CLI forwards to `afm run --max-parallel <N>`. Omitted/absent (the default) ⇒ afm runs unbounded (backward compatible). No-op in discovery mode. The `-p` short alias is a separate namespace from the Docker `-p <port>:<port>` port-publish token, which is assembled inside the launcher |

### Persistent afm state

Run mode mounts a host directory at `/home/goga/pipeline` inside the container and sets `AFM_DIR=/home/goga/pipeline` in the env-file, so afm state (flows, run-state) survives across runs of the same pipeline in the same project on the same branch. The host directory is computed as:

```
~/.goga/runtime/pipelines/<normalized-project-path>/<git-branch>/<name>/
```

It is created before launch and is **not** deleted on exit. Use `--clean` to wipe it before launch when you want a fresh run.

Note that the `prompts/` subdirectory inside it is regenerated on every run (wiped and rebuilt from the shipped defaults plus any `roles` overrides) — it does not persist user-placed content even though the parent directory survives across runs.

### Proxy and hosts

`--proxy URL` (and `pipeline.proxy` in `.goga/config.yml`) route the container's traffic through a corporate proxy. When a proxy is resolved, three variables are written to the container env-file: `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY=localhost,127.0.0.1` (fixed; cannot be overridden). `--add-host HOST:IP` (and `pipeline.hosts` in `.goga/config.yml`) translate to `docker run --add-host HOST:IP` flags; CLI entries merge on top of config with the CLI winning on key conflict.

### Credential mounts

Credential files for claude (`~/.claude/.credentials.json`), codex (`~/.codex/auth.json`), and opencode (`~/.local/share/opencode/auth.json`) are detected on the host and bind-mounted read-only into the container automatically (no flag). Detection is agent-agnostic; only files that exist are mounted.

### Examples

Refresh the image, then run (default skips the refresh):

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
| `1`  | A `ClickException` before launch: the `pipeline` section is missing in `.goga/config.yml`, the named pipeline was not found in either source directory, `--workflow` and `--no-workflow` were both set, or an explicit `--workflow <name>` named a file that does not exist |
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
