# AST tree-level rules

Scope: Rules that validate cross-document relationships across the entire project.
Audience: Consumers applying global manifest validation.

## Available rules

### ImportsHasNotCyclicalDeps

Validates that no cyclic import dependencies exist between documents.

```python
from goga.ast.rules.ast import ImportsHasNotCyclicalDeps

rule = ImportsHasNotCyclicalDeps(tree)
errors = rule.check(document)
```

A cycle occurs when document A imports from document B, and document B also imports from document A.

### ImportTypeExists

Validates that each imported type exists in the document specified by the `From` path.

```python
from goga.ast.rules.ast import ImportTypeExists

rule = ImportTypeExists(tree)
errors = rule.check(document)
```

If the `From` path does not exist on disk, the rule skips validation for that import item.

### EmbeddedTypeHasLowLevel

Validates that embedded types reside deeper in the filesystem hierarchy than their parent document.

```python
from goga.ast.rules.ast import EmbeddedTypeHasLowLevel

rule = EmbeddedTypeHasLowLevel(tree)
errors = rule.check(document)
```

Valid: document at `level-1/` embeds a type from `level-1/level-2/`.
Valid: document at the repository root (`.`) embeds a type from any nested package.
Invalid: document at `level-1/level-2/` embeds a type from `level-1/`.
