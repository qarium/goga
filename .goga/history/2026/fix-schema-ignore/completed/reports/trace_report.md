# Trace Report

## Call Flow

```
PATH A — the working path (lint):
  CLI `goga lint` → lint(lint.py:17)
    → os.chdir(path)
    → load_project_config()                      [goga/config/project/loader.py:747]
    → ConfigHooks().amend_config(config=cfg)     [goga/config/hooks/events.py:77] → ConfigOverlay
    → ignore = overlay.config.lint.ignore        (None when lint section absent)
    → AST(".", ignore=ignore).load()             [goga/ast/ast.py:59,81]
        → os.walk(".") with dirnames[:] pruning against ignore_set   [ast.py:98-108]
    → prints errors + summary, exit(1 if errors else 0)

PATH B — the failing path (schema):
  CLI `goga schema` → schema(commands/schema/schema.py:33)
    → schema_logic(cells, max_depth, depends_on) [goga/schema/schema.py:162]
      → AST(".")                                 [schema.py:185]   ← ignore NEVER delivered
      → ast_obj.load()                           → descends .venv/, build/, example/
      → 160 errors → raise ValueError            [schema.py:188-189]

PATH C — contract (latent, same construction):
  CLI `goga contract` → contract(contract.py:~190)
    → load_project_config() + ConfigHooks().amend_config()   [contract.py:211-214]  ← config IS loaded
    → AST(".")                                   [contract.py:225]  ← but ignore NOT passed
    → ast_obj.document(cell_path) per requested cell; ast_obj.errors never checked → no crash

PATH D — tool (latent, same construction):
  CLI `goga tool <name>` → tool(tool.py) → build_injections(main, tool)
    → _OFFERED_INJECTIONS["ast"] → _build_ast()  [tool.py:15-33]
    → AST(".")                                   [tool.py:30]  ← ignore NOT passed
    → AST handed to external tool package; errors pass through as data (by contract)
```

## Data Flow

```
.goga/config.yml (lint.ignore: [build/, .venv/, example/])
   │
   ├─→ load_project_config() → ProjectConfig(.lint=LintConfig(ignore=[...]))
   │     │
   │     ├─→ [PATH A] lint.py:49-51 → AST(".", ignore) → traversal pruned → 0 errors, 91 cells ✓ (verified live)
   │     ├─→ [PATH C] contract.py:211-223 → config consumed ONLY for language; ignore discarded ✗
   │     └─→ [PATH D] tool.py → no project config load at all ✗
   │
   └─ (never read on PATH B — schema loads no config)

AST.load() [goga/ast/ast.py:81-108]
   ignore list → ignore_set (normpath) → dirnames[:] filter prunes os.walk descent
   ignore=None/[] → ignore_set=∅ → unfiltered traversal → .venv/**/CODEMANIFEST loaded

.venv/lib/python3.14/site-packages/{swax,resq}/**/CODEMANIFEST (22 files, installed 22 Oct, manual pip install)
   → validated with cwd = goga repo root:
     import_has_valid_from_path ×140   (e.g. From: paths like config/ do not exist at goga root)
     usage_filepath_exists     ×13     (e.g. .goga/usages/cooks/pyyaml.md absent in this repo)
     embedded_type_has_low_level ×7    (AST rule, resq embedded types)
   → 153 DocumentRuleErrors + 7 ASTRuleErrors = 160   (verified live: exact match)
```

## Manifest Algorithm Mapping

| Manifest step | Code path | Status |
|---|---|---|
| `goga/schema` CODEMANIFEST: Algorithm 1 "Load the project document tree using the `documents` practice" | `schema.py:185-186` `AST(".")` + `load()` | Matches — but the `documents` practice text says only "instantiate `AST` with the current CWD path ('.')" and is **silent on ignore**; the practice under-specifies the load the code performs |
| `goga/schema` Requirement "If AST.errors is non-empty after loading: raise ValueError with the error count" | `schema.py:188-189` | Matches (fail-fast is contract-defined — NOT the defect) |
| `goga/ast` CODEMANIFEST: load() Algorithm "skip [a subdirectory] when its normalized relative path ... exactly matches one of the normalized entries in ignore ... When ignore is None or empty, no directory is skipped" | `ast.py:92,98-108` | Matches — AST ignore semantics implemented per manifest |
| `goga/ast` Constraint "Do NOT change traversal for consumers that pass ignore=None (default)" | — | Constrains the fix: callers must deliver ignore; AST defaults stay |
| `goga/commands/lint` CODEMANIFEST: Algorithm "Derive ignore ... via ConfigHooks ... when its lint is None -> ignore=None; otherwise ignore=cfg.lint.ignore" | `lint.py:30-51` | Matches — the reference delivery pattern |
| `goga/commands/contract` CODEMANIFEST: step 3 "Create `AST` object and load the project using the `loading` practice" | `contract.py:225-226` | Matches manifest, but manifest silent on ignore; loads config (step 1) yet discards `lint.ignore` |
| `goga/commands/tool` CODEMANIFEST: build_injections "for ast -> construct the project AST at the current project root and load it, following `loading`"; Constraint "Do not block or transform on non-empty `AST` errors" | `tool.py:15-33` | Matches — no config load in this cell by design; error pass-through is contract-defined |
| `goga/commands/schema` CODEMANIFEST: Algorithm 1 "Invoke `schema_logic`(cells, max_depth, depends_on)" | `commands/schema/schema.py:57` | Matches — CLI is a thin wrapper; no config delivery on this path |

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| `goga/schema` | `goga/ast` | call | `schema.py:8` `from ..ast import AST` → `AST(".")` (schema.py:185) |
| `goga/commands/schema` | `goga/schema` | call | `commands/schema/schema.py:7` `from ...schema import schema as schema_logic` → `schema_logic(...)` (:57) |
| `goga/commands/contract` | `goga/ast` | call | `contract.py` `from ...ast import AST` → `AST(".")` (:225) |
| `goga/commands/contract` | `goga/config` + `goga/config/hooks` | call/data | `load_project_config()` (:211) → `ConfigHooks().amend_config()` (:214) → only `language` consumed (:223) |
| `goga/commands/tool` | `goga/ast` | call | `tool.py:10` `from ...ast import AST` → `AST(".")` (:30) |
| `goga/commands/tool` | `goga/config` | call | `load_tool_config` only (:12) — project config never loaded |
| `goga/commands/lint` | `goga/config` + `goga/config/hooks` + `goga/ast` | call/data | `lint.py:30-51` — the complete ignore delivery chain |
| `goga/schema` | `goga/schema/hooks` | call | `SchemaHooks()` walk + gate (schema.py:204-229) — receives whatever tree the unfiltered AST built |

## Inconsistencies

| Type | Location | Expected | Actual |
|---|---|---|---|
| Practice under-specification | `goga/schema` CODEMANIFEST `documents` usage | States how the caller instantiates `AST` for the load | Text mandates CWD path only; silent on ignore — the load the code performs has no way to receive a filter |
| Manifest–code gap (config discarded) | `goga/commands/contract/contract.py:225` | Having loaded `ProjectConfig` (with `.lint`), the command could honor `lint.ignore` as lint does | `AST(".")` built unfiltered; `lint.ignore` loaded then discarded |
| Manifest–code gap (no config) | `goga/commands/tool/tool.py:30` | — (no manifest requirement to filter; constraint forbids blocking on errors) | `AST(".")` unfiltered; foreign `.venv` cells delivered to tool packages |
| Comment–reality drift | `goga/ast/ast.py:89-91` "backward compatible for schema/review/contract" | Documents that schema/contract intentionally run unfiltered | The "backward compatibility" is precisely what breaks `goga schema` when venv packages carry manifests; no `review` AST consumer exists (verified: only 4 `AST(` sites) |

## Trace Graph

```
.goga/config.yml ──lint.ignore──▶ load_project_config ──▶ ConfigHooks.amend_config ──▶ ConfigOverlay.config.lint.ignore
                                                      │
                    ┌─────────────────────────────────┼──────────────────────────────┐
                    ▼ (PATH A ✓)                     ▼ (PATH C ✗ discards)           ▼ (PATH D ✗ never loads)
              commands/lint                    commands/contract                commands/tool
              AST(".", ignore)                 AST(".")                          AST(".")  [_build_ast]
                    │                                │                                │
                    └──────────────┬─────────────────┴────────────────────────────────┘
                                   ▼
                          goga/ast AST.load() ── os.walk(".") ──┐
                        ignore=None/[] ⇒ no pruning            │ descends
                                                                ▼
                                       .venv/**/{swax,resq}/CODEMANIFEST (22 manifests)
                                                                │ rules resolve paths vs repo root
                                                                ▼
                                       140 import_has_valid_from_path + 13 usage_filepath_exists
                                       + 7 embedded_type_has_low_level = 160 errors
                                                                │
                PATH B (schema): goga/schema schema() ──────────┤ ast_obj.errors non-empty
                schema.py:188-189 raise ValueError ────────────┘ ✗ CLI exit 1
```
