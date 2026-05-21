# tree-sitter + tree-sitter-kotlin

## Назначение
Python-биндинги для incremental parsing. tree-sitter-kotlin — грамматика Kotlin.

## Установка
pip install tree-sitter tree-sitter-kotlin

## Базовый паттерн парсинга Kotlin-файла

```python
import tree_sitter_kotlin as tskotlin
from tree_sitter import Language, Parser

KOTLIN_LANG = Language(tskotlin.language())

parser = Parser(KOTLIN_LANG)

tree = parser.parse(source_bytes)
root = tree.root_node
```

## Ключевые типы узлов Kotlin AST

### Декларации
- `function_declaration` — функция (field: receiver; children: modifiers, type_parameters, simple_identifier(имя), function_value_parameters, _type(возврат), function_body)
- `property_declaration` — свойство (field: receiver; children: modifiers, binding_pattern_kind(val/var), variable_declaration, property_delegate, getter, setter)
- `class_declaration` — класс/интерфейс/enum/annotation/data/sealed (children: modifiers, type_identifier(имя), type_parameters, primary_constructor, class_body/enum_class_body)
- `object_declaration` — объект (children: modifiers, type_identifier(имя), class_body)
- `companion_object` — companion object (children: modifiers, type_identifier(имя), class_body)
- `type_alias` — псевдоним типа (children: type_identifier(имя), type_parameters, _type)
- `secondary_constructor` — вторичный конструктор (children: modifiers, function_value_parameters, constructor_delegation_call, _block)
- `anonymous_initializer` — блок init (children: _block)

### Конструктор и параметры
- `primary_constructor` — первичный конструктор (children: class_parameter...)
- `class_parameter` — параметр конструктора класса (children: modifiers, binding_pattern_kind(val/var), simple_identifier(имя), _type, default)
- `function_value_parameters` — список параметров функции (children: parameter_modifiers, parameter, default)
- `parameter` — параметр (children: simple_identifier(имя), _type)

### Тела
- `function_body` — тело функции (блок или expression body через `=`)
- `class_body` — тело класса (children: декларации)
- `enum_class_body` — тело enum (children: enum_entry, декларации)
- `control_structure_body` — тело управляющей конструкции (блок или одно выражение)
- `statements` — список инструкций внутри блока

### Типы
- `user_type` — пользовательский тип (children: type_identifier, type_arguments)
- `nullable_type` — nullable тип `Type?` (children: user_type/parenthesized_type, quest)
- `function_type` — функциональный тип `(Params) -> Ret` (field: receiver; children: function_type_parameters, _type)
- `parenthesized_type` — тип в скобках `(Type)`
- `receiver_type` — тип ресивера для extension (children: type_modifiers, user_type/nullable_type)
- `type_parameters` — `<T, U>` (children: type_parameter)
- `type_arguments` — `<Arg>` (children: type_projection)
- `type_modifiers` — модификаторы типа (children: annotation, suspend)

### Имена и идентификаторы
- `simple_identifier` — идентификатор (имя переменной, параметра, функции)
- `type_identifier` — имя типа (alias от simple_identifier)
- `binding_pattern_kind` — `val` или `var`

### Модификаторы
- `modifiers` — контейнер модификаторов (children: annotation, class_modifier, visibility_modifier, ...)
- `visibility_modifier` — `public`, `private`, `internal`, `protected`
- `class_modifier` — `sealed`, `annotation`, `data`, `inner`, `value`
- `member_modifier` — `override`, `lateinit`
- `function_modifier` — `tailrec`, `operator`, `infix`, `inline`, `external`, `suspend`
- `property_modifier` — `const`
- `inheritance_modifier` — `abstract`, `final`, `open`
- `parameter_modifier` — `vararg`, `noinline`, `crossinline`
- `platform_modifier` — `expect`, `actual`
- `variance_modifier` — `in`, `out`
- `reification_modifier` — `reified`

### Аннотации
- `annotation` — аннотация (children: use_site_target, user_type/constructor_invocation)
- `use_site_target` — target аннотации: `field`, `property`, `get`, `set`, `receiver`, `param`, `setparam`, `delegate`

### Enum
- `enum_entry` — элемент enum (children: modifiers, simple_identifier(имя), value_arguments, class_body)

### Выражения
- `call_expression` — вызов функции (children: _expression, call_suffix)
- `navigation_expression` — доступ к члену `a.b` (children: _expression, navigation_suffix)
- `indexing_expression` — индексация `a[i]` (children: _expression, indexing_suffix)
- `as_expression` — приведение типа `x as Type` (children: _expression, _type)
- `elvis_expression` — elvis `x ?: y` (children: _expression)
- `range_expression` — диапазон `a..b`, `a..<b` (children: _expression)
- `lambda_literal` — лямбда `{ params -> body }` (children: lambda_parameters, statements)
- `anonymous_function` — анонимная функция `fun(params) { body }` (children: function_value_parameters, function_body)
- `if_expression` — if (fields: condition, consequence, alternative)
- `when_expression` — when (children: when_subject, when_entry)
- `try_expression` — try/catch/finally (children: _block, catch_block, finally_block)
- `string_literal` — строка с интерполяцией (children: string_content, interpolated_expression, interpolated_identifier)
- `callable_reference` — ссылка на функцию `Class::method` (children: type_identifier, simple_identifier)
- `this_expression` — `this` или `this@Label`
- `super_expression` — `super` или `super<Type>`
- `jump_expression` — return, throw, continue, break
- `spread_expression` — spread `*args` (children: _expression)
- `object_literal` — объект-выражение `object : Base { ... }`
- `collection_literal` — `[a, b, c]`

### Когда/When
- `when_entry` — ветка when (children: when_condition/guard_condition, control_structure_body)
- `when_condition` — условие ветки (children: _expression, range_test, type_test)
- `when_subject` — субъект when `when(x)` (children: _expression)
- `guard_condition` — guard-условие в when-entry (children: _expression)

### Делегирование и делегаты
- `property_delegate` — делегат свойства `by expr` (children: _expression)
- `explicit_delegation` — делегирование в наследовании `Type by expr`
- `constructor_delegation_call` — `this(...)` или `super(...)` в конструкторе

### Импорт и пакет
- `package_header` — объявление пакета (children: identifier)
- `import_header` — импорт (children: identifier, import_alias)
- `import_list` — список импортов (children: import_header)
- `import_alias` — алиас импорта `as Name`
- `wildcard_import` — звёздочный импорт `.*`

### Getter/Setter
- `getter` — геттер свойства (children: modifiers, function_body)
- `setter` — сеттер свойства (children: modifiers, parameter_with_optional_type, function_body)

## Извлечение сигнатур

Обход AST — `node.children` + проверка `node.type`.
Текст узла — `node.text.decode('utf-8')`.
Дочерние по имени поля — `node.child_by_field_name(field)`.

**ВАЖНО**: большинство узлов Kotlin AST не имеют именованных полей. Дети доступны позиционно через `node.children`.
Именованные поля только у: `function_declaration.receiver`, `property_declaration.receiver`, `function_type.receiver`,
`if_expression.condition/consequence/alternative`.

### Паттерн: извлечение параметров функции
```python
def _extract_params(params_node):
    if params_node is None or params_node.type != "function_value_parameters":
        return ""
    parts = []
    for child in params_node.children:
        if child.type == "parameter":
            name_node = child.child_by_field_name("name")
            if name_node is None:
                for ch in child.children:
                    if ch.type == "simple_identifier":
                        name_node = ch
                        break
            if name_node:
                parts.append(name_node.text.decode("utf-8"))
    return ", ".join(parts)
```

### Паттерн: обход деклараций верхнего уровня
```python
for node in root.children:
    if node.type == "function_declaration":
        name = _first_child_by_type(node, "simple_identifier")
        params = _first_child_by_type(node, "function_value_parameters")
        # extension function?
        receiver = node.child_by_field_name("receiver")
    elif node.type == "class_declaration":
        name = _first_child_by_type(node, "type_identifier")
        body = _first_child_by_type(node, "class_body")
        # проверить modifiers на data/sealed/annotation/inner/value
    elif node.type == "property_declaration":
        binding = _first_child_by_type(node, "binding_pattern_kind")  # val/var
        var_decl = _first_child_by_type(node, "variable_declaration")
    elif node.type == "object_declaration":
        name = _first_child_by_type(node, "type_identifier")
    elif node.type == "type_alias":
        name = _first_child_by_type(node, "type_identifier")

def _first_child_by_type(node, type_name):
    for child in node.children:
        if child.type == type_name:
            return child
    return None
```

### Паттерн: извлечение методов и свойств класса
```python
def _extract_class_members(class_body_node):
    methods = []
    properties = []
    for child in class_body_node.children:
        if child.type == "function_declaration":
            name = _first_child_by_type(child, "simple_identifier")
            params = _first_child_by_type(child, "function_value_parameters")
            if name:
                methods.append(name.text.decode("utf-8"))
        elif child.type == "property_declaration":
            var_decl = _first_child_by_type(child, "variable_declaration")
            if var_decl:
                ident = _first_child_by_type(var_decl, "simple_identifier")
                if ident:
                    properties.append(ident.text.decode("utf-8"))
    return methods, properties
```

### Паттерн: определение типа класса (data/sealed/enum/annotation/interface)
```python
def _class_kind(class_decl_node):
    has_enum_body = any(c.type == "enum_class_body" for c in class_decl_node.children)
    if has_enum_body:
        return "enum"

    for child in class_decl_node.children:
        if child.type == "modifiers":
            for mod in child.children:
                if mod.type == "class_modifier":
                    return mod.text.decode("utf-8")  # "data", "sealed", "annotation", "inner", "value"
        # проверить наличие "interface" среди анонимных токенов
        if child.type == "fun":
            return "fun_interface"

    return "class"
```

### Паттерн: поиск companion object
```python
def _find_companion(class_body_node):
    for child in class_body_node.children:
        if child.type == "companion_object":
            return child
    return None
```
