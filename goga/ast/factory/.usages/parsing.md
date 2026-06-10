# Parsing CODEMANIFEST into a node tree

Scope: Constructing a `DocumentRoot` tree from a CODEMANIFEST YAML file.
Audience: Consumers who need to programmatically create a `DocumentRoot` from a manifest file.

## Minimal example

```python
from goga.ast.factory import Factory

factory = Factory("path/to/cell")
document = factory.create()
```

`path` — path to the directory containing the CODEMANIFEST file, relative to CWD.
`create()` returns a fully populated `DocumentRoot` with `header`, `body`, and `footer`.

## Creating a nested document with a parent reference

```python
from goga.ast.factory import Factory

parent_factory = Factory("path/to/parent")
parent_doc = parent_factory.create()

child_factory = Factory("path/to/parent/child")
child_doc = child_factory.create(parent=parent_doc)
```

Passing `parent` establishes the parent-child relationship between documents.

## Result structure

After `create()`, the document exposes:
- `document.header` — `HeaderNode` with `imports`, `usages`, `annotations`
- `document.body` — `BodyNode` with `entities` and `routines`
- `document.footer` — `FooterNode` with `author`, `created_at`, `description`
- `document.embeddings` — list of `(type_name, from_path)` tuples for embedded types
- `document.types` — dictionary `{name: [nodes]}` of all document types
- `document.links` — dictionary `{link_name: [AnnotationsNode]}` of all annotation links

## Parsing error handling

```python
from goga.ast.errors import DocumentParseError

try:
    document = factory.create()
except DocumentParseError as e:
    print(f"Error in {e.filepath}: {e.message}")
```

`Factory` raises `DocumentParseError` on:
- Unknown keys in header (allowed: Imports, Usages, Annotations)
- Unknown keys in footer (allowed: Author, CreatedAt, Description)
