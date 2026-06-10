# Build API — goga/build

## Overview

The `goga.build` module orchestrates code builds through ralphex — handling
environment preparation, AI agent configuration, and build process execution.

## Usage

```python
from goga.config import load_config
from goga.build import build

# Load project configuration
config = load_config()

# Execute build
exit_code = build(
    plan="docs/plans/my-plan.md",
    config=config,
    cli_options={
        "dry_run": False,
        "worktree": True,
        "skip_finalize": False,
        "skip_manifest_check": False,
    }
)
```

## Parameters

- `plan` — path to the plan file (markdown)
- `config` — Config object loaded via `load_config`
- `cli_options` — options dictionary:
  - `dry_run` (bool) — print the command without executing
  - `worktree` (bool) — enable git worktree isolation mode
  - `skip_finalize` (bool) — skip the finalization step
  - `skip_manifest_check` (bool) — skip CODEMANIFEST commit verification
  - `session_timeout`, `idle_timeout`, `wait` (str) — timeout settings
  - `max_iterations`, `review_patience` (int) — iteration limits

## Supported agents

| Agent | Preconditions |
|-------|--------------|
| `claude` | Creates .claude/settings.json, .ralphex/claude-wrapper.sh, .ralphex/config |
| `codex` | Creates .ralphex/codex-wrapper.sh, .ralphex/config (executor=codex) |

## Return value

- `0` — success
- `1` — failure (uncommitted manifests, ralphex not found, build error)

## Side effects

- Removes `.ralphex/` before each run (cleanup)
- Creates or updates `.claude/settings.json` (when agent=claude)
- Creates `.ralphex/claude-wrapper.sh` and `.ralphex/config` (when agent=claude)
- Creates `.ralphex/codex-wrapper.sh` and `.ralphex/config` (when agent=codex)
- Copies prompts and agents into `.ralphex/`
- Spawns a subprocess (`ralphex`)

## Docker entry point

The module supports invocation via `python -m goga.build` for use inside Docker
containers through the `goga build` CLI command. In this mode, argparse handles
CLI option parsing and calls `build()` directly.

```bash
python -m goga.build plan.md --worktree --skip-manifest-check
```
