# CODEMANIFEST error handling

Scope: Error types raised during parsing and validation of CODEMANIFEST documents.
Audience: Consumers who need to catch, log, or display AST errors.

## Error hierarchy

```
BaseASTError (Exception)
├── DocumentNotFoundError     — no document found at the given path
├── DocumentParseError        — invalid YAML structure in CODEMANIFEST
└── DocumentRuleError         — a document-level rule was violated
    └── (inherits from BaseASTError)
ASTRuleError                  — a tree-level rule was violated
    └── (inherits from BaseASTError)
```

All error types expose a `message` property containing the error description.

## DocumentRuleError — document rule violation

```python
error = errors[0]  # obtained from Visitor.analyze()
error.message   # str — error description
error.rule      # str — name of the violated rule
error.document  # DocumentRoot — source document
error.node      # DocumentNode — offending node
str(error)      # str — formatted multi-line output
```

String representation format:
```
Error: <message>
Rule: <rule>
Path: <document path without filename>
Node:
  <beautiful node data>
```

## ASTRuleError — tree rule violation

```python
error = ast_errors[0]  # obtained from Analyzer.analyze()
error.message   # str — error description
error.rule      # str — name of the violated rule
error.document  # DocumentRoot | None — source document (may be None)
error.node      # DocumentNode | None — offending node (may be None)
str(error)      # str — formatted multi-line output
```

Properties `document` and `node` may be `None` because tree-level rules are not always bound to a specific document.

## DocumentParseError — YAML parsing error

```python
try:
    factory.create()
except DocumentParseError as e:
    e.message    # str — error description
    e.filepath   # str — path to the CODEMANIFEST file
```

`Factory` raises `DocumentParseError` when it encounters unknown keys in the header or footer sections.

## DocumentNotFoundError — document lookup failure

```python
from goga.ast.errors import DocumentNotFoundError

try:
    doc = ast.document("nonexistent/path")
except DocumentNotFoundError as e:
    e.message  # "Document not found for path: nonexistent/path"
```
