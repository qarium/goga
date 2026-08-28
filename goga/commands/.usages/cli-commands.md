# CLI Commands — goga/commands facade

The `goga.commands` package is a facade that re-exports 14 CLI commands. Each command is a `click.Command` registered in a click group. Each subcell is an independent Python package (`goga/commands/<name>/`) with implementation in `<name>.py` and re-export through `__init__.py`.

## Import

All commands are available from the facade in a single line:

```python
from goga.commands import (
    lint,
    build,
    connect,
    schema,
    contract,
    config,
    usages,
    tool,
    init,
    pipeline,
    upgrade,
    install,
    uninstall,
    history,
)
```

Each command is available from its subcell (via `__init__.py` re-export):

```python
from goga.commands.lint import lint
from goga.commands.build import build
from goga.commands.connect import connect
from goga.commands.schema import schema
from goga.commands.contract import contract
from goga.commands.config import config
from goga.commands.usages import usages
from goga.commands.tool import tool
from goga.commands.init import init
from goga.commands.pipeline import pipeline
from goga.commands.upgrade import upgrade
from goga.commands.install import install
from goga.commands.install import uninstall
from goga.commands.history import history
```

## Registration in click group

```python
import click

from goga.commands import (
    lint,
    build,
    connect,
    schema,
    contract,
    config,
    usages,
    tool,
    init,
    pipeline,
    upgrade,
    install,
    uninstall,
    history,
)


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(lint)
app.add_command(build)
app.add_command(connect)
app.add_command(schema)
app.add_command(contract)
app.add_command(config)
app.add_command(usages)
app.add_command(tool)
app.add_command(init)
app.add_command(pipeline)
app.add_command(upgrade)
app.add_command(install)
app.add_command(uninstall)
app.add_command(history)
```

## Testing with CliRunner

```python
from click.testing import CliRunner
from goga.commands.lint import lint


def test_example():
    runner = CliRunner()
    result = runner.invoke(lint, ["."])
    assert result.exit_code in (0, 1)
```

## Command list

| Command     | Subcell                   | Purpose                              |
|-------------|---------------------------|--------------------------------------|
| `lint`      | `goga/commands/lint/`     | CODEMANIFEST file validation         |
| `build`     | `goga/commands/build/`    | Build via ralphex                    |
| `connect`   | `goga/commands/connect/`  | Connect goga skills                  |
| `schema`    | `goga/commands/schema/`   | Project JSON schema                  |
| `contract`  | `goga/commands/contract/` | Compare contract with implementation |
| `config`    | `goga/commands/config/`   | Output configuration values          |
| `usages`    | `goga/commands/usages/`   | Synchronize cell-level usages        |
| `tool`      | `goga/commands/tool/`     | Run tool commands                    |
| `init`      | `goga/commands/init/`     | Initialize goga project              |
| `pipeline`  | `goga/commands/pipeline/` | Run a goga pipeline (or list them)   |
| `upgrade`   | `goga/commands/upgrade/`  | Upgrade goga and re-sync agents      |
| `install`   | `goga/commands/install/`  | Install a goga_tool_* package        |
| `uninstall` | `goga/commands/install/`  | Remove a goga_tool_* package         |
| `history`   | `goga/commands/history/`  | Work with the .goga/history/ tree    |
