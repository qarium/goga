# goga connect

Install goga skills and commands for AI coding agents.

## Synopsis

```bash
goga connect AGENTS... [--force-overwrite]
```

## Description

`goga connect` sets up goga's commands, skills, and DSL specification for one or more AI coding agents. It removes any previously installed goga-related resources, installs the latest versions, downloads the CODEMANIFEST DSL specification, and discovers tool packages.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `AGENTS` | yes | One or more target AI agent names. Currently supported: `claude`. |

## Options

| Option | Default | Description |
|---|---|---|
| `--force-overwrite` | off | Overwrite existing tool skills without prompting. |

## What It Does

For each specified agent, `goga connect` performs the following steps:

1. **Cleanup** -- Removes all existing `goga-*` subfolders from the agent's skills directory.
2. **Install commands** -- Copies goga command definitions to `<agent_dir>/commands/goga/`.
3. **Install skills** -- Copies goga skill packages to `<agent_dir>/skills/`.
4. **Download DSL spec** -- Fetches the CODEMANIFEST DSL specification from GitHub and writes it to `<agent_dir>/skills/goga-cell/dsl.md`.
5. **Discover tool packages** -- Scans installed Python packages with the `goga_tool_*` prefix via `importlib.metadata` and installs any that contain a valid `skills/<name>/SKILL.md` structure.

### Supported Agents

| Agent | Target Directory |
|---|---|
| `claude` | `~/.claude/` |

## Examples

Connect goga to Claude:

```bash
goga connect claude
```

Force overwrite of existing tool skills:

```bash
goga connect claude --force-overwrite
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All agents configured successfully |
| `1` | Error (unsupported agent, resources not found, download failure) |
