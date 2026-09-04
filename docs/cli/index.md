# CLI Reference

Goga is a command-line tool built with [Click](https://click.palletsprojects.com/) for validating and managing CODEMANIFEST-based projects.

This page is the **command cross-road**: every command of the root `goga` group, mapped to the functional domain that owns it. The full reference of each command — synopsis, options, behavior, exit codes — lives in its domain's **CLI** page under [Features](../features/index.md).

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

| Command | Domain | Description |
|---|---|---|
| [`goga init`](../features/init/cli.md) | [Init](../features/init/index.md) | Interactive project initialization |
| [`goga install`](../features/install/cli.md) | [Install](../features/install/index.md) | Install goga-tool packages into the current interpreter and re-sync connected agents |
| [`goga uninstall`](../features/install/uninstall.md) | [Install](../features/install/index.md) | Remove a goga-tool package from the current interpreter and re-sync connected agents |
| [`goga lint`](../features/lint/cli.md) | [Lint](../features/lint/index.md) | Validate CODEMANIFEST files |
| [`goga build`](../features/build/cli.md) | [Build](../features/build/index.md) | Execute build plan via a ralph-loop |
| [`goga contract`](../features/contract/cli.md) | [Contract](../features/contract/index.md) | Compare CODEMANIFEST with implementation |
| [`goga config`](../configuration/cli.md) | [Configuration](../configuration/index.md) | Display configuration values |
| [`goga schema`](../features/schema/cli.md) | [Schema](../features/schema/index.md) | Generate JSON schema from project cells |
| [`goga connect`](../features/connect/cli.md) | [Connect](../features/connect/index.md) | Install goga skills for AI agents |
| [`goga upgrade`](../features/upgrade/cli.md) | [Upgrade](../features/upgrade/index.md) | Upgrade goga and re-sync connected agents |
| [`goga usages`](../features/usages/cli.md) | [Usages](../features/usages/index.md) | Sync cell-level usages from declared git dependencies and check their status against the remote |
| [`goga pipeline`](../features/pipelines/cli.md) | [Pipelines](../features/pipelines/index.md) | Run a goga pipeline, or inspect the available ones (`--list`, `--info`) |
| [`goga history`](../features/history/cli.md) | [History](../features/history/index.md) | Work with the `.goga/history/` tree (`list`, `status`, `path`, `ensure`, `prune`) |
| [`goga topics`](../features/topics/cli.md) | [Topics](../features/topics/index.md) | Work with the topics of one year (`board`, `create`, `switch`, `delete`) |
| [`goga tool`](../features/tools/cli.md) | [Tools](../features/tools/index.md) | Dynamic tool package invocation |
| [`goga hooks`](../features/hooks/cli.md) | [Hooks](../features/hooks/index.md) | Inspect the hooks registered by installed tool packages |

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

The flag takes no part in the host–image version check performed before container launches — that check is part of [`goga build`](../features/build/cli.md) and [`goga pipeline`](../features/pipelines/cli.md).
