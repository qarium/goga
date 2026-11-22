# Pipeline-Stage Assistant Declarations

## Problem

A pipeline-file author who writes a stage cannot express the helper
assistants the stage needs where the stage itself is defined. Assistant
content (the helper's instruction text and its skills) and engagement
(when it engages, whether its verdict gates the stage finish) can be
authored only in the per-project workflow-file — the top-level
`assistants:` catalog and the per-stage attachments
`workflow.stages.<name>.assistants`.

The consequences:

- a stage that needs a helper (for example, a gated diff audit at
  finish) forces every project reusing the pipeline to re-author the
  assistant's prompt and skills in its own workflow-file, and the copies
  drift;
- a pipeline run without a workflow-file (none authored, or
  `--no-workflow`) cannot attach any assistant to any stage;
- the workflow-file author must know stage internals to reproduce the
  assistant content, instead of only deciding delivery and engagement;
- once assistants ship together with a pipeline, projects need an
  explicit governance channel (veto, re-timing, delivery retargeting)
  that the current product does not offer.

## Users

**Primary — pipeline-file author.** Authors the goga DSL pipeline-file:
the stages with their prompts, skills, scripts, and roles. Owns the
knowledge of what each stage does and which helper work belongs to it.
Ships pipelines to projects and runs them standalone.

*Goals:* declare a stage's helper assistants together with the stage;
author their engagement at the declaration site; have them work without
any workflow-file.

**Secondary — workflow-file author (project run configurator).**
Configures how a shared pipeline runs in a specific project: per-stage
overrides, delivery, engagement tuning, skips. Does not own the
pipeline-file and must not edit it.

*Goals:* keep governance over assistants shipped with the pipeline —
veto an assistant for this project, re-time it, retarget its delivery,
extend its content — all without touching the pipeline-file.

**Secondary — tool contributor.** Delivers programmatic workflow
contributions (the workflow amendment overlay) that merge into the
authored workflow before compilation. Needs the merge to stay consistent
when assistants are also declared in the pipeline-file.

## Goals

1. **Stage-owned collaboration.** A pipeline-file author can make a
   stage ship its helper assistants so that any run of the pipeline —
   with or without a workflow-file — engages them exactly as the stage
   defines. No content duplication across project workflows.
2. **Project governance.** A workflow-file author retains full control
   over shipped assistants: veto, re-timing, delivery retargeting, and
   content extension — without editing the pipeline-file.
3. **One assistant model.** Pipeline-authored and workflow-authored
   assistants behave identically downstream: same compiled surfaces,
   same delivery, same errors. No second-class assistant channel.

## User Experience

**Declaring (pipeline author).** The author adds an `assistants` map to
a stage body — in either pipeline body format (stages-map or
phases-list). Each entry is keyed by assistant name and authors the
helper's content and engagement: `prompt` (instruction text), `skills`
(list), `when` (required — `start` / `checkpoints` / `finish` /
`message`, the existing vocabulary), `gate` (optional, default false).
No delivery fields are authored here.

```yaml
# pipeline-file (stage body)
review:
  title: Review
  prompt: Implement the feature
  assistants:
    auditor:
      prompt: Audit the diff.
      skills: [code-audit]
      when: finish
      gate: true
```

**Running.** On the next compile or run, assistants declared in the
pipeline attach to their stage exactly like workflow-authored
attachments: they engage at the authored `when`, block the stage finish
when gated, join the run under their name with their skills delivered.
With no workflow-file — or `--no-workflow` — they still attach. At run
time they are indistinguishable from workflow-authored assistants: same
dashboard presence, same verdict and gating behavior, same delegation
bounds.

**Governing (workflow author).** The project workflow addresses a
shipped assistant through `stages.<stage>.assistants.<name>`:

```yaml
# workflow-file
stages:
  review:
    assistants:
      auditor:
        skip: true          # veto — the assistant does not run here
      # or, alternatively:
      # when: checkpoints   # override the pipeline engagement
      # gate: false
      # agent: codex        # delivery configuration
      # env: {FOO: bar}
      # prompt: ...         # appended to the pipeline text
      # skills: [extra]     # expands the pipeline list
```

`skip: true` removes the assistant from that stage for this project —
no attachment, no team membership, no generated profile; the stage
itself still runs. An extension entry overrides `when`/`gate`, sets
`agent`/`env`/`delegate`, appends `prompt` text after the pipeline
text, and expands the `skills` list with the pipeline entries first. An
entry that only extends may omit `when` — the pipeline engagement
stands. A workflow that mentions a shipped assistant not at all leaves
it exactly as the pipeline authored it.

**Workflow-only assistants (unchanged).** The existing catalog
declarations, full inline declarations, and references keep working
exactly as before, with their existing override semantics.

**Failure behavior.** Every authoring mistake is rejected strictly at
parse/compile time, before any run starts, with a readable structural
error naming the file location (the stage and the assistant) —
following the product's existing error conventions. Failures are
deterministic: fixing the file and re-running is the recovery path; no
partial run state is produced.

## Requirements

### R1. Pipeline-stage authoring surface

- **R1.1** Both DSL body formats (stages-map and phases-list) accept an
  `assistants` key in a stage/step body: a name-keyed map where the
  entry key is the assistant name. An empty map equals absence.
- **R1.2** Entry vocabulary: `prompt` (str), `skills` (list of str),
  `when` (required; one of `start`, `checkpoints`, `finish`,
  `message`), `gate` (bool; optional; default false). The delivery keys
  `agent`, `env`, `delegate` are not part of this vocabulary: authoring
  them is a structural error naming the location.
- **R1.3** Assistant names follow the existing rules: `[A-Za-z0-9._-]`,
  the name `assistant` is reserved, no repetition within the map.
- **R1.4** A declaration must resolve content — `prompt` or `skills`;
  otherwise a structural error naming the stage and the assistant.
- **R1.5** The current blanket rejection of an `assistants` key in a
  stage body is replaced by this authoring surface.

### R2. Immediate attachment

- **R2.1** A pipeline-declared assistant attaches to its own stage by
  its authored `when`/`gate`, with or without a workflow-file
  (including `--no-workflow` runs).
- **R2.2** Compiled engagement is identical to workflow attachments:
  the same `when`-to-trigger mapping (`start` → one-shot, `checkpoints`
  → checkpoints, gated `finish` → pre-completion review, ungated
  `finish` → on-completion, `message` → the resting on-message
  engagement), the same gate-to-mode mapping (`required` / `advisory`).
  Every compiled attachment entry materializes every field; no
  compiler-side engagement defaults exist.
- **R2.3** The existing attachment prohibitions apply to pipeline
  declarations: no assistants on a stage whose body carries `script`,
  and none on a planning-only stage (translated agents exactly
  `["planning"]`) — structural errors naming the stage.
- **R2.4** Every loop-expanded copy of a stage carries its pipeline
  assistants; a workflow stage-level `skip: true` removes the stage and
  its assistants together.

### R3. Delivery parity

- **R3.1** Attached pipeline declarations are delivered exactly like
  catalog assistants: they join the compiled team list (title from the
  name, instruction from the prompt — the empty string when none — and
  the skills list) and receive a generated profile under the existing
  `goga-<name>` scheme.
- **R3.2** Team-list order: catalog members in authored order first,
  then pipeline-declared members in first-attachment order.
- **R3.3** Agent resolution is unchanged: the workflow-configured agent,
  else the effective global agent, else a strict pre-run error naming
  the assistant and its authoring site. A workflow-configured `env`
  delivers through the generated closure exactly as today.
- **R3.4** The collaboration block and delegation bounds apply
  uniformly to pipeline-declared assistants.

### R4. Workflow governance

- **R4.1** A workflow stage attachment entry whose name matches a
  pipeline declaration of that same stage is a skip or an extension —
  never a duplicate attachment:
  - **skip**: `{skip: true}` removes the assistant from that stage — no
    compiled attachment entry, no team member, no generated profile —
    while the stage itself still runs. Skipping a name that is declared
    nowhere is a structural error. Mixing `skip` with any other key is
    a contradictory-authoring structural error.
  - **extension**: `when`/`gate` override the pipeline values; `agent`,
    `env`, `delegate` configure delivery; `prompt` appends to the
    pipeline text (pipeline text first, then the workflow text);
    `skills` expands the pipeline list (pipeline entries first, then
    workflow entries, deduplicated by value; an authored empty list
    adds nothing). `when` may be omitted — the pipeline engagement
    stands.
- **R4.2** A name that matches no pipeline declaration of that stage
  keeps the existing attachment semantics unchanged: a catalog
  reference or a full inline declaration with `when` required, and the
  catalog's existing override semantics (including explicit-empty
  clears) preserved.
- **R4.3** The two merge models are keyed by the name's origin and
  never overlap: a catalog (or inline) entry and a pipeline declaration
  bearing the same name cannot coexist in one effective document — a
  duplicate-name structural error. Assistant names are unique across
  the whole effective namespace (catalog, inline declarations, pipeline
  declarations).
- **R4.4** Pipeline declarations are visible only to their own stage's
  workflow entry: referencing such a name from another stage is an
  unknown-assistant-reference error; the top-level catalog neither
  extends nor consumes pipeline declarations.
- **R4.5** `assistants` remains forbidden in workflow extend-entries;
  attachments of extend-stages continue to be authored in the stages
  block by the new stage's name.

### R5. Consistency and non-regression

- **R5.1** Tool-delivered workflow contributions (the amendment overlay)
  merge under the same namespace rules; any collision with pipeline
  declarations fails with the same structural errors at compilation.
- **R5.2** Pipelines without stage-level assistants, and workflows using
  only the existing collaboration model, compile byte-identically to
  the current product output.
- **R5.3** All new authoring mistakes are rejected strictly at
  parse/compile time — before any run starts — with errors naming the
  file location (stage and assistant), following the existing message
  conventions.
- **R5.4** The parsed pipeline document mirrors the authored source
  (declarations carried, source bodies never mutated); the workflow
  extension applies at compilation, output-side only.

## Constraints

- **C1** The afm engine strict-parses stage attachment entries in the
  compiled flow: only `profile`, `title`, `instruction`, `mode`,
  `trigger` are accepted there; a `skills` key is rejected. Skills
  reach the engine only through team member entries.
- **C2** The compiled flow is the single source of truth for profile
  generation: profiles materialize exactly for the referenced ids; no
  dead profiles remain.
- **C3** The workflow-file remains the delivery-configuration surface:
  `agent`, `env`, `delegate` are workflow-side; the pipeline authors
  content and engagement only.
- **C4** No compiler-side engagement defaults: `when` is always authored
  explicitly; `gate` materializes false; the compiled trigger is always
  written.
- **C5** Assistant names are unique across the effective namespace; the
  name `assistant` is reserved; names match `[A-Za-z0-9._-]`.
- **C6** Assistants from any source are forbidden on script-carrying
  and planning-only stages.
- **C7** Declarations are authored only in the pipeline-file;
  attachments are authored only in the workflow stages block;
  extend-entries stay assistant-free.
- **C8** The `goga-<name>` profile-id scheme and the project-layer
  user-authored profile override channel are preserved.
- **C9** Existing workflow-only collaboration behavior — the catalog
  override model (including explicit-empty clears), inline
  declarations, references, delegation bounds — is unchanged.

## Scope

### In Scope

- `assistants` authoring in pipeline-file stage bodies (both body
  formats) with full structural validation.
- Immediate attachment of pipeline-declared assistants, including runs
  without a workflow-file.
- Workflow skip and extension semantics for pipeline-declared names
  (`skip`, `when`/`gate` override, `agent`/`env`/`delegate`, prompt
  append, skills expand).
- Global assistant-name uniqueness across the effective namespace
  (catalog, inline, pipeline declarations).
- Delivery parity: team membership, skills delivery, generated
  profiles, agent resolution, env closures.
- Consistency of the tool-delivered workflow amendment overlay with the
  extended namespace.
- Non-regression guarantees for existing pipelines and workflows.
- Updated authoring documentation for both surfaces.

### Out of Scope

- Authoring `agent`, `env`, or `delegate` in pipeline declarations.
- Run-level (global) assistant declarations in the pipeline-file.
- Cross-stage visibility of pipeline declarations or a shared
  pipeline-declaration namespace.
- Any change to the existing catalog/inline/reference model and its
  override semantics.
- Engine-side changes (new fields in stage attachment entries, an
  engine-side skills channel).
- `assistants` in workflow extend-entries.
- Changes to delegation, gates, memory, or dashboard/UI behavior.
- New defaults for engagement or assistant content.

## Success Criteria

- **SC1** A pipeline-file with a stage-declared assistant compiles and
  runs with no workflow-file present: the compiled flow carries the
  stage attachment entry (profile, title, instruction, mode, trigger —
  per the authored `when`/`gate`), a team member with the declared
  skills, and the profile for its id is generated.
- **SC2** `stages.<stage>.assistants.<name>: {skip: true}` on a
  pipeline-declared assistant yields a compiled flow with no attachment
  entry, no team member, and no profile for that name — while the stage
  itself still runs.
- **SC3** An extension entry yields the merged outcome, observable in
  the compiled flow: overridden `when`/`gate`, configured `agent`/`env`,
  appended prompt (pipeline text first, then workflow text), and
  expanded skills (pipeline entries first, then workflow entries,
  deduplicated).
- **SC4** Every defined authoring mistake is rejected with a readable
  structural error naming the location, strictly before any run:
  delivery keys in a pipeline declaration, unknown keys, missing `when`
  where required, invalid `when` values, invalid/reserved/duplicate
  names (including a catalog-vs-pipeline collision), a content-free
  declaration, `skip` of an unknown name, `skip` mixed with extension
  keys, assistants on script-carrying or planning-only stages, and
  `assistants` in an extend-entry.
- **SC5** An assistant-free pipeline and a workflow using only the
  existing collaboration model compile byte-identically to the current
  product output.
- **SC6** Existing workflow-only assistants (catalog references, full
  inline declarations) behave exactly as before, including skills
  delivery through catalog team membership.
