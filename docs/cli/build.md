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
6. **Docker execution** -- Launches the ralphex command inside the configured Docker image.

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

Timeout and iteration options fall back to values in `.goga/config.yml` when not provided on the command line.

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

## Configuration

Build settings are loaded from `.goga/config.yml`. Required fields:

```yaml
language: python
build:
  image: qarium/goga-python-3.12:1.0
  task_executor:
    agent: claude
    env: {}
```

The `image` field must be set; otherwise the command exits with an error.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Build completed successfully |
| `1` | Build failed (Docker not found, config error, precondition failure, or ralphex error) |
