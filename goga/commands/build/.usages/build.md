# CLI Command: build

## Purpose

CLI wrapper for the build command. Parses click options, loads configuration, and runs `goga.build` inside a Docker container.

## Syntax

```
goga build <plan> [--dry-run] [--worktree] [--skip-finalize] [--skip-manifest-check]
                 [--session-timeout T] [--idle-timeout T] [--wait T]
                 [--max-iterations N] [--review-patience N]
                 [-e KEY=VALUE ...]
                 [--proxy URL] [--add-host HOST:IP ...] [--clean] [--update | -u]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `plan` | str | Path to the plan for the ralph-loop |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dry-run` | flag | false | Show the command without executing |
| `--worktree` | flag | false | Isolated git worktree mode |
| `--skip-finalize` | flag | false | Skip finalization |
| `--skip-manifest-check` | flag | false | Skip uncommitted CODEMANIFEST check |
| `--session-timeout` | str | from config | Session timeout |
| `--idle-timeout` | str | from config | Idle timeout |
| `--wait` | str | from config | Wait on rate limit |
| `--max-iterations` | int | from config | Maximum iterations |
| `--review-patience` | int | from config | Review stop threshold |
| `-e` / `--env` | str (multiple) | — | Pass environment variables to the container (KEY=VALUE) |
| `--proxy` | str | from config | HTTP/HTTPS proxy URL; overrides `build.proxy` in `.goga/config.yml`. When set, adds HTTP_PROXY/HTTPS_PROXY/NO_PROXY to the container env-file |
| `--add-host` | str (multiple) | — | Add a `docker run --add-host HOST:IP` entry. Merges on top of `build.hosts` from config; CLI wins on host-key conflict |
| `-c` / `--clean` | flag | false | Wipe the persistent ralph-loop runtime directory under `~/.goga/runtime/builds/<normalized_project>/<branch>/` before launching the container. Default is no wipe — ralph-loop state (progress files, config, prompts, agents) survives across runs of the same project on the same branch, useful for resuming interrupted builds |
| `--update` / `-u` | flag | false | Force-refresh the image before launch (build when `dockerfile` is declared in `.goga/config.yml`, else pull). Default is no refresh. Note: the first time a `dockerfile`-declared image is built, the command auto-builds it even WITHOUT `--update` (first-run safety net) — `--update` is only needed to force a RE-build of an already-present image |

## Exit code

- 0 — success
- 1 — error

## Examples

```bash
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md --dry-run --worktree
goga build docs/plans/my-plan.md -e ANTHROPIC_API_KEY=sk-xxx -e MODEL=claude-sonnet-4-6

# Refresh the image before launch (build when dockerfile is declared, else pull)
goga build docs/plans/my-plan.md --update

# First run with a project Dockerfile declared in .goga/config.yml: the image
# is auto-built the first time even WITHOUT --update (first-run safety net).
# Use --update only to force a RE-build of an already-present image.
goga build docs/plans/my-plan.md

# Route container traffic through a corporate proxy and add a local host entry
goga build docs/plans/my-plan.md --proxy http://corp:3128 --add-host foo.local:127.0.0.1

# Wipe ralphex state before launch (start fresh)
goga build docs/plans/my-plan.md --clean

# Without --clean, ralphex state persists across runs of the same project+branch
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md  # second run reuses .ralphex/ from the first
```

## Requirements

- Docker must be installed and available in PATH
- `.goga/config.yml` must contain a `build` section (with a `task_executor.agent`). The loader makes the section optional (`config.build` is `None` when absent), but `goga build` cannot run without it — the command raises `ClickException("build section is required in .goga/config.yml to run 'goga build'")` before any field access and before the container is launched
- `.goga/config.yml` must have the top-level `image` field set — otherwise the command exits with error `image in .goga/config.yml is not set`
- By default the image is NOT refreshed — the local image is used as-is. Use `--update`/`-u` to refresh it before launch: build when a project Dockerfile is declared (fatal on failure), else pull (warning on failure, non-fatal — the build continues with the locally available image)
- First-run safety net: when `dockerfile` is declared in `.goga/config.yml` and the image is absent locally, the command builds it ONCE before launch even WITHOUT `--update` (so the first run after declaring a project Dockerfile does not need `--update`). `--update` forces a RE-build of an already-present image; the safety net is a no-op once the image exists
- Git config (user.name, user.email) is automatically passed to the container as GIT_AUTHOR_NAME/EMAIL, GIT_COMMITTER_NAME/EMAIL. If git config is absent, the build continues without error
- Credential mounts are detected automatically via `resolve_credential_mounts()` — there is no `--credential`/`--mount` flag. The routine scans the host filesystem for known AI-agent credential files (claude `~/.claude/.credentials.json`, codex `~/.codex/auth.json`, opencode `~/.local/share/opencode/auth.json`), is agent-agnostic (it is not filtered by the configured `task_executor.agent`), and returns only files that exist. Every returned file is bind-mounted read-only into the container at the mirrored path under `/home/goga/`. When none exist, no credential mount is added — see the `resolve-credential-mounts` and `docker-auth-mounts` practices for details
- Ralphex state (`.ralphex/`) is isolated from the project directory: the host directory `~/.goga/runtime/builds/<normalized_project>/<branch>/` is bind-mounted into the container at `/workspace/.ralphex`. No `.ralphex/` appears in the project directory, even on crash/SIGKILL. By default the directory persists across runs; pass `--clean` to wipe it before launch

## Proxy and hosts

`--proxy URL` (and `build.proxy` in config) drive three env-file entries when set:

| Variable     | Value                                            |
|--------------|--------------------------------------------------|
| `HTTP_PROXY` | the resolved proxy URL                           |
| `HTTPS_PROXY`| the resolved proxy URL                           |
| `NO_PROXY`   | `localhost,127.0.0.1` (fixed; CLI cannot override)|

`NO_PROXY` is mandatory whenever a proxy is set — without it, `--add-host foo.local:127.0.0.1` would route `foo.local` through the corporate proxy and break. CLI `--add-host` entries are NOT auto-added to `NO_PROXY`.

`--add-host HOST:IP` (and `build.hosts` in config) translate to `docker run --add-host HOST:IP` flags. CLI entries are merged on top of config; on host-key conflict, CLI wins.

## Home configuration (~/.goga/config.yml)

The optional, machine-wide home config is a narrow docker-only layer. Its
absence is normal — `load_home_config()` returns an empty `HomeConfig` and the
build is unaffected. The launcher loads it early (per the `home-configuration`
practice).

- **env (env-file base layer):** `home.env` is the BASE (lowest-priority) layer
  of the container env-file. Project config (`build.task_executor.env`) and CLI
  (`-e/--env`) override it on key conflict —
  `home.env < git identity < task_executor.env < CLI extra env`.
- **docker.run:** `home.docker.run` tokens are appended verbatim to the
  `docker run` (the runner's `extra_args` channel).
- **docker.build:** `home.docker.build` tokens are forwarded verbatim to image
  build — to `docker_build_if_not_exist` (first-run safety net) and
  `docker_update` (`--update`) in their build branch only. `home.env` is NEVER
  passed to `docker build` (no `--build-arg`).

Example `~/.goga/config.yml`:

```yaml
env:
  HTTPS_PROXY: http://corp:3128
docker:
  run:
    - --network=host
  build:
    - --no-cache
```

## Ralphex runtime isolation

By default, ralphex writes its state (config, prompts, agents, progress files) relative to its current working directory inside the container. The `goga build` command bind-mounts a centralized host directory at `/workspace/.ralphex` so this state never lands in the user's project directory.

**Host path:**
```
~/.goga/runtime/builds/<normalized_project>/<branch>/
```

- `<normalized_project>` — the current working directory's absolute path with leading slashes stripped and remaining slashes replaced by hyphens (e.g. `/Users/wb/IdeaProjects/goga` → `Users-wb-IdeaProjects-goga`)
- `<branch>` — the current git branch name with forward slashes replaced by hyphens (e.g. `feature/x` → `feature-x`); `"default"` when git is unavailable, the current directory is not a git repository, or HEAD is detached

**Container path:** `/workspace/.ralphex` (nested bind-mount on top of the `/workspace` project directory mount). ralphex auto-detects `.ralphex/` in its cwd and writes there transparently.

**Default behavior (no `--clean`):** the host directory persists across runs of the same project on the same branch. ralphex progress files survive — useful for resuming interrupted builds (ralphex detects the first incomplete task and continues from there).

**With `--clean`:** the host directory is wiped and recreated empty BEFORE `docker run`. The container starts with a clean `/workspace/.ralphex`.

**Crash safety:** because the runtime state lives under `~/.goga/runtime/`, interrupting a build (Ctrl+C, SIGKILL on docker) leaves no `.ralphex/` behind in the project directory. The host launcher removes any `.ralphex/` that Docker creates in the project directory on every exit path, including crash/SIGKILL. `.ralphex/` is never legitimate user data in the project directory — removal is unconditional when the directory exists.

**Concurrent builds:** two simultaneous `goga build` invocations on the same project + same branch share the same runtime directory and may collide on ralphex progress files. Run on different branches, or use `--clean` in only one of the invocations, to avoid the collision.
