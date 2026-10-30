# Scope Resolution Report

## Task Summary

`goga schema` fails with `ValueError: AST parsing failed with 160 error(s)`. Root cause chain (per TODO `fix-schema-ignore`, verified by reproduction): `schema()` in `goga/schema/schema.py:185` constructs `AST(".")` without an ignore list, so `AST.load()` (`goga/ast/ast.py:98`) descends into `.venv/` where the manually installed `swax` and `resq` pip packages ship their own CODEMANIFESTs. Their contracts are validated against the goga repo root (rules resolve paths from CWD, not from manifest location) producing 153 DocumentRuleErrors + 7 ASTRuleErrors; `schema()` then raises on non-empty `errors` (`schema.py:189`). `goga lint` works because it reads `lint.ignore` from `.goga/config.yml` (contains `.venv/`, `build/`, `example/`) and passes it to `AST(".", ignore=...)` (`goga/commands/lint/lint.py:51`). `goga contract` (`goga/commands/contract/contract.py:225`) and `goga tool` (`goga/commands/tool/tool.py:30`) have the same unfiltered `AST(".")` construction and the same latent failure. Reproduced live: `goga schema` → exit 1, 160 errors.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| `goga/schema` | Owns the failing routine `schema()` — constructs `AST(".")` without ignore (`schema.py:185`) | 1 (runtime participation) |
| `goga/commands/schema` | CLI caller of `schema()` — owns config delivery decision point for the schema path | 2 (direct dependency) |
| `goga/commands/contract` | Same unfiltered `AST(".")` at `contract.py:225` — same latent failure mode | 3 (behavioral proximity) |
| `goga/commands/tool` | Same unfiltered `AST(".")` at `tool.py:30` (`_build_ast`) — same latent failure mode | 4 (behavioral proximity) |
| `goga/commands/lint` | Working reference implementation — ignore delivery pattern to replicate | 5 (reference) |
| `goga/ast` | Owns `AST(path, ignore)` traversal semantics; its manifest constraint (`ignore=None` must not change traversal) bounds the fix | 6 (manifest relevance) |
| `goga/config` | Owns `LintConfig`/`load_project_config`/`ConfigHooks` — source of the ignore list | 7 (manifest relevance) |

## Included Dependencies

| Cell | Behavioral Relevance |
|---|---|
| `goga/ast` | Fix must respect manifest constraint "Do NOT change traversal for consumers that pass ignore=None" — AST itself is correct; no code change expected here, but it constrains the solution shape (ignore must be delivered by callers) |
| `goga/config` | Ignore entries come from `lint.ignore` via `load_project_config()` + `ConfigHooks().amend_config()`; schema/contract/tool callers must reuse this delivery chain |
| `goga/schema/hooks` | `schema()` runs its checkpoint walk over `ast_obj.tree` — filtered vs unfiltered tree changes which cells are delivered; must stay consistent with output |

## Excluded Dependencies

| Cell | Exclusion Reason |
|---|---|
| `goga/ast/rules/**` (incl. `ImportHasValidFromPath`, `UsageFilepathExists`, `EmbeddedTypeHasLowLevel`) | The 160 rule errors are symptoms of validating foreign manifests against the wrong root, not defects in the rules; fixing rules would change semantics for all consumers |
| `.venv/**/CODEMANIFEST` (swax, resq) | Foreign packages, not project cells; must be excluded from traversal, not fixed |
| `goga/docker`, `goga/build`, `goga/pipeline`, `goga/agents`, `goga/afm`, `goga/drift`, `goga/codegraph`, `goga/history`, `goga/hooks`, `goga/topics`, `goga/scaffold`, `goga/connect`, `goga/onboarding`, `goga/usages`, `goga/version`, `goga/runtime`, `goga/ralphex` | No AST construction, no ignore-related data flow — infrastructural-only or unrelated |
| `goga/commands/{build,connect,codegraph,drift,config,usages,init,upgrade,install,history,topics,hooks,pipeline}` | No `AST(` construction (verified by grep across `goga/`); no behavioral participation |

## Usage Relationships

| Usage | Relevance |
|---|---|
| `goga/schema` CODEMANIFEST `documents` practice | Currently mandates "instantiate `AST` with the current CWD path (".")" — silent on ignore; must be updated to mandate ignore delivery, else manifest drift |
| `.goga/usages/conventions.md` (`convention`) | Mandatory code/test conventions for the change (relative imports, docstrings, test mirroring) |
| `goga/commands/lint` config-delivery pattern (inline code comments) | The swallow/clean-error semantics for optional config — pattern to replicate in schema/contract/tool callers |

## Semantic Participation Summary

- `goga/schema` + `goga/commands/schema` participate directly: they construct the AST for the schema command and own where an ignore list would enter the schema path.
- `goga/commands/contract` and `goga/commands/tool` participate by identical construction: any fix that only patches `schema()` leaves them broken the same way the moment a venv package carries a CODEMANIFEST (already true today for `contract`/`tool` when they traverse `.venv/`).
- `goga/config` participates as the data source (`lint.ignore`) already consumed by `goga/commands/lint`.
- `goga/ast` participates as the constrained executor: the fix must deliver `ignore` from callers, not change `AST` defaults.

## Final Investigation Scope

- `goga/schema` (routine `schema()`, `schema.py:185-189`)
- `goga/commands/schema` (CLI command, `schema.py:56-61`)
- `goga/commands/contract` (CLI command, `contract.py:225-226`)
- `goga/commands/tool` (`_build_ast`, `tool.py:15-33`)
- `goga/commands/lint` (reference: `lint.py:25-52`)
- `goga/config` (project config/loader, `ConfigHooks` overlay)
- `goga/ast` (contract constraints on `AST.__init__`/`load` only — read-boundary)

## Scope Risks

- **Under-scoping**: fixing only `schema()` leaves `contract` and `tool` failing on the same project — the bug class is "AST built without config ignore", not "schema broken".
- **Over-scoping**: changing `AST` default traversal or rule path resolution (manifest-relative paths) would alter behavior for every consumer and violate the `goga/ast` CODEMANIFEST constraints — out of scope for this hotfix.
- **Config semantics**: reusing `lint.ignore` for schema/contract/tool is the minimal-change path; introducing a new config key (e.g. `ast.ignore`) touches `goga/config` contract surface and docs — decision point for the plan.
- **Breaking change surface**: changing `schema(cells, max_depth, depends_on)` signature or CLI output shape would be breaking; additive optional parameters are not.

## Notes

- All four `AST(` construction sites verified by grep: `goga/schema/schema.py:185`, `goga/commands/lint/lint.py:51`, `goga/commands/contract/contract.py:225`, `goga/commands/tool/tool.py:30`.
- `.venv` contains 22 CODEMANIFEST files (swax: 19, resq: 6 → counted via find; exact split irrelevant) — all foreign.
- TODO's hypothesis `AST('.', ignore=['.venv']) → 0 errors` still to be validated in the Investigation step.
- `goga schema` currently loads config nowhere on its path — unlike lint/contract, which already run the `ConfigHooks` checkpoint; adding config delivery to the schema path introduces the checkpoint there for the first time (behavioral consideration for the plan).
