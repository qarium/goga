# Init command — Click-handler команды `init`

## Предметная область

Шаблон регистрации и вызова Click-команды `init`. Целевая аудитория: cell `swax/cli/` (регистрирует команду на главной группе `main` через main.add_command(init)).

Команда тонкая — только интерактивные промпты и маппинг ошибок. Прикладная логика (клонирование, копирование, запись конфигурации) делегируется в `run_init` (cell `applications/init/`).

---

## Регистрация команды

`init` — это декорированный @click.command callback. Регистрация на главной группе:

```python
from swax.cli import main
from swax.commands.init import init

main.add_command(init)
```

Соглашения потребителя:
- Команда не принимает CLI-опций — все входы собираются через интерактивные промпты.
- Контекст передаётся через @click.pass_obj — SwaxContext из cell `cli/`.

---

## Выполнение команды

При вызове `swax init` команда:

1. Получает SwaxContext через @click.pass_obj.
2. Промптит repo_url, specs_location, download_path через click.prompt.
3. Определяет project_root = pathlib.Path.cwd().
4. Делегирует в run_init(repo_url, specs_location, download_path, project_root).
5. Перехватывает RepositoryCloneError / SpecsNotFoundError и маппит в click.ClickException.

---

## Обработка ошибок

Доменные исключения из `git/` маппятся в click.ClickException для единообразных exit codes:

- RepositoryCloneError -> click.ClickException(f"Failed to clone {exc.url}: {exc.reason}")
- SpecsNotFoundError -> click.ClickException(f"Specs not found at {exc.path}")

Exit codes: 0 — успех, 1 — сбой (Click default для ClickException).

---

## Тестирование

Тестировать через click.testing.CliRunner, вызывая callback напрямую без subprocess:

```python
from click.testing import CliRunner
from swax.commands.init import init

def test_init_prompts_and_delegates(mocker):
    mocker.patch("swax.commands.init.run_init")
    runner = CliRunner()
    result = runner.invoke(init, input="https://example.com/repo.git\nspecs/\n./local_specs\n")
    assert result.exit_code == 0
```

В тестах мокать run_init в точке импорта — не выполнять реальное клонирование.
