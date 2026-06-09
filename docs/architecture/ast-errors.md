# Error Handling

Goga uses a structured error hierarchy for AST validation. Every error carries context about where and why it occurred, making CLI output actionable.

## Error Hierarchy

```
BaseASTError
 ├── DocumentNotFoundError
 ├── DocumentParseError
 ├── DocumentRuleError
 └── ASTRuleError
```

## Error Types

### BaseASTError

Base class for all AST errors.

| Property | Type | Description |
|---|---|---|
| `message` | `str` | Human-readable description of the error. |

All other AST errors inherit from `BaseASTError`.

### DocumentNotFoundError

Raised when a referenced document cannot be found in the tree.

| Property | Type | Description |
|---|---|---|
| `message` | `str` | Description of the lookup failure. |

This error typically occurs when an import or usage references a file that does not exist in the project.

### DocumentParseError

Raised when YAML parsing fails or when the document contains unrecognized keys.

| Property | Type | Description |
|---|---|---|
| `message` | `str` | Description of the parse failure. |
| `filepath` | `str` | Path to the CODEMANIFEST file that caused the error. |

The [Factory](ast-factory.md) raises this error when it encounters keys outside the allowed set in header or footer sections.

### DocumentRuleError

Raised when a document-level rule is violated. Produced by the [Visitor](ast-visitor.md).

| Property | Type | Description |
|---|---|---|
| `message` | `str` | Description of the rule violation. |
| `rule` | `str` | Name of the rule that was violated. |
| `document` | `DocumentRoot` | The document where the violation was found. |
| `node` | `Node` | The specific AST node that caused the violation, if applicable. |

### ASTRuleError

Raised when a tree-level rule is violated. Produced by the [Analyzer](ast-analyzer.md).

| Property | Type | Description |
|---|---|---|
| `message` | `str` | Description of the rule violation. |
| `rule` | `str` | Name of the rule that was violated. |
| `document` | `DocumentRoot` | The document where the violation was found. |
| `node` | `Node` | The specific AST node that caused the violation, if applicable. |

## Formatted Output

Each error type provides a formatted string representation suitable for CLI output. Errors include:

- The rule name that was violated.
- The file path of the offending document.
- The node location when available, pointing to the specific declaration.
- The human-readable message explaining what is wrong.

This formatting ensures that developers can quickly identify and fix issues reported by goga.

## Where to Next

- [AST Visitor](ast-visitor.md) -- produces `DocumentRuleError`.
- [AST Analyzer](ast-analyzer.md) -- produces `ASTRuleError`.
- [Validation Rules](validation-rules.md) -- the rules that generate these errors.
