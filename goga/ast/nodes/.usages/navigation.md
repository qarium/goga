# Navigating the document node tree

Scope: Structure and traversal of the node tree representing a parsed CODEMANIFEST.
Audience: Consumers who need to read and analyze the contents of a manifest document.

## Root node — DocumentRoot

`DocumentRoot` is the top-level container for a parsed CODEMANIFEST document.

```python
from goga.ast.nodes import DocumentRoot

doc: DocumentRoot = factory.create()

# Section accessors
doc.header  # HeaderNode
doc.body  # BodyNode
doc.footer  # FooterNode

# Metadata
doc.path  # str — relative path to the document's directory
doc.children  # list[DocumentRoot] — nested child documents

# Indexes
doc.types  # dict[str, list[Node]] — maps type names to their nodes
doc.links  # dict[str, list[Node]] — maps link names to their AnnotationsNode occurrences
doc.embeddings  # list[tuple[str, str]] — embedded types as (type_name, from_path) tuples
```

## Header — HeaderNode

`HeaderNode` contains imports, usages, and annotations.

```python
header = doc.header

header.imports  # ImportsNode
header.usages  # UsagesNode
header.annotations  # AnnotationsNode
header.types  # list[str] — names of all imported types
```

### Imports

`ImportsNode` holds type and usage import items.

```python
imports = header.imports

imports.types  # list[ImportTypeItemNode]
imports.usages  # list[ImportUsageItemNode]

# Each ImportTypeItemNode
for item in imports.types:
    item.type_name  # set[str] — names of imported types
    item.from_path  # str — source document path
    item.alias  # str — alias (empty string if no alias)

# Each ImportUsageItemNode
for item in imports.usages:
    item.usage_name  # set[str] — names of imported usages
    item.from_path  # str — source document path
    item.alias  # str — alias (empty string if no alias)
```

### Usages

`UsagesNode` holds usage declarations.

```python
usages = header.usages

for item in usages.items:
    item.name  # str — usage name
    item.annotations  # AnnotationsNode — usage content
```

## Body — BodyNode

`BodyNode` contains entity and routine type definitions.

```python
body = doc.body

body.entities  # list[EntityTypeNode]
body.routines  # list[RoutineTypeNode]
```

### Entity — EntityTypeNode

`EntityTypeNode` represents a type with properties, methods, and optional mutations.

```python
for entity in body.entities:
    entity.name  # str
    entity.signature  # str — e.g. "(param: Type) -> result:Type"
    entity.location  # str — implementation file path
    entity.embedded  # bool — True if embedded from another document
    entity.mutations  # list[tuple[str, str]] — (base_type_name, source_document_path)
    entity.properties  # list[PropertyNode]
    entity.methods  # list[MethodNode]
    entity.annotations  # AnnotationsNode
```

### Routine — RoutineTypeNode

`RoutineTypeNode` represents a function-like type with signature and location.

```python
for routine in body.routines:
    routine.name  # str
    routine.signature  # str
    routine.location  # str
    routine.embedded  # bool
    routine.annotations  # AnnotationsNode
```

### Properties and methods

```python
# PropertyNode
for prop in entity.properties:
    prop.name  # str
    prop.type  # str — data type
    prop.annotations  # AnnotationsNode

# MethodNode
for method in entity.methods:
    method.name  # str
    method.signature  # str
    method.annotations  # AnnotationsNode
```

## Annotations — AnnotationsNode

`AnnotationsNode` holds documentation text with optional links.

```python
ann = entity.annotations

ann.text  # str — inline annotation text
ann.url  # str | None — URL of the linked usage
ann.filepath  # str | None — file path of the linked usage
ann.links  # list[str] — extracted link names enclosed in backticks
```

Invariant: exactly one of `text`, `url`, or `filepath` is non-None per `AnnotationsNode`.

## Footer — FooterNode

`FooterNode` contains document metadata.

```python
footer = doc.footer

footer.author  # str
footer.created_at  # str
footer.description  # str
```

## Traversing the document tree

```python
def walk_tree(docs: list[DocumentRoot]):
    for doc in docs:
        yield doc
        yield from walk_tree(doc.children)
```

Each `DocumentRoot` may contain nested `DocumentRoot` instances in `children`.
