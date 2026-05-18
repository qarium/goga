# Schema API — goga/schema

## Обзор

Модуль `goga.schema` формирует JSON-схему структуры проекта CODEMANIFEST
в виде иерархического дерева.

## Использование

```python
from goga.schema import schema

# Полная схема проекта
json_str = schema(cells=[], max_depth=None, depends_on=[])

# Фильтрация по конкретным cells
json_str = schema(cells=["goga/config", "goga/ast"], max_depth=None, depends_on=[])

# Ограничение вложенности
json_str = schema(cells=[], max_depth=2, depends_on=[])

# Фильтр по зависимостям
json_str = schema(cells=[], max_depth=None, depends_on=["goga/ast"])
```

## Возвращаемое значение

JSON-строка со схемой проекта. Пустое дерево → `"[]"`.

## Структура узла

```json
{
  "cell": "goga/config",
  "description": "Описание cell",
  "types": ["Config", "load_config"],
  "usages": ["configuration.md"],
  "dependencies": {
    "goga/ast": {"types": ["AST"], "usages": []}
  },
  "children": []
}
```

## Побочные эффекты

- Читает CODEMANIFEST файлы из текущего CWD
- Не модифицирует файловую систему
