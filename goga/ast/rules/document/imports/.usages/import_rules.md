# Import validation rules

Scope: Rules validating the correctness of the `Imports` section in CODEMANIFEST documents.
Audience: Consumers of the rule system performing import validation.

## Available rules

### ImportsCanNotBeEmpty

The `Imports` block must not be empty — each import entry must contain at least `Types` and `From`.

```python
from goga.ast.rules.document.imports import ImportsCanNotBeEmpty

rule = ImportsCanNotBeEmpty()
```

### ImportsHasOnlyValidKeys

Each import item must contain only the keys `Types`, `Usages`, `From`.

```python
from goga.ast.rules.document.imports import ImportsHasOnlyValidKeys

rule = ImportsHasOnlyValidKeys()
```

### ImportItemIsValid

Each import item must declare at least one type or usage. Empty strings and null values are invalid.

```python
from goga.ast.rules.document.imports import ImportItemIsValid

rule = ImportItemIsValid()
```

### ImportUsageExists

Each imported usage file must exist at `{from_path}/.usages/{usage_name}.md`.

```python
from goga.ast.rules.document.imports import ImportUsageExists

rule = ImportUsageExists()
```

### ImportHasValidFromPath

The `From` path must: exist on disk, be non-empty, and not escape the CWD boundary.

```python
from goga.ast.rules.document.imports import ImportHasValidFromPath

rule = ImportHasValidFromPath()
```

### ImportHasNotDuplicate

All type names and usage names must be unique across all import entries in the document.

```python
from goga.ast.rules.document.imports import ImportHasNotDuplicate

rule = ImportHasNotDuplicate()
```

### ImportIsUsed

Each imported type or usage must be referenced in at least one of the following locations:
- Annotations: header annotations, usage annotations, entity annotations, routine annotations, method annotations, property annotations
- Signatures: entity signatures, routine signatures, method signatures (types only)
- Mutations: entity mutations in `body[*].mutations` (types only)

```python
from goga.ast.rules.document.imports import ImportIsUsed

rule = ImportIsUsed()
```

Note: embedded type references count as usage and do not trigger this rule.

## Utility function

### signature_contains_type_name

```python
from goga.ast.rules.document.imports import signature_contains_type_name

result = signature_contains_type_name("(param: TypeName) -> void:null", "TypeName")
# True

result = signature_contains_type_name("(param: TypeNameOne)", "TypeName")
# False
```

Returns `True` if `type_name` appears as a whole word in `signature`. Allowed boundary characters: `:`, `>`, `(`, `)`, `[`, `]`, `,`, whitespace, or string edge.

A three-dot prefix before `type_name` is also accepted as a left boundary, so dynamic CODEMANIFEST parameters (e.g. `...args`, `...kwargs`) match by their bare name:

```python
result = signature_contains_type_name("(...args: TypeName)", "args")
# True

result = signature_contains_type_name("(x: foo.args)", "args")
# False — dots inside a type name are not the dynamic-parameter prefix
```
