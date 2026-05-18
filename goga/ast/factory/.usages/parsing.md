# Парсинг CODEMANIFEST в дерево нод

Область: создание дерева документа из YAML файла CODEMANIFEST.
Аудитория: потребители, которым нужно программно создать DocumentRoot из файла манифеста.

## Минимальный пример

```python
from goga.ast.factory import Factory

factory = Factory("path/to/cell")
document = factory.create()
```

`path` — путь до папки с файлом CODEMANIFEST относительно CWD.
Метод `create()` возвращает `DocumentRoot` с заполненными `header`, `body`, `footer`.

## Создание вложенного документа с родителем

```python
from goga.ast.factory import Factory

parent_factory = Factory("path/to/parent")
parent_doc = parent_factory.create()

child_factory = Factory("path/to/parent/child")
child_doc = child_factory.create(parent=parent_doc)
```

При передаче `parent` устанавливается связь между дочерним и родительским документами.

## Структура результата

После `create()` документ содержит:
- `document.header` — `HeaderNode` с `imports`, `usages`, `annotations`
- `document.body` — `BodyNode` с `entities` и `routines`
- `document.footer` — `FooterNode` с `author`, `created_at`, `description`
- `document.embeddings` — список `(type_name, from_path)` для встроенных типов
- `document.types` — словарь `{name: [nodes]}` всех типов в документе
- `document.links` — словарь `{link_name: [AnnotationsNode]}` всех ссылок в аннотациях

## Обработка ошибок парсинга

```python
from goga.ast.errors import DocumentParseError

try:
    document = factory.create()
except DocumentParseError as e:
    print(f"Ошибка в {e.filepath}: {e.message}")
```

Factory выбрасывает `DocumentParseError` при:
- неизвестных ключах в заголовке (допустимы только Imports, Usages, Annotations)
- неизвестных ключах в подвале (допустимы только Author, CreatedAt, Description)
