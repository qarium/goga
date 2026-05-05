# Swift: правила реализации контрактов

Языковой скилл для Swift.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Cell

A cell is a module:

```
cell/
├── CODEMANIFEST
├── *.swift
```

## Implementation

- Public API must use `public`
- Use class/struct depending on semantics

## Signature Rules

Allowed:
```
String, Int, Double, Bool
[T]
[String: T]
T?
```

Forbidden:
```
Any
UnsafePointer
inout
```

---
