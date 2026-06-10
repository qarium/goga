# Analyzing a single document

Scope: Applying document-level validation rules to a single `DocumentRoot`.
Audience: Consumers who need to validate an individual manifest document.

## Minimal example

```python
from goga.ast.visitor import Visitor
from goga.ast.rules import ImportsCanNotBeEmpty, AllUsagesIsUsed

visitor = Visitor(document)
errors = visitor.analyze([
    ImportsCanNotBeEmpty(),
    AllUsagesIsUsed(),
])
```

Constructor parameters:
- `document` — `DocumentRoot`: the document to validate
- `rules` — `list[DocumentRule]`: the rules to apply

`Visitor` wraps the `DocumentRoot` in a `DocumentNode` and calls `rule.check(node)` for each rule.
Returns a flat list of `DocumentRuleError` instances.

## Accessing the document

```python
visitor = Visitor(document)

visitor.document  # DocumentRoot — the document passed at construction
```

## Integration with Factory

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
