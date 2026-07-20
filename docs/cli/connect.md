# goga connect

Install goga skills and commands for AI coding agents.

## Synopsis

```bash
goga connect AGENTS... [--force-overwrite]
```

## Description

`goga connect` installs goga's commands, skills, and DSL specification for one or more AI coding agents. Assets are installed **centrally** into `~/.goga/`, then each connected agent receives **symlinks** into that central store. A registry at `~/.goga/connect.yml` records the connected agents and their `force_overwrite` setting, so [`goga install`](install.md) and [`goga upgrade`](upgrade.md) can re-sync them after a package change.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `AGENTS` | yes | One or more target AI agent names. Currently supported: `claude`, `codex`, `cursor`, `opencode`. |

## Options

| Option | Default | Description |
|---|---|---|
| `--force-overwrite` | off | Overwrite existing tool skills without prompting. Persisted per-agent in `~/.goga/connect.yml`. |

## What It Does

`goga connect` performs the following steps:

1. **Central install** -- Recreates `~/.goga/skills/` (purging old `goga-*` entries) and `~/.goga/commands/`, then copies goga commands and skills into the central store.
2. **Download DSL spec** -- Fetches the CODEMANIFEST DSL specification from GitHub and writes it to `~/.goga/skills/goga-cell/dsl.md`.
3. **Discover tool packages** -- Scans installed Python packages with the `goga_tool_*` prefix via `importlib.metadata` and installs any that contain a valid `skills/<name>/SKILL.md` structure into `~/.goga/skills/`.
4. **Agent symlinks** -- For each specified agent, purges stale `goga-*` real directories and broken symlinks under the agent's skills directory, then symlinks every `~/.goga/skills/goga-*` entry into `~/.<agent>/skills/`. Agents with command support (currently `claude` and `opencode`) also get `~/.<agent>/commands/goga` symlinked to `~/.goga/commands/`.
5. **Install pipelines** -- Installs pipeline `*.yml` files into `~/.goga/pipelines/`. A failure here aborts the connect.
6. **Update registry** -- Atomically updates `~/.goga/connect.yml`, recording each agent with its `force_overwrite` value. Entries for agents not in the current call are preserved.

### Central installation model

`~/.goga/` is the single source of truth:

| Directory | Contents |
|---|---|
| `~/.goga/skills/` | All goga skills (`goga-cell`, ...) plus `goga-tool-*` skills |
| `~/.goga/commands/` | goga commands (claude and opencode consume them via symlink) |
| `~/.goga/pipelines/` | Pipeline `*.yml` files |
| `~/.goga/connect.yml` | Registry of connected agents and per-agent `force_overwrite` |

### Supported Agents

| Agent | Target Directory | Commands symlink |
|---|---|---|
| `claude` | `~/.claude/` | `~/.claude/commands/goga` -> `~/.goga/commands` |
| `codex` | `~/.codex/` | (none) |
| `cursor` | `~/.cursor/` | (none) |
| `opencode` | `~/.config/opencode/` | `~/.config/opencode/commands/goga` -> `~/.goga/commands` |

## Examples

Connect goga to Claude:

```bash
goga connect claude
```

Force overwrite of existing tool skills:

```bash
goga connect claude --force-overwrite
```

Connect multiple agents (opencode also receives the commands symlink):

```bash
goga connect claude codex opencode
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All agents configured successfully |
| `1` | Error (unsupported agent, resources not found, download failure, or pipeline installation failure) |
