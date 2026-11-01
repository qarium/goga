# Architecture plan — recycle-pipeline

Repeating pipeline cycles (`repeatable` + workflow `repeat`) and map-form assistants authoring,
riding the existing pipeline compile path. Decision source: `.goga/history/2026/recycle-pipeline/
adr.md` (normative). All four cells are **modified**; no cell is created.

## Topic

Short name: **recycle-pipeline** · Plan: `.goga/history/2026/recycle-pipeline/arch.md`

## Implementation Order

| # | Cell | Action | Reason for the position |
|---|---|---|---|
| 1 | `goga/pipeline/workflow` | modify | Leaf — no Imports; owns both authoring grammars (`repeat` block, map-form assistants). Everything downstream consumes its models, so its contract lands first. |
| 2 | `goga/pipeline/compiler` | modify | Imports `workflow` (gains `WorkflowRepeat`); owns the `repeatable` header flag, the always-emit rule, the cross-check, and the emission position. |
| 3 | `goga/pipeline/hooks` | modify | Imports `workflow`; carries `repeat` through the overlay rebuild (authored-wins) and counts it in the empty-contribution rule. |
| 4 | `goga/pipeline` | modify | Root — imports compiler/workflow/hooks; carries `repeat` verbatim through the `--skip` rebuild. |

---

## Artifacts

### Cell 1 — `goga/pipeline/workflow` (MODIFIED)

#### CODEMANIFEST diff

**Header — `Usages`:** unchanged (`convention`, `jinja2`).

**Header — `Annotations`:**

1. REPLACE the first paragraph's key enumeration (only the list changes):

```
validates its structure (known top-level keys prompt / stages / extend /
memory / profile / build / assistants / delegation / repeat, field types,
loop counts, extend-entry positioning, and the inline agent/loop fields of
an extend-entry)
```

2. ADD a `repeat` paragraph immediately after the `memory` paragraph:

```
repeat is a declarative run-cycle tuning block — an optional top-level map
carrying the optional integer keys max_cycles and keep_runs in the engine's
vocabulary, verbatim. This cell validates the block structurally: the value
must be a mapping (a scalar value, including a boolean, is a structural
error), every key must be max_cycles or keep_runs, every value must be an
integer (a boolean is not an integer) and not negative. The block carries
authored values only — this cell materializes no defaults; an empty block
equals absence. A workflow consisting of the block alone is valid. This cell
performs NO cycle logic — it counts nothing, decides no stop condition, and
prunes nothing; the consumer compiles the block and the engine owns every
cycle semantic. The import graph stays one-directional.
```

3. REPLACE the `assistants is a declarative collaboration instruction set …`
   paragraph with:

```
assistants is a declarative collaboration instruction set — a top-level
assistants catalog, a top-level delegation block, and a per-stage assistants
attachment map. Both assistants surfaces are name-keyed maps: the catalog is
keyed by assistant name and every stage attachment is keyed by assistant
name. This cell validates the three authoring surfaces structurally (the
name-keyed entry maps, field types, the required when of every stage
attachment, unknown keys, the assistant-name grammar, name uniqueness across
the catalog and every inline declaration, assistants forbidden inside
extend-entries) and extracts them into the document model with materialized
defaults (delegate false, gate false, max_tasks 50 whenever the delegation
block is authored). This cell performs NO collaboration logic — it resolves
no attachment references, derives no profile ids, maps no gate or engagement
values, and emits no team or stage-assistant entries; the consumers consume
the extracted values. The import graph stays one-directional.
```

4. REPLACE the `One entry model serves every authoring form …` paragraph
   with:

```
One entry model serves every authoring form: a catalog entry (the
declaration fields under the assistant's name, no gate/when), a full inline
declaration on a stage (the catalog field set plus gate/when), and a
reference (a value carrying only gate/when). An attachment value that
carries any key beyond gate/when is a full inline declaration and requires
at least one of prompt or skills; a value carrying only gate/when is a
reference and requires nothing further — the reference resolves against the
assistant names of the same document at compilation. The assistant name is
the map key: an inner name key of an entry value is an unknown key, and a
list value or a string value on either surface is a structural error naming
the map form. Every stage attachment states when the assistant engages — one
of start, checkpoints, finish; a missing when is a structural error. gate is
optional on an attachment and materializes false; gate and when are unknown
keys of the catalog.
```

**Body — ADD the type declaration** (inserted between `WorkflowDelegation`
and `WorkflowDocument`):

```yaml
"WorkflowRepeat(max_cycles: int | None = None, keep_runs: int | None = None)":
  location: workflow_repeat.py
  annotations: |
    Data model of the workflow run-cycle tuning block — the authored bounds
    of a repeating run. Constructed by `parse_workflow` from the optional
    top-level block; carried inside `WorkflowDocument`.

    `max_cycles`: the maximum number of complete run cycles, or None when
                  not authored
    `keep_runs`: the number of recent cycle run-directories to retain, or
                 None when not authored

    Build the data model with the standard library dataclasses module
    (NOT pydantic, per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - Both fields default to None — the model carries authored values only
      and materializes no defaults; an authored zero is a value, not an
      omission, and stays distinguishable from None
    - Field order is fixed: max_cycles, keep_runs

    Constraints:
    - Do not validate types or bounds here — `parse_workflow` enforces them
      during parsing
    - Do not interpret the bounds — cycle semantics belong to the consumer
      and the engine
  properties:
    "max_cycles -> int | None": |
      The maximum number of complete run cycles, or None when not authored.
    "keep_runs -> int | None": |
      The number of recent cycle run-directories to retain, or None when
      not authored.
```

**Body — MODIFY `WorkflowDocument`:**

- REPLACE the signature with:

```yaml
"WorkflowDocument(prompt: str | None = None, stages: dict[str, WorkflowStage] | None = None, extend: dict[str, WorkflowExtendStage] | None = None, memory: WorkflowMemory | None = None, profile: str | None = None, build: WorkflowBuild | None = None, assistants: dict[str, WorkflowAssistant] | None = None, delegation: WorkflowDelegation | None = None, repeat: WorkflowRepeat | None = None)":
```

- ADD the parameter line (after the `delegation` line):

```
    `repeat`: the run-cycle tuning block, or None when the workflow-file
              carries no block or authors an empty block. A workflow
              consisting of the block alone is valid
```

- REPLACE the two Requirements bullets that name the field order and the
  empty-workflow rule with:

```
    - memory defaults to None; profile defaults to None; build defaults to
      None; delegation defaults to None; repeat defaults to None; field
      order is fixed: prompt, stages, extend, memory, profile, build,
      assistants, delegation, repeat
    - The empty-workflow rule counts the block: a workflow is empty only when
      prompt is None AND stages is empty AND extend is empty AND memory is
      None AND build is None AND assistants is empty AND delegation is None
      AND repeat is None — `profile` never counts (activation is not
      content: a profile-only workflow is still empty)
```

- REPLACE the Requirements bullet "A workflow-file with none of a top-level
  `prompt`, … the delegation block is rejected …" so its enumeration ends
  "… the assistants block, the delegation block, or the repeat block is
  rejected by `parse_workflow` with a structural error before this dataclass
  is built — at least one must be present".
- ADD the property (after `delegation`):

```yaml
    "repeat -> WorkflowRepeat | None": |
      The run-cycle tuning block, or None when the workflow-file carries no
      block or authors an empty block.
```

**Body — MODIFY `WorkflowStage`:**

- REPLACE the signature with (the `assistants` parameter type changes,
  `list` → `dict`; everything else is unchanged):

```yaml
"WorkflowStage(agent: str | None = None, env: dict[str, str] | None = None, prompt: str | None = None, loop: int | None = None, skills: list[str] | None = None, skip: bool = False, approve: str | None = None, manual: bool | None = None, notes: dict[str, str] | None = None, reflect: WorkflowReflect | None = None, memory: bool | None = None, assistants: dict[str, WorkflowAssistant] | None = None)":
```

- REPLACE the `assistants` parameter annotation with:

```
    `assistants`: the stage's assistant attachments — a map of
                  `WorkflowAssistant` keyed by assistant name, in authored
                  order. None when not specified (an empty map equals
                  absence — normalized by `parse_workflow`). Declarative —
                  extracted here, consumed by the compiler to emit the
                  stage's assistants entries
```

- REPLACE the `assistants` property with:

```yaml
    "assistants -> dict[str, WorkflowAssistant] | None": |
      The stage's assistant attachments keyed by assistant name, in authored
      order. None when not specified (an empty map equals absence).
```

**Body — MODIFY `WorkflowAssistant`:**

- REPLACE the `name` parameter annotation with:

```
    `name`: the assistant name — the map key of the entry on both
             authoring surfaces; matches [A-Za-z0-9._-]; "assistant" is
             rejected; unique across the catalog and every inline
             declaration of one workflow-file
```

- REPLACE the `when` parameter annotation with:

```
    `when`: when the assistant engages — one of "start", "checkpoints",
            "finish". Authored on every stage attachment (a missing when is
            a structural error); unknown in the catalog. The model default
            serves the construction paths that carry no attachment
            authoring
```

- REPLACE the `when` property with:

```yaml
    "when -> str": |
      When the assistant engages — start, checkpoints, or finish; authored
      on every stage attachment, unknown in the catalog.
```

- REPLACE the Requirements bullet "`name` is required (no default); every
  other field defaults to its materialized value; field order is fixed:
  name, prompt, skills, agent, delegate, env, gate, when" with:

```
    - `name` is required (no default); every other field defaults to its
      materialized value — except `when`, whose model default serves the
      construction paths that carry no attachment authoring (per the `when`
      parameter annotation); field order is fixed: name, prompt, skills,
      agent, delegate, env, gate, when
```

**Body — MODIFY `parse_workflow`:**

- Step 4: REPLACE the `assistants` bullet with

```
       - assistants: if present, must be a dict; otherwise raise a
         structural error "non-mapping assistants block in workflow; author
         the map form keyed by assistant name"
```

  and ADD after the `delegation` bullet:

```
       - repeat: if present, must be a dict; otherwise raise a structural
         error "non-mapping repeat block in workflow"
```

- Step 5: REPLACE the valid-keys list with `prompt, stages, extend, memory,
  profile, build, assistants, delegation, repeat`.
- Step 6.1.14: REPLACE the closing phrase "an empty assistants list yields
  None" with "an empty assistants map yields None" (the map-form grammar).
- REPLACE step 6.5 with:

```
    6.5. For the assistants catalog (when present): the block must be a
        mapping keyed by assistant name (otherwise "non-mapping assistants
        block in workflow; author the map form keyed by assistant name");
        each entry value must be a mapping (otherwise "non-mapping
        assistant entry in workflow.assistants.NAME"). Entry value key set:
        prompt, skills, agent, delegate, env — an unknown key (including
        name, gate, and when) raises "unknown key in
        workflow.assistants.NAME: KEY; valid keys: prompt, skills, agent,
        delegate, env". prompt and agent (when present) are str; skills
        (when present) is a list[str]; delegate (when present) is a bool;
        env (when present) is a str→str map with an empty map equal to
        absence. At least one of prompt or skills must be present —
        otherwise "assistant NAME requires at least one of prompt or
        skills". Every entry key must match [A-Za-z0-9._-] and must not be
        "assistant" ("assistant name is reserved"); a key repeated across
        the catalog and any inline declaration raises "duplicate assistant
        name: NAME". Build a `WorkflowAssistant` per entry with the key as
        name and delegate materialized false
```

- REPLACE step 6.7 with:

```
    6.7. For each stage entry carrying an assistants key: the value must be
        a mapping keyed by assistant name (otherwise "non-mapping
        assistants in workflow.stages.NAME; author the map form keyed by
        assistant name"); an empty map equals absence (None). Each entry
        value must be a mapping (otherwise "non-mapping assistant
        attachment in workflow.stages.NAME.ASSISTANT"). Every entry states
        when — a missing when raises "when is required in
        workflow.stages.NAME.assistants.ASSISTANT"; when must be one of
        start/checkpoints/finish. gate (when present) must be a bool. A
        value whose keys are within {gate, when} is a reference; a value
        carrying any further key is a full inline declaration (the catalog
        field set plus gate and when; at least one of prompt or skills).
        The name rules of 6.5 apply to every entry key; the duplicate-name
        rule counts an inline declaration against the catalog and every
        other inline declaration. Build a `WorkflowAssistant` per entry
        with the key as name
```

- ADD step 6.9 after step 6.8:

```
    6.9. For the repeat block (when present): the block must be a dict
        (otherwise "non-mapping repeat block in workflow"); the key set is
        max_cycles, keep_runs — an unknown key raises "unknown key in
        workflow.repeat: KEY; valid keys: max_cycles, keep_runs". Each
        value (when present) must be an int and not negative — otherwise
        raise "non-int value in workflow.repeat.max_cycles" / "non-int
        value in workflow.repeat.keep_runs" (non-int, a boolean included)
        or "max_cycles must be >= 0 in workflow.repeat" / "keep_runs must
        be >= 0 in workflow.repeat" (negative). Build a `WorkflowRepeat`
        from the authored values only; an empty block equals absence —
        carry repeat=None
```

- REPLACE step 7 with:

```
    7. If prompt is None AND stages is empty (no entries) AND extend is
       empty (no entries) AND memory is None AND build is None AND
       assistants is empty AND delegation is None AND repeat is None
       — raise a structural error "empty workflow — provide at least
       prompt, one stage, one extend entry, the memory block, the build
       block, the assistants block, the delegation block, or the repeat
       block" (profile never rescues a workflow from emptiness — activation
       is not content)
```

- REPLACE step 8 with:

```
    8. Return `WorkflowDocument` from the parsed prompt, stages, extend,
       memory, profile, build, assistants, delegation, and repeat
```

- Requirements — REPLACE these bullets:

```
    - Top-level unknown keys are a structural error — only prompt, stages,
      extend, memory, profile, build, assistants, delegation, and repeat
      are accepted
```

```
    - A workflow-file with none of a top-level `prompt`, any stage entries,
      any extend entries, the memory block, the build block, the assistants
      block, the delegation block, or the repeat block is rejected — at
      least one must be present
```

```
    - The assistants catalog grammar: a name-keyed mapping; each entry value
      carries the key set prompt, skills, agent, delegate, env; at least one
      of prompt or skills is present; delegate is a bool; env is a str→str
      map (an empty map equals absence); gate and when are attachment keys —
      authoring either in the catalog is an unknown-key structural error;
      name is the map key — an inner name key is an unknown key
```

```
    - The stage attachment grammar: a name-keyed mapping; an empty map
      equals absence (None); each entry value is a mapping whose keys within
      {gate, when} form a reference and whose any further key forms a full
      inline declaration (the catalog key set plus gate and when; at least
      one of prompt or skills); when is required on every entry and is one
      of start/checkpoints/finish; gate is a bool
```

  and ADD:

```
    - The repeat block grammar: a mapping whose key set is max_cycles,
      keep_runs; each value is an int >= 0 (a boolean is not an integer); a
      scalar block value is a structural error; an empty block equals
      absence
    - A workflow consisting of the repeat block alone is valid
```

**Footer — REPLACE** `Description` with (Author/CreatedAt unchanged):

```yaml
Description: |
  Pure parser of project-level workflow-files into declarative
  `WorkflowDocument` instructions that downstream consumers apply to
  extend a pipeline at compilation time — the per-stage overrides, the
  extend-stages, the memory configuration, the run-cycle tuning, and the
  collaboration instructions (assistant catalog, delegation bounds, stage
  attachments). Additionally owns the contributor-profile zone of the
  workflow path: profile resolution, strict profile-name validation,
  activation precedence resolution, and whole-file Jinja rendering of
  workflow-files before parsing.
```

#### `.usages/` files

**File `goga/pipeline/workflow/.usages/assistants.md` — REWRITE (full content):**

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
| `delegate` | bool | `false` | permission to create child tasks |
| `env` | map[str,str] | — | delivered through a generated closure |

At least one of `prompt` or `skills` is required per entry. The entry key is
the assistant name: it matches `[A-Za-z0-9._-]`, `assistant` is reserved,
and it is unique across the catalog and every inline declaration. `name`,
`gate`, and `when` never appear in a catalog entry value — `name` is the key
itself, and `gate`/`when` are attachment parameters.

## The top-level `delegation:` block

| Key | Type | Default | Note |
|-----|------|---------|------|
| `depth` | int >= 0 | not authored | maximum delegation depth; 0 forbids helper creation |
| `max_tasks` | int >= 1 | `50` (materialized) | whole-run helper task budget |

Both keys are optional; an empty block is valid and materializes
`max_tasks: 50`. A workflow consisting of the block alone is valid.

## Stage attachments (`stages.<name>.assistants`)

A name-keyed map: each key is an assistant name, each value carries the
attachment parameters. A compiling example — every referenced name is
declared, and no name repeats within one stage:

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

| Attachment key | Type | Default | Note |
|------------|------|---------|------|
| `when` | `start` \| `checkpoints` \| `finish` | **required** | when the assistant engages |
| `gate` | bool | `false` | `true` — the verdict must pass before the stage finishes |

`when` is required on every attachment — the entry names the assistant, so
its engagement timing is authored explicitly. `gate` is optional.

A value carrying any key beyond `gate`/`when` is a full inline declaration —
it accepts the catalog field set plus `gate`/`when` and requires at least one
of `prompt` or `skills`. A value carrying only `gate`/`when` is a reference:
the agent, prompt, skills, delegate permission, and env come from the
catalog entry; only `gate` and `when` are the attachment's own.

Attachments are valid only under `stages.<name>` — never inside an
extend-entry (the attachments of a new stage are authored in the stages
block by the new stage's name). An empty map equals absence.

## Minimal examples

Catalog with attachments and bounds:

```yaml
assistants:
  reviewer:
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
      reviewer:
        gate: true
        when: finish
```

Attachments only (every entry a full inline declaration):

```yaml
stages:
  build:
    assistants:
      security:
        prompt: Audit the diff.
        when: start
```

## Structural errors (complete list)

| Authoring | Error |
|---|---|
| `assistants:` non-mapping (a list, a string, a scalar) | non-mapping assistants block in workflow; author the map form keyed by assistant name |
| catalog entry value non-mapping | non-mapping assistant entry in workflow.assistants.NAME |
| unknown catalog key (incl. `name`, `gate`, `when`) | unknown key in workflow.assistants.NAME: KEY; valid keys: prompt, skills, agent, delegate, env |
| no `prompt` and no `skills` | assistant NAME requires at least one of prompt or skills |
| `delegation:` non-mapping | non-mapping delegation block in workflow |
| unknown `delegation:` key | unknown key in workflow.delegation: KEY; valid keys: depth, max_tasks |
| `depth` not int / < 0 | a structural error |
| `max_tasks` not int / < 1 | a structural error |
| `stages.<name>.assistants` non-mapping (a list, a string, a scalar) | non-mapping assistants in workflow.stages.NAME; author the map form keyed by assistant name |
| attachment value non-mapping | non-mapping assistant attachment in workflow.stages.NAME.ASSISTANT |
| missing `when` | when is required in workflow.stages.NAME.assistants.ASSISTANT |
| unknown attachment key | unknown key in workflow.stages.NAME.assistants.ASSISTANT: KEY; valid keys: prompt, skills, agent, delegate, env, gate, when |
| invalid `when` value | a structural error listing the permitted values |
| name outside `[A-Za-z0-9._-]` | a structural error naming the entry |
| the name `assistant` | assistant name is reserved |
| duplicate declaration name | duplicate assistant name: NAME |
| `assistants` in an extend-entry | assistants is forbidden in workflow.extend.NAME |

Compilation-time errors (raised by the compiler, not the parser): an
unknown assistant reference; an attachment on a script-only or
planning-only stage; the same assistant attached twice to one stage by a
programmatic contribution.

## Anti-patterns

- Do not author `name` inside an entry — the map key IS the assistant name.
- Do not author `gate`/`when` in the catalog — they are attachment
  parameters.
- Do not omit `when` on a stage attachment — the engagement timing is always
  authored.
- Do not author `assistants` inside an extend-entry — the attachments of a
  new stage are authored in the stages block by its name.
- Do not rely on engine defaults: `gate`, `delegate`, and `max_tasks` are
  materialized by the parser, not silently inherited; `when` is authored on
  every attachment and the compiled engagement value is always written
  explicitly.
- Do not expect the parser to resolve references — a name that matches no
  catalog entry and no inline declaration of the effective document is a
  compilation error, so a contributor may add catalog entries a workflow
  references.
````

**File `goga/pipeline/workflow/.usages/parse-workflow.md` — UPDATE:**

1. "Accepted structure": REPLACE the top-level key line and the assistants/
   delegation bullets, and ADD a repeat bullet:

```
Top-level keys: `prompt`, `stages`, `extend`, `memory`, `profile`, `build`,
`assistants`, `delegation`, `repeat`.
```

```
- `assistants` — the name-keyed catalog map of run-level helpers; the
  per-stage attachments (`stages.<name>.assistants`) are a name-keyed map
  too — each entry a reference (`gate`/`when`, `when` required) or a full
  inline declaration (the catalog field set plus `gate`/`when`).
- `delegation` — the delegation-bounds block (`depth`, `max_tasks`).
- `repeat` — the run-cycle tuning block (`max_cycles`, `keep_runs`; below).
```

2. ADD a section after "The build block (workflow.build)":

````md
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
````

3. "Per-stage override keys": REPLACE the `assistants` row with:

```
| assistants | map | the stage's assistant attachments keyed by assistant name — a reference (`gate`/`when`) or a full inline declaration; `when` is required on every entry; an empty map equals absence; stages block only; declarative |
```

4. "Empty-workflow rule": REPLACE the paragraph with:

```
A workflow is empty only when `prompt`, `stages`, `extend`, `memory`,
`build`, `assistants`, `delegation`, AND `repeat` are ALL absent —
`profile` never counts (activation is not content). The structural error
"empty workflow" names the content options. A workflow consisting of the
`build:` block alone is valid; a workflow consisting of the `repeat:`
block alone is valid; a workflow carrying only `profile: name` is not.
```

5. "Anti-patterns": ADD the bullet:

```
- Do not author a scalar `repeat` in the workflow-file — the short form
  belongs to the compiled flow-file, not to the authoring surface; a
  missing block already means the compiled default.
```

---

### Cell 2 — `goga/pipeline/compiler` (MODIFIED)

#### CODEMANIFEST diff

**Header — `Imports`:** ADD `WorkflowRepeat` to the workflow `Types` list
(the single import delta of the plan). `Usages` unchanged (`convention`,
`beautiful_yaml`, `afm`).

**Header — `Annotations`:**

1. REPLACE the output-shape sentence so the top-level list reads "… flat
   YAML with top-level prompt, root_dir, name, description, repeat, memory,
   collaboration, team, and a stages list" (both occurrences of the
   enumeration in the first section).
2. ADD a paragraph after the workflow-memory-emission paragraph:

```
Repeat compilation: the pipeline header declares the repeatable capability
and this cell owns the single compilation rule — a repeatable pipeline
ALWAYS produces a repeat key. A workflow repeat block compiles the authored
keys only (this cell materializes no defaults); a missing block, an absent
workflow document, or a workflow-free compilation compiles the scalar form.
A workflow repeat block on a non-repeatable pipeline is a structural error
naming the conflict — the cross-reference check lives here because only
this cell sees both documents. The compiled repeat is emitted immediately
after description, before memory. This cell owns no cycle logic — it counts
no cycles, decides no stop condition, and prunes nothing; the engine owns
every cycle semantic and the run stays a single engine invocation.
```

3. REPLACE the top-level-key-order sentence with:

```
Top-level key order: prompt, root_dir, name, description, repeat, memory,
collaboration, team, stages. The stage assistants key occupies the canonical
fields slot after memory_use and is present only when the stage carries at
least one effective attachment.
```

4. In the collaboration paragraph: the materialization sentence reads
   "… trigger from when (start → one_shot, checkpoints → checkpoints,
   finish → on_completion — always written explicitly, the engine's
   one_shot default is never relied upon) …"; the namespace sentence reads
   "… the catalog plus every full inline declaration of the stages-block
   attachment maps"; the duplicate check reads "An assistant name appearing
   twice in one stage's effective attachment list of a programmatic
   contribution is a structural error naming the stage and the assistant
   (an authored map cannot repeat a key)".
5. REPLACE the closing practice sentence with:

```
Use `afm` for the emitted engine contracts — the repeat directive (the
scalar and map forms, the strict block parse), the team-member and
stage-assistant key sets, the mode and trigger vocabularies, and the
profile binding.
Use `assistants` for the authoring vocabulary of the consumed workflow
instructions.
```

**Body — ADD the type declaration** (inserted between `FlowCollaboration`
and `FlowMemory`):

```yaml
"FlowRepeat(max_cycles: int | None = None, keep_runs: int | None = None)":
  location: flow_repeat.py
  annotations: |
    Emitted top-level repeat directive of the flow-file — the compiled form
    of the workflow run-cycle tuning block. Built by `compile_flow` for a
    repeatable pipeline; consumed by `serialize_flow`.

    `max_cycles`: the authored maximum number of complete run cycles, or
                  None when not authored
    `keep_runs`: the authored number of recent cycle run-directories to
                 retain, or None when not authored

    A directive carrying no authored key IS the scalar form — the
    serialization writes the short form and the engine applies its own
    defaults; this cell materializes no values.

    Build the data model with the standard library dataclasses module
    (NOT pydantic, per `convention`). Use @dataclass(kw_only=True).

    Requirements:
    - Use @dataclass(kw_only=True) (per `convention`)
    - Both fields default to None — an instance carries authored values
      only; an authored zero is a value, not an omission
    - Field order is fixed: max_cycles, keep_runs — the emission order of
      the block keys

    Constraints:
    - Do not decide here whether the directive is emitted — `compile_flow`
      decides on the pipeline capability
    - Do not interpret the bounds — the runtime behavior belongs to the
      engine (per `afm`)
  properties:
    "max_cycles -> int | None": |
      The authored maximum number of complete run cycles, or None when not
      authored.
    "keep_runs -> int | None": |
      The authored number of recent cycle run-directories to retain, or
      None when not authored.
```

**Body — MODIFY `PipelineHeader`:**

- REPLACE the signature with:

```yaml
"PipelineHeader(name: str, description: str, roles: PipelineRoles | None = None, repeatable: bool = False)":
```

- ADD the parameter line (after `roles`):

```
    `repeatable`: the pipeline's repeat capability — a strictly bool flag,
                  False when the key is absent or explicitly false.
                  Declares that the pipeline may run in cycles; never
                  enters the flow-file directly (the compiled repeat key
                  is derived from it)
```

- REPLACE the field-order Requirements bullet with "… roles defaults to
  None; repeatable defaults to False — a pipeline-file may omit the flag;
  field order is fixed: name, description, roles, repeatable".
- ADD the property:

```yaml
    "repeatable -> bool": |
      The pipeline's repeat capability; False when the header omits the
      flag. Never enters the compiled flow-file directly — the repeat
      directive is derived from it.
```

**Body — MODIFY `parse_dsl`:** in the annotations, extend the step-2
extraction text and the Requirements:

```
       Then extract the optional repeatable flag: when present, its value
       must be strictly bool — otherwise raise a structural error
       "non-bool value in header.repeatable"; an absent key equals False.
       Build `PipelineHeader` with name, description, roles, and
       repeatable.
```

```
    - The repeatable key (when present) must be strictly bool; absent
      equals False; the flag is carried into `PipelineHeader` and never
      enters the compiled flow-file directly
```

**Body — MODIFY `FlowDocument`:**

- REPLACE the signature with:

```yaml
"FlowDocument(prompt: str | None = None, root_dir: str | None = None, name: str, description: str, repeat: FlowRepeat | None = None, memory: FlowMemory | None = None, collaboration: FlowCollaboration | None = None, team: list[FlowTeamMember] | None = None, stages: list[FlowStage])":
```

- The opening line reads "a single flat YAML document with up to nine
  top-level keys (prompt (when present), root_dir (when supplied), name,
  description, repeat (when the pipeline is repeatable), memory (when
  memory participates), collaboration (always), team (when the workflow
  carries a catalog), stages)".
- ADD the parameter line (between `description` and `memory`):

```
    `repeat`: the compiled repeat directive, or None when the pipeline is
              not repeatable. Emitted between description and memory when
              not None; an instance carrying no authored key is the scalar
              form; None omits the key entirely (byte-identical output for
              non-repeatable pipelines)
```

- REPLACE the field-order Requirements bullet with "… memory defaults to
  None; collaboration defaults to None; team defaults to None; repeat
  defaults to None; field order is fixed: prompt, root_dir, name,
  description, repeat, memory, collaboration, team, stages — the canonical
  emission order in `serialize_flow`".
- ADD the property:

```yaml
    "repeat -> FlowRepeat | None": |
      The compiled repeat directive; an instance carrying no authored key
      is the scalar form. None when the pipeline is not repeatable — the
      key is omitted from the output entirely.
```

**Body — MODIFY `compile_flow`:**

- ADD algorithm step 4.0 (before the reconstruction — cross-document checks
  first):

```
       4.0. Repeat correspondence check (when `workflow` is not None): when
            the workflow document carries a repeat block and the parsed
            header's repeatable flag is False — raise a structural error
            "workflow repeat block requires a repeatable pipeline; author
            repeatable: true in the pipeline header". The workflow parser
            never sees the pipeline; this cell owns the cross-reference
            check
```

- In step 4.10: the namespace is "… the `WorkflowAssistant` catalog of the
  workflow document ∪ the full inline declarations found in the
  stages-block attachment maps"; the duplicate check reads "the same name
  twice in one stage's effective attachment list of a programmatic
  contribution".
- In step 6, ADD the repeat bullet (with the memory bullet):

```
       - repeat = None when the header's repeatable flag is False;
         otherwise ALWAYS a `FlowRepeat`: built from the authored keys of
         the workflow's repeat block when `workflow` carries one (authored
         keys only — no materialized defaults), else a `FlowRepeat`
         carrying no key (the scalar form; an absent workflow document and
         a workflow-free compilation both land here). Place the directive
         between description and memory
```

- ADD Requirements bullets:

```
    - A repeatable pipeline always compiles a `repeat` key — a workflow
      block emits the authored keys only; no block, no workflow document,
      or a workflow-free compilation emits the scalar form
    - A workflow `repeat` block on a non-repeatable pipeline is a
      structural error naming the conflict — the cross-reference check
      lives in this cell, not in the workflow parser
    - The compiled `repeat` occupies the top-level position immediately
      after description and before memory
    - A non-repeatable pipeline compiles byte-identically — no repeat key
      anywhere
```

- ADD Constraints bullets:

```
    - Do not materialize repeat defaults — the engine owns the cycle
      defaults; this cell emits authored values only, plus the scalar form
      when nothing is authored
    - Do not count cycles, decide stop conditions, or prune run
      directories — engine semantics; the run stays a single engine
      invocation
```

**Body — MODIFY `serialize_flow`:**

- ADD to algorithm step 1 (between the description/root_dir handling and
  the memory bullet):

```
       - when `doc` repeat is not None — emit the repeat directive after
         description and before memory: an instance carrying no authored
         key is the scalar `repeat: true`; otherwise a block-style mapping
         of the authored keys in the fixed order max_cycles, keep_runs
         (present keys only, plain scalars). When `doc` repeat is None —
         omit the key entirely
```

- Requirements: the fixed top-level order reads "name, description, repeat
  (when present), memory (when present), collaboration, team, stages"; ADD:

```
    - a non-repeatable flow document serializes without the repeat key —
      byte-identical output
    - the scalar form is written for a repeatable pipeline carrying no
      authored key
```

**Footer — REPLACE** `Description` with (Author/CreatedAt unchanged):

```yaml
Description: |
  Pure transformer cell that compiles goga DSL pipeline-files
  (phases-list or stages-map) into afm flow-files (flat YAML with
  optional prompt, root_dir, name, description, repeat, memory,
  collaboration, team, and stages). Optionally applies declarative
  workflow instructions to reconstruct the parsed body before
  serialization.
```

#### `.usages/` files

**File `goga/pipeline/compiler/.usages/parse-dsl.md` — ADD a section after
the Usage example:**

````md
## The header repeatable flag

The pipeline header accepts an optional strictly-bool `repeatable` key next
to `name`/`description`:

```yaml
name: Goga feature
description: Feature implementation
repeatable: true
---
```

- absent key or `repeatable: false` — the pipeline is not repeatable and
  compiles no `repeat` key;
- `repeatable: true` — the pipeline declares the cycle capability; the
  compiler then ALWAYS emits a `repeat` key (a workflow `repeat:` block
  supplies the authored tuning keys; otherwise the scalar `repeat: true`).

A non-bool value is a structural error "non-bool value in
header.repeatable". The flag never enters the flow-file directly — it is
the capability the compiled `repeat` directive is derived from; the cycle
tuning itself is authored in the workflow-file.
````

**File `goga/pipeline/compiler/.usages/compile-flow.md` — UPDATE:**

1. REPLACE the top-level key order line with "prompt, root_dir, name,
   description, repeat, memory, collaboration, team, stages".
2. ADD a section after the stage-body translation table:

````md
## Repeat compilation (repeatable pipelines)

One rule, no exceptions: a repeatable pipeline ALWAYS compiles a `repeat`
key — without the key the engine starts no cycle.

| Workflow authoring | Compiled `repeat` |
|---|---|
| `repeat: {max_cycles: 3}` | `repeat: {max_cycles: 3}` |
| `repeat: {keep_runs: 5}` | `repeat: {keep_runs: 5}` |
| `repeat: {max_cycles: 3, keep_runs: 5}` | both keys, order `max_cycles, keep_runs` |
| no block / no workflow-file / `--no-workflow` | `repeat: true` |

- Authored keys only — goga materializes no defaults (`max_cycles: 0` and
  `keep_runs: 0` are authored values and compile verbatim).
- A workflow `repeat:` block on a non-repeatable pipeline is a compile-time
  structural error "workflow repeat block requires a repeatable pipeline;
  author repeatable: true in the pipeline header".
- The compiled `repeat` sits immediately after `description`, before
  `memory`.
- afm owns every cycle semantic (unlimited default cycles, `keep_runs: 2`
  default, stop-on-failed-cycle, pruning) — the compile path never
  duplicates them and the run stays a single `afm run`.
````

**File `goga/pipeline/compiler/.usages/serialize-flow.md` — UPDATE:**

1. Style rules: ADD the bullet "- repeat: the scalar `true` when the
   directive carries no authored key; otherwise a block-style mapping, key
   order max_cycles, keep_runs; plain scalars; present keys only".
2. Key presence: ADD "A flow document without a `repeat` directive (a
   non-repeatable pipeline) serializes without the key — byte-identical
   output. When present, it sits between `description` and `memory`, ahead
   of the `memory` block."

**File `goga/pipeline/compiler/.usages/collaboration-emission.md` — UPDATE
three sentences:**

1. "The `checkpoints` default is written explicitly — the engine's own
   default is `one_shot` and is never relied upon." → "`trigger` is always
   written explicitly — the engine's own default is `one_shot` and is never
   relied upon (`when` is authored on every attachment; there is no
   compiler-side engagement default)."
2. The check bullet "the same assistant name twice in one stage's list" →
   "the same assistant name twice in one stage's effective attachment list
   of a programmatic contribution (an authored attachment map cannot repeat
   a key)".
3. The stage-attachments paragraph notes: the authoring source is a
   name-keyed map and the compiled order follows the authored key order.

---

### Cell 3 — `goga/pipeline/hooks` (MODIFIED)

#### CODEMANIFEST diff

**Header:** `Imports`/`Usages` unchanged. `Annotations` — ADD one sentence
to the overlay-merge paragraph (after the delegation/catalog sentences):

```
The overlay merge preserves the run-cycle tuning the same way: the repeat
block is whole — an authored block is unbeatable, otherwise the later
contributing tool's block wins — and the rebuilt document carries the
effective repeat verbatim, so a tool-amended run never loses an authored
cycle bound.
```

Additionally — the map-form terminology of the stage attachments (wording
only; the merge rules are unchanged). Three REPLACE edits:

1. In the overlay-merge paragraph of the global `Annotations`: REPLACE
   "The per-stage assistant lists append with deduplication by name:" with
   "The per-stage assistant maps append with deduplication by name:".
2. In `merge_workflow_overlay` algorithm step 5a: REPLACE "for each stage
   name the authored list is the ground" with "for each stage name the
   authored map is the ground", and "a stage with no authored entry takes
   the appended contributing list the same way" with "a stage with no
   authored entry takes the appended contributing entries the same way".
3. In `merge_workflow_overlay` Requirements: REPLACE "the appended
   per-stage assistant lists — a rebuild that drops them" with "the
   appended per-stage assistant maps — a rebuild that drops them".

**Body — MODIFY `merge_workflow_overlay`:**

- ADD algorithm step 4c after 4b:

```
    4c. repeat: keep the authored block when present — it is unbeatable;
        otherwise the block of the later contributing tool wins; no
        field-level merging
```

- REPLACE the step-8 closing sentence with "… the final document assembly
  carries the profile and build fields of `base` verbatim (exactly as
  memory survives the rebuild), the assistants field of the base together
  with the appended contributing entries, and the effective repeat —
  workflow-level instructions never vanish in the overlay".
- ADD the Requirements bullet:

```
    - The rebuilt `WorkflowDocument` preserves the run-cycle tuning: the
      effective repeat block rides the rebuild verbatim — a rebuild that
      drops it would silently recompile an authored cycle bound as the
      scalar default on tool-amended runs
```

- ADD the Constraints bullet:

```
    - Do not interpret the repeat block — cycle semantics belong to the
      consumer and the engine; the merge carries the value whole
```

**Body — MODIFY `WorkflowAmendment`:** REPLACE the emptiness sentence of
the `contribute` method annotation with:

```
      - A document with no prompt, no stages, no extend, no memory, no
        assistants, no delegation, and no repeat is an empty contribution —
        the delivery discards it with a warning
```

**Footer:** unchanged.

#### `.usages/` files

**File `goga/pipeline/hooks/.usages/checkpoints.md` — REPLACE the merge-slot
bullet** (under "Amend before compilation"):

````md
- A tool contributes one declarative `WorkflowDocument`; authored intent
  wins per slot — the prompt appends, the memory block is whole, the repeat
  block is whole, stage fields fill only what the author left unset, extend
  entries add; the assistant catalog adds fresh names (authored names win, a
  tool name colliding with any name already in the merged assistant
  namespace is dropped), the delegation block is whole, and stage assistant
  maps append with name deduplication.
````

---

### Cell 4 — `goga/pipeline` (MODIFIED)

#### CODEMANIFEST diff

**Header:** unchanged (`Imports`, `Usages`, `Annotations`).

**Body — MODIFY `apply_skip_stages`:**

- REPLACE the algorithm step-3 sentence about the carry:

```
       (skip wins over any pre-existing entry for that name;
       the compiler removes the stage before applying overrides). The
       replacement CARRIES the pre-skip entry's assistants map: the
       compiler removes the skipped stage before the attachment walk (its
       own attachments are never checked or emitted), but the
       document-wide assistant namespace reads every stage entry, so the
       stage's inline declarations stay resolvable for other stages'
       references — the same carry an authored skip: true keeps
```

- REPLACE the algorithm step-4 enumeration closing with "…; delegation =
  the delegation field of the workflow when it is not None else None; repeat
  = the repeat field of `workflow` when `workflow` is not None else None —
  carried verbatim. The input `workflow` and its maps are NOT mutated".
- REPLACE the survival Requirements bullet with:

```
    - The memory configuration, the profile field, the build block, the
      assistant catalog, the delegation block, and the repeat block of the
      input workflow survive the rebuild verbatim — a rebuild that drops
      them would silently disable memory participation, change activation,
      lose build instructions, lose collaboration, or recompile an authored
      cycle bound as the scalar default for skip-driven runs
```

- REPLACE the construction Requirements bullet's assistants mention:
  "… EXCEPT assistants (the pre-skip entry's map rides along — see
  algorithm step 3) …".

**Footer:** unchanged.

#### `.usages/` files

None.

---

## Dependency Map

```
                         ┌──────────────────────────┐
                         │  goga/pipeline/workflow   │  (leaf; no Imports)
                         └───────────┬───────────────┘
              Types + Usages          │            WorkflowDocument
              (WorkflowRepeat NEW,    │            (repeat rides inside —
               WorkflowDocument,      │             opaque carry)
               WorkflowStage,         │                    │
               WorkflowAssistant,     │                    │
               parse-workflow,        │                    │
               memory, assistants)    │                    │
                                     ▼                    ▼
                 ┌───────────────────────────┐   ┌────────────────────────┐
                 │  goga/pipeline/compiler    │   │  goga/pipeline/hooks   │
                 │  (+ WorkflowRepeat import) │   │  (repeat authored-wins │
                 │  FlowRepeat NEW;           │   │   + verbatim carry)    │
                 │  repeatable / always-emit /│   └───────────┬────────────┘
                 │  cross-check / emission    │               │
                 └─────────────┬──────────────┘               │
                               │ compile_flow, FlowDocument,  │
                               │ translate_role, …            │
                               ▼                              ▼
                         ┌────────────────────────────────────────┐
                         │              goga/pipeline             │
                         │  apply_skip_stages (+ repeat verbatim, │
                         │  assistants map carry)                 │
                         └────────────────────────────────────────┘
```

No cycles; the import graph stays one-directional (workflow never imports
compiler concepts). The single import delta is `WorkflowRepeat`
(`workflow → compiler`).

## Verification Checklist

After each cell, run `goga lint` for the touched cells and the checks below;
at the end run `pytest tests/ -x` and `ruff check goga/`.

**Cell 1 — `goga/pipeline/workflow`:**

- `WorkflowRepeat` parses: map form with either/both keys, `max_cycles: 0`
  and `keep_runs: 0` carried as authored values, empty block → `repeat=None`.
- Repeat structural errors: non-mapping block (incl. `repeat: true`,
  `repeat: false`, any scalar), unknown key, non-int value (incl. a boolean),
  negative value — each with the exact message.
- Catalog map form parses; inner `name`/`gate`/`when` are unknown keys;
  list-form catalog rejected with the error naming the map form.
- Attachment map form parses; reference vs full inline declaration
  discriminated by the value keys; missing `when` rejected; list/bare-string
  attachments rejected with the error naming the map form; duplicate-name
  rule across catalog and inline declarations.
- Empty-workflow rule: `repeat:`-only workflow valid; profile-only still
  empty.
- `.usages/assistants.md` contains no list-form example; the error table is
  complete.

**Cell 2 — `goga/pipeline/compiler`:**

- Header `repeatable` parses: absent = False, explicit false = False, true =
  True, non-bool → `non-bool value in header.repeatable`.
- Always-emit: repeatable + block → authored keys only (no defaults);
  repeatable + no block / no workflow / `--no-workflow` → scalar
  `repeat: true`; non-repeatable → no key (byte-identical output).
- Cross-check: non-repeatable + workflow block → the structural error naming
  the conflict.
- Emission: `repeat` sits immediately after `description`, before `memory`;
  block key order `max_cycles, keep_runs`; present keys only.
- Assistants equivalence: the compiled `stages[].assistants` and `team`
  output for map-form authoring equals the engine list-form output for the
  equivalent authoring (reference and declaration forms both); `trigger`
  written explicitly on every entry.
- Facade exports `FlowRepeat`.

**Cell 3 — `goga/pipeline/hooks`:**

- Authored `repeat` survives the overlay verbatim; a contributing block
  applies only when no authored one; the later tool wins among contributions.
- A `repeat`-only contribution is NOT empty (not discarded).

**Cell 4 — `goga/pipeline`:**

- Authored repeat keys survive a `-s/--skip` rebuild; `workflow=None` + skip
  compiles the scalar form for a repeatable pipeline.
- The pre-skip entry's assistants map rides the skip replacement (inline
  declarations stay resolvable).

**Global:** `goga lint` clean for the four cells; `pytest tests/ -x` green;
`ruff check goga/` clean; compiled outputs for the six shipped assets and
the project pipelines byte-identical (none gains `repeatable`); the
`.goga/workflows/refinement.yml` parse rejection is the known accepted
consequence (its conversion is a separate task).
