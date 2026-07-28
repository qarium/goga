# LLM transport — провайдер-агностичный доступ к LLM API

## Предметная область

Шаблоны работы с LLM-клиентом: фабрика по SWAX_LLM_PROTOCOL, single-turn и multi-turn вызовы, обработка доменных ошибок. Целевая аудитория: cell `applications/discover/` (использует LLM для построения графа отслеживаемости).

Cell `llm/` инкапсулирует только транспорт — принимает готовые промпты и возвращает сырой текст ответа. Доменная логика (формирование промптов, парсинг JSON, multi-turn orchestration) лежит в потребителе. Провайдеры (Anthropic, OpenAI) переключаются переменной окружения без изменения кода потребителя.

---

## Получение клиента

`build_llm_client` выбирает адаптер на основе SWAX_LLM_PROTOCOL и пинит модель
из SWAX_LLM_MODEL:

```python
from swax.llm import build_llm_client, LLMClient

def get_llm() -> LLMClient:
    return build_llm_client()
```

Соглашения потребителя:
- Перед вызовом убедиться, что require_vars (cell `config/`) уже отработал — иначе MissingEnvironmentVariablesError вылетит изнутри build_*_client (проверяет все четыре SWAX_LLM_* переменные, включая SWAX_LLM_MODEL).
- При неизвестном protocol выбрасывает UnsupportedLLMProtocolError — CLI-handler маппит в click.ClickException.
- Возвращает объект, удовлетворяющий протоколу LLMClient — конкретный тип адаптера скрыт.
- Имя модели пользователь задаёт через SWAX_LLM_MODEL; потребителю не нужно знать или передавать модель — она зашита в адаптер на этапе конструирования.

---

## Single-turn вызов

`ask` отправляет один system + один user, возвращает сырой текст ответа:

```python
from swax.prompts import build_graph_system_prompt, build_graph_user_prompt
from swax.llm import build_llm_client

def first_pass(endpoints: list[str]) -> str:
    client = build_llm_client()
    system = build_graph_system_prompt()
    user = build_graph_user_prompt(endpoints)
    return client.ask(system=system, user=user)
```

Соглашения потребителя:
- Возвращает текст ответа (строка). Парсинг JSON — ответственность потребителя.
- При ошибке API выбрасывает LLMCallError или LLMRateLimitedError.

---

## Multi-turn вызов

`ask_multi_turn` отправляет system + упорядоченную историю сообщений — для уточняющего прохода:

```python
from swax.llm import build_llm_client

def refine_pass(system: str, first_user: str, first_response: str, refine_user: str) -> str:
    client = build_llm_client()
    return client.ask_multi_turn(
        system=system,
        messages=[
            {"role": "user", "content": first_user},
            {"role": "assistant", "content": first_response},
            {"role": "user", "content": refine_user},
        ],
    )
```

Соглашения потребителя:
- `messages` — упорядоченный список ролей user/assistant. Порядок критичен — SDK строит контекст из него.
- system передаётся отдельно (не входит в `messages`) — у Anthropic и OpenAI разные конвенции, cell `llm/` инкапсулирует это.

---

## Обработка доменных исключений

Все ошибки API оборачиваются в доменные исключения. Политика повторов отсутствует — это ответственность потребителя:

```python
from swax.llm import LLMCallError, LLMRateLimitedError

def safe_llm_call(client, system, user):
    try:
        return client.ask(system=system, user=user)
    except LLMRateLimitedError:
        # опционально: retry с backoff
        raise
    except LLMCallError as exc:
        # click.ClickException(f"Сбой LLM: {exc.reason}")
        raise
```

LLMRateLimitedError и LLMCallError несут reason — оригинальное сообщение SDK.

---

## Тестирование

В тестах мокать SDK-клиент в точке импорта (conventions — Моки). Не вызывать live API:

```python
def test_first_pass(mocker):
    mock_client = mocker.MagicMock()
    mock_client.ask.return_value = '{"endpoints": []}'
    # ... передать mock_client напрямую в use-case ...
```

Адаптеры принимают SDK-клиент через инъекцию конструктора — это позволяет тестировать их с mock-объектами без патчинга.
