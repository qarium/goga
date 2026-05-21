# tree-sitter + tree-sitter-go

## Назначение
Python-биндинги для incremental parsing. tree-sitter-go — грамматика Go.

## Установка
pip install tree-sitter tree-sitter-go

## Базовый паттерн парсинга Go-файла

```python
import tree_sitter_go as tsgo
from tree_sitter import Language, Parser

GO_LANG = Language(tsgo.language())

parser = Parser(GO_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Ключевые типы узлов Go AST

### Декларации
- `function_declaration` — функция (fields: name, parameters, result)
- `method_declaration` — метод с ресивером (fields: receiver, name, parameters, result)
- `type_declaration` — контейнер объявления типа (children: type_spec)

### Объявления типов
- `type_spec` — спецификация типа внутри type_declaration (fields: name, type)
- `struct_type` — структура (children: field_declaration_list)
- `interface_type` — интерфейс (children: method_elem)

### Поля и параметры
- `field_declaration_list` — список полей структуры (children: field_declaration)
- `field_declaration` — поле структуры (fields: name, type)
- `parameter_list` — список параметров (children: parameter_declaration, variadic_parameter_declaration)
- `parameter_declaration` — параметр (fields: name, type)
- `variadic_parameter_declaration` — вариативный параметр (fields: name, type)

### Методы интерфейса
- `method_elem` — метод интерфейса внутри interface_type (fields: name, parameters, result)

### Имена
- `identifier` — идентификатор (имя переменной, параметра)
- `field_identifier` — имя поля/метода (в ресивере, структуре)
- `type_identifier` — имя типа

## Извлечение сигнатур

Обход AST — `node.children` + проверка `node.type`.
Текст узла — `node.text.decode('utf-8')`.
Дочерние по имени поля — `node.child_by_field_name(field)`.

### Доступные поля узлов (field names)
- `name` — имя декларации (функции, метода, типа, поля)
- `type` — тип (параметра, поля, ресивера)
- `parameters` — список параметров функции/метода
- `result` — возвращаемое значение функции/метода
- `receiver` — ресивер метода (для method_declaration)
