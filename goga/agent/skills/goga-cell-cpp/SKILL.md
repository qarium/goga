# C++: правила реализации контрактов

Языковой скилл для C++.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Cell

A cell is a directory with a public header:

```
cell/
├── CODEMANIFEST
├── cell.hpp
```

## Implementation

- Public API defined in header
- Use namespace per cell

## Signature Rules

Allowed:
```
std::string
int, double, bool
std::vector<T>
std::map<K, V>
std::optional<T>
```

Forbidden:
```
pointers (*T)
references (&, &&)
smart pointers
void*
templates in DSL
```

---
