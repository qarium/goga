# Workflows

A **workflow-file** is an optional YAML document that layers project-specific
behavior on top of a compiled pipeline at run time. A workflow can inject a
top-level prompt, override the agent or prompt of specific stages, attach
**per-stage environment variables** via `env`, expand
a stage into N chained copies via `loop`, **skip (delete) a stage**,
declare per-stage **auto-approval** via `approve`, force or cancel a stage's
**manual launch mode** via `manual`, attach **note buttons** to a stage via
`notes`, **declaratively add new stages** to the pipeline via `extend`,
configure **project-memory participation** via the top-level `memory` block
and the per-stage `reflect` / `memory` instructions (see
[Project memory (`memory`, `reflect`)](#project-memory-memory-reflect)),
author **collaboration with helper agents** via the top-level `assistants`
catalog, the `delegation` block, and the per-stage `assistants` instruction
(see [Collaboration (`assistants`, `delegation`)](#collaboration-assistants-delegation)),
tune **repeating run cycles** via the top-level `repeat` block
(see [Run cycles (`repeat`)](#run-cycles-repeat)),
and adapt the whole file per contributor through **profile-driven rendering**
(see [Profiles](#profiles)) plus a `build:` block that configures nested
`goga build` runs.

Stage names in `workflow.stages` are matched strictly: a name that does not
match any pipeline step or extend-stage is a compile error. Workflows that
reference names absent from the target pipeline must be split or pruned.

Workflow-files live at:

```text
<cwd>/.goga/workflows/<name>.yml
```

They are **project-only** — there is no user-level workflow directory. The
name must be a bare filename resolved inside `.goga/workflows/`; path
traversal via `..` or an absolute prefix is rejected.

## Document shape

A workflow-file is a YAML mapping with up to nine top-level keys (the whole
file is first rendered as a Jinja2 template with the active profile's
content as context — see [Profiles](#profiles)):

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
    notes:                    # optional note buttons attached to the stage
      fix: Fix the failure and continue
    reflect:                  # optional memory-reflection instruction (reflect method only)
      file: shared.md
    memory: true              # optional memory participation (alignment method only; never together with reflect)
    assistants:               # optional stage assistant attachments (a name-keyed map)
      reviewer:
        when: finish

assistants:                   # optional catalog of run-level assistants (a name-keyed map)
  reviewer:
    prompt: Review the stage changes.

delegation:                   # optional delegation-bounds block
  depth: 3
  max_tasks: 50

repeat:                       # optional run-cycle tuning block (repeatable pipelines only)
  max_cycles: 3

memory:                       # optional workflow-memory configuration block
  method: reflect             # reflect | alignment (the instruction vocabulary selector)
  max_rules: 25               # optional rule cap (>= 1)

extend:
  <new-stage-name>:
    after: [specify]          # position the new stage relative to existing ones
    title: Warmup             # optional display label; defaults to the entry key
    prompt: |                 # any other stage field passes through verbatim
      Bootstrap instruction for the new stage.
```

| Key      | Type   | Required | Description                                                |
|----------|--------|----------|------------------------------------------------------------|
| `prompt` | string | no*      | Top-level prompt emitted as the first key of the output.   |
| `stages` | map   | no*      | Per-stage override instructions keyed by stage name.       |
| `extend` | map   | no*      | New stages to add to the pipeline, keyed by new stage name. |
| `memory` | map   | no*      | Workflow-memory configuration (see [Project memory](#project-memory-memory-reflect)). |
| `profile` | string | no    | Default profile name activated when no `--profile`/`GOGA_PROFILE` channel provided one. Must be a literal (a templated default does not participate in activation). A `profile:`-only workflow is invalid — activation is not content. |
| `build` | map   | no*      | Configuration layered onto the `build` section for nested `goga build` runs (see the [build documentation](../../build/configuration.md)). A `build:`-only workflow is valid. |
| `assistants` | map | no*   | Catalog of run-level assistants keyed by assistant name (see [Collaboration](#collaboration-assistants-delegation)). An `assistants:`-only workflow is valid. |
| `delegation` | map | no*   | Delegation bounds — `depth` and `max_tasks` (see [Collaboration](#collaboration-assistants-delegation)). A `delegation:`-only workflow is valid. |
| `repeat` | map | no*   | Run-cycle tuning for a repeatable pipeline — `max_cycles` / `keep_runs` (see [Run cycles](#run-cycles-repeat)). A `repeat:`-only workflow is valid. |

\* At least one of `prompt`, a non-empty `stages` block, a non-empty
`extend` block, a `memory` block, a `build` block, an `assistants`
block, a `delegation` block, or a `repeat` block must be present; an
empty workflow is rejected with a structural error. `profile` does not
count — a `profile:`-only workflow is invalid.

Unknown top-level keys are rejected with
`unknown key in workflow: <KEY>; valid keys: prompt, stages, extend, memory, profile, build, assistants, delegation, repeat`.

## Stage entries

Each entry under `stages` is keyed by stage name and accepts up to twelve
fields:

| Field   | Type     | Default | Description                                                                                              |
|---------|----------|---------|----------------------------------------------------------------------------------------------------------|
| `agent` | string   | —       | CLI agent name (e.g. `codex`, `claude`, `cursor`, `opencode`, `qwen`). Selects which agent runs this stage. See [Workflow `agent` — choosing the CLI agent](#workflow-agent-choosing-the-cli-agent). |
| `env`   | map of str→str | — | Per-stage environment variables, exported verbatim by a generated sh closure wrapping the stage's agent (or the global pipeline agent when the entry sets no `agent`). Every `loop`-expanded copy gets its own closure carrying the same values; keys must be legal environment variable names and values are shell-quoted in the closure. An empty map equals absence. Allowed ONLY in `stages` — it is a structural error under `extend` (`env is forbidden in workflow.extend.<NAME>`). |
| `prompt`| string   | —       | Per-stage context prompt. Lower precedence than the stage's own `prompt` — closer to a section description than to a direct instruction. See [Workflow `prompt` — context, not command](#workflow-prompt-context-not-command). |
| `loop`  | int      | —       | Positive iteration count (`>= 1`). When `>= 2`, the stage is expanded into N chained copies.           |
| `skills`| string list | —   | Skill names merged with the pipeline stage's own `skills` (pipeline-first, deduplicated by value). See [Skills merge](#skills-merge). |
| `skip`  | bool     | —       | When `true`, the compiler DELETES this stage from the compiled pipeline (the stage is absent from the flow-file entirely). Dependents of the skipped stage are transparently reconnected to its predecessors (no dangling references). `false` (or an absent key) leaves the stage in place. `skip` is allowed ONLY in the `stages` block — it is a structural error under `extend`. `skip` wins over `agent`/`prompt`/`loop`/`skills` overrides on the same entry. |
| `approve` | string | —     | Auto-approval directive. Accepted values are `auto`, `plan`, and `dialog`; any other value (or a non-string) is a structural error. Each value drives a subset of two INDEPENDENT effects the compiler applies to the stage body (see [Auto-approval (`approve: auto/plan/dialog`)](#auto-approval-approve-auto-plan-dialog)): (1) **communication effect** — if the body has `communication: true`, the stage's `interactive` output is SUPPRESSED (omitted, not `false`); (2) **roles effect** — if the body's raw `roles` contain `planner`, the stage emits `auto_approve: true`. `auto` drives BOTH effects; `plan` drives only the communication effect; `dialog` drives only the roles effect. Allowed in both `stages` and `extend` (inline default override; a `stages` entry wins per-field). |
| `manual` | bool | —     | Manual-launch instruction, `stages` block only. `true` forces the manual launch mode for the stage, overriding any authored `trigger` in its body. `false` cancels a manual state coming from either body source (a pipeline-file `trigger: manual` or an extend body `trigger: manual`) and is a structural error (`manual: false on non-manual stage <NAME>`) when the stage is not manual. An absent key means no instruction — the stage's own `trigger` decides. The three states (`true`/`false`/absent) are distinct; a non-bool value (including `null`) is a structural error. Allowed ONLY in `stages` — it is a structural error under `extend` (a new stage's launch mode is authored in its body via `trigger`). `skip` wins over `manual`: a skipped stage is removed before the manual instruction is applied. See [Manual launch (`manual` and `trigger`)](#manual-launch-manual-and-trigger). |
| `notes` | map of str→str | — | Note buttons — a map of "note name → prompt text" attached verbatim to the stage. Single-line texts serialize as plain scalars, multi-line texts as block literals. An empty map equals absence (no buttons emitted). Allowed ONLY in `stages` — it is a structural error under `extend` (an extend-stage receives its buttons through the `stages` block by name). Every `loop`-expanded copy carries the same buttons; `skip` wins over `notes`. How the buttons surface during the run is owned by the pipeline runtime — the compiler only assembles them. See [Note buttons (`notes`)](#note-buttons-notes). |
| `reflect` | map | — | Memory-reflection instruction (reflect method): `{file: <path>, mode: r\|w\|rw}` naming which memory file the stage reflects into. `file` is required and must be a relative, non-escaping path shape; `mode` defaults to `rw`. Allowed ONLY in `stages` — it is a structural error under `extend`. See [Project memory (`memory`, `reflect`)](#project-memory-memory-reflect). |
| `memory` | bool | — | Memory-participation instruction (alignment method): `true` marks the stage as participating in project memory. An explicit `false` equals absence. Allowed ONLY in `stages` — it is a structural error under `extend`. See [Project memory (`memory`, `reflect`)](#project-memory-memory-reflect). |
| `assistants` | map | — | Stage assistant attachments keyed by assistant name — each entry a reference (`gate`/`when`, with `when` required) or a full inline declaration; an empty map equals absence. Allowed ONLY in `stages` — it is a structural error under `extend`. See [Collaboration (`assistants`, `delegation`)](#collaboration-assistants-delegation). |

Rules:

- Only `agent`, `env`, `prompt`, `loop`, `skills`, `skip`, `approve`, `manual`, `notes`, `reflect`, `memory`, `assistants` are valid. An
  unknown key is rejected with `unknown key in workflow.stages.<NAME>: <KEY>; valid keys:
  agent, env, prompt, loop, skills, skip, approve, manual, notes, reflect, memory, assistants`.
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
- `reflect` (when present) must be a mapping with a key set within
  `{file, mode}`; `file` is required and must be a valid path shape, `mode`
  one of `r`/`w`/`rw`. `reflect` is allowed only in the `stages` block —
  it is a structural error under `extend` (see
  [Project memory (`memory`, `reflect`)](#project-memory-memory-reflect)).
- `memory` (when present) must be a bool; an explicit `false` equals absence.
  `memory` is allowed only in the `stages` block — it is a structural error
  under `extend` (see
  [Project memory (`memory`, `reflect`)](#project-memory-memory-reflect)).
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
documented in [Agents](../../configuration/agents.md) under
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
  specify:
    prompt: |
      This stage formalizes the user's request into a task document.
      It runs early in the lifecycle and shapes the rest of the pipeline.
```

Example — context with enforceable requirements (the labeled block is
honored as an instruction):

```yaml
stages:
  specify:
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

A `stages` (or `extend`) entry may set an `approve` directive to drive the
stage's auto-approval behavior at compile time. The directive is one of
three values — `auto`, `plan`, or `dialog` — chosen from a closed set, not a
free-form flag, so any other string (or a non-string) is a structural error.

The compiler applies two **independent** effects to the stage body, and each
directive drives a subset of them:

1. **User-input suppression** (the **communication effect**) — if the stage
   body has `communication: true`, the stage's user-input pause is
   SUPPRESSED entirely. This makes an otherwise user-prompting stage run
   non-interactively. `communication: false` (or no `communication` key) is
   unaffected — suppression fires only when `communication is True`.
2. **Auto-approval** (the **roles effect**) — if the stage body's raw
   `roles` list contains `planner`, the stage's agent actions are
   auto-approved. The match is against the authored role alias `planner`.

| `approve`   | communication effect (suppress user input) | roles effect (auto-approve actions) |
|-------------|:----------------------------------------------:|:----------------------------------:|
| *(absent)*  | —                                              | —                                  |
| `auto`      | ✓                                              | ✓                                  |
| `plan`      | ✓                                              | —                                  |
| `dialog`    | —                                              | ✓                                  |

So `auto` is the full directive (both effects, as before); `plan` keeps the
communication effect but turns the roles effect OFF (a `planner` stage does
NOT auto-approve); `dialog` keeps the roles effect but turns the
communication effect OFF (`communication: true` still pauses for input).
The two effects are independent: each fires on its own trigger AND its
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
  forces the manual launch mode (see
  [Pipeline files](pipeline-file.md)): the stage pauses when reached and runs
  only when launched manually. An authoring `auto_run` key in a body is a
  structural error — the launch mode is assembled by the compiler, never
  authored.
- The **workflow `stages` block** carries `manual` — a force/cancel instruction
  applied ON TOP of the body, without editing the pipeline-file:

| `manual`     | Effect on the stage                                            |
|--------------|----------------------------------------------------------------|
| *(absent)*   | No instruction — the body's own `trigger` decides.             |
| `true`       | Forces manual launch, overriding any authored `trigger`. Idempotent on a stage that is already manual. |
| `false`      | Cancels manual: an effective `trigger: manual` (from the pipeline-file body or an `extend` body) is rewritten to `on_success`, so the stage launches automatically. A structural error when the stage is NOT manual (`manual: false on non-manual stage <NAME>`) — cancelling a state that does not exist is an authoring mistake, not a no-op. |

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
map of "note name → prompt text" that the compiler attaches verbatim to
the stage as its note buttons.

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
  `notes` changes nothing else: a workflow whose entries are all empty
  compiles byte-identically to compiling without a workflow, while any
  other instruction (`prompt`, `agent`, `loop`, `skip`, ...) changes the
  output as usual — notes or not.
- Every `loop`-expanded copy carries the same buttons, and `skip` wins over
  `notes`: a skipped stage is removed before the buttons are resolved, so
  its notes never leak into a survivor.
- How the buttons surface during the run is owned by the pipeline runtime —
  the compiler only assembles them.

### Project memory (`memory`, `reflect`)

A workflow can wire its stages into the runner's **project memory**: a
top-level `memory` block selects the method and the block-level settings,
and the per-stage instructions mark which stages participate.

```yaml
memory:
  method: reflect          # reflect (default) | alignment
  max_rules: 40            # rule cap, >= 1, default 25
  commit: false            # whether memory changes are committed

stages:
  prototype:
    reflect:               # reflect method: which file the stage reflects into
      file: shared.md
      mode: rw             # r | w | rw, default rw
  accept:
    reflect:
      file: shared.md
```

Under `method: alignment` the participating stages carry `memory: true` instead — see the key table below.

The top-level block accepts these keys:

| Key         | Type   | Default    | Description                                                                    |
|-------------|--------|------------|--------------------------------------------------------------------------------|
| `method`    | string | `reflect`  | The instruction vocabulary: `reflect` pairs with the per-stage `reflect` instruction, `alignment` with the per-stage `memory` instruction. Never part of any output. |
| `path`      | string | —          | Suffix inside the fixed memory root `.goga/memory`. Must be a relative, non-escaping path shape. |
| `max_rules` | int    | `25`      | The maximum number of memory rules (`>= 1`).                                    |
| `commit`    | bool   | `false`   | Whether memory changes are committed.                                           |
| `mode`      | string | `rw` under `alignment` | The project-memory access mode (`r`/`w`/`rw`). Authored ONLY under `method: alignment` — an authored `mode` together with `method: reflect` is a structural error. |

Behavior rules:

- **The method selects the instruction vocabulary.** Under `reflect` (the
  default when no block is authored) a stage participates by carrying a
  `reflect: {file, mode?}` instruction; under `alignment` it participates by
  carrying `memory: true`. The two vocabularies never mix: a `reflect`
  instruction under `alignment`, or a `memory: true` instruction under
  `reflect` (including with no block at all), is a structural error.
- **The block is emitted iff at least one stage participates.** A memory
  configuration without participation is a silent no-op — no block, no stage
  keys, not even an opting-out stage key. A workflow consisting of the
  `memory` block alone is still valid (it counts as content).
- Participation is counted over the **working body** — after skip removal
  and loop expansion, embedded extend-stages included. A skipped stage's
  instructions die with it: skipping the only participating stage disables
  the block entirely. Every `loop`-expanded copy carries the same memory
  keys as its original.
- Project memory lives under the fixed root `.goga/memory` (plus the
  authored `path` suffix when one is set). How the memory settings and the
  per-stage participation are encoded into the compiled pipeline is an
  internal contract of the compiler; this documentation intentionally does
  not pin the compiled form.
- Both instructions are allowed ONLY in the `stages` block — under `extend`
  they are structural errors. A new stage participates through a
  `stages`-block entry authored under its name. Authoring a `reflect` or
  `memory_use` key in any stage body (a pipeline-file stage or an extend
  body) is likewise a structural error — the memory stage keys come from
  the workflow instructions alone.
- The memory mechanism is executed by the pipeline runtime inside the
  container — goga authors and compiles the instructions. If your image
  predates the mechanism, refresh it with `--update`.

### Collaboration (`assistants`, `delegation`)

A workflow can attach **helper agents** to its stages and add **run-level
team agents** through the runner's collaboration mechanism: a top-level
`assistants` catalog declares the named assistants, a top-level
`delegation` block bounds helper delegation, and the per-stage
`assistants` instruction attaches assistants to stages.

Workflow collaboration requires afm 2.0+ (the shipped image carries it); an
older image predating the mechanism must be refreshed with `--update`.

```yaml
assistants:                     # the catalog — run-level assistants (a name-keyed map)
  reviewer:
    agent: claude               # optional; defaults to the global pipeline agent
    delegate: true              # optional; may create child tasks
    skills: [code-audit]        # the assistant's own skills
    prompt: |
      Review the stage changes and report concrete findings.

delegation:                     # optional delegation bounds
  depth: 3                      # max delegation depth (>= 0); 0 forbids helpers
  max_tasks: 50                 # whole-run helper task budget (>= 1)

stages:
  build:
    assistants:
      reviewer:                 # 1) reference — the declaration comes from the catalog
        when: finish
  accept:
    assistants:
      reviewer:                 # 2) reference with the gate override
        gate: true
        when: finish
      security:                 # 3) full inline declaration
        prompt: Audit the diff.
        when: checkpoints
```

The top-level `assistants:` catalog is a name-keyed map: each key IS the
assistant name — it must match `[A-Za-z0-9._-]`, `assistant` is reserved
(its dashboard handle is), and it is unique across the catalog and every
inline declaration. Each entry value accepts these keys:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `prompt` | string | — | The assistant's instruction. At least one of `prompt` or `skills` is required. |
| `skills` | list of strings | — | The assistant's own skills. At least one of `prompt` or `skills` is required. |
| `agent` | string | global agent | A CLI agent name, resolved implicitly at delivery — no wrapper path is authored. |
| `delegate` | bool | `false` | Whether the assistant may create child tasks. |
| `env` | map of str→str | — | The assistant's environment variables, delivered through a generated closure that wraps the assistant's launch command (the same mechanism as per-stage `env`). An empty map equals absence. |

`name`, `gate`, and `when` never appear in a catalog entry value — the map
key is the name itself, and `gate`/`when` are attachment parameters
(authoring either in the catalog is a structural error).

The top-level `delegation:` block accepts:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `depth` | int `>= 0` | not authored | Maximum delegation depth; `0` forbids helper creation entirely. Travels into the compiled flow as the collaboration depth. Verified engine behavior (afm v2.0.9): at `depth: 0` the engine also declines run-level team-agent creation (`delegation_depth_exceeded` warnings) — team agents start at `depth >= 1`. |
| `max_tasks` | int `>= 1` | `50` | Whole-run helper task budget — every helper, run agent, and child task counts against it. Written into the engine configuration only when the block is authored. |

Both keys are optional; an empty block is valid and materializes
`max_tasks: 50`. A workflow consisting of the `delegation:` block alone —
or of the `assistants:` catalog alone — is valid.

The per-stage `assistants` instruction is a name-keyed map — each key names
the assistant (identifying the catalog entry for a reference, or the
declaration itself for an inline entry), and each value carries the
attachment parameters. Two entry forms:

1. **A reference** — a value carrying only `gate`/`when`: the agent,
   prompt, skills, delegate permission, and env come from the catalog
   entry; only `gate` and `when` are the attachment's own.
2. **A full inline declaration** — a value carrying any further key
   (`prompt`, `skills`, `agent`, `delegate`, `env`, plus `gate`/`when`).
   Independent of the catalog; at least one of `prompt` or `skills` must
   be present. Note: `skills` authored here has no effect — the engine
   accepts skills only on run-level team entries, and only catalog
   entries become team members (see the behavior rules below).

| Attachment key | Type | Default | Description |
|----------------|------|---------|-------------|
| `when` | `start` \| `checkpoints` \| `finish` | **required** | When the assistant engages. |
| `gate` | bool | `false` | `true` — the assistant's verdict must pass (or be waived by a human) before the stage may finish; `false` is advisory. |

`when` is required on every attachment — the entry key already names the
assistant, so its engagement timing is authored explicitly. An unknown
attachment key is a structural error (`valid keys: prompt, skills, agent,
delegate, env, gate, when`).

Behavior rules:

- **Names form one namespace.** The catalog and every inline declaration
  share a single namespace across the workflow-file; a repeated
  declaration name is a structural error (`duplicate assistant name:
  <NAME>`), and the name `assistant` is rejected (`assistant name is
  reserved`).
- **References resolve at compile time.** A reference naming no catalog
  entry and no inline declaration of the effective document is a compile
  error (`unknown assistant reference in workflow.stages.<NAME>`). The
  same assistant attached twice to one stage is a compile error —
  reachable only through a programmatic (tool) contribution, since an
  authored map cannot repeat a key — as is an
  attachment on a stage whose body carries `script` or whose agents value
  is exactly `["planning"]` — helpers attach to execution stages only.
- **Attachments live only under `stages.<name>`.** Authoring `assistants`
  inside an `extend`-entry is a structural error — the attachments of a
  new stage are authored in the `stages` block under its name. Authoring
  an `assistants` key in a stage *body* is likewise a structural error.
- **Defaults are materialized, never inherited.** `gate`,
  `delegate`, and `max_tasks` always carry their materialized values into
  the compiled output; `when` has no default — it is authored on every
  attachment, and the compiled engagement value is always written
  explicitly. The engine's own defaults (a `one_shot` trigger, a
  20-task budget) are never relied upon.
- **Skills deliver through the catalog.** The engine accepts `skills` only
  on run-level team entries, and the team is built from the `assistants:`
  catalog alone — so `skills` authored on a catalog entry reaches the
  engine, while `skills` authored on a full inline declaration has no
  channel: the compiler logs a warning naming the stage and the assistant
  and drops the value. Declare the assistant in the catalog (and attach it
  by reference) to deliver its skills.
- **Every `loop`-expanded copy carries its stage's attachments; a skipped
  stage attaches nothing.**
- **No profile concept is user-visible.** The engine requires each helper
  to reference a profile; goga generates and maintains that plumbing
  (`goga-<name>` bindings and their launch commands) from the compiled
  flow on every launch. There is nothing to author or manage, and a
  user-authored profile with the same `goga-`-prefixed id deliberately
  replaces goga's plumbing.
- **Authored configuration applies on every launch.** The engine
  configuration is rewritten per run and the helper plumbing (including
  env closures) is regenerated with it — the workflow-file is the durable
  source, so the same authoring takes effect on consecutive runs.
- If the environment disables collaboration, declared helpers are skipped
  with engine warnings and the run proceeds.

## Run cycles (`repeat`)

A workflow can put a **repeatable** pipeline into a running cycle: the
pipeline-file header declares the capability (`repeatable: true` — see
[Pipeline File — Header](pipeline-file.md#header)), and the workflow-file
authors the tuning through the top-level `repeat` block. The engine (afm
2.0.9+; the shipped image carries it) then runs the complete stage
sequence in cycles until a stop condition.

```yaml
repeat:
  max_cycles: 3      # at most 3 complete passes
  keep_runs: 5       # keep the 5 most recent cycle run-directories
```

The block carries the engine's vocabulary verbatim — goga materializes no
defaults, and both keys are optional:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_cycles` | int `>= 0` | — | At most N complete passes. `0` is an authored value carried verbatim; its cycle meaning belongs to the engine. |
| `keep_runs` | int `>= 0` | — | How many recent cycle run-directories to keep (the engine default is `2`). |

Rules:

- **The block belongs to a repeatable pipeline.** A `repeat:` block in the
  workflow of a pipeline whose header does not declare `repeatable: true`
  is a compile-time structural error (`workflow repeat block requires a
  repeatable pipeline; author repeatable: true in the pipeline header`).
- **A repeatable pipeline always compiles a `repeat` key.** Authored keys
  ride verbatim (`max_cycles: 0` compiles as `0`); with no block, no
  workflow-file, or `--no-workflow`, the compiled output carries the
  scalar `repeat: true` (unlimited cycles, engine defaults). The compiled
  key sits immediately after `description`. A non-repeatable pipeline
  compiles no `repeat` key at all.
- **Structural validation at parse time.** A non-mapping value — including
  the scalar `repeat: true`, which belongs to the compiled flow-file, not
  to the authoring surface — raises `non-mapping repeat block in
  workflow`; an unknown key raises `unknown key in workflow.repeat:
  <KEY>; valid keys: max_cycles, keep_runs`; a non-int value raises
  `non-int value in workflow.repeat.<KEY>`; a negative value raises
  `<KEY> must be >= 0 in workflow.repeat`. A boolean is not an integer
  for these checks.
- **An empty block (`repeat: {}`) equals absence** — the document carries
  no repeat instruction. A workflow consisting of the block alone is
  valid. The workflow-level way to pin a repeatable pipeline to a single
  pass is `repeat: {max_cycles: 1}`.
- **goga owns no cycle logic.** Cycle counting, stop-on-failed-cycle (a
  cycle that ends with a failed stage stops the repeat — no next cycle),
  run-directory pruning, and the `flow_repeated` events the engine emits
  between cycles all belong to afm — the run stays a single `afm run`
  invocation.

## Extending the pipeline with new stages

The `stages` block only overrides stages that already exist in the target
pipeline. The `extend` block does the complementary thing: it **adds brand-new
stages** that are not in the pipeline-file at all. Each `extend` entry is one
new stage, positioned relative to existing stages via `before` / `after`:

```yaml
extend:
  <new-stage-name>:
    before: [plan]            # place this new stage BEFORE the named stage(s)
    after: [specify]          # place this new stage AFTER the named stage(s)
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
  `skip` is likewise forbidden (a new stage has nothing to skip), and so is
  `env` (`env is forbidden in workflow.extend.<NAME>` — per-stage env
  instructions are declared only for existing stages, under `stages`).
- The `title` field, when omitted, falls back to the entry key — so a stage
  declared under `extend: warmup:` without a `title` is still labeled
  `warmup` in the output.

Extend-stage names are **first-class members** of the workflow's name set:
they are valid targets for `stages` entries and for other extend-entries'
`before`/`after` refs (cross-references between extend-stages resolve). The
new stage is always inserted; if a name collides with an existing stage, the
duplicate surfaces at run time. Dangling `before`/`after` refs —
names in neither the original pipeline body nor any extend-stage — are
**structural errors** raised before the embed (see
[How the compiler applies a workflow — Validate references](#step-1-validate-references)).

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
  by the reference validation (see [How the compiler applies a workflow](#how-the-compiler-applies-a-workflow)).

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

A STAGES pipeline `specify → review` with a new `warmup` stage that runs after
`specify`, and a new `extra` stage that runs before `review`:

```yaml
extend:
  warmup:
    after: [specify]
    title: Warmup
    prompt: |
      Bootstrap instruction.
  extra:
    before: [review]
    title: Extra
    prompt: |
      Additional pass before review.
```

Compiled effect (stages format): `warmup` depends on `specify`, and `review`
gains `extra` as an additional dependency —
`specify → warmup`, `extra → review`.

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
  a structural error raised by the reference validation (`unknown stage name in
  workflow.extend.<NAME>.before: <REF>` or the `.after` variant).
- Extend-stages are embedded into the compiled `FlowDocument.stages` only. The
  original `PipelineDocument.body` is never modified — `extend` is a run-time
  layering, like the rest of a workflow-file.

## How the compiler applies a workflow

When a workflow is in scope, the compiler reconstructs the parsed body in
a fixed sequence of steps **before** building the output stages:
references are validated, extend-stages are embedded, skipped stages are
removed and their dependents reconnected, per-stage overrides are applied,
loops are expanded, external `depends_on` references are rewritten, agent
modes are resolved, and memory participation is computed over the finished
working body. Embedding early means a per-stage override or a loop
expansion can also target a stage introduced by `extend`, by name.

### Step 1 — Validate references

Before anything is moved, the compiler validates every name a workflow
could dangle on — existence only; cycles, self-references, and duplicate
refs surface at run time:

- Every `before`/`after` ref in `workflow.extend` must exist in the union
  of the original pipeline step names and the extend-stage names. A
  dangling ref is a **structural error** (`unknown stage name in
  workflow.extend.<NAME>.before: <REF>` or the `.after` variant).
- Every name in `workflow.stages` must exist in the same union. An absent
  name is a **structural error** (`unknown stage name in workflow.stages:
  <name>`). A stage that exists — even if also marked `skip: true` — is
  not flagged.

Both checks run before skip removal, so a name or ref pointing at a stage
that also carries `skip: true` still validates: the stage exists at
validation time and is removed later, at Step 3.

### Step 2 — Embed extend-stages

For each entry in `workflow.extend`, the compiler appends a new stage to
the working step sequence — the verbatim entry body minus `title`, labeled
with the entry's `title` (or, falling back, the entry key). Positioning is
then applied by body format:

- **Stages format** — each `after` name becomes a `depends_on` entry on the
  new stage, and the new stage's name is appended to the `depends_on` of
  each `before` target (existing entries preserved; idempotent). Dangling
  `before`/`after` targets were already rejected at Step 1, so this step
  only ever sees resolvable names.
- **Phases format** — the new stage is inserted positionally after the
  last `after` target and/or before the first `before` target, with no
  explicit `depends_on`. Inconsistent `after`/`before` positions fall back
  to the `after` position.

After this step the extend-stages live in the working sequence alongside
the originals, so every later step applies to them by the same generic
rules.

### Step 3 — Remove skipped stages and reconnect dependents

Stages with `skip: true` are removed from the working body. Dependents'
`depends_on` are reconnected to the skipped stage's predecessors
(transitively for chains; positional collapse for phases). `skip` wins
over other overrides — removal precedes the override step. If the
reconstructed body is empty, the compiler raises `empty body`.

### Step 4 — Apply per-stage overrides

The compiler first resolves one **effective override map** keyed by stage
name, shared by the override and loop-expansion steps: each `extend`
entry seeds a default override from its inline `agent`/`loop`/`approve`,
and each `stages` entry then overlays per-field, winning whenever its
field is not `None` (the inline value is the fallback). A name that
appears only in `stages` is used verbatim; a name that appears only in
`extend` carries just its inline `agent`/`loop`/`approve`.

For each `(stage_name, effective_stage)` pair in the map:

1. Find the step in the body whose `name` or id equals `stage_name`.
2. If not found — silent (only an intentionally skipped stage removed at
   Step 3 reaches here; unknown names already errored at Step 1).
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
     an internal sentinel key (one of `auto`/`plan`/`dialog`, or `None`);
     it is read and consumed during canonical field assembly to drive the
     two approve effects (each on its own directive subset) and never
     reaches the output. See
     [Auto-approval (`approve: auto/plan/dialog`)](#auto-approval-approve-auto-plan-dialog).
   - The effective `manual` instruction is applied to the WORKING copy of
     the body (the parsed `PipelineDocument` is never mutated): `true` sets
     the working body's trigger to `manual` over any authored value
     (idempotent on an already-manual stage); `false` rewrites an effective
     `trigger: manual` back to `on_success` or raises
     `manual: false on non-manual stage <NAME>` when the stage is not
     manual; absent is a no-op. The resulting trigger is translated during
     canonical field assembly into the stage's launch mode. See
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

### Step 5 — Expand loops

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
  Step 6 for the external-reference rewrite.

### Step 6 — Rewrite external depends_on (stages format only)

For each stage in **stages** format with a non-empty `depends_on`, the
compiler replaces any reference to a base name whose `loop_count >= 2`
with `expanded_ids[ref][-1]` — i.e. the **last** expanded id.

For example, if stage `review` has `loop: 2` and another stage declares
`depends_on: [review]`, the compiled output carries
`depends_on: [review-2]`.

### Step 7 — Resolve agent modes

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

### Step 8 — Compute memory participation

After the working body is final (skip removal, loop expansion, and the
external `depends_on` rewrite have all run), the compiler computes memory
participation from the workflow's effective memory configuration — the
authored `memory` block when present, else the materialized defaults
(`method: reflect`, `max_rules: 25`, `commit: false`).

- Under the **reflect** method a stage participates when it carries a
  `reflect` instruction; under the **alignment** method when it carries
  `memory: true`. Participation is looked up per base name in the working
  body, so every `loop`-expanded copy inherits its base's verdict and a
  skipped stage never counts.
- The memory settings apply **iff at least one stage participates** — a
  configuration without participants is a silent no-op: the compiled
  output carries no memory keys at all.
- How the configuration and the per-stage participation are encoded into
  the compiled pipeline is an internal contract of the compiler — this
  documentation intentionally does not pin the compiled form.
- Memory application is output-side only — the source pipeline-file is
  never touched, and an authoring `reflect` or `memory_use` key in any
  stage body is a structural error. A workflow without memory
  participation compiles byte-identically to the same workflow compiled
  before the mechanism existed.

## Profiles

Before parsing, the whole workflow-file is rendered as a [Jinja2](https://jinja.palletsprojects.com/)
template (`trim_blocks`, `lstrip_blocks`, `keep_trailing_newline`; standard
`Undefined`) with the active profile's content as its context — a plain file
renders to itself, and templates without activation render with an empty
context. Rendering never bypasses validation: the rendered text passes the
standard structural validation unchanged.

A profile is a small YAML mapping stored in one of two places, with the
project source winning on name conflicts:

| Source   | Directory               | Notes                                                     |
|---------|--------------------------|-----------------------------------------------------------|
| project | `<cwd>/.goga/profiles/<name>.yml` | Checked into the repository; wins on name conflict. |
| home    | `~/.goga/profiles/<name>.yml`     | Personal; the whole bundle rides into the container base64-encoded via the `GOGA_HOME_PROFILES` engine variable. |

Activation precedence: the `--profile` CLI flag beats the `GOGA_PROFILE`
environment variable, which beats the workflow's own top-level `profile:`
default. The default is peeked from the RAW text — a templated default
(one that materializes only through rendering) does not participate in
activation. Profile names follow the grammar
`[A-Za-z0-9][A-Za-z0-9._-]*` (with `.` and `..` forbidden).

Strictness: a missing or malformed profile is a clean error naming the
profile; a malformed `*.yml` file in `~/.goga/profiles/` is a clean
host-side error before any docker activity; a damaged `GOGA_HOME_PROFILES`
payload is a clean in-container error before any events or launch.

```yaml
# .goga/profiles/nightly.yml
worker:
  agent: codex
  model: sonnet
```

```yaml
# .goga/workflows/deploy.yml — rendered with the profile as context
{% if worker and worker.agent %}
stages:
  build:
    agent: {{ worker.agent }}
{% endif %}
```

The build command consumes the same profiles (see
[build](../../build/cli.md)).

## Invocation modes

A pipeline run picks up a workflow in one of three mutually exclusive modes.
The launcher communicates the chosen mode to the container through
`docker run` argv flags — never through the environment.

| Mode              | Invocation                                  | Container argv                         | Behavior                                                                  |
|-------------------|---------------------------------------------|----------------------------------------|---------------------------------------------------------------------------|
| Auto-match        | `goga pipeline deploy`                      | *(neither)*                            | If `<cwd>/.goga/workflows/deploy.yml` exists, it is applied silently.     |
| Explicit override | `goga pipeline deploy --workflow custom`   | `-w custom`                            | Apply `<cwd>/.goga/workflows/custom.yml`. Host validates existence first. |
| Disable           | `goga pipeline deploy --no-workflow`        | `--no-workflow`                        | Disable workflow application entirely.                                    |

In auto-match mode no host-side validation runs — the workflow-file is
opened and parsed inside the container, and a missing file is silently
treated as "no workflow". In explicit-override mode the host validates the
file exists before launch (exit 1 if missing).

`--workflow` and `--no-workflow` are mutually exclusive — passing both
exits with code 1 before launch.

The card form honors the same three modes: `goga pipeline deploy --info
[-w <wf> | --no-workflow]` resolves the workflow through the identical
rule set, with the same host-side validation. The decision travels as
`docker run` argv in both forms, and the stage list the card prints
is exactly the composition a run with the same flags executes. See
[pipeline](cli.md).

### Log line

When a workflow will actually be applied (explicit `--workflow`, or an
auto-match file that exists), the in-container goga process prints a single
line before the launch output — extended with the resolved profile when one
activated:

```text
Pipeline running with workflow "<name>"
Pipeline running with workflow "<name>" and profile "<profile>"
```

When no workflow applies, no workflow line is printed.

## Example

A workflow that layers a Russian-language answer directive and two
per-stage prompts on top of a pipeline:

```yaml
prompt: |
  Answer in Russian language

stages:
  specify:
    prompt: |
      Task formalization process.

      Requirements:
      - When setting the task, it is necessary to develop stack technologies more carefully.
      - Carefully examine all the link connections between cells

      Constraints:
      - Don't write code examples in the task
      - Don't build architecture in the task
  prototype:
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

A workflow that expands a `review` stage into two passes and pins
its agent to `claude`:

```yaml
stages:
  review:
    loop: 2
    agent: claude
```

Compiled effect: the original `review` stage is replaced by
`review-1` and `review-2`, each depending on the previous
one, both running with the `claude` wrapper.

A workflow that runs different stages on different CLI agents — authoring
on `codex`, review on `claude` — without touching the pipeline-file:

```yaml
stages:
  specify:
    agent: codex
  prototype:
    agent: codex
  architecture-review:
    agent: claude
  plan-review:
    agent: claude
```

Here `codex` does the heavy authoring (specify, prototype) and `claude`
runs the reviews. The underlying pipeline-file stays unchanged — every
project can pin its own agent-per-stage matrix in its workflow-file.

A workflow that adds stages which are not in the pipeline-file at all — a
`warmup` that runs after `specify`, and an `extra` review that runs before
`plan-review`:

```yaml
extend:
  warmup:
    after: [specify]
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
run. In stages format `warmup` depends on `specify`, and `plan-review` gains
`extra` as an additional dependency; in phases format `warmup` is inserted
after `specify` and `extra` before `plan-review`. The pipeline-file itself is
untouched — `extend` layers new stages on top at run time.

## See also

- [Pipeline File](pipeline-file.md) — the base document a workflow layers
  on top of.
- [`goga pipeline` CLI reference](cli.md) — invocation flags
  for `--workflow` / `--no-workflow` and exit codes.
