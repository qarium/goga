# CLI Reference

Goga is a command-line tool built with [Click](https://click.palletsprojects.com/) for validating and managing CODEMANIFEST-based projects.

## Installation

```bash
pip install goga
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
| [`goga linter`](linter.md) | Validate CODEMANIFEST files |
| [`goga build`](build.md) | Execute build plan via ralphex |
| [`goga contract`](contract.md) | Compare CODEMANIFEST with implementation |
| [`goga config`](config.md) | Display configuration values |
| [`goga schema`](schema.md) | Generate JSON schema from project cells |
| [`goga sync`](sync.md) | Synchronize `.usages/` from external sources |
| [`goga connect`](connect.md) | Install goga skills for AI agents |
| [`goga tool`](tool.md) | Dynamic tool package invocation |

## Global Options

The root `goga` command is a Click group. It supports the standard Click `--help` flag:

```bash
goga --help
```

All subcommands also accept `--help` for inline usage information.
