# Tool command — запуск внешних tool-пакетов

Команда `goga tool` динамически загружает и вызывает внешние tool-пакеты.

## Импорт

```python
from goga.commands.tool import tool
```

## Использование в CLI

```bash
goga tool <name> [args...]
```

- `<name>` — имя tool-пакета (без префикса `goga_tool_`)
- `[args...]` — произвольные аргументы, передаваемые в `main(argv)` tool-пакета

## Регистрация в click-группе

```python
from goga.commands import tool

app.add_command(tool)
```

## Требования к tool-пакету

Пакет `goga_tool_<name>` должен предоставлять функцию:

```python
def main(argv: list[str]) -> None:
    """Entry point для tool-пакета."""
    ...
```

## Тестирование

```python
from click.testing import CliRunner
from goga.commands.tool import tool

def test_tool_example():
    runner = CliRunner()
    result = runner.invoke(tool, ["mytool", "arg1", "--flag", "value"])
    # Проверка зависит от установленного tool-пакета
```
