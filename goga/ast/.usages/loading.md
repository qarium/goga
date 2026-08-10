# Loading and validating a CODEMANIFEST tree

Scope: Loading a project manifest tree and retrieving analysis results.
Audience: Consumers who need to load a CODEMANIFEST document tree and inspect validation errors.

## Minimal example

```python
from goga.ast import AST

ast = AST("path/to/project")
ast.load()
```

After `load()` completes, two properties are available:
- `ast.tree` — list of root documents (`DocumentRoot`), each potentially containing nested `children`
- `ast.errors` — list of validation errors (`DocumentRuleError` | `ASTRuleError`)

## Ignoring directories

Pass the optional `ignore` argument to skip directories by exact relative path
during traversal (consumers use it to honor a configured ignore list).
Glob patterns are not supported; matching is a strict relative-path equality and
is additive to the built-in `.project` skip.

```python
from goga.ast import AST

ast = AST("path/to/project", ignore=[".venv/", "build/dist"])
ast.load()
```

When `ignore` is omitted (or None), traversal is unfiltered — the default for
all consumers that do not opt in.

## Document lookup by path

```python
from goga.ast import AST

ast = AST("path/to/project")
ast.load()

doc = ast.document("path/to/project/some/cell")
```

The `document()` method accepts all path formats:
- Relative: `./some/cell`, `some/cell`
- Absolute: `/abs/path/to/project/some/cell`

Lookup runs in O(1). Raises `DocumentNotFoundError` if the document does not exist.

## Inspecting errors

```python
if ast.errors:
    for error in ast.errors:
        print(error)
```

Each error renders as a formatted string with rule name, document path, and offending node.
