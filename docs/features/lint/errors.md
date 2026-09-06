# Lint — Errors

The catalog of validation errors [`goga lint`](cli.md) reports — one entry per rule, in two scopes: **document-level** (applied to each CODEMANIFEST by the AST visitor) and **tree-level** (applied across the import graph by the analyzer).

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

Structural failures that are not rule violations surface as parse errors: a document that is not valid YAML or violates the document shape (`DocumentParseError`) — the error hierarchy is documented in [Error Hierarchy](error-hierarchy.md).

## Import errors

The `Imports` section of the header.

| Rule | Scope | The error means |
|---|---|---|
| `imports_can_not_be_empty` | Document | The `Imports` block is declared but empty — no Types and no Usages listed (a document without an `Imports` block is not flagged) |
| `imports_has_only_valid_keys` | Document | An import item carries a key other than `Types`, `Usages`, `From` |
| `import_item_is_valid` | Document | An import item lists no Types or no Usages |
| `import_has_not_duplicate` | Document | The same import entry appears twice in the list |
| `import_has_valid_from_path` | Document | The `From` path is not a valid source path (escapes the project, absolute, malformed) |
| `import_usage_exists` | Document | A usage file referenced in imports does not exist at `{From}/.usages/<name>.md` |
| `import_is_used` | Document | A declared import is never referenced in the document body |
| `import_type_exists` | Tree | An imported type exists nowhere in the project tree |

## Usage errors

The `Usages` section of the header.

| Rule | Scope | The error means |
|---|---|---|
| `all_usages_is_used` | Document | A declared usage is never referenced in any annotation |
| `usage_filepath_exists` | Document | A usage declared by file path does not exist on disk (project-level practices must reside in `.goga/usages/`) |
| `usage_url_is_accessible` | Document | A usage declared by URL is not reachable (duplicate URLs are checked once per run) |
| `usage_links_has_not_conflicts` | Document | Two usage links resolve to the same name — an import collides with a local `Usages` key |

## Structure errors

The body — entities, routines, signatures, locations.

| Rule | Scope | The error means |
|---|---|---|
| `entities_and_routines_has_not_conflicts` | Document | An entity or routine has the same name as an imported name — use an alias in Imports |
| `entity_has_only_valid_keys` | Document | An entity declaration carries a key other than `location`, `annotations`, `methods`, `properties` |
| `routine_has_only_valid_keys` | Document | A routine declaration carries a key other than `location`, `annotations` |
| `signature_is_valid` | Document | A type signature does not follow the expected format |
| `location_is_required` | Document | An entity or routine has no `location`, or its `location` carries a directory path or lacks a file extension |
| `return_type_has_link` | Document | A return type in a signature has no paired semantic label (`-> value:Type`, not `-> Type`) |

## Mutation errors

Mutation declarations on entities.

| Rule | Scope | The error means |
|---|---|---|
| `mutation_exists` | Document | The base type of a mutation does not exist |
| `mutation_is_valid` | Document | The mutation declaration is malformed |
| `embedded_entity_can_not_has_mutations` | Document | An embedded entity (`->Type: {}`) declares mutations |

## Annotation errors

| Rule | Scope | The error means |
|---|---|---|
| `annotation_links_exists` | Document | A backtick reference in an annotation points to no entity of the document context — a signature variable, a type, or a practice that does not resolve |

## Tree-level errors

Rules that need the cross-document context.

| Rule | The error means |
|---|---|
| `imports_has_not_cyclical_deps` | A circular import chain exists between CODEMANIFEST documents (cell A imports from B while B imports from A) |
| `import_type_exists` | An imported type cannot be found anywhere in the full document tree |
| `embedded_type_has_low_level` | An embedded entity does not follow the correct hierarchy level relative to its parent |

## Where to next

For maintainers — the implementation side:

- [Validation Rules](validation-rules.md) — the same rules from the implementation side.
- [AST Visitor](../../cell/ast/visitor.md) / [AST Analyzer](../../cell/ast/analyzer.md) — how document-level and tree-level rules are applied.
