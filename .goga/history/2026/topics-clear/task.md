# Topics pointer model: clear command, pointer-only board, delete rework, topic filter

## Current State

The topics domain carries a model ambiguity: a topic is sometimes treated as its
content — the topic directories living in branch trees — and sometimes as a
pointer to history — its own branch plus its slug. Concretely, in the affected
area:

- **Deletion** (`goga/topics`, deletion contract): a topic without its own
  branch, hosted only in the trees of merged branches, is a clean error that
  advises removing the topic "from the hosting branch's tree"; the removal of
  the topic directory is gated by "no merged-work host carries the topic",
  which conflates communal history with working-copy litter.
- **Board** (`goga/topics`, board contract): the aggregated default view
  already shows only topics that still have their own branch, but the per-host
  audit view (its table and its JSON form) carries rows for branchless topics
  too — a documented completeness "including topics without an own branch".
- **Board filter**: only the repeatable `--host` filter exists (exact
  display-name match, union across values); there is no way to narrow the
  board by topic slug.
- **Clear**: no `goga topics clear` command exists — clearing the merged
  topics of a year is manual per-topic deletion.
- The project configuration already carries `topics.base_ref`
  (`TopicsConfig`), and the git layer (`goga/topics/git`) already provides
  local and remote branch deletion and ref tree reading without checkout.

## Description

Adopt the pointer model fixed by the accepted ADR (`.goga/history/2026/topics-clear/adr.md`)
— a topic exists exactly as long as its own branch exists (local or
remote-tracking); history is communal, belongs to no topic, and is never
rewritten or deleted — and land its four consequences as one change:

1. **`goga topics clear`** — removes every own-branched topic of the scoped
   year whose history the base ref carries (the base tree contains the topic
   directory of the year). Base resolution: the `--base-ref` flag over the
   `topics.base_ref` configuration line, otherwise a clean error naming the
   flag and the configuration line. The base is any resolvable revision (a
   local branch, `origin/...`, a tag), is only read, and being on it is not an
   error. Branchless topics are out of scope silently; an empty scope succeeds
   with one line. One confirmation for the whole list, with `--yes/-y` to
   skip it; a non-terminal without `--yes` is a clean error. The current
   branch being a target's own branch is a clean error asking to switch away;
   other hosts of a target are untouched. Failure semantics and the
   `topic_deleted` events are those of the existing deletion machinery.
2. **Delete rework** — a topic without its own branch (history hosted by
   other branches only) becomes a clean error: the topic has no branch, so
   there is nothing to delete — it is history. The current advice to "remove
   it from the hosting branch's tree" is dropped. A topic directory no branch
   hosts remains a targetable identifier (working-copy hygiene: an uncommitted
   topic directory that no branch surviving the deletion carries is litter
   and goes with it — the target's own branch does not gate the directory,
   its tree dies with the branch).
3. **Pointer-only board** — every board view (default, `--per-host`,
   `--json`) shows only topics that still have their own branch; the
   documented per-host completeness "including topics without an own branch"
   is dropped from the cell practices. A deleted pointer disappears from
   every view; its history remains reachable through git itself, not through
   the board.
4. **`--topic <slug>` board filter** — repeatable, exact slug match, union
   across values, AND-composed with `--host`; an unknown slug yields an empty
   board (`[]` under `--json`) with exit 0; applies to every output form.
   Exactness mirrors `--host`: display filters are predictable; prefix
   matching stays the privilege of action-command identifiers.

## Scope

**In scope:**
- The `clear` subcommand of the topics command group — CLI surface and the
  domain contract behind it (scope resolution against the base ref tree,
  confirmation, delegation to the existing deletion machinery)
- Rework of the deletion resolution semantics: branchless topic → clean
  "nothing to delete" error; the hosting-branch advice removed; working-copy
  hygiene for unhosted topic directories kept
- Pointer-only board across all three output forms, including the drop of the
  per-host completeness wording from the cell practices
- The repeatable `--topic` slug filter on `goga topics board`, composed with
  `--host`, in every output form
- Update of the cell-level practices that document the board, the deletion,
  and the topics command group
- Update of the affected CODEMANIFEST contracts to match the implemented
  behavior
- Tests for every changed behavior per the project conventions

**Out of scope:**
- Any removal commit on the base ref — the base is read-only; host trees and
  their history stay untouched
- New git capabilities — branch deletion, twin handling, and ref tree reading
  already cover everything `clear` needs
- Changes to the configuration schema — `TopicsConfig.base_ref` is reused as
  is
- Prefix matching for `--topic` — tiered resolution stays with the
  identifiers of action commands
- Signature and placement decisions — where the topic filter lives, how the
  primary filter is applied in collection versus projection, the exact
  routine shapes — belong to the design stage

## Acceptance Criteria

- `goga topics clear` deletes exactly the own-branched topics of the scoped
  year whose topic directory the base tree carries; the base ref is resolved
  as `--base-ref` over `topics.base_ref`, and with neither a clean error
  names the flag and the configuration line; the base is never moved or
  pushed
- `clear` succeeds with one result line on an empty scope (exit 0), skips
  branchless topics silently, asks one confirmation for the whole list,
  skips it under `--yes/-y`, and errors cleanly in a non-terminal without
  `--yes`
- `clear` errors cleanly when the current branch is a target's own branch,
  and leaves the other hosts of every target untouched
- `clear` reuses the existing deletion machinery: per-target `topic_deleted`
  events fire, remote-twin deletion failures restore the local branch and
  surface one clean error, and targets fully removed before a later failure
  stay removed
- `goga topics delete` on a branchless topic errors cleanly stating there is
  no branch and nothing to delete, with no advice about hosting-branch trees
- A topic directory no branch hosts remains deletable (working-copy hygiene);
  a topic directory carried by any branch that survives the deletion — any
  host other than the target's own branch — is history and stays; the
  target's own branch does not gate the directory
- `goga topics board` in the default, `--per-host`, and `--json` forms shows
  no topic without its own branch; the completeness wording is gone from the
  cell practices
- `goga topics board --topic <slug>` filters by exact slug, unions across
  repeated values, AND-composes with `--host`, yields an empty board (`[]`
  under `--json`) with exit 0 for an unknown slug, and applies to every
  output form
- All tests pass (`pytest tests/ -x`), `ruff check` is clean, and the
  affected CODEMANIFEST files and cell practices agree with the implemented
  behavior (`goga lint` passes)

## Stack

- **Frameworks:** none beyond the existing project stack
- **Libraries:** click (CLI surface — flags, repeatable options,
  confirmation, exit codes), beautiful_json (JSON serialization of the board)
- **Infrastructure:** git through the existing `goga/topics/git` layer
  (subprocess) — local/remote branch deletion and ref tree reading; no new
  git invocations beyond the existing patterns
- **Language:** Python 3.10+ (dataclasses `kw_only`, relative intra-package
  imports, Google-style docstrings, CLI docstring rules per the `convention`
  practice)
- **Testing:** pytest + ruff per the `convention` practice; CLI handlers
  tested by direct Python calls

## External Dependencies

| Component     | Usage file                          | Status   |
|---------------|-------------------------------------|----------|
| click         | `.goga/usages/cooks/click.md`       | existing |
| beautiful_json | `.goga/usages/cooks/beautiful_json.md` | existing |

No new external dependencies. The cell-level practices that change
(`topic-board`, `deleting`, `topics-command` under the affected cells'
`.usages` directories) are part of the task scope, not external dependencies.

## Risks and Constraints

- User-visible behavior change: branchless rows disappear from the per-host
  audit view and the JSON board — the documented completeness is deliberately
  dropped per the ADR; consumers of the JSON shape see fewer records (the
  record shape itself is unchanged and stays additive)
- The delete rework changes the error semantics for merged-host scenarios;
  the removed advice must also disappear from the cell practices so the docs
  do not contradict the model
- `clear` performs network operations (origin twin deletions) and inherits
  the deletion machinery's partial-failure semantics — earlier targets stay
  removed; the result line must reflect what actually happened
- The `-y` short form of `clear` collides with the group `--year` option —
  the same collision pattern as `delete`, distinguished by position on the
  command line
- The configuration is read only for values no flag provided; a missing
  configuration file counts as an unset `topics.base_ref`
- The board and deletion semantics shift must stay consistent with the hooks
  zone: `topic_deleted` facts come from the operation's own data and fire
  exactly once per fully removed target

## Scope Estimate

Single task. The four decisions of the ADR form one coherent model shift
("a topic is a pointer") over a compact area — two code cells and their
practices — and a split into deletion-side and board-side subtasks would
duplicate the pointer-model context without independent value.

## Existing Architecture

- **`goga/topics`** (domain cell) — the board collection and aggregation
  contracts gain the pointer-only primary filter and the topic filter; the
  deletion resolution contract changes its branchless-topic and
  directory-hygiene semantics; a new clear contract (scope resolution
  against the base ref tree plus delegation to the deletion machinery) joins
  the cell
- **`goga/commands/topics`** (CLI cell) — the command group gains the
  `clear` subcommand with its flags and the `board` subcommand gains the
  repeatable `--topic` option; the pointer-only views follow from the domain
- **Cell practices to update** — `goga/topics/.usages/topic-board.md`,
  `goga/topics/.usages/deleting.md`, and
  `goga/commands/topics/.usages/topics-command.md`; a new practice for the
  clear flow may be added if the design introduces a distinct consumption
  pattern
- **Reused unchanged** — `goga/topics/git` (branch deletion and ref tree
  reading — the primitives behind the domain's twin handling), `goga/config`
  (`TopicsConfig.base_ref`) with its config amendment checkpoint
  (`goga/config/hooks`), the topics hooks zone (`topic_deleted` event),
  `goga/history` (slug normalization, topic paths)
- The import graph stays acyclic in the existing direction:
  `goga/commands/topics` → `goga/topics` → `goga/topics/git` /
  `goga/history` / `goga/topics/hooks`

## Notes

- The authoritative decision record is the accepted ADR at
  `.goga/history/2026/topics-clear/adr.md`; the rejected options (a removal
  commit on base_ref, per-host audit completeness, branches-only deletion
  without working-copy hygiene, prefix matching for `--topic`) must not
  resurface in the design or implementation
- Signature and placement decisions are deliberately deferred to the design
  stage: where the topic filter lives, collection versus projection
  mechanics of the primary filter, and the exact routine shapes
- No code examples are included in this task by stage constraint; the task
  fixes scope and behavior, not architecture
- Stack and single-task scope were approved by the user during formulation
  (2026-09-23)
