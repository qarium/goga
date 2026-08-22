# goga uninstall

Remove a goga-tool package from the current interpreter via pip, then re-sync every connected agent.

## Synopsis

```bash
goga uninstall <name> [--yes/-y] [--sudo] [--user NAME]
```

## Description

`goga uninstall` runs `pip uninstall -y goga-tool-<name>` on the current Python interpreter, then re-syncs every agent recorded in `~/.goga/connect.yml` using each agent's persisted `force_overwrite` setting.

Exactly one tool is removed per invocation — no bulk, empty, or local-path forms. The tool `name` is not validated before pip runs: an unknown package is skipped by pip with a WARNING and exit code 0.

The re-sync is the cleanup mechanism. Because tool skills and pipelines are installed centrally into `~/.goga/` and symlinked into each agent directory (see [`goga connect`](connect.md)), removing the package alone would leave orphaned artifacts behind. The post-removal re-sync recreates `~/.goga/skills/` and `~/.goga/pipelines/` from the packages that remain and rebuilds agent symlinks only for entries that still exist — the removed tool's skills and pipelines disappear from `~/.goga/` and from each agent's symlink tree.

## Confirmation

Before pip runs, the command asks:

```
Remove goga tool "<name>"? [Y/n]:
```

- **Enter** (empty input) continues the removal — the default answer is Y.
- **n** / **N** cancels: `Removal of goga tool "<name>" cancelled` is printed to stdout and the command exits `0`. pip is not invoked and nothing is cleaned.
- **EOF** (stdin ended) aborts with a non-zero exit code.
- `--yes` / `-y` skips the prompt entirely — the scripted/CI form. stdin is not read.

The `--yes`/`-y` flag skips only the goga-level confirmation prompt; pip's own `-y` is always passed.

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `name` (positional, required) | string | — | Tool name without the `goga-tool-` prefix; exactly one tool per invocation |
| `--yes`, `-y` | flag | off | Skip the removal confirmation prompt (both forms are aliases on the same option) |
| `--sudo` | flag | off | Prepend `sudo --preserve-env=HOME` to the pip command (system-Python installs requiring root) |
| `--user <name>` | string | -- | Resolve `~/.goga/` for this user via `pwd.getpwnam` — the home the post-removal re-sync targets |

## Sudo and user semantics

| Combination | pip invocation | `~/.goga/` resolution |
|---|---|---|
| (no flags) | `<python> -m pip uninstall -y goga-tool-<name>` | `Path.home()` |
| `--sudo` | `sudo --preserve-env=HOME <python> -m pip uninstall -y goga-tool-<name>` | `Path.home()` (HOME preserved) |
| `--user alice` | `<python> -m pip uninstall -y goga-tool-<name>` | `pwd.getpwnam("alice").pw_dir / ".goga"` |
| `--sudo --user alice` | `sudo --preserve-env=HOME <python> -m pip uninstall -y goga-tool-<name>` | `pwd.getpwnam("alice").pw_dir / ".goga"` (target_user wins) |

`--preserve-env=HOME` is mandatory under `--sudo`: without it sudo switches `$HOME` to `/root`, so the post-removal re-sync would read the wrong `connect.yml`.

`--sudo` applies to the pip invocation only — the re-sync never runs under sudo, against the preserved (or `--user`-resolved) home.

pip is always invoked via the `<python> -m pip` form (never the bare `pip` executable) to guarantee the correct interpreter.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Confirmation declined — cancellation message, no pip, no re-sync |
| `0` | pip succeeded and the re-sync succeeded (or the registry is missing/empty) |
| non-zero | pip failed (returns pip's exit code; the re-sync is not run) |
| non-zero | pip succeeded but the re-sync failed — a malformed or unreadable registry (`1`) or the first non-zero per-agent failure |
| `1` | Unknown `--user <name>` (`pwd.getpwnam` fails) — rejected before the confirmation prompt and pip; nothing is removed |
| non-zero | stdin ended before the prompt could be answered and `--yes`/`-y` was not given (abort) |

A "not installed" answer from pip (`Skipping ... as it is not installed`) is a WARNING with exit code 0 — a pip success by this contract: the re-sync runs and removes the orphaned artifacts, so the final exit code is the re-sync outcome. A missing `~/.goga/connect.yml` after a successful pip is a normal condition (no agents connected yet) and exits with code `0`.

## Examples

Remove a tool interactively (Enter confirms — the default is Y):

```bash
goga uninstall foo
```

Skip the confirmation — the scripted/CI form:

```bash
goga uninstall foo --yes
goga uninstall foo -y
```

Remove from a system-Python install requiring root (the re-sync runs without sudo against the preserved `$HOME`):

```bash
goga uninstall foo --sudo
```

Remove and re-sync another user's goga installation (run as an administrator):

```bash
goga uninstall foo --user alice
```

Combine both: pip under sudo, re-sync home from `--user`:

```bash
goga uninstall foo --sudo --user alice
```

## Notes

- `--sudo` and `--user` rely on `sudo` and `pwd.getpwnam` respectively and are unavailable on Windows; Windows users must omit both.
- `goga uninstall` never reads or writes `connect.yml` itself — [`goga connect`](connect.md) is the single writer of the registry, reached only through the shared re-sync routine.
- Removing a package by hand with plain pip leaves stale skills and pipelines in `~/.goga/` until the next re-sync runs; prefer `goga uninstall`.
