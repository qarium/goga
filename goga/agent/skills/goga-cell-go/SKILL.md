---
name: goga-cell-go
description: Golang: правила реализации контрактов CODEMANIFEST
---
# Golang: правила реализации контрактов

Языковой скилл для Golang.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Examples

Полный пример CODEMANIFEST для Go со всеми конструкциями DSL:

```yaml
Imports:
  - Types:
      - BaseModel
      - RepositoryConfig AS Config
    Usages:
      - query_patterns
    From: path/to/storage_cell

Usages:
  conventions: .goga/usages/go_conventions.md
  pattern: |
    Follow Go idioms: return errors as last return value, use interfaces for abstraction.
  testing: |
    Table-driven tests required for all exported functions and methods.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `query_patterns` from Imports for database query patterns.

  All methods returning errors must follow `(result, error)` pattern.

---

"ParseInput(input string) -> data:[]byte":
  location: parser.go
  annotations: |
    Parse raw input string into structured data.

    `input`: raw string to parse

    Use `pattern` for implementation.

"Server(host string)":
  location: server.go
  annotations: |
    HTTP server with configurable host.

    `host`: server hostname

    Use `query_patterns` from Imports for request handling.
    Use `conventions` for code style.
  properties:
    "Host -> string": |
      Server hostname.
    "Port -> int64": |
      Server port number.
  methods:
    "HandleRequest(req Request) -> resp:Response, err:error": |
      Handle incoming HTTP request.

      `req`: incoming request
      `resp`: response to send
      `err`: error if request handling fails

      Use `pattern` for implementation.
    "Shutdown() -> err:error": |
      Gracefully shut down the server.
      `err`: error if shutdown fails.

"BaseModel::Repository(db DB)":
  location: repository.go
  annotations: |
    Repository extending BaseModel with database operations.

    `db`: database connection

    Use `query_patterns` from Imports for query construction.

->BaseModel: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for Go.
```

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