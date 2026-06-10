# Connect API — goga/connect

## Overview

The `goga.connect` module installs goga skills and commands
into the configuration directory of one or more target AI agents.

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
- `force_overwrite` — allow overwriting existing skills from tool packages. Defaults to False

## Return Value

- `0` — success
- `1` — error (empty agent list, unsupported agent, resources not found, download failure)

## Side Effects

For each agent in the list:
- Removes goga-* subdirectories under <target>/skills/
- Copies goga/agent/commands/* → <target>/commands/goga/
- Copies goga/agent/skills/* → <target>/skills/
- Downloads dsl.md from GitHub and writes to <target>/skills/goga-cell/dsl.md
- Discovers Python packages with the `goga_tool_*` prefix via importlib.metadata
- Copies skills from discovered packages to <target>/skills/ with the `goga-tool-` prefix
- When `force_overwrite=False` — skips existing skills, logs warning
- When `force_overwrite=True` — overwrites existing skills

## Target Directories

| Agent  | Path       | Commands | Skills |
|--------|------------|----------|--------|
| claude | ~/.claude/ | Yes      | Yes    |
| codex  | ~/.codex/  | No       | Yes    |
| cursor | ~/.cursor/ | No       | Yes    |
