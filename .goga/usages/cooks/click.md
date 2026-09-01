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

### Option — repeatable parameters

```python
@click.option('--status', '-s', multiple=True, help='Фильтр по статусу (повторяемый)')
def status(status: tuple[str, ...]) -> None:
    for name in status:
        ...
```

- An option with `multiple=True` may be passed several times; click collects the values into a tuple in passing order (`-s defined -s discovered` → `("defined", "discovered")`)
- The parameter value is a tuple; no passes yield an empty tuple `()`, not `None`
- Check "option not passed" by testing the tuple for emptiness, never against `None`
- A long and a short form on one option (`--status`/`-s`) behave like any other option

## Passing State Between Commands

To pass data from the root group to subcommands, use `ctx.obj`:

```python
class AppState:
    def __init__(self, debug=False):
        self.debug = debug


@click.group()
@click.option("--debug/--no-debug", default=False)
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
    click.echo("Миграция...")
```

Invocation: `cli db migrate`

- Each level is a `@click.group()`
- Terminal commands are registered at their own level: `@db.command()`

## Output and Error Handling

```python
# Output to stdout
click.echo("Сообщение")

# Colored output
click.secho("Ошибка!", fg="red", err=True)
click.secho("Успех!", fg="green")

# Prompt the user
name = click.prompt("Ваше имя")
confirm = click.confirm("Продолжить?")

# Exit with error code
raise click.ClickException("Что-то пошло не так")
sys.exit(1)
```

- Use `click.echo` instead of `print`
- Output errors via `click.secho(..., err=True)` or `raise click.ClickException`
- Do not use `print()` directly

## Colored Output and NO_COLOR

- `click.echo` / `click.secho` strip ANSI codes themselves when the output stream is not a TTY (a pipe or redirect receives plain text) — no manual `isatty()` check is needed for that case
- click does NOT honor the `NO_COLOR` environment variable: check it explicitly and, when it is set to a non-empty value, do not pass a color to `secho` (the no-color.org convention: present and non-empty — color is disabled always, even in a TTY)

## Testing CLI

Click provides the `CliRunner` utility for testing:

```python
from click.testing import CliRunner


def test_hello():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output
```

- Use `CliRunner` for all command tests
- Check `result.exit_code` and `result.output`
- For user input: `runner.invoke(cli, input='yes\n')`

## Interactive Multi-Line Entry

A multi-line text value (paragraphs included) is collected with a prompt
cycle — one input per line; a lone `.` line or EOF finishes:

```python
import sys

import click
from click import termui


def prompt_multiline(label: str) -> str | None:
    if not sys.stdin.isatty():
        raise click.ClickException(f"{label} entry needs an interactive terminal")
    click.echo(f"Enter the {label}. Finish with a lone '.' line or Ctrl+D.")
    lines: list[str] = []
    while True:
        try:
            line = termui.visible_prompt_func("")
        except EOFError:
            break
        except KeyboardInterrupt:
            raise click.Abort() from None
        if line == ".":
            break
        lines.append(line)
    text = "\n".join(lines)
    return text if text else None
```

- Every entered line continues the text; an empty line is an allowed text
  line — paragraphs survive.
- The two terminators are a line consisting of a single `.` and EOF
  (Ctrl+D); the rule is stated in the prompt itself.
- No line entered cancels the entry — return None and continue as without
  the value; an empty text is never produced. A single blank line joins to
  the empty text, so it cancels the entry the same way — the emptiness
  check runs on the joined text, not on the line list.
- Detect the non-interactive terminal before the first prompt — a missing
  TTY is a clean error without a traceback.
- KeyboardInterrupt aborts the command — it is not a terminator.
- Resolve `visible_prompt_func` through the module attribute at call time
  (`termui.visible_prompt_func`) — `CliRunner` patches
  `click.termui.visible_prompt_func` per invoke, and a `from`-imported
  binding never sees the patched function.
- In tests drive the cycle by a direct call: monkeypatch `sys.stdin` with
  `mock.Mock(**{"isatty.return_value": True})` and patch
  `click.termui.visible_prompt_func` with a `side_effect` list of lines —
  `EOFError` in the list models Ctrl+D, `"."` models the terminator. Under
  `CliRunner` the cycle always refuses — its `sys.stdin` is not a TTY — so
  `CliRunner` covers the non-interactive error and the flag matrix only.

### Option with an optional value

The flag that starts the entry takes an optional value — a bare flag
passes the entry marker, a given value passes the text:

```python
@click.option("--todo", "-t", "todo", default=None, is_flag=False, flag_value="",
              metavar="[TEXT]",
              help="Todo of the fresh work; without a value — interactive entry")
```

- `is_flag=False` together with `flag_value` is the optional-value form:
  without the explicit `is_flag=False` the option turns into a pure flag
  that never takes a value.
- No flag -> None; a bare `--todo`/`-t` -> "" (start the entry);
  `--todo "text"` -> the text.
- An empty string parameter value is the entry marker, never a written
  value — an empty file is never created.

## Anti-patterns

- Do not use `argparse` together with `click` in the same application
- Do not use `sys.exit()` inside commands — raise `click.ClickException` or return an error code via `ctx.exit(code)`
- Do not forget a docstring on every group and command — click generates help text from them
