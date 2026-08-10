# goga install

`goga install` adds goga-tool packages into the **current runtime interpreter** — the exact Python that runs goga. It targets the running interpreter's pip directly, so the install lands in the correct environment regardless of how goga was deployed (pipx venv, system Python, or any other).

After a successful pip in single or bulk mode, the command **activates** every agent already recorded in `~/.goga/connect.yml` (re-syncing each with its persisted `force_overwrite`) so the freshly installed tool's skills and pipelines appear in `~/.goga/` and in each connected agent's symlink tree. Pass `--no-connect` to skip activation and perform the install only (useful in CI/Docker where a transient activation failure must not fail the install). To execute an installed tool without going through an agent, run the dedicated tool-runner command.

## Modes

`goga install` branches on whether a tool name or `--local` path is given:

- **Single mode** (`goga install <name>`): install one tool, then activate. `--version` resolves through the four-form grammar; the project config is ignored.
- **Local mode** (`goga install --local <path>` / `-l <path>`): pip-install a local directory (no PyPI lookup). Mutually exclusive with `name`; `--version` is rejected. Activation follows the single/bulk rules.
- **Bulk mode** (`goga install`): install every tool declared in the `tools` section of `.goga/config.yml`, in a single pip invocation in YAML insertion order, then one activation pass.
- **Empty mode** (`goga install` with no `tools` section): no-op — prints `Nothing to install` and exits 0. pip is not invoked, and neither is activation.

## Usage

### Single mode

```bash
# Plain install — current user, latest version
goga install foo

# Install a specific concrete version
goga install foo --version 1.0.1

# Install within a minor x-range (>=1.0.0, <1.1.0)
goga install foo --version 1.0.x

# Install within a major x-range (>=1.0.0, <2.0.0)
goga install foo --version 1.x

# Pin to latest explicitly (same as omitting --version)
goga install foo --version latest

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

# Bulk install only, no activation
goga install --no-connect
```

Bulk mode issues **exactly one** `pip install` whose argv contains every resolved `goga-tool-<name><spec>` in YAML order, followed by one activation pass. This lets pip's resolver see the whole set together under `-U`, avoiding dependency drift between sequential installs.

### Local mode

Install a pip-installable local directory instead of resolving a package from PyPI:

```bash
# Install a tool from a local source checkout
goga install --local ./my-tool

# Short alias
goga install -l ./my-tool

# Local install only, no activation
goga install --local ./my-tool --no-connect

# Under sudo (pip only; activation never uses sudo)
goga install --local ./my-tool --sudo
```

Local mode issues a single `pip install <path> -U` (never `-e`/editable) so the directory is installed the same way a named package is. pip owns the missing-path error — there is no CLI-level existence check, so an invalid path surfaces as pip's own failure with its verbatim return code. The `name` positional and `--local` are mutually exclusive, and `--version` is rejected in local mode (both exit 1 with a clear message). The project config is **not** read in local mode; activation follows the single/bulk rules.

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `name` (positional, optional) | string | None | Tool name without the `goga-tool-` prefix. When absent, bulk/empty mode runs from `.goga/config.yml`. |
| `--sudo` | flag | False | Run pip under `sudo --preserve-env=HOME` (Unix-only). Applies to pip only; activation never uses sudo. Applies to both single and bulk modes. |
| `--version <form>`, `-v <form>` | string | None | Version form in the four-form grammar. Used by single mode only; ignored in bulk mode. Both forms are aliases on the same option — `-v 1.0.x` is identical to `--version 1.0.x`. |
| `--local <path>`, `-l <path>` | string | None | Path to a pip-installable local directory (local mode). Mutually exclusive with `name`; `--version` is rejected in local mode. |
| `--no-connect` | flag | False | Skip post-install agent activation. When set, the command performs the install only and the exit code is pip's. |

## Post-install activation

When pip succeeds in single or bulk mode and `--no-connect` is not set, the command activates every agent listed in `~/.goga/connect.yml`, each with its own recorded `force_overwrite`. Activation is a local operation on `$HOME` and **never** runs under `--sudo` — only pip honors `--sudo`. A missing or empty registry is a no-op that returns 0: the tool is installed on the interpreter but not yet linked to any agent. Connect an agent later with `goga connect <agent>` and the tool will be picked up on the next install/upgrade.

## Version form grammar

`goga install` emits the operator. The four accepted forms resolve to pip specifiers as follows:

| Form | Example | Resolved pip specifier | Semantics |
|---|---|---|---|
| Minor x-range | `1.0.x` | `~=1.0.0` | PEP 440 compatible release: `>=1.0.0,<1.1.0` |
| Major x-range | `1.x` | `~=1.0` | PEP 440 compatible release: `>=1.0.0,<2.0.0` |
| Concrete | `1.0.1` | `==1.0.1` | Exact pin |
| Latest marker | `latest` | *no specifier* | pip selects newest under `-U` |

The following forms are **rejected** with exit code 1 and a clear error:

| Rejected form | Reason |
|---|---|
| `==1.0`, `>=1.0`, `~=1.0`, `<2.0`, `!=1.0` | Operator-prefixed — write the grammar form instead; the command emits the operator |
| `foo`, `1.x.0`, `1.0.x.y` | Malformed — not in the four-form grammar |
| YAML-null `tools` value (e.g. `viewer:`) | Structural type error in the loader — write `latest` explicitly |

## Exit codes

| Exit code | Condition |
|---|---|
| 0 | pip succeeded and activation succeeded (or the registry is missing/empty), or empty mode no-op |
| non-zero (pip) | pip failed — its returncode propagated verbatim, with no translation; activation is not run |
| non-zero (activation) | pip succeeded but activation failed for one or more agents — the first non-zero per-agent failure is returned |
| 1 | a version form was rejected, `name` and `--local` were both given, `--version` was given with `--local`, `.goga/config.yml` could not be loaded in bulk/empty mode, or the pip/sudo executable could not start |

With `--no-connect`, the exit code is always pip's (install-only semantics).

## Notes

- The current interpreter (`sys.executable`) must be the one where goga is installed.
- The caller needs write access to the site-packages directory (or pass `--sudo`) and, for activation, to `~/.goga/`.
- For bulk mode, `.goga/config.yml` must exist and contain a `tools` section (otherwise empty mode runs — a no-op, not an error).
- On Windows, `--sudo` is unavailable (sudo is Unix-only).
- Do not bypass this command and call `pip` with `sudo` directly without `--preserve-env=HOME`: post-install activation depends on reading the caller's `$HOME`.
- In CI/Docker where a transient activation failure must not fail the install, pass `--no-connect` to keep install-only exit semantics.
