# tree-sitter + tree-sitter-python

## Назначение
Python-биндинги для incremental parsing. tree-sitter-python — грамматика Python.

## Установка
pip install tree-sitter tree-sitter-python

## Базовый паттерн парсинга Python-файла

```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANG = Language(tspython.language())

parser = Parser(PY_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Ключевые типы узлов Python AST

### Декларации
- `function_definition` — функция (fields: name, parameters, return_type)
- `class_definition` — класс (fields: name, superclasses, body)
- `decorated_definition` — декорированная декларация (children: decorator + function/class_definition)

### Параметры
- `parameters` — список параметров (children: identifier, typed_parameter, default_parameter, typed_default_parameter, list_parameter_pattern, dictionary_parameter_pattern)
- `typed_parameter` — параметр с аннотацией типа (fields: name, type)
- `default_parameter` — параметр со значением по умолчанию (fields: name, value)
- `typed_default_parameter` — параметр с аннотацией и значением по умолчанию (fields: name, type, value)
- `list_parameter_pattern` — *args (fields: name)
- `dictionary_parameter_pattern` — **kwargs (fields: name)

### Присваивания
- `assignment` — присваивание (fields: left, right)
- `expression_statement` — выражение-утверждение (для __all__ = [...])

### Аннотации типов
- `type` — аннотация типа (children: various type nodes)
- `identifier` — идентификатор
- `string` — строковый литерал (для from __future__ import annotations)

### Свойства и методы
- `decorator` — декоратор (для @property)
- `function_definition` внутри class body — метод

## Извлечение сигнатур

Обход AST — `node.children` + проверка `node.type`.
Текст узла — `node.text.decode('utf-8')`.
Дочерние по имени поля — `node.child_by_field_name(field)`.

### Доступные поля узлов (field names)
- `name` — имя декларации (функции, класса, параметра)
- `type` — тип (параметра, return)
- `parameters` — список параметров функции/метода
- `return_type` — возвращаемый тип функции/метода
- `body` — тело функции/класса
- `superclasses` — базовые классы
- `left` / `right` — левая/правая часть присваивания
- `value` — значение (для default_parameter)
