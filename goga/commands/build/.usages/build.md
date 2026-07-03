# CLI Command: build

## Purpose

CLI wrapper for the build command. Parses click options, loads configuration, and runs goga.build inside a Docker container.

## Syntax

```
goga build <plan> [--dry-run] [--worktree] [--skip-finalize] [--skip-manifest-check]
                 [--session-timeout T] [--idle-timeout T] [--wait T]
                 [--max-iterations N] [--review-patience N]
                 [-e KEY=VALUE ...]
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

## Exit code

- 0 — success
- 1 — error

## Examples

```bash
goga build docs/plans/my-plan.md
goga build docs/plans/my-plan.md --dry-run --worktree
goga build docs/plans/my-plan.md -e ANTHROPIC_API_TOKEN=sk-xxx -e MODEL=claude-sonnet-4-6
```

## Requirements

- Docker must be installed and available in PATH
- `.goga/config.yml` must have the `build.image` field set — otherwise the command exits with error `image in .goga/config.yml is not set`
- Before launch, the build image is refreshed via `docker pull <build.image>`. This requires network access to the image registry; on pull failure a warning is logged (`failed to pull image '<image>'`) and the build continues with the locally available image
- Git config (user.name, user.email) is automatically passed to the container as GIT_AUTHOR_NAME/EMAIL, GIT_COMMITTER_NAME/EMAIL. If git config is absent, the build continues without error
- If `~/.codex/auth.json` exists, the file is mounted into the container as read-only (`/home/goga/.codex/auth.json`)
