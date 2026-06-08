---
name: goga-cell-python
description: Python правила реализации контрактов CODEMANIFEST
---
# Python: правила реализации контрактов

Языковой скилл для Python.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Examples

Полный пример CODEMANIFEST для Python со всеми конструкциями DSL:

```yaml
Imports:
  - Types:
      - DataModel
      - BaseConfig AS Config
    Usages:
      - serialization
    From: path/to/data_cell

Usages:
  conventions: .goga/usages/python_conventions.md
  pattern: |
    All public methods must use type hints. Return values are immutable where possible.
  testing: |
    Each routine and entity method must have a corresponding test in tests/.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `serialization` from Imports for data encoding patterns.

  All methods must return concrete types, not `Any`.

---

"parse_input(input: str) -> data: bytes":
  location: parser.py
  annotations: |
    Parse raw input string into structured data.

    `input`: raw string to parse

    Use `pattern` for implementation.

"DataProcessor(config: Config)":
  location: processor.py
  annotations: |
    Process data according to configuration.

    `config`: processor configuration from `Config` type.

    Use `serialization` from Imports for encoding.
    Use `conventions` for code style.
  properties:
    "name -> str": |
      Processor identifier.
    "buffer_size -> int": |
      Maximum buffer size in bytes.
  methods:
    "process(data: list[T]) -> result: list[T]": |
      Process a batch of data items.

      `data`: input items to process
      `result`: processed items

      Use `pattern` for implementation.
    "reset()": |
      Reset internal state.

"BaseHandler::HTTPHandler(host: str)":
  location: handler.py
  annotations: |
    HTTP-specific handler extending BaseHandler.

    `host`: server hostname

    Use `serialization` from Imports for request/response encoding.

->DataModel: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for Python.
```

## Cell

A cell is a Python package:

```
cell/
├── CODEMANIFEST
├── __init__.py
```

## Особенности языка

**Facade**: `__init__.py` must expose the full contract API через `__all__`. Только имена из `__all__`
составляют фасад ячейки.

**Naming**: PascalCase для классов, snake_case для функций, методов и свойств.

**Constructors**: Entity signature описывает `__init__` (параметр `self` исключается из контракта).

**Type hints**: обязательны. Используются для извлечения сигнатур свойств и методов.

## Маппинг конструкций

| Python                             | CODEMANIFEST     | Примечание                             |
|------------------------------------|------------------|----------------------------------------|
| `class` в `__all__`                | Entity           | Класс экспортируется через `__all__`   |
| `def` на уровне модуля в `__all__` | Routine          | Функция экспортируется через `__all__` |
| `@property` в классе               | Property         | Тип извлекается из return annotation   |
| `def` метод в классе               | Method           | `self` исключается из сигнатуры        |
| `__init__` параметры               | Entity signature | `self` исключается                     |

## Implementation

- Public API must be importable from package root
- Use classes and functions
- Type hints are mandatory

## Signature Rules

Allowed:
```
str, int, float, bool,
list[T], dict[str, T],
T | None
```

Forbidden:
```
*args, **kwargs,
dict without generics,
list without generics
```

---
