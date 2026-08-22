# Upgrade API — goga/commands/upgrade

## Overview

The `goga upgrade` command performs a transactive upgrade: it runs `pip install goga -U` on the
current Python interpreter, then re-syncs all agents recorded in `~/.goga/connect.yml` using their
persisted `force_overwrite` settings. The post-upgrade re-sync is delegated to the shared
`resync_registered_agents` routine in `goga/connect`, the single owner of the registry and the
re-sync logic. The target goga version can optionally be constrained to the installed version's
line with the mutually exclusive `--patch` / `--minor` flags.

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

# Stay on the installed minor line (installed 1.2.3 -> goga~=1.2.0, latest 1.2.*)
goga upgrade --patch

# Move within the installed major line (installed 1.2.3 -> goga~=1.0, latest 1.*)
goga upgrade --minor

# Constrain goga, tools stay latest in the same single pip call
goga upgrade --patch --tools

# Combine with sudo/user freely
goga upgrade --patch --sudo --user alice
```

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `--sudo` | flag | False | Prepend `sudo --preserve-env=HOME` to the pip command |
| `--user <name>` | string | None | Resolve `~/.goga/` for this user via `pwd.getpwnam` |
| `--tools` | flag | False | Also upgrade installed `goga_tool_*` packages |
| `--patch` | flag | False | Constrain goga to the latest patch of the installed minor line (`~=X.Y.0`) |
| `--minor` | flag | False | Constrain goga to the latest release within the installed major line (`~=X.0`) |

## Relative Version Lines (--patch / --minor)

The base for both flags is the goga version installed in the current interpreter — read via
`host_goga_version` from the `goga/version` facade (the single reading point; it wraps
`importlib.metadata`), never the project's docker image tag and never the working directory.

| Installed version | Flag | pip identifier | Target line |
|---|---|---|---|
| `1.2.3` | `--patch` | `goga~=1.2.0` | latest `1.2.*` (minor unchanged) |
| `1.2.3` | `--minor` | `goga~=1.0` | latest `1.*` (major unchanged) |

Rich installed versions are truncated to their leading release segments, so development and
pre-release installations still resolve: `1.2.0rc1`, `1.2.0.post1`, `1.2.0+local`, `1.2.1.dev0`
all count as the `1.2` line. An installed version with no minor segment (e.g. `1`) fails loudly
under `--patch` instead of inventing a `.0`.

Errors (both exit non-zero BEFORE pip runs, so no partial upgrade and no re-sync happens):

- `goga upgrade --patch --minor` — the flags are mutually exclusive; user-facing error.
- goga is not installed in the current interpreter (e.g. run from a foreign venv) — the base is
  undeterminable; clear stderr error, no silent fallback to latest.

Without either flag the command behaves exactly as before: latest, and the installed version is
not read at all. Host/image correspondence stays manual by design: nothing warns or auto-fixes a
docker image tag pinned in `.goga/config.yml` — moving a project to a new minor line is an
explicit `--minor` (or flagless) upgrade plus a manual image-tag edit.

## Sudo and User Semantics

| Combination | pip invocation | `~/.goga/` resolution |
|---|---|---|
| (no flags) | `<python> -m pip install goga -U` | `Path.home()` |
| `--sudo` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `Path.home()` (HOME preserved) |
| `--user alice` | `<python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` |
| `--sudo --user alice` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` (target_user wins) |

`--preserve-env=HOME` is mandatory under `--sudo` — without it, sudo switches `$HOME` to `/root`
and the subsequent re-sync would read the wrong `connect.yml`.

When a line flag is active, the `pip install` target in the table carries the resolved specifier
(`goga~=X.Y.0` instead of bare `goga`); the flags are orthogonal to `--sudo`/`--user`.

## Python API

The semantic handler is `_upgrade` — it carries the contract signature (the Click
callback `upgrade` wraps it and owns option parsing; call the callback only through
Click). Direct Python calls (the form the test suite uses) go to the handler:

```python
from goga.commands.upgrade.upgrade import _upgrade

# Plain upgrade
exit_code = _upgrade()

# With options
exit_code = _upgrade(use_sudo=True, target_user="alice", include_tools=True)

# Stay on the installed minor line (e.g. installed 1.2.3 -> goga~=1.2.0)
exit_code = _upgrade(patch_line=True)
```

The post-upgrade re-sync is delegated to `goga.connect.resync_registered_agents(goga_home)`, which
reads the registry and re-applies `connect` per agent. The resolved `goga_home` (`Path.home()` or
`pwd.getpwnam(target_user).pw_dir / ".goga"`) is the only piece of registry context this command
supplies.

## Return Values

| Exit code | Condition |
|---|---|
| 0 | pip succeeded AND all agents in connect.yml re-synced successfully |
| non-zero | pip failed (returns pip's exit code) |
| non-zero | one or more agents failed to re-sync (returns first failure's exit code) |
| 0 | pip succeeded AND connect.yml is missing (no agents connected yet) |
| 1 (ClickException) | `--patch` and `--minor` combined — rejected before any action |
| 1 (ClickException) | a line flag is set but the installed version cannot be determined — rejected before pip |

## Side Effects

- Runs `pip install` as a subprocess (network/disk activity; may require root).
- Calls `resync_registered_agents(goga_home)`, which reads `~/.goga/connect.yml` and re-applies
  `connect()` once per listed agent (each with its own side effects: centralized asset installation,
  symlink creation, and `connect.yml` updates).
- During re-sync, emits a `Re-syncing <N> registered agent(s): <list>` banner to stderr, followed
  by a `Connecting agent: <name>` line per agent from `connect()`. A missing or empty registry is
  a silent no-op (no banner).

## Preconditions

- The current interpreter (`sys.executable`) must be the one where goga is installed.
- The user must have write access to the site-packages directory (or use `--sudo`).
- On Windows, `--user` is unavailable (`pwd.getpwnam` is Unix-only).
- With `--patch` or `--minor`, goga must be installed in the current interpreter (the base is
  read from its metadata).

## Anti-patterns

- Do not call `pip` as a bare subprocess — always use `<python> -m pip` to target the correct interpreter.
- Do not read or parse `connect.yml` directly — delegate activation to `resync_registered_agents`.
- Do not run `--sudo` without `--preserve-env=HOME` — the subsequent re-sync would target `/root/.goga`.
- Do not write to `connect.yml` from this command — `goga/connect` is the single writer.
- Do not pass both `--patch` and `--minor` — the pair is mutually exclusive.
- Do not expect an image-tag warning: host/image correspondence is manual by design.
- Do not expect `--tools` packages to inherit the version line — only the `goga` identifier is
  constrained; tools upgrade to latest in the same pip invocation.
