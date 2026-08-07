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

## approve (workflow directive: auto | plan | dialog)

`approve` is a per-stage / extend-entry workflow field — a declarative directive
with three accepted values: `auto`, `plan`, `dialog` (any other value, or a
non-str, is rejected by `parse_workflow` before compilation). For a stage whose
effective `approve` is set, the compiler reads the trigger fields from THAT
STAGE'S BODY (pipeline-file body for an existing stage; the extend-stage body for
an extend-stage) and applies up to two INDEPENDENT effects, each fired by its own
body trigger AND driven by its own subset of directives:

| Effect | Body trigger | Directives that drive it |
|--------|--------------|--------------------------|
| SUPPRESS interactive | communication: true (the communication→interactive translation is skipped; no interactive key; communication: false is unaffected → interactive: false) | auto, plan |
| EMIT auto_approve: true | roles contains planner (canonical slot next to interactive) | auto, dialog |

Directive → effects matrix:

| `approve`  | suppress interactive | emit auto_approve |
|------------|:--------------------:|:-----------------:|
| (absent)   | —                    | —                 |
| `auto`     | ✓                    | ✓                 |
| `plan`     | ✓                    | —                 |
| `dialog`   | —                    | ✓                 |

So `auto` drives BOTH effects; `plan` drives only the interactive suppression
(the communication effect — a `planner` stage does NOT emit `auto_approve`);
`dialog` drives only the `auto_approve` emission (the roles effect —
`communication: true` still becomes `interactive: true`). Each effect fires on
its own trigger AND its own directive subset; an effective `approve` whose subset
is empty, or whose trigger is absent, is a no-op. Effects apply uniformly to
every loop-expanded copy. The directive is read from the workflow; the triggers
from the body — the compiler joins them. PipelineDocument is unaffected
(output-side only).

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
