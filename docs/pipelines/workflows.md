# Workflows

A **workflow-file** is an optional YAML document that layers project-specific
behavior on top of a compiled pipeline at run time. A workflow can inject a
top-level prompt, override the agent or prompt of specific stages, expand
a stage into N chained copies via `loop`, **skip (delete) a stage**,
declare per-stage **auto-approval** via `approve`, force or cancel a stage's
**manual launch mode** via `manual`, attach **note buttons** to a stage via
`notes`, and **declaratively add new stages** to the pipeline via `extend`.

Stage names in `workflow.stages` are matched strictly: a name that does not
match any pipeline step or extend-stage is a compile error. Workflows that
reference names absent from the target pipeline must be split or pruned.

Workflow-files live at:

```
<cwd>/.goga/workflows/<name>.yml
```

They are **project-only** — there is no user-level workflow directory. The
name must be a bare filename resolved inside `.goga/workflows/`; path
traversal via `..` or an absolute prefix is rejected.

## Document shape

A workflow-file is a YAML mapping with up to three top-level keys:

```yaml
prompt: |
  Top-level prompt injected as the first directive of the compiled pipeline.

stages:
  <stage-name>:
    agent: codex              # optional per-stage agent override
    prompt: |                 # optional per-stage prompt override
      Additional per-stage instruction.
    loop: 2                   # optional iteration count (>= 1)
    skills: [web-search]      # optional skills merged with the pipeline stage's skills
    approve: auto             # optional auto-approval directive: auto | plan | dialog
    notes:                    # optional note buttons compiled to the afm `buttons` field
      fix: Fix the failure and continue

extend:
  <new-stage-name>:
    after: [propose]          # position the new stage relative to existing ones
    title: Warmup             # optional display label; defaults to the entry key
    prompt: |                 # any other stage field passes through verbatim
      Bootstrap instruction for the new stage.
```

| Key      | Type   | Required | Description                                                |
|----------|--------|----------|------------------------------------------------------------|
| `prompt` | string | no*      | Top-level prompt emitted as the first key of the output.   |
| `stages` | map   | no*      | Per-stage override instructions keyed by stage name.       |
| `extend` | map   | no*      | New stages to add to the pipeline, keyed by new stage name. |

\* At least one of `prompt`, a non-empty `stages` block, or a non-empty
`extend` block must be present; an empty workflow is rejected with a
structural error.

Unknown top-level keys are rejected with
`unknown key in workflow: <KEY>; valid keys: prompt, stages, extend`.

## Stage entries

Each entry under `stages` is keyed by stage name and accepts up to eight
fields:

| Field   | Type     | Default | Description                                                                                              |
|---------|----------|---------|----------------------------------------------------------------------------------------------------------|
| `agent` | string   | —       | CLI agent name (e.g. `codex`, `claude`, `cursor`, `opencode`, `qwen`). Selects which agent runs this stage. See [Workflow `agent` — choosing the CLI agent](#workflow-agent-choosing-the-cli-agent). |
| `prompt`| string   | —       | Per-stage context prompt. Lower precedence than the stage's own `prompt` — closer to a section description than to a direct instruction. See [Workflow `prompt` — context, not command](#workflow-prompt-context-not-command). |
| `loop`  | int      | —       | Positive iteration count (`>= 1`). When `>= 2`, the stage is expanded into N chained copies.           |
| `skills`| string list | —   | Skill names merged with the pipeline stage's own `skills` (pipeline-first, deduplicated by value). See [Skills merge](#skills-merge). |
| `skip`  | bool     | —       | When `true`, the compiler DELETES this stage from the compiled pipeline (the stage is absent from the flow-file entirely). Dependents of the skipped stage are transparently reconnected to its predecessors (no dangling references). `false` (or an absent key) leaves the stage in place. `skip` is allowed ONLY in the `stages` block — it is a structural error under `extend`. `skip` wins over `agent`/`prompt`/`loop`/`skills` overrides on the same entry. |
| `approve` | string | —     | Auto-approval directive. Accepted values are `auto`, `plan`, and `dialog`; any other value (or a non-string) is a structural error. Each value drives a subset of two INDEPENDENT effects the compiler applies to the stage body (see [Auto-approval (`approve: auto/plan/dialog`)](#auto-approval-approve-auto-plan-dialog)): (1) **communication effect** — if the body has `communication: true`, the stage's `interactive` output is SUPPRESSED (omitted, not `false`); (2) **roles effect** — if the body's raw `roles` contain `planner`, the stage emits `auto_approve: true`. `auto` drives BOTH effects; `plan` drives only the communication effect; `dialog` drives only the roles effect. Allowed in both `stages` and `extend` (inline default override; a `stages` entry wins per-field). |
| `manual` | bool | —     | Manual-launch instruction, `stages` block only. `true` forces the manual launch mode: the compiler emits `auto_run: false` for the stage, overriding any authored `trigger` in its body. `false` cancels a manual state coming from either body source (a pipeline-file `trigger: manual` or an extend body `trigger: manual`) and is a structural error (`manual: false on non-manual stage <NAME>`) when the stage is not manual. An absent key means no instruction — the stage's own `trigger` decides. The three states (`true`/`false`/absent) are distinct; a non-bool value (including `null`) is a structural error. Allowed ONLY in `stages` — it is a structural error under `extend` (a new stage's launch mode is authored in its body via `trigger`). `skip` wins over `manual`: a skipped stage is removed before the manual instruction is applied. See [Manual launch (`manual` and `trigger`)](#manual-launch-manual-and-trigger). |
| `notes` | map of str→str | — | Note buttons — a map of "note name → prompt text" compiled verbatim into the stage's afm `buttons` field (canonical slot after `description`). Single-line texts serialize as plain scalars, multi-line texts as block literals. An empty map equals absence (no `buttons` key emitted). Allowed ONLY in `stages` — it is a structural error under `extend` (an extend-stage receives its buttons through the `stages` block by name). Every `loop`-expanded copy carries the same buttons; `skip` wins over `notes`. Interpretation of the buttons belongs to afm — the compiler only assembles and serializes the field. See [Note buttons (`notes`)](#note-buttons-notes). |

Rules:

- Only `agent`, `prompt`, `loop`, `skills`, `skip`, `approve`, `manual`, `notes` are valid. An
  unknown key is rejected with `unknown key in workflow.stages.<NAME>: <KEY>; valid keys:
  agent, prompt, loop, skills, skip, approve, manual, notes`.
- `loop` must be an int `>= 1`. Zero, negative values, and non-int types
  raise a structural error.
- `skills` must be a `list[str]`. A non-list (or a list with non-string
  elements) raises `non-list-of-str skills in workflow.stages.<NAME>`.
- `skip` (when present) must be a `bool`. A non-bool value raises
  `non-bool value in workflow.stages.<NAME>.skip`. `skip` is allowed only in
  the `stages` block — it is a structural error under `extend` (see
  [Skipping a stage](#skipping-a-stage)).
- `approve` (when present) must be one of the strings `auto`, `plan`, or
  `dialog`. A non-string value raises `non-str value in
  workflow.stages.<NAME>.approve`; any other string raises `approve must be
  one of: auto, plan, dialog in workflow.stages.<NAME>` (see
  [Auto-approval (`approve: auto/plan/dialog`)](#auto-approval-approve-auto-plan-dialog)).
- `manual` (when present) must be a `bool`. A non-bool value (including an
  explicit `null`) raises `non-bool value in workflow.stages.<NAME>.manual`.
  `manual` is allowed only in the `stages` block — it is a structural error
  under `extend`.
- `notes` (when present) must be a mapping with string values. A non-mapping
  value (including an explicit `null`) raises `non-mapping notes in
  workflow.stages.<NAME>`; a non-string value raises `non-str value in
  workflow.stages.<NAME>.notes.<KEY>`. An empty map is treated as absence.
  `notes` is allowed only in the `stages` block — it is a structural error
  under `extend` (see [Note buttons (`notes`)](#note-buttons-notes)).
- The stage value must be a mapping. Non-mapping values raise
  `non-mapping stage <NAME> in workflow.stages`.
- Stage names are validated against the target pipeline: a name that does not
  match any step in the pipeline or any `extend`-stage is a structural error.
- `agent` is not validated against a known agent set. Absence of the
  corresponding wrapper file is surfaced at run time.

### Workflow `agent` — choosing the CLI agent

> **Two different `agent` concepts.** The pipeline-file stage field
> `roles` names the **roles** that organize the work inside a stage —
> `planner`, `executor`, `reviewer` (plus the always-on `summary`
> report). See [stage modes](pipeline-file.md#roles). The workflow-file
> stage field `agent` (singular) is a different concept: it names the
> **CLI agent** that runs the stage — `claude`, `codex`, `cursor`,
> `opencode`, or any other installed wrapper. The two are orthogonal.

A workflow's per-stage `agent` field lets the **same pipeline run different
stages on different CLI agents**. This is what makes a pipeline portable
across CLI tools: you keep one pipeline-file (the work to be done) and
express "stage X should run on codex, stage Y on claude" in a
project-level workflow-file, without forking the pipeline.

Each `agent` value resolves to a wrapper script installed in the goga image
at `/home/goga/bin/<agent>-as-claude.sh`. The wrapper presents the named
CLI agent to the pipeline runner in a uniform invocation shape, so the
pipeline itself does not care which concrete CLI is underneath.

The canonical baseline wrappers shipped with the image — `claude`, `codex`,
`cursor`, `opencode`, `qwen` — and their per-agent environment variables are
documented in [Agents](../configuration/agents.md) under
the Configuration reference. This page keeps the workflow-scoped agent
semantics (per-stage override, inline-extend agent); the wrapper set
itself is shared with build and pipeline.

Any other value is permitted as long as the corresponding wrapper file
exists in the image — absence is surfaced at run time, not at validation
time.

When a stage does **not** specify an `agent` in the workflow, the pipeline
uses its global default agent — typically `claude`. Setting `agent`
per-stage overrides that default for the named stage only; other stages
keep the global default.

### Workflow `prompt` — context, not command

The per-stage `prompt` in a workflow-file is **not** a direct instruction
to the agent. Its weight is lower than the stage's own `prompt` field
declared in the [pipeline-file](pipeline-file.md#stage-fields), and it is
closer in role to a section description: it sets context, frames the
stage's intent, and gives the agent additional background to interpret the
stage's main prompt against.

Two consequences follow from this lower precedence:

- The workflow `prompt` does **not** override or replace the stage's own
  `prompt`. The stage's declared prompt remains the authoritative
  instruction; the workflow `prompt` sits beside it as additional context.
- The workflow `prompt` does **not** by itself command the agent to take
  specific actions. Free-form prose is interpreted as background, not as
  a directive.

To make a workflow `prompt` carry actual requirements, follow the
explicit labeled format the goga prompts already use — sections like
`Requirements:`, `Constraints:`, `Algorithm:`. Labeled blocks are
recognized as instructions and are honored as such; unstructured prose is
not.

Example — descriptive context only (no enforceable requirements):

```yaml
stages:
  propose:
    prompt: |
      This stage formalizes the user's request into a task document.
      It runs early in the lifecycle and shapes the rest of the pipeline.
```

Example — context with enforceable requirements (the labeled block is
honored as an instruction):

```yaml
stages:
  propose:
    prompt: |
      Task formalization process.

      Requirements:
      - Examine all link connections between cells carefully.
      - Do not write code examples in the task.

      Constraints:
      - Do not build architecture in the task.
```

In the second form, the `Requirements:` and `Constraints:` blocks are the
load-bearing parts — the leading paragraph is still just context.

### Skipping a stage

A `stages` entry may set `skip: true` to remove the named stage from the
compiled pipeline. The stage disappears from the flow-file entirely, and its
dependents are **transparently reconnected**: any stage that depended on the
skipped stage instead depends on the skipped stage's own predecessors. Chains
are resolved transitively — in `A → B → C`, skipping `B` makes `C` depend on
`A`; skipping both `A` and `B` makes `C` depend on whatever `A` depended on
(nothing, in the limit). For a **phases** pipeline, removal is positional (the
next stage simply chains to the new predecessor). `skip` wins over
`agent`/`prompt`/`loop`/`skills` overrides on the same entry, and removing
every stage is a structural error (`empty body`).

```yaml
stages:
  task-review:
    skip: true
```

### Auto-approval (`approve: auto`, `plan`, `dialog`)

A `stages` (or `extend`) entry may set an `approve` directive to drive the afm
auto-approval behavior for that stage at compile time. The directive is one of
three values — `auto`, `plan`, or `dialog` — chosen from a closed set, not a
free-form flag, so any other string (or a non-string) is a structural error.

The compiler applies two **independent** effects to the stage body, and each
directive drives a subset of them:

1. **`interactive` suppression** (the **communication effect**) — if the stage
   body has `communication: true`, the stage's `interactive` afm output is
   SUPPRESSED (the key is omitted entirely, NOT emitted as `interactive:
   false`). This makes an otherwise user-prompting stage run non-interactively.
   `communication: false` (or no `communication` key) is unaffected —
   suppression fires only when `communication is True`.
2. **`auto_approve` emission** (the **roles effect**) — if the stage body's raw
   `roles` list contains `planner`, the stage emits `auto_approve: true` (the
   afm per-stage auto-approval key, in the canonical slot right after
   `interactive`). The match is against the authored role alias `planner`,
   captured before the compiler translates it to the afm stem `planning`.

| `approve`   | communication effect (suppress `interactive`) | roles effect (emit `auto_approve`) |
|-------------|:----------------------------------------------:|:----------------------------------:|
| *(absent)*  | —                                              | —                                  |
| `auto`      | ✓                                              | ✓                                  |
| `plan`      | ✓                                              | —                                  |
| `dialog`    | —                                              | ✓                                  |

So `auto` is the full directive (both effects, as before); `plan` keeps the
communication effect but turns the roles effect OFF (a `planner` stage does NOT
emit `auto_approve`); `dialog` keeps the roles effect but turns the
communication effect OFF (`communication: true` still becomes `interactive:
true`). The two effects are independent: each fires on its own trigger AND its
own directive subset. With neither trigger present, the directive is a no-op on
the body (it still threads through; it just has nothing to act on).

```yaml
stages:
  deploy:
    approve: auto      # or plan, or dialog
```

Under `extend`, `approve` is an inline default override exactly like inline
`agent`/`loop` (see [Inline agent, loop, and approve overrides](#inline-agent-loop-and-approve-overrides)):
it is extracted from the entry (never reaches the body), and a `stages` entry
naming the same stage wins per-field.

### Manual launch (`manual` and `trigger`)

A stage's launch mode has two authoring surfaces that meet in the compiler:

- The **stage body** (a pipeline-file stage or an `extend` body) carries a
  `trigger` field — `on_success` (the default) or `manual`. `trigger: manual`
  compiles to the afm `auto_run: false` key (see
  [Pipeline files](pipeline-file.md)): the stage pauses when reached and runs
  only when launched manually. An authoring `auto_run` key in a body is a
  structural error — the output key is assembled by the compiler, never
  authored.
- The **workflow `stages` block** carries `manual` — a force/cancel instruction
  applied ON TOP of the body, without editing the pipeline-file:

| `manual`     | Effect on the stage                                            |
|--------------|----------------------------------------------------------------|
| *(absent)*   | No instruction — the body's own `trigger` decides.             |
| `true`       | Forces manual: the stage compiles with `auto_run: false`, overriding any authored `trigger`. Idempotent on a stage that is already manual. |
| `false`      | Cancels manual: an effective `trigger: manual` (from the pipeline-file body or an `extend` body) is rewritten to `on_success`, so no `auto_run` key is emitted. A structural error when the stage is NOT manual (`manual: false on non-manual stage <NAME>`) — cancelling a state that does not exist is an authoring mistake, not a no-op. |

```yaml
stages:
  deploy:
    manual: true   # hold the deploy stage for manual launch
```

`manual` is allowed ONLY in the `stages` block — under `extend` it is a
structural error (`manual is forbidden in workflow.extend.<NAME>`): a new
stage's launch mode is authored in its own body via `trigger`, never via a
workflow instruction. `skip` wins over `manual`: a skipped stage is removed
before the manual instruction is applied, so `skip: true` + `manual: true`
on one entry simply deletes the stage. On a `loop`-expanded stage every copy
carries the launch mode of the original.

### Note buttons (`notes`)

A workflow's per-stage `notes` field attaches **note buttons** to a stage: a
map of "note name → prompt text" that the compiler emits verbatim as the
stage's afm `buttons` field (in the canonical slot right after
`description`).

```yaml
stages:
  deploy:
    notes:
      fix: Fix the failure and continue
      investigate: |
        Gather diagnostics for the failure.
        Include the last 50 log lines.
```

- The map passes through verbatim — keys and values unchanged, authoring
  order preserved. Single-line texts serialize as plain scalars (quoted as
  needed); multi-line texts serialize as block literals.
- Buttons are authored ONLY through this instruction. An authoring
  `buttons` key in a stage body (a pipeline-file stage or an `extend` body)
  is a structural error (`buttons key is forbidden in stage body; use notes
  in workflow.stages`) — there is exactly one authoring source, so the
  compiler-assembled field can never collide with an authored one.
- `notes` is allowed ONLY in the `stages` block — under `extend` it is a
  structural error (`notes is forbidden in workflow.extend.<NAME>`). An
  extend-stage receives its buttons through the `stages` block by its name,
  like any other stage.
- An empty map (`notes: {}`) equals absence — no `buttons` key is emitted.
  A pipeline compiled without notes is byte-identical to one compiled
  without a workflow.
- Every `loop`-expanded copy carries the same buttons, and `skip` wins over
  `notes`: a skipped stage is removed before the buttons are resolved, so
  its notes never leak into a survivor.
- Interpretation of the buttons belongs to afm — the compiler only assembles
  and serializes the field.

## Extending the pipeline with new stages

The `stages` block only overrides stages that already exist in the target
pipeline. The `extend` block does the complementary thing: it **adds brand-new
stages** that are not in the pipeline-file at all. Each `extend` entry is one
new stage, positioned relative to existing stages via `before` / `after`:

```yaml
extend:
  <new-stage-name>:
    before: [plan]            # place this new stage BEFORE the named stage(s)
    after: [propose]          # place this new stage AFTER the named stage(s)
    agent: codex              # optional: default agent override for the new stage
    loop: 2                   # optional: default loop override (>= 2 expands)
    title: Warmup             # optional; any other stage field passes through
    prompt: |                 # verbatim stage body — same fields as a pipeline stage
      Bootstrap the environment before the pipeline runs.
```

Positioning (`before` / `after`), default overrides (`agent` / `loop` /
`approve`), and the stage body are separate concerns:

- `before` and `after` are **lists of existing stage names**. The new stage is
  declared to run before the `before` names and after the `after` names. At
  least one of the two must be present — an entry with neither is rejected.
- `agent`, `loop`, and `approve` are optional **default overrides** extracted
  from the entry (see [Inline agent, loop, and approve overrides](#inline-agent-loop-and-approve-overrides)).
- Everything else in the entry (`title`, `prompt`, `skills`, `roles`,
  `communication`, `trigger`, or any other stage field) is the **verbatim body** of the new
  stage. It is carried through unchanged and embedded as an ordinary stage in
  the compiled output. `before`, `after`, `agent`, `loop`, `approve`, and
  `depends_on` are never part of the body — `agent`/`loop`/`approve` are
  extracted as override fields, and `depends_on` is forbidden here (positioning
  is declared structurally, not as a dependency edge). `trigger` IS part of the
  body: a new stage's launch mode is authored right there (`trigger: manual`
  compiles to `auto_run: false`), which is why the workflow `manual` key is
  forbidden in an `extend` entry (see
  [Manual launch (`manual` and `trigger`)](#manual-launch-manual-and-trigger));
  `skip` is likewise forbidden (a new stage has nothing to skip).
- The `title` field, when omitted, falls back to the entry key — so a stage
  declared under `extend: warmup:` without a `title` is still labeled
  `warmup` in the output.

Extend-stage names are **first-class members** of the workflow's name set:
they are valid targets for `stages` entries and for other extend-entries'
`before`/`after` refs (cross-references between extend-stages resolve). The
new stage is always inserted; if a name collides with an existing stage, the
duplicate is surfaced downstream by afm. Dangling `before`/`after` refs —
names in neither the original pipeline body nor any extend-stage — are
**structural errors** raised before the embed (see
[How the compiler applies a workflow — Pass 0a0-pre](#pass-0a0-pre-strict-validation-of-extend-refs)).

### Positioning semantics by body format

How `before` / `after` translate into run order depends on the compiled
body format of the target pipeline:

- **Stages format** — the compiler derives `depends_on` edges from the names.
  Each `after` name is added to the new stage's `depends_on` (so the new stage
  runs after it), and the new stage's name is added to the `depends_on` of each
  `before` target (so they run after it). Existing `depends_on` on the targets
  is preserved — the new edge is appended, not overwritten. Execution order is
  then governed entirely by `depends_on`, exactly as for any other stage.
- **Phases format** — the compiler inserts the new stage **positionally**:
  immediately after the last `after` target and/or immediately before the
  first `before` target. Run order comes from list position, not `depends_on`.
  When `after` and `before` targets place the stage inconsistently, the
  `after` position wins. Every `before`/`after` target is guaranteed to exist
  by Pass 0a0-pre (see [How the compiler applies a workflow](#how-the-compiler-applies-a-workflow)).

### Inline agent, loop, and approve overrides

Alongside positioning, an extend entry may carry inline `agent`, `loop`, and
`approve` fields. They are extracted from the body exactly like
`before`/`after` — they never reach the compiled stage as separate fields — and
act as **default overrides** for the new stage, mirroring what a `stages` entry
provides for an existing stage:

- `agent` (a string) is composed into the stage's `command` wrapper path by
  the same template as a `stages`-block `agent`
  (`/home/goga/bin/<agent>-as-claude.sh`).
- `loop` (an int `>= 1`; `>= 2` expands) expands the new stage into
  `<name>-1..N` chained copies by the same rules as a `stages`-block `loop`,
  including the external `before`/`after` reference rewrite to the last
  expanded id.
- `approve` (one of `auto`/`plan`/`dialog`) drives the stage's auto-approval
  effects, same as a `stages`-block `approve` (see
  [Auto-approval (`approve: auto/plan/dialog`)](#auto-approval-approve-auto-plan-dialog)).

An inline `agent`/`loop`/`approve` is a **default**: if a `stages` entry also
names the same stage, the `stages` value wins **per field** — an unset `stages`
field falls back to the inline one. This lets `extend` declare a sensible
default that a `stages` override can selectively tighten. An inline
`agent: null`, `loop: null`, or `approve: null` is a structural type error, not
an absence — omit the key to express absence (symmetric with the per-stage
`agent`/`loop`/`approve`).

### Examples

A STAGES pipeline `propose → review` with a new `warmup` stage that runs after
`propose`, and a new `extra` stage that runs before `review`:

```yaml
extend:
  warmup:
    after: [propose]
    title: Warmup
    prompt: |
      Bootstrap instruction.
  extra:
    before: [review]
    title: Extra
    prompt: |
      Additional pass before review.
```

Compiled effect (stages format): `warmup` depends on `propose`, and `review`
gains `extra` as an additional dependency —
`propose → warmup`, `extra → review`.

The same idea for a PHASES pipeline `[a, b, c]` — insert `x` after `b`:

```yaml
extend:
  x:
    after: [b]
    title: X
    prompt: |
      Stage inserted between b and c.
```

Compiled effect (phases format): the run order becomes `[a, b, x, c]`.

A workflow can consist of `extend` alone — this is a valid, non-empty workflow:

```yaml
extend:
  teardown:
    after: [summary]
    title: Teardown
    prompt: |
      Final cleanup after the summary stage.
```

### Rules and anti-patterns

- `depends_on` is **forbidden** inside an extend entry. Positioning is declared
  via `before` / `after`; the compiler derives the dependency edges.
- At least one of `before` / `after` must be present. An entry with neither is
  rejected with
  `extend entry <NAME> requires at least one of before/after`.
- `before` and `after` must each be a `list[str]` when present. A scalar or a
  list with non-string elements is rejected with `non-list-of-str before in
  workflow.extend.<NAME>` / `non-list-of-str after in workflow.extend.<NAME>`.
- An inline `agent` (when present) must be a string; an inline `loop` (when
  present) must be an int `>= 1`; an inline `approve` (when present) must be one of
  `auto`/`plan`/`dialog` — the same type rules as the `stages` block. A non-string
  `agent` raises `non-str value in workflow.extend.<NAME>.agent`; a non-int or
  `< 1` `loop` raises `non-int value in workflow.extend.<NAME>.loop` /
  `loop must be >= 1 in workflow.extend.<NAME>`; a non-string `approve` raises
  `non-str value in workflow.extend.<NAME>.approve`, and any other string
  raises `approve must be one of: auto, plan, dialog in workflow.extend.<NAME>`. Inline
  `agent`/`loop`/`approve` are default overrides — a `stages` entry for the
  same name wins per field.
- An extend entry that names a `before`/`after` target that does not exist in
  the pipeline (and is not another extend-stage) is a **dangling reference** —
  a structural error raised by Pass 0a0-pre (`unknown stage name in
  workflow.extend.<NAME>.before: <REF>` or the `.after` variant).
- Extend-stages are embedded into the compiled `FlowDocument.stages` only. The
  original `PipelineDocument.body` is never modified — `extend` is a run-time
  layering, like the rest of a workflow-file.

## How the compiler applies a workflow

When `compile_flow` is invoked with a non-None `WorkflowDocument`, the
compiler reconstructs the parsed body in a fixed sequence of passes **before**
building the output stages. The ordering is mandatory: extend-stages are
embedded first, stage names are strictly validated and skipped stages removed,
then per-stage overrides are applied, then loops are expanded, then external
`depends_on` references are rewritten. Embedding first means a per-stage
override (Pass 1) or loop expansion (Pass 2) can also target a stage introduced
by `extend`, by name.

### Pass 0 — Embed extend-stages (in-place)

For each entry in `workflow.extend`, the compiler appends a new stage to the
working step sequence — the verbatim entry body minus `title`, labeled with the
entry's `title` (or, falling back, the entry key). Positioning is then applied
by body format:

- **Stages format** — each `after` name becomes a `depends_on` entry on the new
  stage, and the new stage's name is appended to the `depends_on` of each
  `before` target (existing entries preserved; idempotent). Dangling
  `before`/`after` targets are rejected up front by Pass 0a0-pre (see below),
  so this pass only ever sees resolvable names.
- **Phases format** — the new stage is inserted positionally after the last
  `after` target and/or before the first `before` target, with no explicit
  `depends_on`. Inconsistent `after`/`before` positions fall back to the
  `after` position. Targets that cannot be resolved are caught by Pass 0a0-pre
  before this pass runs.

After this pass the extend-stages live in the working sequence alongside the
originals, so Passes 1–3 below apply to them by the same generic rules.

Before Pass 1, the compiler resolves one **effective override map** keyed by
stage name, computed once and shared by Passes 1 and 2: each `extend` entry
seeds a default override from its inline `agent`/`loop`/`approve`, and each
`stages` entry then overlays per-field, winning whenever its field is not
`None` (the inline value is the fallback). A name that appears only in `stages`
is used verbatim; a name that appears only in `extend` carries just its inline
`agent`/`loop`/`approve`.

### Pass 0.5 — Strict validation of stage names

Before applying any override, the compiler validates every name in `workflow.stages`
against the full name set = original pipeline step names ∪ extend-stage names. A name
absent from both is a **structural error** (`unknown stage name in workflow.stages:
<name>`). A stage that exists — even if also marked
`skip: true` — is NOT flagged (the check runs on the full set before removal). Strictness
is symmetric: dangling `extend.<name>.before/.after` refs are likewise rejected by
Pass 0a0-pre (below).

### Pass 0a0-pre — Strict validation of extend refs

Before the embed pass, the compiler validates every `before`/`after` ref in
`workflow.extend` against the union of original pipeline step names and
extend-stage names. Any ref absent from that set raises a **structural error**
(`unknown stage name in workflow.extend.<NAME>.before: <ref>` or the `.after`
variant) — a dangling `before`/`after` ref does not pass through verbatim.
The check runs before embed and before skip removal, so a ref to a stage that
also carries `skip: true` is NOT flagged here (it still exists in the original
body at this point and is removed later at Pass 0.6). Existence only — cycles,
self-references, and duplicate refs remain afm's responsibility.

### Pass 0.6 — Skip removal + transparent reconnection

Stages with `skip: true` are removed from the working body. Dependents' `depends_on` are
reconnected to the skipped stage's predecessors (transitively for chains; positional
collapse for phases). `skip` wins over other overrides (removal precedes Pass 1). If the
reconstructed body is empty, the compiler raises `empty body`.

### Pass 1 — Per-stage overrides (in-place)

For each `(stage_name, effective_stage)` pair in the effective override map:

1. Find the step in the body whose `name` or id equals `stage_name`.
2. If not found — silent (only an intentionally skipped stage removed at Pass 0.6
   reaches here; unknown names already errored at Pass 0.5).
3. If found:
   - When `effective_stage.agent` is not None — set the stage's `command`
     field to the composed wrapper path
     `/home/goga/bin/<agent>-as-claude.sh`. This applies the inline-extend
     `agent` too, via the effective map.
   - When `effective_stage.prompt` is not None — attach the prompt as
     per-stage context for the agent running the stage. The prompt has
     lower precedence than the stage's own `prompt` field and is treated
     as ambient guidance, not as a direct command. See
     [Workflow `prompt` — context, not command](#workflow-prompt-context-not-command).
   - When `effective_stage.skills` is not None — merge the workflow skills
     with the stage's existing `skills` (pipeline-first, deduplicated). See
     [Skills merge](#skills-merge).
   - The effective `approve` directive is threaded into the step body under
     an internal sentinel key (one of `auto`/`plan`/`dialog`, or `None`); it is
     read and consumed during canonical field assembly (Pass 4) to drive the two
     approve effects (each on its own directive subset) and never reaches the
     output. See
     [Auto-approval (`approve: auto/plan/dialog`)](#auto-approval-approve-auto-plan-dialog).
   - The effective `manual` instruction is applied to the WORKING copy of the
     body (the parsed `PipelineDocument` is never mutated): `true` sets the
     working body's trigger to `manual` over any authored value (idempotent on
     an already-manual stage); `false` rewrites an effective `trigger: manual`
     back to `on_success` or raises `manual: false on non-manual stage <NAME>`
     when the stage is not manual; absent is a no-op. The resulting trigger is
     translated during canonical field assembly (Pass 4) into the afm
     `auto_run: false` key. See
     [Manual launch (`manual` and `trigger`)](#manual-launch-manual-and-trigger).

### Skills merge

A `stages`-block `skills` override is **merged** with the pipeline-file
`skills` of the matched stage, not replaced:

- Pipeline-file skills come first (their relative order is preserved), then
  the workflow skills, with any value already seen dropped (deduplication is
  by value, first-occurrence order).
- A stage with no pipeline `skills` gets the workflow list as-is; a workflow
  override of `[]` (or a stage with neither side carrying skills) leaves the
  `skills` key absent rather than emitting an empty list.
- An `extend` entry's own body `skills` are the new stage's pipeline-side
  skills — when a `stages` entry also names that stage, the merge combines the
  extend-body skills with the `stages` override. With no matching `stages`
  entry the extend-body skills pass through verbatim.

### Pass 2 — Loop expansion

For each step, determine `loop_count` from the effective override's `loop`
for that stage name when set, else `1`. The effective `loop` folds an
inline-extend `loop` together with a `stages`-block `loop` (the `stages`
value wins per-field when both are present).

When `loop_count >= 2`, the compiler appends N copies with ids
`<name>-1`, ..., `<name>-N`, each subsequent copy depending on the previous
one. The compiler records an `expanded_ids` map from base-name to the list
of ids produced.

Expansion interacts with body format:

- **Phases format** — the expanded copies chain naturally via list position.
  The first copy inherits the original position; subsequent copies depend
  on their predecessor; the next **original** step depends on the last
  expanded copy.
- **Stages format** — `depends_on` is otherwise passed through as-is. See
  Pass 3 for the external-reference rewrite.

### Pass 3 — External depends_on rewrite (stages format only)

For each stage in **stages** format with a non-empty `depends_on`, the
compiler replaces any reference to a base name whose `loop_count >= 2`
with `expanded_ids[ref][-1]` — i.e. the **last** expanded id.

For example, if stage `review` has `loop: 2` and another stage declares
`depends_on: [review]`, the compiled output carries
`depends_on: [review-2]`.

### Pass 4 — Agent-mode resolution

After overrides and expansion, the compiler resolves the agent mode for
every stage the same way the no-workflow path does: a stage without an
authored non-empty `roles` value runs in autonomous mode, and a stage
with an authored non-empty `roles` value runs in coordinated mode. See
[stage modes](pipeline-file.md#roles) for the functional description
of each mode.

A workflow-applied `command` override (from a per-stage `agent` field) and
the stage's own agent-mode resolution are independent — the override
selects which agent binary runs the stage, while the `roles` field
selects how the work is organized inside it.

## Invocation modes

A pipeline run picks up a workflow in one of three mutually exclusive modes.
The launcher communicates the chosen mode to the container through env-file
entries.

| Mode              | Invocation                                  | Env-file entry                         | Behavior                                                                  |
|-------------------|---------------------------------------------|----------------------------------------|---------------------------------------------------------------------------|
| Auto-match        | `goga pipeline deploy`                      | *(neither)*                            | If `<cwd>/.goga/workflows/deploy.yml` exists, it is applied silently.     |
| Explicit override | `goga pipeline deploy --workflow custom`   | `GOGA_WORKFLOW_NAME=custom`            | Apply `<cwd>/.goga/workflows/custom.yml`. Host validates existence first. |
| Disable           | `goga pipeline deploy --no-workflow`        | `GOGA_WORKFLOW_DISABLED=1`             | Disable workflow application entirely.                                    |

In auto-match mode no host-side validation runs — the workflow-file is
opened and parsed inside the container, and a missing file is silently
treated as "no workflow". In explicit-override mode the host validates the
file exists before launch (exit 1 if missing).

`--workflow` and `--no-workflow` are mutually exclusive — passing both
exits with code 1 before launch.

The card form honors the same three modes: `goga pipeline deploy --info
[-w <wf> | --no-workflow]` resolves the workflow through the identical
rule set, with the same host-side validation. The decision travels as
`docker run` argv (not the env-file), and the stage list the card prints
is exactly the composition a run with the same flags executes. See
[pipeline](../cli/pipeline.md).

### Log line

When a workflow will actually be applied (explicit `--workflow`, or an
auto-match file that exists), the launcher prints a single line to stdout:

```
Pipeline running with workflow "<name>"
```

When no workflow applies, the launcher prints no workflow line.

## Example

A workflow that layers a Russian-language answer directive and two
per-stage prompts on top of a pipeline:

```yaml
prompt: |
  Answer in Russian language

stages:
  propose:
    prompt: |
      Task formalization process.

      Requirements:
      - When setting the task, it is necessary to develop stack technologies more carefully.
      - Carefully examine all the link connections between cells

      Constraints:
      - Don't write code examples in the task
      - Don't build architecture in the task
  brainstorm:
    prompt: |
      Architectural design process.

      Requirements:
      - Annotations describe the high-level order of actions
      - Every usage file is connected through Imports and referenced in annotations
      - Usage files are self-contained
      - Footer Description describes the responsibility zone

      Constraints:
      - Annotations must not reference previous functionality
      - Annotations do not contain implementation details
      - Annotations must not use "X from Imports" phrasing
      - Footer Description does not contain details
```

A workflow that expands a `propose-review` stage into two passes and pins
its agent to `claude`:

```yaml
stages:
  propose-review:
    loop: 2
    agent: claude
```

Compiled effect: the original `propose-review` stage is replaced by
`propose-review-1` and `propose-review-2`, each depending on the previous
one, both running with the `claude` wrapper.

A workflow that runs different stages on different CLI agents — authoring
on `codex`, review on `claude` — without touching the pipeline-file:

```yaml
stages:
  propose:
    agent: codex
  brainstorm:
    agent: codex
  architecture-review:
    agent: claude
  plan-review:
    agent: claude
```

Here `codex` does the heavy authoring (propose, brainstorm) and `claude`
runs the reviews. The underlying pipeline-file stays unchanged — every
project can pin its own agent-per-stage matrix in its workflow-file.

A workflow that adds stages which are not in the pipeline-file at all — a
`warmup` that runs after `propose`, and an `extra` review that runs before
`plan-review`:

```yaml
extend:
  warmup:
    after: [propose]
    title: Warmup
    prompt: |
      Boot up tooling context before the pipeline runs.

  extra:
    before: [plan-review]
    title: Extra review
    prompt: |
      An additional review pass before the plan is finalized.
```

Compiled effect: two stages absent from the pipeline-file now appear in the
run. In stages format `warmup` depends on `propose`, and `plan-review` gains
`extra` as an additional dependency; in phases format `warmup` is inserted
after `propose` and `extra` before `plan-review`. The pipeline-file itself is
untouched — `extend` layers new stages on top at run time.

## Errors

| Condition                                                       | Exception                                                                   |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------|
| File is not valid YAML                                          | `invalid YAML in workflow-file`                                             |
| Root is not a mapping                                           | `workflow must be a mapping`                                                |
| `prompt` present but not a string                               | `non-str value in workflow.prompt`                                          |
| `stages` present but not a mapping                              | `non-mapping stages block in workflow`                                      |
| Unknown top-level key                                           | `unknown key in workflow: <KEY>; valid keys: prompt, stages, extend`        |
| Stage value is not a mapping                                    | `non-mapping stage <NAME> in workflow.stages`                               |
| `extend` present but not a mapping                              | `non-mapping extend block in workflow`                                      |
| Extend entry value is not a mapping                             | `non-mapping extend entry <NAME> in workflow.extend`                        |
| `depends_on` present in an extend entry                         | `depends_on is forbidden in workflow.extend.<NAME>`                         |
| `before` in an extend entry not a `list[str]`                   | `non-list-of-str before in workflow.extend.<NAME>`                          |
| `after` in an extend entry not a `list[str]`                    | `non-list-of-str after in workflow.extend.<NAME>`                           |
| Inline `agent` in an extend entry not a string                  | `non-str value in workflow.extend.<NAME>.agent`                             |
| Inline `loop` in an extend entry not an int                     | `non-int value in workflow.extend.<NAME>.loop`                              |
| Inline `loop` in an extend entry is an int but `< 1`            | `loop must be >= 1 in workflow.extend.<NAME>`                               |
| Inline `approve` in an extend entry not a string                | `non-str value in workflow.extend.<NAME>.approve`                           |
| Inline `approve` in an extend entry not one of `auto`/`plan`/`dialog` | `approve must be one of: auto, plan, dialog in workflow.extend.<NAME>` |
| Extend entry has neither `before` nor `after`                   | `extend entry <NAME> requires at least one of before/after`                 |
| Unknown per-stage key                                           | `unknown key in workflow.stages.<NAME>: <KEY>; valid keys: agent, prompt, loop, skills, skip, approve, manual, notes` |
| `agent` present but not a string                                | `non-str value in workflow.stages.<NAME>.agent`                             |
| `prompt` present but not a string                               | `non-str value in workflow.stages.<NAME>.prompt`                            |
| `loop` present but not an int                                   | `non-int value in workflow.stages.<NAME>.loop`                              |
| `loop` is an int but `< 1`                                      | `loop must be >= 1 in workflow.stages.<NAME>`                               |
| `skills` present but not a `list[str]`                          | `non-list-of-str skills in workflow.stages.<NAME>`                          |
| `skip` is not a bool                                            | `non-bool value in workflow.stages.<NAME>.skip`                             |
| `manual` is not a bool                                          | `non-bool value in workflow.stages.<NAME>.manual`                           |
| `approve` present but not a string                              | `non-str value in workflow.stages.<NAME>.approve`                           |
| `approve` present but not one of `auto`/`plan`/`dialog`         | `approve must be one of: auto, plan, dialog in workflow.stages.<NAME>`      |
| `skip` present under `extend`                                   | `skip is forbidden in workflow.extend.<NAME>`                               |
| `manual` present under `extend`                                 | `manual is forbidden in workflow.extend.<NAME>`                             |
| `notes` present under `extend`                                  | `notes is forbidden in workflow.extend.<NAME>`                              |
| `notes` present but not a mapping (including `null`)            | `non-mapping notes in workflow.stages.<NAME>`                               |
| `notes` value not a string                                      | `non-str value in workflow.stages.<NAME>.notes.<KEY>`                       |
| `manual: false` on a stage that is not manual                   | `manual: false on non-manual stage <NAME>`                                  |
| Unknown stage name in `workflow.stages` (absent from pipeline and extend) | `unknown stage name in workflow.stages: <NAME>`                  |
| Unknown ref in `workflow.extend.<NAME>.before`                 | `unknown stage name in workflow.extend.<NAME>.before: <REF>`               |
| Unknown ref in `workflow.extend.<NAME>.after`                  | `unknown stage name in workflow.extend.<NAME>.after: <REF>`                |
| All stages skipped (empty reconstructed body)                   | `empty body`                                                                |
| None of `prompt`, `stages`, `extend` entries are present        | `empty workflow — provide at least prompt, one stage, or one extend entry`  |

## See also

- [Pipeline File](pipeline-file.md) — the base document a workflow layers
  on top of.
- [`goga pipeline` CLI reference](../cli/pipeline.md) — invocation flags
  for `--workflow` / `--no-workflow` and exit codes.
