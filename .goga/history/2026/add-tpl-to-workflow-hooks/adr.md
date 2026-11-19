# Profile-aware workflow contributions from pipeline hooks

Tool contributions through the `pipeline.amend_workflow` hook are profile-blind
today (no profile fact on the amendment view, no rendering of contributed
strings), while authored workflow-files render with the active contributor
profile. We decided (interview 2026-11-19, PRD `add-tpl-to-workflow-hooks`)
that the amendment view gains the operation's already-resolved profile as a
read-only fact, and that every string of a contributed document renders as a
Jinja template with that profile's content before the authored-wins merge —
one profile activation shapes the whole effective workflow.

## Settled decisions

1. **The profile fact is the already-resolved value.** The view carries the
   profile that rendered the authored file (the loaded workflow's profile:
   name, content, source project/home — or absence) as operation data; no
   reads and no re-resolution happen at the checkpoint. The fact is identical
   for every tool (mutual blindness extended to it), identical in the run and
   card forms, and reads absent in the no-workflow silent-miss case.
2. **Render at commit, inside the walk.** A tool's contribution renders at
   its commit moment; a render failure is disciplinarily a hook failure —
   the first failing tool stops the command pre-run and later tools' hooks
   never run.
3. **Uniform type-driven render law.** Every string leaf and every string
   mapping key at any depth of the contributed `WorkflowDocument` renders —
   including the open extend-stage bodies and the never-merging global fields
   (`profile`, `build`, `agent`, `env`); non-string scalars are not template
   surfaces. The context is exactly the active profile's content (empty
   without activation, no ambient variables such as tool or pipeline), and
   the Jinja environment is the same fixed flag set the whole-file render
   uses.
4. **Failures.** A template error anywhere in a contribution (dead fields
   included) is a hard pre-run failure: one error in the existing
   amendment-failure format (hook, tool, action) carrying the template cause
   — error class, message, and a document path (the dot-path of the string
   within the contribution; source — pre-render — keys in the path; list
   elements indexed; `gates` disambiguated positionally: `gates.patience`
   vs `stages.<name>.gates[0].script`). A rendered-key collision inside one
   contribution map is the same hard failure (tool, map, source keys,
   colliding result).
5. **Unchanged rules.** Rendering runs before the empty-contribution check;
   that check stays presence-based and unchanged, and rendering cannot change
   field presence. No new post-render structural validation exists — rendered
   strings flow to the checks that already exist (env-key legality at wrapper
   generation, compilation validation of the merged result). Merge rules, the
   global-run-settings boundary, feedback surfaces, and byte-identical
   composition for template-free contributions stay as-is.

## Considered options (rejected)

- Rendering all contributions after the walk, before the merge — would run
  later tools' hooks after an earlier contribution is already broken,
  breaking the "first failing tool stops everything" discipline.
- Enumerated field-list rendering — a per-field list drifts as the workflow
  model grows; the type-driven law parallels the merge's field-set-complete
  principle ("a new stage field flows through without touching this cell
  again").
- Later-wins on rendered-key collisions (PyYAML parity) — silently losing a
  whole stage override is a surprise; the product's strict actionable pre-run
  discipline prefers the error.

## Consequences

- Contributed strings become template surfaces: a tool whose strings carry
  literal `{{ }}` today will see them render — the intended and only
  behavior change.
- A template error in a never-merging global field fails the run: the tool's
  template is broken regardless of where the string sits.

## Unresolved questions (for design/plan, outside this record)

- Which zone owns the field-level rendering routine and the profile-fact
  wiring, and the concrete contracts and signatures — not decided here.
- Where the tool-author documentation of the amendment contract lives (the
  profile fact and the rendering rule).
