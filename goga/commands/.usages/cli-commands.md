# CLI Commands — фасад goga/commands

Пакет `goga.commands` — фасад, реэкспортирующий 7 CLI-команд. Каждая команда — `click.Command`, регистрируемый в click-группе. Каждая подклетка — независимый Python-пакет (`goga/commands/<name>/`) с реализацией в `<name>.py` и реэкспортом через `__init__.py`.

## Импорт

Все команды доступны из фасада одной строкой:

```python
from goga.commands import linter, build, install, schema, contract, config, sync
```

Каждая команда доступна из своей подклетки (через `__init__.py` реэкспорт):

```python
from goga.commands.linter import linter
from goga.commands.build import build
from goga.commands.install import install
from goga.commands.schema import schema
from goga.commands.contract import contract
from goga.commands.config import config
from goga.commands.sync import sync
```

Или напрямую из модуля реализации подклетки:

```python
from goga.commands.linter.linter import linter
from goga.commands.build.build import build
from goga.commands.install.install import install
from goga.commands.schema.schema import schema
from goga.commands.contract.contract import contract
from goga.commands.config.config import config
from goga.commands.sync.sync import sync
```

## Регистрация в click-группе

```python
import click

from goga.commands import linter, build, install, schema, contract, config, sync


@click.group()
def app() -> None:
    """Goga — CODEMANIFEST validation tool."""


app.add_command(linter)
app.add_command(build)
app.add_command(install)
app.add_command(schema)
app.add_command(contract)
app.add_command(config)
app.add_command(sync)
```

## Тестирование через CliRunner

```python
from click.testing import CliRunner
from goga.commands.linter import linter


def test_example():
    runner = CliRunner()
    result = runner.invoke(linter, ["."])
    assert result.exit_code in (0, 1)
```

## Список команд

| Команда | Подклетка | Назначение |
|---------|-----------|-----------|
| `linter` | `goga/commands/linter/` | Валидация CODEMANIFEST файлов |
| `build` | `goga/commands/build/` | Сборка через ralphex |
| `install` | `goga/commands/install/` | Установка скиллов goga |
| `schema` | `goga/commands/schema/` | JSON-схема проекта |
| `contract` | `goga/commands/contract/` | Сравнение контракта с реализацией |
| `config` | `goga/commands/config/` | Вывод значений конфигурации |
| `sync` | `goga/commands/sync/` | Синхронизация .usages/ |