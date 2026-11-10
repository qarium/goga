# Investigation Report

## Task Summary

`goga schema` exits 1 with `AST parsing failed with 160 error(s)` whenever the project's `.venv/` contains pip packages that ship CODEMANIFESTs (here: `swax` 1.0.0 and `resq` 1.0.0, installed manually on 22 Oct). The task is to find the root cause and fix it so the schema command works again without touching foreign package contents or changing `AST` semantics. Reproduced live at investigation start: exit 1, 160 errors; `goga lint` passes (cells: 91, errors: 0); `goga contract` passes (does not check errors); the failure is exclusive to the schema path's fail-fast contract.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| `goga/schema` | Owns failing routine `schema()`; constructs `AST(".")` unfiltered at `schema.py:185` | 1 |
| `goga/commands/schema` | CLI caller; owns config delivery point for the schema path (currently none) | 2 |
| `goga/commands/contract` | Same unfiltered `AST(".")` (`contract.py:225`) with config already loaded and `lint.ignore` discarded | 3 |
| `goga/commands/tool` | Same unfiltered `AST(".")` (`tool.py:30`); foreign cells delivered to tool packages | 4 |
| `goga/commands/lint` | Reference implementation of the ignore delivery chain | 5 |
| `goga/config` | Source of `lint.ignore` via `load_project_config` + `ConfigHooks` overlay | 6 |
| `goga/ast` | Constrained executor of `ignore`; no defect | 7 |

## Tracing Summary

Full trace in `trace_report.md`. Four `AST(` construction sites exist (verified by grep, no others): `schema.py:185`, `lint.py:51`, `contract.py:225`, `tool.py:30`. Only lint delivers `ignore` (from `.goga/config.yml` `lint.ignore` through `load_project_config` → `ConfigHooks.amend_config` → `ConfigOverlay.config.lint.ignore`). The schema path loads no config at all; contract loads config but consumes only `language`; tool never loads project config. The comment `ast.py:89-91` documents the unfiltered behavior as intentional ("backward compatible for schema/review/contract") — no `review` AST consumer exists today.

## Data Flow

`.goga/config.yml` (`lint.ignore: [build/, .venv/, example/]`) → `load_project_config()` → `ProjectConfig.lint: LintConfig` → `ConfigHooks().amend_config()` → `ConfigOverlay.config.lint.ignore` → (lint only) `AST(".", ignore)` → `AST.load()` builds `ignore_set` and prunes `os.walk` descent (`ast.py:92,103-108`). With `ignore=None`, `ignore_set=∅` and the walk enters `.venv/`, loading 22 foreign manifests (swax: 19, resq: 6 verified via find... actual count 22 total). Rules resolve import/usage paths against the repo root (cwd), producing `import_has_valid_from_path` ×140, `usage_filepath_exists` ×13, `embedded_type_has_low_level` ×7 = 160. `schema()` raises `ValueError` per its manifest requirement (`schema.py:188-189`).

## Manifest Algorithm Analysis

- `goga/schema` CODEMANIFEST Algorithm step 1 ("Load the project document tree using the `documents` practice") maps to `schema.py:185-186`. The `documents` practice says only: "The caller must instantiate `AST` with the current CWD path ('.')" — it under-specifies the load: no provision for delivering an ignore list. The fail-fast requirement ("If AST.errors is non-empty after loading: raise ValueError with the error count") is contract-defined and implemented correctly — the defect is upstream of it (foreign errors enter the tree at all).
- `goga/commands/lint` CODEMANIFEST defines the complete ignore-derivation algorithm (swallow-style optional config load → checkpoint → `ignore` from overlay) — the pattern any other AST consumer must replicate.
- `goga/commands/contract` CODEMANIFEST step 1 loads config and delivers the checkpoint; step 3 creates the AST — the manifest never connects the two for ignore.
- `goga/commands/tool` CODEMANIFEST constraint "Do not block or transform on non-empty `AST` errors; validation errors pass through to the tool unchanged" — filtering traversal is orthogonal to error pass-through (ignored directories produce no errors because they are never loaded).
- `goga/ast` CODEMANIFEST constraint: "Do NOT change traversal for consumers that pass ignore=None (default)" — `AST` is correct and must not change.

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| `documents` (inline practice) | `goga/schema` | DIRECTLY AFFECTED | Must specify the ignore delivery to `AST` for the load step |
| `checkpoints` (imported from `goga/schema/hooks`) | `goga/schema`, `goga/commands/schema` | INDIRECTLY AFFECTED | The walk and gate run over the filtered tree; delivery set changes when ignored cells disappear — no text change needed, semantics already say "filters prune delivery exactly as they prune output" |
| `project-configuration` (imported from `goga/config`) | `goga/commands/contract` | INDIRECTLY AFFECTED | The command already consumes it; consumption extends to `lint.ignore` |
| `checkpoints` (imported from `goga/config/hooks`) | `goga/commands/schema` (new), `goga/commands/contract` | DIRECTLY AFFECTED | The schema command gains the config amendment checkpoint on its path for the first time |
| `loading` (imported from `goga/ast`) | `goga/commands/contract`, `goga/commands/tool` | INDIRECTLY AFFECTED | Practice describes loading via `AST`; the caller now passes ignore alongside the path |
| `convention`/`conventions` (.goga/usages/conventions.md) | all touched cells | INDIRECTLY AFFECTED | Governs the implementation style of the change |
| `lint` algorithm text | `goga/commands/lint` | NOT AFFECTED | Reference stays as is (unless a shared derive-helper refactor is chosen — plan decision) |

## Rejected Hypotheses

1. **"The rules resolve paths from the wrong root (cwd instead of manifest location)" — a rule defect.** Rejected: rules validate project-internal consistency against the project root by design; the foreign manifests are simply not part of this project. Rewriting path resolution to be manifest-relative changes semantics for every consumer (a feature, not a hotfix) and contradicts the acceptance that `AST('.', ignore=['.venv'])` → 0 errors (verified: the project itself is clean).
2. **"swax/resq packages are broken — uninstall or fix them."** Rejected: they are legitimately installed dev tools; their manifests are valid inside their own Goga projects. Any pip package may carry manifests; the traversal boundary must not depend on package contents.
3. **"`AST` should skip `.venv` by default."** Rejected: violates the `goga/ast` CODEMANIFEST constraint ("Do NOT change traversal for consumers that pass ignore=None"); only `.project` is a documented hardcoded skip. A default change silently alters every consumer's tree.
4. **"The fail-fast in `schema()` is the bug."** Rejected: the ValueError-on-errors behavior is a manifest-defined requirement with a dedicated test (`test_ast_errors_raises_value_error`); it works exactly as specified. The bug is that foreign errors reach the tree at all.
5. **"`goga contract` / `goga tool` are equally broken today."** Rejected as stated: contract does not inspect `ast_obj.errors` (verified live: exit 0 on this repo) and tool's contract mandates error pass-through. Their exposure is wasted traversal + foreign cells in the delivered tree — same root cause, weaker symptom; still in scope for a uniform fix, but they are not crashing.

## Confirmed Root Cause

**`schema()` builds the project AST without the configured ignore list.** Evidence chain:

1. `goga/schema/schema.py:185` — `ast_obj = AST(".")` — no `ignore` argument (code).
2. `goga/ast/ast.py:92` — `ignore_set = ... if self._ignore else set()` — `None` → no pruning → `os.walk` descends `.venv/` (code).
3. Live measurement: unfiltered → 160 errors / 12 top-level cells; filtered with the exact `lint.ignore` entries (`build/`, `.venv/`, `example/`) → **0 errors / 1 root cell** (empirical, exact rule split 140+13+7 matches the TODO's 153 Document + 7 AST).
4. `goga/schema/schema.py:188-189` — non-empty `errors` → `ValueError` (code, contract-defined).
5. The schema cell's `documents` practice provides no channel for an ignore list, and the CLI command loads no config — so the delivery path that exists for lint (`lint.py:30-51`) is absent end-to-end on the schema path (trace).

Secondary (same root cause, weaker symptoms): `contract.py:225` discards the already-loaded `lint.ignore`; `tool.py:30` never loads project config. Root cause class: **AST consumers other than lint do not deliver `lint.ignore` to `AST`**.

## Confidence Level

**HIGH** — deterministic causality with a complete evidence chain: source-verified construction sites, live reproduction (160 → 0 by exactly the configured ignore list), rule-level breakdown matching the report, and manifest text explaining why each path behaves as it does.

## Breaking Change Assessment

Proposed change (recommended option, refined in planning): add an optional `ignore: list[str] | None = None` parameter to `schema()`; deliver `lint.ignore` from config in the schema CLI command (lint-style: config optional, swallow loader errors, checkpoint on successful load); deliver the already-loaded ignore in `contract`; load config (same swallow semantics) in `tool._build_ast`.

1. **Existing function call with same arguments → different behavior?** Python-level `schema(cells, max_depth, depends_on)`: **NO** — new parameter defaults to `None`, traversal identical. CLI-level `goga schema` (same invocation): **YES** — on projects whose `lint.ignore` covers manifest-bearing directories, the command now succeeds and excludes those directories; today it crashes (this project) or includes them (projects where ignored dirs are error-free). ⚠ This is the intended bug fix; per policy it is flagged, not dismissed — user approval of the plan is the required override.
2. **Existing file paths change?** **NO** — no files move; only traversal pruning changes.
3. **Output format change?** **NO** — the JSON shape, key order, and projection logic are untouched; the cell set shrinks by ignored directories (currently unreachable output on this repo because the command exits 1).
4. **Return value semantics change?** **NO** for default-argument calls of `schema()`; the CLI's effective result changes as in (1).
5. **Manifest-defined guarantees altered?** **YES, by amendment (not violation)** — `goga/schema` CODEMANIFEST signature/algorithm/`documents` practice and `goga/commands/schema` / `goga/commands/contract` / `goga/commands/tool` algorithm texts gain the ignore-delivery step; the fail-fast and gate guarantees are preserved. Manifest reconciliation is a pipeline step (Step 7).
6. **Existing tests break?** **YES — exactly one pin:** `tests/schema/test_schema.py:984` `test_schema_keeps_the_declared_signature` asserts `list(parameters) == ["cells", "max_depth", "depends_on"]` and must be updated to include the new parameter. All other existing calls stay 3-arg (optional param); CLI tests run in tmp_path projects without `.goga/config.yml` → swallow path → `ignore=None` → byte-identical output (verified against test fixtures: no config files written in `tests/commands/schema`, `tests/schema`).

**BREAKING CHANGE DETECTED** (items 1-CLI and 6; item 5 is a governed amendment) — per policy the pipeline stops for user decision; the plan presentation below doubles as the escalation point. Only the user can approve proceeding.
