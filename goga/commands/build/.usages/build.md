# CLI Command: build

## Purpose

CLI wrapper for the build command. Parses click options, loads configuration, and runs `goga.build` inside a Docker container.

## Syntax

```
goga build <plan> [--dry-run] [--worktree] [--skip-finalize] [--skip-manifest-check]
                 [--session-timeout T] [--idle-timeout T] [--wait T]
                 [--max-iterations N] [--review-patience N]
                 [-e KEY=VALUE ...]
                 [--proxy URL] [--add-host HOST:IP ...] [--update | -u]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `plan` | str | Path to the plan for ralphex |

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
| `--update` / `-u` | flag | false | Pull the image before launching the container. Default is no pull — the local image is used as-is |

## Exit code

- 0 — success
- 1 — error

## Examples

```bash
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md --dry-run --worktree
goga build docs/plans/my-plan.md -e ANTHROPIC_API_TOKEN=sk-xxx -e MODEL=claude-sonnet-4-6

# Pull the latest image, then build (default skips the pull)
goga build docs/plans/my-plan.md --update

# Route container traffic through a corporate proxy and add a local host entry
goga build docs/plans/my-plan.md --proxy http://corp:3128 --add-host foo.local:127.0.0.1
```

## Requirements

- Docker must be installed and available in PATH
- `.goga/config.yml` must have the top-level `image` field set — otherwise the command exits with error `image in .goga/config.yml is not set`
- By default the image is NOT pulled — the local image is used as-is. Use `--update`/`-u` to pull before launch. On pull failure a warning is logged and the build continues with the locally available image
- Git config (user.name, user.email) is automatically passed to the container as GIT_AUTHOR_NAME/EMAIL, GIT_COMMITTER_NAME/EMAIL. If git config is absent, the build continues without error
- Credential mounts are detected automatically via `resolve_credential_mounts()` — there is no `--credential`/`--mount` flag. The routine scans the host filesystem for known AI-agent credential files (claude `~/.claude/.credentials.json`, codex `~/.codex/auth.json`, opencode `~/.local/share/opencode/auth.json`), is agent-agnostic (it is not filtered by the configured `task_executor.agent`), and returns only files that exist. Every returned file is bind-mounted read-only into the container at the mirrored path under `/home/goga/`. When none exist, no credential mount is added — see the `resolve-credential-mounts` and `docker-auth-mounts` practices for details

## Proxy and hosts

`--proxy URL` (and `build.proxy` in config) drive three env-file entries when set:

| Variable     | Value                                            |
|--------------|--------------------------------------------------|
| `HTTP_PROXY` | the resolved proxy URL                           |
| `HTTPS_PROXY`| the resolved proxy URL                           |
| `NO_PROXY`   | `localhost,127.0.0.1` (fixed; CLI cannot override)|

`NO_PROXY` is mandatory whenever a proxy is set — without it, `--add-host foo.local:127.0.0.1` would route `foo.local` through the corporate proxy and break. CLI `--add-host` entries are NOT auto-added to `NO_PROXY`.

`--add-host HOST:IP` (and `build.hosts` in config) translate to `docker run --add-host HOST:IP` flags. CLI entries are merged on top of config; on host-key conflict, CLI wins.