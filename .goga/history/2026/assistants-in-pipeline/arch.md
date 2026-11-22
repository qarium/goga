# Architecture Plan — Pipeline-stage assistant declarations

Short name: `assistants-in-pipeline` — immediate attachment, origin-aware
workflow governance.

Plan path: `.goga/history/2026/assistants-in-pipeline/arch.md`.
Normative inputs: `task.md`, `prd.md` (R1–R5, C1–C9, SC1–SC6), `adr.md`
in this topic directory.

All four cells below are **modified** — no cell is created. One new type
(`PipelineAssistant`) is added inside an existing cell; one new code-unit
location (`pipeline_assistant.py`) is introduced by that type. All
annotation and usage-file text below is the current-state contract — the
plan carries no changelogs.

---

## Implementation Order

1. **`goga/pipeline/workflow`** — no dependencies on the other affected
   cells (leaf). Provides the entry model (`WorkflowAssistant`), the
   stage model field semantics, and the authoring-vocabulary practices
   (`assistants`, `parse-workflow`) that the compiler and hooks consume.
2. **`goga/pipeline/compiler`** — depends on `goga/pipeline/workflow`
   (imports `WorkflowAssistant` and the workflow models). Owns the new
   authoring surface, the declaration carriage, and the origin-aware
   assembly — the single place where both documents meet.
3. **`goga/pipeline/hooks`** — depends on `goga/pipeline/workflow`
   (imports the workflow models). Minimal: the overlay merge stays
   pipeline-blind and form-blind; only the contract text of the append
   rule is extended.
4. **`goga/pipeline`** — depends on `goga/pipeline/compiler`,
   `goga/pipeline/workflow`, and `goga/pipeline/hooks`. Owns delivery:
   profile materialization across the extended namespace and the
   threading of the parsed pipeline document.

Documentation updates ride with their cells:
`docs/features/pipelines/pipeline-file.md` with cell 2 (authoring
surface), `docs/features/pipelines/workflows.md` with cell 1
(governance surface).

---

## Artifacts

### Cell 1 — `goga/pipeline/workflow` (MODIFIED)

#### CODEMANIFEST diff — `goga/pipeline/workflow/CODEMANIFEST`

**Header.** Imports: none (unchanged). Usages: `convention`,
`jinja2` (unchanged). Annotations — REPLACE the assistants paragraph
(the one beginning "assistants is a declarative collaboration
instruction set") with:

```yaml
  assistants is a declarative collaboration instruction set — a top-level
  assistants catalog, a top-level delegation block, and a per-stage
  assistants attachment map. Both assistants surfaces are name-keyed maps:
  the catalog is keyed by assistant name and every stage attachment is
  keyed by assistant name. This cell validates the authoring surfaces
  structurally — the name-keyed entry maps, field types, the
  assistant-name grammar, the skip-entry form, the value domain of every
  authored when, unknown keys — and extracts them into the document model
  with ABSENCE-PRESERVING attachment fields (an omitted when/gate is
  carried as not-authored; an authored gate: false is a value) and a
  skip-veto carriage. This cell performs NO collaboration logic — it
  resolves no attachment references, classifies no entry origin (which
  entry is a skip veto over a pipeline-declared assistant, which is an
  extension of one, and which is a reference or an inline declaration is
  knowable only where both documents meet, at compilation), derives no
  profile ids, maps no gate or engagement values, and emits no team or
  stage-assistant entries; the consumers consume the extracted values.
  The import graph stays one-directional.

  One entry model serves every authoring form: a catalog entry (the
  declaration fields under the assistant's name), a full inline
  declaration on a stage (the catalog field set plus gate/when), a
  reference (a value carrying only gate/when), an extension (any entry
  addressing a name declared by the pipeline-file stage — it may omit
  when and author delivery/content fields), and a skip veto ({skip:
  true} alone). Every entry carries exactly one meaningful instruction:
  the veto alone, or at least one extension, reference, or declaration
  field. Whether a when is required is decided by the name's origin at
  compilation, not here. Assistant names match [A-Za-z0-9._-]; the name
  "assistant" is rejected. Uniqueness of a name across the effective
  namespace (the catalog, every inline declaration, and the pipeline
  declarations of the compiled pipeline-file) is a compilation check;
  this cell enforces the grammar and the per-map key uniqueness only.
```

**Body — `WorkflowAssistant`** — REPLACE the whole entry with:

```yaml
"WorkflowAssistant(name: str, prompt: str | None = None, skills: list[str] | None = None, agent: str | None = None, delegate: bool | None = None, env: dict[str, str] | None = None, gate: bool | None = None, when: str | None = None, skip: bool | None = None)":
  location: workflow_assistant.py
  annotations: |
    Data model of one assistant authoring entry — a named helper
    declaration and, on a stage entry, its attachment, extension, or
    veto parameters. Constructed by parse_workflow from a catalog entry
    or a stage attachment; carried inside WorkflowDocument (the
    catalog) and WorkflowStage (the stage entries).

    `name`: the assistant name — the map key of the entry on every
            authoring surface; matches [A-Za-z0-9._-]; "assistant" is
            rejected
    `prompt`: the assistant's instruction text, or None when not
              authored
    `skills`: list of the assistant's own skill names, or None when not
              authored — an authored empty list is carried as an
              explicit override that clears
    `agent`: agent name the delivery resolves into the assistant's
             launch command, or None — None resolves to the effective
             global pipeline agent
    `delegate`: whether the assistant may create child tasks — None when
                not authored (an inheritable value at the overlay
                merge), False when explicitly authored off, True when
                authored on
    `env`: the assistant's environment instruction (string map); None
           when not authored — an authored empty map is an explicit
           override that clears
    `gate`: whether the assistant's verdict must pass before the stage
            may finish — None when not authored (an entry addressing a
            pipeline-declared name inherits its gate; a reference or an
            inline declaration materializes false at emission), True or
            False when authored
    `when`: when the assistant engages — one of start, checkpoints,
            finish, message, or None when not authored (an entry
            addressing a pipeline-declared name inherits its engagement;
            a reference or an inline declaration requires one at
            compilation)
    `skip`: the veto carriage — None on every non-skip entry, True on a
            {skip: true} entry addressing a pipeline-declared name of
            that stage

    Use `convention` for the data-model rules (dataclasses kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - gate/when/skip default to None — absence stays distinguishable
      from every authored value; field order is fixed: name, prompt,
      skills, agent, delegate, env, gate, when, skip

    Constraints:
    - Do not validate the name grammar, types, or value domains here —
      parse_workflow enforces them during parsing
    - Do not classify the entry origin, resolve references, derive
      profile ids, or map gate/when onto engine values here — the
      consumers perform both
  properties:
    "name -> str": |
      The assistant name — the map key on every authoring surface.
    "prompt -> str | None": |
      The assistant's instruction text, or None when not authored.
    "skills -> list[str] | None": |
      The assistant's own skill names, or None when not authored; an
      authored empty list is an explicit override that clears.
    "agent -> str | None": |
      Agent name resolved at delivery into the launch command; None
      resolves to the effective global pipeline agent.
    "delegate -> bool | None": |
      Whether the assistant may create child tasks — None inheritable
      at the overlay merge, explicit False an authored opt-out.
    "env -> dict[str, str] | None": |
      The assistant's environment instruction (string map); None when
      not authored — an authored empty map is an explicit override that
      clears.
    "gate -> bool | None": |
      Whether the assistant's verdict holds stage completion — None
      when not authored (an entry addressing a pipeline-declared name
      inherits its gate; a reference or an inline declaration
      materializes false at emission), authored True/False otherwise.
    "when -> str | None": |
      When the assistant engages — start, checkpoints, finish, or
      message, or None when not authored (an entry addressing a
      pipeline-declared name inherits its engagement; a reference or an
      inline declaration requires one at compilation).
    "skip -> bool | None": |
      The veto carriage — None on every non-skip entry, True on a
      {skip: true} entry addressing a pipeline-declared name of that
      stage.
```

**Body — `WorkflowStage`** — signature unchanged. In the type
annotation, REPLACE the `assistants` parameter description with:

```yaml
    `assistants`: the stage's assistant entries — a map of
                  WorkflowAssistant keyed by assistant name, in authored
                  order. None when not specified (an empty map equals
                  absence). Each entry is a reference, a full inline
                  declaration, an extension of a name declared by the
                  pipeline-file stage, or a skip veto; the origin decides
                  at compilation. Declarative — extracted here, consumed
                  by the compiler to emit the stage's assistants entries
```

and REPLACE the property annotation with the same semantics:

```yaml
    "assistants -> dict[str, WorkflowAssistant] | None": |
      The stage's assistant entries keyed by assistant name, in authored
      order. None when not specified (an empty map equals absence). Each
      entry is a reference, a full inline declaration, an extension of a
      name declared by the pipeline-file stage, or a skip veto; the
      origin decides at compilation.
```

**Body — `parse_workflow`** — signature unchanged. In the Algorithm,
REPLACE step 6.7 with:

```yaml
    6.7. For each stage entry carrying an assistants key: the value must
        be a mapping keyed by assistant name (otherwise "non-mapping
        assistants in workflow.stages.NAME; author the map form keyed by
        assistant name"); an empty map equals absence (None). Each entry
        value must be a mapping (otherwise "non-mapping assistant
        attachment in workflow.stages.NAME.ASSISTANT"). Every entry
        carries exactly one meaningful instruction:
        - skip form: the value carries skip alone, strictly bool;
          skip: true is the veto entry; a lone skip: false raises
          "skip: false requires an extension field in
          workflow.stages.NAME.assistants.ASSISTANT"; skip together with
          any other key raises "skip cannot be combined with extension
          keys in workflow.stages.NAME.assistants.ASSISTANT"; an empty
          entry raises "empty assistant entry in
          workflow.stages.NAME.assistants.ASSISTANT"
        - every other form: the key set is prompt, skills, agent,
          delegate, env, gate, when — an unknown key raises "unknown key
          in workflow.stages.NAME.assistants.ASSISTANT: KEY; valid keys:
          prompt, skills, agent, delegate, env, gate, when". prompt and
          agent (when present) are str; skills (when present) is a
          list[str] (an authored empty list is an explicit override that
          clears); delegate (when present) is a bool (absent builds
          None — not False); env (when present) is a str→str map (an
          authored empty map is an explicit override — NOT normalized to
          absence). gate (when present) is strictly bool, carried as
          None when absent. when (when present) is one of
          start/checkpoints/finish/message, carried as None when absent.
          The name rules apply to every entry key; names are unique
          within the map. Build a WorkflowAssistant per entry with the
          key as name
```

In the Algorithm, in step 6.5 (assistants catalog), REPLACE the closing
name-rules sentence ("Every entry key must match [A-Za-z0-9._-] and must
not be "assistant" ("assistant name is reserved"); a key repeated across
the catalog and any inline declaration raises "duplicate assistant
name: NAME"") with:

```yaml
    Every entry key must match [A-Za-z0-9._-] and must not be "assistant"
    ("assistant name is reserved"); names are unique within the map (a
    YAML mapping cannot repeat a key) — uniqueness of a name across the
    catalog, the stage attachment maps, and the pipeline declarations of
    the compiled pipeline-file is a compilation check, not a parse rule
```

In the Requirements of `parse_workflow`: REMOVE the requirement line
requiring `when` on every stage attachment ("The stage attachment
grammar: ... when is required on every entry ..."); REPLACE the
assistant-grammar requirements with:

```yaml
    - The stage attachment grammar: a name-keyed mapping; an empty map
      equals absence (None); each entry value is a mapping whose lone key
      skip forms the veto, whose keys within {gate, when} form a
      reference, and whose any further key forms a full inline
      declaration or an extension (the catalog key set plus gate and
      when); the value domain of when is validated whenever authored;
      gate and skip are bools
    - For assistant fields, presence is preserved: skills [] and env {}
      are explicit empty overrides; delegate/gate/when absent are None
```

REMOVE the duplicate-name requirement ("Assistant names ... unique
across the catalog and every inline declaration — a repeated declaration
name raises ..."). In the Constraints, ADD:

```yaml
    - Do not enforce a when on any entry and do not check name uniqueness
      beyond the entry's own map — both are origin-aware compilation
      checks
    - Do not classify an entry as skip/extension/reference/inline — the
      origin resolves where both documents meet
```

**Footer** — unchanged.

#### `.usages/` files

**File `goga/pipeline/workflow/.usages/assistants.md`** — REPLACE the
whole file with:

````md
# assistants — authoring collaboration in the workflow-file

`assistants` enables a workflow's collaboration with helper agents: a
top-level catalog of run-level assistants, a delegation-bounds block, and
per-stage attachments. The document addresses workflow-file authors:
everything described here is validated structurally at parse time — typos
and type or value mismatches are rejected with a readable error naming the
workflow location.

Both assistants surfaces are name-keyed maps: the entry key IS the assistant
name, and an entry value never repeats it.

## The top-level `assistants:` catalog

Each key is an assistant name; each value declares an assistant present from
run start and reachable by name for the whole run:

| Value key | Type | Default | Note |
|-----------|------|---------|------|
| `prompt` | str | — | the assistant's instruction |
| `skills` | list[str] | — | the assistant's own skills |
| `agent` | str | global agent | a goga agent name; resolved implicitly at delivery |
| `delegate` | bool | not authored | explicit false is an authored opt-out; omitted is inheritable |
| `env` | map[str,str] | — | delivered through a generated closure |

An entry MAY carry neither `prompt` nor `skills` — an override-style
entry that configures delivery fields (`agent`, `delegate`, `env`) and
takes its content from a tool-delivered entry of the same name. The
EFFECTIVE entry must resolve `prompt` or `skills` — enforced at
compilation with an error naming the assistant and its authoring site;
an override naming an assistant no tool delivers stops compilation. The
entry key is the assistant name: it matches `[A-Za-z0-9._-]`,
`assistant` is reserved, and it is unique across the catalog and every
inline declaration. `name`, `gate`, `when`, and `skip` never appear in a
catalog entry value — `name` is the key itself, and `gate`/`when`/`skip`
are stage-entry parameters.

## Explicit empty values (overrides)

`skills: []` and `env: {}` are authored overrides that CLEAR the field —
they are not absence. `delegate:` omitted is absence (the value may flow
from a tool-delivered entry); `delegate: false` is an explicit opt-out.
`gate:` and `when:` omitted are absence too — an entry addressing a
pipeline-declared assistant inherits its values (below). Absence vs
empty decides what a tool delivery or a pipeline declaration may still
supply.

## The top-level `delegation:` block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `depth` | int >= 0 | not authored | maximum delegation depth; 0 forbids helper creation |
| `max_tasks` | int >= 1 | `50` (materialized) | whole-run helper task budget |

Both keys are optional; an empty block is valid and materializes
`max_tasks: 50`. A workflow consisting of the block alone is valid.

## Stage attachments (`stages.<name>.assistants`)

A name-keyed map: each key is an assistant name, each value carries the
entry's instruction — exactly one meaningful instruction per entry. A
compiling example:

```yaml
assistants:
  reviewer:
    prompt: Review the stage changes.
  auditor:
    prompt: Audit the stage changes.
stages:
  build:
    assistants:
      reviewer:
        when: finish          # 1) reference — declaration comes from the catalog
      auditor:
        gate: true            # 2) reference with the gate override
        when: finish
      security:               # 3) full inline declaration
        agent: codex
        prompt: Audit the diff.
        when: checkpoints
```

| Entry key | Type | Default | Note |
|------------|------|---------|------|
| `when` | `start` \| `checkpoints` \| `finish` \| `message` | not authored | when the assistant engages |
| `gate` | bool | not authored | `true` — the verdict must pass before the stage finishes |
| `skip` | bool | not authored | `true` ALONE — veto one pipeline-declared assistant of this stage |

`when` is required on an entry that names an assistant declared in the
workflow-file (a catalog entry or a full inline declaration) — the entry
names the assistant, so its engagement timing is authored explicitly. A
when-less entry is legal authoring when the name is declared by the
pipeline-file stage the entry addresses (an extension — see below);
compilation raises "when is required" for a when-less entry naming no
such declaration. `gate` is optional on every entry.

`when: message` is the resting engagement: the engine sends NO initial
request — the helper waits idle until someone messages it, each message
is one turn, and the helper stays attached afterwards. Combine it with
`gate: true` deliberately: a gated message helper produces a verdict only
after it is messaged, so a stage attaching one never finishes until
someone writes to the helper and its verdict passes.

A value carrying any key beyond `gate`/`when` is a full inline declaration
— it accepts the catalog field set plus `gate`/`when` and may carry
neither `prompt` nor `skills` (an override-style inline declaration; the
effective-content requirement is enforced at compilation). A value
carrying only `gate`/`when` is a reference: the agent, prompt, skills,
delegate permission, and env come from the catalog entry; only `gate` and
`when` are the entry's own.

Attachments are valid only under `stages.<name>` — never inside an
extend-entry (the attachments of a new stage are authored in the stages
block by the new stage's name). An empty map equals absence.

## Governing pipeline-shipped assistants

A stage of the pipeline-file may ship its own helper declarations (authored
in the pipeline-file stage body). The workflow addresses such a shipped
assistant through the same `stages.<stage>.assistants.<name>` entry, keyed
by the name's origin:

**Skip — the veto.** `{skip: true}` alone removes the assistant from that
stage for this project: no attachment, no team membership, no generated
profile — the stage itself still runs. `skip` targets exactly one
pipeline declaration of that stage; skipping a name no pipeline
declaration of that stage declares is a compilation error (a catalog or
inline name is governed by not authoring an attachment, never by skip).
`skip: false` alone authoring nothing is a structural
error, and `skip` mixed with any other key is a contradictory-authoring
error.

**Extension — additive configuration.** Any other entry addressing a
pipeline-declared name extends it:

| Key | Effect |
|-----|--------|
| `when` | overrides the pipeline engagement (omitted — the pipeline value stands) |
| `gate` | overrides the pipeline gate (omitted — stands; explicit `false` deliberately downgrades a gated helper to advisory) |
| `agent` / `env` / `delegate` | configure delivery for this project |
| `prompt` | APPENDED to the pipeline text — pipeline text first, one blank line, then this text |
| `skills` | EXPANDS the pipeline list — pipeline entries first, then these, deduplicated by value |

An extension may omit `when` — the pipeline engagement stands. A workflow
that mentions a shipped assistant not at all leaves it exactly as the
pipeline authored it — it attaches on every run, with or without a
workflow-file.

**Visibility.** A pipeline-declared name is visible only to its own
stage's entry: addressing it from another stage is an unknown-assistant
error. The name must not collide with the workflow's catalog or any
inline declaration — one global namespace, enforced at compilation.

## Minimal examples

Veto one shipped assistant, extend another:

```yaml
stages:
  review:
    assistants:
      auditor:            # declared by the pipeline-file stage 'review'
        skip: true        # veto — does not run in this project
      notifier:           # declared by the pipeline-file stage 'review'
        when: checkpoints # re-time: pipeline 'finish' overridden
        agent: codex      # delivery retargeted for this project
```

Extend content (append + expand):

```yaml
stages:
  build:
    assistants:
      security:           # declared by the pipeline-file stage 'build'
        prompt: |
          Also check the lockfile.
        skills: [dep-audit]   # added after the pipeline skills, deduplicated
```

## Structural errors (complete list)

| Authoring | Error |
|---|---|
| `assistants:` non-mapping (a list, a string, a scalar) | non-mapping assistants block in workflow; author the map form keyed by assistant name |
| catalog entry value non-mapping | non-mapping assistant entry in workflow.assistants.NAME |
| unknown catalog key (incl. `name`, `gate`, `when`, `skip`) | unknown key in workflow.assistants.NAME: KEY; valid keys: prompt, skills, agent, delegate, env |
| `delegation:` non-mapping | non-mapping delegation block in workflow |
| unknown `delegation:` key | unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks |
| `depth` not int / < 0 | a structural error |
| `max_tasks` not int / < 1 | a structural error |
| `stages.<name>.assistants` non-mapping (a list, a string, a scalar) | non-mapping assistants in workflow.stages.NAME; author the map form keyed by assistant name |
| attachment value non-mapping | non-mapping assistant attachment in workflow.stages.NAME.ASSISTANT |
| unknown stage-entry key | unknown key in workflow.stages.NAME.assistants.ASSISTANT: KEY; valid keys: prompt, skills, agent, delegate, env, gate, when |
| invalid `when` value (when authored) | a structural error listing the permitted values |
| non-bool `gate` / non-bool `skip` | a structural error |
| `skip: true` mixed with any other key | skip cannot be combined with extension keys in workflow.stages.NAME.assistants.ASSISTANT |
| lone `skip: false` | skip: false requires an extension field in workflow.stages.NAME.assistants.ASSISTANT |
| empty entry `{}` | empty assistant entry in workflow.stages.NAME.assistants.ASSISTANT |
| name outside `[A-Za-z0-9._-]` | a structural error naming the entry |
| the name `assistant` | assistant name is reserved |
| `assistants` in an extend-entry | assistants is forbidden in workflow.extend.NAME |

Compilation-time errors (raised by the compiler, not the parser): a
missing `when` on an entry naming no pipeline declaration of that stage
(a reference or a full inline declaration); an unknown assistant
reference (including a pipeline-declared name addressed from another
stage); a name collision across the effective namespace (catalog, inline,
pipeline declarations — including tool-delivered contributions); an
effective entry resolving no prompt and no skills; an attachment on a
script-only or planning-only stage; the same assistant attached twice to
one stage by a programmatic contribution.

## Anti-patterns

- Do not author `name` inside an entry — the map key IS the assistant name.
- Do not author `gate`/`when`/`skip` in the catalog — they are stage-entry
  parameters.
- Do not rely on a defaulted `when` on a workflow-declared assistant — its
  engagement timing is always authored; only a pipeline-declared assistant
  carries one the extension may inherit.
- Do not combine `skip` with extension keys — the veto is authored alone.
- Do not author `assistants` inside an extend-entry — the attachments of a
  new stage are authored in the stages block by its name.
- Do not expect the parser to resolve references or classify origins — a
  name that matches no declaration of the effective document is a
  compilation error.
- Do not rely on engine defaults: `gate` and `max_tasks` materialize at
  emission; `delegate` omitted is inheritable; the compiled engagement
  value is always written explicitly.
````

**File `goga/pipeline/workflow/.usages/parse-workflow.md`** — two
replacements:

1. The `- assistants` bullet in "Accepted structure" becomes:

```md
- `assistants` — the name-keyed catalog map of run-level helpers; the
  per-stage attachments (`stages.<name>.assistants`) are a name-keyed map
  too — each entry a reference (`gate`/`when`), a full inline declaration
  (the catalog field set plus `gate`/`when`), an extension of a
  pipeline-declared name (may omit `when`), or a `{skip: true}` veto.
```

2. The `assistants` row of "Per-stage override keys" becomes:

```md
| assistants | map | the stage's assistant entries keyed by assistant name — a reference (`gate`/`when`), a full inline declaration, an extension of a pipeline-declared name (may omit `when`), or a `{skip: true}` veto; every entry carries exactly one meaningful instruction; an empty map equals absence; stages block only; declarative (origin classification, `when`-requirement, and namespace uniqueness are compilation checks) |
```

---

### Cell 2 — `goga/pipeline/compiler` (MODIFIED)

#### CODEMANIFEST diff — `goga/pipeline/compiler/CODEMANIFEST`

**Header.** Imports: unchanged (WorkflowAssistant and the workflow
models are already imported; usages parse-workflow/memory/assistants/
gates unchanged). Usages: `convention`, `beautiful_yaml`, `afm`
(unchanged). Annotations — five changes:

1. REPLACE the paragraph "Stage-body key prohibition: an authored
   assistants key in a stage body ... is a structural error ..." with:

```yaml
  Stage-body assistant declarations: an authored assistants key in a
  pipeline-file stage body (both body formats) is the stage's helper
  declaration surface — a name-keyed map where every entry declares one
  helper of that stage: its content (prompt, skills) and its engagement
  (when — required, one of start/checkpoints/finish/message; gate —
  optional, materializing false). The delivery keys (agent, env,
  delegate) are not part of the stage-body vocabulary — authoring any of
  them is a structural error naming the stage and the assistant;
  delivery is workflow-file territory. Every declaration resolves
  content — prompt or skills authored — a structural error naming the
  stage and the assistant otherwise. An authored assistants key inside
  an embedded extend-stage body is a structural error naming the stage —
  attachments of a new stage are authored in the workflow stages block
  by the new stage's name.
```

2. REPLACE the paragraph beginning "The assistant namespace of a
   workflow document is the catalog plus every full inline declaration
   ..." with:

```yaml
  The effective assistant namespace of a compilation spans the workflow
  catalog, every full inline declaration of the stages-block entry maps,
  and the pipeline declarations of the compiled body. A name carried by
  two sources is a structural error naming both authoring sites (a
  tool-delivered contribution colliding through the overlay included).
  An entry naming a pipeline declaration of its own stage is a skip (the
  {skip: true} veto — no attachment, no team member, no profile for that
  name; the stage itself still runs) or an additive extension: when/gate
  override the pipeline values with absence inheriting them (an authored
  gate: false deliberately downgrades a gated helper), agent/env/
  delegate configure delivery, prompt appends to the pipeline text
  (pipeline text first, one blank line, then the workflow text; a
  single-sided text stands alone), and skills expands the pipeline list
  (pipeline entries first, then workflow entries, deduplicated by value
  preserving first occurrence). An entry naming no pipeline declaration
  of that stage keeps the catalog-reference and inline-declaration
  semantics and requires its own when — the when-required check is
  origin-aware and lives here, where both documents meet (a when-less
  entry extending a pipeline declaration of the same stage is legal
  authoring). A pipeline declaration is visible only to its own stage's
  entry: an entry of another stage naming it is an
  unknown-assistant-reference structural error. An attachment from any
  source on a stage whose translated body carries script, or whose
  translated agents value is exactly ["planning"], is a structural error
  naming the stage and the assistant — the check runs over the working
  body with or without a workflow document (a pipeline declaration
  attaches on every run). An attachment on a skipped stage is silent —
  the stage is removed from the compiled body and nothing attaches.
```

3. REPLACE the paragraph beginning "Collaboration emission: the cell
   compiles the workflow's collaboration instructions ..." with:

```yaml
  Collaboration emission: the cell compiles collaboration from both
  authoring surfaces — the workflow document (catalog, delegation, stage
  entries) and the pipeline declarations each stage body carries — into
  the flow-file alongside the pipeline stages. The top-level
  collaboration block is emitted into every compiled flow — mode
  "assistants" — with max_depth carried when the workflow's delegation
  block authors a depth. The team list is emitted from the catalog in
  authored order, then the pipeline-declared members in pipeline body
  stage order (each stage's declarations in authored order;
  loop-expanded copies collapse to their base stage's first occurrence;
  vetoed and stage-skipped declarations never join; a name joins exactly
  once) — omitted entirely when both sources are empty. Stage assistants
  entries are emitted for every effective attachment of every stage
  present in the compiled body — uniform across every loop-expanded
  copy; a skipped stage attaches nothing; within one stage's compiled
  attachment list the pipeline declarations come first (pipeline
  authored order), then the workflow entries (workflow authored order) —
  the same pipeline-first rule as the prompt append and the skills
  expansion. The team list order is deliberately the opposite: catalog
  members before pipeline-declared members.
```

4. In the emission-defaults paragraph ("Every emitted entry
   materializes its defaults: ..."), REPLACE the skills-channel
   sentences with:

```yaml
  The stage entry carries NO skills key — the engine strict-parses
  stages[].assistants and rejects unknown fields ("unknown field
  \"skills\"; use \"profile\"" on afm v2.0.9); skills reach the engine
  ONLY through a team member entry (which accepts them), and the team
  draws from the catalog and the pipeline declarations — so a catalog or
  pipeline declaration's skills are delivered, while a workflow inline
  declaration's authored skills have no engine channel and a compile-time
  WARNING names the stage and the assistant (once per name) instead of
  dropping them silently.
```

5. ADD a new paragraph after the collaboration-emission paragraph:

```yaml
  Pipeline declaration carriage: the assistants map of a pipeline-file
  stage body is extracted at parse time into the typed assistants field
  of the step models; the verbatim body mirrors every other field. The
  parsed representation carries the declarations unchanged — the
  workflow extension applies at compilation, output-side only;
  PipelineDocument stays the faithful mirror of the source.
```

**Body — ADD the new entry** (new code unit
`goga/pipeline/compiler/pipeline_assistant.py` referenced by location):

```yaml
"PipelineAssistant(name: str, prompt: str | None = None, skills: list[str] | None = None, when: str, gate: bool = False)":
  location: pipeline_assistant.py
  annotations: |
    Data model of one pipeline-file stage-declared helper — the
    declaration a stage body carries under its assistants map.
    Constructed by parse_dsl from one entry of the stage's map; carried
    inside PhaseStep and StageStep (their assistants field); consumed by
    compile_flow to assemble the stage's attachments and team members.

    `name`: the assistant name — the map key; matches [A-Za-z0-9._-];
            "assistant" is rejected; unique within its stage's map
            (uniqueness across the effective namespace is a compilation
            check)
    `prompt`: the helper's instruction text, or None when not authored
    `skills`: the helper's own skill names, or None when not authored —
              an authored empty list is a value
    `when`: the engagement — one of start, checkpoints, finish, message;
            authored on every declaration; no default exists
    `gate`: whether the helper's verdict must pass before the stage may
            finish; materialized false when not authored

    Use `convention` for the data-model rules (dataclasses kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - name is required (no default); prompt and skills default to None;
      when is required (no default — no compiler-side engagement
      default exists); gate defaults to False; field order is fixed:
      name, prompt, skills, when, gate

    Constraints:
    - Do not validate the name grammar, types, or value domains here —
      parse_dsl enforces them during parsing
    - Do not resolve delivery — the declaration carries no delivery
      fields; agent, env, and delegate are workflow-file territory
  properties:
    "name -> str": |
      The assistant name — the map key; unique within its stage's map.
    "prompt -> str | None": |
      The helper's instruction text, or None when not authored.
    "skills -> list[str] | None": |
      The helper's own skill names, or None when not authored; an
      authored empty list is a value.
    "when -> str": |
      The engagement — start, checkpoints, finish, or message; authored
      on every declaration; no default exists.
    "gate -> bool": |
      Whether the helper's verdict holds stage completion; materialized
      false when not authored.
```

**Body — `PhaseStep`** — REPLACE the entry with (signature gains the
field; annotations gain the parameter line; properties gain the field):

```yaml
"PhaseStep(name: str, title: str, body: dict[str, Any], assistants: dict[str, PipelineAssistant] | None = None)":
  location: phase_step.py
  annotations: |
    One element of a phases-DSL body — a single dash-prefixed name list item.

    `name`: step id (the value of the name field inside the list item)
    `title`: display label (the value of title inside the item)
    `body`: verbatim copy of every other field in the item (e.g. roles,
            prompt, skills, interactive, and any extra fields),
            excluding name, title, and assistants
    `assistants`: the step's pipeline assistant declarations — a map of
                  PipelineAssistant keyed by assistant name, in authored
                  order, or None when the source body carries no
                  assistants key or an empty map

    Does not carry depends_on — the compiler generates it from list
    position when building FlowStage.

    The body field is intentionally typed as dict[str, Any]: the cell
    does not validate or know the schema of step fields. Build the data
    model with the standard library dataclasses module (NOT pydantic,
    per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - The body field excludes name, title, and assistants (those are
      separate fields); the assistants key is extracted from the source
      body at parse time

    Constraints:
    - Do not validate the contents of body — pass it through verbatim
    - Do not normalize or rename keys in body

  properties:
    "name -> str": |
      Step id.
    "title -> str": |
      Display label.
    "body -> dict[str, Any]": |
      Verbatim extra fields of the step (excluding name, title, and the
      extracted assistants key).
    "assistants -> dict[str, PipelineAssistant] | None": |
      The step's pipeline assistant declarations keyed by assistant
      name, in authored order. None when the source body carries no
      assistants key or an empty map (an empty map equals absence).
```

**Body — `StageStep`** — REPLACE symmetrically:

```yaml
"StageStep(name: str, title: str, depends_on: list[str] | None, body: dict[str, Any], assistants: dict[str, PipelineAssistant] | None = None)":
  location: stage_step.py
  annotations: |
    One entry of a stages-DSL body — a value in the body map, keyed by step id.

    `name`: step id (the map key)
    `title`: display label (the value of title inside the value)
    `depends_on`: list of predecessor step ids, or None when the field
                  is absent from the source value
    `body`: verbatim copy of every other field in the value (excluding
            title, depends_on, and the extracted assistants key)
    `assistants`: the step's pipeline assistant declarations — a map of
                  PipelineAssistant keyed by assistant name, in authored
                  order, or None when the source body carries no
                  assistants key or an empty map

    Carries `depends_on` from the source; the compiler passes it through
    unchanged when building FlowStage.

    The body field is intentionally typed as dict[str, Any]: the cell
    does not validate or know the schema of step fields. Build the data
    model with the standard library dataclasses module (NOT pydantic,
    per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - The body field excludes title, depends_on, and assistants (those
      are separate fields); name is the map key, also not part of the
      body; the assistants key is extracted from the source body at
      parse time
    - `depends_on` distinguishes None (absent) from an empty list
      (explicit empty)

    Constraints:
    - Do not validate the contents of `body` — pass it through verbatim
    - Do not normalize or rename keys in `body`
    - Do not validate `depends_on` references — afm's responsibility

  properties:
    "name -> str": |
      Step id.
    "title -> str": |
      Display label.
    "depends_on -> list[str] | None": |
      Predecessor step ids, or None when absent.
    "body -> dict[str, Any]": |
      Verbatim extra fields of the step (excluding title, depends_on,
      and the extracted assistants key).
    "assistants -> dict[str, PipelineAssistant] | None": |
      The step's pipeline assistant declarations keyed by assistant
      name, in authored order. None when the source body carries no
      assistants key or an empty map (an empty map equals absence).
```

**Body — `parse_dsl`** — signature unchanged. In the Algorithm, ADD
after step 4 (format detection / item building):

```yaml
    4a. For each parsed step item (both formats), when the item value
        carries an assistants key: a non-mapping value raises a
        structural error "non-mapping assistants in stage <name>; author
        the map form keyed by assistant name"; an empty map equals
        absence (assistants None); every entry value must be a mapping
        with the key set prompt, skills, when, gate — an unknown key
        raises a structural error naming the stage, the assistant, and
        the valid keys (the delivery keys agent, env, delegate are named
        in the message as workflow-file territory); every entry key
        matches [A-Za-z0-9._-] and is not "assistant"; prompt (when
        present) is a str; skills (when present) is a list[str]; when is
        required and one of start/checkpoints/finish/message; gate (when
        present) is strictly bool; a declaration resolving neither
        prompt nor skills raises a structural error naming the stage and
        the assistant. Build one PipelineAssistant per entry; the map is
        extracted into the step's typed assistants field and excluded
        from the verbatim body
```

In the Requirements of `parse_dsl`, ADD:

```yaml
    - The stage-body assistants grammar: a name-keyed mapping; an empty
      map equals absence; each entry value carries the key set prompt,
      skills, when, gate; when is required and one of the four values;
      gate is strictly bool; a declaration must resolve prompt or skills;
      the delivery keys agent, env, delegate are rejected with an error
      naming the stage and the assistant
    - The assistants map is extracted into the typed step field and
      excluded from the verbatim body; steps carry deep copies of the
      parsed declarations
```

**Body — `compile_flow`** — signature unchanged. REPLACE Algorithm step
4.10 with:

```yaml
    4.10. Resolve the assistant attachments of the working body (after
          skip removal and loop expansion) over the effective assistant
          namespace — the WorkflowAssistant catalog of the workflow
          document, the full inline declarations found in the
          stages-block entry maps, and the pipeline declarations carried
          by the working body's steps:
          - namespace uniqueness: a name carried by two sources
            (catalog, inline, pipeline declarations — a tool-delivered
            contribution included through the overlay) raises a
            structural error naming both authoring sites
          - the content check: EVERY workflow declaration of the
            effective namespace (the catalog plus every full inline
            declaration, override-style entries included) must resolve
            content — its effective prompt or its effective skills is
            not None; a declaration resolving neither raises a
            structural error naming the assistant and its authoring site.
            The check addresses workflow declarations only — a pipeline
            declaration resolves content at parse time, and a reference
            or extension carries no content of its own
          For each stage of the working body, assemble the effective
          attachment list — the stage's pipeline declarations first
          (authored order), then the stage's workflow entries (authored
          order):
          - a workflow entry naming a pipeline declaration of THIS
            stage: a {skip: true} entry vetoes that declaration — no
            attachment, no team member, no profile for the name; the
            stage still runs. Any other entry is an additive extension:
            effective when = the entry's authored when, else the
            declaration's; effective gate = the entry's authored gate,
            else the declaration's; effective prompt = the declaration's
            prompt joined to the entry's prompt with exactly one blank
            line when both are authored (pipeline text first; a
            single-sided text stands alone); effective skills = the
            declaration's list expanded with the entry's (declaration
            entries first, then entry entries, deduplicated by value
            preserving first occurrence); the entry's agent/env/delegate
            configure delivery (consumed by the engine configuration
            write)
          - a workflow entry naming no pipeline declaration of this
            stage: an entry naming no namespace member raises a
            structural error "unknown assistant reference in
            workflow.stages.NAME: <assistant>" — including a name
            pipeline-declared by ANOTHER stage (a pipeline declaration
            is visible only to its own stage's entry). A reference or
            full inline declaration carrying when None raises the
            structural error "when is required in
            workflow.stages.NAME.assistants.ASSISTANT" (the origin-aware
            when-required check: a when-less entry is legal only as an
            extension of a pipeline declaration of the same stage). A
            {skip: true} entry naming no pipeline declaration of this
            stage raises a structural error "skip targets a
            pipeline-declared assistant in
            workflow.stages.NAME.assistants.ASSISTANT" — the veto is
            exclusively the veto over what the pipeline ships; the name
            may be a namespace member (a catalog entry or an inline
            declaration), and not authoring the attachment is how those
            are governed. The
            same name twice in one stage's effective attachment list of
            a programmatic contribution raises a structural error naming
            the stage and the assistant
          - every assembled attachment from any source on a stage whose
            translated body carries script, or whose translated agents
            value is exactly ["planning"], raises a structural error
            naming the stage and the assistant — the check runs over the
            working body with or without a workflow document
          An emitted attachment whose resolved source is a workflow
          inline declaration authoring skills logs a WARNING naming the
          stage and the assistant — once per name (no engine channel;
          only catalog and pipeline declarations become team members);
          the warning replaces a silent drop and never adds an
          output-side key
```

In step 6 (Build FlowDocument), REPLACE the collaboration/team bullet
with:

```yaml
       - collaboration = a FlowCollaboration with mode "assistants" and
         max_depth = the depth of the workflow's WorkflowDelegation when
         it carries one, else None; team = one FlowTeamMember per catalog
         entry in authored order, then one FlowTeamMember per attached
         pipeline declaration in pipeline body stage order (each stage's
         declarations in authored order; loop-expanded copies collapse to
         their base stage's first occurrence; vetoed and stage-skipped
         declarations never join; a name joins exactly once) — id =
         title = the name, profile = goga-<name>, instruction = the
         effective prompt (the extended text) or the empty string,
         skills = the effective list or an empty list; place
         collaboration between memory and team, team between
         collaboration and stages
```

In the Requirements of `compile_flow`, ADD:

```yaml
    - Pipeline declarations attach with or without a workflow document
      (including workflow-free runs) and on every loop-expanded copy
    - A stage-level skip (workflow or CLI) removes the stage and its
      pipeline declarations together
    - Within one stage's compiled attachment list the pipeline
      declarations come first; the team list orders catalog members
      before pipeline-declared members (loop-expanded copies collapse to
      their base stage's first occurrence)
    - The extension prompt join uses exactly one blank line; the skills
      expansion deduplicates by value preserving first occurrence
    - A compilation without stage-declared assistants and without
      workflow attachments is byte-identical to the same compilation
      without this authoring surface
```

In the Constraints of `compile_flow`, ADD:

```yaml
    - Do not author engagement defaults — when is authored on every
      pipeline declaration; the compiled trigger is always written
    - Do not let the workflow extension mutate the parsed pipeline
      document — the merge is output-side only
    - Do not re-validate the workflow authoring vocabulary — the
      workflow parser owns it
    - Do not add a skills key to a stage attachment entry — the engine
      rejects it
    - Do not resolve agent names or compose commands for assistants
      here — the engine configuration write owns that
```

REMOVE the stage-body assistants prohibition from the stage-body
checking pass — the pipeline-file side is replaced by the authoring
surface; the embedded extend-stage body side of the check remains in
force (defensive re-check against programmatic contributions). The
sentence "An authored assistants key in a stage body (pipeline-file
stage OR embedded extend-stage body) raises a structural error ... use
assistants in workflow.stages" in step 5 is REPLACEd with:

```yaml
        An authored assistants key in an embedded extend-stage body
        raises a structural error "assistants key is forbidden in stage
        body; use assistants in workflow.stages" (same pass as the
        other authoring-key prohibitions — a defensive re-check: the
        workflow parser rejects it at parse time, a programmatic
        contribution reaches this cell unparsed)
```

and its Requirements counterpart ("An authored assistants key in a stage
body (pipeline-file stage or embedded extend-stage body) is a structural
error raised by `compile_flow`") is REPLACEd with:

```yaml
    - An authored assistants key in an embedded extend-stage body is a
      structural error raised by `compile_flow` (defensive re-check
      against programmatic contributions; the pipeline-file stage body
      side is replaced by the authoring surface of `parse_dsl`)
```

**Footer** — unchanged.

#### `.usages/` files

**File `goga/pipeline/compiler/.usages/parse-dsl.md`** — ADD a section
after "The header repeatable flag":

````md
## The stage-body `assistants` map

A stage body (both body formats) may declare the stage's helper
assistants — a name-keyed map where each entry ships with the pipeline:

```yaml
---
- name: review
  title: Review
  prompt: Implement the feature
  assistants:
    auditor:
      prompt: Audit the diff.
      skills: [code-audit]
      when: finish
      gate: true
```

| Value key | Type | Default | Note |
|-----------|------|---------|------|
| `prompt` | str | — | the helper's instruction |
| `skills` | list[str] | — | the helper's own skills (delivered via the team member) |
| `when` | `start` \| `checkpoints` \| `finish` \| `message` | **required** | when the helper engages |
| `gate` | bool | `false` | `true` — the verdict must pass before the stage finishes |

Every declaration resolves content — `prompt` or `skills` must be
authored. The delivery keys `agent`, `env`, `delegate` are NOT part of
this vocabulary: authoring any of them is a structural error naming the
stage and the assistant — delivery is configured per project in the
workflow-file (`stages.<stage>.assistants.<name>`).

The parsed steps carry the declarations in a typed `assistants` field
(`PhaseStep`/`StageStep`); the key is extracted from the verbatim body.
The declarations attach to their own stage on EVERY run — with a
workflow-file or without one — and every loop-expanded copy carries
them. Assistants are forbidden on a stage whose body carries `script`
and on a planning-only stage. An `assistants` map in a workflow
extend-entry body is a structural error there (workflow-side rule).
````

**File `goga/pipeline/compiler/.usages/collaboration-emission.md`** —
REPLACE the whole file with:

```md
# collaboration-emission — compiling collaboration into the afm flow-file

The document describes how the compiler handles collaboration from both
authoring surfaces — the workflow-file (catalog, delegation, stage
entries) and the pipeline-file stage-body declarations — which top-level
blocks are emitted, which entries the stages receive, and which defaults
are materialized. The audience is compiler consumers and authors of
either surface checking the expected output.

## The always-emitted collaboration block

`collaboration: {mode: assistants}` is emitted into EVERY compiled flow —
the one deliberate byte-level difference from a collaboration-free
compilation. `max_depth` rides in the block only when the workflow's
`delegation:` block authors a depth. The block sits between `memory` and
`team`; its key order is `mode, max_depth`.

## The team list

The `team:` list is emitted from TWO sources in a fixed order — the
workflow catalog in authored order first (one member per entry), then
the pipeline-declared members in pipeline body stage order (each stage's
declarations in authored order; loop-expanded copies collapse to their
base stage's first occurrence; vetoed and stage-skipped declarations
never join; a name joins exactly once). The list is omitted entirely
when both sources are empty. Every member materializes every key:

| Key | Value |
|-----|-------|
| `id` | the authored name — the identity the engine recognizes on resume |
| `title` | the authored name — the dashboard handle derives from it |
| `profile` | `goga-<name>` — the binding to the generated profile |
| `instruction` | the effective prompt; the empty string when none |
| `skills` | the effective list; an empty list when none |

## Stage attachments

A stage of the compiled body emits an `assistants` list when it carries
at least one effective attachment — the canonical slot after
`memory_use`. Loop-expanded copies each carry the original stage's
attachments; a skipped stage attaches nothing. Within one stage's
compiled list, the pipeline declarations come first (pipeline authored
order), then the workflow entries (workflow authored order) — the same
pipeline-first rule as the prompt append and the skills expansion.

Every entry materializes every key:

| Key | Value |
|-----|-------|
| `profile` | `goga-<name>` |
| `title` | the assistant name |
| `instruction` | the effective prompt; the empty string when none |
| `mode` | `required` when the effective `gate` is true; `advisory` otherwise |
| `trigger` | `one_shot` / `checkpoints` / `on_completion` / `pre_completion` / `on_message` — mapped from the effective `when` (a gated `finish` maps to `pre_completion`) |

`trigger` is always written explicitly — the engine's own default is
`one_shot` and is never relied upon (a pipeline declaration authors
`when` on every entry; a workflow reference or inline declaration
carries its own). The stage entry carries NO `skills` key: the afm
engine strict-parses `stages[].assistants` and rejects unknown fields
(`unknown field "skills"; use "profile"`). Skills reach the engine ONLY
through a `team` member entry — and the team draws from the catalog and
the pipeline declarations, so a declaration from either source delivers
its skills while a workflow inline declaration's authored skills have no
channel: the compiler logs a WARNING naming the stage and the assistant
(once per name) instead of dropping them silently.

## Origin-aware resolution

The effective assistant namespace spans the workflow catalog, every full
inline declaration, and the pipeline declarations of the compiled body —
one global uniqueness domain; a name collision between any two sources
(including a tool-delivered contribution through the overlay) is a
structural error naming both authoring sites.

A workflow entry addressing a name declared by its own stage's
pipeline-file body resolves by origin:

- `{skip: true}` — the veto: no attachment, no team member, no generated
  profile for that name; the stage itself still runs.
- any other entry — the extension: `when`/`gate` override the pipeline
  values (omitted keys inherit; an explicit `gate: false` deliberately
  downgrades), `agent`/`env`/`delegate` configure delivery, `prompt`
  appends to the pipeline text (pipeline text first, one blank line,
  then the workflow text), `skills` expands the pipeline list (pipeline
  entries first, then workflow entries, deduplicated by value).

An entry naming no pipeline declaration of that stage keeps the existing
semantics — a catalog reference or a full inline declaration — and
requires its own `when`; a when-less entry is legal only as an extension
of a pipeline declaration of the same stage. A pipeline declaration is
visible only to its own stage's entry: addressing it from another stage
is an unknown-assistant-reference error.

## Compilation checks

Raised as structural errors naming the location:

- a name collision across the effective namespace (catalog, inline,
  pipeline declarations, overlay contributions)
- an attachment naming no namespace member — unknown assistant reference
  (including a pipeline-declared name addressed from another stage)
- a missing `when` on an entry naming no pipeline declaration of the
  stage (a reference or a full inline declaration)
- the same assistant name twice in one stage's effective attachment list
  of a programmatic contribution
- an attachment from any source on a stage whose translated body carries
  `script`
- an attachment from any source on a stage whose translated agents value
  is exactly `["planning"]`
- a workflow declaration (catalog or inline) resolving no effective
  prompt and no effective skills

The checks run over the working body after skip removal and loop
expansion — the attachments of a removed stage never count — with or
without a workflow document (pipeline declarations attach on every run).

## Invariants

- a collaboration-free compilation (no pipeline declarations, no
  workflow collaboration authoring) compiles byte-identically except the
  always-present collaboration mode key
- `PipelineDocument` is the exact mirror of the source pipeline-file —
  the collaboration block, the team list, and the stage attachments are
  output-side only; the workflow extension never mutates the parsed
  representation
- the `compile_flow`/`serialize_flow` signatures are unaffected by
  collaboration authoring
- the compiled flow is the single source of truth for the engine
  configuration: every profile id the flow references (`goga-<name>` of
  each member and each attachment) is materialized there exactly — no
  dead profiles remain for attachments removed by a veto or a stage skip

## Anti-patterns

- Do not author delivery keys in a pipeline declaration — `agent`, `env`,
  `delegate` belong to the workflow-file entry addressing the name.
- Do not expect a workflow-only attachment to inherit engagement — a
  reference or inline declaration carries its own `when`; only a
  pipeline declaration's extension may omit it.
- Do not re-check the authoring vocabulary on the compiler side — the
  parsers rejected non-conforming authoring before compilation.
- Do not rely on engine defaults for mode/trigger/instruction — every
  entry materializes them.
- Do not add a `skills` key to a stage attachment entry — the engine
  rejects unknown fields there; skills travel on the team member (catalog
  and pipeline declarations only; an inline declaration's skills warn,
  never emit).
```

**File `goga/pipeline/compiler/.usages/compile-flow.md`** — REPLACE the
section "Collaboration emission" with:

```md
## Collaboration emission

Collaboration compiles from both authoring surfaces — the workflow's
collaboration instructions and the pipeline-file stage-body
declarations — into three output surfaces:

- the top-level `collaboration` block is emitted into EVERY compiled flow
  — `mode: assistants` always, `max_depth` only when the workflow's
  `delegation:` block authors a depth; it sits between `memory` and
  `team`
- the `team` list is emitted from the workflow catalog in authored order,
  then the pipeline-declared members in pipeline body stage order
  (loop-expanded copies collapse to their base stage's first occurrence;
  vetoed and stage-skipped declarations never join) — omitted entirely
  when both sources are empty
- a stage emits its `assistants` list when it carries at least one
  effective attachment — the canonical slot after `memory_use`; within
  the list, pipeline declarations first (authored order), then workflow
  entries (authored order); uniform across every loop-expanded copy; a
  skipped stage attaches nothing

Compilation checks (structural errors naming the location): a name
collision across the effective namespace (catalog, inline, pipeline
declarations, overlay contributions); an attachment naming no member of
the namespace (a pipeline-declared name is visible only to its own
stage's entry); a missing `when` on an entry naming no pipeline
declaration of the stage; the same assistant name twice in one stage's
list; an attachment from any source on a stage whose translated body
carries `script`; an attachment from any source on a planning-only stage
(translated agents exactly `["planning"]`); a workflow declaration
resolving no effective prompt and no skills. The checks run over the
working body after skip removal and loop expansion, with or without a
workflow document. A workflow entry addressing a pipeline-declared name
of its own stage is a `{skip: true}` veto or an additive extension
(when/gate override with inheritance, prompt append with one blank line,
skills expand with deduplication, agent/env/delegate delivery
configuration).
```

---

### Cell 3 — `goga/pipeline/hooks` (MODIFIED)

#### CODEMANIFEST diff — `goga/pipeline/hooks/CODEMANIFEST`

**Header.** Imports/Usages unchanged. Annotations — in the overlay
paragraph (the one beginning "The overlay merge preserves the
collaboration instructions of the workflow model"), REPLACE the closing
clause of the per-stage-append sentences ("and an appended inline
declaration whose name is already present anywhere in the merged
assistant namespace dropped silently the same way") with:

```yaml
  and an appended entry shaped as a declaration (any key beyond gate,
  when, skip) whose name is already present anywhere in the merged
  workflow-side assistant namespace is dropped silently the same way —
  the append rule is form-blind. An appended stage-assistant entry may
  carry any authored form — a reference, a full inline declaration, a
  when-less extension, or a {skip: true} veto; a skip entry and a
  gate/when-only entry append like any other: the merge never resolves a
  name beyond the workflow document — an entry may address a name the
  workflow-file does not declare (a pipeline-file declaration, an
  extension, or a veto of one), and the entry's origin classification
  and the effective-namespace uniqueness (the pipeline declarations
  included) are compilation checks raised where both documents meet.
```

**Body — `merge_workflow_overlay`** — signature unchanged. In the
Algorithm, REPLACE step 5.1 with:

```yaml
    5.1. stage assistants: for each stage name the authored map is the
        ground — the authored entries first, in authored order; the
        contributing entries append in enumeration order, an entry whose
        name is already present on the stage dropped silently, and an
        appended entry shaped as a declaration (any key beyond gate,
        when, skip) whose name is already present anywhere in the merged
        workflow-side assistant namespace dropped silently the same way;
        a skip entry and a gate/when-only entry append like every other
        entry (their origin classification belongs to compilation); a
        stage with no authored entry takes the appended contributing
        entries the same way
```

In the Requirements, ADD:

```yaml
    - The merge is form-blind over the stage-assistant entry forms: a
      skip veto, a when-less extension, a reference, and a full inline
      declaration all ride the append rule unchanged; the merged
      workflow document never resolves a name beyond the workflow-file —
      entries addressing pipeline-file declarations pass through, and
      every collision with them fails at compilation with the
      effective-namespace errors
```

In the Constraints, ADD:

```yaml
    - Do not classify an appended entry's origin (veto, extension,
      reference, declaration) and do not resolve names against any
      pipeline-file — the overlay is pipeline-blind by design
```

**Footer** — unchanged.

#### `.usages/` files

**File `goga/pipeline/hooks/.usages/checkpoints.md`** — in the bullet
beginning "A tool contributes one declarative `WorkflowDocument`",
REPLACE the closing sentence ("; the delegation block is whole, and
stage assistant maps append with name deduplication.") with:

```md
; the delegation block is whole, and stage assistant maps append with
  name deduplication — an appended entry may carry any authored form (a
  reference, a full inline declaration, a when-less extension, a `{skip:
  true}` veto): entries addressing names the workflow-file does not
  declare (pipeline-file declarations) pass through undistorted, and the
  origin classification plus the effective-namespace uniqueness are
  compilation checks.
```

---

### Cell 4 — `goga/pipeline` (MODIFIED)

#### CODEMANIFEST diff — `goga/pipeline/CODEMANIFEST`

**Header.** In the Imports entry `From: goga/pipeline/compiler`, ADD the
type `PipelineDocument` to the Types list. Usages unchanged.
Annotations — REPLACE the "Collaboration delivery:" paragraph with:

```yaml
  Collaboration delivery: the afm configuration write materializes the
  engine's collaboration plumbing from the artifacts the run already
  produces — the compiled flow, the effective workflow, and the parsed
  pipeline document. The section writes on EVERY launch, always headed
  by collaboration.runtime_context: wrapper and
  collaboration.hide_attach_helpers: true — the static
  execution-context decision (every command goga hands the engine,
  client and generated profiles alike, is an as-claude wrapper or a
  closure over one) and the static dashboard decision (helpers join a
  goga-managed run only through the authored plumbing — the
  workflow-file instructions and the pipeline-file stage declarations —
  never through dynamic dashboard attachment). The compiled flow is the
  single source of truth: the helper profiles are materialized exactly
  for the generated profile ids the flow references, so the two
  artifacts cannot diverge and no dead profile remains for an attachment
  removed by an assistant veto or a stage skip; without the artifacts
  the section stays the bare static head. Every command the write
  produces — the client wrapper and each profile command, wrapper or
  closure alike — is labeled in the top-level command_names map with the
  bare agent id of its underlying as-claude wrapper, so the dashboard
  never falls back to the file base name; the map is written only when
  at least one labeled command exists. A generated profile is exactly
  {title, command, delegate}: the title from the assistant name, the
  delegate permission from the delivery source, and the command resolved
  the stage-agent way — the source's agent, else the effective global
  pipeline agent; a name that resolves to nothing fails the launch with
  a pre-run error naming the assistant and its authoring site (the
  catalog, the stage whose attachment declares it, or the pipeline stage
  whose body declares it). A pipeline-declared assistant carries no
  delivery fields of its own: its delivery configuration comes from the
  workflow extension entry addressing its name (agent, env, delegate),
  and without one it launches under the effective global agent. An
  assistant carrying an env instruction is delivered through a generated
  sh closure whose path becomes the profile's command (a profile carries
  its own command and inherits none); closures are regenerated on every
  launch, so the authored configuration survives the per-launch rewrite
  by living in the workflow-file. The whole-run task budget is written
  as collaboration.limits.max_tasks only when the workflow carries a
  delegation block — the materialized value, 50 when the block omits it.
  The goga- profile prefix is the intended override channel: a
  user-authored same-named profile in the project layer deliberately
  replaces goga's plumbing, and the project-layer engine configuration
  is user territory goga never touches. goga neither reads nor writes
  the collaboration kill-switch — an environment that disables
  collaboration gets engine warnings and skipped helpers, and the run
  proceeds.
```

**Body — `write_afm_config`** — REPLACE the signature line with:

```yaml
"write_afm_config(agent: str | None, flow: FlowDocument | None = None, workflow: WorkflowDocument | None = None, pipeline: PipelineDocument | None = None) -> config_path: Path":
```

ADD the parameter description after the `workflow` parameter
description:

```yaml
    `pipeline`: the parsed pipeline document (a `PipelineDocument`) —
                the carrier of the pipeline-file stage-body assistant
                declarations. Together with `flow` and `workflow` it
                completes the delivery resolution: a pipeline-declared
                name resolves its delivery fields from the workflow
                extension entry addressing it, and its authoring site
                (the pipeline stage whose body declares it) is named by
                strict pre-run errors. None when no pipeline document is
                at hand — the section head still writes and no
                pipeline-declared profile resolves
```

REPLACE Algorithm step 3.2 (declaration lookup) with:

```yaml
       2. For each referenced id, locate the assistant's delivery source
          by name across the effective namespace — the workflow's
          assistant declarations (the catalog plus every full inline
          declaration of the stages block) and the pipeline declarations
          the `pipeline` document carries:
          - a workflow catalog or inline declaration supplies agent,
            delegate, and env as authored
          - a pipeline declaration carries no delivery fields: the
            workflow entry addressing the name (its extension entry)
            supplies agent, delegate, and env; the pipeline stage whose
            body declares the name is the authoring site
          - a name resolving to no declaration is a caller-side
            inconsistency (compilation validated the flow) — one strict
            pre-run error naming the assistant
```

In Algorithm step 3.3 (command resolution), EXTEND the failure clause
to:

```yaml
          ...no agent resolves at all — one strict pre-run error naming
          the assistant and its authoring site (the catalog, the stage
          whose attachment declares it, or the pipeline stage whose body
          declares it), raised before the file is written; the effective
          delegate materializes False when None
```

In the Requirements, ADD:

```yaml
    - A pipeline-declared assistant's profile resolves through the
      workflow extension entry's delivery fields, else the effective
      global agent — the declaration itself contributes no command, no
      env, and no delegate; the goga-<name> id scheme and the {title,
      command, delegate} profile shape are unchanged
    - The profiles are materialized exactly for the ids the compiled
      flow references — no more, no less; an attachment removed by an
      assistant veto or a stage skip leaves no profile behind
```

In the Constraints, ADD:

```yaml
    - Do not resolve a pipeline-declared name's delivery from the
      pipeline document — it carries content and engagement only;
      delivery fields come from the workflow entry addressing the name
      or the global fallback
```

**Body — `run_pipeline`** — in the Algorithm step that calls
`write_afm_config`, UPDATE to pass the parsed pipeline document:

```yaml
       ...call `write_afm_config` with the compiled flow document, the
       effective workflow document, and the parsed pipeline document
       (the compile step's returned PipelineDocument — the carrier of
       the pipeline-file stage-body assistant declarations) as the
       `pipeline` parameter
```

**Body — `describe_pipeline`** — unchanged (the card composes through
the same compilation machine; pipeline attachments appear in the
post-workflow composition without a contract change).

**Footer** — unchanged.

#### `.usages/` files

**File `goga/pipeline/.usages/collaboration-delivery.md`** — REPLACE the
whole file with:

```md
# collaboration-delivery — delivering assistants into the afm configuration

How authored collaboration reaches the engine on every launch: the
generated helper profiles, the env closures behind their commands, and
the whole-run task budget. Target audience: contributors reasoning about
the delivered artifacts and authors of either surface (workflow-file or
pipeline-file) checking why their authoring survives every launch.

## The three artifacts

The engine consumes collaboration through artifacts goga already
produces:

- the **compiled flow-file** — `collaboration: {mode: assistants}`,
  `max_depth` when a depth is authored, the `team` list, and the stage
  `assistants` entries;
- the **effective workflow** — the delivery configuration of every
  assistant (the catalog declarations, the inline declarations, and the
  extension entries addressing pipeline-declared names);
- the **parsed pipeline document** — the stage-body assistant
  declarations (content and engagement; no delivery fields).

The engine configuration written before every launch carries the static
section head (`collaboration.runtime_context: wrapper` and
`collaboration.hide_attach_helpers: true`), the generated
`collaboration.profiles` and `collaboration.limits.max_tasks`, plus the
top-level `command_names` labels of the generated commands.

The compiled flow is the single source of truth: a profile is
materialized exactly for the ids the flow references (`goga-<name>` of
every team member and every stage attachment). The artifacts cannot
diverge, and no dead profile remains for an attachment removed by an
assistant veto or a stage skip.

## The static head and the command labels

The `collaboration` section always writes, even without collaboration
authoring: `runtime_context: wrapper` (every command goga hands the
engine is an as-claude wrapper or a closure over one) and
`hide_attach_helpers: true` — the run's dynamic attach-helpers dashboard
entry point stays hidden, so helpers join a goga-managed run only
through the authored plumbing (the workflow-file instructions and the
pipeline-file stage declarations).

Every command the write produces — the resolved client wrapper and each
profile command, wrapper or closure alike — is labeled in the top-level
`command_names` map with the bare agent id of its underlying
`<agent>-as-claude.sh` wrapper (`/home/goga/bin/claude-as-claude.sh` →
`claude`), so the dashboard never falls back to the file base name. The
map writes only when at least one labeled command exists.

## Generated profiles

| Key | Value |
|-----|-------|
| `title` | the assistant's authored name |
| `command` | the resolved launch command (below) |
| `delegate` | the delivery source's permission, false by default |

Nothing else is written into a generated profile. The profile id is
`goga-<name>`; the `goga-` prefix is the intended override channel — a
user-authored same-named profile in the project layer (`.afm/config.yaml`)
deliberately replaces goga's plumbing, and that file is user territory
goga never touches.

## Command resolution

The profile's command resolves exactly like a stage agent command, over
the delivery source of the name:

- a **workflow catalog or inline declaration** — its authored `agent`;
- a **pipeline-file stage declaration** — no delivery fields of its own:
  the `agent`/`env`/`delegate` of the workflow extension entry
  addressing the name (`stages.<stage>.assistants.<name>`), else the
  effective global agent (the workflow's global `agent` when the
  effective workflow carries one, else `pipeline.agent`);
- else the effective global agent for every source — the same ladder as
  stage agents;
- else the launch fails strictly before the run with an error naming
  the assistant and its authoring site (the catalog, the stage whose
  attachment declares it, or the pipeline stage whose body declares
  it).

An assistant carrying an `env` instruction is delivered through a
generated sh closure: the closure exports the assistant's env values and
execs the resolved wrapper, and the closure path becomes the profile's
command — a profile carries its own command and inherits none. Closures
are regenerated on every launch in a container-local temp directory, so
the authored configuration survives the per-launch configuration rewrite
by living in the authoring files. Env keys must be legal environment
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
- goga resolves no delivery from a pipeline declaration — delivery
  fields are workflow territory; a pipeline-declared assistant launches
  under its extension entry's configuration or the global agent.
```

**File `goga/pipeline/.usages/run-pipeline.md`** — two replacements:

1. In "afm configuration", extend the opening sentence to:

```md
Before the launch the coordination writes the whole afm configuration
file via `write_afm_config` — passing the parsed pipeline document
alongside the compiled flow and the effective workflow (the delivery
resolution of pipeline-declared assistants): the client command resolved
from the effective global agent ...
```

2. REPLACE the closing sentences of the `collaboration` paragraph
   ("The compiled flow is the single source of truth ... become the
   profile commands.") with:

```md
The compiled flow is the single source of truth for the profile set;
the delivery sources resolve across the effective namespace — workflow
catalog and inline declarations supply their own agent/env/delegate, a
pipeline-file stage declaration takes them from the workflow extension
entry addressing its name (else the effective global agent), with the
authoring site named by any strict pre-run error; assistant env travels
through regenerated closures whose paths become the profile commands.
```

---

### Documentation (rides with the cells)

- `docs/features/pipelines/pipeline-file.md` — ADD the stage-body
  `assistants` authoring surface (mirror of the parse-dsl.md section:
  vocabulary table, delivery-keys rule, immediate attachment, no-workflow
  runs, loop copies, prohibitions).
- `docs/features/pipelines/workflows.md` — ADD the governance surface for
  pipeline-shipped assistants (mirror of the assistants.md
  "Governing pipeline-shipped assistants" section: skip veto, extension
  table, visibility).

---

## Dependency Map

```
  goga/pipeline/workflow  (modified; leaf)
        │
        │  Imports: WorkflowDocument, WorkflowStage, WorkflowAssistant,
        │           WorkflowExtendStage, WorkflowGates, ...
        │           usages: parse-workflow, memory, assistants, gates
        ├──────────────────────────────────┐
        ▼                                  ▼
  goga/pipeline/compiler              goga/pipeline/hooks
  (modified; core)                    (modified; minimal)
        │                                  │
        │  Imports: compile_flow,          │  Imports: PipelineHooks,
        │  parse_dsl, StructuralError,     │  WorkflowOverlay, ...
        │  FlowDocument, FlowStage,        │
        │  FlowTeamMember,                 │
        │  FlowAssistant, ...              │
        │  + PipelineDocument (NEW in      │
        │    this plan)                    │
        ├──────────────────┬───────────────┘
        ▼                  ▼
      goga/pipeline  (modified; delivery + run coordination)
```

No cycles. The only dependency-graph change: `PipelineDocument` joins
the Types imported by `goga/pipeline` from `goga/pipeline/compiler`
(existing direction).

## Verification Checklist

After implementing each artifact, run `goga lint` on the touched cells
and the validation commands per `.goga/usages/conventions.md`
(`pytest tests/ -x`, `ruff check goga/pipeline/`).

**Cell 1 — workflow:**
- parse_workflow accepts a when-less stage entry and a `{skip: true}`
  entry; a lone `skip: false`, an empty entry, and skip mixed with any
  key are structural errors; duplicate-name and when-required checks no
  longer fire at parse time.
- Absence vs authored values: `gate`/`when`/`skip` None-defaults are
  distinguishable; `skills []`/`env {}` stay explicit overrides.
- Catalog grammar unchanged (gate/when/skip unknown in the catalog).

**Cell 2 — compiler:**
- `parse_dsl` builds `PipelineAssistant` for both body formats; the map
  is extracted (body verbatim without it); delivery keys, unknown keys,
  bad names, missing when, non-bool gate, content-free declarations are
  structural errors naming stage and assistant.
- `compile_flow` with `workflow=None` and a declared assistant: the
  compiled flow carries the stage attachment entry (all five fields
  materialized), the team member with the declared skills (SC1).
- `{skip: true}`: no attachment entry, no team member, no profile id for
  the name; the stage still runs (SC2).
- Extension: overridden when/gate, appended prompt (one blank line,
  pipeline first), expanded deduplicated skills, delivery fields carried
  (SC3); attachments pipeline-first; team catalog-first with loop
  collapse.
- Namespace collisions (catalog-vs-pipeline, cross-stage pipeline
  duplicates, overlay contributions) and when-required for non-pipeline
  names raise compile-time structural errors naming the sites (SC4).
- An assistant-free pipeline and a workflow-only collaboration document
  compile byte-identically (SC5); inline-declaration skills keep the
  WARNING (SC6).
- Prohibitions (script-carrying, planning-only) fire for pipeline
  declarations without a workflow document.

**Cell 3 — hooks:**
- Overlay contributions carrying skip/when-less entries for pipeline
  names pass through the merge undistorted; no name resolution beyond
  the workflow document; collisions surface only at compilation.

**Cell 4 — pipeline:**
- `write_afm_config` resolves a pipeline-declared name's delivery from
  the workflow extension entry, else the global agent; an unresolvable
  agent names the assistant and the pipeline stage; profile shape and
  `goga-<name>` scheme unchanged.
- `run_pipeline` threads the `PipelineDocument` into the write; the card
  reflects pipeline attachments with no contract change.
- Docs pages for both surfaces updated.
