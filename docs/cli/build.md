# goga build

Execute a build plan via ralphex inside a Docker container.

## Synopsis

```bash
goga build PLAN [OPTIONS]
```

## Description

`goga build` launches the goga build pipeline for a given plan file. It prepares the environment, validates preconditions, and delegates execution to [ralphex](https://github.com/qarium/ralphex) running inside a Docker container with `python -m goga.build` as the entry point.

The build pipeline performs these steps:

1. **Docker check** -- Verifies Docker is installed and accessible.
2. **Config loading** -- Reads `.goga/config.yml` for build settings.
3. **Uncommitted manifest check** -- Scans `git status` for uncommitted `CODEMANIFEST` files (can be skipped).
4. **Agent preconditions** -- Sets up agent-specific files (e.g., `.claude/settings.json`, `.ralphex/claude-wrapper.sh` for Claude).
5. **Defaults copy** -- Copies default prompts and agent configurations to `.ralphex/`.
6. **Image pull (optional)** -- When `--update`/`-u` is set, refreshes the configured build image via `docker pull`. A pull failure is logged as a warning; the build then proceeds with the locally available image. By default no pull happens and the local image is used as-is.
7. **Docker execution** -- Launches the ralphex command inside the configured Docker image. Credential files for claude, codex, and opencode are detected on the host and bind-mounted read-only into the container automatically (no flag).

## Arguments

| Argument | Description |
|---|---|
| `PLAN` | Path to the build plan file (required). |

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
| `-e`, `--env` | string | -- | Additional environment variable (`KEY=VALUE`, repeatable) |
| `--proxy` | string | config | HTTP/HTTPS proxy URL; overrides `build.proxy`. Adds `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY=localhost,127.0.0.1` to the container env-file |
| `--add-host` | string (repeatable) | -- | Add a `docker run --add-host HOST:IP` entry; merges on top of `build.hosts` (CLI wins on key conflict) |
| `--update`, `-u` | flag | off | Pull the image before launching the container (default skips the pull) |

Timeout and iteration options fall back to values in `.goga/config.yml` when not provided on the command line.

### Proxy and hosts

`--proxy URL` (and `build.proxy` in `.goga/config.yml`) route the container's traffic through a corporate proxy. When a proxy is resolved, three variables are written to the container env-file:

| Variable | Value |
|---|---|
| `HTTP_PROXY` | the resolved proxy URL |
| `HTTPS_PROXY` | the resolved proxy URL |
| `NO_PROXY` | `localhost,127.0.0.1` (fixed; cannot be overridden) |

`--add-host HOST:IP` (and `build.hosts` in `.goga/config.yml`) translate to `docker run --add-host HOST:IP` flags. CLI entries are merged on top of config; on host-key conflict, the CLI entry wins. Format is split on the first colon only — Docker reports malformed entries itself.

### Credential mounts

Credential files for the supported AI agents are detected on the host and bind-mounted read-only into the container automatically (no flag): claude (`~/.claude/.credentials.json`), codex (`~/.codex/auth.json`), and opencode (`~/.local/share/opencode/auth.json`). Detection is agent-agnostic — it is not filtered by the configured `task_executor.agent` — and only files that exist are mounted. When none exist, no credential mount is added.

## Examples

Run a build plan:

```bash
goga build plan.md
```

Dry run to see the command without executing:

```bash
goga build plan.md --dry-run
```

Run with custom timeouts and an extra environment variable:

```bash
goga build plan.md --session-timeout 3600 --max-iterations 50 -e ANTHROPIC_API_KEY=sk-xxx
```

Skip the uncommitted CODEMANIFEST check:

```bash
goga build plan.md --skip-manifest-check
```

Pull the latest image, then build (default skips the pull):

```bash
goga build plan.md --update
```

Route container traffic through a corporate proxy and add a local host entry:

```bash
goga build plan.md --proxy http://corp:3128 --add-host foo.local:127.0.0.1
```

## Configuration

Build settings are loaded from `.goga/config.yml`. Required fields:

```yaml
language: python
image: qarium/goga-python-3.12:1.0
pipeline:
  agent: claude
build:
  task_executor:
    agent: claude
    env: {}
  proxy: http://corp:3128      # optional HTTP/HTTPS proxy URL for the build container
  hosts:                        # optional docker run --add-host entries
    foo.local: 127.0.0.1
```

The top-level `image` field must be set; otherwise the command exits with an error. The deprecated `build.image` field is rejected — use the top-level `image` field. The optional `build.proxy` and `build.hosts` fields are overridden/augmented by the `--proxy` and `--add-host` CLI options respectively.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Build completed successfully |
| `1` | Build failed (Docker not found, config error, precondition failure, or ralphex error) |
