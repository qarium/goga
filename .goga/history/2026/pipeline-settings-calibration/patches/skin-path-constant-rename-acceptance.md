# Acceptance: skin-path constant rename + skin gutter reset

Acceptance of commits `5ca0392c` (fix: reset native button styling on
file-view line-number gutter) and `eee6a3ab` (refactor: rename skin-path
constants to match their shapes) — the diff this run's worker handed to
commit-changes. Run: `Editor-20261105-222054-5b52`, stage `accept-result`.

## Summary

The acceptance pipeline (scope → manifest review → usage review → test
assessment → report) verified the semantic-swap rename of the two private
skin-path module constants and the additive skin CSS reset. Code,
CODEMANIFEST, cell usages, project usages, and tests already agreed — zero
discrepancies, zero fixes required. Lint is clean (92 cells, 0 errors),
`goga contract goga/pipeline` exits 0 with the facade carrying all 20
contract types, the full `tests/pipeline/` suite is green (1763 passed),
and ruff passes on every changed file.

## Acceptance Scope

| Cell | Path | Change types |
|---|---|---|
| pipeline | `goga/pipeline` | CODE (`afm_config.py`, `afm_skin.py`, asset `goga/assets/afm/skin/goga.css`), TEST (`tests/pipeline/conftest.py`, `tests/pipeline/test_afm_skin.py`) |

Affected dependencies (imports): `goga/commands/pipeline` (DIRECT —
usages-only import from `goga/pipeline`). The rename touches private
module constants (leading underscore, absent from the facade and every
manifest/usages text), and the CSS edit changes asset content only —
zero dependent impact.

Change inventory:

- `_SKINS_DIR` → `_SKIN_DIR` (`afm_config.py` — definition + `skin_dir`
  usage + cross-file comment now citing `_SKINS_TARGET_BASE/_SKIN_NAME`),
  `_SKIN_TARGET_BASE` → `_SKINS_TARGET_BASE` (`afm_skin.py` — definition
  + 2 usages). Pure identifier rename: the string values
  `"/home/goga/.afm/skins/goga"` and `Path("/home/goga/.afm/skins")` are
  byte-identical, so the emitted afm config YAML and runtime behavior are
  unchanged. The two test-side `monkeypatch.setattr` attribute strings
  follow in lockstep.
- `.file-line-num` reset appended to the packaged `goga.css` (the gutter
  cell is a `<button>`; the inlined v1.2.4 stack never reset the native
  button background/border).

## CODEMANIFEST Status

**CONSISTENT** — 0 updates.

- Pre-flight `goga lint`: 92 cells, 0 errors.
- `goga contract goga/pipeline`: exit 0; both changed routines match —
  `write_afm_config (agent, flow, workflow) -> config_path: Path` and
  `materialize_afm_skin() -> skin_dir: Path`; facade `__all__` carries
  exactly the 20 contract types (verified both directions).
- Algorithm comparison: `materialize_afm_skin` implements its manifest
  algorithm step-for-step (resolve relative to the module → validate-all
  before touching the target → reset → flat verbatim copy → return); the
  rename alters none of it. `write_afm_config` behavior is untouched; the
  five static launcher fields including `skin_dir:
  /home/goga/.afm/skins/goga` are intact.
- Completeness: no new public entities or routines; the renamed constants
  are private module internals (LOW — no manifest action). Old names
  return zero matches outside the immutable history patch record.
- CSS asset: the `default_skin` practice explicitly frees the skin file
  set and content — "the skin evolves with the package without a contract
  change" — and the file-name list (index.css, goga.css, favicon.png,
  title.txt) is unchanged, so the appended rule needs no manifest change.
- Baseline audit: `convention` usage and the base annotations are present
  verbatim in the manifest header.

## Usages Status

**CONSISTENT** — no updates needed. `run-pipeline.md` (config write,
`skin_dir` value, skin materialization after the write) and the project
`afm` practice (`skin_dir`/materialization mechanism) describe the
unchanged behavior and values. Integrity holds: every `Usages` key
resolves, every imported usage exists (lint-verified), and every key is
referenced in annotations (`convention` 21, `afm` 10, `argparse` 2,
`cli_entrypoint` 2, `default_prompts` 5, `default_skin` 8 refs).

## Test Coverage Assessment

**EXCELLENT** for the changed surface:

- Materialization contract/logic: facade import, flat verbatim copy,
  packaged-directory resolution, reset/idempotency, missing/empty
  pre-run errors, survival of the previous skin on failed validation
  (`test_afm_skin.py`, 7 tests).
- Config-write `skin_dir`: asserted by value (`test_afm_config.py:100,145`,
  `test_afm_config_collaboration.py:290`) — value-level assertions that
  would catch any accidental constant-value change while being inherently
  rename-safe.
- The rename itself is covered in lockstep by the two monkeypatch
  attribute strings; a missed site would fail loudly (the old attribute
  no longer exists).
- The CSS rule has no test surface by design — asset content, same
  category as `favicon.png`/`title.txt`, and the contract explicitly
  places the file set outside test obligations.

Runs: targeted `test_afm_skin.py` + `test_afm_config.py` +
`test_afm_config_collaboration.py` — 44 passed; full `tests/pipeline/` —
**1763 passed, 0 failed**; `ruff check` on all four changed Python files —
all checks passed.

## Critical Findings

None.

## Warnings

| Source | Finding | Recommendation |
|---|---|---|
| Usage (INFO) | `per-stage-env.md` and `collaboration-delivery.md` in `goga/pipeline/.usages/` are imported by no CODEMANIFEST (the only importer of the cell is `goga/commands/pipeline`, which takes six other usages) | pre-existing, outside this diff; record for a follow-up import-or-merge decision — not modified here per the acceptance invariants |

## Applied Updates

- this report file (no CODEMANIFEST, usages, code, or test edits were
  required)

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| rename accidentally changes a path value | none observed | diff shows byte-identical string values; value-level test assertions and the full suite pass |
| `.file-line-num` reset regresses other skin elements | low | rule is scoped to the single gutter class, additive at end of file; dashboard skin is re-materialized per launch from this package |

## Verdict

**ACCEPTED_WITH_NOTES** — no critical findings and no fixes were needed:
manifest, usages, and tests were already consistent with both commits.
The single INFO note (two cell-level usage files without an importing
manifest) is pre-existing and outside this diff, and does not block
acceptance.
