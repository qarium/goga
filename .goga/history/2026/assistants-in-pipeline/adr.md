# Pipeline-stage assistant declarations: immediate attachment, origin-aware workflow governance

A pipeline-file author declares a stage's helper assistants in the stage body
itself (full declarations: `prompt`/`skills` content plus `when`/`gate`
engagement; delivery keys stay workflow territory), and every declaration
attaches to its own stage on every run — with a workflow-file or without one.
A workflow governs the shipped assistants through
`stages.<stage>.assistants.<name>` entries keyed by the name's origin:
`{skip: true}` vetoes one pipeline declaration; any other entry is an additive
extension (`when`/`gate` override, `agent`/`env`/`delegate` configure
delivery, `prompt` appends, `skills` expands). We chose this over keeping the
workflow as the single authoring surface because a stage that needs a helper
otherwise forces every consuming project to re-author the helper's content in
its own workflow, and runs without a workflow-file could attach nothing at
all. Source PRD: `prd.md` in this topic directory.

## Considered options

- **Syntactic extension marker** — a key distinguishing extensions from
  references/inline declarations, keeping the `when`-required check at parse
  time. Rejected: the workflow parser is deliberately pipeline-blind; a name's
  origin is knowable only where both documents meet (compilation), and a marker
  adds vocabulary without adding meaning.
- **`skip` as a general attachment veto** — also canceling catalog/inline
  attachments on a stage. Rejected: not authoring an attachment already
  governs those; `skip` is exclusively the veto over what the pipeline ships.
- **A separate key name for the assistant-level veto** (e.g. `veto`) —
  rejected: `skip` keeps one word for one semantic (remove the entity) at two
  positions (stage level, assistant level), disambiguated by position.

## Consequences

- **The `when`-required check moves to compilation for every attachment.**
  The parser accepts a when-less entry (it may be an extension of a pipeline
  declaration); the compiler raises the `when is required` error for entries
  naming no pipeline declaration of that stage — including ordinary references
  and inline declarations. The error shifts from parse-time to compile-time;
  this is the accepted cost of marker-less extensions.
- **Extension entries preserve field absence.** Omitted `when`/`gate` inherit
  the pipeline values; an explicit `gate: false` deliberately downgrades a
  gated assistant to advisory — so absence and authored `false` must stay
  distinguishable on the attachment model. A lone `skip: false` and an empty
  entry `{}` are structural errors: every entry carries exactly one meaningful
  instruction (the veto alone, or at least one extension field).
- **Extended prompts join with a blank line** — pipeline text, one blank line,
  workflow text; a workflow-only text stands alone with no leading separator.
  Fixed for byte-exact output.
- **Ordering: the pipeline body is the base, the workflow is the overlay.**
  Within a stage's compiled attachment list, pipeline declarations come first
  (pipeline authored order), then workflow attachments (workflow authored
  order) — the same pipeline-first rule as skills expansion and prompt append.
  The team list is deliberately the opposite: catalog members in authored
  order first, then pipeline-declared members in pipeline body stage order
  (loop-expanded copies collapse to their base stage's first occurrence).
- **Skills delivery parity is with the catalog, not with workflow inline
  declarations.** Pipeline-declared assistants become team members, so their
  skills reach the engine through the team entry; workflow inline declarations
  keep their existing compile-time WARNING (no skills channel) — the existing
  collaboration model is unchanged, deliberately.
- **The effective namespace spans catalog, inline, and pipeline declarations**
  — one global uniqueness domain; a catalog-vs-pipeline name collision is a
  structural error at compilation, as are tool-delivered overlay collisions
  under the same rules. Pipeline declarations are visible only to their own
  stage's workflow entry; workflow extend-entries stay assistant-free.
- Assistant-free pipelines and workflow-only collaboration models compile
  byte-identically to today's output (the non-regression guarantee).
