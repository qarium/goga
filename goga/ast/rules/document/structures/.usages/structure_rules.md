# Правила валидации структур entity и routine

Область: правила, проверяющие корректность объявления типов (Entity, Routine) в теле CODEMANIFEST.
Аудитория: потребители системы правил, нуждающиеся в валидации структур документа.

## Доступные правила

### EntitiesAndRoutinesHasNotConflicts

Имена entities и routines не должны конфликтовать с именами импортированных типов.
Конфликт разрешается через алиас в Imports. Встраиваемые типы (embedded=True) — исключение.

```python
from goga.ast.rules.document.structures import EntitiesAndRoutinesHasNotConflicts
rule = EntitiesAndRoutinesHasNotConflicts()
```

### EntityHasOnlyValidKeys

Entity содержит только допустимые ключи: `location`, `annotations`, `methods`, `properties`.

```python
from goga.ast.rules.document.structures import EntityHasOnlyValidKeys
rule = EntityHasOnlyValidKeys()
```

### RoutineHasOnlyValidKeys

Routine содержит только допустимые ключи: `location`, `annotations`.

```python
from goga.ast.rules.document.structures import RoutineHasOnlyValidKeys
rule = RoutineHasOnlyValidKeys()
```

### SignatureIsValid

Сигнатура соответствует формату `(...) -> ...` или `(...)`.

```python
from goga.ast.rules.document.structures import SignatureIsValid
rule = SignatureIsValid()
```

### ReturnTypeHasLink

Возвращаемый тип в сигнатуре имеет семантическую метку: `-> label:Type`, а не просто `-> Type`.
Если сигнатура ничего не возвращает — это валидная ситуация.

```python
from goga.ast.rules.document.structures import ReturnTypeHasLink
rule = ReturnTypeHasLink()
```

Валидно: `"method() -> result:int"`, `"method()"` (нет возврата)
Невалидно: `"method() -> int"` (нет семантической метки)

### LocationIsRequired

Entity и routine содержат `location` — имя файла с расширением, без директорий.
Embedded типы пропускаются.

```python
from goga.ast.rules.document.structures import LocationIsRequired
rule = LocationIsRequired()
```

Валидно: `location: impl.py`
Невалидно: отсутствие location, `location: src/impl.py`, `location: noext`
