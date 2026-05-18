# Загрузка и валидация дерева CODEMANIFEST

Область: загрузка проекта манифестов и получение результатов анализа.
Аудитория: потребители, которым нужно загрузить CODEMANIFEST дерево и проверить его на ошибки.

## Минимальный пример

```python
from goga.ast import AST

ast = AST("path/to/project")
ast.load()
```

После вызова `load()` доступны два свойства:
- `ast.tree` — список корневых документов (`DocumentRoot`), каждый из которых может содержать вложенные `children`
- `ast.errors` — список ошибок (`DocumentRuleError` | `ASTRuleError`), найденных при валидации

## Поиск документа по пути

```python
from goga.ast import AST

ast = AST("path/to/project")
ast.load()

doc = ast.document("path/to/project/some/cell")
```

Метод `document()` принимает любой формат пути:
- относительный: `./some/cell`, `some/cell`
- полный: `/abs/path/to/project/some/cell`

Поиск выполняется за O(1). Если документ не найден — выбрасывается `DocumentNotFoundError`.

## Проверка наличия ошибок

```python
if ast.errors:
    for error in ast.errors:
        print(error)
```

Каждая ошибка приводится к строке с указанием правила, пути и проблемной ноды.
