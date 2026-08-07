# parse_workflow — workflow-file parser

`parse_workflow` reads a project-level workflow-file, validates its structure, and
returns a `WorkflowDocument` carrying declarative instructions for the compiler. It
is a pure parser: no I/O beyond the path it receives, no agent resolution, no loop
expansion, no stage removal, no approval logic — all of that is the compiler's job.

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

## Extend-entry keys (workflow.extend.<name>)

Positioning: `before`, `after` (list[str]; at least one required).
Inline overrides extracted into the model (excluded from body): `agent`, `loop`,
`approve` (one of "auto"/"plan"/"dialog").
Body: the verbatim stage content (title, prompt, skills, roles, communication,
script directives, …) — everything except before/after/agent/loop/approve/depends_on.

## The approve field

`approve` is an optional, declarative auto-approval directive. The accepted
values are "auto", "plan", and "dialog"; any other value (or a non-str) is a
structural error raised at parse time:

- stages-block: "approve must be one of: auto, plan, dialog in workflow.stages.<name>"
- extend-entry: "approve must be one of: auto, plan, dialog in workflow.extend.<name>"

This cell does NOT act on `approve`. The compiler (goga/pipeline/compiler)
consumes it and applies two INDEPENDENT effects, each value driving a subset:
for a stage with `approve: "auto"` the stage body's `communication: true` is
suppressed (no `interactive: true`) AND its `roles` containing `planner` emits
`auto_approve: true`; `approve: "plan"` drives only the `interactive`
suppression (communication effect); `approve: "dialog"` drives only the
`auto_approve` emission (roles effect).

## Anti-patterns

- Do not perform approval logic here — this cell stays declarative.
- Do not pass `approve` into the extend-entry `body` — it is extracted inline.
