# Golang: правила реализации контрактов

Языковой скилл для Golang.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Cell

A cell is a Go package:

```
cell/
├── CODEMANIFEST
├── cell.go
```

## Implementation

- Public API = exported identifiers
- Use structs + functions

## Signature Rules

Allowed:
```
string, int, float64, bool, []T, map[string]T
```

Forbidden:
```
pointers (*T),
interface{},
variadic (...),
channels,
```

---