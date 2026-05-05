# Kotlin: правила реализации контрактов

Языковой скилл для Kotlin.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Cell

A cell is a package/module:

```
cell/
├── CODEMANIFEST
├── *.kt
```

## Implementation

- Public classes and functions
- Use immutable types when possible

## Signature Rules

Allowed:
```
String, Int, Double, Boolean
List<T>, Map<String, T>
T?
```

Forbidden:
```
Any
vararg
untyped collections
```

---
