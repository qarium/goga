# CLI facade — точка входа и pass object

## Предметная область

Шаблоны использования точки входа CLI Swax и pass object SwaxContext. Целевая аудитория: cell-ы `commands/init/` и `commands/discover/` (регистрируются на группе main и читают SwaxContext через @click.pass_obj).

Click — единственный CLI-фреймворк Swax. Группа main верхнего уровня с опцией --env-file загружает окружение перед выполнением любой подкоманды.

---

## Регистрация подкоманд

Подкоманды init и discover регистрируются на группе main через main.add_command(). Чтобы избежать циклических импортов между cli/ и commands/, регистрация выполняется лениво в __main__.py ячейки cli/:

```python
# swax/cli/__main__.py
from swax.cli import main

# Ленивая регистрация — разрывает цикл cli/ <-> commands/
from swax.commands.init import init
from swax.commands.discover import discover

main.add_command(init)
main.add_command(discover)

if __name__ == "__main__":
    main()
```

Соглашения потребителя:
- main — это группа Click верхнего уровня, декорированная @click.group.
- Скрипт точки входа swax указывает на swax.cli.__main__:main в [project.scripts].
- Команды импортируются только в __main__.py, не в __init__.py — это сохраняет контракт CODEMANIFEST без цикла.

---

## Использование SwaxContext в подкоманде

Подкоманды получают SwaxContext через @click.pass_obj. Контекст несёт env_file; конфигурация проекта подгружается лениво:

```python
import click

from swax.cli import SwaxContext

@click.command()
@click.pass_obj
def my_command(ctx: SwaxContext) -> None:
    # ctx.env_file — путь к .env, уже загруженному callback-ом main
    # ctx.config — None по умолчанию; подгрузите через load_config при необходимости
    pass
```

Соглашения потребителя:
- env_file — только для чтения после конструирования; уже передан в load_env callback-ом группы.
- config — опциональный кэш конфигурации. Команда init не использует его (она записывает конфигурацию). Команда discover подгружает конфигурацию через load_config внутри use-case, а не через контекст.

---

## Опция --env-file

Конечный пользователь передаёт .env через --env-file:

```bash
swax --env-file .env discover
swax --env-file /path/to/.env init
```

По умолчанию --env-file .env. Переменные окружения, уже заданные в shell, имеют приоритет над файлом (override=False в load_dotenv).

---

## Тестирование

Тестировать точку входа через CliRunner, передавая mock SwaxContext через obj=:

```python
from pathlib import Path

from click.testing import CliRunner

def test_main_loads_env(mocker, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SWAX_LLM_TOKEN=test\n")

    mock_load_env = mocker.patch("swax.cli.load_env")
    runner = CliRunner()
    result = runner.invoke(main, ["--env-file", str(env_file), "init"], input="\n\n\n")
    assert mock_load_env.called
```

В тестах load_env можно мокать, чтобы избежать реальной записи в os.environ.
