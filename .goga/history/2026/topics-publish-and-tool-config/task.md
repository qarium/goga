# Topics publish command, tool config loading standard, and schema validation gate

Source: the accepted ADR of this topic
(`.goga/history/2026/topics-publish-and-tool-config/adr.md`). The task
formulates the ADR's three decisions as one implementation task; every
decision below is settled there — this document adds scope boundaries,
stack, and cell linkage only.

## Current State

1. **Topic publication.** The `goga/topics` domain creates-and-publishes
   fresh work (`publish_topic` — one quarantined commit, branch plant,
   push, full rollback on failure), refreshes a topic with an optional
   publish push (`update --publish`), and delivers a topic into its base
   (`propagate`, whose push is inherent). There is no command that
   delivers an **existing** topic branch to origin as an operation of
   its own — a user falls back to raw `git push`. The soft hook event
   `topics/topic_published` (context `TopicPublished` in
   `goga/topics/hooks`) carries creation-shaped facts today:
   `identity`, `commit_message`, `commit_hash`, `todo` — the invocation
   moment shaped the context.
2. **Tool config reading.** The onboarding engine is the single writer
   of the tool-config standard: `write_config` buffers verbatim
   filenames and the engine writes them into
   `.goga/tools/<tool>/<file>`. No reader exists anywhere in the
   project. The `goga tool` dispatcher (`goga/commands/tool`) offers one
   optional injection — `ast` — projected from the entry point's
   declared parameters.
3. **Schema validation.** `goga schema` assembles the JSON cell tree
   (the cells/depends_on/max_depth filters prune the tree first, then
   the per-cell `amend_cell` contributions are merged as the tools
   overlay over the surviving nodes, then serialization).
   The schema domain has no validation hook event: tool packages cannot
   observe or veto the delivered artifact. The only validate precedent
   in the project is `build/validate_build` (`goga/build/hooks`) — a
   hard gate whose walk runs to completion, collects exactly one
   `Violation` per tool (tool, hook, reason), treats a crashed hook as
   that tool's veto, and reports a merged error with exit code 1.

## Description

One task, three independent changes:

**A. `goga topics publish [IDENTIFIER]` — delivery of an existing topic
branch to origin.**

- Addressing mirrors `update`/`propagate` exactly: an optional
  IDENTIFIER defaults to the current topic; a branch hosting no topic is
  a clean error naming the branch; a remote-only own branch is a clean
  error hinting `goga topics switch`; no new configuration keys.
- The operation runs one targeted fetch of its own origin twin (one
  stdout report line before it runs), then resolves one of four
  deterministic outcomes:
  - twin absent — the push creates it: outcome **pushed**;
  - twin equals the local tip — success, nothing to do: outcome
    **up-to-date**;
  - twin strictly ahead (contains the local tip) — success, nothing to
    push: outcome **remote-ahead** (the remote already carries the
    local work — not an error);
  - diverged (neither contains the other) — a clean error naming both
    tips; reconciliation is manual git, then re-run.
- Publish is delivery, never history rewriting: no force, no lease,
  ever. No confirmation is asked; a dirty working tree is irrelevant to
  a push. `origin_configured` reading False is a clean error. The result
  is exactly one stdout line distinguishing the three success kinds.
- **Event.** The existing soft action `topics/topic_published` is
  reused — no new action. Its context is reshaped to be
  publication-centric: `identity` (slug, year, branch as entered),
  `remote_branch` (the origin branch that received the delivery — the
  topic's own twin, or the base branch for propagate), `commit_hash`
  and `commit_message` (git facts of the commit the remote branch
  carries after the operation), and `outcome` — a `str` with the fixed
  kind set `pushed | up-to-date | remote-ahead` (the domain's
  documented-outcome-kinds convention, not an enum type). The `todo`
  field is removed: it is creation context, not publication context.
- Emission happens on every completed publication, including idempotent
  outcomes, at every site that publishes: `publish_topic` (as today),
  the new `publish` command, `update --publish`, and `propagate` (its
  inherent push is a publication; outcome there is always `pushed`).

**B. `load_tool_config` — the read-side counterpart of the tool-config
write standard — plus a `config` injection in the tool dispatcher.**

- A library procedure on the `goga/config` facade owning **path
  standardization only**: compose `.goga/tools/<tool>/<filename>` with
  `filename` taken verbatim (with extension, exact match — the same
  standard as the writer), requiring flat name segments (non-empty, no
  separators, no `..` — traversal protection); a violation is a clean
  error. An absent file returns `None` — absence is the normal state of
  a tool config. A present file returns the **raw parsed data as-is**:
  a mapping, a string, a list — whatever the YAML parses to is what the
  caller gets. No models, no content validation, no structural
  expectations, no merging with the Project/Home/amend layers, no
  cache; an optional path override exists for tests. Interpreting the
  content is the tool package's responsibility, not the loader's.
- The `goga tool` dispatcher offers a **second optional injection beside
  `ast`**: an entry point that declares a parameter named `config`
  receives, lazily and as a keyword argument, the loaded
  `.goga/tools/<tool>/config.yml` — raw data as-is, or `None` when
  absent. The offered-injection set stays the single source of opt-in;
  a parameter with any other name never triggers a load.

**C. `schema/validate_schema` — a hard validation gate over the final
schema, mirroring `validate_build`.**

- A new validation hook event in the schema domain, named by project
  precedent (`build/validate_build`; verb+object amend pattern):
  domain `schema`, action `validate_schema`, error class **hard**; the
  catalog record is added additively in `goga/hooks/catalog`.
- Delivery mirrors `validate_build` exactly, including its recorded
  domain-local deviation: the walk runs **to completion** — never
  stopping at the first failure — producing exactly one `Violation` per
  tool (tool, hook, reason); a crashed hook is a veto of its tool
  carrying the failure reason. On failure nothing is printed to stdout,
  one merged error listing every violation goes to stderr, exit code 1.
  With no subscriptions the schema is approved and the output is
  byte-for-byte unchanged.
- The event fires **once over the final assembled tree** — after all
  `amend_cell` contributions are merged and the cells/depends_on/
  max_depth filters are applied, before serialization. Subscribers
  receive a read-only context view of the tree (not a JSON string) with
  a veto method. The validator deliberately sees the final result
  **including the tools overlay** — a recorded exception to the
  "authored facts only" rule, to be fixed explicitly in the schema
  contract. Observe-and-veto only: the tree is never modified by a
  validator.

## Scope

**In scope:**

- The `goga topics publish` command end to end: addressing, targeted
  fetch, the four-outcome matrix, the single stdout result line, and
  its CLI surface in `goga/commands/topics`.
- The publication-centric reshape of the `TopicPublished` context and
  its emission method in `goga/topics/hooks`, plus emission wiring at
  `publish_topic`, the new command, `update --publish`, and
  `propagate`.
- The `goga/topics` contract update: the new publication operation and
  the extension of the sanctioned network set with the publish
  command's targeted fetch and publication push.
- A recording migration note for existing `topics/topic_published`
  subscribers under the reshaped context (the breaking reshape is a
  fact; its addressee list is established at the design/contract
  stage).
- `load_tool_config` as a library procedure on the `goga/config`
  facade, with the optional test path override.
- The `config` optional injection in `goga/commands/tool` beside
  `ast`.
- The `schema/validate_schema` action: the context view with veto, the
  verdict collection, the checkpoint method in the schema hooks zone,
  the additive catalog record, the firing point in the schema
  assembly, and the CLI failure rendering (merged stderr error, exit
  code 1) in `goga/commands/schema`.
- The explicit recording of the tools-overlay exception in the schema
  contract.
- Tests for all of the above per the project conventions.

**Out of scope:**

- Any migration of existing `topic_published` subscribers beyond the
  recording note (who currently consumes `todo` is an ADR open
  question for the design/contract stages).
- Any interpretation, modeling, validation, or merging of tool-config
  content beyond raw passthrough.
- Changes to the board's divergence marker and any reuse decision of
  the twin-vs-tip containment computation there (ADR open question).
- Force or lease pushes anywhere in publish; confirmation prompts; new
  `topics` configuration keys.
- Exact signatures, `location` values, final cell boundaries, and
  Imports/Usages wiring for the new types — design/contract-stage
  work; this task deliberately prescribes none.

## Acceptance Criteria

- `goga topics publish` with no IDENTIFIER addresses the current topic;
  with an IDENTIFIER it resolves through the same tiers as
  `update`/`propagate`; a branch hosting no topic and a remote-only
  own branch produce their respective clean errors.
- The four-outcome matrix behaves exactly as specified: pushed creates
  the twin; up-to-date and remote-ahead succeed without mutation or
  user action; divergence is a clean error naming both tips; no code
  path constructs a force or lease push; `origin_configured` False is
  a clean error; the success output is exactly one stdout line naming
  the outcome kind.
- The `TopicPublished` context carries exactly `identity`,
  `remote_branch`, `commit_hash`, `commit_message`, `outcome`; `todo`
  is gone; `outcome` is one of the three fixed kinds; the action
  address and its soft error class are unchanged in the catalog.
- Every site that publishes emits the event, including the idempotent
  no-op outcomes of the publish command; `propagate` emits it with
  outcome `pushed`.
- `load_tool_config` returns `None` for an absent file; returns the raw
  parsed YAML value as-is for a present one; rejects a non-flat or
  empty or traversing filename with a clean error; honors the path
  override; performs no merging, validation, or caching.
- `goga tool <name>` injects `config` as a keyword argument only when
  the entry point declares a parameter named `config`; the load is
  lazy — it happens only for entry points that opt in; absent config
  yields `None`; the `ast` injection behavior is unchanged.
- `schema/validate_schema` exists as a hard catalog record; with no
  subscriptions (and with no tool packages installed) `goga schema`
  output is byte-for-byte unchanged; a vetoing or crashing subscriber
  yields one `Violation` per tool with the walk run to completion, an
  empty stdout, one merged stderr error listing every violation, and
  exit code 1; a validator receives a read-only view of the final tree
  including the tools overlay and cannot modify it.
- Unit and edge-case tests exist for every new public routine and CLI
  command per the `conventions` practice (CLI commands tested by
  direct handler call); `ruff check` passes on the touched packages.

## Stack

- **Language:** Python 3.10+ (dataclasses with `kw_only=True`).
- **Frameworks:** none beyond the project's existing CLI framework —
  click (usage: `.goga/usages/cooks/click.md`).
- **Libraries:** PyYAML (`yaml`) — already a project dependency, used
  for the raw parse in `load_tool_config`; formatting conventions
  covered by the `conventions` practice.
- **Infrastructure:** git — accessed exclusively through the existing
  `goga/topics/git` cell (subprocess-backed routines: targeted fetch,
  push, containment probes, origin introspection); no new git
  operations are invented.
- **Runtime:** all code and tests execute in the project virtualenv;
  validation via `pytest tests/ -x` and `ruff check`.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| click | `.goga/usages/cooks/click.md` | existing |
| PyYAML | — (covered by `conventions`) | existing, no dedicated file needed |
| git (via subprocess) | — (owned by the `goga/topics/git` cell) | existing |

No new external dependencies are introduced; no usage files are
created or updated by this task.

## Risks and Constraints

- **Breaking event reshape.** The `TopicPublished` context change
  (`todo` removed; `remote_branch`, `outcome` added) breaks existing
  subscribers of `topics/topic_published`; the migration note is in
  scope, the subscriber inventory itself is not (ADR open question).
- **Facade character change.** `goga/config` is today a pure re-export
  facade that "owns no behavior"; `load_tool_config` becomes its first
  owned procedure — the facade contract description must change
  accordingly.
- **Exception to authored-facts-only.** `validate_schema` subscribers
  see the tools overlay of the final tree; the deviation must be
  recorded explicitly in the schema contract, not left implicit.
- **Sanctioned network set.** The topics contract's network
  enumeration must be extended to the publish command's targeted fetch
  and publication push; nothing else may fetch.
- **Idempotency discipline.** All three no-op outcomes (up-to-date,
  remote-ahead, approved-schema-with-no-subscriptions) must stay
  successes with observable, byte-stable output.
- **Injection set stability.** The `config` injection must follow the
  lazy, opt-in discipline of `ast` exactly — no eager loads, no name
  guessing beyond the declared parameter set.

## Scope Estimate

Single task — all three changes in one topic. A decomposition into
three independent topics (publish command / tool-config loading /
schema validation gate) was proposed and explicitly rejected by the
user on 2026-09-29: the task is delivered as one.

## Existing Architecture

Affected cells and their current link connections:

- `goga/topics` — the domain facade. Imports identity/addressing/status
  machinery from `goga/history`; git routines (targeted fetch, push,
  containment, branch inventory) from `goga/topics/git`; the editor
  entry from `goga/topics/editor`; the hooks surface (`TopicIdentity`,
  `TopicHooks`, contexts) from `goga/topics/hooks`. The new publication
  operation extends this facade and its sanctioned-network-set
  annotations; the exchange operations (`update`, `propagate`) gain the
  publication emission.
- `goga/topics/hooks` — the topics hooks zone. Built on the
  `goga/hooks` platform (registry, emission, context wrapping, declared
  actions). `TopicPublished` and its emission method are reshaped here
  (breaking).
- `goga/commands/topics` — the CLI surface of the domain; gains the
  `publish` command.
- `goga/config` — re-export facade embedding types from
  `goga/config/project`, `goga/config/home`, and `goga/config/git`;
  gains its first owned procedure. No import edges change inside the
  config subtree.
- `goga/commands/tool` — imports `AST` from `goga/ast` for the `ast`
  injection; gains the `config` injection and, with it, a read
  dependency on the config facade for the loader (new import edge
  `goga/commands/tool` → `goga/config`; no cycle — nothing in the
  config subtree imports the command layer).
- `goga/schema` — imports `AST` from `goga/ast` and the hooks surface
  from `goga/schema/hooks`; the validation firing point sits between
  the overlay merge + filters and the serialization.
- `goga/schema/hooks` — the schema hooks zone on the `goga/hooks`
  platform; gains the validation view, verdict collection, and
  checkpoint method. Whether the violation/verdict types mirror the
  `goga/build/hooks` precedent by re-declaration or by import is a
  design-stage decision (an edge `goga/schema/hooks` →
  `goga/build/hooks` would be acyclic but is not prescribed here).
- `goga/commands/schema` — the `schema` command; gains the failure
  rendering (merged stderr error, exit code 1) mirroring the build
  command's validate delivery.
- `goga/hooks/catalog` — the action catalog; gains the additive hard
  record for `schema/validate_schema`; the `topics/topic_published`
  record (soft) is unchanged.

## Notes

- All decisions, rejected alternatives, and the fixed glossary live in
  the ADR; the glossary terms (publish flag vs publish command, origin
  twin, tool config, final schema, outcome kind) are normative for
  this task's wording.
- ADR open questions intentionally carried to the design/contract
  stages: exact signatures and cell wiring; the `topic_published`
  subscriber migration inventory; the board divergence marker's
  containment reuse.
- User decisions made during task formulation (2026-09-29): the
  formulation and boundaries were approved as presented; the task is
  delivered as a single task without decomposition.
