# Build

Execute the implementation plan via a ralph-loop inside a Docker container. This is the bridge between the workflow and actual code — the ralph-loop reads the plan and produces the implementation.

## Synopsis

```bash
goga build <plan> [OPTIONS]
```

## Output artifact

Implemented code in the project tree, produced by the ralph-loop executing each plan task in sequence. CODEMANIFEST files remain **read-only** throughout the build.

## Algorithm

`goga build` runs a deterministic pipeline. Host-side steps assemble the environment and launch the container; the in-container entrypoint then guards its environment, prepares the `.ralphex` configuration, resolves the ralph-loop options, and delegates the launch to the ralph-loop launcher (`run_ralphex` in `goga/ralphex`), which invokes the external `ralphex` binary on `$PATH`, turning a missing binary or a rejected launch into a clean one-line error with exit code 1 and otherwise propagating ralphex's own exit code.

| Step | Stage | Action |
|---|---|---|
| 1. Docker check | host | Verify Docker is installed and accessible. Halt on failure. |
| 2. Config loading | host | Read `.goga/config.yml` for `image`, `dockerfile`, `build.task_executor.agent`, env, and timeouts. Refuse to run when the `build` section is absent, the top-level `image` is unset, or `build.task_executor.agent` is unset. |
| 3. Home config + git identity layering | host | Load the optional machine-wide home config (`~/.goga/config.yml`). `home.env` is the BASE (lowest-priority) layer of the container env-file; `home.docker.run` is appended to every `docker run`; `home.docker.build` is forwarded to image build. Layer in git identity env (`GIT_AUTHOR_NAME/EMAIL`, `GIT_COMMITTER_NAME/EMAIL`) — tolerate absent git config. |
| 4. Project preconditions | host → in-container | Resolve proxy (CLI `--proxy` wins over `config.build.proxy`); resolve hosts (CLI `--add-host` merges on top of `config.build.hosts`, CLI wins on conflict); when `--skip-manifest-check` is not set, scan `git status` for uncommitted `CODEMANIFEST` files and reject with exit 1 if any are found. |
| 5. Agent preconditions | host → in-container | The in-container entrypoint resolves the agent wrapper via `resolve_wrapper_path(config.build.task_executor.agent)` and writes `.ralphex/config` per pass with `claude_command` set to the pass's wrapper path (`/home/goga/bin/<agent>-as-claude.sh`), `claude_args` defaults when missing, `codex_enabled` from `BuildConfig`, `preserve_anthropic_api_key: true`, and `move_plan_on_completion: false` (goga owns the plan relocation itself). A review executor whose agent differs from the task executor, or that declares a non-empty `env`, combined with an active worktree is rejected on the host with exit 1 before any container launch (skip-independent — `--skip-review` does not bypass it). |
| 6. Defaults sync | in-container | Fully rewrite `.ralphex/prompts/` and `.ralphex/agents/` (stale files removed) from the configured `build.prompts_dir`/`build.agents_dir`, or from the vendored ralph-loop defaults shipped with goga (`goga/assets/ralphex/`). When `build.review_executor.roles` is a non-empty list, both review prompts are filtered to the selected roles and their counters adapted; with the full role set or no roles the files are byte-identical to the source. Custom directories are copied as-is, without filtering. |
| 7. ralph-loop option resolution | in-container | Two zones. Universal options resolve once in `_resolve_options` with precedence CLI options > `BuildConfig` > omit — `worktree`, `skip_finalize`, `session_timeout`, `idle_timeout`, `wait`, `max_iterations` — and join every pass. Review-scoped options — `base_ref`, `patience` — resolve in `resolve_review_options` with precedence CLI options > `ReviewExecutorConfig` > omit and join review-carrying passes only. The resolved options are forwarded to `run_ralphex`; the launcher does not resolve precedence itself. |
| 8. Image refresh (optional, `--update`/`-u`) | host | When set, refresh the image via `docker_update`: build when a top-level `dockerfile` is declared in `.goga/config.yml` (fatal on failure — exit 1), otherwise `docker pull <image>` (warning on failure, non-fatal — the build proceeds with the locally available image). Off by default. |
| 8b. First-run safety net | host | Runs unconditionally at launch entry via `docker_build_if_not_exist`: when `config.image` is absent locally AND `config.dockerfile` is declared, build it once before launch (fatal on failure — surfaces as a `ClickException`, launch skipped). No-op when the image is present or no Dockerfile is set. This closes the corner case where a project Dockerfile is declared but the image was never built and `--update` is not passed. |
| 9. Persistent ralph-loop runtime isolation | host | Bind-mount a centralized host directory at `/workspace/.ralphex` inside the container so ralph-loop state never lands in the user's project directory. The host directory is `~/.goga/runtime/builds/<normalized_project>/<branch>/` and survives across runs of the same project on the same branch (useful for resuming interrupted builds). Pass `-c`/`--clean` to wipe it before launch. Any `.ralphex/` Docker creates in the project directory is removed unconditionally on every exit path, including crash/SIGKILL. |
| 10. Docker launch | host | Launch the ralph-loop inside the configured Docker image using the in-container build entry point. A SIGTERM/SIGINT handler is installed before the secret env-file is written so a signal during setup unwinds to `finally` and unlinks the file. |
| 10a. Pre-launch version check | host | Inside the Docker launch, before the work container starts: one short-lived probe container (`docker run --rm --entrypoint python3 <image> -c "from importlib.metadata import version; print(version('goga'))"`, output captured) reports the image's goga version, compared with the host version at the (major, minor) level. A mismatch, a probe that cannot answer, or an undeterminable host version → one stderr message + exit 1, container not started. An image reporting `0.0.0` (locally built, no stamped version) → stderr warning, launch continues. Set `GOGA_SKIP_VERSION_CHECK=1` to skip the probe and the comparison entirely. |
| 11. Docker guard | in-container | The in-container entrypoint refuses to proceed outside the goga Docker image as its very first action. |
| 12. ralph-loop launch via `run_ralphex` | in-container | `build()` resolves the review options (`--skip-review`/`--no-skip-review` CLI pair > `build.review_executor.skip` > full cycle), validates them when the review phase will run, then delegates each pass to `run_ralphex` (goga/ralphex) with `plan`, the pass's options, `dry_run`, and — for the review pass of a two-pass run — the review env layer. One pass by default; a skipped review runs a single tasks-only pass (`ralphex --tasks-only`); a review executor agent differing from the task agent, or a non-empty `build.review_executor.env` (with an agent set), runs two passes — tasks with the task wrapper, then the review pass (`ralphex --review`) with the review wrapper and the review env overlaid on the container environment for that subprocess only (a failed first pass skips the second). The review-carrying pass — the single full-cycle pass or the review pass of a two-pass run — also carries the review-scoped options resolved in step 7 (`base_ref` → ralphex `--base-ref`, `patience` → ralphex `--review-patience`); a tasks-only pass carries the universal options only. `run_ralphex` maps options to ralphex CLI flags, verifies the `ralphex` binary is on `$PATH`, and propagates the subprocess exit code. A binary missing from `$PATH` — including when the env layer's `PATH` override hides it from the exec — or a launch rejected before the exec (an env-layer key that is not a legal environment variable name, an oversized layer, or a `PATH` override resolving a non-executable or non-directory ralphex binary) returns 1 with a clean one-line message on stderr — never a traceback, and never the env layer's values. The build environment is inherited from the docker env-file (`os.environ`) with an optional caller-supplied overlay for the review subprocess — never reconstructed from a config object. |
| 13. Plan relocation | in-container | After a successful final pass the plan file moves to `<plan_dir>/completed/<plan_name>` (atomic replace, idempotent by name). A failed run or a dry run leaves the plan in place for the ralph-loop to resume. |

Inside the container, the ralph-loop executes the plan: one task per iteration, following the ralphex execution protocol (declaration → contract tests → implementation → interface verification → logic tests → debugging → contract re-verification → lint → completion → review → approval → next task).

## When to use

- After `plan` and `review(plan)`, when the plan is approved.
- Whenever an execution plan exists under `.goga/history/` and is ready to be executed.

## Inputs and outputs

| | |
|---|---|
| **Input** | `.goga/history/<year>/<topic>/plan.md` — the execution plan |
| **Output** | Implemented code in the project tree; after a successful run the plan itself moves to `.goga/history/<year>/<topic>/completed/plan.md` |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | off | Print the assembled command without executing |
| `--worktree` | flag | off | Enable ralph-loop worktree mode |
| `--skip-finalize` | flag | off | Skip finalization step |
| `--skip-manifest-check` | flag | off | Skip check for uncommitted CODEMANIFEST files |
| `--skip-review` / `--no-skip-review` | bool pair (tri-state) | unset | Skip the review phase (`--skip-review`, the ralph-loop `--tasks-only`) or force the full cycle (`--no-skip-review`). Overrides `build.review_executor.skip`; when neither is given, the config decides |
| `--session-timeout` | string | config | Session timeout duration |
| `--idle-timeout` | string | config | Idle timeout duration |
| `--wait` | string | config | Wait time before starting |
| `--max-iterations` | int | config | Maximum number of build iterations |
| `--review-patience` | int | config | Review patience count |
| `--base-ref` | string | config | Review diff base (branch name or commit hash); overrides `build.review_executor.base_ref` |
| `-e`, `--env` | string | -- | Additional environment variable (`KEY=VALUE`, repeatable). Forwarded into the container env-file. |
| `--proxy` | string | config | HTTP/HTTPS proxy URL; overrides `build.proxy` in `.goga/config.yml`. When set, adds `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` to the container env-file. |
| `--add-host` | string (repeatable) | -- | Add a `docker run --add-host HOST:IP` entry. Merges on top of `build.hosts` from config; CLI wins on host-key conflict. |
| `--update`, `-u` | flag | off | Force-refresh the image before launch (build when `dockerfile` is declared in `.goga/config.yml`, else pull). Default skips the refresh. The first time a `dockerfile`-declared image is built, the command auto-builds it even WITHOUT `--update` (first-run safety net) — `--update` is only needed to force a RE-build of an already-present image. |
| `-c`, `--clean` | flag | off | Wipe the persistent ralph-loop runtime host directory under `~/.goga/runtime/builds/<normalized_project>/<branch>/` before launching the container. Default preserves state across runs of the same project on the same branch. |

Timeout and iteration options fall back to `.goga/config.yml` when not provided on the command line.

`--review-patience` and `--base-ref` are review-scoped: they resolve with precedence CLI > `build.review_executor.*` in `.goga/config.yml` > omit, and they apply to review-carrying passes only — the single full-cycle pass, or the review pass of a two-pass run; a tasks-only run carries neither. The legacy `build.review_patience` key is not parsed (the setting moved to `build.review_executor.patience`).

## Examples

```bash
goga build .goga/history/<year>/json-export/plan.md
goga build .goga/history/<year>/json-export/plan.md --dry-run
goga build .goga/history/<year>/json-export/plan.md --skip-manifest-check
goga build .goga/history/<year>/json-export/plan.md -e ANTHROPIC_API_KEY=sk-xxx

# Force-refresh the image before launch (build when dockerfile is declared, else pull)
goga build .goga/history/<year>/json-export/plan.md --update

# Route container traffic through a corporate proxy and add a local host entry
goga build .goga/history/<year>/json-export/plan.md --proxy http://corp:3128 --add-host foo.local:127.0.0.1

# Wipe persistent ralph-loop state before launch (start fresh)
goga build .goga/history/<year>/json-export/plan.md --clean

# Without --clean, ralph-loop state persists across runs of the same project+branch
goga build .goga/history/<year>/json-export/plan.md
goga build .goga/history/<year>/json-export/plan.md  # second run reuses .ralphex/ from the first
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Build completed successfully |
| `1` | Build failed (Docker not found, config error, `build` section missing, top-level `image` unset, a missing `build.task_executor.agent`, uncommitted `CODEMANIFEST` files, invalid review configuration, two-pass review combined with worktree, a missing `ralphex` binary or a rejected ralphex launch, a fatal `docker build` under `--update`, a ralphex error, or a refused pre-launch version check — a host–image (major, minor) mismatch, an image that cannot answer the version probe, or an undeterminable host version; see [`goga build`](../cli/build.md)) |

## What happens next

- The completed plan now lives in `.goga/history/<year>/<topic>/completed/` — nothing further reads it, but it stays for reference.
- Test the produced implementation manually.
- If bugs or defects are found — fix them with [`change`](change.md).
- Once the implementation is stable — run [`accept`](accept.md) for final sign-off.

See the full CLI reference: [`goga build`](../cli/build.md).
