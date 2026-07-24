# AST Visitor

The visitor applies document-level validation rules to a single `DocumentRoot`. It is complementary to the [Analyzer](ast-analyzer.md), which handles tree-level rules.

## API

### Constructor

```python
Visitor(document: DocumentRoot)
```

- `document` -- a single `DocumentRoot` to validate. The visitor operates on one document at a time.

### Running Analysis

```python
Visitor.analyze(rules: list[DocumentRule]) -> list[DocumentRuleError]
```

- `rules` -- a list of `DocumentRule` instances to apply.
- Returns a list of `DocumentRuleError` for every rule violation found. An empty list means the document passes all rules.

## Rule Contract

Each rule passed to the visitor must implement the `DocumentRule` interface:

```python
class DocumentRule:
    def check(self, document: DocumentRoot) -> list[DocumentRuleError]: ...
```

- The `check` method receives the `DocumentRoot` being validated.
- It returns a list of `DocumentRuleError` instances. Returning an empty list means no violations.
- Rules can inspect any part of the document: header, body, footer, and all nested nodes.

## Execution Model

The visitor iterates over the provided rules and calls `check()` on each:

```
for rule in rules:
    errors = rule.check(document)
    all_errors.extend(errors)
```

Rules are applied independently -- the output of one rule does not affect another. The visitor collects all errors from all rules before returning.

## Complementary to Analyzer

| Component | Scope | Rule Base Class | Error Type |
|---|---|---|---|
| Visitor | Single document | `DocumentRule` | `DocumentRuleError` |
| Analyzer | Full tree | `ASTRule` | `ASTRuleError` |

Use the visitor for rules that can be checked within one CODEMANIFEST file (imports format, entity structure, signature validity). Use the analyzer for rules that need cross-document context (cyclic imports, type existence, embedding hierarchy).

## Where to Next

- [AST Analyzer](ast-analyzer.md) -- tree-level validation.
- [Validation Rules](validation-rules.md) -- full list of document-level rules applied by the visitor.
- [Error Handling](ast-errors.md) -- the `DocumentRuleError` type.
