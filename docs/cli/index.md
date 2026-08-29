# CLI Reference

Goga is a command-line tool built with [Click](https://click.palletsprojects.com/) for validating and managing CODEMANIFEST-based projects.

## Installation

```bash
pipx install goga
```

After installation, the `goga` command is available:

```bash
goga --help
```

You can also invoke it as a Python module:

```bash
python -m goga --help
```

## Commands

| Command | Description |
|---|---|
| [`goga init`](init.md) | Interactive project initialization |
| [`goga install`](install.md) | Install goga-tool packages into the current interpreter and re-sync connected agents |
| [`goga uninstall`](uninstall.md) | Remove a goga-tool package from the current interpreter and re-sync connected agents |
| [`goga lint`](lint.md) | Validate CODEMANIFEST files |
| [`goga build`](build.md) | Execute build plan via a ralph-loop |
| [`goga contract`](contract.md) | Compare CODEMANIFEST with implementation |
| [`goga config`](config.md) | Display configuration values |
| [`goga schema`](schema.md) | Generate JSON schema from project cells |
| [`goga connect`](connect.md) | Install goga skills for AI agents |
| [`goga upgrade`](upgrade.md) | Upgrade goga and re-sync connected agents |
| [`goga usages`](usages.md) | Sync cell-level usages from declared git dependencies and check their status against the remote |
| [`goga pipeline`](pipeline.md) | Run a goga pipeline, or inspect the available ones (`--list`, `--info`) |
| [`goga history`](history.md) | Work with the `.goga/history/` tree (`list`, `status`, `path`, `ensure`) |
| [`goga topics`](topics.md) | Work with the topics of one year (`status` board, `create`, `switch`) |
| [`goga tool`](tool.md) | Dynamic tool package invocation |

## Global Options

The root `goga` command is a Click group. It supports the standard Click `--help` flag:

```bash
goga --help
```

All subcommands also accept `--help` for inline usage information.

The group also carries a global `--version` / `-v` flag:

| Option | Description |
|---|---|
| `--version`, `-v` | Print the goga version installed on the host and exit |

```bash
goga --version
goga -v
```

The flag prints a bare version string (machine-readable, no decorations) to stdout and exits with code `0`:

```
1.2.3
```

The option belongs to the root group and is processed eagerly, before any subcommand dispatch — it is available on the root invocation only (`goga --version`), never as a subcommand option. Subcommands with their own same-named option are unaffected: `goga install --version <v>` still addresses the `install` command's value option, which the group flag does not intercept.

When the installed version cannot be determined (goga is not installed for the current interpreter, or its metadata is broken), the command fails cleanly: a one-line `Error: cannot determine the installed goga version (...)` message on stderr, exit code `1`, no traceback.

The flag takes no part in the host–image version check performed before container launches — that check is part of [`goga build`](build.md) and [`goga pipeline`](pipeline.md).
