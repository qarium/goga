# Creating custom validation rules

Scope: Extending the validation system by subclassing base rule types.
Audience: Developers who need to add new validation rules.

## DocumentRule — per-document rule base class

Subclass `DocumentRule` to validate a single document in isolation.

```python
from goga.ast.rules.base import DocumentRule
from goga.ast.errors import DocumentRuleError


class MyCustomRule(DocumentRule):
    def __init__(self, name: str = "my_custom_rule"):
        super().__init__(name)

    def check(self, node):
        errors = []
        # `node` is a DocumentNode wrapping the DocumentRoot
        # `node.root` is the underlying DocumentRoot
        document = node.root

        # Validation logic...
        if some_violation:
            errors.append(
                DocumentRuleError(
                    message="Description of error",
                    rule=self.name,
                    document=document,
                    node=problematic_node,
                )
            )

        return errors
```

Method `check(node)` receives a `DocumentNode` wrapper and must return `list[DocumentRuleError]`.
Access the underlying `DocumentRoot` via `node.root`.

## ASTRule — tree-wide rule base class

Subclass `ASTRule` to validate documents in the context of the entire tree.

```python
from goga.ast.rules.base import ASTRule
from goga.ast.errors import ASTRuleError


class MyGlobalRule(ASTRule):
    def __init__(self, tree, name: str = "my_global_rule"):
        super().__init__(tree, name)

    def check(self, document):
        errors = []
        # `document` is the DocumentRoot being checked
        # `self.tree` is list[DocumentRoot] — the full document tree

        # Validation logic...
        if some_violation:
            errors.append(
                ASTRuleError(
                    message="Description of error",
                    rule=self.name,
                    document=document,
                    node=problematic_node,
                )
            )

        return errors
```

Method `check(document)` is called once per document in the tree.
Access the full tree via `self.tree`.

## Choosing a base class

- **DocumentRule**: use when the rule validates a single document without needing data from other documents (e.g., structure checks, key validation, local reference resolution).
- **ASTRule**: use when the rule requires visibility into other documents in the tree (e.g., cycle detection, cross-document references, hierarchy enforcement).
