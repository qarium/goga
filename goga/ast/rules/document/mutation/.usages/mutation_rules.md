# Mutation and embedding validation rules

Scope: Rules validating type mutation declarations (`::` syntax) in CODEMANIFEST.
Audience: Consumers of the rule system performing mutation validation.

## Available rules

### MutationExists

The base type of each mutation must exist in one of:
- Entity names in the current document
- Routine names in the current document
- Types imported via `Imports`

```python
from goga.ast.rules.document.mutation import MutationExists
rule = MutationExists()
```

### MutationIsValid

The mutation name must differ from the entity name — a type cannot mutate from itself.

```python
from goga.ast.rules.document.mutation import MutationIsValid
rule = MutationIsValid()
```

### EmbeddedEntityCanNotHasMutations

Embedded entities (declared with `->` prefix) must not define mutations. Embedded types are imported as-is.

```python
from goga.ast.rules.document.mutation import EmbeddedEntityCanNotHasMutations
rule = EmbeddedEntityCanNotHasMutations()
```

## Valid mutation example

```yaml
# In a document with imports:
Imports:
  - Types:
      - BaseType
    From: other/cell

---

"BaseType::ConcreteType()":
  location: impl.py
  annotations: |
    BaseType specialization
```

Validation: `BaseType` exists in imports, `ConcreteType` differs from `BaseType`. All rules pass.
