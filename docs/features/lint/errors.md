# Lint — Errors

The catalog of validation errors [`goga lint`](cli.md) reports — one entry per rule. 24 rules in two scopes: **document-level** (21, applied to each CODEMANIFEST by the AST visitor) and **tree-level** (3, applied across the import graph by the analyzer).

## Reading an error

```
[RULE_NAME] Error message
  --> path/to/CODEMANIFEST
      ---
      yaml_fragment_key: value
      ...
```

The rule name in brackets, the message, the offending document, and the YAML fragment that triggered it. A closing summary counts the run:

```
goga lint
-------------------------
cells: N errors: M
```

Structural failures that are not rule violations surface as parse errors: a document that is not valid YAML or violates the document shape (`DocumentParseError`) — see [Architecture — Error Handling](../../architecture/ast-errors.md).

## Import errors (8)

The `Imports` section of the header.

| Rule | Scope | The error means |
|---|---|---|
| `ImportsCanNotBeEmpty` | Document | The `Imports` block is declared but empty — no Types and no Usages listed (a document without an `Imports` block is not flagged) |
| `ImportsHasOnlyValidKeys` | Document | An import item carries a key other than `Types`, `Usages`, `From` |
| `ImportItemIsValid` | Document | An import item lists no Types or no Usages |
| `ImportHasNotDuplicate` | Document | The same import entry appears twice in the list |
| `ImportHasValidFromPath` | Document | The `From` path is not a valid source path (escapes the project, absolute, malformed) |
| `ImportUsageExists` | Document | A usage file referenced in imports does not exist at `{From}/.usages/<name>.md` |
| `ImportIsUsed` | Document | A declared import is never referenced in the document body |
| `ImportTypeExists` | Tree | An imported type exists nowhere in the project tree |

## Usage errors (4)

The `Usages` section of the header.

| Rule | Scope | The error means |
|---|---|---|
| `AllUsagesIsUsed` | Document | A declared usage is never referenced in any annotation |
| `UsageFilepathExists` | Document | A usage declared by file path does not exist on disk (project-level practices must reside in `.goga/usages/`) |
| `UsageUrlIsAccessible` | Document | A usage declared by URL is not reachable (duplicate URLs are checked once per run) |
| `UsageLinksHasNotConflicts` | Document | Two usage links resolve to the same name — an import collides with a local `Usages` key |

## Structure errors (6)

The body — entities, routines, signatures, locations.

| Rule | Scope | The error means |
|---|---|---|
| `EntitiesAndRoutinesHasNotConflicts` | Document | An entity or routine has the same name as an imported name — use an alias in Imports |
| `EntityHasOnlyValidKeys` | Document | An entity declaration carries a key other than `location`, `annotations`, `methods`, `properties` |
| `RoutineHasOnlyValidKeys` | Document | A routine declaration carries a key other than `location`, `annotations` |
| `SignatureIsValid` | Document | A type signature does not follow the expected format |
| `LocationIsRequired` | Document | An entity or routine has no `location`, or its `location` carries a directory path or lacks a file extension |
| `ReturnTypeHasLink` | Document | A return type in a signature has no paired semantic label (`-> value:Type`, not `-> Type`) |

## Mutation errors (3)

Mutation declarations on entities.

| Rule | Scope | The error means |
|---|---|---|
| `MutationExists` | Document | The base type of a mutation does not exist |
| `MutationIsValid` | Document | The mutation declaration is malformed |
| `EmbeddedEntityCanNotHasMutations` | Document | An embedded entity (`->Type: {}`) declares mutations |

## Annotation errors (1)

| Rule | Scope | The error means |
|---|---|---|
| `AnnotationLinksExists` | Document | A backtick reference in an annotation points to no entity of the document context — a signature variable, a type, or a practice that does not resolve |

## Tree-level errors (3)

Rules that need the cross-document context.

| Rule | The error means |
|---|---|
| `ImportsHasNotCyclicalDeps` | A circular import chain exists between CODEMANIFEST documents (cell A imports from B while B imports from A) |
| `ImportTypeExists` | An imported type cannot be found anywhere in the full document tree |
| `EmbeddedTypeHasLowLevel` | An embedded entity does not follow the correct hierarchy level relative to its parent |

## Where to next

- [Validation Rules Reference](../../architecture/validation-rules.md) — the same rules from the implementation side.
- [AST Visitor](../../architecture/ast-visitor.md) / [AST Analyzer](../../architecture/ast-analyzer.md) — how document-level and tree-level rules are applied.
