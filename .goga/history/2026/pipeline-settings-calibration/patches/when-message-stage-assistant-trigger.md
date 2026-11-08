# Change: `when: message` — the on_message stage-assistant trigger

Task Classification: **extension** (new value in a closed authoring vocabulary,
backward compatible).

## Summary

Added `when: message` as the fourth engagement value of a stage-assistant
attachment in the workflow-file. It authors the resting engagement of the afm
engine: no initial request is sent — the helper waits idle until messaged,
each message is one turn, and the helper stays attached afterwards. The parser
accepts the value (`_WHEN_VALUES`), the compiler translates it
(`message → on_message`), and the engine (afm v2.2.5) validates the emitted
flow. `gate` stays combinable with it (user decision — the engine owns the
completion semantics; the risk is documented in `assistants.md`).

## Root Cause

Not a defect — a vocabulary extension. The `when` set is closed at
`parse_workflow.py` (`_WHEN_VALUES`) and translated 1:1 at
`compile_flow.py` (`_WHEN_TRIGGER`); a value missing from the dict would raise
`KeyError` at the attachment loop, so both sites must grow together.

## Evidence (engine, afm v2.2.5)

- `afm validate` rejects invalid triggers with `trigger must be "one_shot",
  "checkpoints", "on_completion", or "on_message"` — the accepted 4-value set.
- A hand-built flow with `trigger: on_message` validates OK with both
  `mode: advisory` and `mode: required`.
- A real goga-compiled workflow using `when: message` validates OK
  (end-to-end: workflow-file → parse_workflow → compile_flow → afm validate).

## Modified Cells

| Cell | Files Modified |
|---|---|
| goga/pipeline/workflow | parse_workflow.py, workflow_assistant.py, CODEMANIFEST, .usages/assistants.md |
| goga/pipeline/compiler | compile_flow.py, flow_assistant.py, CODEMANIFEST, .usages/collaboration-emission.md |
| tests | test_parse_workflow_assistants.py, test_compile_flow_collaboration.py |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| vocabulary | goga/pipeline/workflow/parse_workflow.py | `_WHEN_VALUES` gains `message` (last); error message derives from the tuple and now lists four values; two docstrings updated |
| model doc | goga/pipeline/workflow/workflow_assistant.py | `when` docstring lists `message` with its resting-engagement meaning |
| mapping | goga/pipeline/compiler/compile_flow.py | `_WHEN_TRIGGER` gains `"message": "on_message"` |
| model doc | goga/pipeline/compiler/flow_assistant.py | `trigger` docstring lists the fourth mapping |
| manifest | goga/pipeline/workflow/CODEMANIFEST | the attachment `when` vocabulary lists four values; the resting semantics and gate combinability stated |
| manifest | goga/pipeline/compiler/CODEMANIFEST | the trigger mapping table gains `message → on_message` |
| usage | goga/pipeline/workflow/.usages/assistants.md | `when` table row; resting-engagement paragraph; `gate: true` warning (stage waits for a verdict that only a message can produce) |
| usage | goga/pipeline/compiler/.usages/collaboration-emission.md | `trigger` table row; mapping note |

Untouched by design (verified): the overlay merge carries `when` verbatim
(`overlay.py`), `serialize_flow.py` writes `trigger` verbatim, and
`afm_config.py` materializes profiles trigger-independently.

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| test_parse_attachment_when_message_is_accepted | tests/pipeline/workflow/test_parse_workflow_assistants.py | `when: message` parses and is carried, with `gate: true` |
| test_compile_when_message_maps_to_on_message | tests/pipeline/compiler/test_compile_flow_collaboration.py | the mapping and the serialized `trigger: on_message` |
| test_compile_when_message_combines_with_gate | tests/pipeline/compiler/test_compile_flow_collaboration.py | `mode: required` + `trigger: on_message` (gate orthogonality) |
| (updated) invalid-`when` parametrized case | tests/pipeline/workflow/test_parse_workflow_assistants.py | the error message enumerates four values |

## Validation Results

- Full suite: **8048 passed, 8 skipped** (baseline before the change: 135/135
  in the affected area).
- `ruff check goga/ tests/`: clean.
- `goga lint`: 92 cells, 0 errors.
- `goga drift`: no drift entries for the affected cells (7 pre-existing
  entries in unrelated cells).
- End-to-end: goga-compiled flow with `when: message` → `afm validate` OK.

## Compatibility Status

Backward compatible. Two formally-NO guard checkboxes were intrinsic to a
closed-vocabulary extension and were explicitly covered by the approved plan
(the invalid-value error message enumerates one more permitted value; one
vocabulary test updated). Existing valid inputs map identically; output
format, paths, signatures, defaults unchanged.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| an author combining `gate: true` with `when: message` stalls a stage until the helper is messaged | medium | documented warning in `assistants.md`; user decision A (allow, engine owns semantics) |
| a future engine version changing its trigger set | low | the engine's 4-value set was verified empirically at implementation time |

## Updated Files

- goga/pipeline/compiler/.usages/collaboration-emission.md
- goga/pipeline/compiler/CODEMANIFEST
- goga/pipeline/compiler/compile_flow.py
- goga/pipeline/compiler/flow_assistant.py
- goga/pipeline/workflow/.usages/assistants.md
- goga/pipeline/workflow/CODEMANIFEST
- goga/pipeline/workflow/parse_workflow.py
- goga/pipeline/workflow/workflow_assistant.py
- tests/pipeline/compiler/test_compile_flow_collaboration.py
- tests/pipeline/workflow/test_parse_workflow_assistants.py
