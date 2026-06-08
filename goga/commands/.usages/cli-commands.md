# CLI Commands — фасад goga/commands

Пакет `goga.commands` — фасад, реэкспортирующий 9 CLI-команд. Каждая команда — `click.Command`, регистрируемый в click-группе. Каждая подклетка — независимый Python-пакет (`goga/commands/<name>/`) с реализацией в `<name>.py` и реэкспортом через `__init__.py`.

## Импорт

Все команды доступны из фасада одной строкой:

```python
from goga.commands import lint, build, connect, schema, contract, config, sync, tool, init
```

Каждая команда доступна из своей подклетки (через `__init__.py` реэкспорт):

```python
from goga.commands.lint import lint
from goga.commands.build import build
from goga.commands.connect import connect
from goga.commands.schema import schema
from goga.commands.contract import contract
from goga.commands.config import config
from goga.commands.sync import sync
from goga.commands.tool import tool
from goga.commands.init import init
```

Или напрямую из модуля реализации подклетки:

```python
from goga.commands.lint.lint import lint
from goga.commands.build.build import build
from goga.commands.connect.connect import connect
from goga.commands.schema.schema import schema
from goga.commands.contract.contract import contract
from goga.commands.config.config import config
from goga.commands.sync.sync import sync
from goga.commands.tool.tool import tool
from goga.commands.init.init import init
```

## Регистрация в click-группе

```python
import click

from goga.commands import lint, build, connect, schema, contract, config, sync, tool, init


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(lint)
app.add_command(build)
app.add_command(connect)
app.add_command(schema)
app.add_command(contract)
app.add_command(config)
app.add_command(sync)
app.add_command(tool)
app.add_command(init)
```

## Тестирование через CliRunner

```python
from click.testing import CliRunner
from goga.commands.lint import lint


def test_example():
    runner = CliRunner()
    result = runner.invoke(lint, ["."])
    assert result.exit_code in (0, 1)
```

## Список команд

| Команда    | Подклетка                 | Назначение                        |
|------------|---------------------------|-----------------------------------|
| `lint`     | `goga/commands/lint/`     | Валидация CODEMANIFEST файлов     |
| `build`    | `goga/commands/build/`    | Сборка через ralphex              |
| `connect`  | `goga/commands/connect/`  | Подключение скиллов goga          |
| `schema`   | `goga/commands/schema/`   | JSON-схема проекта                |
| `contract` | `goga/commands/contract/` | Сравнение контракта с реализацией |
| `config`   | `goga/commands/config/`   | Вывод значений конфигурации       |
| `sync`     | `goga/commands/sync/`     | Синхронизация .usages/            |
| `tool`     | `goga/commands/tool/`     | Запуск инструментальных команд    |
| `init`     | `goga/commands/init/`     | Инициализация проекта goga        |