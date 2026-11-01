# Change Plan

## Task Classification

**Type: bugfix** (defect: AST consumers other than lint never deliver the configured `lint.ignore` list to `AST`, making `goga schema` fail outright on this repo).

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga/schema` | `goga/schema/schema.py`, `goga/schema/CODEMANIFEST` | `schema()` gains optional `ignore: list[str] \| None = None` param, passed to `AST(".", ignore=ignore)`; manifest signature/annotations/`documents` practice updated |
| `goga/commands/schema` | `goga/commands/schema/schema.py`, `goga/commands/schema/CODEMANIFEST` | Command loads config lint-style (optional, swallow loader errors; `ConfigHooks` checkpoint on successful load; summary lines → stderr), derives `ignore`, forwards it to `schema_logic`; manifest gains Imports (`load_project_config`, `ProjectConfig`, `ConfigHooks`, `ConfigOverlay` + usages `project-configuration`, `checkpoints`) and the algorithm step |
| `goga/commands/contract` | `goga/commands/contract/contract.py`, `goga/commands/contract/CODEMANIFEST` | Derive `ignore` from the already-loaded `overlay.config.lint` and pass to `AST(".", ignore=ignore)`; manifest algorithm step 3 updated |
| `goga/commands/tool` | `goga/commands/tool/tool.py`, `goga/commands/tool/CODEMANIFEST` | `_build_ast()` loads config loader-only (swallow semantics, **no** checkpoint — injection stays transparent), derives `ignore`, passes to `AST`; manifest `build_injections` annotations updated |
| `goga/ast` | — | **No change** — constraint "Do NOT change traversal for consumers that pass ignore=None" preserved; `AST` already implements ignore correctly |
| `goga/config` | `goga/config/.usages/project-configuration.md` | Wording only: `lint.ignore` described as honored by all AST-consuming commands (lint, schema, contract, tool), not only `goga lint` |

## Root Cause Analysis

From Investigation Report (confidence HIGH): `schema()` constructs `AST(".")` without an ignore list (`goga/schema/schema.py:185`). With `ignore=None`, `AST.load()` prunes nothing and `os.walk` descends into `.venv/`, where the manually installed `swax`/`resq` packages ship 22 CODEMANIFESTs. Their contracts are validated against the goga repo root (rules resolve paths from cwd), yielding 140 `import_has_valid_from_path` + 13 `usage_filepath_exists` + 7 `embedded_type_has_low_level` = 160 errors; `schema()` then raises `ValueError` per its fail-fast contract. Verified live: unfiltered → 160 errors; filtered with the exact `lint.ignore` entries → 0 errors. `goga lint` works because it alone delivers `lint.ignore` (`goga/commands/lint/lint.py:30-51`); `goga contract` loads config but discards `lint.ignore`; `goga tool` loads no project config.

## Trace Summary

From Trace Report — four `AST(` construction sites; only lint delivers ignore. Data path to enable: `.goga/config.yml` → `load_project_config()` → `ConfigHooks().amend_config()` → `ConfigOverlay.config.lint.ignore` → `AST(".", ignore)` → `ignore_set` prunes `os.walk` descent. The fail-fast in `schema()` (raise on non-empty `errors`) is contract-defined and stays untouched; the fix removes the foreign errors from the tree before that check.

## Change Strategy

1. **`goga/schema/schema.py`** — add `ignore: list[str] | None = None` as the 4th parameter of `schema()`; construct `AST(".", ignore=ignore)`; document the parameter in the docstring (passed verbatim; `AST` owns matching semantics). No other logic changes — filters, checkpoint walk, and gate operate on the filtered tree exactly as the manifest already prescribes ("filters prune delivery exactly as they prune output").
2. **`goga/commands/schema/schema.py`** — replicate lint's delivery block before the `schema_logic` call: optional config load (any loader exception — `OSError`, `KeyError`, `ValueError`, `yaml.YAMLError` — swallowed → `ignore=None`); on successful load deliver `ConfigHooks().amend_config(config=cfg)` (hard failure of the checkpoint → clean `click.ClickException`, never treated as config-absent); print `overlay.summary_lines` to stderr; derive `ignore = None if overlay.config.lint is None else overlay.config.lint.ignore`; forward as `schema_logic(..., ignore=ignore)`. New imports: `yaml`, `load_project_config`, `ConfigHooks` (relative, per conventions).
3. **`goga/commands/contract/contract.py`** — after the existing config delivery (already loads config + checkpoint + prints summary), derive `ignore` the same way and construct `AST(".", ignore=ignore)`. No new imports.
4. **`goga/commands/tool/tool.py`** — `_build_ast()` gains a loader-only config read: `try: cfg = load_project_config() except (OSError, KeyError, ValueError, yaml.YAMLError): cfg = None`; derive `ignore` from `cfg.lint`; construct `AST(".", ignore=ignore)`. No `ConfigHooks` checkpoint and no output — the injection stays transparent and error pass-through semantics are unchanged (ignored directories are never loaded, so they contribute no errors to pass through). New imports: `yaml`, `load_project_config`.
5. **Manifest reconciliation (per cell above)** — after code + tests stabilize; see Specification Impact.
6. **Usage reconciliation** — `project-configuration.md` wording; `goga/ast/.usages/loading.md` already documents ignore delivery and needs **no** change.

## Specification Impact

- `goga/schema/CODEMANIFEST`: body signature → `"schema(cells: list[str], max_depth: int | None = None, depends_on: list[str] = [], ignore: list[str] | None = None) -> tree: list[SchemaNode]"`; `documents` practice → "The caller must instantiate `AST` with the current CWD path ('.') and may deliver an ignore list of exact relative paths (`ignore=None` keeps traversal unfiltered)"; annotations gain `ignore` parameter description and a requirement: ignore entries flow verbatim to `AST`; ignored directories contribute no cells and no errors.
- `goga/commands/schema/CODEMANIFEST`: header gains Imports from `goga/config` (`load_project_config`, `ProjectConfig`, usage `project-configuration`) and `goga/config/hooks` (`ConfigHooks`, `ConfigOverlay`, usage `checkpoints`); Annotations reference both practices for the ignore derivation; Algorithm gains step: derive ignore (config optional — absent/invalid → `ignore=None`, unfiltered; checkpoint on successful load; summary lines → stderr) and step 1 invocation passes `ignore`.
- `goga/commands/contract/CODEMANIFEST`: Algorithm step 1 adds deriving `ignore` from the effective configuration (`lint is None → None; else lint.ignore`); step 3 becomes "Create `AST` object passing the derived ignore, and load the project using the `loading` practice"; Requirements line: ignore is passed verbatim, `AST` owns matching semantics.
- `goga/commands/tool/CODEMANIFEST`: `build_injections` annotations — the ast injection derivation gains: load project config loader-only (absent/invalid → unfiltered), derive `ignore` from `lint.ignore`, pass to `AST`; constraint kept: no blocking/transforming on `AST` errors.
- `goga/ast/CODEMANIFEST`: unchanged (constraint honored — default `None` traversal untouched).
- `goga/config/CODEMANIFEST`: unchanged (facade already re-exports everything needed).

## Usage Impact

- `goga/config/.usages/project-configuration.md`: `lint.ignore` rows/notes reworded from "excluded from AST traversal by `goga lint`" to "honored by the AST-consuming commands (`lint`, `schema`, `contract`, `tool`)"; semantics (exact relative paths, no glob, `None` when section absent) unchanged.
- `goga/ast/.usages/loading.md`: no change (already documents `ignore` for consumers).
- `goga/schema/hooks/.usages/checkpoints.md`: no change (delivery-set semantics already filter-consistent).
- No cell-level `.usages` files require new entries (no new public API beyond the optional parameter).

## Compatibility Verification

**Python-level backward compatible**: `schema(cells, max_depth, depends_on)` with unchanged arguments behaves identically (new parameter defaults to `None` → unfiltered, per the `goga/ast` constraint). `contract`/`tool` keep their output contracts; tool's error pass-through is preserved.

**NOT fully backward compatible at two flagged points** (Breaking Change Escalation, per Investigation Report):
1. **CLI behavior change (the intended fix)**: `goga schema` on a project whose `lint.ignore` covers manifest-bearing directories now succeeds and excludes them (today: crashes on this repo; on clean projects with ignored dirs, includes them). Same invocation → different outcome — flagged, not dismissed; user approval of this plan is the required override.
2. **One signature-pin test update**: `tests/schema/test_schema.py:984` `test_schema_keeps_the_declared_signature` pins `["cells", "max_depth", "depends_on"]` → updated to include `"ignore"`.

All other existing tests keep their outcomes: CLI schema/contract/tool tests run in tmp_path projects without `.goga/config.yml` → swallow path → `ignore=None` → byte-identical output (verified against fixtures). Config key `lint.ignore` is reused as-is — no config schema change, no user migration.

## Test Strategy

Add (mirroring structure per conventions — tests mirror source):
- `tests/schema/test_schema.py` (logic):
  - `test_ignore_excludes_directory_from_tree`: project with a valid root + a directory holding a broken/foreign manifest; `schema([], None, [], ignore=["that_dir"])` → succeeds, foreign cell absent from tree.
  - `test_ignore_none_keeps_unfiltered_traversal`: same project, no `ignore` → `ValueError` (guards the default the `goga/ast` constraint mandates).
- `tests/commands/schema/test_schema.py` (CLI):
  - honors `lint.ignore` from `.goga/config.yml` → exit 0, ignored dir absent from JSON;
  - no config → unfiltered (current behavior: exit 1 with error count);
  - invalid config (bad YAML) → swallowed, unfiltered, no traceback.
- `tests/commands/contract/test_contract.py`: config with `lint.ignore` → ignored cell not in AST (`document()` for it → error path exit 1 / absent from output); no config → unchanged.
- `tests/commands/tool/test_tool.py`: `_build_ast` honors `lint.ignore` (tree lacks ignored dir); no config / invalid config → unfiltered.
- Update: `test_schema_keeps_the_declared_signature` → `["cells", "max_depth", "depends_on", "ignore"]`.

Validation: `pytest tests/schema tests/commands/schema tests/commands/contract tests/commands/tool -x`, then full `pytest tests/ -x`, `ruff check goga/`, and the live gate: `goga schema` exits 0 with the single root cell `goga`; `goga lint` stays `cells: 91 errors: 0`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Behavior change at CLI level surprises users relying on unfiltered schema output | Low | Medium | This is the fix's purpose; documented in plan + summary lines on stderr; `ignore=None` default preserved at API level |
| Config checkpoint now runs on the schema path (first time) — tool packages amending config affect `goga schema` | Low | Medium | Same surface lint/contract already run; schema tests pin the package environment; checkpoint failure = clean ClickException |
| Duplication of the ~15-line ignore-derivation block (lint ↔ schema) | Certain | Low | Follows the project's per-command delivery idiom (contract already duplicates its config delivery); a shared helper is a refactor out of hotfix scope |
| Tool injection gains a config read — new failure mode for `goga tool` | Low | Low | Loader-only, swallow-all semantics; no checkpoint, no output; worst case = today's unfiltered behavior |
| Hidden consumer of `schema()` beyond the CLI | Ruled out | — | Grep verified: single caller (`goga/commands/schema/schema.py:57`) |
| Scope creep into config-key rename / rule path-resolution redesign | Ruled out | — | Explicitly rejected in Investigation Report; `lint.ignore` reused verbatim |
