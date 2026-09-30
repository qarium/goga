---
status: accepted
date: 2026-09-29
---

# Topics publish command, tool config loading standard, and schema validation gate

Three decisions in one scope, reached through a design-tree interview: a standalone
command that publishes an existing topic branch, a read-side counterpart to the
onboarding tool-config write standard, and a validation hook for the final schema.

## Decision 1 — `goga topics publish` reuses `topic_published` as a publication-centric event

Add `goga topics publish [IDENTIFIER]` — delivery of an **existing** topic branch to
origin. Addressing mirrors `update`/`propagate` exactly (optional IDENTIFIER defaults
to the current topic; a branch hosting no topic is a clean error naming the branch; a
remote-only own branch is a clean error hinting `goga topics switch`; no new config
keys). The operation runs a targeted fetch of its own origin twin (one stdout report
line), then resolves one of four deterministic outcomes:

| origin twin vs local tip | Outcome |
|---|---|
| twin absent | `push_branch` creates it — **pushed** |
| twin == tip | success, nothing to do — **up-to-date** |
| twin strictly ahead (contains tip) | success, nothing to push — **remote-ahead** |
| diverged (neither contains the other) | clean error naming both tips; reconcile manually via git, re-run |

**Why.** `remote-ahead` must not be an error: the remote already carries the local
work, and rejecting it would force the user into an unnecessary action. Publish is
delivery, never history rewriting — no force, no lease, ever (lease protection
belongs to `update` after a rebase). No confirmation is asked (the push is the
explicitly requested action) and a dirty working tree is irrelevant to a push.
`origin_configured == False` is a clean error, as in `update`. The result is exactly
one stdout line distinguishing the three success kinds.

**Event.** Reuse the existing soft action `topics/topic_published` — no new action —
with the context reshaped to be **publication-centric**: what matters is the
publication itself and its facts, not which operation invoked it. The context carries
`identity` (slug, year, branch as entered), `remote_branch` (the origin branch that
received the delivery — the topic's own twin, or the base branch for propagate),
`commit_hash` and `commit_message` (facts of the commit the remote branch carries
after the operation), and `outcome` — a `str` with a fixed kind set
(`pushed | up-to-date | remote-ahead`), following the domain's existing convention of
documented outcome kinds rather than enum types. `todo` is removed: it is creation
context, not publication context.

Emission happens on **every completed publication, including idempotent outcomes** —
holding the zone's precedent that `already-current` and `nothing-to-do` emit — at
every site that publishes: `publish_topic` (as today), the new `publish` command,
`update --publish`, and `propagate` (whose inherent push is a publication; outcome
there is always `pushed`).

### Considered options

- A new `topics/topic_pushed` event — rejected: the publication moment already has
  its address; reuse keeps one vocabulary.
- Keeping the creation-specific required fields (`commit_message`, `todo` always
  present) — rejected: a standalone publish builds no commit, and the invocation
  moment must not shape the context. `commit_message` stays only because it is a git
  fact of the published commit, symmetric with `commit_hash`.
- Emitting only on actual pushes (variant "fact event", no `outcome` field) —
  rejected: a repeated publish then gives subscribers no idempotent
  "work is on origin" signal.

### Consequences

- The `TopicPublished` context is a breaking reshape for existing subscribers of
  `topics/topic_published`: `todo` disappears; `remote_branch` and `outcome` appear.
- The topics contract's sanctioned network set gains the publish command's targeted
  fetch and publication push.

## Decision 2 — `load_tool_config` on the `goga/config` facade plus a `config` injection in the tool dispatcher

The onboarding engine is today the single writer of the tool-config standard
(`write_config` buffers verbatim filenames into `.goga/tools/<tool>/<file>`); reading
gets its standard counterpart:

- `load_tool_config` — a library procedure on the `goga/config` facade. The loader
  owns **path standardization only**: compose `.goga/tools/<tool>/<filename>` with
  `filename` taken verbatim (with extension, exact match — the same standard as the
  writer), requiring flat name segments (non-empty, no separators, no `..` —
  traversal protection), a violation being a clean error. An absent file returns
  `None` — absence is the normal state for a tool config. A present file returns the
  **raw parsed data as-is**: a mapping, a string, a list — whatever the YAML parses
  to is what the caller gets. No models, no content validation, no structural
  expectations, no merging with Project/Home/amend layers, no cache; an optional
  path override exists for tests. Interpreting the content is the tool package's
  responsibility, not the loader's.
- The `goga tool` dispatcher offers a **second optional injection beside `ast`**: a
  tool entry point that declares a parameter named `config` receives, lazily and as
  a keyword argument, the loaded `.goga/tools/<tool>/config.yml` — raw data as-is or
  `None` when absent. The offered-injection set stays the single source of opt-in;
  a parameter with any other name never triggers a load.

**Why.** The write side already fixes the standard; the read side must follow it
verbatim rather than inventing suffix rules. Raw passthrough keeps every decision
about content with the tool that owns it. Inside a tool package the name `config` is
unambiguous — the `tool_` prefix would imply some other config could appear there.

### Considered options

- `ValueError` on non-mapping content — rejected: "raw" means as-is; a type check
  would be the thin end of content validation.
- Parameter name `tool_config` — rejected (see above).
- Injecting into the dispatcher without the library procedure — rejected: tools with
  other filenames still need the standard read path.

## Decision 3 — `schema/validate_schema`, a hard validation gate mirroring `validate_build`

Add the validation hook event to the schema domain as
`schema/validate_schema` — **named by project precedent**: the only existing validate
action is `build/validate_build`, and the amend pattern is verb+object
(`amend_cell`, `amend_workflow`, `amend_config`); both readings converge on
`validate_schema`. Where a precedent exists it is already a forming pattern and is
followed rather than diluted. Error class is **hard**; the catalog record is added
additively.

Delivery mirrors `validate_build` exactly, including its recorded domain-local
deviation: the walk runs **to completion** — never stopping at the first failure —
producing exactly one `Violation` per tool (tool, hook, reason); a crashed hook is a
veto of its tool carrying the failure reason. On failure nothing is printed to
stdout, one merged error listing every violation goes to stderr, exit code 1. With
no subscriptions the schema is approved and the output is byte-for-byte unchanged.

The event fires **once over the final assembled tree** — after all `amend_cell`
contributions are merged and the cells/depends_on/max_depth filters are applied,
before serialization. Subscribers receive a read-only context view of the tree with
a veto method (not a JSON string). The validator deliberately sees the final result
**including the tools overlay** — a recorded exception to the "authored facts only"
rule, to be fixed explicitly in the schema contract. Observe-and-veto only: the tree
is never modified by a validator.

**Why.** The final schema is what consumers receive; validating the authored input
but not the delivered output would validate the wrong artifact.

## Glossary (fixed during the interview)

- **publish (flag)** — push of a topic branch as a step of another operation
  (`create --publish`, `update --publish`).
- **publish (command)** — delivery of an existing topic branch to origin as an
  operation of its own.
- **origin twin** — the remote-tracking counterpart of a topic's own branch on
  origin.
- **tool config** — a YAML file in `.goga/tools/<tool>/<filename>`, tool-specific,
  written only by the onboarding engine, opaque to the engine.
- **final schema** — the assembled JSON cell tree produced by `goga schema`,
  including the tools overlay.
- **outcome kind** — a `str` field with a fixed, documented value set (domain
  convention; not an enum type).

## Open questions (for the design and contract stages)

- Exact signatures, `location` values, cell boundaries, and Imports/Usages wiring
  for all three changes — out of the discover stage's scope by constraint.
- Migration note for existing `topics/topic_published` subscribers under the
  reshaped context (who currently consumes `todo`).
- Whether the board's divergence marker reuses the publish command's twin-vs-tip
  containment computation or keeps its own local-refs-only path.
