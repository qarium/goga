# Validation Rules Reference

Goga enforces 21 validation rules across two scopes: 18 document-level rules applied by the [Visitor](ast-visitor.md) and 3 tree-level rules applied by the [Analyzer](ast-analyzer.md).

## Import Rules (8)

Rules that validate the `imports` section of a CODEMANIFEST header.

| Rule | Scope | Description |
|---|---|---|
| `ImportsCanNotBeEmpty` | Document | Requires that every document has an import block. |
| `ImportsHasOnlyValidKeys` | Document | Ensures import items contain only `Types`, `Usages`, and `From` keys. |
| `ImportItemIsValid` | Document | Validates that each import item is well-formed. |
| `ImportHasNotDuplicate` | Document | Ensures no duplicate entries exist in the import list. |
| `ImportHasValidFromPath` | Document | Validates that the `From` path in imports is a valid source path. |
| `ImportUsageExists` | Document | Checks that usage files referenced in imports exist on disk. |
| `ImportIsUsed` | Document | Ensures all declared imports are actually referenced in the document body. |
| `ImportTypeExists` | Tree | Checks that every imported type exists somewhere in the project tree. |

## Usage Rules (4)

Rules that validate the `usages` section of a CODEMANIFEST header.

| Rule | Scope | Description |
|---|---|---|
| `AllUsagesIsUsed` | Document | Ensures all declared usages are referenced in the document body. |
| `UsageFilepathExists` | Document | Validates that file paths declared in usages exist on disk. |
| `UsageUrlIsAccessible` | Document | Checks that URLs declared in usages are reachable (results are cached). |
| `UsageLinksHasNotConflicts` | Document | Ensures no naming conflicts exist among usage links. |

## Structure Rules (5)

Rules that validate the `body` section -- entities, routines, their signatures, and locations.

| Rule | Scope | Description |
|---|---|---|
| `EntitiesAndRoutinesHasNotConflicts` | Document | Ensures entity and routine names do not collide. |
| `EntityHasOnlyValidKeys` | Document | Validates that entity declarations use only allowed keys. |
| `RoutineHasOnlyValidKeys` | Document | Validates that routine declarations use only allowed keys. |
| `SignatureIsValid` | Document | Checks that type signatures follow the expected format. |
| `LocationIsRequired` | Document | Requires that every entity and routine specifies a source file location. |
| `ReturnTypeHasLink` | Document | Ensures return types in signatures have a corresponding link label. |

## Mutation Rules (3)

Rules that validate mutation declarations on entities.

| Rule | Scope | Description |
|---|---|---|
| `MutationExists` | Document | Checks that the base type for a mutation exists. |
| `MutationIsValid` | Document | Validates that the mutation declaration is well-formed. |
| `EmbeddedEntityCanNotHasMutations` | Document | Ensures embedded entities do not declare mutations. |

## Annotation Rules (1)

Rules that validate annotation declarations.

| Rule | Scope | Description |
|---|---|---|
| `AnnotationLinksExists` | Document | Ensures that links in annotations reference valid, existing types. |

## Tree-Level Rules (3)

Rules that require cross-document context. These are applied by the [Analyzer](ast-analyzer.md).

| Rule | Description |
|---|---|
| `ImportsHasNotCyclicalDeps` | Detects circular import chains between CODEMANIFEST documents. |
| `ImportTypeExists` | Ensures every imported type can be found somewhere in the full document tree. |
| `EmbeddedTypeHasLowLevel` | Validates that embedded entities follow the correct hierarchy level relative to their parent. |

## Where to Next

- [AST Visitor](ast-visitor.md) -- how document-level rules are applied.
- [AST Analyzer](ast-analyzer.md) -- how tree-level rules are applied.
- [Error Handling](ast-errors.md) -- the error types produced by rule violations.
