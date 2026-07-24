# Entity and routine structure validation rules

Scope: Rules validating type declarations (Entity, Routine) in the CODEMANIFEST body section.
Audience: Consumers of the rule system performing structure validation.

## Available rules

### EntitiesAndRoutinesHasNotConflicts

Entity and routine names must not collide with imported type names.
Collisions are resolved via import aliases. Embedded types (embedded=True) are exempt.

```python
from goga.ast.rules.document.structures import EntitiesAndRoutinesHasNotConflicts

rule = EntitiesAndRoutinesHasNotConflicts()
```

### EntityHasOnlyValidKeys

Entity definitions must contain only: `location`, `annotations`, `methods`, `properties`.

```python
from goga.ast.rules.document.structures import EntityHasOnlyValidKeys

rule = EntityHasOnlyValidKeys()
```

### RoutineHasOnlyValidKeys

Routine definitions must contain only: `location`, `annotations`.

```python
from goga.ast.rules.document.structures import RoutineHasOnlyValidKeys

rule = RoutineHasOnlyValidKeys()
```

### SignatureIsValid

Signature must match the format `(...) -> ...` or `(...)`.

```python
from goga.ast.rules.document.structures import SignatureIsValid

rule = SignatureIsValid()
```

### ReturnTypeHasLink

Return type must include a semantic label: `-> label:Type` (not bare `-> Type`).
Signatures without a return type are valid.

```python
from goga.ast.rules.document.structures import ReturnTypeHasLink

rule = ReturnTypeHasLink()
```

Valid: `"method() -> result:int"`, `"method()"` (no return)
Invalid: `"method() -> int"` (missing semantic label)

### LocationIsRequired

Entity and routine must specify `location` as a filename with extension, without directory components.
Embedded types are skipped.

```python
from goga.ast.rules.document.structures import LocationIsRequired

rule = LocationIsRequired()
```

Valid: `location: impl.py`
Invalid: missing location, `location: src/impl.py`, `location: noext`
