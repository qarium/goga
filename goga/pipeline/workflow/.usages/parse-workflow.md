# parse_workflow — workflow-file parser

`parse_workflow` accepts the rendered text of a project-level workflow-file, validates its structure, and
returns a `WorkflowDocument` carrying declarative instructions for the compiler. It
is a pure parser: no file I/O (rendering and reading happen before it — see
`load-workflow`), no agent resolution, no loop
expansion, no stage removal, no approval, manual-launch, or note-buttons logic —
all of that is the compiler's job.

## Accepted structure

Top-level keys: `prompt`, `stages`, `extend`, `memory`, `profile`, `build`,
`assistants`, `delegation`, `repeat`, `gates`.

- `profile` — optional top-level string default naming the workflow's default
  contributor profile (`profile: default`); a non-str value is a structural
  error "non-str value in workflow.profile"; an empty/whitespace value
  normalizes to None. Activation reads this default from the RAW text via the
  load-time peek — a value that materializes only through template rendering
  does not participate in activation.
- `build` — the strict six-field build block (see below).
- `assistants` — the name-keyed catalog map of run-level helpers; the
  per-stage attachments (`stages.<name>.assistants`) are a name-keyed map
  too — each entry a reference (`gate`/`when`, `when` required) or a full
  inline declaration (the catalog field set plus `gate`/`when`).
- `delegation` — the delegation-bounds block (`depth`, `max_tasks`).
- `repeat` — the run-cycle tuning block (`max_cycles`, `keep_runs`; below).

## The build block (workflow.build)

The optional top-level `build:` block carries exactly six fields — `agent`,
`env`, `review.agent`, `review.env`, `review.additional.agent`,
`review.additional.env`. Anything else in the block — **including `proxy` and
`hosts`** — is a structural error "unknown key in workflow.build.…": those are
consumed on the host before the container starts, and the host launcher never
reads workflow files. env maps follow the string-map pattern (str→str —
  a non-str key is a structural error "non-str key in <location>.env", a
  non-str value raises "non-str value in <location>.env.<key>"). A
non-mapping block raises "non-mapping build block in workflow". A workflow
consisting of the `build:` block alone is valid.

## The repeat block (workflow.repeat)

`repeat` is the optional run-cycle tuning block — a map carrying the
engine's vocabulary verbatim. goga materializes no defaults: the block
carries authored values only; whether a `repeat` key is compiled at all is
the pipeline's `repeatable` capability, decided by the compiler.

| Key | Type | Default | Note |
|-----|------|---------|------|
| `max_cycles` | int >= 0 | not authored | at most N complete passes (per `afm`) |
| `keep_runs` | int >= 0 | not authored | recent cycle run-directories to keep (afm default 2) |

`0` is an authored value carried verbatim; its cycle meaning belongs to
afm and is not re-stated here.

Structural validation (parse time):

- a non-mapping value (including `repeat: true`, `repeat: false`, and any
  scalar) → structural error "non-mapping repeat block in workflow"
- an unknown key → structural error "unknown key in workflow.repeat: KEY;
  valid keys: max_cycles, keep_runs"
- a non-int value → structural error "non-int value in
  workflow.repeat.max_cycles" / "non-int value in workflow.repeat.keep_runs"
- a negative value → structural error "max_cycles must be >= 0 in
  workflow.repeat" / "keep_runs must be >= 0 in workflow.repeat"

A boolean is not an integer for these checks. An empty block (`repeat: {}`)
equals absence — the document carries no repeat instruction. A workflow
consisting of the block alone is valid. The workflow-level way to pin a
repeatable pipeline to a single pass is `repeat: {max_cycles: 1}`.

This cell does NOT act on `repeat` — no cycle counting, no stop conditions,
no pruning. The compiler emits the block (authored keys only) for a
repeatable pipeline and rejects it for a non-repeatable one; the engine owns
every cycle semantic.

## The gates blocks (settings + per-stage steps)

`gates` is the stage quality-gate instruction set: an optional top-level
settings block (`patience`, `max_iterations`, `fresh_correction` — authored
keys only, an empty block equals absence, a workflow consisting of the block
alone is valid) and an optional per-stage list of check steps in the stages
block (an empty list equals absence). Each step carries a required `name`
(the dashboard label), exactly one of `script` (a shell check) / `agent`
(an AI review), and optional `timeout`/`prompt` (`prompt` belongs to an
`agent` step — it is forbidden on a `script` step); value grammar (durations,
name text) is engine-owned. Every structural violation raises a one-line
error naming the workflow location.

## Per-stage override keys (workflow.stages.<name>)

| Key | Type | Notes |
|-----|------|-------|
| agent | str | agent name composed into the wrapper path by the compiler |
| env | map[str]str | per-stage environment variables — string map, literal and/or rendered; declarative — consumed by the pipeline run coordination's wrapper generation, NOT the compiler; an empty map equals absence; stages block only |
| prompt | str | per-stage prompt → compiler `description` field |
| loop | int (>=1) | expand the stage into N copies |
| skills | list[str] | merged with the stage's pipeline-file skills |
| skip | bool | instruct the compiler to DELETE the stage |
| approve | str ("auto"/"plan"/"dialog") | auto-approval directive; one of the three accepted; declarative |
| manual | bool | manual-launch instruction; strictly bool; stages block only; declarative |
| notes | map[str]str | note buttons — map "note name → prompt text"; compiled into the stage's `buttons` field; stages block only; declarative |
| reflect | map {file, mode?} | memory-reflection instruction — reflect method only; compiled into the stage's `reflect` field; stages block only; declarative |
| memory | bool | memory-participation instruction — alignment method only; `true` participates, `false` equals absence; compiled into the stage's `memory_use` field; stages block only; declarative |
| assistants | map | the stage's assistant attachments keyed by assistant name — a reference (`gate`/`when`) or a full inline declaration; `when` is required on every entry; an empty map equals absence; stages block only; declarative (override-style entries — no prompt/skills — are valid declarations; content resolves at compilation) |
| gates | list | the stage's check steps — a required `name`, exactly one of `script`/`agent`, optional `timeout`/`prompt` (`prompt` on `agent` steps only); an empty list equals absence; compiled into the stage's `verify` gate; stages block only; declarative |

## The notes field

`notes` is an optional per-stage instruction (stages block only) carrying note
buttons — a map of "note name → prompt text". Structurally validated at parse
time:

- a non-map value → structural error "non-mapping notes in workflow.stages.<name>"
- a non-str value inside the map → structural error "non-str value in
  workflow.stages.<name>.notes.<key>"

| In the workflow-file | WorkflowStage.notes | Meaning |
|----------------------|---------------------|---------|
| key absent | None | no instruction — the stage compiles without `buttons` |
| `notes: {...}` non-empty | the map | the compiler emits the stage's `buttons` field with the same keys and values |
| `notes: {}` empty | None | equals absence — no `buttons` in the output |

This cell does NOT act on `notes`. The compiler consumes it: a non-None notes
map becomes the per-stage `buttons` field of the flow-file (canonical slot
right after `description`); every loop-expanded copy carries the same
`buttons`; a skipped stage never reaches the application. Interpretation of
the buttons belongs to afm — goga only compiles the field.

`notes` applies to extend-stages by name: note buttons of a new stage from
`extend` are authored in the same workflow-file as
`stages.<new-stage-name>.notes` — there is no separate authoring inside an
extend-entry.

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

`env` is forbidden in an extend-entry (structural error "env is forbidden in
workflow.extend.<name>") — `env` is valid ONLY under `stages.<name>`; the
environment of a new stage is authored in the stages block by the new stage's
name.

`notes` is forbidden in an extend-entry (structural error "notes is forbidden
in workflow.extend.<name>") — note buttons of a new stage are authored in the
stages block by the new stage's name.

`reflect` and `memory` are forbidden in an extend-entry (structural errors
"reflect is forbidden in workflow.extend.<name>" / "memory is forbidden in
workflow.extend.<name>") — memory participation of a new stage is authored in
the stages block by the new stage's name.

`assistants` is forbidden in an extend-entry (structural error "assistants is
forbidden in workflow.extend.<name>") — the attachments of a new stage are
authored in the stages block by the new stage's name.

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
  workflow.stages.<name>: trigger; valid keys: agent, env, prompt, loop, skills,
  skip, approve, manual, notes, reflect, memory, assistants"
- in an extend-entry body it is legal and passes through verbatim — the compiler
  validates its value (`on_success` | `manual`) at compilation time

## Empty-workflow rule

A workflow is empty only when `prompt`, `stages`, `extend`, `memory`, `build`,
`assistants`, `delegation`, AND `repeat` are ALL absent — `profile` never
counts (activation is not content). The structural error "empty workflow"
names the content options. A workflow consisting of the `build:` block alone
is valid; a workflow consisting of the `repeat:` block alone is valid; a
workflow carrying only `profile: name` is not.

## The approve field

`approve` is an optional, declarative auto-approval directive. The accepted
values are "auto", "plan", and "dialog"; any other value (or a non-str) is a
structural error raised at parse time:

- stages-block: "approve must be one of: auto, plan, dialog in workflow.stages.<name>"
- extend-entry: "approve must be one of: auto, plan, dialog in workflow.extend.<name>"

This cell does NOT act on `approve`. The compiler consumes it and applies two
INDEPENDENT effects, each value driving a subset: for a stage with
`approve: "auto"` the stage body's `communication: true` is suppressed (no
`interactive: true`) AND its `roles` containing `planner` emits
`auto_approve: true`; `approve: "plan"` drives only the `interactive`
suppression (communication effect); `approve: "dialog"` drives only the
`auto_approve` emission (roles effect).

## Anti-patterns

- Do not perform approval, manual-launch, or note-buttons logic here — this cell
  stays declarative.
- Do not pass `approve` into the extend-entry `body` — it is extracted inline.
- Do not author `manual` in an extend-entry — the launch mode of a new stage
  belongs to its body (`trigger`).
- Do not author `notes` in an extend-entry — note buttons of a new stage are
  authored in the stages block by its name.
- Do not author `trigger` in the stages block — it is a stage-body field, not a
  workflow modifier.
- Do not author a scalar `repeat` in the workflow-file — the short form
  belongs to the compiled flow-file, not to the authoring surface; a
  missing block already means the compiled default.
