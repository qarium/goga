# AST Node Types

Every CODEMANIFEST file is represented as a tree of AST nodes. This page documents the node hierarchy, the properties each node exposes, and how nodes relate to one another.

## Node Hierarchy

```
DocumentRoot
 ├── HeaderNode
 │    ├── ImportsNode
 │    ├── UsagesNode
 │    └── AnnotationsNode
 ├── BodyNode
 │    ├── EntityTypeNode
 │    │    ├── MethodNode
 │    │    └── PropertyNode
 │    └── RoutineTypeNode
 └── FooterNode
```

## Common Properties

Every node in the tree shares two properties:

| Property | Type | Description |
|---|---|---|
| `parent` | `Node or None` | Reference to the containing node. `DocumentRoot` has `parent=None` unless it is a nested CODEMANIFEST. |
| `data` | `dict` | Raw parsed data from the YAML source for this section. |

These properties enable upward navigation from any node to the root, and downward traversal through children.

## Node Reference

### DocumentRoot

The top-level node representing a single CODEMANIFEST file.

| Property | Type | Description |
|---|---|---|
| `header` | `HeaderNode` | Imports, usages, and annotations. |
| `body` | `BodyNode` | Entity and routine declarations. |
| `footer` | `FooterNode` | Author, created_at, description. |
| `parent` | `DocumentRoot or None` | Set when this document is a nested CODEMANIFEST. |

### HeaderNode

Contains declaration metadata that affects how the rest of the document is interpreted.

| Property | Type | Description |
|---|---|---|
| `imports` | `ImportsNode` | External type and usage imports. |
| `usages` | `UsagesNode` | Declared usages (files, URLs). |
| `annotations` | `AnnotationsNode` | Annotations applied to the document. |

### BodyNode

Holds the actual contract declarations.

| Property | Type | Description |
|---|---|---|
| `entities` | `list[EntityTypeNode]` | Entity type declarations. |
| `routines` | `list[RoutineTypeNode]` | Routine declarations. |

### FooterNode

Metadata about the document itself.

| Property | Type | Description |
|---|---|---|
| `author` | `str` | Document author. |
| `created_at` | `str` | Creation timestamp. |
| `description` | `str` | Human-readable description. |

### EntityTypeNode

Represents an entity type with its methods, properties, signature, and source location.

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Entity type name. |
| `methods` | `list[MethodNode]` | Methods defined on the entity. |
| `properties` | `list[PropertyNode]` | Properties of the entity. |
| `signature` | `str` | Type signature string. |
| `location` | `str` | File path in the source code. |

### RoutineTypeNode

Represents a standalone routine (function).

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Routine name. |
| `signature` | `str` | Function signature string. |
| `location` | `str` | File path in the source code. |

### MethodNode

A method belonging to an entity.

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Method name. |
| `signature` | `str` | Method signature string. |
| `annotations` | `list` | Annotations on the method. |

### PropertyNode

A property belonging to an entity.

| Property | Type | Description |
|---|---|---|
| `name` | `str` | Property name. |
| `signature` | `str` | Property type signature. |
| `annotations` | `list` | Annotations on the property. |

### ImportsNode

Declares external types and modules imported by the document.

Contains import items with keys: `Types`, `Usages`, `From`.

### UsagesNode

Declares file paths and URLs that the document references.

### AnnotationsNode

Annotations attached at the document level.

## Navigation

Parent-child relationships enable full tree traversal:

- **Downward**: from `DocumentRoot` through `header` / `body` / `footer` to individual entities, methods, and properties.
- **Upward**: from any node, follow `parent` references back to the `DocumentRoot`.
- **Sibling**: entities within `BodyNode.entities` or methods within `EntityTypeNode.methods` are siblings at the same level.

This structure allows validation rules to navigate from an error location up to the document root for context, or down from the root to inspect specific declarations.
