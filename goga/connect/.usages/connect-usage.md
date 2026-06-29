# Connect API — goga/connect

## Overview

The `goga.connect` module installs goga skills, commands, and flows **centrally** into `~/.goga/`,
then creates symlinks from each connected agent's directory into `~/.goga/`. A registry at
`~/.goga/connect.yml` records which agents are connected and with which `force_overwrite` setting,
so `goga upgrade` can re-sync them after a package upgrade.

## Usage

```python
from goga.connect import connect

# Install for a single agent
exit_code = connect(agents=["claude"])

# Install for multiple agents
exit_code = connect(agents=["claude", "codex"])

# Install with tool skill overwrite
exit_code = connect(agents=["claude"], force_overwrite=True)
```

## Parameters

- `agents` — list of target AI agents (required, non-empty). Supported: "claude", "codex", "cursor"
- `force_overwrite` — allow overwriting existing skills from tool packages. Defaults to False.
  Persisted per-agent in `~/.goga/connect.yml`.

## Return Value

- `0` — success
- `1` — error (empty agent list, unsupported agent, resources not found, download failure,
  flow installation failure)

## Central Installation Model

`~/.goga/` is the single source of truth:

| Directory               | Contents                                                 |
|-------------------------|----------------------------------------------------------|
| `~/.goga/skills/`       | All goga skills (goga-cell, goga-ast, ...) + goga-tool-* |
| `~/.goga/commands/`     | goga commands (claude-only consumers via symlink)        |
| `~/.goga/flows/`        | Flow `*.yml` files (populated by `install_flows`)        |
| `~/.goga/connect.yml`   | Registry of connected agents + per-agent force_overwrite |

## Agent Symlinks

For each agent in `agents`, the following symlinks are created (existing real directories and
stale symlinks matching the `goga-*` pattern are purged before symlink creation):

| Agent  | Skills symlinks                                       | Commands symlink                        |
|--------|-------------------------------------------------------|-----------------------------------------|
| claude | `~/.claude/skills/goga-*` → `~/.goga/skills/goga-*`   | `~/.claude/commands/goga` → `~/.goga/commands` |
| codex  | `~/.codex/skills/goga-*` → `~/.goga/skills/goga-*`    | (no commands)                           |
| cursor | `~/.cursor/skills/goga-*` → `~/.goga/skills/goga-*`   | (no commands)                           |

## Registry Format

`~/.goga/connect.yml`:

```yaml
agents:
  claude:
    force_overwrite: false
  codex:
    force_overwrite: true
```

Each call to `connect(agents=[...], force_overwrite=...)` updates the entries for the listed
agents; entries for agents not in the current call are preserved. `goga upgrade` reads this file
to determine which agents to re-sync after a package upgrade, using the per-agent `force_overwrite`.

## Side Effects

- Recreates `~/.goga/{skills,commands}` (purge + copy from `goga/assets/`).
- Downloads `dsl.md` from GitHub into `~/.goga/skills/goga-cell/dsl.md`.
- Discovers `goga_tool_*` packages and copies their skills into `~/.goga/skills/`.
- Purges stale `goga-*` entries under each `~/.<agent>/skills/` (and `~/.<agent>/commands/goga` for claude).
- Creates symlinks from agent directories into `~/.goga/`.
- Calls `install_flows` to populate `~/.goga/flows/`.
- Writes `~/.goga/connect.yml`.

## Preconditions

- The user must have write access to `~/.goga/` and to each agent's target directory.
- On Windows, symlink creation may require elevated privileges or Developer Mode.

## Anti-patterns

- Do not copy assets directly into per-agent directories — the centralized model requires symlinks.
- Do not call `connect()` from outside `goga/connect` or `goga/commands/upgrade` — connect.yml integrity
  depends on a single writer.
