# Работа с ошибками CODEMANIFEST

Область: обработка ошибок при парсинге и валидации манифестов.
Аудитория: потребители, которым нужно перехватывать, логировать или отображать ошибки AST.

## Иерархия ошибок

```
BaseASTError (Exception)
├── DocumentNotFoundError     — документ не найден по пути
├── DocumentParseError        — ошибка при разборе YAML
└── DocumentRuleError         — нарушение правила документа
    └── (наследуется от BaseASTError)
ASTRuleError                  — нарушение правила уровня дерева
    └── (наследуется от BaseASTError)
```

Все ошибки имеют свойство `message` с текстом ошибки.

## DocumentRuleError — ошибка правила документа

```python
error = errors[0]  # из Visitor.analyze()
print(error.message)   # текст ошибки
print(error.rule)      # имя нарушенного правила
print(error.document)  # DocumentRoot документа
print(error.node)      # проблемная нода (DocumentNode)
print(str(error))      # форматированный вывод
```

Строковое представление:
```
Error: <message>
Rule: <rule>
Path: <document path without filename>
Node:
  <beautiful node data>
```

## ASTRuleError — ошибка правила дерева

```python
error = ast_errors[0]  # из Analyzer.analyze()
print(error.message)   # текст ошибки
print(error.rule)      # имя нарушенного правила
print(error.document)  # DocumentRoot | None
print(error.node)      # DocumentNode | None
print(str(error))      # форматированный вывод
```

`document` и `node` могут быть `None`, так как правило может не привязываться к конкретному документу.

## DocumentParseError — ошибка парсинга

```python
try:
    factory.create()
except DocumentParseError as e:
    print(e.message)    # описание ошибки
    print(e.filepath)   # путь к файлу CODEMANIFEST
```

Выбрасывается Factory при обнаружении неизвестных ключей в заголовке или подвале.

## DocumentNotFoundError — документ не найден

```python
from goga.ast.errors import DocumentNotFoundError

try:
    doc = ast.document("nonexistent/path")
except DocumentNotFoundError as e:
    print(e.message)  # "Document not found for path: nonexistent/path"
```
