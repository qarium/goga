# Анализ отдельного документа

Область: применение правил уровня документа к одному DocumentRoot.
Аудитория: потребители, которым нужно валидировать отдельный документ манифеста.

## Минимальный пример

```python
from goga.ast.visitor import Visitor
from goga.ast.rules import ImportsCanNotBeEmpty, AllUsagesIsUsed

visitor = Visitor(document)
errors = visitor.analyze([
    ImportsCanNotBeEmpty(),
    AllUsagesIsUsed(),
])
```

Visitor принимает:
- `document` — `DocumentRoot` для анализа
- `rules` — список правил типа `DocumentRule`

Visitor оборачивает DocumentRoot в `DocumentNode` и вызывает `rule.check(node)` для каждого правила.
Результат — плоский список `DocumentRuleError`.

## Доступ к документу

```python
visitor = Visitor(document)

visitor.document  # DocumentRoot — документ, переданный при создании
```

## Использование с Factory

```python
from goga.ast.factory import Factory
from goga.ast.visitor import Visitor
from goga.ast.rules import SignatureIsValid, LocationIsRequired

factory = Factory("path/to/cell")
doc = factory.create()

visitor = Visitor(doc)
errors = visitor.analyze([
    SignatureIsValid(),
    LocationIsRequired(),
])

for error in errors:
    print(f"{error.rule}: {error.message}")
```
