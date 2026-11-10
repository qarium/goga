# Manifest Reconciliation Report

## Cells Reconciled

| Cell | Manifest Updated? | Sections Changed |
|---|---|---|
| `goga/schema` | Yes | Body signature (+`ignore: list[str] \| None = None`); `documents` practice (ignore delivery to `AST`); type annotations (`ignore` param); Requirements (verbatim flow, no normalization/glob, ignored dirs contribute no cells/errors) |
| `goga/commands/schema` | Yes | Header Imports (+`load_project_config`, `ProjectConfig`, usage `project-configuration` from `goga/config`; +`ConfigHooks`, `ConfigOverlay` from `goga/config/hooks`); Annotations (config load + checkpoint delivery references); Algorithm (new step 1 — ignore derivation; step 2 forwards ignore; renumbered 3-5); Requirements (verbatim pass-through, config-less behavior unchanged) |
| `goga/commands/contract` | Yes | Algorithm step 2 (derive ignore from the effective configuration); step 3 (pass derived ignore to `AST`); Requirements (verbatim, ignored dirs contribute no documents) |
| `goga/commands/tool` | Yes | `build_injections` Algorithm step 3 ast bullet (loader-only config read, swallow semantics, no checkpoint, nothing printed); Requirements (never fails on present-but-invalid config) |
| `goga/ast` | No | Implementation unchanged; constraints ("Do NOT change traversal for consumers that pass ignore=None") hold — verified against the delivered code |
| `goga/config` | No | Facade exports unchanged; no new config surface introduced |

## Algorithm Consistency

- `goga/schema`: manifest Algorithm step 1 ("Load the project document tree using the `documents` practice") now matches the code — the practice specifies the CWD instantiation and the optional verbatim ignore delivery; steps 2-7 unchanged and unchanged in code. Match.
- `goga/commands/schema`: Algorithm now numbers five steps matching the code flow (derive ignore → invoke with ignore → error conversion → projection → serialization). The error-conversion step text is untouched (code path unchanged). Match.
- `goga/commands/contract`: steps 1-2 (config load/checkpoint/language + ignore derivation) and step 3 (`AST` with ignore) mirror `contract.py` exactly; steps 4-6 untouched. Match.
- `goga/commands/tool`: `build_injections` step 3 ast bullet matches `_build_ast` (loader-only read, swallow tuple `OSError/KeyError/ValueError/yaml.YAMLError`, no checkpoint, no output); the error pass-through constraint text is untouched and still holds. Match.

## Operational Flow Consistency

- `goga/commands/schema`: config delivery precedes the logic invocation, checkpoint only on successful load, summary lines to stderr — flow text matches code order. The `except Exception` conversion around `schema_logic` is unchanged.
- `goga/commands/contract`: ignore derived after language resolution from the same overlay — matches code order (`lang` line, then ignore, then `AST`).
- `goga/commands/tool`: laziness preserved — the manifest's "build the value lazily" wording covers the config read inside `_build_ast`; nothing printed (no summary lines on the tool path), consistent with the injection transparency wording.

## Guarantees Verification

- `goga/schema` fail-fast ("If AST.errors is non-empty after loading: raise ValueError with the error count") — preserved; ignore reduces what reaches the check, the check itself untouched. Preserved.
- `goga/schema` checkpoint/gate guarantees ("filters prune delivery exactly as they prune output", gate fires once over the final tree) — preserved; an ignored directory simply produces no node to deliver. Preserved.
- `goga/commands/schema` ("stdout carries the machine-consumed JSON only", "Exit 0 only on a complete generation") — preserved; new summary lines go to stderr per the new algorithm text. Preserved.
- `goga/commands/tool` ("Do not block or transform on non-empty `AST` errors") — preserved; ignored directories are never loaded, so they generate no errors to transform. Preserved.
- `goga/ast` guarantees — untouched by this change; lint confirms 0 errors.

## Practices Consistency

- Base `convention` usage and its annotations block — present and unchanged in all four manifests (verified during editing; `goga lint` all_usages_is_used/annotation rules pass).
- `goga/commands/schema`: the config-checkpoint practice could not be imported — the `checkpoints` usage name is already imported from `goga/schema/hooks`, and the `import_has_not_duplicate` rule rejects importing the same usage name from two cells (aliasing does not lift it). Resolution: import only the `ConfigHooks`/`ConfigOverlay` types from `goga/config/hooks` and describe the checkpoint delivery against those types plus the imported `project-configuration` practice. All links resolve (`goga lint` clean).
- `goga/schema` `documents` practice now carries the ignore semantics — the practice stays the single load recipe for the cell.
- `goga/ast` `.usages/loading.md` already documents ignore delivery — manifest references remain valid.

## Semantic Consistency Summary

**Consistent.** All four modified manifests describe the implemented behavior; `goga lint` over the project reports `cells: 91, errors: 0`. Two reconciliation-driven corrections were applied before reaching clean state: (1) dropped the illegal duplicate import of the `checkpoints` practice in `goga/commands/schema` in favor of types-only import + descriptive annotations; (2) removed `` `ignore` `` backticks in `goga/commands/schema` annotations (not a signature parameter of the CLI command — not a valid link there; it remains a valid parameter link in `goga/schema` where it IS in the signature). No implementation-vs-manifest contradictions remain; no unplanned behavioral changes surfaced.
