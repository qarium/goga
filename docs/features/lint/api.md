# Lint — API

The facade of the domain package **`goga.ast`** — the parse-and-validate surface behind `goga lint`.

The signature below is the CODEMANIFEST contract of the cell.

```python
AST(path: str, ignore: list[str] | None = None)
```

Load the project tree rooted at `path` and validate it: parse every `CODEMANIFEST`, apply the document-level rules to each document, then the tree-level rules across the import graph. `ignore` — directory relative paths pruned from traversal (the `lint.ignore` configuration). The violations surface as the AST error types — `DocumentParseError` for structural YAML/DSL failures, `DocumentRuleError` for document-level rule violations, `ASTRuleError` for tree-level ones (see [Architecture — Error Handling](../../architecture/ast-errors.md)).

The parse product is the same tree the [Contract](../contract/api.md) and [Schema](../schema/api.md) domains consume, and the one injected into a tool's keyword-capable `ast` parameter (see [Tools — CLI](../tools/cli.md#optional-injections)).

## Example

```python
from goga.ast import AST

tree = AST(path=".", ignore=[".venv"])
print(tree)  # the validated document tree
```
