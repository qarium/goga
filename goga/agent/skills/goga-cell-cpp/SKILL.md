---
name: goga-cell-cpp
description: C++: правила реализации контрактов CODEMANIFEST
---
# C++: правила реализации контрактов

Языковой скилл для C++.

Применяйте спецификацию в контексте вызвавшего скилла. Не пересказывайте содержимое — используйте его
для принятия решений.

Вызывается через роутер `goga-lang-disp`.

---

## Examples

Полный пример CODEMANIFEST для C++ со всеми конструкциями DSL:

```yaml
Imports:
  - Types:
      - Buffer
      - StreamConfig AS Config
    Usages:
      - memory_layout
    From: path/to/stream_cell

Usages:
  conventions: .goga/usages/cpp_conventions.md
  pattern: |
    Use RAII for resource management. Prefer stack allocation over heap allocation.
  testing: |
    Use Catch2. Each public function must have test coverage.

Annotations: |
  Use `conventions` for code style.
  Use `testing` for test requirements.
  Use `memory_layout` from Imports for buffer alignment rules.

  Use value semantics only. No raw pointers or references in public API.

---

"lookup_entry(std::string key) -> value: int":
  location: engine.hpp
  annotations: |
    Look up an entry by key.

    `key`: lookup key string
    `value`: found value or 0 if not found

    Use `pattern` for implementation.

"Parser(input: std::string)":
  location: parser.hpp
  annotations: |
    Configurable parser for structured input.

    `input`: raw input string

    Use `memory_layout` from Imports for buffer sizing.
    Use `conventions` for code style.
  properties:
    "position -> int": |
      Current parsing position.
    "length -> int": |
      Total input length.
  methods:
    "parse() -> tokens: std::vector<std::string>": |
      Parse input into tokens.

      `tokens`: parsed token list

      Use `pattern` for implementation.
    "reset()": |
      Reset parser state to beginning.

"Buffer::StreamBuffer(config: Config)":
  location: stream.hpp
  annotations: |
    Stream buffer extending Buffer with configurable capacity.

    `config`: buffer configuration from `Config` type.

    Use `memory_layout` from Imports for allocation strategy.

->Buffer: {}

---

Author: Goga
CreatedAt: 22/05/26
Description: |
  Example CODEMANIFEST demonstrating all DSL constructs for C++.
```

## Cell

A cell is a directory with a public header:

```
cell/
├── CODEMANIFEST
├── cell.hpp
```

## Особенности языка

**Facade**: header-файл (`cell.hpp`) определяет публичный API. Всё, что объявлено в header в cell namespace,
составляет фасад. Реализация — в соответствующих `.cpp` файлах.

**Naming**: PascalCase для пользовательских классов и структур, snake_case для функций и переменных.
Типы стандартной библиотеки (`std::string`, `std::vector`) используются как есть (snake_case).

**Namespace**: каждая ячейка использует свой namespace для изоляции.

**Constructors**: Entity signature описывает конструктор класса. Параметры конструктора — входные данные.

**Memory**: запрещены указатели, ссылки и smart pointers в контракте. Используйте value semantics.

## Маппинг конструкций

| C++                            | CODEMANIFEST     | Примечание                     |
|--------------------------------|------------------|--------------------------------|
| `class` / `struct` в namespace | Entity           | Конструктор → Entity signature |
| Свободная функция в namespace  | Routine          |                                |
| Public member variable         | Property         |                                |
| Public member function         | Method           |                                |
| Конструктор                    | Entity signature |                                |

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
