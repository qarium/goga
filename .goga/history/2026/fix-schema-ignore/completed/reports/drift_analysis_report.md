# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/schema` | Signature lacked `ignore`; `documents` practice silent on ignore delivery — manifest under-specified the load the code (after fix) performs | Yes — signature extended, practice states the optional verbatim delivery, Requirements pin no-normalization/no-glob |
| `goga/commands/schema` | Manifest described a two-step delegate-and-serialize flow; code now performs a config delivery first — flow text was behind the implementation | Yes — Imports (`load_project_config`, `ProjectConfig`, `project-configuration`; `ConfigHooks`, `ConfigOverlay`), Annotations, and a five-step Algorithm now describe the delivered flow; lint-validated (0 errors) |
| `goga/commands/contract` | Algorithm loaded config yet built `AST` unfiltered — the manifest matched the old code but both drifted from the config's declared purpose (`lint.ignore` existed for traversal exclusion) | Yes — step 2 derives ignore from the effective configuration, step 3 passes it; Requirements record verbatim pass-through |
| `goga/commands/tool` | `build_injections` annotations described the ast injection without the config read the code now performs | Yes — loader-only read documented in the ast bullet + Requirements (never fails on invalid config) |
| `goga/ast` | None — untouched; its constraints verified intact (default `None` traversal unchanged, `.project` skip additive, ignore matching semantics untouched) | N/A (no drift introduced) |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/config` (`project-configuration.md`) | `lint.ignore` documented as consumed by `goga lint` only; four consumers now deliver it | Yes — field-table row and accessor notes reworded to the four-command consumer set |
| `goga/commands/lint` (`lint.md`) | "Ignoring directories" section implied lint-private semantics | Yes — one additive bullet names the sibling consumers; canonical examples and matching rules unchanged |
| `goga/ast` (`loading.md`) | None — already framed ignore generically for consumers | N/A |
| `goga/schema/hooks` (`checkpoints.md`) | None — filter/delivery equivalence already covers load-time filtering | N/A |
| `goga/config/hooks` (`checkpoints.md`) | None — the load-moment amendment recipe matches the schema command's new delivery verbatim | N/A |

## Behavioral Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/schema` (routine) | Intended behavior change: `ignore` excludes directories from tree/errors; default unchanged — user-approved deviation, covered by tests (`test_ignore_excludes_directory_from_tree`, `test_ignore_none_keeps_unfiltered_traversal`) | Yes — approved and tested |
| `goga/commands/schema` | CLI `goga schema` honors `lint.ignore` (was: always unfiltered) — the fix itself; live-verified exit 0 / 91 cells / clean stderr on this repo | Yes — approved and live-verified |
| `goga/commands/contract` | AST built filtered when config present; requested ignored cells now miss the document lookup — tested (`test_contract_honors_lint_ignore_from_config`) | Yes |
| `goga/commands/tool` | `ast` injection tree excludes ignored dirs; invalid config swallowed — tested (`TestBuildAstIgnore`) | Yes |
| `goga/commands/lint` | None — code untouched | N/A |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/schema` | Algorithm step 1 load now carries an argument the text must mention; steps 2-7 (filters, walk, gate, projection) unchanged in code | Yes — text updated; steps 2-7 byte-identical |
| `goga/commands/schema` | New precedence: config delivery (swallow → checkpoint → derive) strictly before the logic invocation; error-conversion semantics untouched | Yes — Algorithm step order matches code (verified by re-reading final `schema.py:59-92`); delegation pins updated (`ignore=None`) |
| `goga/commands/contract` | Ignore derived after language from the same overlay — matches code order; comparison flow untouched | Yes |
| `goga/commands/tool` | `_build_ast` gains a config read before construction; lazy build and error pass-through preserved | Yes |
| `goga/ast` | None — `AST.load()` algorithm and `ignore_set` construction untouched | N/A |

## Resolution Status

**All drift resolved.** Every divergence between specification and implementation found during the change was reconciled in the manifest and usage steps; `goga lint` reports `cells: 91, errors: 0`; the affected test suites pass (321/321); the full-suite failure set is byte-identical to the pre-change baseline (68 infrastructure-dependent build/pipeline tests). No unresolved manifest, usage, behavioral, or algorithmic drift remains.
