# compile_flow — pipeline-file → afm flow-file compiler

`compile_flow` compiles a goga DSL pipeline-file into an afm flow-file. It parses
and detects the body format, applies per-stage workflow overrides + loop-expansion
+ skip-removal, assembles each `FlowStage` in canonical key order, serializes via
`serialize_flow`, writes the flow-file, and returns (PipelineDocument, FlowDocument).

## Stage-body field translation (canonical order)

Output FlowStage fields, canonical order:
interactive, auto_approve, command, prompt, description, agents, supervisor,
supervisor_prompt, skills, script_before, script, script_after, <unknown A-Z>.

Authoring key → output key (the authoring key is consumed, not passed through):
- communication → interactive (value true/false)
- before_script → script_before
- script → script
- after_script → script_after
- roles → agents (via translate_role; default ["auto"] when absent/empty)

## approve: auto (workflow directive)

`approve` is a per-stage / extend-entry workflow field (value "auto" only). For a
stage whose effective `approve` is "auto", the compiler reads the trigger fields
from THAT STAGE'S BODY (pipeline-file body for an existing stage; the
extend-stage body for an extend-stage) and applies two INDEPENDENT effects:

| Trigger (in stage body) | Effect (when approve == "auto") |
|-------------------------|---------------------------------|
| communication: true | SUPPRESS interactive — the communication→interactive translation is skipped (no interactive key). communication: false is unaffected (→ interactive: false). |
| roles contains planner | EMIT auto_approve: true (canonical slot next to interactive). |

Both fire together when both triggers are present. approve: "auto" with neither
trigger is a no-op. Effects apply uniformly to every loop-expanded copy. The
directive is read from the workflow; the triggers from the body — the compiler
joins them. PipelineDocument is unaffected (output-side only).

## Stage script directives

before_script, script, after_script are string stage-body directives that
translate (word-order reversal) to script_before, script, script_after.

Structural error: a stage body that carries script together with prompt
and/or skills is rejected at compile time — "script is mutually exclusive with
prompt/skills in stage <name>". before_script/after_script are compatible
with prompt/skills/script (no error).

## Backward compatibility

Stages without approve, without script directives, and without
communication/roles changes compile byte-identically to before. The new keys
appear only when their source directive is present.
