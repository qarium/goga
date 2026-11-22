# Test Report

## Changes Requiring Coverage

| Change | Type |
|---|---|
| Workflow parser skips hidden dot-prefixed top-level keys | behavior |
| Hidden keys never satisfy the empty-workflow rule | edge |
| Ordinary unknown top-level keys still rejected (selectivity) | regression |
| Pipeline anchor carriage across the `---` separator (header → body) | behavior |
| Hidden body keys dropped before stage assembly (no bogus stage) | behavior/edge |
| Anchor + alias within one segment (no hidden key needed) | regression |
| Alias-before-anchor and duplicate-across-segments failures wrapped | edge |
| Invalid YAML wrapped as `StructuralError("invalid YAML in pipeline-file")` | behavior |
| Extra separator line → `StructuralError("extra body separator")` | edge |
| No-separator / four-dash messages preserved | regression |
| CRLF pipeline files parse with anchor carriage | regression |
| Empty / comment-only / leading-separator header keeps "header missing name/description" | regression |
| Anchored pipeline + workflow compile end-to-end through `compile_flow` | integration |

## Tests Added

| Test Name | File | What It Validates |
|---|---|---|
| `TestParseWorkflowAnchors::test_hidden_anchor_key_with_stage_merge` | `tests/pipeline/workflow/test_parse_workflow_logic.py` | `.anchor` + `<<:` merge into a stage yields merged fields |
| `TestParseWorkflowAnchors::test_hidden_anchor_key_block_merge_into_stages` | same | The TODO's example: whole stages merged into the `stages` block |
| `TestParseWorkflowAnchors::test_hidden_key_scalar_value_is_skipped` | same | Hidden-key value shape is irrelevant (skipped, not validated) |
| `TestParseWorkflowAnchors::test_hidden_key_alone_is_empty_workflow` | same | A hidden key alone does not satisfy the empty-workflow rule |
| `TestParseWorkflowAnchors::test_unknown_key_still_rejected_next_to_hidden_key` | same | Tolerance is selective — ordinary unknown keys still error |
| `TestParseWorkflowAnchors::test_alias_reuse_within_stages` | same | Plain aliases work with no hidden key |
| `TestParseDslAnchors::test_header_anchor_merged_into_stages_stage` | `tests/pipeline/compiler/test_parse_dsl.py` | RC2: header anchor merges into a STAGES stage |
| `TestParseDslAnchors::test_hidden_body_key_with_merge` | same | RC3: hidden body key merges, never becomes a stage |
| `TestParseDslAnchors::test_hidden_body_key_alone_is_dropped` | same | Unused hidden body key is dropped |
| `TestParseDslAnchors::test_header_anchor_merged_into_phases_item` | same | Header anchor merges into a PHASES list item |
| `TestParseDslAnchors::test_alias_within_body_segment` | same | Body-internal alias reuse (regression) |
| `TestParseDslAnchors::test_alias_before_anchor_raises_wrapped` | same | Sequential alias order still fails, wrapped |
| `TestParseDslAnchors::test_duplicate_anchor_across_segments_raises_wrapped` | same | Anchor name reuse across segments fails, wrapped |
| `TestParseDslAnchors::test_invalid_yaml_raises_structural_error` | same | Damaged YAML → clean structural error |
| `TestParseDslAnchors::test_extra_separator_raises` | same | Third document → "extra body separator" |
| `TestParseDslAnchors::test_crlf_file_parses` | same | CRLF file with anchors parses |
| `TestParseDslAnchors::test_empty_header_segment_keeps_message` | same | Empty header keeps today's message |
| `TestParseDslAnchors::test_leading_separator_keeps_message` | same | Leading separator keeps today's message |
| `TestCompileFlowAnchors::test_compile_flow_with_anchored_pipeline_and_workflow` | `tests/pipeline/compiler/test_compile_flow_workflow.py` | End-to-end: anchored pipeline body + anchored workflow stages compile; merged content reaches `FlowDocument`; no bogus stage |

Plus one locked behavior updated (disclosed error-type change, not a coverage gap): `tests/pipeline/test_describe_pipelines.py::test_describe_pipelines_aborts_on_damaged_yaml` now asserts `StructuralError("invalid YAML in pipeline-file")` instead of raw `yaml.YAMLError` — the test's stated intent (atomic abort, single file read) is unchanged and still asserted.

## Test Results

| Test Run | Status | Details |
|---|---|---|
| New anchor tests (19) | PASS | 19/19 |
| Full suite | PASS | 8552 passed, 8 skipped (baseline before change: 8533 passed) |
| `ruff check goga/ tests/` | PASS | All checks passed |
| `ruff format --check` | PASS | All files formatted |

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| Hidden-key skip (workflow) | Yes | 6 tests incl. selectivity and empty-workflow edge |
| Anchor carriage (pipeline) | Yes | STAGES, PHASES, CRLF, cross-segment failure modes |
| Error wrapping and document-count dispatch | Yes | Wrapped invalid YAML, extra separator, empty/leading header, alias-order, duplicate anchor |
| Preserved legacy messages | Yes | No-separator and four-dash covered by pre-existing tests (still green) plus CRLF/empty-body regressions in new tests |
| End-to-end compile | Yes | One integration test through `compile_flow` |

## Missing Coverage Analysis

Nothing material is untested. Two deliberate exclusions: (1) the exact PyYAML `compose_document` override is covered behaviorally (carriage, order-sensitivity, duplicate detection) rather than by mocking internals — mocking the loader would test the mock, not the behavior; (2) profile/home YAML loading (`load_home_profiles`, `resolve_profile`) is intentionally out of scope per the approved plan.
