# Environment — `.env` and `SWAX_*` variables

## Предметная область

Шаблоны загрузки `.env` и валидации переменных окружения `SWAX_*`. Целевая аудитория: cell `swax/cli/` (точка входа CLI загружает `.env` перед выполнением команд) и cell-и, которым нужны креды LLM (`applications/discover/`, `swax/llm/`).

Все переменные имеют префикс `SWAX_`. Файл `.env` загружается опционально — реальные переменные окружения имеют приоритет.

---

## Обязательные переменные

| Variable | Назначение |
|----------|-----------|
| `SWAX_LLM_MODEL` | имя модели (например, `"claude-sonnet-4-6"` или `"gpt-4o"`) |
| `SWAX_LLM_PROTOCOL` | `"anthropic"` или `"openai"` |
| `SWAX_LLM_BASE_URL` | базовый URL **без** версионного сегмента (`/v1`) |
| `SWAX_LLM_TOKEN` | токен доступа к LLM API |

---

## Загрузка `.env`

Выполнять рано — в callback группы Click, до подкоманд:

```python
from pathlib import Path

from swax.config import load_env

def setup_cli(env_file: Path) -> None:
    load_env(env_file)
```

`load_env` использует `override=False`: переменные, уже заданные в shell, не перезаписываются. Это позволяет разработчикам и CI переопределять значения без редактирования `.env`.

---

## Ленивая валидация

`require_vars()` возвращает mapping только если все обязательные переменные присутствуют; иначе выбрасывает `MissingEnvironmentVariablesError`. Вызывать лениво — только в use-case-ах, которым нужен LLM:

```python
from swax.config import require_vars

def before_llm_call() -> dict[str, str]:
    return require_vars()
```

`init` не нуждается в кредах LLM и не должен вызывать `require_vars`.

---

## Валидаторы значений

`parse_protocol` и `parse_base_url` проверяют формат значений до конструирования SDK-клиентов:

```python
from swax.config import parse_protocol, parse_base_url

protocol = parse_protocol(os.environ["SWAX_LLM_PROTOCOL"])
base_url = parse_base_url(os.environ["SWAX_LLM_BASE_URL"])
```

Оба выбрасывают доменные исключения (`InvalidLLMProtocolError`, `InvalidLLMBaseURLError`) с понятным сообщением, которое CLI маппит в `click.ClickException`.

---

## Тестирование

В тестах задавать переменные через `monkeypatch.setenv` и удалять через `monkeypatch.delenv` — не писать файлы `.env`.
