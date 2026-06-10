# CODEMANIFEST validation rule registry

Scope: Overview of all available validation rules and their classification.
Audience: Consumers selecting rules for manifest validation.

## Two rule tiers

Rules are organized into two categories by scope:

### DocumentRule — per-document validation

Applied via `Visitor` to each document independently.

**Imports:**
- `ImportsCanNotBeEmpty` — import block must not be empty
- `ImportsHasOnlyValidKeys` — only Types, Usages, From keys allowed
- `ImportItemIsValid` — each import must declare a type or usage
- `ImportUsageExists` — imported usage file must exist on disk
- `ImportHasValidFromPath` — From path must exist and stay within CWD
- `ImportHasNotDuplicate` — no duplicate names across imports
- `ImportIsUsed` — every import must be referenced in the document

**Usages:**
- `AllUsagesIsUsed` — every declared usage must appear in annotations
- `UsageFilepathExists` — usage file must exist on disk
- `UsageUrlIsAccessible` — usage URL must return HTTP 200
- `UsageLinksHasNotConflicts` — usage names must not conflict with type names

**Annotations:**
- `AnnotationLinksExists` — backtick links in annotations must resolve to existing entities

**Structures:**
- `EntitiesAndRoutinesHasNotConflicts` — entity/routine names must not conflict with imports
- `EntityHasOnlyValidKeys` — entity must contain only allowed keys
- `RoutineHasOnlyValidKeys` — routine must contain only allowed keys
- `SignatureIsValid` — signature must match `(...) -> ...` or `(...)` format
- `ReturnTypeHasLink` — return type must include a semantic label
- `LocationIsRequired` — type must specify a filename with extension

**Mutations:**
- `MutationExists` — mutation base type must exist
- `MutationIsValid` — mutation must not reference itself
- `EmbeddedEntityCanNotHasMutations` — embedded entities must not define mutations

### ASTRule — tree-wide validation

Applied via `Analyzer` across all documents.

- `ImportsHasNotCyclicalDeps` — no cyclic import dependencies between documents
- `ImportTypeExists` — imported type must exist in the target document
- `EmbeddedTypeHasLowLevel` — embedded types must reside deeper in the file hierarchy

## Utility function

- `signature_contains_type_name(signature, type_name) -> bool` — tests whether a type name appears in a signature
