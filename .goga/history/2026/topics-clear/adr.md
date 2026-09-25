# A topic is a pointer: clear merged topics, pointer-only board, exact topic filter

Status: accepted (2026-09-23)

The topics domain carried a model ambiguity: is a topic its content — the
topic directories living in branch trees — or a pointer to history — its own
branch plus its slug? We decided **pointer**. A topic exists exactly as long
as its own branch exists (local or remote-tracking); history is communal —
any branch may host it, it belongs to no topic, and it is never rewritten or
deleted. Every other decision below follows from this one.

## Decision set

1. **Deletion model** — deleting a topic is deleting its own branch (local +
   origin twin) and nothing more. Deletion creates no commits; host trees and
   their history stay untouched. The only network operation is the deletion
   of origin twins. Working-copy hygiene stays: an uncommitted topic
   directory that no branch carries is removed with the deletion (litter,
   not history).
2. **`goga topics clear`** — removes every topic of the scoped year that has
   its own branch and whose history the base ref carries (the base tree
   contains the topic directory of the year). Base resolution: `--base-ref`
   over `topics.base_ref`, otherwise a clean error naming the flag and the
   configuration line; the base is any resolvable revision (local branch,
   `origin/...`, a tag), is only read, and being on it is not an error.
   Branchless topics are out of scope silently; an empty scope succeeds with
   one line. One confirmation for the whole list with `--yes/-y` to skip; a
   non-terminal without `--yes` is a clean error. The current branch being a
   target's own branch is a clean error asking to switch away; other hosts
   of a target are untouched. Failure semantics and the `topic_deleted`
   events are those of the existing deletion machinery.
3. **Delete rework** — a topic without its own branch (history hosted by
   other branches only) becomes a clean error: the topic has no branch, so
   there is nothing to delete — it is history. The current advice to
   "remove it from the hosting branch's tree" is dropped: it contradicts the
   model. A topic directory no branch hosts remains a targetable identifier
   (working-copy hygiene).
4. **Pointer-only board** — the whole board (default view, `--per-host`,
   `--json`) shows only topics that still have their own branch; the
   documented per-host completeness "including topics without an own branch"
   is dropped. A deleted pointer disappears from every view; its history
   remains reachable through git itself, not through the board.
5. **`--topic <slug>` board filter** — repeatable, exact slug match, union
   across values, AND-composed with `--host`; an unknown slug yields an empty
   board (`[]` under `--json`) with exit 0; applies to every output form.
   Exactness mirrors `--host`: display filters are predictable; prefix
   matching stays the privilege of action-command identifiers.

## Considered options

- **A removal commit on base_ref** — one quarantined commit deleting the
  cleared topic directories, the base moved and pushed. Rejected: deletion
  cannot have a commit; the trees of hosts are history, and history stays
  as is.
- **Per-host audit completeness** — keeping branchless rows in the audit
  view. Rejected: a topic without a branch does not pass the primary
  filter; showing branchless rows contradicts the pointer model.
- **Branches-only deletion without working-copy hygiene** — Rejected: it
  accumulates permanent litter from uncommitted `switch --todo` writes.
- **Prefix matching for `--topic`** — Rejected: unpredictable in a display
  filter; tiered resolution stays with the identifiers of action commands.

## Consequences

- The end state of `clear` is "history lives, no topic pointers": cleared
  topics vanish from the board entirely while their commits remain reachable
  from the base ref's history.
- No new git capability is required: branch deletion, twin handling, and ref
  tree reading already cover everything `clear` needs.
- Signature and placement decisions — where the topic filter lives, how the
  primary filter is applied in collection versus projection, the exact
  routine shapes — are deliberately left to the design stage; this record
  fixes only the problem-level decisions above.
