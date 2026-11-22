# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| `goga/pipeline/workflow/.usages/parse-workflow.md` | DIRECTLY AFFECTED |
| `goga/pipeline/compiler/.usages/parse-dsl.md` | DIRECTLY AFFECTED |
| `goga/pipeline/workflow/.usages/load-workflow.md` | INDIRECTLY AFFECTED |
| `goga/pipeline/compiler/.usages/compile-flow.md`, `serialize-flow.md`, `collaboration-emission.md`, `memory-emission.md` | UNAFFECTED |
| `goga/pipeline/workflow/.usages/assistants.md`, `gates.md`, `memory.md`, `profiles.md` | UNAFFECTED |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| `parse-workflow.md` | New "YAML links and hidden declaration keys" subsection under "Accepted structure": the dot-key idiom, a `.anchor` + `<<:` worked example, the empty-workflow caveat, and the anchor-without-hidden-key note | The Accepted-structure list alone no longer describes the full top-level grammar |
| `parse-dsl.md` | New "YAML links and shared starting points" section (header/body anchor example, PHASES caveat, failure modes); Errors table gained the "invalid YAML in pipeline-file" and "extra body separator" rows | The split-parse contract changed to the stream parse with anchor carriage; the error surface changed |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `load-workflow.md` | YES | Step 6 ("parses the rendered text through the standard grammar … unchanged rules; rendering never bypasses validation") stays true — the grammar extension is documented in `parse-workflow.md`, and Jinja rendering precedes YAML parsing, so anchors are unaffected by the chain order |

## Canonical Patterns Status

**Preserved.** Both files keep their section structure, table formats, and example style; the additions are new subsections in the established voice. No existing example was rewritten — all pre-existing examples still parse identically (the full suite including shipped-workflow tests is green).

## Consistency Summary

**Consistent.** `goga lint` passes (94 cells, 0 errors); every DIRECTLY AFFECTED usage now documents the implemented behavior, each documented example matches a green test case, and INDIRECTLY/UNAFFECTED usages were verified against the reconciled implementation.
