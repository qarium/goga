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
