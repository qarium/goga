# Profile-aware workflow contributions from pipeline hooks

## Current State

The authored workflow-file is profile-aware: the workflow cell resolves the
contributor profile (CLI flag > environment variable > workflow default;
project lookup wins over home) and renders the whole file as a Jinja
template with that profile's content before parsing. The amendment layer of
the pipeline domain hooks is profile-blind in two ways:

1. the amendment view delivered to a subscribed tool's
   `pipeline.amend_workflow` hook carries no profile fact — tool code
   cannot learn which profile is active, on any activation channel,
   including the home-profile bundle it cannot see;
2. a committed contribution has no rendering step — Jinja template syntax
   in a contributed string lands in the effective workflow literally.

Both delivery forms already resolve the profile through the same loading
chain — the resolution result carries the resolved profile value (name,
content, source, or absence) next to the parsed document — but the value
stops there: the amendment checkpoint is reached without it. The merge that
follows the amendment, the empty-contribution check, the global run-settings
boundary, and the feedback surfaces are settled and work as specified; none
of them is affected by the profile blindness.

The tool-author documentation of the amendment contract does not mention a
profile fact or a rendering rule — the capability has no authoring
vocabulary today.

## Description

Make the workflow amendment layer profile-aware, exactly per the settled
decisions of the ADR (`add-tpl-to-workflow-hooks`, 2026-11-19):

1. **Profile fact on the amendment view.** The view delivered to each
   subscribed tool gains the operation's already-resolved active
   contributor profile as a read-only fact — the profile that rendered the
   authored file: its name, its whole content, and its source (project or
   home). The fact is operation data passed in by the caller: no reads and
   no re-resolution happen at the checkpoint. It is identical for every
   tool (the mutually-blind-tools rule extended to it), identical in the
   run and the card delivery forms, and reads as absent when no profile is
   active — including the no-workflow silent-miss case (activation without
   a workflow in effect is ignored by the existing rule).
2. **Field-level rendering of contributions.** Every string of a committed
   contribution — every string leaf and every string mapping key at any
   depth of the contributed workflow document, including the extend-stage
   bodies and the never-merging global fields (`profile`, `build`, `agent`,
   `env`) — renders as a Jinja template with the active profile's content
   before the authored-wins merge. Non-string scalars are not template
   surfaces. Rendering uses the same fixed template environment and the
   same context rule as the workflow-file render: the context is exactly
   the active profile's content (empty without activation), with no
   ambient variables (tool, pipeline, workflow name); there is no separate
   contribution dialect.
3. **Render at the tool's commit, inside the walk.** A tool's contribution
   renders at its commit moment in the delivery walk; a render failure is
   disciplinarily a hook failure — the first failing tool stops the
   command pre-run with a clean error, and later tools' hooks never run.
   The tool's whole contribution is discarded.
4. **Failure format.** A template error anywhere in a contribution — dead
   fields included — is one hard pre-run failure in the existing
   amendment-failure format (naming the hook, the tool, and the action)
   carrying the template cause: the error class, the message, and a
   document path — the dot-path of the string within the contribution
   built from the source (pre-render) keys, with list elements indexed and
   the gates fields disambiguated positionally (the workflow-level gates
   settings block path vs a stage check-step list path). A rendered-key
   collision inside one contribution map (two distinct source keys
   rendering to the same result key) is the same hard failure naming the
   tool, the map, the source keys, and the colliding result.
5. **Everything else unchanged.** Rendering runs before the
   empty-contribution check; that check stays presence-based and
   unchanged, and rendering cannot change field presence. No new
   post-render structural validation exists — rendered strings flow to the
   checks that already exist. The merge rules, the global-run-settings
   boundary, the notification and event hook actions, the feedback
   surfaces, and the byte-identical composition of template-free
   contributions stay as-is.

From the moment the change lands, contributed strings are template
surfaces: a tool whose contributed strings carry literal template syntax
today (previously inert text) will see them render. This is the intended
behavior change and its only one.

## Scope

**In scope:**

- The read-only active-profile fact (name, content, source, or absence) on
  the amendment view, identical for every tool, delivered in both the run
  and the card forms.
- The wiring that passes the operation's already-resolved profile value
  from the workflow resolution into the amendment checkpoint in both
  delivery forms.
- The field-level template rendering of every string of a committed
  contribution with the active profile's content, applied at the tool's
  commit inside the delivery walk, before the merge, under the
  workflow-file rendering semantics (same environment, same context rule).
- The hard-failure behavior for template errors in contributions:
  pre-run stop, the existing amendment-failure format plus the template
  cause (error class, message, document path), and the rendered-key
  collision failure.
- The tool-author documentation of the amendment contract — the profile
  fact and the rendering rule — so the capability reaches its primary
  user.
- The update of the project-level jinja2 usage file for the new
  field-level rendering surface (completed during task formulation — see
  External Dependencies).

**Out of scope:**

- Any change to the profile mechanism itself: activation precedence,
  lookup locations, the strict name grammar, profile-file management,
  home-bundle carriage.
- The build path (no amendment layer there; its workflow rendering stays
  as-is).
- A whole-document-text contribution path (rendering is field-level only)
  and any re-rendering of the authored workflow at amendment time.
- Any change to the merge rules and precedence (authored-wins overlay,
  globals exclusion, whole-block and append/dedup rules).
- Changes to other hook actions: the soft notifications (`run_created`,
  `run_completed`) and the bridged run/stage events gain no profile facts.
- New CLI commands or flags, per-tool or per-contribution profile
  selection, and new feedback surfaces (no render previews or diffs).

## Acceptance Criteria

- **Profile-visible amendment.** A subscribed hook reads the active
  profile's name, content, and source on its view when a profile is active
  (any activation channel — CLI flag, environment variable, workflow
  default), and reads absence when none is active (including the
  no-workflow silent-miss case) — identically in the run and the card
  forms.
- **Profile-aware contribution.** A contributed document carrying template
  syntax in its strings (values and mapping keys alike, at any depth —
  stage and extend-stage fields, assistant entries, memory, delegation,
  repeat, gates blocks, and the global fields) has those strings rendered
  with the active profile's content in the effective workflow, observable
  in the card's merged composition and in the compiled flow the run
  executes.
- **Uniform effect.** With a profile active, the authored workflow text
  and the contributed strings render against the same profile content —
  one activation shapes the whole effective workflow.
- **Parity semantics.** Without an active profile, a templated
  contribution renders against an empty context (missing keys render
  empty), matching the workflow-file render behavior exactly.
- **Strict failures.** A contributed string with a template error stops
  the command pre-run: the existing amendment-failure format (hook, tool,
  action) carries the template cause (error class, message, document
  path); nothing compiles, writes, or launches; the tool's whole
  contribution is discarded; later tools' hooks never run. A rendered-key
  collision inside one contribution map fails the same way naming the
  tool, the map, the source keys, and the colliding result.
- **Backward compatibility and boundaries.** A contribution without
  template syntax composes the effective workflow byte-identically to the
  current product, with or without an active profile; a contribution
  carrying only global run settings still counts as empty and is discarded
  (rendering included, before the unchanged presence-based check); the
  authored-workflow fact of the view stays the post-decision,
  post-skip-merge, pre-layer document; the notification and event hook
  actions are unchanged; the run feedback line, the card, and the run
  events carry no new surfaces.
- **Regression safety.** The existing test suite of the affected cells
  passes; new tests mirror the source structure per the project
  convention.

## Stack

- **Frameworks:** none beyond the existing project baseline (Python 3.10+
  package `goga`, stdlib `dataclasses` with `kw_only=True` per convention)
- **Libraries:** jinja2 >= 3.1 (existing dependency; one fixed template
  environment — `trim_blocks`, `lstrip_blocks`, `keep_trailing_newline`,
  the standard `Undefined`, `autoescape=False` — shared by the whole-file
  render and the new field-level render)
- **Infrastructure:** none (no databases, brokers, or new services);
  pytest / ruff from the existing test extra

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| jinja2 | `.goga/usages/cooks/jinja2.md` | updated (this task formulation: added the field-level contribution-rendering pattern, extended the domain, rescoped the parsed-document anti-pattern) |

No new external dependencies. No synced usage files participate in the
task. Synced usage files are managed by `goga usages sync` — reference them
read-only, never create or update them in the task.

## Risks and Constraints

- **Behavior change for legacy contributions.** Contributed strings become
  template surfaces; a tool whose strings carry literal template syntax
  today will see them render (or fail). This is intended and must be
  called out in the tool-author documentation.
- **Render-failure discipline.** The first failing tool stops the command
  pre-run; the implementation must not run later tools' hooks after an
  earlier contribution fails to render (rendering belongs at the commit,
  inside the walk — not as a post-walk pass).
- **Zone ownership is open.** Which cell owns the field-level rendering
  routine and the profile-fact wiring (the hooks zone, the workflow
  profile zone, or a split), and the concrete contracts and signatures,
  are unresolved questions of the ADR, deliberately left to the design
  stage. This task must not presuppose an answer.
- **Documentation placement is open.** Where the tool-author documentation
  of the amendment contract lives (the pipeline cell tool-author practices
  that document the amendment view today, or the hooks cell practices) is
  an unresolved question of the ADR for the design stage.
- **Parity, not a dialect.** The rendering must reuse the workflow-file
  rendering semantics exactly — one environment, one context rule; a
  contribution-specific template dialect violates a product consistency
  rule.
- **Strict pre-run failures only.** All new failure modes are pre-run
  strict failures with actionable messages; humans and CI see identical
  behavior; nothing partial executes.
- **Run/card equivalence.** Both delivery forms must carry the same fact
  and the same rendering; the card's merged composition equals what the
  run would execute.

## Scope Estimate

Single task — one semantic capability (the profile-aware amendment) across
three tightly coupled cells sharing one wiring path; no decomposition, no
additional topics created.

## Existing Architecture

Affected cells and their integration points (facts from the current
schema; boundary decisions belong to the design stage):

- **`goga/pipeline/workflow`** — owner of the contributor-profile zone:
  the resolved profile value (name, content, source, or absence), the
  profile source vocabulary (project / home), the loading chain that
  returns the parsed document together with the active profile, and the
  whole-file Jinja rendering of workflow-files before parsing. The fact
  delivered to the amendment view is this zone's already-resolved value;
  the whole-file render is the parity reference for the new field-level
  render (same environment flags, same context rule).
- **`goga/pipeline/hooks`** — owner of the amendment zone: the
  read-and-contribute view of one tool (the delivered facts and the
  contribution buffer — gains the profile fact), the checkpoint surface
  that walks the subscriptions per tool and commits each tool's
  contribution (gains the render-at-commit step and the extended failure
  format), and the authored-wins overlay merge that consumes the rendered
  contributions unchanged.
- **`goga/pipeline`** — owner of both delivery forms: the workflow
  resolution that returns the parsed document plus the active profile, the
  run coordination, and the card composition. Both forms deliver the
  amendment with the same facts through the checkpoint surface; both gain
  the wiring that passes the resolved profile value into the delivery.

The overlay merge, the compilation validation, the wrapper generation, and
the feedback surfaces are consumers of the rendered contributions exactly
as of today's raw ones — no changes there.

## Notes

- Input documents: the PRD (`prd.md`) and the ADR (`adr.md`) of this topic
  — the ADR is the normative source for the settled decisions; the task
  restates them without adding new ones.
- The project-level jinja2 usage file was updated during task formulation
  (this stage) to cover the field-level rendering surface; the tool-author
  documentation of the amendment contract remains implementation work in
  scope of the task.
- Per stage constraints this document carries no code examples and fixes
  no architecture: signatures, cell ownership of the new routine, and
  documentation placement are design-stage questions.
- The document-path vocabulary for template failures: dot-paths over the
  source (pre-render) keys, list elements indexed, the two gates shapes
  disambiguated positionally — pinned in the ADR interview and reused
  verbatim here.
