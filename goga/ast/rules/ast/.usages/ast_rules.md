# Правила уровня AST-дерева

Область: правила, проверяющие связи между документами в рамках всего проекта.
Аудитория: потребители, применяющие глобальную валидацию манифестов.

## Доступные правила

### ImportsHasNotCyclicalDeps

Проверяет отсутствие циклических зависимостей между документами.

```python
from goga.ast.rules.ast import ImportsHasNotCyclicalDeps

rule = ImportsHasNotCyclicalDeps(tree)
errors = rule.check(document)
```

Циклом считается ситуация, когда документ A импортирует из документа B, а документ B импортирует из документа A.

### ImportTypeExists

Проверяет, что импортируемый тип существует в целевом документе.

```python
from goga.ast.rules.ast import ImportTypeExists

rule = ImportTypeExists(tree)
errors = rule.check(document)
```

Если путь в `From` не существует на файловой системе, проверка для этого импорта пропускается.

### EmbeddedTypeHasLowLevel

Проверяет, что встраиваемые типы находятся ниже в иерархии файловой системы.

```python
from goga.ast.rules.ast import EmbeddedTypeHasLowLevel

rule = EmbeddedTypeHasLowLevel(tree)
errors = rule.check(document)
```

Допустимо: `level-1/` встраивает тип из `level-1/level-2/`.
Недопустимо: `level-1/level-2/` встраивает тип из `level-1/`.
