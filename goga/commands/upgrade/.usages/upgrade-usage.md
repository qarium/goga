# Upgrade API — goga/commands/upgrade

## Overview

The `goga upgrade` command performs a transactive upgrade: it runs `pip install goga -U` on the
current Python interpreter, then re-syncs all agents recorded in `~/.goga/connect.yml` using their
persisted `force_overwrite` settings. This replaces the manual `goga post-install` workflow with a
single command that handles both the package upgrade and the agent re-sync.

## CLI Usage

```bash
# Plain upgrade — current user, no sudo
goga upgrade

# Upgrade with sudo (system-Python installs requiring root)
goga upgrade --sudo

# Re-sync another user's goga installation
goga upgrade --user alice

# Upgrade goga AND all installed goga_tool_* packages
goga upgrade --tools

# Combined: sudo + target user + tool packages
goga upgrade --sudo --user alice --tools
```

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `--sudo` | flag | False | Prepend `sudo --preserve-env=HOME` to the pip command |
| `--user <name>` | string | None | Resolve `~/.goga/` for this user via `pwd.getpwnam` |
| `--tools` | flag | False | Also upgrade installed `goga_tool_*` packages |

## Sudo and User Semantics

| Combination | pip invocation | `~/.goga/` resolution |
|---|---|---|
| (no flags) | `<python> -m pip install goga -U` | `Path.home()` |
| `--sudo` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `Path.home()` (HOME preserved) |
| `--user alice` | `<python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` |
| `--sudo --user alice` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` (target_user wins) |

`--preserve-env=HOME` is mandatory under `--sudo` — without it, sudo switches `$HOME` to `/root`
and the subsequent re-sync would read the wrong `connect.yml`.

## Python API

```python
from goga.commands.upgrade.upgrade import upgrade

# Plain upgrade
exit_code = upgrade()

# With options
exit_code = upgrade(use_sudo=True, target_user="alice", include_tools=True)
```

## Return Values

| Exit code | Condition |
|---|---|
| 0 | pip succeeded AND all agents in connect.yml re-synced successfully |
| non-zero | pip failed (returns pip's exit code) |
| non-zero | one or more agents failed to re-sync (returns first failure's exit code) |
| 0 | pip succeeded AND connect.yml is missing (no agents connected yet) |

## Side Effects

- Runs `pip install` as a subprocess (network/disk activity; may require root).
- Reads `~/.goga/connect.yml`.
- Calls `connect()` once per agent listed in the registry (each call has its own side effects,
  including centralized asset installation, symlink creation, and `connect.yml` updates).

## Preconditions

- The current interpreter (`sys.executable`) must be the one where goga is installed.
- The user must have write access to the site-packages directory (or use `--sudo`).
- On Windows, `--user` is unavailable (`pwd.getpwnam` is Unix-only).

## Anti-patterns

- Do not call `pip` as a bare subprocess — always use `<python> -m pip` to target the correct interpreter.
- Do not hardcode `force_overwrite=True` — read the per-agent value from `connect.yml`.
- Do not run `--sudo` without `--preserve-env=HOME` — the subsequent re-sync would target `/root/.goga`.
- Do not write to `connect.yml` from this command — `goga/connect` is the single writer.
