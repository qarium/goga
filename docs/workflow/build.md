# Build

Execute the implementation plan via ralphex inside a Docker container. This is the bridge between the workflow and actual code — ralphex reads the plan and produces the implementation.

## Synopsis

```bash
goga build <plan> [OPTIONS]
```

## Output artifact

Implemented code in the project tree, produced by ralphex executing each plan task in sequence. CODEMANIFEST files remain **read-only** throughout the build.

## Algorithm

`goga build` runs a deterministic pipeline. Host-side steps assemble the environment and launch the container; the in-container entrypoint then guards its environment, prepares the `.ralphex` configuration, resolves the ralphex options, and delegates the launch to `run_ralphex` (goga/ralphex), which invokes the external `ralphex` binary on `$PATH` and propagates its exit code.

| Step | Stage | Action |
|---|---|---|
| 1. Docker check | host | Verify Docker is installed and accessible. Halt on failure. |
| 2. Config loading | host | Read `.goga/config.yml` for `image`, `dockerfile`, `build.task_executor.agent`, env, and timeouts. Refuse to run when the `build` section is absent or the top-level `image` is unset. |
| 3. Home config + git identity layering | host | Load the optional machine-wide home config (`~/.goga/config.yml`). `home.env` is the BASE (lowest-priority) layer of the container env-file; `home.docker.run` is appended to every `docker run`; `home.docker.build` is forwarded to image build. Layer in git identity env (`GIT_AUTHOR_NAME/EMAIL`, `GIT_COMMITTER_NAME/EMAIL`) — tolerate absent git config. |
| 4. Project preconditions | host → in-container | Resolve proxy (CLI `--proxy` wins over `config.build.proxy`); resolve hosts (CLI `--add-host` merges on top of `config.build.hosts`, CLI wins on conflict); when `--skip-manifest-check` is not set, scan `git status` for uncommitted `CODEMANIFEST` files and reject with exit 1 if any are found. |
| 5. Agent preconditions | host → in-container | The in-container entrypoint resolves the agent wrapper via `resolve_wrapper_path(config.build.task_executor.agent)` and writes `.ralphex/config` with `claude_command` set to the absolute wrapper path (`/home/goga/bin/<agent>-as-claude.sh`), `claude_args` defaults when missing, `codex_enabled` from `BuildConfig`, and `preserve_anthropic_api_key: true`. |
| 6. Defaults copy | in-container | Copy the shipped goga prompts and agents into `.ralphex/`. |
| 7. ralphex option resolution | in-container | Resolve ralphex options with precedence CLI options > `BuildConfig` > omit — `worktree`, `skip_finalize`, `session_timeout`, `idle_timeout`, `wait`, `max_iterations`, `review_patience`. The resolved options are forwarded to `run_ralphex`; the launcher does not resolve precedence itself. |
| 8. Image refresh (optional, `--update`/`-u`) | host | When set, refresh the image via `docker_update`: build when a top-level `dockerfile` is declared in `.goga/config.yml` (fatal on failure — exit 1), otherwise `docker pull <image>` (warning on failure, non-fatal — the build proceeds with the locally available image). Off by default. |
| 8b. First-run safety net | host | Runs unconditionally at launch entry via `docker_build_if_not_exist`: when `config.image` is absent locally AND `config.dockerfile` is declared, build it once before launch (fatal on failure — surfaces as a `ClickException`, launch skipped). No-op when the image is present or no Dockerfile is set. This closes the corner case where a project Dockerfile is declared but the image was never built and `--update` is not passed. |
| 9. Persistent ralphex runtime isolation | host | Bind-mount a centralized host directory at `/workspace/.ralphex` inside the container so ralphex state never lands in the user's project directory. The host directory is `~/.goga/runtime/builds/<normalized_project>/<branch>/` and survives across runs of the same project on the same branch (useful for resuming interrupted builds). Pass `-c`/`--clean` to wipe it before launch. Any `.ralphex/` Docker creates in the project directory is removed unconditionally on every exit path, including crash/SIGKILL. |
| 10. Docker launch | host | Launch ralphex inside the configured Docker image using the in-container build entry point. A SIGTERM/SIGINT handler is installed before the secret env-file is written so a signal during setup unwinds to `finally` and unlinks the file. |
| 11. Docker guard | in-container | The in-container entrypoint refuses to proceed outside the goga Docker image as its very first action. |
| 12. ralphex launch via `run_ralphex` | in-container | `build()` delegates the launch to `run_ralphex` (goga/ralphex) with `plan`, the resolved options, and `dry_run`. `run_ralphex` maps options to ralphex CLI flags, verifies the `ralphex` binary is on `$PATH` (returns 1 when missing), and propagates the subprocess exit code. The build environment is inherited from the docker env-file (`os.environ`), not reconstructed from a config object. |

Inside the container, ralphex executes the plan: one task per iteration, following the ralphex execution protocol (declaration → contract tests → implementation → interface verification → logic tests → debugging → contract re-verification → lint → completion → review → approval → next task).

## When to use

- After `plan` and `review(plan)`, when the plan is approved.
- Whenever an execution plan exists in `docs/plans/` and is ready to be executed.

## Inputs and outputs

| | |
|---|---|
| **Input** | `docs/plans/<topic>.md` — the execution plan |
| **Output** | Implemented code in the project tree |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | off | Print the assembled command without executing |
| `--worktree` | flag | off | Enable ralphex worktree mode |
| `--skip-finalize` | flag | off | Skip finalization step |
| `--skip-manifest-check` | flag | off | Skip check for uncommitted CODEMANIFEST files |
| `--session-timeout` | string | config | Session timeout duration |
| `--idle-timeout` | string | config | Idle timeout duration |
| `--wait` | string | config | Wait time before starting |
| `--max-iterations` | int | config | Maximum number of build iterations |
| `--review-patience` | int | config | Review patience count |
| `-e`, `--env` | string | -- | Additional environment variable (`KEY=VALUE`, repeatable). Forwarded into the container env-file. |
| `--proxy` | string | config | HTTP/HTTPS proxy URL; overrides `build.proxy` in `.goga/config.yml`. When set, adds `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` to the container env-file. |
| `--add-host` | string (repeatable) | -- | Add a `docker run --add-host HOST:IP` entry. Merges on top of `build.hosts` from config; CLI wins on host-key conflict. |
| `--update`, `-u` | flag | off | Force-refresh the image before launch (build when `dockerfile` is declared in `.goga/config.yml`, else pull). Default skips the refresh. The first time a `dockerfile`-declared image is built, the command auto-builds it even WITHOUT `--update` (first-run safety net) — `--update` is only needed to force a RE-build of an already-present image. |
| `-c`, `--clean` | flag | off | Wipe the persistent ralphex runtime host directory under `~/.goga/runtime/builds/<normalized_project>/<branch>/` before launching the container. Default preserves state across runs of the same project on the same branch. |

Timeout and iteration options fall back to `.goga/config.yml` when not provided on the command line.

## Examples

```bash
goga build docs/plans/json-export.md
goga build docs/plans/json-export.md --dry-run
goga build docs/plans/json-export.md --skip-manifest-check
goga build docs/plans/json-export.md -e ANTHROPIC_API_KEY=sk-xxx

# Force-refresh the image before launch (build when dockerfile is declared, else pull)
goga build docs/plans/json-export.md --update

# Route container traffic through a corporate proxy and add a local host entry
goga build docs/plans/json-export.md --proxy http://corp:3128 --add-host foo.local:127.0.0.1

# Wipe persistent ralphex state before launch (start fresh)
goga build docs/plans/json-export.md --clean

# Without --clean, ralphex state persists across runs of the same project+branch
goga build docs/plans/json-export.md
goga build docs/plans/json-export.md  # second run reuses .ralphex/ from the first
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Build completed successfully |
| `1` | Build failed (Docker not found, config error, `build` section missing, top-level `image` unset, uncommitted `CODEMANIFEST` files, missing `ralphex` binary, a fatal `docker build` under `--update`, or a ralphex error) |

## What happens next

- Test the produced implementation manually.
- If bugs or defects are found — fix them with [`change`](change.md).
- Once the implementation is stable — run [`accept`](accept.md) for final sign-off.

See the full CLI reference: [`goga build`](../cli/build.md).
