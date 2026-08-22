# Uninstall API — goga/commands/install

## Overview

The `goga uninstall` command removes one goga-tool package from the current
runtime interpreter — the exact Python that runs goga — and then re-syncs
every connected agent so the removed tool's skills and pipelines disappear
from `~/.goga/` and from each agent's symlink tree.

The command asks for confirmation before touching pip:

```
Remove goga tool "<tool>"? [Y/n]
```

Enter (empty input) continues the removal — the default answer is Y. An
explicit `n` cancels: a message is printed to stdout and the command exits 0;
pip is not invoked and nothing is cleaned. `--yes` (short `-y`) skips the
prompt for scripts and CI.

After a successful pip uninstall, the post-removal re-sync runs over
`~/.goga/connect.yml` (each agent with its persisted `force_overwrite`).
The re-sync is the cleanup mechanism: the removed tool's goga-tool-<tool>
skills and <tool>:*.yml pipelines disappear, and agent symlinks are recreated
only for entries that still exist.

## CLI Usage

```bash
# Remove one tool (interactive confirmation, default Y)
goga uninstall foo

# Skip the confirmation — the scripted/CI form
goga uninstall foo --yes
goga uninstall foo -y

# Remove under sudo (system-Python installs requiring root); the re-sync
# runs without sudo against the preserved $HOME
goga uninstall foo --sudo

# Remove and re-sync another user's goga installation
goga uninstall foo --user alice

# Combined: pip under sudo, re-sync home from --user
goga uninstall foo --sudo --user alice
```

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `name` (positional, required) | string | — | Tool name without the goga-tool- / goga_tool_ prefix. Exactly one tool per invocation. |
| `--yes`, `-y` | flag | False | Skip the confirmation prompt. Both forms are aliases on the same option — `-y` is identical to `--yes`. |
| `--sudo` | flag | False | Run pip under `sudo --preserve-env=HOME` (Unix-only). Applies to pip only; the re-sync never uses sudo. |
| `--user <name>` | string | None | Resolve `~/.goga/` for this user via `pwd.getpwnam` — the home the post-removal re-sync targets. |

## Sudo and User Semantics

| Combination | pip invocation | `~/.goga/` resolution |
|---|---|---|
| (no flags) | `<python> -m pip uninstall -y goga-tool-<tool>` | `Path.home()` |
| `--sudo` | `sudo --preserve-env=HOME <python> -m pip uninstall -y goga-tool-<tool>` | `Path.home()` (HOME preserved) |
| `--user alice` | `<python> -m pip uninstall -y goga-tool-<tool>` | `pwd.getpwnam("alice").pw_dir / ".goga"` |
| `--sudo --user alice` | `sudo --preserve-env=HOME <python> -m pip uninstall -y goga-tool-<tool>` | `pwd.getpwnam("alice").pw_dir / ".goga"` (target user wins) |

`--preserve-env=HOME` is mandatory under `--sudo` — without it, sudo switches
`$HOME` to `/root` and the subsequent re-sync would read the wrong registry.

## Return Values

| Exit code | Condition |
|---|---|
| 0 | confirmation declined — cancellation message, no pip, no re-sync |
| 0 | pip succeeded AND the re-sync succeeded (or the registry is missing/empty) |
| non-zero (pip) | pip failed — its return code propagated verbatim; the re-sync is not run |
| non-zero (re-sync) | pip succeeded but the re-sync failed — a malformed or unreadable registry (1) or the first non-zero per-agent failure |
| non-zero (abort) | stdin ended before the prompt could be answered and `--yes`/`-y` was not given |
| 1 | unknown `--user <name>` (`pwd.getpwnam` fails) — rejected before the confirmation prompt and pip; nothing is removed |

A "not installed" answer from pip (Skipping ... as it is not installed) is a
WARNING with exit code 0 — a pip success by this contract: the re-sync runs
and removes the orphaned artifacts, so the final exit code is the re-sync
outcome (0 unless an agent fails). The `--yes`/`-y` flag skips only the
goga-level confirmation prompt; pip's own -y is always passed.

## Side Effects

- Runs pip as a subprocess of the current interpreter (disk activity; may
  require root under system-Python installs).
- On pip success, re-syncs every agent in `~/.goga/connect.yml`: recreates
  central assets, downloads dsl.md, recreates `~/.goga/pipelines/` from the
  packages that remain, and rebuilds agent symlinks — via the shared
  activation routine.
- During the re-sync, emits a `Re-syncing <N> registered agent(s): <list>`
  banner to stderr followed by a `Connecting agent: <name>` line per agent.
  A missing or empty registry is a silent no-op (no banner).
- Removing a package by hand with pip leaves stale skills and pipelines in
  `~/.goga/` until the next re-sync runs.

## Preconditions

- The current interpreter (`sys.executable`) must be the one where goga is
  installed.
- The caller must have write access to the site-packages directory (or pass
  `--sudo`) and to the target `~/.goga/` for the re-sync.
- The tool name is not validated before pip runs — an unknown package is
  skipped by pip with a WARNING and exit code 0; the post-removal re-sync
  then cleans its orphaned artifacts.
- On Windows, `--sudo` and `--user` are unavailable (Unix-only).

## Python API

```python
from goga.commands.install.uninstall import uninstall

# Click commands are normally invoked via the CLI. For testing or programmatic
# invocation, use click.testing.CliRunner — drive the confirmation with
# input="y\n" / input="n\n", or pass ["--yes", ...] to skip it.
```
