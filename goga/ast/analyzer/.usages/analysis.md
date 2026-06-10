# Analyzing the document tree

Scope: Global validation across all documents in the AST tree.
Audience: Consumers who need to apply project-level validation rules to a loaded document tree.

## Minimal example

```python
from goga.ast.analyzer import Analyzer
from goga.ast.nodes import DocumentRoot

# tree: list[DocumentRoot] obtained from Factory or AST
analyzer = Analyzer(tree)
errors = analyzer.analyze(ast_rules)
```

Constructor parameters:
- `tree` — `list[DocumentRoot]`: flat list of all documents (including nested children)

`analyze()` parameters:
- `rules` — `list[ASTRule]`: tree-level rules to apply

Behavior: For each rule, `Analyzer` calls `rule.check(document)` on each document in the tree.
Returns a flat list of `ASTRuleError` instances.

## Relationship to Visitor

`Analyzer` and `Visitor` operate at different scopes:
- `Visitor` applies `DocumentRule` instances to individual documents
- `Analyzer` applies `ASTRule` instances across the entire tree

Recommended order: run `Visitor` on each document first, then run `Analyzer` on the full tree.
