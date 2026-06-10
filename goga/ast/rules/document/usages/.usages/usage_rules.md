# Usage (Usages) validation rules

Scope: Rules validating the `Usages` section in CODEMANIFEST documents.
Audience: Consumers of the rule system performing usage validation.

## Available rules

### AllUsagesIsUsed

Every declared usage must be referenced in at least one annotation node.

```python
from goga.ast.rules.document.usages import AllUsagesIsUsed
rule = AllUsagesIsUsed()
```

Search scope: annotations on `HeaderNode`, `UsageItemNode`, `EntityTypeNode`, `RoutineTypeNode`, `MethodNode`, `PropertyNode`.

### UsageFilepathExists

Usage filepath validation:
- Path is resolved relative to project root (CWD)
- Path must include the `.goga/usages/` prefix
- File must exist on disk

```python
from goga.ast.rules.document.usages import UsageFilepathExists
rule = UsageFilepathExists()
```

Inline usages (`annotations.text`) and URL usages (`annotations.url`) are skipped.

### UsageUrlIsAccessible

Usage URL must respond with HTTP 200.

```python
from goga.ast.rules.document.usages import UsageUrlIsAccessible
rule = UsageUrlIsAccessible()
```

- Uses HEAD request with GET fallback
- Timeout: 10 seconds
- Network errors produce validation errors
- Inline and filepath usages are skipped
- URL validation results are cached per rule instance — duplicate URLs do not trigger additional network requests
- Reuse the rule instance across documents for optimal performance (matching linter behavior)

### UsageLinksHasNotConflicts

Usage names must not conflict with:
- Imported type names (resolvable via alias)
- Entity and routine names in the document body

```python
from goga.ast.rules.document.usages import UsageLinksHasNotConflicts
rule = UsageLinksHasNotConflicts()
```

## Correct usage example

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  pattern: |
    Inline pattern text

Annotations: |
  Use `conventions` for style.
  Use `pattern` for implementation.
```

Both usages (`conventions`, `pattern`) are referenced in annotations — rule `AllUsagesIsUsed` passes.
