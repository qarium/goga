# Extraction — пути и схемы из разобранной спецификации

## Предметная область

Шаблоны извлечения данных из разобранной спецификации для построения графа отслеживаемости. Целевая аудитория: cell `applications/discover/` (собирает узлы графа из путей и готовит схемы для уточняющего ЛЛМ-прохода).

Граф отслеживаемости оперирует только путями — без HTTP-методов, без абстракции ресурсов. Это архитектурное правило Swax: минимальная абстракция.

---

## Извлечение путей (узлы графа)

`extract_paths` возвращает отсортированный список путей API из разобранной спецификации:

```python
from swax.openapi import extract_paths

def collect_nodes(spec: dict) -> list[str]:
    return extract_paths(spec)
```

Соглашения потребителя:
- `spec` — вывод `parse_spec` (dereferenced dict).
- Возвращает шаблоны путей (например, /users, /users/{id}).
- Результат напрямую становится узлами графа отслеживаемости — методов в графе нет.

---

## Извлечение схем (контекст для LLM)

`extract_schemas` возвращает определения схем для уточняющего ЛЛМ-прохода. Функция автоматически различает OpenAPI 3.x (components.schemas) и Swagger 2.0 (definitions):

```python
from swax.openapi import extract_schemas

def collect_schema_context(spec: dict) -> dict:
    return extract_schemas(spec)
```

Соглашения потребителя:
- Схемы используются ТОЛЬКО в `build_refine_user_prompt` (cell `prompts/`) для уточнения неоднозначных пар зависимостей.
- Схемы НИКОГДА не сохраняются в граф отслеживаемости — граф хранит только пути.

---

## Полный сценарий извлечения

```python
from swax.openapi import extract_paths, extract_schemas

def extract_graph_input(spec: dict) -> tuple[list[str], dict]:
    return extract_paths(spec), extract_schemas(spec)
```

Use-case `run_discover` агрегирует пути всех спецификаций в единый список узлов, а схемы передаёт в уточняющий промпт при необходимости.
