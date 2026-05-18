# Правила валидации мутаций и встраиваний

Область: правила, проверяющие корректность мутаций типов (синтаксис `::`) в CODEMANIFEST.
Аудитория: потребители системы правил, нуждающиеся в валидации мутаций.

## Доступные правила

### MutationExists

Базовый тип мутации должен существовать в одном из источников:
- имена entities в текущем документе
- имена routines в текущем документе
- типы, подключённые через Imports

```python
from goga.ast.rules.document.mutation import MutationExists
rule = MutationExists()
```

### MutationIsValid

Имя мутации не должно совпадать с именем самой сущности — тип не может мутировать из самого себя.

```python
from goga.ast.rules.document.mutation import MutationIsValid
rule = MutationIsValid()
```

### EmbeddedEntityCanNotHasMutations

Встроенная сущность (префикс `->`) не может определять мутации — встроенные типы подключаются как есть.

```python
from goga.ast.rules.document.mutation import EmbeddedEntityCanNotHasMutations
rule = EmbeddedEntityCanNotHasMutations()
```

## Пример валидного использования мутаций

```yaml
# В документе с Imports:
Imports:
  - Types:
      - BaseType
    From: other/cell

---

"BaseType::ConcreteType()":
  location: impl.py
  annotations: |
    Конкретизация BaseType
```

`BaseType` — существует в импортах, `ConcreteType` — не совпадает с `BaseType`. Правило соблюдено.
