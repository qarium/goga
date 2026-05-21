# JavaScript: правила реализации контрактов

Языковой скилл для JavaScript.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Cell

A cell is a module:

```
cell/
├── CODEMANIFEST
├── index.js
```

## Особенности языка

**Facade**: `index.js` — единая точка входа. Все экспорты контракта идут через `module.exports` или `export`.
Только то, что экспортировано из `index.js`, составляет фасад ячейки.

**Naming**: camelCase для функций и методов, PascalCase для классов.

**Types**: JSDoc используется для аннотаций типов. Без JSDoc сигнатуры не могут быть извлечены.

**Constructors**: Entity signature описывает вызов `new ClassName()` или фабричную функцию.

## Маппинг конструкций

| JavaScript             | CODEMANIFEST     | Примечание                                   |
|------------------------|------------------|----------------------------------------------|
| `class` в экспортах    | Entity           | Class fields → properties, methods → methods |
| `function` в экспортах | Routine          | Функция на уровне модуля                     |
| Class method           | Method           |                                              |
| Class field / getter   | Property         | Тип из JSDoc                                 |

## Implementation

- All exports go through `index.js`

## Signature Rules

Use JSDoc for type annotations where needed.

Allowed:
```
string, number, boolean
Array<T>
Object<string, T>
T | null
Promise<T>
```

Forbidden:
```
Function
Object (without generics)
...args
```

---
