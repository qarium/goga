# goga upgrade

Upgrade the goga package (and optionally installed tool packages), then re-sync every connected agent.

## Synopsis

```bash
goga upgrade [--sudo] [--user NAME] [--tools] [--patch | --minor]
```

## Description

`goga upgrade` runs `pip install goga -U` on the current Python interpreter, then re-syncs every agent recorded in `~/.goga/connect.yml` using each agent's persisted `force_overwrite` setting.

This is the supported way to move to a new goga release: because `goga connect` installs assets centrally into `~/.goga/` and symlinks them into each agent directory (see [`goga connect`](../connect/cli.md)), an upgrade must re-run that install and refresh the symlinks. `goga upgrade` does both in one command, driven by the registry that `goga connect` wrote when you first connected your agents.

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--sudo` | flag | off | Prepend `sudo --preserve-env=HOME` to the pip command (system-Python installs requiring root) |
| `--user <name>` | string | — | Resolve `~/.goga/` for this user via `pwd.getpwnam` instead of `$HOME` |
| `--tools` | flag | off | Also upgrade discovered `goga_tool_*` packages |
| `--patch` | flag | off | Constrain goga to the latest patch of the installed minor line (`~=X.Y.0`) |
| `--minor` | flag | off | Constrain goga to the latest release within the installed major line (`~=X.0`) |

## Sudo and user semantics

| Combination | pip invocation | `~/.goga/` resolution |
|---|---|---|
| (no flags) | `<python> -m pip install goga -U` | `Path.home()` |
| `--sudo` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `Path.home()` (HOME preserved) |
| `--user alice` | `<python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` |
| `--sudo --user alice` | `sudo --preserve-env=HOME <python> -m pip install goga -U` | `pwd.getpwnam("alice").pw_dir / ".goga"` (`--user` wins) |

`--preserve-env=HOME` is mandatory under `--sudo`: without it sudo switches `$HOME` to `/root`, so the post-upgrade re-sync would read the wrong `connect.yml`.

pip is always invoked via the `<python> -m pip` form (never the bare `pip` executable) to guarantee the correct interpreter.

## Relative version lines (--patch / --minor)

By default `goga upgrade` installs the latest released goga (`pip install goga -U`). The line flags constrain that upgrade to stay within the line of the currently installed version:

| Installed version | Flag | pip identifier |
|---|---|---|
| `1.2.3` | `--patch` | `goga~=1.2.0` (latest patch of the 1.2 line) |
| `1.2.3` | `--minor` | `goga~=1.0` (latest release of the 1.x line) |

- The line base is read from the current interpreter's `importlib.metadata` — not from the container image tag and not from the working directory. Whatever goga the invoked interpreter has installed defines the line.
- Rich version bases are truncated to their release segments: an installed `1.2.1.dev0` (likewise `1.2.0rc1`, `1.2.0.post1`, `1.2.0+local`) still resolves to the 1.2 line — `goga~=1.2.0` under `--patch`, `goga~=1.0` under `--minor`.
- `--patch` requires the installed version to carry a minor segment: an installed major-only version (e.g. `2`) exits 1 with `cannot resolve the version line` — no `.0` minor is invented. `--minor` works from a major-only base (`2` → `goga~=2.0`).
- Both flags are validated before pip runs: combining `--patch --minor` exits 1 with a mutual-exclusion error, and an installed version that cannot be read in this interpreter exits 1 — there is no fallback to latest.
- With `--tools`, the constraint applies only to the goga identifier; discovered `goga_tool_*` packages are upgraded unconstrained in the same pip invocation.

## The connect.yml registry

`~/.goga/connect.yml` is written by `goga connect` and read by `goga install`, `goga upgrade`, and [`goga uninstall`](../install/uninstall.md) (via the shared re-sync routine):

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

Stay on the installed minor line (with `1.2.3` installed, upgrade to the latest `1.2.x`):

```bash
goga upgrade --patch
```

Move to the latest release within the installed major line (with `1.2.3` installed, upgrade to the latest `1.x`):

```bash
goga upgrade --minor
```

Constrain goga to its line while upgrading tool packages freely:

```bash
goga upgrade --patch --tools
```

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Upgrade succeeded; all registered agents re-synced (or no `connect.yml` exists yet) |
| non-zero | pip failed (returns pip's exit code) |
| non-zero | One or more agents failed to re-sync (returns the first failure's exit code) |
| `1` | Unknown `--user <name>` (`pwd.getpwnam` fails) — pip has already run; the re-sync is skipped |
| `1` | `--patch` and `--minor` combined (ClickException — rejected before pip runs, no side effects) |
| `1` | Installed goga version unreadable in this interpreter under `--patch`/`--minor` (ClickException — rejected before pip runs, no fallback to latest) |
| `1` | Installed goga version readable but its line unresolvable — e.g. a major-only installed version under `--patch` (ClickException — rejected before pip runs, no side effects) |

A missing `~/.goga/connect.yml` after a successful pip is a normal condition (no agents connected yet) and exits with code `0`.

## Notes

- `--user` relies on `pwd.getpwnam` and is unavailable on Windows; Windows users must omit `--user`.
- `goga upgrade` never writes to `connect.yml` itself — `goga connect` is the single writer of the registry.
- Host/image correspondence is manual by design: the image tag in `.goga/config.yml` is neither checked nor edited — moving to a new minor line is an explicit `--minor` (or flagless) upgrade plus a manual tag edit.
