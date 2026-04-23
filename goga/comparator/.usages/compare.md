Сравнение контрактов CODEMANIFEST с реализацией

```python
from goga.comparator import compare
from goga.ast import AST

# Загрузить проект
ast_obj = AST(".")
ast_obj.load()

# Сравнить все клетки проекта
result = compare(ast_obj.tree)

# Сравнить только указанные клетки
result = compare(ast_obj.tree, paths=["goga/contract", "goga/ast/nodes"])
```

Результат — словарь, где ключи — пути клеток, значения — структура сравнения:

```json
{
  "cell/path": {
    "codemanifest": {
      "EntityName": {
        "()": "конструктор_сигнатура",
        "methods": { "method_name": "сигнатура" },
        "properties": { "prop_name": "тип_сигнатура" }
      },
      "routine_name": "полная_сигнатура"
    },
    "source": {
      "EntityName": {
        "()": "конструктор_сигнатура",
        "methods": { "method_name": "сигнатура" },
        "properties": { "prop_name": "тип_сигнатура" }
      },
      "routine_name": "полная_сигнатура"
    }
  }
}
```

- `codemanifest` — контракт из CODEMANIFEST с разрешёнными мутациями
- `source` — контракт из исходного кода (пустой dict если пакет не найден)
- Entity содержит вложенные methods и properties
- Routine — строка с сигнатурой
