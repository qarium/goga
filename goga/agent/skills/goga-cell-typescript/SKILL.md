# TypeScript: правила реализации контрактов

Языковой скилл для TypeScript.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Cell

A cell is a module:

```
cell/
├── CODEMANIFEST
├── index.ts
```

## Implementation

- All exports go through `index.ts`

## Signature Rules

Allowed:
```
string, number, boolean
T[]
Record<string, T>
T | null
Promise<T>
```

Forbidden:
```
any
unknown (without constraints)
object
...args
```

---
