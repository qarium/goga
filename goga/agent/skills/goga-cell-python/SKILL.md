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

`__init__.py` must expose the full contract API.

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
