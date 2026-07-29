# CLI Command: connect

## Purpose

CLI wrapper for the connect command. Parses click arguments and delegates business logic to `goga/connect`.

## Syntax

```
goga connect <agent> [<agent> ...] [--force-overwrite]
```

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `agents` | tuple[str, ...] | Yes | One or more target AI agents |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--force-overwrite` | flag | False | Overwrite existing skills when installing from tool packages |

## Exit code

- 0 — success
- 1 — error

## Examples

```bash
goga connect claude
goga connect codex
goga connect cursor
goga connect opencode
goga connect qwen
goga connect claude codex cursor
goga connect claude codex cursor opencode
goga connect claude codex cursor opencode qwen
goga connect claude --force-overwrite
```
