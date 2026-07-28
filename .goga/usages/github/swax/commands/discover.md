# Discover command — Click-handler команды `discover`

## Предметная область

Шаблон регистрации и вызова Click-команды `discover`. Целевая аудитория: cell `swax/cli/` (регистрирует команду на главной группе `main` через main.add_command(discover)).

Команда тонкая — только маппинг ошибок. Прикладная логика (парсинг спецификаций, LLM-анализ, сборка графа) делегируется в `run_discover` (cell `applications/discover/`). В отличие от `init`, `discover` не имеет интерактивных промптов — все входы из .swax/config.yml и окружения.

---

## Регистрация команды

`discover` — это декорированный @click.command callback. Регистрация на главной группе:

```python
from swax.cli import main
from swax.commands.discover import discover

main.add_command(discover)
```

Соглашения потребителя:
- Команда не принимает CLI-опций и не имеет промптов.
- Контекст передаётся через @click.pass_obj — SwaxContext из cell `cli/`.
- Требует предварительно загруженный .env (callback группы main уже вызвал load_env).

---

## Выполнение команды

При вызове `swax discover` команда:

1. Получает SwaxContext через @click.pass_obj.
2. Определяет project_root = pathlib.Path.cwd().
3. Делегирует в run_discover(project_root).
4. Перехватывает доменные исключения из `config/`, `openapi/`, `llm/` и маппит в click.ClickException.

---

## Обработка ошибок

Все доменные исключения маппятся в click.ClickException с понятными сообщениями:

| Exception | Сообщение |
|-----------|-----------|
| MissingEnvironmentVariablesError | Missing env vars: {missing} |
| SpecParseError | Failed to parse {path}: {reason} |
| LLMRateLimitedError | LLM rate limited; retry later |
| LLMCallError | LLM call failed: {reason} |
| UnsupportedLLMProtocolError | Unsupported LLM protocol: {protocol} |
| LLMResponseParseError | LLM response parse failed: {reason} |

Exit codes: 0 — успех, 1 — сбой (Click default для ClickException).

Команда НЕ повторяет rate-limited вызовы и НЕ логирует SWAX_LLM_TOKEN в сообщениях об ошибках.

---

## Тестирование

Тестировать через click.testing.CliRunner, мокая run_discover в точке импорта:

```python
from pathlib import Path

from click.testing import CliRunner

def test_discovers_graph_on_success(mocker, tmp_path):
    mocker.patch("swax.commands.discover.run_discover")
    runner = CliRunner()
    result = runner.invoke(discover, obj=SwaxContext(env_file=Path(".env")))
    assert result.exit_code == 0

def test_discovers_maps_missing_env_vars(mocker):
    def raise_missing(project_root):
        raise MissingEnvironmentVariablesError(missing=["SWAX_LLM_TOKEN"])
    mocker.patch("swax.commands.discover.run_discover", side_effect=raise_missing)
    runner = CliRunner()
    result = runner.invoke(discover, obj=SwaxContext(env_file=Path(".env")))
    assert result.exit_code == 1
    assert "SWAX_LLM_TOKEN" in result.output
```

Не вызывать live LLM API в тестах — всегда mock run_discover.
