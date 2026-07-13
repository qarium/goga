# Install API — goga/commands/install

## Overview

The `goga install` command adds a goga-tool package into the current runtime interpreter —
the exact Python that runs goga. It targets the running interpreter's pip directly, which
makes the install land in the correct environment regardless of how goga was deployed
(pipx venv, system Python, or any other).

The command is install-only: it does not run the tool and does not touch goga's connection
configuration. To execute an installed tool, invoke the dedicated tool-runner command.

## CLI Usage

```bash
# Plain install — current user, no sudo
goga install foo

# Install with sudo (system-Python installs requiring root)
goga install foo --sudo

# Install a specific version (caller owns the operator — raw append)
goga install foo --version '==1.2.3'

# Install with a version range
goga install foo --version '>=1.0'

# Combined: sudo + specific version
goga install foo --sudo --version '==1.2.3'
```

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `name` (positional) | string | — | Tool name without the goga-tool- / goga_tool_ prefix |
| `--sudo` | flag | False | Run pip under `sudo --preserve-env=HOME` (Unix-only) |
| `--version <specifier>` | string | None | Version specifier appended RAW to the package identifier |

## Version Specifier Semantics

`--version` is a **raw-append** to the package identifier. The caller owns the operator:

| `--version` value | Resulting pip argument |
|---|---|
| (not set) | `goga-tool-foo -U` |
| `1.0` | `goga-tool-foo1.0 -U` (pip rejects — must write `==1.0`) |
| `==1.0` | `goga-tool-foo==1.0 -U` |
| `>=1.0` | `goga-tool-foo>=1.0 -U` |
| `<2.0` | `goga-tool-foo<2.0 -U` |

The command does NOT validate or modify the `--version` string. pip is the validation
authority — invalid specifiers surface as pip errors and the pip returncode is propagated
as the command exit code.

## Python API

```python
from goga.commands.install.install import install

# Plain install
exit_code = install("foo")

# With sudo (Unix-only)
exit_code = install("foo", use_sudo=True)

# With a version specifier (raw append — caller owns the operator)
exit_code = install("foo", version="==1.2.3")
```

## Return Values

| Exit code | Condition |
|---|---|
| 0 | pip succeeded |
| non-zero | pip failed (pip's returncode propagated as-is) |

## Side Effects

- Runs pip as a subprocess of the current interpreter (network/disk activity; may require
  root under system-Python installs).
- The installed package becomes importable in the running interpreter's environment.

## Preconditions

- The current interpreter (`sys.executable`) must be the one where goga is installed.
- The caller must have write access to the site-packages directory (or pass `--sudo`).
- On Windows, `--sudo` is unavailable (sudo is Unix-only).

## Anti-patterns

- Do not pass a bare version (`--version 1.0`) expecting it to resolve — the operator is
  caller-owned. Write `--version '==1.0'` explicitly.
- Do not invoke pip as a bare subprocess — always go through the running interpreter
  (`<python> -m pip`). The command enforces this invariant.
- Do not expect the command to run the tool after install — this API is install-only.
- Do not bypass the command and call `pip` with `sudo` directly without `--preserve-env=HOME`:
  post-install tool discovery depends on reading the caller's `$HOME`.
