# Change Execution Report — List payloads for every `script` key

## Summary

Every `script` key in the pipeline and workflow authoring surfaces now
accepts the script's lines as a list of strings, in addition to the existing
single-string form. A list payload is joined with newlines into ONE
multi-line script string at the parse/compile boundary — shell-identical to
authoring the same text as a block scalar. The internal models stay
string-typed (`WorkflowGateStep.script`, the `FlowStage` `script_*`
fields), so the serializer (block-literal emission) and the stage/gate env
wrappers are untouched.

Covered surfaces (the complete `script`-key inventory):

| Surface | Keys | Normalization point |
|---|---|---|
| Pipeline-file stage body (STAGES format) | `before_script`, `script`, `after_script` | `compile_flow._canonical_fields` → `_normalize_script_directives` |
| Pipeline-file phase body (PHASES format) | the same three | the same path |
| Workflow `extend.<name>` entry body | the same three | the same path |
| Workflow gate step `stages.<name>.gates[i]` | `script` | `parse_workflow._validate_gate_step_payload(allow_lines=True)` |

`agent` stays a single string (an agent alias, never a list);
`timeout`/`script_timeout` stay duration strings.

## Motivation

User request (branch `add-gates-to-workflow`, ad-hoc stage): "давай добавим
для всех script ключей в pipeline и workflow возможность передавать массив
строк". Before the change a list-valued gate `script` was a parse error,
and a list-valued stage-body script directive silently compiled into a YAML
list in the flow-file — a shape the engine rejects at load (verified on the
pre-change tree). The change turns both into one supported, validated
authoring form and gives the pipeline path a clean compile-time error for
malformed payloads.

## Implemented Changes

| Change | File | Description |
|--------|------|-------------|
| Gates script list form | goga/pipeline/workflow/parse_workflow.py | `_validate_gate_step_payload` gains `allow_lines` (script-only): a non-empty list of non-empty strings joins with `\n`; scalar defects keep the exact legacy message, list defects raise `script must be a non-empty list of non-empty strings in <scope>`; `agent` keeps the string-only rule |
| Script directive normalization | goga/pipeline/compiler/compile_flow.py | `_normalize_script_directives` validates/joins the translated `script_before`/`script`/`script_after` values in `_canonical_fields` after the exclusivity check, before the timeout directive; non-str/non-list values raise `<authored-key> must be a string or a non-empty list of non-empty strings in stage <name>` (message names the AUTHORED key) |
| Contract | goga/pipeline/workflow/CODEMANIFEST | Gates global annotation, rule 6.1.15, `WorkflowGateStep` entity/property annotations describe the list form and both messages |
| Contract | goga/pipeline/compiler/CODEMANIFEST | "Stage script directives" paragraph, `compile_flow` algorithm step 5, `FlowStage`/`FlowVerifyStep` annotations describe the join and the new error |
| Usage | goga/pipeline/workflow/.usages/gates.md | `script` type row, a list example, the new error line |
| Usage | goga/pipeline/workflow/.usages/parse-workflow.md | Gates step grammar mentions the joined list form |
| Usage | goga/pipeline/compiler/.usages/compile-flow.md | Script-directives section: the list form, an example, the error message |
| Docs | docs/features/pipelines/pipeline-file.md | Type tables (`string or list of strings`) and a list example in Script directives |
| Docs | docs/features/pipelines/workflows.md | Gates step table, a list example, the error messages in Rules |

## Tests Added

| Test | File | What It Validates |
|------|------|-------------------|
| test_compile_script_directives_list_payloads_joined | tests/pipeline/compiler/test_compile_flow.py | All three directives as lists → joined `script_*`; block-literal serialization for multi-line, plain scalar for single-line |
| test_compile_single_element_list_script_stays_single_line | tests/pipeline/compiler/test_compile_flow.py | A one-element list joins to the element — no invented newline |
| test_compile_phases_list_script_joined | tests/pipeline/compiler/test_compile_flow.py | The PHASES body format joins identically |
| test_compile_workflow_extend_list_script_joined | tests/pipeline/compiler/test_compile_flow.py | An extend-stage body joins identically |
| test_compile_script_directive_bad_payload_raises (×6) | tests/pipeline/compiler/test_compile_flow.py | Empty list / empty element / non-str element / non-str scalar per directive → the exact message naming the authored key |
| test_step_list_script_joined_into_one_multiline_string | tests/pipeline/workflow/test_parse_workflow_gates.py | Gates list script → one joined `str`; model stays str |
| test_step_single_element_list_script_joins_to_the_element | tests/pipeline/workflow/test_parse_workflow_gates.py | One-element list → the element |
| test_step_agent_list_stays_a_structural_error | tests/pipeline/workflow/test_parse_workflow_gates.py | An agent list keeps the legacy scalar error |
| 3 parametrized rejection rows | tests/pipeline/workflow/test_parse_workflow_gates.py | Empty list / empty element / non-str element → the list-form message |
| test_list_form_gate_script_compiles_to_joined_run | tests/pipeline/compiler/test_compile_flow_gates.py | The joined payload reaches the compiled verify `run` and serializes as a block literal |

## Validation Results

- pytest tests/ — 8262 passed, 8 skipped
- ruff check goga/ tests/ — all checks passed
- goga schema — validates
- Full-repo YAML scan — no in-repo file authors a non-string script payload (the new strictness breaks nothing)

## Compatibility Status

Compatible (approved plan). Scalar payloads behave byte-identically
everywhere. The two behavior deltas are both upgrades of previously broken
states: a list gate script was a parse error and now joins; a malformed
stage-body script value previously compiled into an engine-rejected
flow-file and now fails at compile time naming the stage and the authored
key. No existing documented error message changed.

## Updated Files

- goga/pipeline/workflow/parse_workflow.py
- goga/pipeline/compiler/compile_flow.py
- goga/pipeline/workflow/CODEMANIFEST
- goga/pipeline/compiler/CODEMANIFEST
- goga/pipeline/workflow/.usages/gates.md
- goga/pipeline/workflow/.usages/parse-workflow.md
- goga/pipeline/compiler/.usages/compile-flow.md
- docs/features/pipelines/pipeline-file.md
- docs/features/pipelines/workflows.md
- tests/pipeline/compiler/test_compile_flow.py
- tests/pipeline/compiler/test_compile_flow_gates.py
- tests/pipeline/workflow/test_parse_workflow_gates.py
- .goga/history/2026/add-gates-to-workflow/patches/script-list-payloads.md (this report)
