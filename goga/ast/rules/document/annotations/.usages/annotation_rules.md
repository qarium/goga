# Annotation validation rules

Scope: Rules validating that backtick-enclosed links in CODEMANIFEST annotations resolve to existing entities.
Audience: Consumers of the rule system performing annotation validation.

## AnnotationLinksExists

Validates that every link enclosed in backticks within annotations resolves to an existing entity in the document.

```python
from goga.ast.rules.document.annotations import AnnotationLinksExists

rule = AnnotationLinksExists()
```

A link resolves if it matches any of:
- A type name or alias declared in `Imports`
- A usage name declared in `Usages`
- An entity name or routine name in the document body
- A parameter name in the type signature (applicable to `EntityTypeNode`, `RoutineTypeNode`, `MethodNode`)

The rule checks annotations on the following node types:
- `HeaderNode` (global annotations)
- `UsageItemNode` (usage entries)
- `EntityTypeNode`, `RoutineTypeNode` (type definitions)
- `MethodNode`, `PropertyNode` (members)

## Error format

On unresolved link:
```
Link `{link}` in {context} annotation does not match any import, usage, entity, routine, or signature parameter
```
