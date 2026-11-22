# Pipeline-stage assistant declarations

## Current State

Helper assistants are authored exclusively in the workflow-file. The
project analysis shows:

- The workflow-file carries the only authoring surfaces: the top-level
  `assistants:` catalog and the per-stage attachments
  `stages.<name>.assistants` (references, gated references, full inline
  declarations). Delivery keys (`agent`, `env`, `delegate`) are
  workflow-side.
- The compiler rejects an `assistants` key in a pipeline stage body with
  a structural error ("assistants key is forbidden in stage body; use
  assistants in workflow.stages") — in both body formats.
- The workflow parser enforces `when` on every stage attachment at parse
  time; assistant names are unique across the catalog and every inline
  declaration; `assistants` is forbidden in workflow extend-entries.
- The compiled team list draws from the workflow catalog alone; skills
  authored on inline declarations have no delivery channel and warn at
  compilation.
- The compiled flow is the single source of truth for profile
  generation; delivery resolves every referenced assistant's declaration
  from the workflow document's namespace only.
- The tool-delivered workflow amendment overlay merges under the
  existing namespace invariants.

Consequences a pipeline-file author faces today: a stage needing a
helper forces every consuming project to re-author the helper's content
in its own workflow; a run without a workflow-file can attach nothing;
and shipped assistants have no governance channel.

## Description

Implement the confirmed ADR (see `adr.md`; source PRD `prd.md` in this
topic directory): a pipeline-file author declares a stage's helper
assistants in the stage body itself — full declarations carrying the
helper's content (`prompt`, `skills`) and engagement (`when` required,
`gate` optional, default false); delivery keys stay workflow territory
and authoring them is a structural error. Every declaration attaches to
its own stage on every run — with a workflow-file or without one
(including `--no-workflow`).

The workflow governs shipped assistants through
`stages.<stage>.assistants.<name>` entries keyed by the name's origin:

- a `{skip: true}` entry vetoes exactly one pipeline declaration of that
  stage — no compiled attachment, no team member, no generated profile;
  the stage itself still runs;
- any other entry is an additive extension: `when`/`gate` override the
  pipeline values (omitted keys inherit; an explicit `gate: false`
  deliberately downgrades), `agent`/`env`/`delegate` configure
  delivery, `prompt` appends to the pipeline text (pipeline text first,
  one blank line, then the workflow text), `skills` expands the pipeline
  list (pipeline entries first, then workflow entries, deduplicated by
  value);
- a name matching no pipeline declaration of that stage keeps the
  existing attachment semantics unchanged (catalog reference or full
  inline declaration).

The `when`-required check becomes origin-aware and moves from the
workflow parser to compilation: the parser accepts a when-less entry (it
may extend a pipeline declaration), and the compiler raises the
"when is required" error for entries naming no pipeline declaration of
that stage — including ordinary references and inline declarations.

The effective assistant namespace spans catalog, inline, and pipeline
declarations — one global uniqueness domain; a collision between
sources is a structural error at compilation. Pipeline declarations are
visible only to their own stage's workflow entry.

Pipeline-declared assistants get catalog-parity delivery: they join the
compiled team list (catalog members in authored order first, then
pipeline-declared members in pipeline body stage order — loop-expanded
copies collapse to their base stage's first occurrence) and receive a
generated `goga-<name>` profile. Within a stage's compiled attachment
list, pipeline declarations come first (pipeline authored order), then
workflow attachments (workflow authored order) — the same pipeline-first
rule as skills expansion and prompt append. The team list order is
deliberately the opposite of the attachment order.

Full normative requirements (R1 authoring surface, R2 immediate
attachment, R3 delivery parity, R4 workflow governance, R5 consistency
and non-regression) and constraints (C1–C9) are defined in `prd.md`;
the decision record with rejected alternatives is `adr.md`. Both files
in this topic directory are normative inputs of this task.

## Scope

**In scope:**

- `assistants` authoring in pipeline-file stage bodies (both body
  formats: stages-map and phases-list) with full structural validation
  (vocabulary, name rules, content resolution, delivery-key rejection).
- Immediate attachment of pipeline-declared assistants, including runs
  without a workflow-file and loop-expanded stage copies; the existing
  attachment prohibitions apply (script-carrying and planning-only
  stages); a stage-level skip removes the stage and its assistants
  together.
- Workflow skip and extension semantics for pipeline-declared names:
  skip veto, `when`/`gate` override with absence preservation, delivery
  configuration (`agent`/`env`/`delegate`), prompt append with a blank
  line, skills expand with deduplication.
- Origin-aware `when` check at compile time; the parser accepts
  when-less entries.
- Global assistant-name uniqueness across the effective namespace
  (catalog, inline, pipeline declarations); stage-scoped visibility of
  pipeline declarations; extend-entries stay assistant-free.
- Delivery parity: team membership and ordering, skills delivery,
  generated profiles, agent resolution, env closures, collaboration
  block and delegation bounds applied uniformly.
- Consistency of the tool-delivered workflow amendment overlay with the
  extended namespace (same collision errors at compilation).
- Non-regression: assistant-free pipelines and workflows using only the
  existing collaboration model compile byte-identically to the current
  output; existing workflow-only behavior (catalog overrides including
  explicit-empty clears, inline declarations, references, delegation
  bounds) is unchanged.
- Updated authoring documentation for both surfaces
  (`docs/features/pipelines/`).

**Out of scope:**

- Authoring `agent`, `env`, or `delegate` in pipeline declarations.
- Run-level (global) assistant declarations in the pipeline-file.
- Cross-stage visibility of pipeline declarations or a shared
  pipeline-declaration namespace.
- Changes to the existing catalog/inline/reference model and its
  override semantics.
- Engine-side changes (new fields in compiled stage attachment entries,
  an engine-side skills channel) — the engine strict-parses stage
  attachment entries and accepts only the existing five keys.
- `assistants` in workflow extend-entries.
- Changes to delegation, gates, memory, or dashboard/UI behavior.
- New defaults for engagement or assistant content.

## Acceptance Criteria

From `prd.md` (SC1–SC6), restated:

- **SC1** A pipeline-file with a stage-declared assistant compiles and
  runs with no workflow-file present: the compiled flow carries the
  stage attachment entry with every field materialized (profile, title,
  instruction, mode, trigger mapped from the authored `when`/`gate`),
  a team member with the declared skills, and the profile for its id is
  generated.
- **SC2** A workflow `skip: true` on a pipeline-declared assistant
  yields a compiled flow with no attachment entry, no team member, and
  no profile for that name — while the stage itself still runs.
- **SC3** An extension entry yields the merged outcome observable in
  the compiled flow: overridden `when`/`gate`, configured
  `agent`/`env`, appended prompt (pipeline text first, then workflow
  text), expanded skills (pipeline entries first, then workflow
  entries, deduplicated); the stage's compiled attachment list orders
  pipeline declarations before workflow attachments, and the team list
  orders catalog members before pipeline-declared members
  (loop-expanded copies collapse to their base stage's first
  occurrence).
- **SC4** Every defined authoring mistake is rejected with a readable
  structural error naming the location, strictly before any run:
  delivery keys in a pipeline declaration, unknown keys, missing `when`
  where required, invalid `when` values, invalid/reserved/duplicate
  names (including a catalog-vs-pipeline collision), a content-free
  declaration, a lone `skip: false` or empty extension entry, skip of
  an unknown name, skip mixed with extension keys, assistants on
  script-carrying or planning-only stages, and `assistants` in an
  extend-entry.
- **SC5** An assistant-free pipeline and a workflow using only the
  existing collaboration model compile byte-identically to the current
  product output.
- **SC6** Existing workflow-only assistants (catalog references, full
  inline declarations) behave exactly as before, including skills
  delivery through catalog team membership (inline-declaration skills
  keep their existing compile-time WARNING — deliberately unchanged).

## Stack

- **Frameworks:** none (standard library only for models:
  `dataclasses` with `kw_only=True`, `pathlib`)
- **Libraries:** PyYAML (already a project dependency — pipeline and
  workflow parsing, flow serialization)
- **Infrastructure:** none (no databases, brokers, queues)

Language/runtime: Python 3.10+ per project convention. Testing and
lint: pytest (+ pytest-cov) and ruff per the project convention
practice; tests mirror the source structure.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| Project conventions (Python, tests, lint) | `.goga/usages/conventions.md` | existing |
| PyYAML serialization parameters | `.goga/usages/cooks/beautiful_yaml.md` | existing |
| afm engine contract (stage attachments, team members, mode/trigger vocabularies, profiles) | `.goga/usages/cooks/afm.md` | existing |

No new external dependencies. Synced usage files are managed by
`goga usages sync` — referenced read-only.

## Risks and Constraints

- The afm engine strict-parses compiled stage attachment entries and
  accepts only `profile`, `title`, `instruction`, `mode`, `trigger` —
  a `skills` key is rejected there; skills reach the engine only
  through team member entries. No engine-side changes are in scope.
- No compiler-side engagement defaults: `when` is always authored
  explicitly, `gate` materializes false, the compiled trigger is always
  written.
- Extension entries must preserve field absence: omitted `when`/`gate`
  inherit the pipeline values, an explicit `gate: false` downgrades —
  absence and authored `false` must stay distinguishable on the
  attachment model.
- The `when`-required check moves from parse time to compile time for
  every attachment — an accepted, deliberate cost of marker-less
  extensions; error wording and location naming must stay within the
  existing message conventions.
- Byte-exact non-regression (SC5) constrains serialization: prompt
  append joins with exactly one blank line; ordering rules are fixed
  (pipeline-first attachments, catalog-first team list); the compiled
  output for collaboration-free and workflow-only documents must not
  change.
- The parsed pipeline document mirrors the authored source —
  declarations are carried, source bodies never mutated; the workflow
  extension applies at compilation, output-side only.
- The `goga-<name>` profile-id scheme and the project-layer
  user-authored profile override channel are preserved.
- The tool-delivered amendment overlay must merge under the extended
  namespace rules — overlay collisions fail with the same structural
  errors at compilation.

## Scope Estimate

Single task. The feature is one behavioral thread crossing four cells
(authoring surface, attachment assembly, governance, delivery) whose
pieces do not deliver independent value separately; non-regression and
the acceptance criteria verify only on the assembled whole.

## Existing Architecture

Affected cells and their link connections:

- **`goga/pipeline/compiler`** (imports from `goga/pipeline/workflow`)
  — owns pipeline parsing (`parse_dsl`), the parsed pipeline document
  mirror, and compilation (`compile_flow`) with collaboration emission
  (team list, stage attachments, collaboration block). Gains: the
  stage-body authoring surface, pipeline-declaration carriage on the
  parsed document, origin-aware attachment assembly with the merge
  rules, the compile-time `when` check, the extended namespace checks,
  and the extended team emission.
- **`goga/pipeline/workflow`** (no dependencies; imported by compiler,
  hooks, pipeline, build, and commands cells — only the affected three
  consume its assistant model) — owns the workflow-file grammar
  (`parse_workflow`), the assistant and stage models. Gains: parse-time
  acceptance of when-less entries and absence-preserving attachment
  fields; its types flow to every consumer through the existing
  imports.
- **`goga/pipeline/hooks`** (imports from `goga/pipeline/workflow`) —
  owns the workflow amendment overlay merge. Gains: overlay
  consistency with the extended namespace — a tool contribution
  colliding with a pipeline declaration fails with the same structural
  errors at compilation; the overlay itself stays pipeline-blind. No
  new dependencies.
- **`goga/pipeline`** (imports from compiler, workflow, hooks) — owns
  run coordination and delivery (`write_afm_config`): profile
  materialization for flow-referenced ids, agent resolution, env
  closures, collaboration section authorship. Gains: declaration
  resolution across the effective namespace (workflow documents and
  pipeline documents), extended team delivery, authoring-site error
  naming.

Integration requirements: the compiler remains the single place where
the two documents meet (the workflow parser stays pipeline-blind); the
parsed pipeline document carries declarations without mutating source
bodies; delivery reads declarations from the compiled flow and the
effective workflow plus the pipeline document through the existing
interfaces. No new cross-cell imports beyond the existing directions;
no imports between cells that import each other.

Cell-level usage documents of the touched cells (e.g. `parse-dsl`,
`collaboration-emission`, `assistants`, `parse-workflow`) are updated
together with their CODEMANIFEST contracts in the downstream stages of
this workflow.

## Notes

- Normative inputs: `adr.md` (the confirmed decision record, including
  the seven interview decisions and the rejected alternatives) and
  `prd.md` (full requirements R1–R5, constraints C1–C9, success
  criteria SC1–SC6) in this topic directory.
- Per stage constraints, this task document deliberately contains no
  code examples and prescribes no internal architecture — contract
  shape, signatures, and type design belong to the downstream design
  stages.
- Deliberate non-parity recorded in the ADR: skills delivery parity is
  with the catalog, not with workflow inline declarations (inline
  skills keep their WARNING); the collaboration model is unchanged.
- Formulation confirmed by the user: scope and boundaries (question 1),
  stack and absence of new external dependencies (question 2), single
  task without decomposition (question 3).
