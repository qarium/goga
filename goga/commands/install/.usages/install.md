# Install API — goga/commands/install

## Overview

The `goga install` command adds goga-tool packages into the current runtime
interpreter — the exact Python that runs goga — then runs each installed
tool's optional post-install hook, and finally activates every
already-connected agent so the freshly installed skills and pipelines
appear in `~/.goga/` and in each agent's symlink tree.

The command operates in four modes:

- **Single mode** (`goga install <name>`): install one tool. `--version`
  resolves via the four-form grammar; the project config is ignored.
- **Bulk mode** (`goga install`): install every tool declared in the
  `tools` section of `.goga/config.yml`, in a single pip invocation, in
  YAML order.
- **Empty mode** (`goga install` with no `tools` section): no-op, prints
  `Nothing to install`, exits 0.
- **Local mode** (`goga install --local <path>` / `-l <path>`): pip-install
  a local directory; mutually exclusive with `name` and `--version`. The
  value is `<path>` or `<path>:<tool-name>`.

After a successful pip in single, local, and bulk mode the command runs
the post-install hooks (see below), then the activation re-sync of every
agent recorded in `~/.goga/connect.yml`. Pass `--no-connect` to skip the
activation only — the hooks still run.

## CLI Usage

### Single mode

    # Plain install + activation — current user, no sudo, latest version
    goga install foo

    # Install a specific concrete version, then activate
    goga install foo --version 1.0.1

    # Short alias form — identical to the line above
    goga install foo -v 1.0.1

    # Install within a minor x-range (>=1.0.0, <1.1.0)
    goga install foo --version 1.0.x

    # Install with sudo (system-Python installs requiring root); hooks and
    # activation run without sudo, the hook receives the current OS user
    # (SUDO_USER only when goga itself runs under sudo)
    goga install foo --sudo

    # Install only — skip activation; the post-install hook still runs
    goga install foo --no-connect

### Bulk mode

Declare tools in `.goga/config.yml`:

    tools:
      viewer: latest        # → no specifier (pip selects newest)
      afm: 1.0.x            # → ~=1.0.0 (minor x-range)
      ralphex: 1.x          # → ~=1.0   (major x-range)
      go: 1.0.1             # → ==1.0.1 (concrete pin)

Then install in a single command:

    # Install every declared tool, run each tool's hook in YAML order,
    # then one activation pass
    goga install

    # Same, but pip under sudo with HOME preserved
    goga install --sudo

    # Bulk install with hooks, no activation
    goga install --no-connect

Bulk mode issues **exactly one** `pip install` call whose argv contains
every resolved `goga-tool-<name><spec>` in YAML order; hooks run per tool
in the same order, then one activation pass.

### Local mode

Install a goga-tool from a local source directory instead of PyPI:

    # Install the package located at ./my-tool, then activation.
    # No hook runs — a warning names the way to enable it
    goga install --local ./my-tool

    # Same path with the :<tool-name> suffix — the post-install hook of
    # goga_tool_mytool runs after pip
    goga install --local ./my-tool:mytool

    # Short alias form — identical
    goga install -l ./my-tool:mytool

    # Local install only, no activation; the hook still runs (suffix present)
    goga install --local ./my-tool:mytool --no-connect

    # Local install under sudo (system-Python); hooks and activation run
    # without sudo, the hook receives the current OS user (SUDO_USER only
    # when goga itself runs under sudo)
    goga install --local ./my-tool:mytool --sudo

Local mode issues exactly one `pip install <path> -U` against the current
interpreter, then the hook of the suffixed tool (when given), then
activation by the same rules as single/bulk mode (suppressed by
`--no-connect`). Pip's return code is translated unchanged — a missing or
non-installable path surfaces as pip's own non-zero exit code.

Constraints:
- `name` and `--local` are mutually exclusive (`goga install foo --local
  ./x` exits 1).
- `--version` is rejected in local mode (`goga install --local ./x -v 1.0.1`
  exits 1) — versions apply to PyPI packages only.
- A malformed suffix (empty tool name, a path separator, an extra colon)
  exits 1 before any pip.
- Editable installs (`-e`) are not performed.

### Empty mode

When the `tools` section is absent or empty in `.goga/config.yml`:

    goga install
    # stdout: Nothing to install
    # exit code: 0

Neither pip, nor hooks, nor activation is invoked.

## Options

| Option | Type | Default | Purpose |
|---|---|---|---|
| `name` (positional, optional) | string | None | Tool name without the goga-tool- / goga_tool_ prefix. When absent, bulk/empty mode runs from `config.tools`. |
| `--sudo` | flag | False | Run pip under `sudo --preserve-env=HOME` (Unix-only). Applies to pip only; hooks and activation never use sudo. |
| `--version <form>`, `-v <form>` | string | None | Version form in the four-form grammar. Single mode only. Both forms are aliases on the same option — `-v 1.0.x` is identical to `--version 1.0.x`. |
| `--local <path>[:<tool-name>]`, `-l` | string | None | Pip-installable local directory, optionally followed by `:<tool-name>` — the name of the tool whose `install()` hook should run. Without the suffix no hook runs (a warning names the suffix as the way to enable it). `-l ./x:foo` is identical to `--local ./x:foo`. |
| `--no-connect` | flag | False | Skip the post-install activation re-sync only. Hooks still run after a successful pip. |

## Post-install Hooks

After a successful pip install (single, local with a `:<tool-name>`
suffix, and bulk), the command imports each installed tool's facade module
`goga_tool_<tool>` and calls its `install` callable when one exists:

- No facade module or no callable `install` → quiet skip (the hook is
  optional; existing tools without a hook install exactly as before).
- The hook's signature declares a keyword-capable parameter `user` → it is
  called as `install(user=<initiating user>)`; otherwise it is called with
  no arguments.
- The initiating user is `SUDO_USER` when goga itself runs under sudo
  (`sudo goga install ...`), otherwise the current OS user — the actual
  initiator, not root. The `--sudo` flag runs only pip under sudo and does
  not set `SUDO_USER`. What the
  tool does with the string (chown, per-user config, git identity) is the
  tool's business; goga does not re-execute the hook as that user.
- Hook failure (an exception from the hook body): non-zero exit with the
  tool name and the hook message; the pip package stays installed (no
  rollback); the activation re-sync does not run. In bulk mode the
  sequence stops at the first failing hook — the remaining tools' hooks
  are not called.
- Hooks run before the activation re-sync; `--no-connect` suppresses only
  the re-sync.
- Hooks are not run by `uninstall` or `upgrade`.

A tool with a hook looks like this:

    # inside the goga_tool_mytool facade package
    def install(user: str | None = None) -> None:
        ...  # tool-owned setup; `user` receives the initiating user
             # only when the parameter is declared keyword-capable

## Post-install Activation

When pip and hooks succeed in single, local, or bulk mode and
`--no-connect` is not set, the command activates every agent listed in
`~/.goga/connect.yml`, each with its own recorded `force_overwrite`.
Activation is a local operation on `$HOME` and never runs under `--sudo`.
A missing or empty registry is a no-op that returns 0: the tool is
installed on the interpreter but not yet linked to any agent — connect an
agent later with `goga connect <agent>` and the tool will be picked up.

## Version Form Grammar

Version forms are resolved by the shared version-resolution routine;
`goga install` emits the operator. The four accepted forms resolve to pip
specifiers as follows:

| Form | Example | Resolved pip specifier | Semantics |
|---|---|---|---|
| Minor x-range | `1.0.x` | `~=1.0.0` | PEP 440 compatible release: `>=1.0.0,<1.1.0` |
| Major x-range | `1.x` | `~=1.0` | PEP 440 compatible release: `>=1.0.0,<2.0.0` |
| Concrete | `1.0.1` | `==1.0.1` | Exact pin |
| Latest marker | `latest` | *no specifier* | pip selects newest under `-U` |
| (absent `--version`) | — | *no specifier* | same as `latest` (single mode only) |

Rejected forms: operator-prefixed (`==1.0`, `>=1.0`), malformed (`1.x.0`),
and YAML-null `tools` values (e.g. `viewer:`) — each exits non-zero with a
clear error.

## Python API

    from goga.commands.install.install import install

    # Click commands are normally invoked via the CLI. For testing or
    # programmatic invocation, use click.testing.CliRunner to drive the
    # command in-process.

## Return Values

| Exit code | Condition |
|---|---|
| 0 | pip succeeded, all hooks succeeded (or none applied), and activation succeeded (or registry missing/empty, or `--no-connect`); or empty mode no-op |
| non-zero (pip) | pip failed — its returncode propagated verbatim; no hooks, no activation |
| non-zero (hook) | pip succeeded but a hook raised — tool name + message; no rollback, no activation; bulk stops at the first failing hook |
| non-zero (activation) | pip and hooks succeeded but activation failed for one or more agents — the first non-zero per-agent failure is returned |
| 1 (`ClickException`) | a version form was rejected; `load_project_config` failed in bulk/empty mode; `name` + `--local` combined; `--version` in local mode; malformed `--local` suffix (empty tool name, path separator, extra colon) |

## Side Effects

- Runs pip as a subprocess of the current interpreter (network/disk
  activity; may require root under system-Python installs).
- Runs each installed tool's `install()` hook — arbitrary code provided by
  the installed package, with the trust level of any pip package.
- On success (and without `--no-connect`), activates every agent in
  `~/.goga/connect.yml` via the shared activation routine.
- A local install without the `:<tool-name>` suffix logs a warning that no
  hook will run and how to enable it.

## Preconditions

- The current interpreter (`sys.executable`) must be the one where goga is
  installed.
- The caller must have write access to the site-packages directory (or
  pass `--sudo`) and to `~/.goga/` for activation.
- For bulk mode, `.goga/config.yml` must exist and contain a `tools`
  section (otherwise empty mode runs — a no-op, not an error).
- On Windows, `--sudo` is unavailable (sudo is Unix-only).

## Anti-patterns

- Do not pass operator-prefixed forms (`--version '==1.0'`) — write
  `--version 1.0.1` or `--version 1.0.x`; the command emits the operator.
- Do not declare `tools:` values with YAML-null (`viewer:`) — write
  `viewer: latest`.
- Do not bypass the command and call `pip` with `sudo` directly without
  `--preserve-env=HOME`: the hook's initiating-user resolution and the
  post-install activation depend on the caller's `$HOME`.
- Do not expect `--version` to apply in bulk mode — it is ignored when
  `name` is absent.
- Do not expect a hook for a local install without the suffix — goga does
  not guess the tool name from the path; pass
  `--local ./my-tool:mytool` explicitly.
- Do not expect `--no-connect` to suppress hooks — it suppresses the
  activation re-sync only.
- Do not rely on a pip rollback after a hook failure — the package stays
  installed; fix the tool or uninstall it.
- In CI/Docker where a transient activation failure must not fail the
  install, pass `--no-connect` (hooks still gate the exit code).
