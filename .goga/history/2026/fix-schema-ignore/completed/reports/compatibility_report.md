# Compatibility Report

## Checklist Results

### API Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Function signature unchanged for existing callers? | YES | `schema()` gains only an optional trailing parameter `ignore: list[str] | None = None`; every existing 3-arg call site (`goga/commands/schema/schema.py:57`; tests `tests/schema/test_schema.py` pass-through calls, `tests/commands/schema/test_schema.py:1414,1474`) remains valid and resolved identically. `contract()`, `tool()`, `build_injections()` signatures unchanged. `AST` signature unchanged. |
| Return type unchanged? | YES | `schema() -> list[SchemaNode]` (test pin `typing.get_type_hints(schema)["return"] == list[SchemaNode]` still holds); CLI JSON projection unchanged; contract JSON shape unchanged; tool injection type unchanged (`AST`). |
| Default parameter values preserved? | YES | `cells`, `max_depth`, `depends_on` defaults untouched; new `ignore` defaults to `None` — the exact value `AST` receives today, so the unfiltered traversal default is preserved (`ast.py:92` `ignore_set=∅` when falsy). |

### Semantic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Same arguments produce same behavior? | NO* | Python API: YES — `schema(cells, max_depth, depends_on)` with no `ignore` constructs `AST(".", ignore=None)`, byte-identical behavior. CLI: NO — `goga schema` now honors `lint.ignore` (on this repo: crash → success; on projects with error-free ignored dirs: those cells leave the output). *User-approved deviation — see Breaking Change Details. |
| Output format unchanged? | YES | JSON shape, key set (`cell`, `description`, `types`, `usages`, `dependencies`, `children`, `tools`), ordering, and serialization are untouched; only the delivered cell set can shrink by ignored directories. Lint summary/error formats untouched. |
| File paths unchanged? | YES | No files move, no paths rewritten; ignored directories are skipped at traversal (never read), not deleted or relocated. |
| Error messages and codes unchanged? | YES | The fail-fast message `AST parsing failed with {n} error(s)` and all checkpoint/gate error texts unchanged; exit codes unchanged (schema: 0/1; contract: 0/1; tool: unchanged). New clean `ClickException` path in commands/schema mirrors lint's existing message surface for checkpoint failures. |

### Algorithmic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Manifest-defined algorithm steps preserved? | YES | `goga/schema` Algorithm steps 1-7 preserved (step 1 gains the ignore pass-through); fail-fast requirement kept verbatim; checkpoint walk, filters, gate order untouched. `goga/commands/lint` algorithm untouched (reference implementation not modified). `goga/ast` load algorithm and constraints untouched. `contract` steps 1-6 order preserved (step 3 gains ignore). `tool` build_injections steps preserved; error pass-through constraint kept (ignored dirs are never loaded → contribute no errors to pass through). |
| Execution order unchanged? | YES | schema CLI: config delivery happens before `schema_logic` (as lint does before `AST`); inside `schema()`, load → errors check → filters → walk → gate order identical. contract: config load/checkpoint (already first) → AST build → lookups → checkpoint order identical. tool: `_build_ast` laziness and injection order unchanged. |
| Side effects unchanged? | YES* | stdout cleanliness preserved (summary lines → stderr, as contract/lint already do). *New effect, user-approved: the config amendment checkpoint now runs on the schema path (first time) — same surface lint/contract already deliver; tool deliberately gets **no** checkpoint (injection stays transparent, loader-only). |

### Consumer Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Existing tests pass without modification? | NO* | Exactly one test requires an update: `tests/schema/test_schema.py:984` `test_schema_keeps_the_declared_signature` pins `["cells", "max_depth", "depends_on"]`. All other tests keep outcomes: CLI tests run in tmp_path projects without `.goga/config.yml` → swallow path → `ignore=None` → byte-identical output. *User-approved update — see Breaking Change Details. |
| Usage recipes remain valid? | YES | `goga/ast/.usages/loading.md` ignore section already documents the delivery being wired in; `goga/schema/hooks/.usages/checkpoints.md` semantics ("filters prune delivery exactly as they prune output") already cover a filtered tree. `project-configuration.md` gets a factual wording update (lint.ignore honored by all AST commands) — no recipe invalidated. |
| Downstream consumers unaffected? | YES | Grep-verified: single caller of `schema()` logic (commands/schema); `goga review` does not exist as an AST consumer; no other module imports `goga.schema.schema`. Tool packages receive a cleaner tree — their opt-in contract (`ast` injection) is unchanged in type and semantics. |

## Verdict

**BREAKING — two flagged items, both explicitly approved by the user (plan approval, answer q1: "Утвердить план полностью").** Per policy, the STOP was escalated instead of dismissed; the user's approval is the recorded override. Proceeding is authorized. All non-flagged checkboxes are YES; `goga/ast`'s manifest constraint ("Do NOT change traversal for consumers that pass ignore=None") is honored by design.

## Breaking Change Details

1. **CLI behavior change — intended fix (Semantic/Same-arguments).** `goga schema` with an identical invocation now honors `lint.ignore`: on this repository the command goes from `exit 1` (160 foreign errors) to `exit 0` with the single root cell; in general, ignored directories no longer appear in schema output. User approved as the core purpose of the hotfix. Python-level API remains fully backward compatible (`ignore=None` default).
2. **Signature-pin test update (Consumer/Existing tests).** `tests/schema/test_schema.py:984` pins the routine's parameter list; adding the optional `ignore` parameter requires updating the pin to `["cells", "max_depth", "depends_on", "ignore"]`. User approved alongside the plan.
