# Architecture Plan — support-afm-assistants

## Topic

**support-afm-assistants** — afm collaboration (stage assistants and run agents) authored in the workflow-file and delivered through the flow-file parts plus the engine-config plumbing.

Plan path: `.goga/history/2026/support-afm-assistants/arch.md` (printed by `goga history path -f arch.md`).

Decision sources: `adr.md` (delivery decisions — two channels, compiled flow as the single source of truth, fixed defaults) and `prd.md` (requirements) in this topic directory. External engine contract: `.goga/usages/cooks/afm.md`, section "Collaboration (afm v2.x)" (read-only synced usage, already carries the contract on this branch).

Scope guard: four existing cells are modified; no cells, commands, or flags are created. All `WorkflowDocument`/`WorkflowStage`/`write_afm_config` extensions are additive optional parameters with safe defaults, so `goga/build`, `goga/commands/pipeline`, and `goga/commands/build` keep compiling unchanged.

## Implementation Order

1. **`goga/pipeline/workflow`** — leaf, no Imports. Everything downstream consumes its new models and authoring vocabulary; it must exist first.
2. **`goga/pipeline/compiler`** — depends only on `goga/pipeline/workflow`; imports the new `WorkflowAssistant`/`WorkflowDelegation` types and the `assistants` usage.
3. **`goga/pipeline/hooks`** — depends on `goga/pipeline/workflow` (and the hooks platform); extends the overlay merge over the model extended at step 1.
4. **`goga/pipeline`** — depends on compiler, workflow, and hooks; threads the compiled `FlowDocument` and the effective `WorkflowDocument` into the engine-config write.

Rationale per cell: workflow is dependency-free; compiler needs the workflow model; hooks needs the workflow model (merge semantics over the extended fields); pipeline needs all three (it consumes the emitted flow and the effective workflow together).

## Artifacts

### 1. Cell: goga/pipeline/workflow (MODIFIED)

#### CODEMANIFEST delta

**Header**

- `Usages`: unchanged (`convention`, `jinja2`). No `Imports` (the cell stays dependency-free).
- `Annotations`: append after the `memory` paragraph:

```
  assistants is a declarative collaboration instruction set — a top-level
  `assistants:` catalog, a top-level `delegation:` block, and a per-stage
  `assistants:` attachment list. This cell validates the three authoring
  surfaces structurally (entry forms, field types, `when` values, unknown
  keys, the assistant-name grammar, name uniqueness across the catalog and
  every inline declaration, `assistants` forbidden inside extend-entries)
  and extracts them into the document model with materialized defaults
  (`delegate` false, `gate` false, `when` "checkpoints", `max_tasks` 50
  whenever the delegation block is authored). This cell performs NO
  collaboration logic — it resolves no attachment references, derives no
  profile ids, maps no gate or engagement values, and emits no team or
  stage-assistant entries; the consumers consume the extracted values. The
  import graph stays one-directional.

  One entry model serves every authoring form: a catalog entry (name plus
  the declaration fields, no gate/when), a full inline declaration on a
  stage (the catalog field set plus gate/when), and a reference (a bare
  name or a map carrying only name/gate/when). A map entry that carries
  any key beyond name/gate/when is a full inline declaration and requires
  at least one of prompt or skills; a map carrying only name/gate/when is
  a reference and requires nothing further — the reference resolves
  against the assistant names of the same document at compilation.

  Assistant names are globally unique across the workflow-file: the
  catalog and every inline declaration form one namespace, and a repeated
  declaration name is a structural error. Every authored name matches
  [A-Za-z0-9._-]; the name "assistant" is rejected — its dashboard handle
  is reserved by the engine.
```

**Body — new declarations (insert after `WorkflowMemory`)**

```yaml
"WorkflowAssistant(name: str, prompt: str | None = None, skills: list[str] | None = None, agent: str | None = None, delegate: bool = False, env: dict[str, str] | None = None, gate: bool = False, when: str = \"checkpoints\")":
  location: workflow_assistant.py
  annotations: |
    Data model of one assistant authoring entry — a named helper
    declaration and, on a stage entry, its attachment parameters.
    Constructed by `parse_workflow` from a catalog entry or a stage
    attachment; carried inside `WorkflowDocument` (the catalog) and
    `WorkflowStage` (the attachments).

    `name`: the assistant name — matches [A-Za-z0-9._-]; "assistant" is
             rejected; unique across the catalog and every inline
             declaration of one workflow-file
    `prompt`: the assistant's instruction text, or None when not authored
    `skills`: list of the assistant's own skill names, or None when not
              authored
    `agent`: agent name the delivery resolves into the assistant's launch
             command, or None — None resolves to the effective global
             pipeline agent
    `delegate`: whether the assistant may create child tasks; materialized
                false when not authored
    `env`: the assistant's environment instruction (string map, literal
           and/or rendered); an empty map equals absence — None
    `gate`: whether the assistant's verdict must pass before the stage may
            finish; materialized false (advisory) when not authored
    `when`: when the assistant engages — one of "start", "checkpoints",
            "finish"; materialized "checkpoints" when not authored.
            Authored only on a stage attachment; the catalog rejects the
            key

    Build the data model with the standard library dataclasses module
    (NOT pydantic, per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - `name` is required (no default); every other field defaults to its
      materialized value; field order is fixed: name, prompt, skills,
      agent, delegate, env, gate, when

    Constraints:
    - Do not validate the name grammar, types, or value domains here —
      `parse_workflow` enforces them during parsing
    - Do not resolve `agent` into a command, derive a profile id, or map
      `gate`/`when` onto engine values here — the consumers perform both
    - Do not act on `env` here — its delivery is the pipeline run
      coordination's responsibility
  properties:
    "name -> str": |
      The assistant name; unique across one workflow-file's namespace.
    "prompt -> str | None": |
      The assistant's instruction text, or None when not authored.
    "skills -> list[str] | None": |
      The assistant's own skill names, or None when not authored.
    "agent -> str | None": |
      Agent name resolved at delivery into the launch command; None
      resolves to the effective global pipeline agent.
    "delegate -> bool": |
      Whether the assistant may create child tasks; false when not
      authored.
    "env -> dict[str, str] | None": |
      The assistant's environment instruction (string map); None when not
      specified (an empty map equals absence).
    "gate -> bool": |
      Whether the assistant's verdict holds stage completion; false
      (advisory) when not authored.
    "when -> str": |
      When the assistant engages — start, checkpoints, or finish;
      checkpoints when not authored.

"WorkflowDelegation(depth: int | None = None, max_tasks: int = 50)":
  location: workflow_delegation.py
  annotations: |
    Data model of the workflow delegation block — the bounds of helper
    delegation for the run. Constructed by `parse_workflow` from the
    optional top-level block with materialized defaults; carried inside
    `WorkflowDocument`.

    `depth`: the maximum delegation depth — an integer >= 0, or None when
             not authored (no depth bound is delivered)
    `max_tasks`: the whole-run helper task budget; materialized 50
                 whenever the block is authored, the authored value
                 otherwise

    Build the data model with the standard library dataclasses module
    (NOT pydantic, per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - `depth` defaults to None; `max_tasks` defaults to 50 — a
      materialized value, not an omission
    - Field order is fixed: depth, max_tasks

    Constraints:
    - Do not validate types or bounds here — `parse_workflow` enforces
      them during parsing
    - Do not decide which channel each bound travels — the consumers
      deliver depth into the flow and max_tasks into the engine
      configuration
  properties:
    "depth -> int | None": |
      The maximum delegation depth (>= 0), or None when not authored.
    "max_tasks -> int": |
      The whole-run helper task budget; 50 whenever the block is authored
      without a value.
```

**Body — modified declarations**

- `WorkflowStage` — append the last signature parameter `assistants: list[WorkflowAssistant] | None = None`; add the field description, the field-order requirement update, and the property:

```
    `assistants`: the stage's assistant attachments (a list of
                  `WorkflowAssistant`), or None when not specified (an
                  empty list equals absence — normalized to None by
                  `parse_workflow`). Declarative — extracted here, consumed
                  by the compiler to emit the stage's assistants entries
```

```
    "assistants -> list[WorkflowAssistant] | None": |
      The stage's assistant attachments. None when not specified (an empty
      list equals absence).
```

- `WorkflowDocument` — append two signature parameters after `build`: `assistants: dict[str, WorkflowAssistant] | None = None, delegation: WorkflowDelegation | None = None`; add field descriptions, properties, and update the empty-workflow rule:

```
    `assistants`: the assistant catalog — an insertion-ordered map of
                  `WorkflowAssistant` keyed by name (the authored order is
                  the delivery order of the run agents); an empty map
                  (default) means no catalog
    `delegation`: the delegation block, or None when the workflow-file
                  carries no block. A workflow consisting of the block
                  alone is valid
```

```
    "assistants -> dict[str, WorkflowAssistant]": |
      The assistant catalog keyed by name, in authored order. Empty map
      when the workflow-file has no assistants section.
    "delegation -> WorkflowDelegation | None": |
      The delegation block, or None when the workflow-file carries no
      block.
```

Requirements additions: `assistants` defaults to an empty dict via field(default_factory=dict) in the implementation (the signature default None is a DSL representation, the actual default factory is applied at construction); `delegation` defaults to None; the field order extends the fixed order with assistants, delegation after build.

Empty-workflow rule text: prompt None AND stages empty AND extend empty AND memory None AND build None AND assistants empty AND delegation None → structural error; the accepted-top-level-keys message becomes `prompt, stages, extend, memory, profile, build, assistants, delegation`; a workflow consisting of the `assistants:` block alone or the `delegation:` block alone is valid.

- `parse_workflow` — extend the Algorithm with steps 6.5–6.8 (below), extend Requirements/Constraints accordingly:

```
    6.5. For the assistants catalog (when present): the block must be a
        list (otherwise "non-list assistants block in workflow"); each
        entry must be a mapping (otherwise "non-mapping assistant entry in
        workflow.assistants"). Entry key set: name, prompt, skills, agent,
        delegate, env — an unknown key (including gate and when) raises
        "unknown key in workflow.assistants.NAME: KEY; valid keys: name,
        prompt, skills, agent, delegate, env". name is required and a str;
        prompt and agent (when present) are str; skills (when present) is
        a list[str]; delegate (when present) is a bool; env (when present)
        is a str→str map with an empty map equal to absence. At least one
        of prompt or skills must be present — otherwise "assistant NAME
        requires at least one of prompt or skills". Every authored name
        must match [A-Za-z0-9._-] and must not be "assistant" ("assistant
        name is reserved"); a name repeated across the catalog and any
        inline declaration raises "duplicate assistant name: NAME". Build
        a `WorkflowAssistant` per entry with delegate materialized false
    6.6. For the delegation block (when present): the block must be a dict
        (otherwise "non-mapping delegation block in workflow"); the key set
        is depth, max_tasks — an unknown key raises "unknown key in
        workflow.delegation: KEY; valid keys: depth, max_tasks". depth
        (when present) must be an int >= 0; max_tasks (when present) must
        be an int >= 1. Build a `WorkflowDelegation` with max_tasks
        materialized to 50 when not authored
    6.7. For each stage entry carrying an assistants key: the value must
        be a list (otherwise "non-list assistants in
        workflow.stages.NAME"); an empty list equals absence (None). Each
        element is one of three forms — a bare str (a reference; build a
        `WorkflowAssistant` with the name and the materialized defaults),
        a mapping whose keys are within {name, gate, when} (a reference
        with attachment overrides; name required), or a mapping carrying
        any further key (a full inline declaration: the catalog key set
        plus gate and when; name required and at least one of prompt or
        skills). gate (when present) must be a bool; when (when present)
        must be one of start/checkpoints/finish. The name rules of 6.5
        apply to every element; the duplicate-name rule counts an inline
        declaration against the catalog and every other inline
        declaration
    6.8. An assistants key in an extend-entry raises a structural error
        "assistants is forbidden in workflow.extend.NAME" — attachments of
        a new stage are authored in the stages block by the new stage's
        name
```

Requirements additions: the catalog/attachment grammar above; reference names are not resolved here (the compiler raises on a name matching no declaration of the effective document). Constraints addition: do not resolve attachment references or derive profile ids here.

**Footer** — new Description (responsibility zone, no details):

```yaml
Description: |
  Pure parser of project-level workflow-files into declarative
  `WorkflowDocument` instructions that downstream consumers apply to
  extend a pipeline at compilation time — the per-stage overrides, the
  extend-stages, the memory configuration, and the collaboration
  instructions (assistant catalog, delegation bounds, stage
  attachments). Additionally owns the contributor-profile zone of the
  workflow path: profile resolution, strict profile-name validation,
  activation precedence resolution, and whole-file Jinja rendering of
  workflow-files before parsing.
```

#### .usages files

**File: `goga/pipeline/workflow/.usages/assistants.md` (NEW)**

```markdown
# assistants — authoring collaboration in the workflow-file

`assistants` enables a workflow's collaboration with helper agents: a
top-level catalog of run-level assistants, a delegation-bounds block, and
per-stage attachments. The document addresses workflow-file authors:
everything described here is validated structurally at parse time — typos
and type or value mismatches are rejected with a readable error naming the
workflow location.

## The top-level `assistants:` catalog

Each entry is a named assistant present from run start and reachable by
name for the whole run:

| Key | Type | Default | Note |
|-----|------|---------|------|
| `name` | str | required | `[A-Za-z0-9._-]`; `assistant` is reserved; unique across the catalog and every inline declaration |
| `prompt` | str | — | the assistant's instruction |
| `skills` | list[str] | — | the assistant's own skills |
| `agent` | str | global agent | a goga agent name; resolved implicitly at delivery |
| `delegate` | bool | `false` | permission to create child tasks |
| `env` | map[str]str | — | delivered through a generated closure |

At least one of `prompt` or `skills` is required. `gate` and `when` are
attachment parameters — authoring either in the catalog is a structural
error.

## The top-level `delegation:` block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `depth` | int >= 0 | not authored | maximum delegation depth; 0 forbids helper creation |
| `max_tasks` | int >= 1 | `50` (materialized) | whole-run helper task budget |

Both keys are optional; an empty block is valid and materializes
`max_tasks: 50`. A workflow consisting of the block alone is valid.

## Stage attachments (`stages.<name>.assistants`)

Three entry forms:

```yaml
stages:
  build:
    assistants:
      - reviewer                      # 1) bare name — catalog reference
      - name: reviewer                # 2) reference with overrides
        gate: true
        when: finish
      - name: security                # 3) full inline declaration
        agent: codex
        prompt: Audit the diff.
        when: checkpoints
```

| Attachment key | Type | Default | Note |
|------------|------|---------|------|
| `name` | str | required | identifies the assistant |
| `gate` | bool | `false` | `true` — the verdict must pass before the stage finishes |
| `when` | `start` \| `checkpoints` \| `finish` | `checkpoints` | when the assistant engages |

A map entry carrying any key beyond `name`/`gate`/`when` is a full inline
declaration — it accepts the catalog field set plus `gate`/`when` and
requires at least one of `prompt` or `skills`. A map carrying only
`name`/`gate`/`when` is a reference: the agent, prompt, skills, delegate
permission, and env come from the catalog entry; only `gate` and `when`
may be overridden.

Attachments are valid only under `stages.<name>` — never inside an
extend-entry (the attachments of a new stage are authored in the stages
block by the new stage's name). An empty list equals absence.

## Minimal examples

Catalog with attachments and bounds:

```yaml
assistants:
  - name: reviewer
    agent: claude
    delegate: true
    skills:
      - code-audit
    prompt: |
      Review the stage changes and report concrete findings.
delegation:
  depth: 3
  max_tasks: 50
stages:
  build:
    assistants:
      - name: reviewer
        gate: true
        when: finish
```

Attachments only (every entry a full inline declaration):

```yaml
stages:
  build:
    assistants:
      - name: security
        prompt: Audit the diff.
```

## Structural errors (complete list)

| Authoring | Error |
|---|---|
| `assistants:` non-list | non-list assistants block in workflow |
| catalog entry non-mapping | non-mapping assistant entry in workflow.assistants |
| unknown catalog key (incl. `gate`/`when`) | unknown key in workflow.assistants.NAME: KEY; valid keys: name, prompt, skills, agent, delegate, env |
| missing `name` | name is required in workflow.assistants entry |
| no `prompt` and no `skills` | assistant NAME requires at least one of prompt or skills |
| `delegation:` non-mapping | non-mapping delegation block in workflow |
| unknown `delegation:` key | unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks |
| `depth` not int / < 0 | a structural error |
| `max_tasks` not int / < 1 | a structural error |
| `stages.<name>.assistants` non-list | non-list assistants in workflow.stages.NAME |
| invalid `when` value | a structural error listing the permitted values |
| name outside `[A-Za-z0-9._-]` | a structural error naming the entry |
| the name `assistant` | assistant name is reserved |
| duplicate declaration name | duplicate assistant name: NAME |
| `assistants` in an extend-entry | assistants is forbidden in workflow.extend.NAME |

Compilation-time errors (raised by the compiler, not the parser): an
unknown assistant reference; an attachment on a script-only or
planning-only stage; the same assistant attached twice to one stage.

## Anti-patterns

- Do not author `gate`/`when` in the catalog — they are attachment
  parameters.
- Do not author `assistants` inside an extend-entry — the attachments of a
  new stage are authored in the stages block by its name.
- Do not rely on engine defaults: `when`, `gate`, `delegate`, and
  `max_tasks` are materialized by the parser, not silently inherited.
- Do not expect the parser to resolve references — a name that matches no
  catalog entry and no inline declaration of the effective document is a
  compilation error, so a contributor may add catalog entries a workflow
  references.
```

**File: `goga/pipeline/workflow/.usages/parse-workflow.md` (MODIFIED)**

- "Accepted structure": `Top-level keys: prompt, stages, extend, memory, profile, build, assistants, delegation.` plus one-line entries (`assistants` — the catalog list of named run-level helpers; `delegation` — the delegation-bounds block).
- Per-stage key table gains the row: `| assistants | list | the stage's assistant attachments — bare name, reference with gate/when overrides, or full inline declaration; an empty list equals absence; stages block only; declarative |`
- Extend-entry section gains: `assistants is forbidden in an extend-entry (structural error "assistants is forbidden in workflow.extend.<name>") — the attachments of a new stage are authored in the stages block by the new stage's name.`
- Empty-workflow rule: `A workflow is empty only when prompt, stages, extend, memory, build, assistants, AND delegation are ALL absent — profile never counts.`

### 2. Cell: goga/pipeline/compiler (MODIFIED)

#### CODEMANIFEST delta

**Header**

- `Imports` — From: goga/pipeline/workflow. Types become: `WorkflowDocument`, `WorkflowStage`, `WorkflowExtendStage`, `WorkflowMemory`, `WorkflowReflect`, `WorkflowAssistant`, `WorkflowDelegation`. Usages become: `parse-workflow`, `memory`, `assistants`.
- `Usages`: unchanged (`convention`, `beautiful_yaml`, `afm`).
- `Annotations`: in the first paragraph, update the output top-level key enumeration to `prompt, root_dir, name, description, memory, collaboration, team, stages` (replacing "top-level prompt (when present), top-level root_dir (when supplied by the caller), name, description, memory (when memory participates), and a stages list"); append after the workflow-memory-emission paragraph:

```
  Collaboration emission: the cell compiles the workflow's collaboration
  instructions into the flow-file alongside the pipeline stages. The
  top-level collaboration block is emitted into every compiled flow —
  mode "assistants" — with max_depth carried when the workflow's
  delegation block authors a depth. The team list is emitted from the
  catalog in authored order — one member per entry — and omitted entirely
  when the catalog is empty. Stage assistants entries are emitted for
  every attachment of every stage present in the compiled body — uniform
  across every loop-expanded copy; a skipped stage attaches nothing.

  The assistant namespace of a workflow document is the catalog plus
  every full inline declaration of the stages block. An attachment
  naming no namespace member is a structural error "unknown assistant
  reference in workflow.stages.NAME: <assistant>". An assistant name
  appearing twice in one stage's list is a structural error naming the
  stage and the assistant. An attachment on a stage whose translated body
  carries script, or whose translated agents value is exactly
  ["planning"], is a structural error naming the stage and the
  assistant. An attachment on a skipped stage is silent — the stage is
  removed from the compiled body and nothing attaches. The checks run
  over the working body after skip removal and loop expansion, so the
  attachments of a removed stage never count.

  Every emitted entry materializes its defaults: mode from gate (true →
  required, false → advisory), trigger from when (start → one_shot,
  checkpoints → checkpoints, finish → on_completion — the checkpoints
  default is written explicitly, the engine's one_shot default is never
  relied upon), title from the authored name, instruction from the
  authored prompt (the empty string when none), and skills from the
  authored list (an empty list when none). A reference takes its
  declaration fields from the named namespace entry and its own gate and
  when overrides. Every team member and every stage attachment carries
  the generated profile binding goga-<name> — the binding to the profile
  the engine configuration materializes for the ids this flow references.

  Stage-body key prohibition: an authored assistants key in a stage body
  (pipeline-file stage or embedded extend-stage body) is a structural
  error "assistants key is forbidden in stage body; use assistants in
  workflow.stages" — the stage assistants entries are compiled
  exclusively from the workflow instructions.

  Top-level key order: prompt, root_dir, name, description, memory,
  collaboration, team, stages. The stage assistants key occupies the
  canonical fields slot after memory_use and is present only when the
  stage carries at least one effective attachment.

  Use `afm` for the emitted collaboration contract — the team-member and
  stage-assistant key sets, the mode and trigger vocabularies, and the
  profile binding.
  Use `assistants` for the authoring vocabulary of the consumed workflow
  instructions.
```

**Body — new declarations (insert after `FlowMemory`)**

```yaml
"FlowCollaboration(mode: str = \"assistants\", max_depth: int | None = None)":
  location: flow_collaboration.py
  annotations: |
    Emitted top-level collaboration block of the flow-file. Built by
    `compile_flow` on every compilation; consumed by `serialize_flow`.

    `mode`: the dashboard collaboration mode — always "assistants"
    `max_depth`: the authored delegation depth, or None — None omits the
                 key from the output entirely

    Build the data model with the standard library dataclasses module
    (NOT pydantic, per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - mode defaults to "assistants" — the block is emitted into every
      compiled flow
    - Field order is fixed: mode, max_depth — the emission order of the
      block keys; a None max_depth is omitted from the output entirely

    Constraints:
    - Do not decide here whether the block is emitted — `compile_flow`
      always constructs it
    - Do not interpret the block — the runtime behavior belongs to afm
      (per `afm`)
  properties:
    "mode -> str": |
      The dashboard collaboration mode; "assistants" in every emitted
      block.
    "max_depth -> int | None": |
      The authored delegation depth, or None when no depth is authored
      (the key is omitted from the output).

"FlowTeamMember(id: str, title: str, profile: str, instruction: str, skills: list[str])":
  location: flow_team_member.py
  annotations: |
    Emitted team member — one run-level assistant of the flow-file. Built
    by `compile_flow` from one catalog entry of the workflow document, in
    authored order; consumed by `serialize_flow`.

    `id`: the assistant's authored name — the stable identity the engine
          recognizes on resume
    `title`: the display title — the authored name; the dashboard handle
             derives from it
    `profile`: the generated profile binding goga-<name> — the binding to
               the profile the engine configuration materializes for this
               flow
    `instruction`: the assistant's instruction — the authored prompt, the
                   empty string when none is authored
    `skills`: the assistant's own skills — the authored list, an empty
              list when none is authored

    Build the data model with the standard library dataclasses module
    (NOT pydantic, per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - Field order is fixed: id, title, profile, instruction, skills — the
      emission order of the member keys
    - instruction and skills are always materialized — defaults included

    Constraints:
    - Do not derive the profile command here — the engine configuration
      write materializes it
    - Do not interpret the member — the runtime behavior belongs to afm
      (per `afm`)
  properties:
    "id -> str": |
      The assistant's authored name; the identity the engine recognizes
      on resume.
    "title -> str": |
      The display title — the authored name.
    "profile -> str": |
      The generated profile binding goga-<name>.
    "instruction -> str": |
      The assistant's instruction; the empty string when none is authored.
    "skills -> list[str]": |
      The assistant's own skills; an empty list when none is authored.

"FlowAssistant(profile: str, title: str, instruction: str, mode: str, trigger: str, skills: list[str])":
  location: flow_assistant.py
  annotations: |
    Emitted stage attachment entry — one assistant attached to one stage
    of the flow-file. Built by `compile_flow` from one effective
    attachment; consumed by `serialize_flow`.

    `profile`: the generated profile binding goga-<name>
    `title`: the assistant's name
    `instruction`: the authored prompt, the empty string when none
    `mode`: the gate mapping — "required" when the effective gate is
            true, "advisory" otherwise
    `trigger`: the engagement mapping — "one_shot" from start,
               "checkpoints" from checkpoints, "on_completion" from
               finish
    `skills`: the authored skills list, an empty list when none

    Build the data model with the standard library dataclasses module
    (NOT pydantic, per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - Field order is fixed: profile, title, instruction, mode, trigger,
      skills — the emission order of the entry keys
    - Every field is always materialized — defaults included; the
      checkpoints trigger is written explicitly, never inherited from the
      engine default

    Constraints:
    - Do not interpret mode or trigger — the runtime behavior belongs to
      afm (per `afm`)
  properties:
    "profile -> str": |
      The generated profile binding goga-<name>.
    "title -> str": |
      The assistant's name.
    "instruction -> str": |
      The authored prompt; the empty string when none is authored.
    "mode -> str": |
      required when the effective gate is true, advisory otherwise.
    "trigger -> str": |
      one_shot, checkpoints, or on_completion — mapped from when.
    "skills -> list[str]": |
      The authored skills list; an empty list when none is authored.
```

**Body — modified declarations**

- `FlowDocument` — signature becomes `"FlowDocument(prompt: str | None = None, root_dir: str | None = None, name: str, description: str, memory: FlowMemory | None = None, collaboration: FlowCollaboration | None = None, team: list[FlowTeamMember] | None = None, stages: list[FlowStage])"`; update the opening paragraph of the type annotation: the enumeration "a single flat YAML document with up to six top-level keys (prompt (when present), root_dir (when supplied), name, description, memory (when memory participates), stages)" becomes "a single flat YAML document with up to eight top-level keys (prompt (when present), root_dir (when supplied), name, description, memory (when memory participates), collaboration (always), team (when the workflow carries a catalog), stages)" — the rest of the paragraph (no segmentation, no header sub-object; the format is flat, and this type mirrors that flatness) stands; add field descriptions and properties:

```
    `collaboration`: the compiled collaboration block — constructed on
                     every compilation (mode "assistants" in every
                     compiled flow); emitted between memory and team
    `team`: the compiled team list — one `FlowTeamMember` per catalog
            entry in authored order; an empty list omits the key from
            the output entirely
```

```
    "collaboration -> FlowCollaboration | None": |
      The compiled collaboration block; present in every compiled flow.
    "team -> list[FlowTeamMember] | None": |
      The compiled team list in authored order; empty when the workflow
      carries no catalog.
```

The fixed field-order requirement becomes: prompt, root_dir, name, description, memory, collaboration, team, stages — the canonical emission order.

- `FlowStage` — everywhere the canonical fields order is stated (type annotation, `fields` property, `compile_flow`, `serialize_flow`) it becomes: `interactive, auto_approve, auto_run, command, prompt, description, buttons, agents, supervisor, supervisor_prompt, skills, script_before, script, script_after, script_timeout, reflect, memory_use, assistants, then alphabetically-sorted unknown keys`, with the presence rule: `assistants (list) is present only when the stage carries at least one effective attachment; uniform across every loop-expanded copy; a skipped stage carries none`.

- `compile_flow` — extend the Algorithm with sub-step 4.10 and the FlowDocument assembly additions; extend step 5 with the assistants assembly:

```
       4.10. Resolve the assistant attachments of the working body (after
           skip removal and loop expansion): build the assistant namespace
           = the `WorkflowAssistant` catalog of the workflow document ∪
           the full inline declarations found in the stages-block
           attachment lists. For each stage of the working body carrying
           a non-empty effective attachment list:
           - an entry naming no namespace member raises a structural
             error "unknown assistant reference in workflow.stages.NAME:
             <assistant>"
           - the same name twice in one stage's list raises a structural
             error naming the stage and the assistant
           - a stage whose translated body carries script raises a
             structural error naming the stage and the assistant
           - a stage whose translated agents value is exactly ["planning"]
             raises a structural error naming the stage and the assistant
           A reference resolves to the named namespace entry: its
           declaration fields (prompt, skills, agent, delegate, env) come
           from that entry; its gate and when overrides are its own
```

```
       6.   (in FlowDocument assembly) collaboration = a `FlowCollaboration`
            with mode "assistants" and max_depth = the depth of the
            workflow's `WorkflowDelegation` when it carries one, else
            None; team = one `FlowTeamMember` per catalog entry in
            authored order (id = title = the name, profile = goga-<name>,
            instruction = the authored prompt or the empty string,
            skills = the authored list or an empty list); place
            collaboration between memory and team, team between
            collaboration and stages
```

```
       - (step 5 addition) assemble the assistants key from the stage's
         effective attachment list — one `FlowAssistant` per entry with
         every field materialized — into the canonical slot after
         memory_use; uniform across every loop-expanded copy; a stage
         without attachments assembles no assistants key. An authored
         assistants key in a stage body (pipeline-file stage OR embedded
         extend-stage body) raises a structural error "assistants key is
         forbidden in stage body; use assistants in workflow.stages"
         (same pass as the other authoring-key prohibitions)
```

Requirements additions: the checks and materializations above; a collaboration-free workflow compiles byte-identically except the always-emitted collaboration mode key; output-side only — `PipelineDocument` and the source bodies stay untouched. Constraints additions: do not resolve agent names or compose commands for assistants here (the engine configuration write owns that); do not interpret gate/when beyond the mapping; do not re-validate the authoring vocabulary (the workflow parser rejected it).

- `serialize_flow` — extend Algorithm/Requirements/Constraints:

```
       - when `doc` collaboration is not None — emit the collaboration
         block after memory (when present) and before team: a block-style
         mapping, key order mode, max_depth, plain scalars; a None
         max_depth is omitted entirely
       - when `doc` team is non-empty — emit the team list before stages:
         a block-style list; each member a block-style mapping, key order
         id, title, profile, instruction, skills; instruction a plain
         scalar when single-line and a block-literal scalar when
         multi-line (the script-family pattern); skills a block-style
         list, written explicitly when empty
       - stage assistants: a block-style list of mappings in the
         canonical slot after memory_use; each entry a block-style
         mapping, key order profile, title, instruction, mode, trigger,
         skills; instruction follows the script-family pattern; mode and
         trigger plain scalars; skills a block-style list, written
         explicitly when empty
```

Requirements addition: a flow document without a team and without stage attachments serializes without those keys — byte-identical output except the always-present collaboration mode key. Constraints addition: do not reorder the new keys — canonical order is fixed at assembly.

**Footer** — new Description:

```yaml
Description: |
  Pure transformer cell that compiles goga DSL pipeline-files
  (phases-list or stages-map) into afm flow-files (flat YAML with
  optional prompt, name, description, memory, collaboration, team,
  and stages). Optionally applies declarative workflow instructions to
  reconstruct the parsed body before serialization.
```

#### .usages files

**File: `goga/pipeline/compiler/.usages/collaboration-emission.md` (NEW)**

```markdown
# collaboration-emission — compiling collaboration into the afm flow-file

The document describes how the compiler handles workflow collaboration:
which top-level blocks are emitted, which entries the stages receive, and
which defaults are materialized. The audience is compiler consumers and
workflow-file authors checking the expected output.

## The always-emitted collaboration block

`collaboration: {mode: assistants}` is emitted into EVERY compiled flow —
the one deliberate byte-level difference from a collaboration-free
compilation. `max_depth` rides in the block only when the workflow's
`delegation:` block authors a depth. The block sits between `memory` and
`team`; its key order is `mode, max_depth`.

## The team list

The `team:` list is emitted from the workflow catalog in authored order —
one member per entry — and is omitted entirely when the catalog is empty.
Every member materializes every key:

| Key | Value |
|-----|-------|
| `id` | the authored name — the identity the engine recognizes on resume |
| `title` | the authored name — the dashboard handle derives from it |
| `profile` | `goga-<name>` — the binding to the generated profile |
| `instruction` | the authored prompt; the empty string when none |
| `skills` | the authored list; an empty list when none |

## Stage attachments

A stage of the compiled body emits an `assistants` list when it carries at
least one effective attachment — the canonical slot after `memory_use`.
Loop-expanded copies each carry the original stage's attachments; a
skipped stage attaches nothing. References resolve against the assistant
namespace (the catalog plus every full inline declaration): the
declaration fields come from the named entry, the `gate`/`when` overrides
are the attachment's own. Every entry materializes every key:

| Key | Value |
|-----|-------|
| `profile` | `goga-<name>` |
| `title` | the assistant name |
| `instruction` | the authored prompt; the empty string when none |
| `mode` | `required` when `gate: true`; `advisory` otherwise |
| `trigger` | `one_shot` / `checkpoints` / `on_completion` — mapped from `when` |
| `skills` | the authored list; an empty list when none |

The `checkpoints` default is written explicitly — the engine's own
default is `one_shot` and is never relied upon. `skills` is emitted
although the engine does not interpret it on attachments yet (unknown
keys pass silently); the forward-compatible emission starts working the
day the engine supports it.

## Compilation checks

Raised as structural errors naming the workflow location:

- an attachment naming no namespace member — unknown assistant reference
- the same assistant name twice in one stage's list
- an attachment on a stage whose translated body carries `script`
- an attachment on a stage whose translated agents value is exactly
  `["planning"]`

The checks run over the working body after skip removal and loop
expansion — the attachments of a removed stage never count. An authored
`assistants` key in a stage body is likewise a structural error: the
single authoring source is the workflow stages block.

## Invariants

- a collaboration-free workflow compiles byte-identically except the
  always-present collaboration mode key
- `PipelineDocument` is the exact mirror of the source pipeline-file —
  the collaboration block, the team list, and the stage attachments are
  output-side only
- the `compile_flow`/`serialize_flow` signatures are unaffected by
  collaboration authoring
- the compiled flow is the single source of truth for the engine
  configuration: every profile id the flow references (`goga-<name>` of
  each member and each attachment) is materialized there exactly — no dead
  profiles remain for attachments removed by stage skips

## Anti-patterns

- Do not author `assistants` in a stage body or an extend-entry — the
  single authoring point is the workflow stages block.
- Do not re-check the authoring vocabulary on the compiler side — the
  workflow parser rejects it before compilation.
- Do not rely on engine defaults for mode/trigger/instruction/skills —
  every entry materializes them.
```

**File: `goga/pipeline/compiler/.usages/compile-flow.md` (MODIFIED)** — the canonical key-order listings gain the top-level order `prompt, root_dir, name, description, memory, collaboration, team, stages`; the per-stage order gains `assistants` after `memory_use`; a short "Collaboration emission" section states the always-emitted block, the team-list condition, the stage-attachment condition, and the compilation checks.

**File: `goga/pipeline/compiler/.usages/serialize-flow.md` (MODIFIED)** — the canonical per-stage key order gains `assistants` after `memory_use`; the style rules gain the collaboration block, team list, and stage-assistant styles (block-style mappings/lists; instruction follows the script-family pattern; skills written explicitly when empty); key presence gains: team omitted when empty, assistants omitted without attachments, collaboration always present.

### 3. Cell: goga/pipeline/hooks (MODIFIED)

#### CODEMANIFEST delta

**Header** — `Imports`/`Usages` unchanged. `Annotations`: append after the overlay-merge paragraph:

```
  The overlay merge preserves the collaboration instructions of the
  workflow model. The merge maintains the assistant-namespace invariant
  end to end: each name appears at most once across the merged catalog
  and every inline declaration. The assistant catalog merges by name: an
  authored entry wins under its name; a contributing entry adds a fresh
  name; among contributing tools the later entry wins per name; a
  contribution entry whose name appears anywhere in the evolving merged
  assistant namespace — the authored catalog, an inline declaration of
  an authored stage entry, or an entry of an earlier-accepted
  contribution (catalog or inline declaration) — is dropped silently, so
  the merged document never carries a duplicate assistant name. The
  delegation block is whole: the authored block is unbeatable, and
  with no authored block the later contributing block wins — no
  field-level merging. The per-stage assistant lists append with
  deduplication by name: the authored entries first in authored order,
  then the contributing entries in enumeration order, each entry whose
  name is already present on the stage dropped silently, and an appended
  inline declaration whose name is already present anywhere in the merged
  assistant namespace dropped silently the same way. The final
  document assembly carries the merged collaboration fields like every
  workflow-level field — they never vanish in the overlay.
```

**Body — modified declarations**

- `merge_workflow_overlay` — extend the Algorithm with steps 4a, 4b, 5a; add the carve-out sentence to step 4:

```
    4a. assistants (catalog): keep the authored entries — a contribution
        entry under an authored name is not applied; among contributing
        tools the later entry wins per name; a contribution entry whose
        name appears anywhere in the evolving merged assistant namespace
        (the authored catalog, an inline declaration of an authored stage
        entry, or an entry of an earlier-accepted contribution — catalog
        or inline declaration) is dropped silently — the merged namespace
        carries each name exactly once
    4b. delegation: keep the authored block when present — it is
        unbeatable; otherwise the block of the later contributing tool
        wins; no field-level merging
    5a. stage assistants: for each stage name the authored list is the
        ground — the authored entries first, in authored order; the
        contributing entries append in enumeration order, an entry whose
        name is already present on the stage dropped silently, and an
        appended inline declaration whose name is already present
        anywhere in the merged assistant namespace dropped silently the
        same way; a stage with no authored entry takes the appended
        contributing list the same way
```

```
    The assistants field is the one append-merge stage field — it follows
    5a instead of the authored-value-wins rule; every other stage field
    follows the field-set-complete merge unchanged.
```

Requirements additions:

```
    - The rebuilt `WorkflowDocument` preserves the collaboration fields:
      the merged catalog, the effective delegation block, and the
      appended per-stage assistant lists — a rebuild that drops them
      would silently disable collaboration for tool-amended runs
    - The merged result stays declarative — it passes the same compilation
      validation an authored workflow passes, and the merged assistant
      namespace (the catalog plus every inline declaration) never carries
      a duplicate name
```

- `WorkflowAmendment.contribute` — the empty-contribution rule becomes: `A document with no prompt, no stages, no extend, no memory, no assistants, and no delegation is an empty contribution — the delivery discards it with a warning.`
- `PipelineHooks.amend_workflow` — step 5 becomes: `A tool whose buffered document is empty — no prompt, no stages, no extend, no memory, no assistants, no delegation — is a content no-op: a warning naming the tool, the action, and the reason, the contribution discarded, the walk continues.`

**Footer** — new Description:

```yaml
Description: |
  Owner of the pipeline domain hooks zone — the run-event facts, the
  workflow amendment with its overlay, the checkpoint surface over the
  hooks platform, and the bridged mid-run events with their passthrough
  contexts. The overlay merge preserves the full workflow model —
  per-stage `env` instructions, the workflow-level `profile` and `build`
  fields, and the collaboration instructions (assistant catalog,
  delegation block, stage attachments).
```

#### .usages files

**File: `goga/pipeline/hooks/.usages/checkpoints.md` (MODIFIED)** — the amendment bullet becomes:

```markdown
- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, stage
  fields fill only what the author left unset, extend entries add; the
  assistant catalog adds fresh names (authored names win, a tool name
  colliding with any name already in the merged assistant namespace is
  dropped), the delegation block is whole, and stage assistant lists
  append with name deduplication.
```

### 4. Cell: goga/pipeline (MODIFIED)

#### CODEMANIFEST delta

**Header**

- `Imports`:
  - From `goga/pipeline/compiler` — Types: `compile_flow`, `translate_role`, `parse_dsl`, `StructuralError`, `PipelineRoles`, `FlowStage`, `FlowDocument`, `FlowTeamMember`, `FlowAssistant`; Usages: `compile-flow`, `parse-dsl`, `serialize-flow`, `memory-emission`, `collaboration-emission`.
  - From `goga/pipeline/workflow` — Types unchanged; Usages: `parse-workflow`, `memory`, `load-workflow`, `profiles`, `assistants`.
  - All other Imports unchanged.
- `Usages`: unchanged.
- `Annotations`: append after the per-stage-environment-delivery paragraph:

```
  Collaboration delivery: the afm configuration write materializes the
  engine's collaboration plumbing from the two artifacts the run already
  produces — the compiled flow and the effective workflow. The compiled
  flow is the single source of truth: the helper profiles are
  materialized exactly for the generated profile ids the flow references
  (the binding of every team member and of every stage attachment), so
  the two artifacts cannot diverge and no dead profile remains for an
  attachment removed by a stage skip. A generated profile is exactly
  {title, command, delegate}: the title from the assistant name, the
  delegate permission from the declaration, and the command resolved the
  stage-agent way — the declaration's agent, else the effective global
  pipeline agent; a name that resolves to nothing fails the launch with
  a pre-run error naming the assistant and its authoring site (the
  catalog or the stage whose attachment declares it). An assistant carrying an env
  instruction is delivered through a generated sh closure whose path
  becomes the profile's command (a profile carries its own command and
  inherits none); closures are regenerated on every launch, so the
  authored configuration survives the per-launch rewrite by living in
  the workflow-file. The whole-run task budget is written as
  collaboration.limits.max_tasks only when the workflow carries a
  delegation block — the materialized value, 50 when the block omits it.
  The goga- profile prefix is the intended override channel: a
  user-authored same-named profile in the project layer deliberately
  replaces goga's plumbing, and the project-layer engine configuration is
  user territory goga never touches. goga neither reads nor writes the
  collaboration kill-switch — an environment that disables collaboration
  gets engine warnings and skipped helpers, and the run proceeds.

  Use `afm` for the collaboration configuration contract — the profile
  shape, the limits, and the config layers.
  Use `collaboration-emission` for the compiled flow surface the profile
  ids are read from.
  Use `assistants` for the authoring vocabulary of the delivered
  instructions.
```

**Body — modified declarations**

- `write_afm_config` — full replacement of the declaration:

```yaml
"write_afm_config(agent: str | None, flow: FlowDocument | None = None, workflow: WorkflowDocument | None = None) -> config_path: Path":
  location: afm_config.py
  annotations: |
    Write the whole afm configuration file in-container before the afm
    launch: the agent client command resolved from the effective pipeline
    agent, the four static launcher-side fields, goga's own observer hook
    entry, and the collaboration plumbing — the generated helper profiles
    and the whole-run task budget.

    `agent`: the effective pipeline agent — the authored pipeline.agent as
             amended by the config delivery; None when no agent resolves
    `flow`: the compiled flow document — the source of the generated
            profile ids (the binding of every team member and of every
            stage attachment the flow carries); None writes no
            collaboration profiles
    `workflow`: the effective workflow document — the source of each
                referenced assistant's declaration (agent, delegate,
                env); None writes no collaboration plumbing
    `config_path`: the fixed in-container path of the written file

    Apply `convention` for docstring style and intra-package imports.
    Apply `afm` for the configuration-file contract — the field set, the
    fixed home path, the per-stage override relationship, the
    lifecycle-hooks registration of the observer hook entry, and the
    collaboration profile and limits contract.
    Apply `resolve-wrapper-path` when resolving the client agent command
    and every generated profile command.
    Apply `collaboration-emission` for the compiled flow surface the
    profile ids are read from.
    Apply `assistants` for the authoring vocabulary of the delivered
    instructions.

    Algorithm:
    1. Resolve the absolute wrapper path via `resolve_wrapper_path` — only
       when `agent` is not None
    2. Compose the base content: the client command carrying the resolved
       absolute wrapper path (never a bare agent name) — written only when
       an agent resolved, omitted otherwise so per-stage workflow agents
       or the binary's own defaults cover the absent global default; the
       four static fields — the dashboard theme, the disabled browser
       launch, the disabled internal proxy provider, and the in-container
       prompts directory; and the observer hook entry — the stable id
       goga, the in-container hook command of this package's CLI, the
       all-events subscription, the inherited environment, and the afm
       default timeout and retries
    3. When `flow` and `workflow` are both not None — materialize the
       collaboration plumbing:
       1. Collect the referenced profile ids: the profile binding of
          every `FlowTeamMember` of the flow plus the profile binding of
          every stage attachment entry (`FlowAssistant`) of the flow
       2. For each referenced id, locate the assistant declaration by
          name in the workflow's assistant namespace — the catalog plus
          every full inline declaration of the stages block
       3. Resolve each profile's command: when the declaration carries an
          env instruction — validate every declared key as a legal
          environment variable name BEFORE writing any file (an illegal
          key is one strict pre-run error naming the assistant and the
          key), generate the sh closure in a container-local temp
          directory (owner-only access) exporting the env values and
          exec-ing the resolved target wrapper, and the closure path
          becomes the command; otherwise the wrapper of the declaration's
          agent, else the wrapper of the effective global agent (`agent`);
          no agent resolves at all — one strict pre-run error naming the
          assistant and its authoring site (the catalog or the stage
          whose attachment declares it), raised before the file is
          written
       4. Write collaboration.profiles.<id> = {title: <name>, command:
          <resolved>, delegate: <declaration delegate>} — nothing else in
          the profile
       5. When the workflow carries a delegation block — write
          collaboration.limits.max_tasks = the materialized max_tasks
    4. Write the whole file to the fixed in-container home configuration
       path — the path is independent of the afm state directory variable
    5. Return the written path

    Requirements:
    - The whole file is rewritten on every run — a repeated invocation
      stays safe; the collaboration plumbing is regenerated with it, so
      the same authoring takes effect on every consecutive launch
    - The profiles are materialized exactly for the ids the compiled flow
      references — no more, no less; an attachment removed by a stage
      skip leaves no profile behind
    - A generated profile carries exactly title, command, and delegate
    - collaboration.limits.max_tasks is written only when the workflow
      carries a delegation block
    - The four static fields and the hook entry are constants — never
      configurable through the project configuration or the CLI
    - The hook entry declares no secret environment references of its own
    - The content is serialized programmatically — never hand-escaped as
      a string
    - The file lands only at the fixed home configuration path — never in
      the project directory, never in the afm state directory

    Constraints:
    - Do not write a bare agent name as a client or profile command —
      always the resolved absolute wrapper path or closure path
    - Do not derive the prompts directory value or the hook entry values
      from arguments or configuration fields — both are fixed
    - Do not create or manage the prompts directory — the run
      coordination materializes it
    - Do not print any part of the written content
    - Do not write collaboration plumbing from the workflow alone — the
      compiled flow decides which ids exist
    - Do not read or write the collaboration kill-switch (the enabled
      flag or its environment variable) — a disabled environment gets
      engine warnings and skipped helpers, and the run proceeds
    - Do not write closures under the project directory or /workspace —
      container-local temp only
    - Do not print or log env values
```

- `run_pipeline` — the docstring step list and the Algorithm's configuration-write step (16) become:

```
    16. Write the afm configuration file via `write_afm_config` with the
        effective pipeline agent, the compiled flow document, and the
        effective workflow document (the overlay workflow; the resolved
        workflow when the amendment layer is off; None when no workflow
        resolved) — the whole file at the fixed in-container home path,
        before the launch; the collaboration plumbing materializes from
        the two documents, and a collaboration pre-run error (an
        unresolvable assistant agent name or an illegal env key) fails
        the launch with a clean error naming the assistant and its
        authoring site before any events fire
```

Requirements addition: `The afm configuration write receives the compiled flow document and the effective workflow document — the profile set derives from the flow's references, the declarations from the workflow; a collaboration pre-run error fires no events and afm never launches.`

- `apply_skip_stages` — the rebuild step gains: `assistants = the assistants field of the workflow when it is not None else the default empty map; delegation = the delegation field of the workflow when it is not None else None — carried verbatim`; the survival requirement becomes: `The memory configuration, the profile field, the build block, the assistant catalog, and the delegation block of the input workflow survive the rebuild verbatim — a rebuild that drops them would silently disable memory participation, change activation, lose build instructions, or lose collaboration for skip-driven runs.`

**Footer** — new Description:

```yaml
Description: |
  Cell that owns the pipeline workflow: discovery of *.yml pipeline
  files across the project and user pipeline directories, the
  pipeline-file entity model, the informational surface (overview and
  card), run coordination with the in-container run parameters — the
  configuration load-and-amend, the afm configuration authorship with
  the observer-hook registration and the collaboration plumbing
  (generated helper profiles and the task budget), and the launch
  environment composition — the per-stage env delivery through
  generated closure wrappers, the lifecycle-event bridge of the run
  interior, and the in-container CLI entrypoint pipeline_cli.
```

#### .usages files

**File: `goga/pipeline/.usages/collaboration-delivery.md` (NEW)**

```markdown
# collaboration-delivery — delivering assistants into the afm configuration

How authored collaboration reaches the engine on every launch: the
generated helper profiles, the env closures behind their commands, and
the whole-run task budget. Target audience: contributors reasoning about
the delivered artifacts and workflow authors checking why their authoring
survives every launch.

## The two artifacts

The engine consumes collaboration through two artifacts goga already
produces:

- the **compiled flow-file** — `collaboration: {mode: assistants}`,
  `max_depth` when a depth is authored, the `team` list, and the stage
  `assistants` entries;
- the **engine configuration** written before every launch — the generated
  `collaboration.profiles` and `collaboration.limits.max_tasks`.

The compiled flow is the single source of truth: a profile is
materialized exactly for the ids the flow references (`goga-<name>` of
every team member and every stage attachment). The two artifacts cannot
diverge, and no dead profile remains for an attachment removed by a stage
skip.

## Generated profiles

| Key | Value |
|-----|-------|
| `title` | the assistant's authored name |
| `command` | the resolved launch command (below) |
| `delegate` | the authored permission, false by default |

Nothing else is written into a generated profile. The profile id is
`goga-<name>`; the `goga-` prefix is the intended override channel — a
user-authored same-named profile in the project layer (`.afm/config.yaml`)
deliberately replaces goga's plumbing, and that file is user territory
goga never touches.

## Command resolution

The profile's command resolves exactly like a stage agent command:

1. the assistant's authored `agent` → its wrapper path;
2. else the effective global pipeline agent → its wrapper path;
3. else the launch fails strictly before the run with an error naming the
   assistant and its authoring site (the catalog or the stage whose
   attachment declares it).

An assistant carrying an `env` instruction is delivered through a
generated sh closure: the closure exports the assistant's env values and
execs the resolved wrapper, and the closure path becomes the profile's
command — a profile carries its own command and inherits none. Closures
are regenerated on every launch in a container-local temp directory, so
the authored configuration survives the per-launch configuration rewrite
by living in the workflow-file. Env keys must be legal environment
variable names — anything else is a strict pre-run error naming the
assistant and the key, raised before any closure is written.

## The task budget

`collaboration.limits.max_tasks` is written only when the workflow
carries a `delegation:` block — the authored `max_tasks`, materialized to
50 when the block omits it (the engine's own default is 20 and is never
relied upon). `delegation.depth` travels in the flow-file as
`collaboration.max_depth`.

## What goga never does

- goga neither reads nor writes the collaboration kill-switch — an
  environment that disables collaboration gets engine warnings and
  skipped helpers, and the run proceeds.
- goga writes no profile beyond the ids the flow references, and no key
  beyond `{title, command, delegate}`.
- goga never touches the project-layer `.afm/config.yaml`.
```

**File: `goga/pipeline/.usages/run-pipeline.md` (MODIFIED)** — the "afm configuration" section gains:

```markdown
The write also materializes the collaboration plumbing when the run
carries collaboration authoring: generated `collaboration.profiles`
entries (`goga-<name>` = `{title, command, delegate}`) exactly for the
profile ids the compiled flow references, and
`collaboration.limits.max_tasks` when the workflow carries a `delegation:`
block. The compiled flow is the single source of truth for the profile
set; assistant env travels through regenerated closures whose paths
become the profile commands.
```

**File: `goga/pipeline/.usages/per-stage-env.md` (MODIFIED)** — closing self-contained section:

```markdown
## Assistant env

Assistant declarations (`assistants:` catalog entries and inline stage
declarations) carry their own `env` maps delivered through the same
closure mechanism — but the closure path becomes the `command` of the
generated `goga-<name>` helper profile in the afm configuration, not a
flow-file stage patch. Assistant closures are regenerated on every
launch, so the authored configuration survives the per-launch
configuration rewrite by living in the workflow-file.
```

### 5. Documentation (MODIFIED, outside the cells)

**File: `docs/features/pipelines/workflows.md`** — add the user-facing authoring sections for the `assistants:` catalog, the `delegation:` block, and the per-stage `assistants:` instruction (three entry forms, defaults, validation errors), mirroring the structure of the existing workflow-feature sections; state that no profile concept is user-visible and that authored configuration applies on every launch.

## Dependency Map

```
goga/pipeline/workflow (no Imports)
        ▲ WorkflowAssistant, WorkflowDelegation (types) + assistants (usage)
        │
        ├──▶ goga/pipeline/compiler ── FlowDocument, FlowTeamMember, FlowAssistant (types)
        │                                + collaboration-emission (usage) ──▶ goga/pipeline
        │
        └──▶ goga/pipeline/hooks ──────── PipelineHooks et al. (unchanged imports) ──▶ goga/pipeline

goga/pipeline additionally imports (unchanged): goga/afm (run_flow), goga/agents
(resolve_wrapper_path), goga/config, goga/config/hooks, goga/docker, goga/history,
goga/pipeline/workflow (types + usages, extended with `assistants`).
```

Direction is strictly one-way (consumer → supplier, leaves → root); no cycles: the compiler never imports `goga/pipeline` or `goga/pipeline/hooks`; hooks never imports the compiler or the pipeline cell; the workflow cell imports nothing.

## Verification Checklist

Per artifact, after implementation:

**goga/pipeline/workflow**

- `goga lint` passes on the modified CODEMANIFEST; `goga schema goga/pipeline/workflow` lists the two new types.
- Parser tests mirror `tests/pipeline/workflow/`: all three entry forms; every structural error of steps 6.5–6.8 (message text pinned); materialized defaults (`when: checkpoints`, `delegate: false`, `gate: false`, `max_tasks: 50`); duplicate/reserved/charset names; `assistants` in an extend-entry rejected; assistants-only and delegation-only workflows valid; empty-list-equals-absence normalization.
- The cell stays dependency-free: no new `Imports`; `python -c "from goga.pipeline.workflow import WorkflowAssistant, WorkflowDelegation"` resolves through the facade.

**goga/pipeline/compiler**

- `goga lint` passes; schema shows the three new types and the extended imports.
- Compile tests: `collaboration: {mode: assistants}` present in every compiled output (including workflow-less runs); `max_depth` only when authored; team list in authored order, omitted when the catalog is empty; stage assistants materialized in full (mode/trigger/title/instruction/skills) and uniform across loop copies; skipped stage attaches nothing and leaves no dead id; each compile-time error (unknown reference; twice on one stage; script-only; planning-only via `roles: [planner]`); authored `assistants` key in a stage body rejected.
- Byte-identity: a collaboration-free workflow compiles byte-identically except the added mode key (golden comparison).
- Serialization tests: styles of the new keys (block-style mappings/lists; instruction script-family pattern; explicit empty skills lists).

**goga/pipeline/hooks**

- `goga lint` passes.
- Merge tests: catalog merge (authored wins per name; tool adds fresh; a tool name colliding with any name already in the merged assistant namespace dropped); delegation whole-block; stage assistants append-with-dedup; the rebuilt document carries the collaboration fields; the empty-contribution rule counts the new blocks; the merged assistant namespace (catalog plus inline declarations) never duplicates a name — including a tool catalog entry colliding with another tool's inline declaration and the same inline name contributed to two stages.

**goga/pipeline**

- `goga lint` passes; facade imports (`write_afm_config`, `run_pipeline`) unchanged in name.
- Config-write tests: profiles exactly for the referenced ids (`{title, command, delegate}` only); no profile for a skipped attachment; `limits.max_tasks` only with a delegation block, materialized 50; agent fallback chain and the pre-run error naming the assistant and its authoring site; env closures generated with the closure path as command; illegal env key rejected before any file is written; kill-switch never read/written.
- `apply_skip_stages` rebuild carries `assistants`/`delegation` verbatim.
- `run_pipeline` threads flow+workflow into the write; a collaboration pre-run error fires no events and afm never launches.
- Engine-assumption verification (per the task risks): against the afm binary in the image — profile ids of the form `goga-<name>` with `<name>` matching [A-Za-z0-9._-] are accepted; a project-layer `collaboration.limits.max_tasks` overrides goga's global write; `max_depth: 0` suppresses helper creation but not team members. A contradicted assumption updates `.goga/usages/cooks/afm.md` in-task (through the usages-sync flow, never a hand-edit of the synced copy) and the affected delivery rule.
- Full battery: `pytest tests/ -x` and `ruff check` green; existing consumers (`goga/build`, `goga/commands/pipeline`, `goga/commands/build`) import and compile unchanged.

**Documentation**

- `docs/features/pipelines/workflows.md` documents the three authoring surfaces with the same defaults and error behavior the parser enforces.
