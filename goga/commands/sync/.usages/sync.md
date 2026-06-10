# CLI Command: sync

## Purpose

CLI wrapper for the synchronization command. Delegates business logic to `goga/sync`. Copies .usages/ from a local path or git repository.

## Syntax

```
goga sync <source> [--token TOKEN] [--branch BRANCH]
```

## Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `source` | str | Path to directory (local) or git repository URL |

## Options

| Option | Type | Description |
|--------|------|-------------|
| `--token` | str | Authorization token for HTTPS git repository |
| `--branch` | str | Branch or tag for checkout when cloning |

## Exit code

- 0 — success
- 1 — error

## Examples

```bash
goga sync /path/to/external/project/goga
goga sync https://github.com/owner/repo
goga sync --token ghp_xxx https://github.com/owner/private-repo
goga sync --token glpat-xxx --branch v2.0 https://gitlab.com/org/repo
goga sync git@github.com:owner/repo.git
```
