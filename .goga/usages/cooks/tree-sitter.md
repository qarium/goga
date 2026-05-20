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

- `function_declaration` — функция (name, parameters, result)
- `method_declaration` — метод с ресивером (receiver, name, parameters, result)
- `type_declaration` — объявление типа (struct, interface, type alias)
- `struct_type` — структура (field_declaration_list)
- `interface_type` — интерфейс (method_spec)
- `parameter_list` — список параметров
- `type_identifier` — имя типа

## Извлечение сигнатур

Обход AST — `node.children` + проверка `node.type`.
Текст узла — `node.text.decode('utf-8')`.
Дочерние по имени поля — `node.child_by_field_name('name')`.
