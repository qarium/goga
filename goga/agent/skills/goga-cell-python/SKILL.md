# Python: правила реализации контрактов

Языковой скилл для Python.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

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
