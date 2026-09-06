# Lint — Validation Rules

The implementation-side reference of the rules `goga lint` enforces.

Goga enforces validation rules across two scopes: document-level rules applied by the [Visitor](../../cell/ast/visitor.md) and tree-level rules applied by the [Analyzer](../../cell/ast/analyzer.md).

## Import Rules

Rules that validate the `imports` section of a CODEMANIFEST header.

| Rule | Scope | Description |
|---|---|---|
| `imports_can_not_be_empty` | Document | Requires that every document has an import block. |
| `imports_has_only_valid_keys` | Document | Ensures import items contain only `Types`, `Usages`, and `From` keys. |
| `import_item_is_valid` | Document | Validates that each import item is well-formed. |
| `import_has_not_duplicate` | Document | Ensures no duplicate entries exist in the import list. |
| `import_has_valid_from_path` | Document | Validates that the `From` path in imports is a valid source path. |
| `import_usage_exists` | Document | Checks that usage files referenced in imports exist on disk. |
| `import_is_used` | Document | Ensures all declared imports are actually referenced in the document body. |
| `import_type_exists` | Tree | Checks that every imported type exists somewhere in the project tree. |

## Usage Rules

Rules that validate the `usages` section of a CODEMANIFEST header.

| Rule | Scope | Description |
|---|---|---|
| `all_usages_is_used` | Document | Ensures all declared usages are referenced in the document body. |
| `usage_filepath_exists` | Document | Validates that file paths declared in usages exist on disk. |
| `usage_url_is_accessible` | Document | Checks that URLs declared in usages are reachable (results are cached). |
| `usage_links_has_not_conflicts` | Document | Ensures no naming conflicts exist among usage links. |

## Structure Rules

Rules that validate the `body` section -- entities, routines, their signatures, and locations.

| Rule | Scope | Description |
|---|---|---|
| `entities_and_routines_has_not_conflicts` | Document | Ensures entity and routine names do not collide. |
| `entity_has_only_valid_keys` | Document | Validates that entity declarations use only allowed keys. |
| `routine_has_only_valid_keys` | Document | Validates that routine declarations use only allowed keys. |
| `signature_is_valid` | Document | Checks that type signatures follow the expected format. |
| `location_is_required` | Document | Requires that every entity and routine specifies a source file location. |
| `return_type_has_link` | Document | Ensures return types in signatures have a corresponding link label. |

## Mutation Rules

Rules that validate mutation declarations on entities.

| Rule | Scope | Description |
|---|---|---|
| `mutation_exists` | Document | Checks that the base type for a mutation exists. |
| `mutation_is_valid` | Document | Validates that the mutation declaration is well-formed. |
| `embedded_entity_can_not_has_mutations` | Document | Ensures embedded entities do not declare mutations. |

## Annotation Rules

Rules that validate annotation declarations.

| Rule | Scope | Description |
|---|---|---|
| `annotation_links_exists` | Document | Ensures that links in annotations reference valid, existing types. |

## Tree-Level Rules

Rules that require cross-document context. These are applied by the [Analyzer](../../cell/ast/analyzer.md).

| Rule | Description |
|---|---|
| `imports_has_not_cyclical_deps` | Detects circular import chains between CODEMANIFEST documents. |
| `import_type_exists` | Ensures every imported type can be found somewhere in the full document tree. |
| `embedded_type_has_low_level` | Validates that embedded entities follow the correct hierarchy level relative to their parent. |

## Where to Next

- [AST Visitor](../../cell/ast/visitor.md) -- how document-level rules are applied.
- [AST Analyzer](../../cell/ast/analyzer.md) -- how tree-level rules are applied.
- [Error Handling](errors.md) -- the error types produced by rule violations.
