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

## Особенности языка

**Facade**: все `public` классы и функции верхнего уровня в пакете составляют фасад.
Приватные и internal объявления не входят в контракт.

**Naming**: camelCase для функций и свойств, PascalCase для классов.

**Constructors**: Entity signature описывает primary constructor. Параметры constructor'а — это входные данные
для получения экземпляра.

**Nullability**: `T?` — nullable, `T` — non-null. В CODEMANIFEST отражается через `T?` и `T`.

## Маппинг конструкций

| Kotlin                          | CODEMANIFEST | Примечание                             |
|---------------------------------|--------------|----------------------------------------|
| `class` / `data class` (public) | Entity       | Primary constructor → Entity signature |
| `fun` верхнего уровня           | Routine      | Public функция на уровне файла         |
| `val` / `var` свойство класса   | Property     | Тип из объявления                      |
| `fun` метод класса              | Method       |                                        |

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
