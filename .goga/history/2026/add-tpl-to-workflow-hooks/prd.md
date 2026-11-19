# Profile-Aware Workflow Contributions from Pipeline Hooks

## Problem

Tool-package authors who contribute workflow content through the
`pipeline.amend_workflow` hook cannot make that content profile-aware.

The authored workflow-file is rendered with the active contributor profile
before parsing: a contributor activates a profile once (`--profile` flag,
`GOGA_PROFILE` environment variable, or the workflow's own `profile:` default),
and every template expression in the authored file renders against that
profile's content. The amendment layer, however, is profile-blind in two ways:

1. the amendment view delivered to a tool's hook carries no profile facts —
   tool code cannot even learn which profile is active, on any activation
   channel, including the home-profile bundle it cannot see;
2. the contributed document has no rendering step — Jinja template syntax in a
   contributed string lands in the effective workflow literally instead of
   rendering.

As a result, the effective workflow of a run mixes profile-aware authored
instructions with profile-blind tool-contributed instructions. Teams that need
tool contributions to vary by profile cannot express it and resort to
per-profile forks of workflows or tool packages, or drop the tool integration
entirely. The prevented outcome: one profile activation shaping the whole
effective workflow — authored and tool-contributed parts alike.

## Users

**Primary user — the tool-package author.** Maintains a goga tool package that
subscribes to `pipeline.amend_workflow` and writes the hook code that builds
the contribution. Knows the workflow grammar and the profile concept; today
can only contribute fixed content. Wants one authoring vocabulary shared with
workflow authors, strict actionable pre-run failures, and no need to
reimplement profile resolution (the CLI channel and the home bundle are
invisible to tool code) inside the tool.

**Secondary actor — the pipeline contributor.** Runs `goga pipeline <name>`
(or reads the card with `--info`) with a profile activated. Expects the whole
effective workflow — authored and tool-contributed — to follow the activated
profile, with the same predictable strict pre-run failures and truthful
feedback lines the product already gives.

**Secondary actor — the workflow/profile author.** Owns the project's profile
files and workflow files, and with them the profile data model ("defined
solely by what the workflow's templates read"). Expects profiles to remain
free-form mappings and the rendering semantics to stay identical to the
workflow-file render — tool templates are simply another reader of the same
data model.

## Goals

1. **Profile-aware contributions.** A tool-package author can make amendment
   contributions follow the active contributor profile using the same profile
   vocabulary and rendering semantics the authored workflow-file already uses.
2. **Profile visibility for tool code.** A tool's hook can read the active
   contributor profile at the amendment moment, so programmatic contributions
   can branch on it without reimplementing profile resolution.
3. **Uniform profile effect.** For the pipeline contributor, one profile
   activation shapes the entire effective workflow — authored and
   tool-contributed instructions alike — under the product's existing strict
   pre-run failure discipline.

## User Experience

### Entry points

Two entry points meet in the same composition moment:

- the **tool-package author** writes the hook subscribed to
  `pipeline.amend_workflow` (authoring experience);
- the **pipeline contributor** runs `goga pipeline <name>` or views the card
  with `--info` while a profile is active (consumption experience).

### Primary scenario — authoring a profile-aware contribution

The tool author's hook receives the amendment view as today. The view now also
carries the operation's active contributor profile as a read-only fact: its
name, its content, and its source (project or home). When no profile is active,
the fact reads as absent. The author uses it in two complementary ways:

- **programmatic branching** — hook code reads the profile fact and decides
  what to contribute;
- **templated content** — the hook builds the contribution as today
  (programmatically, as a workflow document), and any string inside it may
  carry Jinja template syntax (`{{ ... }}`, `{% ... %}`); the platform renders
  those strings with the active profile's content before the merge, with the
  same semantics the workflow-file render uses.

The rendered contribution then merges onto the authored workflow under the
existing authored-wins rules — rendering changes what the strings say, never
how the merge decides.

### Primary scenario — running with a profile

The contributor activates a profile by any existing channel and runs the
pipeline (or opens the card). The authored workflow renders with the profile
exactly as today; the tool contributions' templated strings render with the
same profile content; the run executes — and the card displays — one effective
workflow shaped by that single activation. Feedback surfaces do not change:
the run line still names the resolved workflow and profile, the card still
reports the contributing tools, and the run events still carry the provenance.

### Alternative states

- **No workflow resolved (silent auto-match miss).** The amendment still fires
  onto the empty base. No profile is active (activation is ignored entirely
  without a workflow — existing rule): the profile fact reads as absent, and
  templated contribution strings render against an empty context, exactly as a
  workflow-file renders without activation.
- **Workflow disabled (`--no-workflow`).** The amendment is not delivered at
  all — unchanged.
- **No tools subscribed.** The layer stays the passthrough — the workflow
  composes exactly as passed, byte-identical.

### Failure behavior

- **A template syntax or rendering error inside a contributed string** fails
  the amendment hard, under the existing hard-failure contract: the command
  stops before any compile, write, or launch; the error follows the existing
  amendment-failure format (naming the hook, the tool, and the action) and
  carries the template cause (error class, message, and location) so the tool
  author can fix the template; the tool's whole contribution is discarded and
  nothing partial executes.
- **A contribution that is (or renders to) an empty document** remains a
  content no-op: a warning names the tool, the contribution is discarded, the
  walk continues.
- Recovery is re-run after fixing: contributions are transient per-run
  composition events — nothing persists between runs, and re-running
  deterministically re-delivers and re-renders.

### Consequences

Contributed strings are template surfaces from the moment the change lands: a
tool whose contributed strings contain literal `{{ }}` today (previously
inert text) will see them render. This is the intended behavioral change and
its only one — contributions without template syntax compose exactly as
before.

## Requirements

### A. The profile fact on the amendment view

1. The amendment view delivered to each subscribed tool must expose the
   operation's active contributor profile — its name, its content, and its
   source (project or home) — as a read-only fact, identical for every tool
   (the mutually-blind-tools rule extended to the new fact).
2. When no profile is active for the operation — no activation resolved, or no
   workflow in effect — the fact must read as absent.
3. The fact must be available identically in both forms that deliver the
   amendment: the run form and the card form.

### B. Profile-aware rendering of contributions

4. Every string inside a contributed workflow document — values and mapping
   keys alike, wherever they sit (the top-level prompt; stage and
   extend-stage fields such as prompt, agent, env values, skills entries,
   notes; assistant catalog and per-stage attachment entries including their
   prompt, skills, agent, delegate, and env values; the string leaves of the
   memory, delegation, repeat, and gates blocks) — must be rendered as a
   template with the active profile's content before the contribution merges.
   Non-string values are not template surfaces.
5. Rendering must follow the workflow-file rendering semantics exactly: the
   same template environment behavior; a missing profile key renders as
   empty; no active profile renders against an empty context (template syntax
   still processes); there is no separate contribution-specific dialect.
6. Rendering must not alter merge semantics: the authored-wins overlay rules,
   the per-key stage env fill, the assistant field-level overrides, the
   whole-block rules, and the append/dedup rules operate on the rendered
   contribution exactly as on today's raw one.

### C. Failure behavior

7. A template syntax or rendering failure inside a contributed string must
   fail the amendment hard: the command stops pre-run before any compile,
   write, or launch; the error names the hook, the tool, and the action in the
   existing amendment-failure format and carries the template cause (error
   class, message, location); the tool's whole contribution is discarded.
8. A contribution that renders to an empty document remains a content no-op:
   a warning names the tool; the contribution is discarded; the walk
   continues.

### D. Boundaries preserved

9. The global-run-settings boundary is unchanged: contributed `profile`,
   `build`, `agent`, and `env` (workflow-level) never reach the effective
   workflow — rendering included — and a document contributing only them
   still counts as empty and is discarded.
10. The authored-workflow fact of the amendment view remains the post-decision,
    post-skip-merge, pre-layer authored document — read-only, identical for
    every tool, and never re-rendered by the amendment.
11. A contribution whose strings carry no template syntax must compose the
    effective workflow byte-identically to the current product, with or
    without an active profile; existing tool packages keep working unchanged.

### E. Feedback

12. The composition feedback surfaces stay unchanged: the run feedback line
    names the resolved workflow and active profile as today; the card reports
    the merged composition and the contributing tools as today; run events
    carry the provenance as today. The rendered contribution reaches the
    contributor only through the resulting effective workflow (the card and
    the compiled output) — no new dedicated surfaces.

## Constraints

1. **Backward compatibility.** A tool whose contributed strings carry no
   template syntax composes byte-identically to today, with or without an
   active profile. The only intentional behavior change is for contributions
   carrying template syntax.
2. **The amendment stays hard and content-only.** Contributions shape the
   effective workflow; they cannot cancel, redirect, or defer the run; the
   first failing tool stops the command pre-run. Profile support must not
   weaken or bypass this.
3. **Global run settings are workflow-author territory.** Workflow-level
   `profile`, `build`, `agent`, `env` can never be supplied or overridden by a
   contribution — a rendered value landing in those fields still never merges.
4. **The profile mechanism itself is untouched.** Activation precedence
   (CLI > environment > workflow default), the two lookup locations (project
   wins over home), the strict name grammar, and the strict pre-run profile
   failures stay as-is; the change only consumes the already-resolved
   profile.
5. **Activation requires a workflow in effect.** Without a resolved workflow
   no profile is active — the amendment view's profile fact reads absent and
   contributed templates render against an empty context. The change must not
   introduce profile activation for the no-workflow case.
6. **Mutually blind tools.** Every tool reads the same original facts — the
   authored workflow and now the profile — through its own view; no tool ever
   sees another tool's contribution.
7. **Rendering parity.** Contribution rendering uses the same template
   semantics as the workflow-file render — one vocabulary, no separate
   dialect (a product consistency rule, not an implementation choice).
8. **Run and card forms behave identically.** Both deliver the same amendment
   with the same profile facts and the same rendering; the card's merged
   composition equals what the run would execute.
9. **Strict pre-run failure discipline.** All new failure modes (template
   errors in contributions) are pre-run strict failures with actionable
   messages — nothing partial executes; humans and CI see identical behavior.
10. **The build path is untouched.** The build workflow loading has no
    amendment layer; its profile rendering stays as-is. The change is scoped
    to the pipeline amendment.

## Scope

### In Scope

- The read-only active-profile fact (name, content, source, or absence) on
  the amendment view, in both the run and card forms.
- Field-level template rendering of contributed documents' strings with the
  active profile's content, before the merge, under workflow-file rendering
  semantics.
- The hard-failure behavior for template errors in contributions (pre-run,
  existing error format plus the template cause).
- The wiring that makes the operation's already-resolved profile available at
  the amendment checkpoint in both delivery forms.
- The tool-author documentation of the amendment contract (the profile fact
  and the rendering rule) so the capability reaches its primary user.

### Out of Scope

- Any change to the profile mechanism itself: activation precedence, lookup
  locations, name grammar, profile-file management, home-bundle carriage.
- The build path (no amendment layer there; its workflow rendering already
  works as-is).
- A whole-document-text contribution path (rendering is field-level only).
- Re-rendering the authored workflow at amendment time (it is already
  rendered at load; the amendment never re-renders it).
- Any change to the merge rules and precedence (authored-wins, globals
  exclusion, whole-block and append/dedup rules).
- Changes to other hook actions: the soft notifications (`run_created`,
  `run_completed`) and the bridged run/stage events do not gain profile
  facts.
- New CLI commands or flags, per-tool or per-contribution profile selection,
  and new feedback surfaces (no render previews or diffs).

## Success Criteria

1. **Profile-visible amendment.** A subscribed hook reads the active
   profile's name, content, and source on its view when a profile is active
   (any activation channel — CLI flag, environment variable, workflow
   default), and reads absence when none is active (including the
   no-workflow silent-miss case) — identically in the run and card forms.
2. **Profile-aware contribution.** A tool whose contributed document carries
   template syntax in its strings (e.g. a stage prompt reading
   `Model: {{ model }}`) has those strings rendered with the active profile's
   content in the effective workflow — observable in the card's merged
   composition and in the compiled flow the run executes.
3. **Uniform effect.** With a profile active, the authored workflow text and
   the tool-contributed strings render against the same profile content —
   one activation shapes the whole effective workflow.
4. **Parity semantics.** Without an active profile, a templated contribution
   renders against an empty context (missing keys render empty), matching the
   workflow-file render behavior exactly.
5. **Strict failures.** A contributed string with a template syntax error
   stops the command pre-run with the existing amendment-failure format
   (hook, tool, action) carrying the template cause; nothing compiles,
   writes, or launches; the tool's whole contribution is discarded.
6. **Backward compatibility and boundaries.** With no profile active, a tool
   contribution without template syntax composes the effective workflow
   byte-identically to the current product; a contribution carrying only
   global run settings is still discarded as empty; the authored-workflow
   fact stays the pre-layer document; the notification and event hook
   actions are unchanged.
