# Создание command line приложения на базе click

## Библиотека

**click** — Command Line Interface Creation Kit

Установка: `pip install click`

**ВАЖНО** - библиотека должна быть добавлена в зависимости проекта.

## Структура приложения

CLI-приложение строится из групп и команд. Группа — контейнер подкоманд, команда — конечное действие.

```
cli.py          # корневая группа (entry point)
__main__.py     # для вызова приложения через python -m
commands/
    __init__.py
    cmd_one.py  # подкоманда
    cmd_two.py  # подкоманда
```

- Корневая группа располагается в файле, указанном как entry point
- Каждая подкоманда — отдельный модуль
- Подкоманды регистрируются через декоратор `@<group>.command()`

## Регистрация команд в корневой группе

Для того чтобы команда попала в корневую группу и стала доступна в CLI интерфейсе,
ее необходимо импортировать и подключить.

```python
from .commands.module import command


@click.group()
def app() -> None:
    pass


app.add_command(command)
```

**ВАЖНО** - каждая новая команда должна проходить процедуру регистрации в корневой группе.

## Базовые декораторы

| Декоратор             | Назначение                           |
|-----------------------|--------------------------------------|
| `@click.group()`      | Группа (контейнер подкоманд)         |
| `@click.command()`    | Команда (конечное действие)          |
| `@click.option()`     | Именованный параметр (`--name`)      |
| `@click.argument()`   | Позиционный параметр                 |
| `@click.pass_context` | Передача `Context` первым аргументом |
| `@click.pass_obj`     | Передача `ctx.obj` первым аргументом |

## Параметры

### Option — именованные параметры

```python
@click.option('--name', default='World', help='Имя для приветствия')
@click.option('--count', default=1, type=int, help='Количество повторений')
@click.option('--verbose', is_flag=True, help='Подробный вывод')
@click.option('--level', type=click.Choice(['low', 'medium', 'high']))
@click.option('--config', type=click.Path(exists=True))
@click.option('--debug/--no-debug', default=False)
@click.option('--port', envvar='APP_PORT', default=8080, type=int)
```

- Всегда указывай `help` для каждого `--option`
- Используй `type` для валидации (`int`, `click.Path`, `click.Choice`, `click.File`)
- Используй `envvar` для чтения из переменных окружения

### Argument — позиционные параметры

```python
@click.argument('src')
@click.argument('dest', required=False)
@click.argument('files', nargs=-1, type=click.Path())
```

- Применяй только для очевидных позиционных данных (пути, имена файлов)
- Если смысл параметра неочевиден — используй `option`

## Передача состояния между командами

Для передачи данных от корневой группы к подкомандам используй `ctx.obj`:

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

- Создавай класс состояния вместо `dict` — обеспечивает типобезопасность
- Используй `ctx.ensure_object(Cls)` для безопасной инициализации
- Используй `click.make_pass_decorator(Cls)` для поиска объекта по иерархии контекстов

## Группы и вложенность

Группы вкладываются друг в друга для создания иерархии команд:

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

Вызов: `cli db migrate`

- Каждый уровень — `@click.group()`
- Конечные команды регистрируются на своём уровне: `@db.command()`

## Вывод и обработка ошибок

```python
# Вывод в stdout
click.echo('Сообщение')

# Вывод с цветом
click.secho('Ошибка!', fg='red', err=True)
click.secho('Успех!', fg='green')

# Запрос у пользователя
name = click.prompt('Ваше имя')
confirm = click.confirm('Продолжить?')

# Завершение с кодом ошибки
raise click.ClickException('Что-то пошло не так')
sys.exit(1)
```

- Используй `click.echo` вместо `print`
- Ошибки выводи через `click.secho(..., err=True)` или `raise click.ClickException`
- Не используй `print()` напрямую

## Тестирование CLI

Click предоставляет утилиту `CliRunner` для тестирования:

```python
from click.testing import CliRunner

def test_hello():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output
```

- Используй `CliRunner` для всех тестов команд
- Проверяй `result.exit_code` и `result.output`
- Для ввода от пользователя: `runner.invoke(cli, input='yes\n')`

## Антипаттерны

- Не используй `argparse` вместе с `click` в одном приложении
- Не используй `sys.exit()` внутри команд — выбрасывай `click.ClickException` или возвращай код ошибки через `ctx.exit(code)`
- Не забывай docstring на каждой группе и команде — click формирует из них help
