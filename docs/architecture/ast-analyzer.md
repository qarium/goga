# AST Analyzer

The analyzer applies tree-level validation rules to the full list of `DocumentRoot` nodes. It handles cross-document checks that the [Visitor](ast-visitor.md) cannot perform on a single document in isolation.

## API

### Constructor

```python
Analyzer(tree: list[DocumentRoot])
```

- `tree` -- the complete list of `DocumentRoot` nodes produced by the [Factory](ast-factory.md). This represents all CODEMANIFEST files in the project.

### Running Analysis

```python
Analyzer.analyze(rules: list[ASTRule]) -> list[ASTRuleError]
```

- `rules` -- a list of `ASTRule` instances to apply.
- Returns a list of `ASTRuleError` for every rule violation found. An empty list means the tree passes all rules.

## Rule Contract

Each rule passed to the analyzer must implement the `ASTRule` interface:

```python
class ASTRule:
    def __init__(self, tree: list[DocumentRoot], name: str):
        self.tree = tree
        self.name = name

    def check(self, document: DocumentRoot) -> list[ASTRuleError]:
        ...
```

- The constructor receives the full tree and a human-readable rule name.
- The `check` method receives one `DocumentRoot` at a time but has access to the full tree through `self.tree`.
- It returns a list of `ASTRuleError` instances. Returning an empty list means no violations for that document.

## Execution Model

The analyzer iterates over every document in the tree and applies each rule:

```
for document in tree:
    for rule in rules:
        errors = rule.check(document)
        all_errors.extend(errors)
```

This means each rule is called once per document. Because the rule holds a reference to the full tree, it can look up other documents when checking relationships such as import resolution or type existence.

## When to Use the Analyzer vs the Visitor

| Situation | Use |
|---|---|
| Validate key names or structure within one file | Visitor |
| Check that imports reference types that exist in the project | Analyzer |
| Detect cyclic dependencies between CODEMANIFEST files | Analyzer |
| Validate embedding hierarchy across documents | Analyzer |
| Check signature format or entity keys locally | Visitor |

## Tree-Level Rules

The analyzer applies three tree-level rules:

| Rule | What It Checks |
|---|---|
| `ImportsHasNotCyclicalDeps` | No circular import chains between documents. |
| `ImportTypeExists` | Every imported type exists somewhere in the tree. |
| `EmbeddedTypeHasLowLevel` | Embedded entities follow the correct hierarchy level. |

See [Validation Rules](validation-rules.md) for the complete reference.

## Where to Next

- [AST Visitor](ast-visitor.md) -- single-document validation.
- [Validation Rules](validation-rules.md) -- full list of all rules, document-level and tree-level.
- [Error Handling](ast-errors.md) -- the `ASTRuleError` type.
