# parse_workflow — workflow-file parser

`parse_workflow` reads a project-level workflow-file, validates its structure, and
returns a `WorkflowDocument` carrying declarative instructions for the compiler. It
is a pure parser: no I/O beyond the path it receives, no agent resolution, no loop
expansion, no stage removal, no approval or manual-launch logic — all of that is
the compiler's job.

## Accepted structure

Top-level keys: `prompt`, `stages`, `extend`.

## Per-stage override keys (workflow.stages.<name>)

| Key | Type | Notes |
|-----|------|-------|
| agent | str | agent name composed into the wrapper path by the compiler |
| prompt | str | per-stage prompt → compiler `description` field |
| loop | int (>=1) | expand the stage into N copies |
| skills | list[str] | merged with the stage's pipeline-file skills |
| skip | bool | instruct the compiler to DELETE the stage |
| approve | str ("auto"/"plan"/"dialog") | auto-approval directive; one of the three accepted; declarative |
| manual | bool | manual-launch instruction; strictly bool; stages block only; declarative |

## Extend-entry keys (workflow.extend.<name>)

Positioning: `before`, `after` (list[str]; at least one required).
Inline overrides extracted into the model (excluded from body): `agent`, `loop`,
`approve` (one of "auto"/"plan"/"dialog").
Body: the verbatim stage content (title, prompt, skills, roles, communication,
`trigger`, script directives, …) — everything except before/after/agent/loop/
approve/depends_on.

`manual` is forbidden in an extend-entry (structural error "manual is forbidden
in workflow.extend.<name>") — the launch mode of a new stage is authored in its
body via `trigger`, not via workflow instructions.

## The manual field

`manual` is an optional per-stage instruction (stages block only) controlling the
manual (human-triggered) launch mode of a pipeline stage. The value is strictly
bool; a non-bool value is a structural error raised at parse time:

- "non-bool value in workflow.stages.<name>.manual"

Three states, carried into `WorkflowStage.manual`:

| In the workflow-file | WorkflowStage.manual | Meaning |
|----------------------|----------------------|---------|
| key absent | None | no instruction — the stage's own `trigger` decides |
| `manual: true` | True | force the manual launch mode (compiler emits `auto_run: false`) |
| `manual: false` | False | explicitly cancel the resulting manual state (compiler error when the stage is not manual) |

This cell does NOT act on `manual`. The compiler consumes it: `true` forces
`auto_run: false` idempotently; `false` cancels the resulting manual state and is
a compile-time structural error ("manual: false on non-manual stage <name>") when
there is nothing to cancel.

## The trigger field

`trigger` is a full stage-body field, not a workflow key:

- in the stages block it is an unknown key → structural error "unknown key in
  workflow.stages.<name>: trigger; valid keys: agent, prompt, loop, skills,
  skip, approve, manual"
- in an extend-entry body it is legal and passes through verbatim — the compiler
  validates its value (`on_success` | `manual`) at compilation time

## The approve field

`approve` is an optional, declarative auto-approval directive. The accepted
values are "auto", "plan", and "dialog"; any other value (or a non-str) is a
structural error raised at parse time:

- stages-block: "approve must be one of: auto, plan, dialog in workflow.stages.<name>"
- extend-entry: "approve must be one of: auto, plan, dialog in workflow.extend.<name>"

This cell does NOT act on `approve`. The compiler
consumes it and applies two INDEPENDENT effects, each value driving a subset:
for a stage with `approve: "auto"` the stage body's `communication: true` is
suppressed (no `interactive: true`) AND its `roles` containing `planner` emits
`auto_approve: true`; `approve: "plan"` drives only the `interactive`
suppression (communication effect); `approve: "dialog"` drives only the
`auto_approve` emission (roles effect).

## Anti-patterns

- Do not perform approval or manual-launch logic here — this cell stays declarative.
- Do not pass `approve` into the extend-entry `body` — it is extracted inline.
- Do not author `manual` in an extend-entry — the launch mode of a new stage
  belongs to its body (`trigger`).
- Do not author `trigger` in the stages block — it is a stage-body field, not a
  workflow modifier.
