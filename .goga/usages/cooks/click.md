# Building a Command Line Application with click

## Library

**click** — Command Line Interface Creation Kit

Installation: `pip install click`

**IMPORTANT** — the library must be added to the project dependencies.

## Application Structure

A CLI application is built from groups and commands. A group is a container for subcommands, a command is a terminal action.

```
cli.py          # root group (entry point)
__main__.py     # for invoking the application via python -m
commands/
    __init__.py
    cmd_one.py  # subcommand
    cmd_two.py  # subcommand
```

- The root group is located in the file specified as the entry point
- Each subcommand is a separate module
- Subcommands are registered via the `@<group>.command()` decorator

## Registering Commands in the Root Group

For a command to be included in the root group and become available in the CLI interface,
it must be imported and connected.

```python
from .commands.module import command


@click.group()
def app() -> None:
    pass


app.add_command(command)
```

**IMPORTANT** — every new command must go through the registration procedure in the root group.

## Basic Decorators

| Decorator              | Purpose                                    |
|------------------------|--------------------------------------------|
| `@click.group()`       | Group (container for subcommands)          |
| `@click.command()`     | Command (terminal action)                  |
| `@click.option()`      | Named parameter (`--name`)                 |
| `@click.argument()`    | Positional parameter                       |
| `@click.pass_context`  | Pass `Context` as the first argument       |
| `@click.pass_obj`      | Pass `ctx.obj` as the first argument       |

## Parameters

### Option — named parameters

```python
@click.option('--name', default='World', help='Имя для приветствия')
@click.option('--count', default=1, type=int, help='Количество повторений')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
@click.option('--level', type=click.Choice(['low', 'medium', 'high']))
@click.option('--config', type=click.Path(exists=True))
@click.option('--debug/--no-debug', default=False)
@click.option('--port', envvar='APP_PORT', default=8080, type=int)
```

- Always specify `help` for each `--option`
- Use `type` for validation (`int`, `click.Path`, `click.Choice`, `click.File`)
- Use `envvar` to read from environment variables

### Argument — positional parameters

```python
@click.argument('src')
@click.argument('dest', required=False)
@click.argument('files', nargs=-1, type=click.Path())
```

- Use only for obvious positional data (paths, file names)
- If the meaning of a parameter is not obvious — use `option`

## Passing State Between Commands

To pass data from the root group to subcommands, use `ctx.obj`:

```python
class AppState:
    def __init__(self, debug=False):
        self.debug = debug

@click.group()
@click.option('--debug/--no-debug', default=False)
@click.pass_context
def cli(ctx, debug):
    ctx.ensure_object(AppState)
    ctx.obj.debug = debug

@cli.command()
@click.pass_obj
def status(state):
    click.echo(f"Debug: {state.debug}")
```

- Create a state class instead of a `dict` — it provides type safety
- Use `ctx.ensure_object(Cls)` for safe initialization
- Use `click.make_pass_decorator(Cls)` to search for an object up the context hierarchy

## Groups and Nesting

Groups are nested within each other to create a command hierarchy:

```python
@click.group()
def cli():
    """Основная команда."""
    pass

@cli.group()
def db():
    """Команды базы данных."""
    pass

@db.command()
def migrate():
    click.echo('Миграция...')
```

Invocation: `cli db migrate`

- Each level is a `@click.group()`
- Terminal commands are registered at their own level: `@db.command()`

## Output and Error Handling

```python
# Output to stdout
click.echo('Сообщение')

# Colored output
click.secho('Ошибка!', fg='red', err=True)
click.secho('Успех!', fg='green')

# Prompt the user
name = click.prompt('Ваше имя')
confirm = click.confirm('Продолжить?')

# Exit with error code
raise click.ClickException('Что-то пошло не так')
sys.exit(1)
```

- Use `click.echo` instead of `print`
- Output errors via `click.secho(..., err=True)` or `raise click.ClickException`
- Do not use `print()` directly

## Testing CLI

Click provides the `CliRunner` utility for testing:

```python
from click.testing import CliRunner

def test_hello():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output
```

- Use `CliRunner` for all command tests
- Check `result.exit_code` and `result.output`
- For user input: `runner.invoke(cli, input='yes\n')`

## Anti-patterns

- Do not use `argparse` together with `click` in the same application
- Do not use `sys.exit()` inside commands — raise `click.ClickException` or return an error code via `ctx.exit(code)`
- Do not forget a docstring on every group and command — click generates help text from them
