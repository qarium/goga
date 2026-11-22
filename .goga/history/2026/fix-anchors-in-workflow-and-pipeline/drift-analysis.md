# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/pipeline/workflow` | Manifest step 5 mandated rejection of EVERY non-listed top-level key while the implementation now skips hidden dot-prefixed keys | YES — step 5 and Requirements amended in the same change; `goga lint` green |
| `goga/pipeline/compiler` | Manifest steps 1-3 described split-then-two-loads parsing while the implementation now does split-pre-check + single anchor-carrying stream parse; no clause covered YAML-error wrapping | YES — steps 1-3 rewritten and four Requirements bullets added; `goga lint` green |
| `goga/pipeline` | Source docstrings documented `yaml.YAMLError` propagation from `parse_dsl` (contracts themselves use behavior-level wording) | YES — docstrings aligned to the contracts ("structurally malformed — invalid YAML included"); the contracts needed no change |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/pipeline/workflow` | `parse-workflow.md` "Accepted structure" listed only the twelve keys — silent about the hidden-key idiom and YAML links | YES — new subsection with a worked example and the empty-workflow caveat |
| `goga/pipeline/compiler` | `parse-dsl.md` documented the split-parse contract and an error table without the wrapped-YAML/extra-separator rows; nothing about anchor carriage | YES — new "YAML links and shared starting points" section + two new error rows |
| `goga/pipeline/workflow` (indirect) | `load-workflow.md` chain description | NO DRIFT — verified truthful against the final implementation |

## Behavioral Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/pipeline/workflow` | `.anchor`-style top-level keys: error → accepted-and-skipped (the task's requested behavior) | YES — intended, approved by the user (q1), covered by 6 tests |
| `goga/pipeline/compiler` | Header-declared anchors and hidden body keys: error → resolved/dropped (the task's requested behavior) | YES — intended, approved, covered by 12 tests + 1 integration test |
| `goga/pipeline/compiler` | Raw `yaml.YAMLError` leaks → `StructuralError("invalid YAML in pipeline-file")`; extra `---` → `StructuralError("extra body separator")` | YES — disclosed in the plan and compatibility report, approved; one consumer test updated to the new contract |
| — | Every currently-valid input parses byte-identically; all 8533 pre-existing tests (minus the one error-type lock, updated) stay green | VERIFIED — full suite 8552 passed |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga/pipeline/workflow` | `_extract_top_level` gained a skip branch before the unknown-key rejection — ordering of all other validations unchanged | YES — manifest algorithm matches the code branch-for-branch |
| `goga/pipeline/compiler` | `parse_dsl` internal flow: split pre-check → stream parse → document-count dispatch → header validation → body normalization + hidden-key drop → body build; `_parse_header` takes a parsed mapping (private helper, facade unchanged) | YES — manifest steps 1-5 describe exactly this flow; deep-copy isolation and assistants extraction untouched |
| User docs (`docs/features/pipelines/*`) | Not part of the goga triple; checked anyway — every documented parser statement remains true (separator requirement, error names) | NO DRIFT — documenting the new anchor authoring in user docs was not in the approved scope; cell usages carry it |

## Resolution Status

**All drift resolved.** No unresolved manifest, usage, behavioral, or algorithmic drift. Final gates: `goga lint` 94 cells / 0 errors; `ruff check` clean; `ruff format --check` clean; full test suite 8552 passed / 8 skipped.
