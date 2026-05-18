# Правила валидации импортов

Область: правила, проверяющие корректность секции Imports в CODEMANIFEST.
Аудитория: потребители системы правил, нуждающиеся в валидации импортов.

## Доступные правила

### ImportsCanNotBeEmpty

Блок импортов не может быть пустым — каждый импорт должен содержать хотя бы Types и From.

```python
from goga.ast.rules.document.imports import ImportsCanNotBeEmpty
rule = ImportsCanNotBeEmpty()
```

### ImportsHasOnlyValidKeys

Каждый элемент Imports содержит только допустимые ключи: `Types`, `Usages`, `From`.

```python
from goga.ast.rules.document.imports import ImportsHasOnlyValidKeys
rule = ImportsHasOnlyValidKeys()
```

### ImportItemIsValid

Каждый элемент импорта содержит хотя бы один тип или практику (не пустая строка и не null).

```python
from goga.ast.rules.document.imports import ImportItemIsValid
rule = ImportItemIsValid()
```

### ImportUsageExists

Импортируемая практика существует по пути `{from_path}/.usages/{usage_name}.md`.

```python
from goga.ast.rules.document.imports import ImportUsageExists
rule = ImportUsageExists()
```

### ImportHasValidFromPath

Путь `From` существует на файловой системе, не пустой и не выходит за пределы CWD.

```python
from goga.ast.rules.document.imports import ImportHasValidFromPath
rule = ImportHasValidFromPath()
```

### ImportHasNotDuplicate

Все имена типов и практик уникальны в рамках всех импортов документа.

```python
from goga.ast.rules.document.imports import ImportHasNotDuplicate
rule = ImportHasNotDuplicate()
```

### ImportIsUsed

Каждый импортированный тип или практика используется хотя бы в одном месте документа:
- в аннотациях (заголовок, практики, типы, методы, свойства)
- в сигнатурах (entities, routines, methods) — только для типов

```python
from goga.ast.rules.document.imports import ImportIsUsed
rule = ImportIsUsed()
```

Встраивание (embedded) типа считается использованием.

## Вспомогательная функция

### signature_contains_type_name

```python
from goga.ast.rules.document.imports import signature_contains_type_name

result = signature_contains_type_name("(param: TypeName) -> void:null", "TypeName")
# True

result = signature_contains_type_name("(param: TypeNameOne)", "TypeName")
# False
```

Проверяет точное вхождение имени типа в сигнатуру. Допускаемые разделители вокруг имени: `:`, `>`, `(`, `)`, `[`, `]`, `,`, пробел или край строки.
