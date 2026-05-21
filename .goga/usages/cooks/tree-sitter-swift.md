# tree-sitter + tree-sitter-swift

## Назначение
Python-биндинги для incremental parsing. tree-sitter-swift -- грамматика Swift (alex-pinkus/tree-sitter-swift).

## Установка
pip install tree-sitter tree-sitter-swift

## Базовый паттерн парсинга Swift-файла

```python
import tree_sitter_swift as tsswift
from tree_sitter import Language, Parser

SWIFT_LANG = Language(tsswift.language())

parser = Parser(SWIFT_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node  # source_file
```

## Ключевые типы узлов Swift AST

### Корень
- `source_file` -- корневой узел (children: все top-level declarations, statements, expressions, import_declaration, shebang_line, comment, multiline_comment)

### Декларации

#### Функция
- `function_declaration` -- функция (fields: name, return_type, body, default_value; children: attribute, modifiers, parameter, throws, type_parameters, type_constraints, inheritance_modifier, ownership_modifier, property_behavior_modifier)

#### Класс / Struct / Enum / Actor / Extension
- `class_declaration` -- класс/struct/enum/actor/extension (fields: name, body, declaration_kind; children: attribute, modifiers, inheritance_modifier, inheritance_specifier, ownership_modifier, property_behavior_modifier, type_parameters, type_constraints)
  - `declaration_kind`: `actor` | `class` | `enum` | `extension` | `struct`
  - `name`: type_identifier | user_type | ...
  - `body`: `class_body` | `enum_class_body`

#### Protocol
- `protocol_declaration` -- протокол (fields: name, body, declaration_kind; children: attribute, modifiers, inheritance_specifier, type_parameters, type_constraints)
  - `declaration_kind`: `protocol`
  - `name`: type_identifier
  - `body`: `protocol_body`

#### Initializer
- `init_declaration` -- инициализатор (fields: name, body, default_value; children: attribute, modifiers, parameter, throws, type_parameters, type_constraints, bang -- для failable init `init?`)

#### Deinitializer
- `deinit_declaration` -- деинициализатор (fields: body; children: modifiers)

#### Subscript
- `subscript_declaration` -- индекс (fields: name, return_type, default_value; children: attribute, computed_property, modifiers, parameter, type_parameters, type_constraints)

#### Property
- `property_declaration` -- свойство (fields: name, value, computed_value; children: attribute, modifiers, type_annotation, type_constraints, value_binding_pattern, willset_didset_block, inheritance_modifier, ownership_modifier, property_behavior_modifier)
  - `name`: pattern
  - `computed_value`: computed_property
  - `value`: выражение (инициализатор)

#### Typealias
- `typealias_declaration` -- typealias (fields: name, value; children: attribute, modifiers, inheritance_modifier, ownership_modifier, property_behavior_modifier, type_parameters)

#### Associated Type
- `associatedtype_declaration` -- associated type (fields: name, default_value, must_inherit; children: modifiers, type_constraints)

#### Import
- `import_declaration` -- import (children: identifier, modifiers)

#### Operator
- `operator_declaration` -- объявление оператора (children: bang, custom_operator, deprecated_operator_declaration_body, simple_identifier)

#### Precedence Group
- `precedence_group_declaration` -- группа приоритетов (children: precedence_group_attributes, simple_identifier)

#### Macro
- `macro_declaration` -- макрос (fields: default_value, definition; children: attribute, modifiers, parameter, simple_identifier, type_constraints, type_parameters, + типы)
  - `definition`: macro_definition

### Тела

#### Class Body
- `class_body` -- тело class/struct/actor/extension (children: associatedtype_declaration, class_declaration, deinit_declaration, function_declaration, import_declaration, init_declaration, multiline_comment, operator_declaration, precedence_group_declaration, property_declaration, protocol_declaration, subscript_declaration, typealias_declaration)

#### Enum Body
- `enum_class_body` -- тело enum (children: как class_body + enum_entry)

#### Enum Entry
- `enum_entry` -- case enum'а (fields: name, raw_value, data_contents; children: modifiers)
  - `name`: simple_identifier
  - `raw_value`: выражение
  - `data_contents`: enum_type_parameters

#### Protocol Body
- `protocol_body` -- тело протокола (fields: body -- protocol_function_declaration; children: associatedtype_declaration, deinit_declaration, init_declaration, protocol_function_declaration, protocol_property_declaration, subscript_declaration, typealias_declaration)

#### Protocol Function
- `protocol_function_declaration` -- функция протокола (fields: name, return_type, default_value; children: attribute, modifiers, parameter, statements, throws, type_constraints, type_parameters)

#### Protocol Property
- `protocol_property_declaration` -- свойство протокола (fields: name; children: modifiers, protocol_property_requirements, type_annotation, type_constraints)
  - `name`: pattern
  - `protocol_property_requirements`: getter_specifier, setter_specifier

### Типы

- `user_type` -- пользовательский тип (children: type_identifier, type_arguments)
- `array_type` -- массив (fields: element, name)
- `dictionary_type` -- словарь (fields: key, name, value)
- `optional_type` -- опционал (fields: wrapped -- array_type | dictionary_type | tuple_type | user_type)
- `tuple_type` -- кортеж (fields: element -- tuple_type_item; children: tuple_type_item)
- `function_type` -- тип функции (fields: name, params, return_type; children: throws)
- `existential_type` -- `any P` (children: тип)
- `opaque_type` -- `some P` (children: тип)
- `protocol_composition_type` -- `P1 & P2` (children: типы)
- `metatype` -- `.Type` / `.Protocol` (children: тип)
- `type_pack_expansion` -- `each T` (children: тип)
- `type_parameter_pack` -- параметр-пак (children: тип)
- `suppressed_constraint` -- `~` (fields: suppressed -- type_identifier)

### Параметры

- `parameter` -- параметр функции (fields: external_name, name, type; children: parameter_modifiers)
  - `external_name`: simple_identifier
  - `name`: simple_identifier | тип
  - `type`: тип
  - `parameter_modifiers`: parameter_modifiers (например, inout, borrowing, consuming)
- `lambda_parameter` -- параметр замыкания (fields: external_name, name, type; children: parameter_modifiers, self_expression)

### Аннотации типов

- `type_annotation` -- аннотация типа (fields: name, type)
- `type_arguments` -- generic-аргументы (fields: name; children: type_modifiers)
- `type_parameters` -- generic-параметры (children: type_parameter, type_constraints)
- `type_parameter` -- generic-параметр (fields: name; children: type_identifier, type_modifiers, type_parameter_modifiers, type_parameter_pack)
- `type_constraints` -- `where`-ограничения (children: type_constraint, where_keyword)
- `type_constraint` -- ограничение (children: equality_constraint | inheritance_constraint)
- `equality_constraint` -- `T == U` (fields: constrained_type, name, must_equal; children: attribute)
- `inheritance_constraint` -- `T: P` (fields: constrained_type, name, inherits_from; children: attribute)
- `type_modifiers` -- модификаторы типа (children: attribute)
- `type_parameter_modifiers` -- модификаторы параметра типа (children: attribute)
- `type_identifier` -- идентификатор типа

### Модификаторы

- `modifiers` -- блок модификаторов (children: attribute, function_modifier, inheritance_modifier, member_modifier, mutation_modifier, ownership_modifier, parameter_modifier, property_behavior_modifier, property_modifier, visibility_modifier)
- `attribute` -- @-атрибута (children: выражения, user_type)
- `member_modifier` -- static, class, override (keyword)
- `visibility_modifier` -- public, private, fileprivate, internal, open, package
- `inheritance_modifier` -- final, required, convenience, optional, dynamic
- `mutation_modifier` -- mutating, nonmutating
- `ownership_modifier` -- weak, unowned, unowned(safe), unowned(unsafe)
- `parameter_modifier` -- inout, borrowing, consuming
- `property_modifier` -- lazy, distributed
- `property_behavior_modifier` -- будет использовано для будущих property behaviors
- `function_modifier` -- infix, prefix, postfix, optional

### Специальные Swift-конструкции

#### Опционалы
- `optional_type` -- `T?` (fields: wrapped)
- `bang` -- force-unwrap `expr!`
- `try_expression` с `try!` / `try?` -- child: try_operator

#### Guard
- `guard_statement` -- guard (fields: condition, bound_identifier, name; children: else, statements)

#### Async/Await
- `await_expression` -- await (fields: expr)
- `async` -- модификатор (ключевое слово в условии if/guard)

#### Actors
- `class_declaration` с `declaration_kind` = `actor`

#### Property Wrappers
- Реализуются через `attribute` -- `@propertyWrapper`, `@Published`, и т.д.
- `willset_didset_block` -- наблюдатели свойства (children: willset_clause, didset_clause)
- `willset_clause` / `didset_clause` -- (children: modifiers, simple_identifier, statements)

#### Computed Properties
- `computed_property` -- вычисляемое свойство (children: computed_getter, computed_modify, computed_setter, statements)
- `computed_getter` -- get (children: attribute, getter_specifier, statements)
- `computed_setter` -- set (children: attribute, setter_specifier, simple_identifier, statements)
- `computed_modify` -- _modify (children: attribute, modify_specifier, statements)
- `getter_specifier` -- get (children: mutation_modifier, throws)
- `setter_specifier` -- set (children: mutation_modifier)
- `modify_specifier` -- _modify (children: mutation_modifier)

#### Closures (Lambda)
- `lambda_literal` -- замыкание (fields: captures, type; children: attribute, statements)
  - `captures`: capture_list
  - `type`: lambda_function_type
- `lambda_function_type` -- тип замыкания (fields: name, return_type; children: lambda_function_type_parameters, throws)
- `capture_list` -- список захвата (children: capture_list_item)
- `capture_list_item` -- элемент захвата (fields: name, value; children: ownership_modifier)

#### Error Handling
- `try_expression` -- try / try! / try? (fields: expr; children: try_operator)
- `do_statement` -- do блок (children: statements, catch_block)
- `catch_block` -- catch (fields: error -- pattern; children: catch_keyword, statements, where_clause)
- `throws` -- throws-модификатор
- `control_transfer_statement` -- return, throw, break, continue (fields: result; children: throw_keyword, выражения)

#### Switch
- `switch_statement` -- switch (fields: expr; children: switch_entry)
- `switch_entry` -- case / default (children: switch_pattern, default_keyword, statements, modifiers, where_keyword, выражения)
- `switch_pattern` -- паттерн case (children: pattern)

#### Statements
- `if_statement` -- if / if let (fields: condition, bound_identifier, name; children: statements, else, if_statement)
- `guard_statement` -- guard (fields: condition, bound_identifier, name; children: else, statements)
- `for_statement` -- for-in (fields: item, collection; children: statements, try_operator, type_annotation, where_clause)
- `while_statement` -- while (fields: condition, bound_identifier, name; children: statements)
- `repeat_while_statement` -- repeat-while (fields: condition, bound_identifier, name; children: statements)

#### Patterns
- `pattern` -- паттерн (fields: bound_identifier, name; children: выражения, pattern, value_binding_pattern, wildcard_pattern, type_modifiers, user_type)
- `value_binding_pattern` -- let/var паттерн (fields: mutability: `let` | `var`)
- `wildcard_pattern` -- `_`

### Выражения

#### Литералы
- `boolean_literal` -- true/false
- `integer_literal` -- целое число
- `real_literal` -- число с точкой
- `hex_literal` -- 0x...
- `bin_literal` -- 0b...
- `oct_literal` -- 0o...
- `line_string_literal` -- строка (fields: text, interpolation)
- `multi_line_string_literal` -- многострочная строка (fields: text, interpolation)
- `raw_string_literal` -- raw-строка (fields: text, interpolation; children: raw_str_continuing_indicator)
- `regex_literal` -- регулярное выражение
- `array_literal` -- массив (fields: element)
- `dictionary_literal` -- словарь (fields: key, value)
- `nil` -- nil (anonymous)
- `special_literal` -- #file, #line, #column, #function, #dsohandle, #filePath, #fileID

#### Операции
- `assignment` -- присваивание (fields: operator, target, result)
- `additive_expression` -- +/- (fields: lhs, op, rhs)
- `multiplicative_expression` -- *///% (fields: lhs, op, rhs)
- `comparison_expression` -- < > <= >= (fields: lhs, op, rhs)
- `equality_expression` -- == != === !== (fields: lhs, op, rhs)
- `conjunction_expression` -- && (fields: lhs, op, rhs)
- `disjunction_expression` -- || (fields: lhs, op, rhs)
- `bitwise_operation` -- & | ^ << >> (fields: lhs, op, rhs)
- `nil_coalescing_expression` -- ?? (fields: if_nil, value)
- `ternary_expression` -- a ? b : c (fields: condition, if_true, if_false)
- `infix_expression` -- кастомный инфиксный оператор (fields: lhs, op, rhs)
- `prefix_expression` -- префиксная операция (fields: operation, target)
- `postfix_expression` -- постфиксная операция (fields: operation, target)
- `range_expression` -- ... / ..< (fields: start, end, op)
- `fully_open_range` -- ...
- `open_end_range_expression` -- a... (fields: start)
- `open_start_range_expression` -- ...a (fields: end)

#### Приведение типов
- `as_expression` -- as / as! / as? (fields: expr, name, type; children: as_operator)
- `check_expression` -- `is` (fields: target, name, op, type)

#### Вызовы и доступ
- `call_expression` -- вызов функции (children: call_suffix, выражения)
- `call_suffix` -- суффикс вызова (fields: name; children: lambda_literal, value_arguments)
- `constructor_expression` -- вызов инициализатора (fields: constructed_type; children: constructor_suffix)
- `navigation_expression` -- точечный доступ (fields: target, suffix, element)
- `navigation_suffix` -- .identifier / .integer (fields: suffix)

#### Специальные выражения
- `self_expression` -- self
- `super_expression` -- super
- `try_expression` -- try (fields: expr; children: try_operator)
- `await_expression` -- await (fields: expr)
- `key_path_expression` -- \.path (children: simple_identifier, user_type, type_identifier, type_arguments, value_argument, bang, dictionary_type, array_type)
- `key_path_string_expression` -- #keyPath (children: выражение)
- `selector_expression` -- #selector (children: выражение)
- `tuple_expression` -- кортеж (fields: name, value)
- `lambda_literal` -- замыкание (fields: captures, type; children: attribute, statements)
- `macro_invocation` -- вызов макроса (children: call_suffix, simple_identifier, type_parameters)

#### Идентификаторы
- `simple_identifier` -- идентификатор
- `identifier` -- составной идентификатор (children: simple_identifier)

### Аргументы

- `value_arguments` -- список аргументов вызова (children: value_argument)
- `value_argument` -- аргумент (fields: name, reference_specifier, value; children: type_modifiers)
  - `name`: value_argument_label
- `value_argument_label` -- метка аргумента (children: simple_identifier)

### Pack Expansion (Swift 5.9+)
- `value_pack_expansion` -- `each expr` (children: выражение)
- `value_parameter_pack` -- pack-параметр (children: выражение)

### Директивы
- `directive` -- #if / #else / #elseif / #endif / #warning / #error (children: boolean_literal, integer_literal, simple_identifier)
- `availability_condition` -- #available / #unavailable (children: identifier, integer_literal)
- `diagnostic` -- #warning / #error

### Комментарии (extra-узлы)
- `comment` -- однострочный комментарий
- `multiline_comment` -- многострочный комментарий

## Извлечение сигнатур

Обход AST -- `node.children` + проверка `node.type`.
Текст узла -- `node.text.decode('utf-8')`.
Дочерние по имени поля -- `node.child_by_field_name('name')`.

### Паттерн: извлечение всех функций из файла
```python
def extract_functions(root):
    functions = []
    for child in root.children:
        if child.type == "function_declaration":
            name_node = child.child_by_field_name("name")
            return_type_node = child.child_by_field_name("return_type")
            body_node = child.child_by_field_name("body")
            name = name_node.text.decode("utf-8") if name_node else "<anon>"
            return_type = return_type_node.text.decode("utf-8") if return_type_node else "Void"
            is_async = any(c.type == "simple_identifier" and c.text == b"async" for c in child.children)
            throws = any(c.type == "throws" for c in child.children)
            functions.append({
                "name": name,
                "return_type": return_type,
                "async": is_async,
                "throws": throws,
            })
    return functions
```

### Паттерн: поиск class/struct/enum/actor/extension
```python
for child in root.children:
    if child.type == "class_declaration":
        kind_node = child.child_by_field_name("declaration_kind")
        name_node = child.child_by_field_name("name")
        body_node = child.child_by_field_name("body")
        # declaration_kind: actor | class | enum | extension | struct
        kind = kind_node.text.decode("utf-8") if kind_node else "class"
        name = name_node.text.decode("utf-8") if name_node else ""
```

### Паттерн: извлечение параметров функции
```python
def _extract_params(func_node):
    params = []
    for child in func_node.children:
        if child.type == "parameter":
            ext_name_node = child.child_by_field_name("external_name")
            name_node = child.child_by_field_name("name")
            type_node = child.child_by_field_name("type")
            ext_name = ext_name_node.text.decode("utf-8") if ext_name_node else ""
            name = name_node.text.decode("utf-8") if name_node else ""
            typ = type_node.text.decode("utf-8") if type_node else ""
            params.append({"external_name": ext_name, "name": name, "type": typ})
    return params
```

### Паттерн: извлечение методов класса
```python
def _extract_class_methods(class_body_node):
    methods = []
    for child in class_body_node.children:
        if child.type == "function_declaration":
            name_node = child.child_by_field_name("name")
            # ... извлечение параметров, модификаторов и т.д.
            methods.append(name_node.text.decode("utf-8") if name_node else "<anon>")
    return methods
```

### Паттерн: обход enum case'ов
```python
def _extract_enum_cases(enum_body_node):
    cases = []
    for child in enum_body_node.children:
        if child.type == "enum_entry":
            name_node = child.child_by_field_name("name")
            raw_value_node = child.child_by_field_name("raw_value")
            data_node = child.child_by_field_name("data_contents")
            name = name_node.text.decode("utf-8") if name_node else ""
            cases.append(name)
    return cases
```