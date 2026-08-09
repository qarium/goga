# Install API — goga/commands/install

## Overview

The `goga install` command adds goga-tool packages into the current runtime
interpreter — the exact Python that runs goga — and then activates every
already-connected agent so the freshly installed skills and pipelines appear in
`~/.goga/` and in each agent's symlink tree.

The command operates in three modes:

- **Single mode** (`goga install <name>`): install one tool. `--version` resolves
  via the four-form grammar; the project config is ignored.
- **Bulk mode** (`goga install`): install every tool declared in the `tools`
  section of `.goga/config.yml`, in a single pip invocation, in YAML order.
- **Empty mode** (`goga install` with no `tools` section): no-op, prints
  `Nothing to install`, exits 0.

After a successful pip in single and bulk mode, the command runs a post-install
activation: it re-syncs every agent recorded in `~/.goga/connect.yml` (using each
agent's persisted `force_overwrite`) so the new tool's skills and pipelines are
linked into place. Pass `--no-connect` to skip activation — the command performs
the install only (useful in CI/Docker where a non-zero activation must not fail
the install). Empty mode performs neither pip nor activation.

## CLI Usage

### Single mode

```bash
# Plain install + activation — current user, no sudo, latest version
goga install foo

# Install a specific concrete version, then activate
goga install foo --version 1.0.1

# Short alias form — identical to the line above
goga install foo -v 1.0.1

# Install within a minor x-range (>=1.0.0, <1.1.0)
goga install foo --version 1.0.x

# Install with sudo (system-Python installs requiring root); activation runs
# without sudo against the preserved $HOME
goga install foo --sudo

# Install only — skip activation (escape-hatch for CI/Docker)
goga install foo --no-connect
```

### Bulk mode

Declare tools in `.goga/config.yml`:

```yaml
tools:
  viewer: latest        # → no specifier (pip selects newest)
  afm: 1.0.x            # → ~=1.0.0 (minor x-range)
  ralphex: 1.x          # → ~=1.0   (major x-range)
  go: 1.0.1             # → ==1.0.1 (concrete pin)
```

Then install and activate in a single command:

```bash
# Install every declared tool, then one activation pass over connect.yml
goga install

# Same, but pip under sudo with HOME preserved
goga install --sudo

# Bulk install only, no activation
goga install --no-connect
```

Bulk mode issues **exactly one** `pip install` call whose argv contains every
resolved `goga-tool-<name><spec>` in YAML order, followed by one activation pass.

### Empty mode

When the `tools` section is absent or empty in `.goga/config.yml`:

```bash
goga install
# stdout: Nothing to install
# exit code: 0
```

Neither pip nor activation is invoked.

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `name` (positional, optional) | string | None | Tool name without the goga-tool- / goga_tool_ prefix. When absent, bulk/empty mode runs from `config.tools`. |
| `--sudo` | flag | False | Run pip under `sudo --preserve-env=HOME` (Unix-only). Applies to pip only; activation never uses sudo. |
| `--version <form>`, `-v <form>` | string | None | Version form in the four-form grammar. Used by single mode only; ignored in bulk mode. Both forms are aliases on the same option — `-v 1.0.x` is identical to `--version 1.0.x`. |
| `--no-connect` | flag | False | Skip post-install activation. When set, the command performs the install only and the exit code is pip's. |

## Post-install Activation

When pip succeeds in single or bulk mode and `--no-connect` is not set, the
command activates every agent listed in `~/.goga/connect.yml`, each with its own
recorded `force_overwrite`. Activation is a local operation on `$HOME` and never
runs under `--sudo`. A missing or empty registry is a no-op that returns 0: the
tool is installed on the interpreter but not yet linked to any agent — connect an
agent later with `goga connect <agent>` and the tool will be picked up.

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

Rejected forms: operator-prefixed (`==1.0`, `>=1.0`), malformed (`1.x.0`), and
YAML-null `tools` values (e.g. `viewer:`) — each exits non-zero with a clear error.

## Python API

```python
from goga.commands.install.install import install, resolve_version

# Click commands are normally invoked via the CLI. For testing or programmatic
# invocation, use click.testing.CliRunner — see .goga/usages/cooks/click.md.
```

## Return Values

| Exit code | Condition |
|---|---|
| 0 | pip succeeded and activation succeeded (or registry missing/empty), or empty mode no-op |
| non-zero (pip) | pip failed — its returncode propagated verbatim; activation is not run |
| non-zero (activation) | pip succeeded but activation failed for one or more agents — the first non-zero per-agent failure is returned |
| 1 (`ClickException`) | `resolve_version` rejected a form, or `load_project_config` failed in bulk/empty mode |

With `--no-connect`, the exit code is always pip's (install-only semantics).

## Side Effects

- Runs pip as a subprocess of the current interpreter (network/disk activity;
  may require root under system-Python installs).
- The installed package(s) become importable in the running interpreter's
  environment.
- On success (and without `--no-connect`), activates every agent in
  `~/.goga/connect.yml`: recreates central assets, downloads `dsl.md`, creates
  agent symlinks, and refreshes pipelines — via the shared activation routine.
- During activation, emits a `Re-syncing <N> registered agent(s): <list>` banner
  to stderr followed by a `Connecting agent: <name>` line per agent. A missing
  or empty registry is a silent no-op (no banner).
- Bulk mode performs exactly one `subprocess.run` regardless of how many tools
  are declared.

## Preconditions

- The current interpreter (`sys.executable`) must be the one where goga is
  installed.
- The caller must have write access to the site-packages directory (or pass
  `--sudo`) and to `~/.goga/` for activation.
- For bulk mode, `.goga/config.yml` must exist and contain a `tools` section
  (otherwise empty mode runs — a no-op, not an error).
- On Windows, `--sudo` is unavailable (sudo is Unix-only).

## Anti-patterns

- Do not pass operator-prefixed forms (`--version '==1.0'`) — write
  `--version 1.0.1` or `--version 1.0.x`; the command emits the operator.
- Do not declare `tools:` values with YAML-null (`viewer:`) — write
  `viewer: latest`.
- Do not bypass the command and call `pip` with `sudo` directly without
  `--preserve-env=HOME`: post-install activation depends on reading the caller's
  `$HOME`.
- Do not expect `--version` to apply in bulk mode — it is ignored when `name`
  is absent.
- In CI/Docker where a transient activation failure must not fail the install,
  pass `--no-connect` to keep install-only exit semantics.
