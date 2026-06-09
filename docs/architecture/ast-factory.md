# AST Factory

The factory is responsible for converting CODEMANIFEST YAML files into `DocumentRoot` AST trees. This page describes the factory API, the parsing process, and error handling.

## API

### Constructor

```python
Factory(path: str)
```

- `path` -- the root directory of the project. The factory scans this directory for CODEMANIFEST files.

### Creating a Tree

```python
Factory.create(parent: DocumentRoot | None = None) -> DocumentRoot
```

Builds a `DocumentRoot` tree from the CODEMANIFEST files found under the configured path.

- `parent` -- when `None`, the returned `DocumentRoot` is a top-level document. When a `DocumentRoot` is passed, the new document is registered as a child, supporting nested CODEMANIFEST structures.
- Returns a fully populated `DocumentRoot` with `header`, `body`, and `footer` nodes.

## Parsing Process

The factory performs the following steps:

1. **Locate files** -- scan the project path for CODEMANIFEST YAML files.
2. **Parse YAML** -- read each file using PyYAML and parse the content into a Python dictionary.
3. **Create header** -- build a `HeaderNode` from the `imports`, `usages`, and `annotations` sections.
4. **Create body** -- build a `BodyNode` from the `entities` and `routines` sections, creating nested `EntityTypeNode`, `RoutineTypeNode`, `MethodNode`, and `PropertyNode` instances.
5. **Create footer** -- build a `FooterNode` from the `author`, `created_at`, and `description` fields.
6. **Assemble tree** -- attach header, body, and footer to a new `DocumentRoot`, set parent references.
7. **Handle nesting** -- if a CODEMANIFEST references another CODEMANIFEST, the factory calls `create(parent=current_root)` recursively.

## Nested CODEMANIFEST Support

CODEMANIFEST files can reference other CODEMANIFEST files, forming a tree of documents. The `parent` parameter controls this relationship:

```
create(parent=None)          -> root DocumentRoot
  create(parent=root)        -> child DocumentRoot
    create(parent=child)     -> grandchild DocumentRoot
```

Each nested document maintains a `parent` reference to its containing document, enabling upward traversal during tree-level validation.

## Error Handling

### DocumentParseError

Raised when the YAML content contains unrecognized keys in the header or footer sections.

```python
DocumentParseError(message: str, filepath: str)
```

- `message` -- description of the parse failure.
- `filepath` -- path to the CODEMANIFEST file that caused the error.

The factory validates that header keys are limited to `imports`, `usages`, and `annotations`, and that footer keys are limited to `author`, `created_at`, and `description`. Any other keys trigger a `DocumentParseError`.

## Dependencies

| Dependency | Purpose |
|---|---|
| PyYAML | Parsing CODEMANIFEST YAML content into Python dictionaries. |

## Where to Next

- [AST Node Types](ast-nodes.md) -- the structure of the trees the factory produces.
- [AST Visitor](ast-visitor.md) -- how those trees are validated at the document level.
- [AST Analyzer](ast-analyzer.md) -- how the full tree is validated.
