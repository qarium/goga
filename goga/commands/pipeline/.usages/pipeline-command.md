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

The command allocates a free localhost port and launches afm inside the
container with that port forwarded. The launcher does NOT print a dashboard
URL line on stdout — the user already knows the port from the `-p` mapping
and the container output stream is forwarded unchanged.

To pass extra environment variables into the container (e.g. an agent
authorization token), repeat `-e KEY=VALUE` (or `--env KEY=VALUE`) on the
host-side invocation. The strings are appended to the container env-file
verbatim, with no validation — the same semantics as `goga build -e`:

```bash
goga pipeline deploy -e ANTHROPIC_API_KEY=sk-xxx -e MODEL=claude-sonnet-4-6
```

Refresh the image before launch (build when dockerfile is declared, else pull). Default skips the refresh:

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

### Workflow layer

Apply an explicit workflow-file (must exist on host — early validation,
exit 1 on missing file):

```bash
goga pipeline deploy --workflow custom
```

Output on success:

```
Pipeline running with workflow "custom"
```

Disable workflow application entirely (overrides the basename auto-match
fallback and any `--workflow`):

```bash
goga pipeline deploy --no-workflow
```

When NEITHER `--workflow` NOR `--no-workflow` is passed, the launcher
attempts the basename auto-match fallback: it checks whether
`<cwd>/.goga/workflows/<name>.yml` exists on the host. When present, the
log line is printed and the container resolves the workflow via the
basename fallback. When absent, no log is printed and the container
silent-misses.

`--workflow` and `--no-workflow` are mutually exclusive — passing both
exits 1 with a readable ClickException before any further work.

The `Pipeline running with workflow "<name>"` log line is printed to
stdout ONLY when a workflow will actually be applied:

- explicit `--workflow X` (file validated on the host at step 6 of the
  click command), OR
- basename auto-match file `<cwd>/.goga/workflows/<name>.yml` exists on
  the host.

When `--no-workflow` is set OR the auto-match file does not exist, NO
workflow log is printed.

The launcher does NOT print any dashboard URL line — stdout carries at
most the workflow log line (above) and the docker output stream.

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
- `--update` / `-u` (flag) — force-refresh the image before launch (build when
  `dockerfile` is declared in `.goga/config.yml`, else pull). Default is no
  refresh. Effective in both modes. Note: the first time a `dockerfile`-declared
  image is built, the command auto-builds it even WITHOUT `--update` (first-run
  safety net, runs in both modes) — `--update` is only needed to force a RE-build
  of an already-present image.
- `--workflow NAME` (str) — apply an explicit workflow-file at
  `<cwd>/.goga/workflows/<name>.yml`. Mutually exclusive with `--no-workflow`.
  When provided, the launcher validates that the file exists on the host
  BEFORE launching the container (ClickException with exit 1 on missing
  file). Run mode only — has no effect in discovery mode. The workflow name
  is forwarded into the container env-file as `GOGA_WORKFLOW_NAME=<name>`.
- `--no-workflow` (flag) — disable workflow application entirely. Mutually
  exclusive with `--workflow`. Run mode only. Sets
  `GOGA_WORKFLOW_DISABLED=1` in the container env-file, forcing the
  in-container `run_pipeline` routine to skip workflow resolution.

## Workflow flag matrix

| CLI flags                                  | Host validation                          | Env-file entries                                  | Workflow log line                                  | In-container behavior                                          |
|--------------------------------------------|------------------------------------------|---------------------------------------------------|----------------------------------------------------|----------------------------------------------------------------|
| (none)                                     | basename auto-match file existence check | (neither env var set)                             | printed ONLY when auto-match file exists           | `run_pipeline` resolves basename fallback; silent miss if absent |
| `--workflow X`                             | file existence for `<cwd>/.goga/workflows/X.yml` (early, exit 1 on miss) | `GOGA_WORKFLOW_NAME=X`                            | `Pipeline running with workflow "X"`               | `run_pipeline` resolves `X.yml`; defensive silent-miss on absent file |
| `--no-workflow`                            | (none — pure flag)                       | `GOGA_WORKFLOW_DISABLED=1`                        | (no log)                                           | `run_pipeline` skips workflow resolution entirely              |
| `--workflow X --no-workflow`               | (rejected)                               | (rejected)                                        | (rejected)                                         | ClickException "--workflow and --no-workflow are mutually exclusive", exit 1 |

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
2. When `config.pipeline` is `None` (the `pipeline` section is absent in `.goga/config.yml`) → raises `ClickException("pipeline section is required in .goga/config.yml to run 'goga pipeline'")` before any field access. The section is optional at the loader level, but `goga pipeline` cannot run without it.
3. Verifies docker availability.
4. Checks `config.image` is set (ClickException otherwise).
5. Assembles a docker run command including one `--add-host HOST:IP` flag per
   resolved hosts entry (CLI `--add-host` merged on top of `pipeline.hosts`
   from config; CLI wins on conflict).
6. First-run safety net: when `dockerfile` is declared in `.goga/config.yml`
   and the image is absent locally, builds it ONCE before launch (no-op when
   the image is present or no Dockerfile is set; fatal build surfaces as
   ClickException, launch skipped).
7. When `--update` is set: refreshes the image via `docker_update` (build when a project Dockerfile is declared, fatal on failure; else pull, warning on failure, non-fatal). Default is no refresh.
8. Runs `docker run --rm [-v <host_dir>:/workspace -w /workspace] [--add-host HOST:IP ...] --entrypoint python3 <config.image> -m goga.pipeline list` (in-container entrypoint).
9. Propagates the container's exit code.

`extra_env`, `proxy`, `--clean`, `--workflow`, and `--no-workflow` have no
effect in discovery mode — no env-file is written, no afm state directory
is involved, no workflow layer applies.

### Run mode

1. Loads `.goga/config.yml` via `load_config`.
2. When `config.pipeline` is `None` (the `pipeline` section is absent in `.goga/config.yml`) → raises `ClickException("pipeline section is required in .goga/config.yml to run 'goga pipeline'")` before any field access. Same guard as Discovery mode step 2.
3. Validates the workflow flag combination:
   - When `--workflow` AND `--no-workflow` are both set → raises
     `ClickException("--workflow and --no-workflow are mutually exclusive")`,
     exit 1, BEFORE any further work.
4. When `--workflow X` is set: validates that
   `<cwd>/.goga/workflows/X.yml` exists on the host. Missing file raises
   `ClickException("workflow 'X' not found at <path>")`, exit 1, BEFORE
   container launch.
5. Verifies docker availability; checks `config.image`.
6. Allocates a free localhost port (bind to `("", 0)`, read assigned port, close socket).
7. Resolves the agent wrapper path via `resolve_wrapper_path(config.pipeline.agent)`
   and writes a tmpfile containing `client.command: <resolved wrapper path>`,
   `theme: goga`, `open_browser: false`, `proxy.enabled: false`, and
   `prompts_dir: /home/goga/pipeline/prompts` (mode 0600). `theme`,
   `open_browser`, `proxy.enabled`, and `prompts_dir` are static launcher-side
   constants — `prompts_dir` is the in-container prompts directory populated by
   the in-container `run_pipeline` from the four goga-packaged defaults plus
   any inline overrides from the pipeline-file header; goga writes this field
   unconditionally so afm uses goga-managed prompts rather than its own
   built-in defaults, regardless of whether the pipeline-file contains an
   `agents` block.
8. Resolves the persistent afm state host directory via
   `resolve_pipeline_runtime_dir(name)` (= `~/.goga/runtime/pipelines/<normalized_project>/<git-branch>/<name>/`)
   and ensures it exists (`mkdir -p`, idempotent).
9. When `--clean` is set: wipes the directory via `clean_pipeline_runtime_dir`
   (recursive rmtree + recreate) **before** launch.
10. Computes the workflow env-file entries (host-side, BEFORE container launch):
    - When `--no-workflow` is set:
      - `workflow_env = {"GOGA_WORKFLOW_DISABLED": "1"}`
      - `workflow_log_name = None` (no log emitted)
    - Else when `--workflow X` is set (file already validated by step 4):
      - `workflow_env = {"GOGA_WORKFLOW_NAME": "X"}`
      - `workflow_log_name = "X"`
    - Else (auto-match fallback):
      - Compose `auto_match_path = <cwd>/.goga/workflows/<name>.yml`
      - When `auto_match_path.exists()`:
        - `workflow_env = {}` (in-container `run_pipeline` resolves basename fallback)
        - `workflow_log_name = <name>` (the candidate)
      - Else:
        - `workflow_env = {}` (in-container `run_pipeline` will silent-miss)
        - `workflow_log_name = None` (no log — file does not exist)
11. When `workflow_log_name` is not None: prints
    `Pipeline running with workflow "<workflow_log_name>"` to stdout. This
    cell surfaces ONLY this workflow log line — it does NOT print any
    dashboard URL line.
12. Builds an env-file with `config.pipeline.env` + git identity + extra
    `KEY=VALUE` pairs supplied via `-e/--env` + `AFM_DIR=/home/goga/pipeline` +
    `workflow_env` entries (GOGA_WORKFLOW_NAME and/or GOGA_WORKFLOW_DISABLED
    per step 10) + (when proxy is set) `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1`
    (mode 0600).
13. Installs SIGTERM/SIGINT handlers that `docker kill` the container.
14. Assembles the docker run command:
    - `--rm -p <port>:<port>`
    - `-v <project_dir>:/workspace -w /workspace`
    - `-v <pipeline_runtime_dir>:/home/goga/pipeline` (read-write — persistent state)
    - `-v <afm_tmpfile>:/home/goga/.afm/config.yaml:ro` (read-only — `client.command` overlay; this path is independent of `AFM_DIR`)
    - one `--add-host HOST:IP` flag per resolved hosts entry
    - one `-v <host_path>:<container_path>:ro` flag per credential file detected by `resolve_credential_mounts()` (claude/codex/opencode when present on the host)
    - `--env-file <env_file>`
    - `--entrypoint python3 <config.image> -m goga.pipeline run <name> --port <port>`
15. First-run safety net: when `dockerfile` is declared in `.goga/config.yml`
    and the image is absent locally, builds it ONCE before launch (no-op when
    the image is present or no Dockerfile is set; fatal build surfaces as
    ClickException, launch skipped; secret tmpfile/env-file are unlinked).
16. When `--update` is set: refreshes the image via `docker_update` (build when a project Dockerfile is declared, fatal on failure; else pull, warning on failure, non-fatal). Default is no refresh.
17. Launches the container and waits for its exit code.
18. In `finally`: deletes the `client.command` tmpfile and the env-file,
    `docker kill`s the container. **The persistent afm state host directory
    is NOT deleted** — it survives across runs of the same pipeline.

## Container exit code mapping

| Exit code | Condition                                                                |
|-----------|--------------------------------------------------------------------------|
| 0         | Discovery succeeded / afm ran the pipeline successfully                  |
| 1         | ClickException: missing pipeline section, missing --workflow file, mutually-exclusive flag violation |
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
- Run mode: allocates a localhost port, creates two tmpfiles (afm config, env-file),
  launches afm inside the container. The host installs SIGTERM/SIGINT handlers for
  the lifetime of the run. When a workflow will be applied, the launcher prints
  the `Pipeline running with workflow "<name>"` log line to stdout BEFORE
  launch; otherwise nothing is printed before the docker output stream.
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
- (Run mode, `--workflow X`) `<cwd>/.goga/workflows/X.yml` must exist on
  the host. The launcher validates this BEFORE container launch.

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
- Do NOT refresh the image by default — the default behavior is no refresh.
  Use `--update`/`-u` to refresh before launch (build when a project Dockerfile
  is declared, else pull).
- Do NOT derive the `client.command` tmpfile mount target from `AFM_DIR` —
  `config.yaml` is always read from `~/.afm/config.yaml` regardless of where
  `AFM_DIR` points. The persistent directory mounted at `/home/goga/pipeline`
  supplies the rest of afm state (flows, run-state).
- Do not filter credential mounts by the configured `pipeline.agent` — detection
  is agent-agnostic (see the `docker-auth-mounts` practice).
- Do NOT derive `prompts_dir` from an additional CLI option, config field, or
  runtime argument — the value is fixed at `/home/goga/pipeline/prompts` and
  follows from the known `AFM_DIR=/home/goga/pipeline` constant. goga does not
  duplicate the afm-owned `prompts_dir` setting in its own Config; the
  launcher-side value is the single source of truth.
- Do NOT pass `--workflow X --no-workflow` together — exit 1 with a
  readable ClickException before any further work.
- Do NOT expect `--workflow X` to launch the container when the file is
  missing on the host — the launcher exits 1 BEFORE container launch.
- Do NOT expect host-side existence validation for the basename auto-match
  case (no `--workflow` and no `--no-workflow`) — that resolution lives
  in-container.
- Do NOT expect a dashboard URL line on stdout — this cell prints only the
  workflow log line (when applicable) and forwards the docker output stream.
- Do NOT expect the `Pipeline running with workflow "<name>"` line when
  `--no-workflow` is set OR when the auto-match file does not exist on the
  host — the log is emitted ONLY when a workflow will actually be applied.
- Do NOT import workflow-parsing routines or workflow-document types on
  the host — workflow parsing happens in-container; the host only writes
  the env vars and validates file existence for explicit `--workflow`.
