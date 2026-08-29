# compile_flow — pipeline-file → afm flow-file compiler

`compile_flow` compiles a goga DSL pipeline-file into an afm flow-file. It parses
and detects the body format, applies per-stage workflow overrides + loop-expansion
+ skip-removal, assembles each `FlowStage` in canonical key order, serializes via
`serialize_flow`, writes the flow-file, and returns (PipelineDocument, FlowDocument).

## Stage-body field translation (canonical order)

Output FlowStage fields, canonical order:
interactive, auto_approve, auto_run, command, prompt, description, buttons, agents, supervisor,
supervisor_prompt, skills, script_before, script, script_after, script_timeout, <unknown A-Z>.

Authoring key → output key (the authoring key is consumed, not passed through):
- communication → interactive (value true/false)
- trigger → auto_run (manual ⇒ auto_run: false; on_success/absent ⇒ no key)
- before_script → script_before
- script → script
- after_script → script_after
- timeout → script_timeout (verbatim str; requires script; omitempty)
- notes (workflow.stages.<name>) → buttons (map verbatim; slot right after
  description; omitempty)
- roles → agents (via translate_role; default ["auto"] when absent/empty). In a body
  carrying `script`, NO agents key is emitted at all (afm rejects the combination) —
  neither the default nor a translated roles value — while the roles elements are still
  validated (a non-str element → structural error, same as without script)

An authoring auto_run key is rejected ("auto_run key is forbidden in stage body;
use trigger: manual") — auto_run is a runtime key, authored as trigger.

## trigger (stage-body: on_success | manual) & manual (workflow: bool)

`trigger` is a full stage-body field (pipeline-file stage or extend-stage body);
`manual` is a workflow stages-block instruction (strictly bool). Together they
control the manual (human-triggered) launch mode of a stage, compiled into the
afm per-stage key `auto_run: false`.

Stage body:

- `trigger: manual` → the flow stage carries `auto_run: false` in the canonical
  slot immediately after `auto_approve`
- `trigger: on_success` (explicit) or no trigger → no `auto_run` key
  (byte-identical output for pipelines without trigger/manual)
- any other value (incl. `on_failure`) → structural error "trigger must be one
  of: on_success, manual"
- authoring `auto_run` in a stage body → structural error "auto_run key is
  forbidden in stage body; use trigger: manual"

Workflow `stages.<name>.manual` (applied after embed and skip-removal):

| manual | Effect |
|--------|--------|
| (absent) | the stage body's trigger decides |
| `true` | force manual — `auto_run: false` over any trigger; idempotent on an already-manual stage (no error) |
| `false` | cancel the RESULTING manual state (pipeline-file body OR extend body) — the `auto_run` key disappears; on a non-manual stage → structural error "manual: false on non-manual stage <name>" |

Interactions:

- `skip: true` wins — the stage is removed entirely; trigger/manual never apply
- loop-expansion: every copy of a manual stage carries `auto_run: false`
- `PipelineDocument` is unaffected (output-side only; source bodies never mutated)

## notes (workflow directive: map str→str) → buttons (flow-file)

`notes` is a per-stage workflow instruction carrying note buttons — a map of
"note name → prompt text". The compiler translates it into the afm per-stage
key `buttons`.

- authoring source is SINGLE: `workflow.stages.<name>.notes`. An authoring
  `buttons` key in a stage body (pipeline-file stage or extend-stage body) is a
  structural error — "buttons key is forbidden in stage body; use notes in
  workflow.stages"
- a non-empty notes map assembles `buttons` (the map verbatim — keys and values
  unchanged) into the canonical slot immediately after `description`
- `notes: {}` (empty map) equals absence — no `buttons` key in the output
- `notes` applies per stage name to extend-stages as well (note buttons of a new
  stage are authored as `stages.<new-stage-name>.notes`; `notes` in an
  extend-entry is rejected by the workflow parser)
- loop-expanded copies carry the same `buttons`
- `skip: true` wins — the stage is removed before the notes application
- a name absent from both the pipeline body and the extend-stages raises the
  existing structural error "unknown stage name in workflow.stages: <name>"
- `PipelineDocument` is unaffected (output-side only; source bodies never mutated)
- interpretation of the buttons belongs to afm — the compiler only assembles and
  serializes the field

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

## Stage timeout directive

`timeout` is a string stage-body directive (pipeline-file stage or extend-stage
body) translated to the afm per-stage key `script_timeout`.

- `timeout: "30m"` with `script` in the same body → the flow stage carries
  `script_timeout: 30m` in the canonical slot immediately after `script_after`
- a non-string value (int/bool/null/list/map) → structural error naming the stage
- `timeout` without `script` (before_script/after_script do not open the
  directive — script_timeout scopes to the script action) → structural error
  naming the stage
- the value passes verbatim — goga does not validate the Go duration grammar;
  a malformed string (e.g. "3 min") reaches the flow-file as-is and fails in
  afm at runtime
- the key is emitted only when authored (omitempty); a pipeline without
  `timeout` compiles byte-identically (no script_timeout key anywhere)
- direct authoring of `script_timeout` in a stage body is not forbidden
  (same stance as direct `script_before`); when both `timeout` and a direct
  `script_timeout` are authored, the translated `timeout` value wins
- loop-expanded copies inherit `script_timeout` verbatim; `PipelineDocument`
  is unaffected (output-side only)

## Key presence

Stages without approve, without notes, without script directives, without
communication/roles changes, and without a manual-effective trigger produce
no auto_approve / buttons / auto_run / script_* / script_timeout keys — those
keys appear only when their source directive is present.
