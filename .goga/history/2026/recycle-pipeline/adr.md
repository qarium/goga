# Repeating pipeline cycles and map-form assistants authoring

goga gains two authoring changes that ride the existing compile path: a repeating
run cycle, and a terser `assistants` syntax. afm (v2.0.9) already owns the cycle
mechanics — one `afm run` performs multiple complete passes, emits `flow_repeated`,
stops a repeat on a failed cycle, and prunes old run directories — so goga authors
and compiles the directive and nothing more; `run_pipeline` stays a single
`afm run` invocation. The role split for repeat is deliberate: the pipeline header
declares a **capability** (`repeatable: true`, next to `name`/`description` — the
pipeline's nature, authored by the pipeline's author), while the workflow file
carries the **tuning** (`repeat: {max_cycles, keep_runs}` — project settings in
afm's vocabulary, verbatim). The assistants change replaces the list-of-mappings
authoring (`- name: X, ...`) with name-keyed maps in both the catalog and stage
attachments; the compiled flow-file output is untouched (the engine's list-form
`stages[].assistants` and `team` contracts stay as they are).

## Decision map

1. **`repeatable: true` compiles to `repeat` — one rule, no exceptions.** A
   repeatable pipeline always produces a `repeat` key in the compiled flow-file:
   a workflow `repeat` block emits the block (authored keys only — goga
   materializes no defaults), and a missing block, a missing workflow, or
   `--no-workflow` emits the scalar `repeat: true` (afm defaults: unlimited
   cycles, `keep_runs: 2`). Rejected: gating the emission on the workflow's
   explicit opt-in — the flag is the pipeline's nature, not half an agreement,
   and a silent single pass for a repeatable pipeline would be the surprising
   outcome.

2. **A workflow `repeat` block on a non-repeatable pipeline is a structural
   error at compile time.** The workflow parser cannot check this (it never sees
   the pipeline); the compiler sees both documents, so the cross-reference check
   lives there — same two-layer pattern as stage-name and attachment validation.

3. **The workflow authors only the map form.** `repeat: true` / `repeat: false`
   in the workflow are rejected: the short form is meaningless there (a missing
   block already means defaults) and `false` would duplicate "not repeatable",
   which belongs to the pipeline. Both keys are optional (afm semantics apply);
   an empty `repeat: {}` equals absence (the project's empty-map convention).
   The workflow-level way to stop a repeatable pipeline from cycling is
   `repeat: {max_cycles: 1}`. goga validates structure at parse time
   (non-mapping block, unknown key, non-int value, negative value); cycle
   semantics belong to afm.

4. **`repeat` is emitted into the flow-file immediately after `description`**,
   before `memory` — a lifecycle directive sits with the document identity, and
   the collaboration zone (`memory`, `collaboration`, `team`, `stages`) stays
   grouped. New top-level key order: `prompt, root_dir, name, description,
   repeat, memory, collaboration, team, stages`.

5. **Assistants authoring becomes name-keyed maps.** Catalog:
   `assistants: {<name>: {agent, prompt, skills, delegate, env}}` — the name
   moves into the key; an inner `name:` key is an unknown key (error); `gate`/
   `when` stay forbidden in the catalog. Stage attachments take a map value
   only (`architector: {when: finish}`), compiled to the engine's list form
   unchanged.

6. **`when` is required in every stage attachment.** With the name in the key,
   the old bare-string reference has no map rendering, and a materialized
   `checkpoints` default would make `architector: {...}` ambiguous about
   engagement timing — so the default is removed from authoring and every
   attachment (reference and inline declaration alike) must state
   `when: start | checkpoints | finish`; a missing `when` is a structural
   error. `gate` remains optional (default `false`). The compiled `trigger` is
   still written explicitly on every entry, exactly as before (the engine's
   default is `one_shot`, not goga's). Reference vs declaration discrimination
   is unchanged: value keys within `{gate, when}` → reference, any further key
   → full inline declaration.

7. **The transition is hard, not dual-accepting.** The list form is rejected
   with an error naming the map form — the established project precedent
   (`agents` → `roles` in the header, `interactive`/`auto_run` in stage
   bodies). Nothing has shipped in a release yet, so there is nothing to keep
   compatible. The one authored consumer, `.goga/workflows/refinement.yml`,
   is NOT converted as part of the change (amended at task formulation by
   user decision): the file stays in the list form, its parse is rejected
   after this change, and the refinement pipeline breaks on its next run
   until a separate conversion task lands — a known, accepted consequence.

8. **No existing pipeline YAML gains `repeatable: true`.** The six shipped
   assets and the project pipelines stay untouched: repeat is DSL support only,
   and adopting it is a deliberate per-pipeline decision for later. Profiles
   (`language`, `stages`) do not carry repeat; `goga pipeline card` /
   `describe_pipeline` do not surface it (a card change can be its own decision
   later).

## Out of scope (recorded, not silently assumed)

- Cell/CODEMANIFEST architecture and contract layout — the next stage's work.
- Any goga-side awareness of cycles beyond compilation: history statuses,
  run coordination, hooks, and memory are unchanged; afm owns the cycle, and
  `run_pipeline`'s post-run status recomputation already runs after all cycles
  finish.
- User-facing docs and usage updates (`assistants.md` authoring forms) happen
  with implementation; the afm `repeat` section in
  `.goga/usages/cooks/afm.md` was written at task formulation
  (user-approved), and implementation keeps it consistent with the final
  behavior.
