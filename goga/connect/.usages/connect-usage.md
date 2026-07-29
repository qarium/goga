# Connect API — goga/connect

## Overview

The `goga.connect` module installs goga skills, commands, and pipelines centrally
into `~/.goga/`, then creates symlinks from each connected agent's directory into
`~/.goga/`. A registry at `~/.goga/connect.yml` records which agents are connected
and with which `force_overwrite` setting, so commands that change the installed
packages (`goga install`, `goga upgrade`) can re-sync them afterwards.

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

- `agents` — list of target AI agents (required, non-empty). Supported: "claude", "codex", "cursor", "opencode", "qwen"
- `force_overwrite` — allow overwriting existing skills from tool packages. Defaults to False.
  Persisted per-agent in `~/.goga/connect.yml`.

## Return Value

- `0` — success
- `1` — error (empty agent list, unsupported agent, resources not found, download failure,
  pipeline installation failure)

## Re-sync API

`resync_registered_agents(goga_home)` re-applies `connect` to every agent listed in
`<goga_home>/connect.yml`, each with its own recorded `force_overwrite`. It is the
single, shared entry point for post-change activation used by `goga install` and
`goga upgrade`. A missing or empty registry is a no-op that returns 0.

```python
from goga.connect import resync_registered_agents
from pathlib import Path

# Re-sync every connected agent for the current user after a package change
exit_code = resync_registered_agents(Path.home() / ".goga")
```

Return value: `0` when every agent re-synced or the registry is missing/empty;
otherwise the first non-zero `connect` exit code. The loop continues after a
per-agent failure and reports the first one.

## Diagnostic Output

Every invocation of `connect()` prints a per-agent line to stderr as soon as it
begins processing that agent:

```
Connecting agent: claude
```

When `resync_registered_agents()` runs against a non-empty registry, it first
prints a one-line banner so the user can distinguish a re-sync from a direct
`goga connect`:

```
Re-syncing 3 registered agent(s): claude, codex, opencode
```

The banner is followed by the per-agent lines from `connect()` and the regular
central-install / pipeline / symlink summaries. A missing or empty registry is
a silent no-op (return 0, no banner).

## Central Installation Model

`~/.goga/` is the single source of truth:

| Directory               | Contents                                                 |
|-------------------------|----------------------------------------------------------|
| `~/.goga/skills/`       | All goga skills (goga-cell, goga-ast, ...) + goga-tool-* |
| `~/.goga/commands/`     | goga commands (claude/opencode/qwen consume them via symlink) |
| `~/.goga/pipelines/`    | Pipeline `*.yml` files (populated by `install_pipelines`)|
| `~/.goga/connect.yml`   | Registry of connected agents + per-agent force_overwrite |

## Registry Format

`~/.goga/connect.yml`:

```yaml
agents:
  claude:
    force_overwrite: false
  codex:
    force_overwrite: true
```

Each call to `connect(agents=[...], force_overwrite=...)` updates the entries for
the listed agents; entries for agents not in the current call are preserved.
`goga install` and `goga upgrade` read this file via `resync_registered_agents` to
re-sync the connected agents after a package change, using the per-agent
`force_overwrite`.

## Side Effects

- Recreates `~/.goga/{skills,commands}` (purge + copy from `goga/assets/`).
- Downloads `dsl.md` from GitHub into `~/.goga/skills/goga-cell/dsl.md`.
- Discovers `goga_tool_*` packages and copies their skills into `~/.goga/skills/`.
- Purges stale `goga-*` entries under each `~/.<agent>/skills/`.
- Creates symlinks from agent directories into `~/.goga/`.
- Calls `install_pipelines` to populate `~/.goga/pipelines/`.
- Writes `~/.goga/connect.yml` (single writer).

## Preconditions

- The user must have write access to `~/.goga/` and to each agent's target directory.
- On Windows, symlink creation may require elevated privileges or Developer Mode.

## Anti-patterns

- Do not copy assets directly into per-agent directories — the centralized model requires symlinks.
- Do not write to `~/.goga/connect.yml` from outside `goga/connect` — it is the single
  writer. The `goga install` and `goga upgrade` commands call `connect()` /
  `resync_registered_agents()` for activation and never write the registry directly.
