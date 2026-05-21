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

## Особенности языка

**Facade**: только объявления с модификатором `public` составляют фасад. `internal` (по умолчанию) и `private`
не входят в контракт.

**Naming**: camelCase для функций и свойств, PascalCase для типов.

**Value types**: `struct` — value type, `class` — reference type. Выбор определяется семантикой сущности.

**Optionals**: `T?` — optional. В CODEMANIFEST отражается как `T?`.

**Protocol**: протоколы описывают интерфейсы — маппятся в Entity без properties, только methods.

## Маппинг конструкций

| Swift                            | CODEMANIFEST     | Примечание                        |
|----------------------------------|------------------|-----------------------------------|
| `public class` / `public struct` | Entity           | Init параметры → Entity signature |
| `public func` верхнего уровня    | Routine          |                                   |
| `public var` / `public let`      | Property         | Тип из объявления                 |
| `public func` метод              | Method           |                                   |
| `public protocol`                | Entity           | Только methods, без properties    |
| `init` параметры                 | Entity signature |                                   |

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
