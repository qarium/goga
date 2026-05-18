# Навигация по дереву нод документа

Область: структура и обход дерева нод, представляющего разобранный CODEMANIFEST.
Аудитория: потребители, которым нужно читать и анализировать содержимое документа манифеста.

## Корневая нода — DocumentRoot

```python
from goga.ast.nodes import DocumentRoot

doc: DocumentRoot = factory.create()

# Доступ к секциям
doc.header      # HeaderNode
doc.body        # BodyNode
doc.footer      # FooterNode

# Метаинформация
doc.path        # относительный путь расположения документа
doc.children    # list[DocumentRoot] — вложенные документы

# Индексы
doc.types       # dict[str, list[Node]] — все типы документа
doc.links       # dict[str, list[Node]] — ссылки в аннотациях
doc.embeddings  # list[tuple[str, str]] — встроенные типы (name, from_path)
```

## Заголовок — HeaderNode

```python
header = doc.header

header.imports     # ImportsNode
header.usages      # UsagesNode
header.annotations # AnnotationsNode
header.types       # list[str] — имена импортированных типов
```

### Импорты

```python
imports = header.imports

imports.types   # list[ImportTypeItemNode]
imports.usages  # list[ImportUsageItemNode]

# Каждый импорт типа
for item in imports.types:
    item.type_name   # set[str] — имена типов
    item.from_path   # str — путь источника
    item.alias       # str — алиас (пустая строка если нет)

# Каждый импорт практики
for item in imports.usages:
    item.usage_name  # set[str] — имена практик
    item.from_path   # str — путь источника
    item.alias       # str — алиас (пустая строка если нет)
```

### Практики

```python
usages = header.usages

for item in usages.items:
    item.name        # str — имя практики
    item.annotations # AnnotationsNode — содержимое
```

## Тело — BodyNode

```python
body = doc.body

body.entities  # list[EntityTypeNode]
body.routines  # list[RoutineTypeNode]
```

### Сущность — EntityTypeNode

```python
for entity in body.entities:
    entity.name        # str
    entity.signature   # str — "(param: Type) -> result:Type"
    entity.location    # str — путь к файлу реализации
    entity.embedded    # bool — встроена из другого документа
    entity.mutations   # list[tuple[str, str]] — (base_name, source_path)
    entity.properties  # list[PropertyNode]
    entity.methods     # list[MethodNode]
    entity.annotations # AnnotationsNode
```

### Рутина — RoutineTypeNode

```python
for routine in body.routines:
    routine.name        # str
    routine.signature   # str
    routine.location    # str
    routine.embedded    # bool
    routine.annotations # AnnotationsNode
```

### Свойства и методы

```python
# Свойство
for prop in entity.properties:
    prop.name        # str
    prop.type        # str — тип данных
    prop.annotations # AnnotationsNode

# Метод
for method in entity.methods:
    method.name        # str
    method.signature   # str
    method.annotations # AnnotationsNode
```

## Аннотации — AnnotationsNode

```python
ann = entity.annotations

ann.text     # str — текст аннотации
ann.url      # str | None — URL практики
ann.filepath # str | None — путь к файлу практики
ann.links    # list[str] — извлечённые ссылки в обратных кавычках
```

У каждой аннотации заполнен ровно один из трёх: `text`, `url` или `filepath`.

## Подвал — FooterNode

```python
footer = doc.footer

footer.author      # str
footer.created_at  # str
footer.description # str
```

## Обход дерева документов

```python
def walk_tree(docs: list[DocumentRoot]):
    for doc in docs:
        yield doc
        yield from walk_tree(doc.children)
```

Каждый `DocumentRoot` может содержать вложенные документы в `children`.
