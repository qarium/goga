# Traceability LLM prompts — сборка промптов для построения графа

## Предметная область

Шаблоны сборки промптов для ЛЛМ-анализа зависимостей API. Целевая аудитория: cell `applications/discover/` (использует три промпт-билдера в двухпроходном сценарии построения графа отслеживаемости).

Cell собирает строки промптов — сами вызовы LLM и парсинг JSON выполняются потребителем через `LLMClient` (cell `llm/`). Это разделение ответственности: prompts/ знает «что сказать LLM», llm/ знает «как вызвать API».

---

## System-промпт аналитика

`build_graph_system_prompt` возвращает константный system-промпт, переиспользуемый в обоих проходах:

```python
from swax.prompts import build_graph_system_prompt

def setup_llm_context() -> str:
    return build_graph_system_prompt()
```

Соглашения потребителя:
- Без параметров — системный промпт постоянен для use-case-а discover.
- Передаётся как system= в LLMClient.ask / ask_multi_turn.
- Запрашивает JSON-объект {source_path: [dependent_paths]} без prose-обёртки.

---

## Первый проход: гипотезы зависимостей

`build_graph_user_prompt` формирует user-сообщение с полным списком эндпоинтов:

```python
from swax.prompts import build_graph_user_prompt

def first_pass(endpoints: list[str]) -> str:
    return build_graph_user_prompt(endpoints)
```

Соглашения потребителя:
- `endpoints` — пути API из `extract_paths` (cell `openapi/`), отсортированные.
- LLM возвращает гипотезы зависимостей и может помечать неуверенные пары для уточняющего прохода.
- Потребитель парсит JSON защитно (через json.loads с обработкой JSONDecodeError).

---

## Уточняющий проход: схемы для неоднозначных пар

`build_refine_user_prompt` формирует user-сообщение для второго (multi-turn) хода — со схемами неоднозначных пар:

```python
from swax.prompts import build_refine_user_prompt

def refine_pass(ambiguous_pairs: list[str], schemas: dict) -> str:
    return build_refine_user_prompt(ambiguous_pairs, schemas)
```

Соглашения потребителя:
- `ambiguous_pairs` — пары, помеченные LLM как неуверенные в первом проходе (например, "/users -> /orders").
- `schemas` — словарь схем из `extract_schemas` (cell `openapi/`).
- Используется в LLMClient.ask_multi_turn — multi-turn context уже несёт первый ход.
- Выходной JSON-контракт идентичен первому проходу — потребитель переиспользует тот же парсер.

---

## Полный сценарий двух проходов

use-case `run_discover` собирает все три промпта в один сценарий:

```python
from swax.prompts import (
    build_graph_system_prompt,
    build_graph_user_prompt,
    build_refine_user_prompt,
)

def run_two_pass_analysis(endpoints, ambiguous_pairs, schemas, llm_client):
    system = build_graph_system_prompt()
    first_user = build_graph_user_prompt(endpoints)
    raw_first = llm_client.ask(system=system, user=first_user)
    # ... parse raw_first, collect ambiguous_pairs ...

    refine_user = build_refine_user_prompt(ambiguous_pairs, schemas)
    raw_refined = llm_client.ask_multi_turn(
        system=system,
        messages=[
            {"role": "user", "content": first_user},
            {"role": "assistant", "content": raw_first},
            {"role": "user", "content": refine_user},
        ],
    )
    return raw_refined
```

Потребитель сам управляет маппингом ошибок LLM (LLMCallError, LLMRateLimitedError) и парсингом JSON — это не ответственность cell-а `prompts/`.
