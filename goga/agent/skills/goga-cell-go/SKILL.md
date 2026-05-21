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

## Особенности языка

**Facade**: пакет Go и есть фасад. Все exported identifiers составляют публичный API ячейки.
Контракт-экстрактор читает exported имена как есть — имена в CODEMANIFEST должны совпадать точно.

**Naming**: camelCase для всех идентификаторов (без подчёркиваний). Экспортируемые начинаются с
большой буквы: `SomeFunc`, `SomeField`. Неэкспортируемые — с маленькой: `someFunc`, `someField`.
В CODEMANIFEST используются экспортируемые имена.

**Constructors**: в Go нет конструкторов. Entity signature описывает фабричную функцию (например `NewServer()`).

**Methods**: методы определяются через receiver, а не внутри struct. Контракт-экстрактор привязывает методы
к struct по типу receiver.

**Error handling**: идиома `(result, error)`. В CODEMANIFEST возвращаемое значение обязано иметь
семантическую метку: `() -> err:error` или `() -> result:T, err:error`.

## Маппинг конструкций

| Go                              | CODEMANIFEST     | Примечание                                 |
|---------------------------------|------------------|--------------------------------------------|
| `type X struct`                 | Entity           | Поля struct → properties (только exported) |
| `type X interface`              | Entity           | Методы интерфейса → methods                |
| `func (r *X) Method()`          | Method           | Привязывается к Entity по типу receiver    |
| `func Name()` (без receiver)    | Routine          | Функция на уровне пакета                   |
| Exported поле struct            | Property         | Тип извлекается из объявления поля         |

## Implementation

- Public API = exported identifiers
- Use structs + functions

## Signature Rules

Allowed:
```
string, int, float64, bool, error
[]T, map[string]T
```

Forbidden:
```
pointers (*T),
interface{},
variadic (...),
channels,
```

---