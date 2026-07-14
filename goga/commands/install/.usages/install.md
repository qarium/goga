# Install API — goga/commands/install

## Overview

The `goga install` command adds goga-tool packages into the current runtime
interpreter — the exact Python that runs goga. It targets the running
interpreter's pip directly, so the install lands in the correct environment
regardless of how goga was deployed (pipx venv, system Python, or any other).

The command operates in three modes:

- **Single mode** (`goga install <name>`): install one tool. `--version` resolves
  via the four-form grammar; the project config is ignored.
- **Bulk mode** (`goga install`): install every tool declared in the `tools`
  section of `.goga/config.yml`, in a single pip invocation, in YAML order.
- **Empty mode** (`goga install` with no `tools` section): no-op, prints
  `Nothing to install`, exits 0.

The command is install-only: it does not run the tool and does not touch goga's
connection configuration. To execute an installed tool, invoke the dedicated
tool-runner command.

## CLI Usage

### Single mode

```bash
# Plain install — current user, no sudo, latest version
goga install foo

# Install a specific concrete version
goga install foo --version 1.0.1

# Install within a minor x-range (>=1.0.0, <1.1.0)
goga install foo --version 1.0.x

# Install within a major x-range (>=1.0.0, <2.0.0)
goga install foo --version 1.x

# Pin to latest explicitly (same as omitting --version)
goga install foo --version latest

# Install with sudo (system-Python installs requiring root)
goga install foo --sudo

# Combined: sudo + version form
goga install foo --sudo --version 1.0.x
```

### Bulk mode

Declare tools in `.goga/config.yml`:

```yaml
tools:
  viewer: latest        # → no specifier (pip selects newest)
  afm: 1.0.x            # → ~=1.0.0 (minor x-range, >=1.0.0,<1.1.0)
  ralphex: 1.x          # → ~=1.0   (major x-range, >=1.0.0,<2.0.0)
  go: 1.0.1             # → ==1.0.1 (concrete pin)
```

Then install them all in a single pip invocation:

```bash
# Install every declared tool under the current user
goga install

# Same, but under sudo with HOME preserved
goga install --sudo
```

The bulk mode issues **exactly one** `pip install` call whose argv contains
every resolved `goga-tool-<name><spec>` in YAML order. This lets pip's resolver
see the whole set together under `-U`, avoiding dependency drift between
sequential installs.

### Empty mode

When the `tools` section is absent or empty in `.goga/config.yml`:

```bash
goga install
# stdout: Nothing to install
# exit code: 0
```

pip is not invoked.

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `name` (positional, optional) | string | None | Tool name without the goga-tool- / goga_tool_ prefix. When absent, bulk/empty mode runs from `config.tools`. |
| `--sudo` | flag | False | Run pip under `sudo --preserve-env=HOME` (Unix-only). Applies to both single and bulk modes. |
| `--version <form>` | string | None | Version form in the four-form grammar. Used by single mode only; ignored in bulk mode. |

## Version Form Grammar

`goga install` emits the operator. The four accepted forms resolve to pip
specifiers as follows:

| Form | Example | Resolved pip specifier | Semantics |
|---|---|---|---|
| Minor x-range | `1.0.x` | `~=1.0.0` | PEP 440 compatible release: `>=1.0.0,<1.1.0` |
| Major x-range | `1.x` | `~=1.0` | PEP 440 compatible release: `>=1.0.0,<2.0.0` |
| Concrete | `1.0.1` | `==1.0.1` | Exact pin |
| Latest marker | `latest` | *no specifier* | pip selects newest under `-U` |
| (absent `--version`) | — | *no specifier* | same as `latest` (single mode only) |

Major vs minor x-range is distinguished by **counting dots**: `1.x` has one dot
(major bound `~=1.0`, PEP 440 `<2.0`); `1.0.x` has two dots (minor bound
`~=1.0.0`, PEP 440 `<1.1.0`). The trailing `.0` in the minor case is what
drives the tighter upper bound — `~=1.0` alone has only a major bound.

The following forms are **rejected** with a non-zero exit code and a clear
error:

| Rejected form | Reason |
|---|---|
| `==1.0`, `>=1.0`, `~=1.0`, `<2.0`, `!=1.0` | Operator-prefixed — write the grammar form instead; the command emits the operator |
| `foo`, `1.x.0`, `1.0.x.y` | Malformed — not in the four-form grammar |
| YAML-null `tools` value (e.g. `viewer:`) | Structural type error in loader — write `latest` explicitly |

## Python API

### Click command

```python
from goga.commands.install.install import install

# Click commands are normally invoked via the CLI. For testing or programmatic
# invocation, use click.testing.CliRunner — see .goga/usages/cooks/click.md.
```

### resolve_version

```python
from goga.commands.install.install import resolve_version

# resolve_version is the sole owner of the four-form grammar
resolve_version("1.0.x")    # -> "~=1.0.0"  (PEP 440: >=1.0.0,<1.1.0)
resolve_version("1.x")      # -> "~=1.0"    (PEP 440: >=1.0.0,<2.0.0)
resolve_version("1.0.1")    # -> "==1.0.1"
resolve_version("1.0")      # -> "==1.0"    (concrete pin — N.M is valid)
resolve_version("latest")   # -> None
resolve_version(None)       # -> None  (for absent --version flag)
resolve_version("==1.0")    # raises ValueError
```

## Return Values

| Exit code | Condition |
|---|---|
| 0 | pip succeeded (single / bulk mode), or empty mode no-op |
| non-zero | pip failed (pip's returncode propagated as-is), or `resolve_version` rejected a version form |

## Side Effects

- Runs pip as a subprocess of the current interpreter (network/disk activity;
  may require root under system-Python installs).
- The installed package(s) become importable in the running interpreter's
  environment.
- Bulk mode performs exactly one `subprocess.run` regardless of how many tools
  are declared.

## Preconditions

- The current interpreter (`sys.executable`) must be the one where goga is
  installed.
- The caller must have write access to the site-packages directory (or pass
  `--sudo`).
- For bulk mode, `.goga/config.yml` must exist and contain a `tools` section
  (otherwise empty mode runs — a no-op, not an error).
- On Windows, `--sudo` is unavailable (sudo is Unix-only).

## Anti-patterns

- Do not pass operator-prefixed forms (`--version '==1.0'`) — write
  `--version 1.0.1` for a pin or `--version 1.0.x` for a range. The command
  emits the operator from the grammar form.
- Do not declare `tools:` values with YAML-null (`viewer:`) — the loader rejects
  null values structurally. Write `viewer: latest` to request "no specifier".
- Do not expect the command to run the tool after install — this API is
  install-only.
- Do not bypass the command and call `pip` with `sudo` directly without
  `--preserve-env=HOME`: post-install tool discovery depends on reading the
  caller's `$HOME`.
- Do not expect `--version` to apply in bulk mode — bulk mode reads
  `config.tools` exclusively; `--version` is ignored when `name` is absent.
