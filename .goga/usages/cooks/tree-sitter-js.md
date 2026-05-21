# tree-sitter + tree-sitter-javascript

## Назначение
Python-биндинги для incremental parsing. tree-sitter-javascript — грамматика JavaScript.

## Установка
pip install tree-sitter tree-sitter-javascript

## Базовый паттерн парсинга JavaScript-файла

```python
import tree_sitter_javascript as tsjs
from tree_sitter import Language, Parser

JS_LANG = Language(tsjs.language())

parser = Parser(JS_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Ключевые типы узлов JavaScript AST

### Декларации
- `function_declaration` — функция (fields: name, parameters, body)
- `class_declaration` — класс (fields: name, body, decorator; children: class_heritage)
- `generator_function_declaration` — generator-функция (fields: name, parameters, body)
- `lexical_declaration` — let/const объявление (children: variable_declarator)
- `variable_declaration` — var объявление (children: variable_declarator)

### Экспорт (ESM)
- `export_statement` — экспорт (fields: declaration, source, value; children: export_clause, namespace_export)
  - `export function Foo() {}` → declaration → function_declaration
  - `export class Bar {}` → declaration → class_declaration
  - `export { a, b }` → children → export_clause → export_specifier
  - `export default expr` → value → expression
  - `export * from 'mod'` → source → string, children → namespace_export

### Класс
- `class_body` — тело класса (field: member → field_definition | method_definition | class_static_block)
- `method_definition` — метод класса (fields: name, parameters, body, decorator)
- `field_definition` — поле класса (fields: property, value, decorator)

### Функция
- `formal_parameters` — список параметров (children: assignment_pattern | pattern)
- `identifier` — имя переменной/параметра
- `assignment_pattern` — параметр со значением по умолчанию (fields: left, right)

### CommonJS
- `expression_statement` → `assignment_expression` — для `module.exports = ...`
  - `assignment_expression` (fields: left, right)
  - left → `member_expression` (module.exports)
  - right → `object` (с методами/свойствами) или `identifier` (имя функции)

### Имена
- `identifier` — обычный идентификатор
- `property_identifier` — имя свойства/метода
- `private_property_identifier` — приватное свойство (#field)

### Комментарии
- `comment` — узел комментария (extra-узел, доступен через обход)
- JSDoc: `/** @param {string} name - description */` — парсится как комментарий, типы извлекаются текстовым анализом

## Извлечение сигнатур

Обход AST — `node.children` + проверка `node.type`.
Текст узла — `node.text.decode('utf-8')`.
Дочерние по имени поля — `node.child_by_field_name('name')`.

### Паттерн: извлечение параметров функции
```python
def _extract_params(params_node):
    if params_node is None or params_node.type != "formal_parameters":
        return ""
    parts = []
    for child in params_node.children:
        if child.type == "identifier":
            parts.append(child.text.decode("utf-8"))
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            if left:
                parts.append(left.text.decode("utf-8"))
    return ", ".join(parts)
```

### Паттерн: поиск экспортов
```python
for node in root.children:
    if node.type == "export_statement":
        decl = node.child_by_field_name("declaration")
        if decl and decl.type == "function_declaration":
            # обработка экспортируемой функции
            pass
        elif decl and decl.type == "class_declaration":
            # обработка экспортируемого класса
            pass
```

### Паттерн: извлечение методов класса
```python
def _extract_class_methods(class_body_node):
    methods = []
    for member in class_body_node.children_by_field_name("member"):
        if member.type == "method_definition":
            name_node = member.child_by_field_name("name")
            params_node = member.child_by_field_name("parameters")
            # ...
    return methods
```