# goga upgrade

Upgrade the goga package (and optionally installed tool packages), then re-sync every connected agent.

## Synopsis

```bash
goga upgrade [--sudo] [--user NAME] [--tools]
```

## Description

`goga upgrade` runs `pip install goga -U` on the current Python interpreter, then re-syncs every agent recorded in `~/.goga/connect.yml` using each agent's persisted `force_overwrite` setting.

This is the supported way to move to a new goga release: because `goga connect` installs assets centrally into `~/.goga/` and symlinks them into each agent directory (see [`goga connect`](connect.md)), an upgrade must re-run that install and refresh the symlinks. `goga upgrade` does both in one command, driven by the registry that `goga connect` wrote when you first connected your agents.

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--sudo` | flag | off | Prepend `sudo --preserve-env=HOME` to the pip command (system-Python installs requiring root) |
| `--user <name>` | string | -- | Resolve `~/.goga/` for this user via `pwd.getpwnam` instead of `$HOME` |
| `--tools` | flag | off | Also upgrade discovered `goga_tool_*` packages |

## Sudo and user semantics

| Combination | pip invocation | `~/.goga/` resolution |
|---|---|---|
| (no flags) | `<python> -m pip install goga -U` | `Path.home()` |
| `--sudo` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `Path.home()` (HOME preserved) |
| `--user alice` | `<python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` |
| `--sudo --user alice` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` (target_user wins) |

`--preserve-env=HOME` is mandatory under `--sudo`: without it sudo switches `$HOME` to `/root`, so the post-upgrade re-sync would read the wrong `connect.yml`.

pip is always invoked via the `<python> -m pip` form (never the bare `pip` executable) to guarantee the correct interpreter.

## The connect.yml registry

`~/.goga/connect.yml` is written by `goga connect` and read by `goga upgrade`:

```yaml
agents:
  claude:
    force_overwrite: false
  codex:
    force_overwrite: true
```

For every agent listed, `goga upgrade` re-runs the central install and symlinks for that agent, forwarding the agent's own `force_overwrite` value — never a hardcoded default.

## Examples

Plain upgrade for the current user:

```bash
goga upgrade
```

Upgrade a system-Python install requiring root:

```bash
goga upgrade --sudo
```

Upgrade goga and all installed tool packages:

```bash
goga upgrade --tools
```

Re-sync another user's installation (run as an administrator):

```bash
goga upgrade --user alice
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Upgrade succeeded; all registered agents re-synced (or no `connect.yml` exists yet) |
| non-zero | pip failed (returns pip's exit code) |
| non-zero | One or more agents failed to re-sync (returns the first failure's exit code) |

A missing `~/.goga/connect.yml` after a successful pip is a normal condition (no agents connected yet) and exits with code `0`.

## Notes

- `--user` relies on `pwd.getpwnam` and is unavailable on Windows; Windows users must omit `--user`.
- `goga upgrade` never writes to `connect.yml` itself — `goga connect` is the single writer of the registry.
