# Architecture Plan — Topics pointer model

## Topic

**Short name:** Topics pointer model — `clear` command, pointer-only board, delete rework, exact
`--topic` filter.

**Plan path:** `.goga/history/2026/topics-clear/arch.md`

**Model decision (accepted ADR `adr.md`):** a topic exists exactly as long as its own branch exists
(local or remote-tracking); history is communal, belongs to no topic, and is never rewritten or
deleted.

**Cells:** 3 modified (`goga/topics`, `goga/commands/topics`, `goga/commands`); 0 created; no new
practices, no new external dependencies.

## Implementation Order

1. **`goga/topics`** (domain — leaf of this change). No cell of this plan is its dependency; its
   CODEMANIFEST changes define the import (`resolve_clear_targets`) that the CLI cell consumes.
   Implement the domain first: the reworked deletion resolution, the new clear scope resolution,
   the board filters.
2. **`goga/commands/topics`** (CLI). Depends on `goga/topics` (imports the domain types,
   including the new `resolve_clear_targets`), on `goga/config` / `goga/config/hooks` (base
   resolution, unchanged). Implement after the domain: the `clear` subcommand and the `--topic`
   option.
3. **`goga/commands`** (root facade). Re-exports the `topics` group unchanged; the only edit is
   one annotation sentence aligning the practice-coverage enumeration with the reworked
   `topics-command` practice. Implement last, after the cell it consumes.

Reused unchanged (do not touch): `goga/topics/git`, `goga/history`, `goga/topics/hooks`,
`goga/topics/editor`, `goga/config`, `goga/config/hooks`.

---

## Artifacts

### Cell 1 — `goga/topics` (MODIFIED)

#### CODEMANIFEST — change set

**Header.** `Imports` — no change (all four blocks stay verbatim). `Usages` — no change
(`convention`, `click`). `Annotations` — keep the base `convention` paragraph and all
practice-binding sentences verbatim; replace the responsibility-zone paragraph (the one beginning
"This cell owns the topics domain") with:

```yaml
  This cell owns the topics domain under the pointer model — a topic
  exists exactly as long as its own branch exists, local or
  remote-tracking; history is communal, belongs to no topic, and is
  never rewritten or deleted. The domain is the work-tracker view of
  the history tree: the cross-branch topic inventory of one year over
  the topics that still have their own branch, in two projections —
  the per-host records, one per topic and hosting branch, as the single
  source of board facts, and the aggregated one-entry-per-topic view
  computed from them, each entry with its own branch, the hosts
  carrying the topic's history, the own branch's statuses, and the todo
  summary; the switch-identifier resolution and switching orchestration
  with the optional todo entry; the creation procedure off an explicit
  base with its todo acquisition ladder — an explicit value, else the
  declared stdin source, else the interactive editor, else a clean
  error — with the preflight and the publication ask that skips itself
  when the todo came from stdin: by default one quarantined todo commit
  planted as the branch without a switch, under the switch flag the
  checked-out branch with its working-copy topic directory; the fast
  creation-and-publication procedure — a committed branch off an
  explicit base without switching, pushed to origin, rolled back fully
  on a failed publication; the combined ensure orchestration of the
  fast process — always from the current HEAD, the topic directory
  ensured on any hosting branch, the todo entry after the switch or the
  creation; the todo entry of an existing topic; the identified-topic
  deletion — a topic without its own branch is history and nothing to
  delete, a deletable topic loses its own local branch, its origin
  twin, and its topic directory when no branch surviving the deletion
  carries it, removed symmetrically with restore on failure; and the
  merged-topic clear scope — the
  own-branched topics of the year whose topic directory the base ref's
  tree carries, resolved read-only against the base and executed by the
  deletion machinery. The domain opens its
```

…continuing with the existing hooks-zone sentence, facade allocation, and constraints verbatim
("…lifecycle to tool packages through its hooks zone: … Use relative imports.").

**Body — replace** the `collect_topic_board` block with:

```yaml
"collect_topic_board(year: str | None = None, remote: bool = False, hosts: tuple[str, ...] | None = None, topics: tuple[str, ...] | None = None) -> records: list[BoardRecord]":
  location: board.py
  annotations: |
    Collect the cross-branch topic inventory of one year — one record
    per topic and hosting branch of the topics that still have their
    own branch: the complete audit view and the single source of the
    board's facts.

    `year`: optional year as four digits; None means the current year
    `remote`: True reads remote-tracking refs instead of local branches
    `hosts`: optional hosting-branch display names — None or empty
             keeps every record; when non-empty, only the records
             whose branch display name exactly equals one of them
             survive, union across values; an unknown name yields the
             empty list, never an error
    `topics`: optional topic slugs — None or empty keeps every record;
              when non-empty, only the records of the named topics
              survive, exact slug equality, union across values,
              composed with `hosts`; an unknown slug yields the empty
              list, never an error
    `records`: one `BoardRecord` per topic and hosting branch of the
               own-branched topics, sorted by scale order of the first
               maximal status, then alphabetically by topic

    Apply the `topic-paths` practice for the year and tree-root patterns.
    Apply the `topic-statuses` practice for the scale assembly and
    maximal-status computation.
    Apply the `refs-and-switching` practice for the inventory,
    tree-reading, and file-reading patterns.

    Algorithm:
    1. Resolve the year — `year` when given, otherwise the current year
       via `current_year`
    2. Assemble the status scale via `assemble_status_scale` once
    3. Local mode enumerates local branches via `list_branch_refs` and
       reads the current branch from the working copy via
       `resolve_current_branch_name`; remote mode enumerates the
       remote-tracking `BranchRef` entries of the same inventory only.
       Local mode takes the full inventory of `list_branch_refs` — a
       topic hosted only by a remote-tracking ref keeps its row with
       the remote marker
    4. Read the topic tree of every ref under the root resolved via
       `resolve_history_root` with `read_ref_tree_paths`, without
       checkout
    5. For every ref, take the topics of the resolved year with their
       artifact paths and compute the maximal statuses — the working
       copy over the directory composed by `resolve_topic_dir` via
       `resolve_topic_status`, every other ref via the `StatusScale`
    6. Read the todo summary of every hosted topic — the working copy
       from todo.md of its directory, every other ref from the todo.md
       of its ref tree via `read_ref_file`; the summary is the first
       line that yields a non-empty result after leading # markers
       are stripped and the edges trimmed; None when the file is
       absent, the empty string when no line qualifies; the file is
       never modified
    7. Collapse a local branch and its remote twin into one row — the
       local branch wins; different branches hosting one slug stay
       separate rows
    8. Primary filter: a topic keeps its records only when it has its
       own branch — some ref of the full inventory of `list_branch_refs`
       — both local and remote-tracking entries — whatever `remote`
       mode enumerates — whose branch part (the whole name of a local
       branch, the short name of a remote-tracking ref) normalizes into
       the topic slug; a topic without an own branch is history and
       passes no records
    9. Mark the row hosting the current branch
    10. A non-empty `hosts` keeps the records of the named hosting
        branches, a non-empty `topics` keeps the records of the named
        topics — both exact, union across values, composed together;
        the sort order of the survivors stays
    11. Sort by scale order of the first maximal status, then
        alphabetically by topic, and return the records

    Requirements:
    - The current branch is read from the working copy — uncommitted
      progress is visible; remote mode shows it through its remote
      twin
    - Read-only — no checkout, no worktree, no mutation of any kind
    - A year without topics yields an empty list — not an error
    - A multi-line todo.md yields its first qualifying line; a todo.md
      whose every line reduces to emptiness yields the empty summary
    - The todo summary never affects the sort order
    - A topic without an own branch appears in no record, whatever
      hosts carry it
    - An unknown `hosts` name or `topics` slug yields the empty list —
      not an error

    Constraints:
    - Do not render — output shaping belongs to the consumer
    - Do not cross the year boundary — other years are invisible here
```

**Body — replace** the `aggregate_topic_board` block with:

```yaml
"aggregate_topic_board(records: list[BoardRecord], hosts: tuple[str, ...] | None = None, topics: tuple[str, ...] | None = None) -> entries: list[BoardEntry]":
  location: board.py
  annotations: |
    Project the per-host records into the default board — exactly one
    entry per topic that still has an own branch.

    `records`: the collected per-host records — the source of facts
    `hosts`: optional hosting-branch display names — None or empty
             keeps every entry; when non-empty, only the entries whose
             hosts list contains one of them survive, union across
             values; an unknown name yields the empty list, never an
             error
    `topics`: optional topic slugs — None or empty keeps every entry;
              when non-empty, only the entries of the named topics
              survive, exact slug equality, union across values,
              composed with `hosts`; the own-branch requirement stands
              first — a filter never resurrects a topic without an own
              branch; an unknown slug yields the empty list, never an
              error
    `entries`: one `BoardEntry` per topic with an own branch, sorted by
               scale order of the first maximal status, then
               alphabetically by topic

    Apply the `topic-paths` practice for the slug normalization pattern.

    Algorithm:
    1. Group the records by topic slug
    2. Hosts list of a topic — the branch display names of its
       records, alphabetical; a local branch and its remote twin count
       as one host under the local name — the collapse belongs to the
       collection
    3. Own branch — the topic's records whose branch part — the whole
       display name of a local branch, the short name (the part after
       the first "/") of a remote-tracking ref — normalizes into the
       topic slug via `normalize_topic_slug`; a remote-tracking ref
       qualifies; a topic without an own branch produces no entry —
       its history survives only in merged hosts
    4. Several own branches collide -> the deterministic winner: the
       record hosting the current branch, otherwise a non-remote record
       over a remote-tracking one, otherwise the first in the
       display-name alphabet
    5. The entry carries the winner's statuses, remote marker, and todo
       summary; the current marker is True when the winner hosts the
       current branch — a merged host carrying the topic's history
       never marks the entry
    6. Sort by scale order of the first maximal status, then
       alphabetically by topic
    7. A non-empty `hosts` keeps the entries whose hosts list contains
       any given name, a non-empty `topics` keeps the entries of the
       named topics — both exact, union across values, composed
       together; None or empty keeps every entry

    Requirements:
    - Read-only over `records` — no mutation, no re-sort of the input;
      no git access happens here — every fact comes from the records
    - Both board views derive from one collection pass — this routine
      computes, it never reads the ref trees
    - A topic without an own branch produces no entry, whatever hosts
      carry it
    - A filter never resurrects a hidden topic — the own-branch
      requirement precedes both
    - In remote mode a topic whose own branch exists only locally keeps
      its merged-host rows but produces no entry — the records carry no
      own-branch row for it; the local mode inventory covers every own
      branch
    - An empty `records` yields the empty list

    Constraints:
    - Do not render — output shaping belongs to the consumer
    - Do not cross the year boundary — the records already scope it
```

**Body — replace** the `DeleteTarget` block with:

```yaml
"DeleteTarget(topic: str, branch: str | None, remote: str | None, has_dir: bool)":
  location: deletion.py
  annotations: |
    One identified deletion target — a topic with its own hosting refs
    and its working-copy directory flag.

    `topic`: the topic slug
    `branch`: the own local branch name, or None
    `remote`: the own origin twin name, or None
    `has_dir`: True when the topic directory of the year exists on
               disk and no branch surviving the deletion carries the
               topic — the target's own branch is not a gate: its tree
               dies with the branch; a surviving host carrying the
               topic keeps the directory

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "topic -> str": |
      The topic slug.
    "branch -> str | None": |
      The own local branch name, or None.
    "remote -> str | None": |
      The own origin twin name, or None.
    "has_dir -> bool": |
      True when the topic directory of the year exists on disk and no
      branch surviving the deletion carries the topic — the target's
      own branch is not a gate; a surviving host carrying the topic
      keeps the directory.
```

**Body — modify** `resolve_delete_targets`: signature, `location`, and the practice lines stay;
replace Algorithm step 4 and the Requirements list:

```yaml
    Algorithm:
    1. [carried verbatim]
    2. [carried verbatim]
    3. [carried verbatim]
    4. A topic without its own branch — no hosting ref whose name
       normalizes into the topic slug — is a clean error: the topic
       has no branch, there is nothing to delete — it is history. A
       topic with its own refs and other carriers loses its own refs
       only; its directory flag is survivor-gated. A topic directory
       no branch hosts stays targetable (no refs, directory only)
    5. [carried verbatim]
    6. [carried verbatim]
    7. [carried verbatim]

    Requirements:
    - Read-only — nothing is removed, created, or switched
    - All-or-nothing — any unresolved or ambiguous identifier cancels
      the whole call
    - A branchless topic is a clean error stating there is no branch
      and nothing to delete
    - The directory flag is survivor-gated — a topic directory carried
      by any branch surviving the deletion stays; the target's own
      branch does not gate the directory

    Constraints:
    - [carried verbatim]
```

**Body — insert** the new type between `resolve_delete_targets` and `delete_topics`:

```yaml
"resolve_clear_targets(base_ref: str, year: str | None = None) -> targets: list[DeleteTarget]":
  location: deletion.py
  annotations: |
    Resolve the clear scope of one year against the base ref's tree —
    every own-branched topic whose history the base carries — into
    deletion targets; nothing is removed here.

    `base_ref`: the base revision as resolved by the caller — any
                revision string git resolves; read-only, being on it
                is not an error
    `year`: optional year as four digits; None means the current year
    `targets`: one `DeleteTarget` per topic in scope, alphabetical by
               topic; an empty scope yields the empty list — not an
               error

    Apply the `topic-paths` practice for the year and tree-root
    patterns.
    Apply the `refs-and-switching` practice for the inventory,
    tree-reading, and revision-resolution patterns.

    Algorithm:
    1. Resolve the year — `year` when given, otherwise the current
       year via `current_year`
    2. Collect the branch inventory via `list_branch_refs` and
       resolve the own-branched topics of the year — a topic whose
       slug normalizes from the branch part of some ref (the whole
       name of a local branch, the short name of a remote-tracking
       ref); a topic without an own branch is out of scope silently —
       it is history
    3. Read the base tree under the root resolved via
       `resolve_history_root` with `read_ref_tree_paths` — the topics
       of the year whose topic directory the base tree carries; an
       unresolvable base is a clean error carrying the reason
    4. The scope is the intersection — the own-branched topics whose
       topic directory the base tree carries
    5. Build one `DeleteTarget` per topic in scope — the own local
       branch, the origin twin, and the survivor-gated directory flag:
       the directory fact reads the topics of the year on disk via
       `collect_history_tree`, and the gate probes the trees of the
       refs surviving the deletion — the inventory minus the target's
       own refs — via `read_ref_tree_paths`; a survivor carrying the
       topic keeps the directory
    6. The current branch — read via `resolve_current_branch_name` —
       being the own branch of any target -> clean error asking to
       switch away first; the whole call cancels
    7. Return the targets

    Requirements:
    - Read-only — the base is never moved or pushed; no branch is
      deleted and no directory is removed here
    - Branchless topics are out of scope silently; an empty scope
      yields the empty list
    - Only the target's own refs enter a target — the other hosts of
      a target are untouched

    Constraints:
    - Do not resolve remote state over the network — the local
      inventory only
    - Do not confirm or execute — the confirmation and the deletion
      belong to the caller
```

All other body blocks (`BoardRecord`, `BoardEntry`, `SwitchCandidate`, `resolve_switch_candidates`,
`switch_topic`, `ensure_topic`, `create_topic`, `enter_topic_todo`, `check_branch_occupancy`,
`publish_topic`, `check_slug_occupancy`, `delete_topics`) — carried verbatim.

**Footer — replace** `Description`:

```yaml
Description: |
  The topics domain — the pointer model of a topic (its own branch):
  the cross-branch topic inventory of one year in two projections
  (per-host audit records as the source of facts, the aggregated
  one-entry-per-topic view) with todo summaries, the todo acquisition
  ladder of the creation — value, declared stdin, editor, clean error —
  with preflight and the publication ask skipped when the todo came
  from stdin, quarantined without a switch by default, checked out
  under the switch flag, fast creation with publication, the ensure
  orchestration of the fast process, the todo entry of a topic, the
  identified-topic deletion, and the merged-topic clear scope; the
  lifecycle events of the domain fire through its hooks zone.
```

#### `.usages/` files

**File:** `goga/topics/.usages/topic-board.md` — replace the full content with:

````markdown
# topics — the topic board

How to collect the cross-branch topic inventory of one year with the
`goga.topics` facade, in its two projections. For consumers that show
all work of a repository: CLI boards, reviews, overviews, tools.

The board sees one year at a time and shows only topics that still
have their own branch — a hosting branch whose branch part (the whole
name of a local branch, the short name of a remote-tracking ref)
normalizes into the topic slug. A topic without its own branch is
history: it appears in no view, and its commits stay reachable through
git itself, not through the board. The per-host collection is the
single source of facts: one record per topic and hosting branch,
twin-collapsed. The default view is a projection of those records —
one entry per topic. Local mode reads the full branch inventory and
the current branch from the working copy — uncommitted progress is
visible. Remote mode lists remote-tracking refs instead; the current
branch shows through its remote twin. No checkout happens: every ref
is read through git plumbing, so the working copy and .git stay
untouched.

## Collecting the per-host records

```python
from goga.topics import collect_topic_board

records = collect_topic_board()  # current year, local — every own-branched topic × host row
records = collect_topic_board(year="2025", remote=True)
records = collect_topic_board(hosts=("main", "release/1.3"))  # named hosts only
records = collect_topic_board(topics=("feature-foo",))  # named topics only
records = collect_topic_board(hosts=("main",), topics=("feature-foo",))  # both filters, AND
```

- One `BoardRecord` per topic and hosting branch of the own-branched
  topics: the slug, the hosting branch display name, that branch's
  maximal status names in scale order, the current and remote markers,
  and the todo summary — the first line of the topic's `todo.md` that
  yields text after leading `#` markers are stripped and the edges
  trimmed, or None when the topic has none. Rows hosted by other
  branches read their summaries from the ref trees without checkout;
  the current branch's row reads the working copy, so an uncommitted
  todo edit shows at once. The file is never modified — the stripping
  is for display.
- A local branch and its remote twin collapse to one row — the local
  branch wins. Two different branches hosting one slug stay two rows.
- A topic without an own branch yields no records in any mode — the
  primary filter owns this, the display filters never see its rows.
- `hosts` keeps the records of the named hosting branches only —
  exact display-name match; `topics` keeps the records of the named
  topics only — exact slug match; several values unite, and the two
  filters compose — a record survives both. An unknown name or slug
  yields the empty list, never an error.
- Sorting: scale order of the first maximal status, then topic
  alphabet.
- A year without topics yields an empty list — not an error.
- Strictly read-only.

## Aggregating the one-entry-per-topic view

```python
from goga.topics import aggregate_topic_board

entries = aggregate_topic_board(records)  # one entry per own-branched topic
entries = aggregate_topic_board(records, hosts=("main",))
entries = aggregate_topic_board(records, topics=("feature-foo",))
entries = aggregate_topic_board(records, hosts=("main",), topics=("feature-foo",))
for entry in entries:
    print(entry.topic, entry.branch, entry.hosts, entry.statuses, entry.current, entry.todo)
```

- One `BoardEntry` per topic that still has an own branch — a hosting
  branch whose branch part (the whole name of a local branch, the
  short name of a remote-tracking ref) normalizes into the topic
  slug; a remote-tracking ref qualifies, so remote-only topics keep
  their entry. A topic whose history survives only in merged hosts
  produces no entry — and no records either.
- `branch` is the own branch; several colliding own branches resolve
  deterministically — the current branch when it is among them,
  otherwise a local branch over a remote-tracking one, otherwise the
  display-name alphabet.
- `hosts` lists every branch carrying the topic's history, the own
  branch included, alphabetical by display name.
- `statuses` are the own branch's maximal statuses — artifacts that
  exist solely on merged hosts do not advance them.
- `current` marks the topic whose own branch is the current working
  branch — a merged host carrying the topic's history never marks the
  entry.
- `hosts` and `topics` filter as in the collection — exact match,
  union across values, composed together; the own-branch requirement
  stands first, a filter never resurrects a hidden topic; an unknown
  name or slug yields the empty list, never an error.
- The entries sort like the records: scale order of the first maximal
  status, then topic alphabet. Strictly read-only over the records —
  no second git read happens; both views derive from one collection
  pass.
````

**File:** `goga/topics/.usages/deleting.md` — replace the full content with:

```markdown
# topics — deleting topics and clearing merged topics

How to resolve and delete identified topics — and how to resolve and
clear the merged topics of a year — with the `goga.topics` facade.
For consumers that tear down work: the topics command layer.

A topic exists exactly as long as its own branch exists. Deleting a
topic deletes its own branch — the local branch and its origin twin —
and nothing else: no host tree is touched, no commit is created,
history is communal and stays. The topic directory of the working
copy is litter when no branch surviving the deletion carries the
topic — it goes with the deletion; a surviving branch carrying the
topic keeps the directory, it is history.

## Resolving targets

    from goga.topics import resolve_delete_targets

    targets = resolve_delete_targets(["feature-foo", "release-1-3-0"])
    for target in targets:
        print(target.topic, target.branch, target.remote, target.has_dir)

- Identifier tiers: exact branch name, exact topic slug, prefixes —
  plus topic directories of the year no branch hosts. An exact branch
  name hosting nothing falls through to the slug tier: an unpublished
  topic (its todo uncommitted) resolves through its disk directory,
  while the bare branch itself never resolves.
- No match or several matches -> a clean error, no interactive
  selection; the whole call is cancelled — all-or-nothing.
- A local branch and its origin twin form one target; repeated
  identifiers collapse.
- A topic without its own branch — its history hosted by other
  branches only — is a clean error: the topic has no branch, there is
  nothing to delete, it is history.
- A topic directory no branch hosts stays targetable — working-copy
  hygiene (no refs, directory only).
- The current branch hosting a target -> a clean error asking to
  switch away first.

## Deleting confirmed targets

    from goga.topics import delete_topics

    result = delete_topics(targets)   # the caller has confirmed
    print(result)                      # one line — the outcome

- The confirmation belongs to the caller; the deletion is
  unconditional — no merge checks.
- Local branch + origin twin: both removed, the local first; a failed
  remote deletion restores the local branch at its former commit and
  raises one clean error — targets removed before the failure stay
  removed.
- The topic directory joins the deletion exactly when no branch
  surviving the deletion carries the topic — the target's own branch
  is not a gate; a surviving host carrying the topic keeps it.
- The deletion push is a network operation of the domain; no fetch
  ever happens.

## Resolving the clear scope of a year

    from goga.topics import resolve_clear_targets

    targets = resolve_clear_targets("origin/release/2.0.0")
    targets = resolve_clear_targets("release/2.0.0", year="2025")
    result = delete_topics(targets)   # confirm first, then delete

- The clear scope: every own-branched topic of the year whose topic
  directory the base ref's tree carries — the merged topics of the
  year. The base is any resolvable revision (a local branch, an
  `origin/...` ref, a tag), is only read, and being on it is not an
  error.
- Branchless topics are out of scope silently; a year without merged
  topics yields the empty list — print one line and succeed.
- The targets are ordinary `DeleteTarget`s: confirm once for the
  whole list, then delete via `delete_topics` — the deletion
  semantics, the restore-on-failure behavior, and the `topic_deleted`
  events are those of the machinery above.
- Only the target's own refs enter a target — the other hosts of a
  target are untouched.
- The current branch being a target's own branch -> a clean error
  asking to switch away first.
```

### Cell 2 — `goga/commands/topics` (MODIFIED)

#### CODEMANIFEST — change set

**Header.** `Imports` — in the `From: goga/topics` block add `resolve_clear_targets` to `Types`
(after `delete_topics`). `Usages` — no change. `Annotations` — four edits:

1. In the click sentence, replace "the repeatable host filter, echo, exit-code propagation, the
   confirmation of the delete subcommand, and the clean error rendering." with "the repeatable host
   and topic filters, echo, exit-code propagation, the confirmation of the delete and clear
   subcommands, and the clean error rendering."
2. Replace "the `deleting` practice for the deletion contract of the domain" with "the `deleting`
   practice for the deletion and clear contracts of the domain".
3. After "The switch flag passes through to the domain." insert: "The clear subcommand resolves its
   base the same way minus the current HEAD — a flag beats the topics section; no base at all is a
   clean error naming the flag and the configuration line."
4. Replace "and confirms the deletion." with "and confirms the deletion and the clear."

**Body — modify** the `topics` group entity: replace its type-level annotation (Subcommand
surfaces) with:

```yaml
    Subcommand surfaces:
    - board — a --remote/-r flag, an --info/-i flag, a repeatable
      --host option, a repeatable --topic option, a --per-host flag,
      a --json flag
    - create — a NAME positional, a --todo/-t option with an optional
      value, a --publish/-p flag, a --base-ref option, a --from-current
      flag, a --commit/-c option, a --switch/-s flag
    - switch — an IDENTIFIER positional, a --todo flag
    - delete — IDENTIFIER positionals, a --yes/-y flag
    - clear — a --base-ref option, a --yes/-y flag
```

**Body — replace** the `board` method with:

```yaml
    "board(remote: bool = False, info: bool = False, host: tuple[str, ...], per_host: bool = False, json_output: bool = False, topic: tuple[str, ...]) -> exit_code: int": |
      Subcommand goga topics board: print the board of the scoped
      year — by default one entry per topic as a four-column table,
      five with the todo column under --info/-i; under --per-host one
      row per topic and hosting branch; under --json the
      machine-readable record array instead of a table. Every view
      shows only topics that still have their own branch.

      `remote`: the --remote/-r flag — read remote-tracking refs instead
                of local branches
      `info`: the --info/-i flag — add the todo column to the table
      `host`: the repeatable --host option — hosting-branch display
              names, exact match, union across values; empty — no
              filtering; an unknown name yields the empty board, never
              an error
      `per_host`: the --per-host flag — the expanded audit view, one
                  row per topic and hosting branch
      `json_output`: the --json flag — print the board as a
                     pretty-printed JSON array instead of a table
      `topic`: the repeatable --topic option — topic slugs, exact
               match, union across values, composed with `host`;
               empty — no filtering; an unknown slug yields the empty
               board, never an error
      `exit_code`: 0 on success (an empty board included), 1 on error

      Apply the `topic-board` practice for the board contract of the
      domain.
      Apply the `click` practice for the flags, the repeatable options,
      echo, and the color rules.
      Apply the `beautiful_json` practice for the JSON serialization.

      Algorithm:
      1. `json_output` together with `info` -> clean error: the todo is
         always present in the JSON records
      2. The default view: collect the per-host records via
         `collect_topic_board` with the scoped year and `remote`, then
         project via `aggregate_topic_board` with `host` and `topic`
      3. The per-host view: collect via `collect_topic_board` with the
         scoped year, `remote`, and `host` and `topic` as the record
         filters
      4. The table output: measure the terminal width and render — the
         default view via `render_topic_board` with the entries, the
         per-host view via `render_topic_host_rows` with the records;
         both take `info`
      5. The JSON output: render via `render_board_json` with the
         entries or the records
      6. An empty board renders nothing as a table and [] as JSON —
         exit 0

      Requirements:
      - Read-only — nothing is created, written, or switched
      - The year scoping and `remote` apply to the JSON output exactly
        as to the table

      Constraints:
      - Do not print the year or the artifacts, and no heading line
        outside the table or the JSON array — the table carries topic,
        branch, hosts, the todo column under `info`, and statuses only
      - Do not compute the board here — the projection of the default
        view and both filter semantics belong to the domain
```

**Body — insert** the new method after the `delete` method of the `topics` entity:

```yaml
    "clear(base_ref: str | None = None, yes: bool = False) -> exit_code: int": |
      Subcommand goga topics clear: resolve and delete the merged
      topics of the scoped year — every own-branched topic whose
      history the base ref carries — under one confirmation for the
      whole list.

      `base_ref`: the --base-ref value — the base whose tree defines
                  the clear scope
      `yes`: the --yes/-y flag — skip the confirmation
      `exit_code`: 0 on success (an empty scope and a declined
                   confirmation included), 1 on error

      Apply the `deleting` practice for the deletion and clear
      contracts of the domain.
      Apply the `project-configuration` practice for the topics
      section schema.
      Apply the `click` practice for the confirmation, echo, and
      exit-code propagation.

      Algorithm:
      1. Resolve the base — `base_ref`, otherwise the topics section of
         the effective configuration of the `ConfigOverlay` (loaded via
         `load_project_config`; the configuration load delivers the
         config amendment checkpoint per the `checkpoints` practice via
         the `ConfigHooks` checkpoint surface — amend_config(config=...));
         no base at all -> clean error naming the flag and the
         configuration line, before anything else
      2. Resolve the targets via `resolve_clear_targets` with the base
         and the scoped year; an empty scope echoes one line and
         exits 0
      3. Without `yes`: no interactive terminal -> clean error;
         otherwise print the topic-to-branch pairs of the list and ask
         one confirmation for the whole list; a declined answer exits
         0 with nothing deleted
      4. Delegate to `delete_topics` with the targets and the scoped
         year
      5. Echo the single result line
      6. Propagate the exit code

      Requirements:
      - The configuration is read only for values no flag provided; a
        missing configuration file counts as an unset value
      - The amendment summary lines of the `ConfigOverlay` print to
        stderr (nothing when empty)
      - One confirmation for the whole list — never per topic
      - The -y short form collides with the group --year; the
        positions on the command line distinguish them

      Constraints:
      - Do not compute the scope here — the scope resolution and the
        deletion belong to the domain
      - Do not delete anything before the resolution and the
        confirmation are complete
```

Methods `create`, `switch`, `delete` and the three render routines — carried verbatim.

**Footer — replace** `Description`:

```yaml
Description: |
  The goga topics command group — board in its two views and its
  JSON form, create with the optional-value todo option, switch,
  delete, and clear — over the topics domain.
```

#### `.usages/` files

**File:** `goga/commands/topics/.usages/topics-command.md` — change set:

1. **Header/intro** — audience line becomes "For users who manage work as topics: boarding,
   creating, switching, deleting, and clearing; for the command facade that registers the group."
   In the options paragraph, after "filters by hosting branch with the repeatable --host" insert "
   and by topic slug with the repeatable --topic"; append at the end of the paragraph: "the clear
   subcommand removes the merged topics of the scoped year." Add the new paragraph:

```markdown
A topic exists exactly as long as its own branch exists. The board
shows only topics that still have their own branch; a topic whose
history survives only in merged hosts appears in no view — its
history stays reachable through git itself.
```

2. **Boarding all work** — extend the examples with:

```markdown
    goga topics board --topic feature-foo
    goga topics board --host main --topic feature-foo
```

   In the narrative, drop "(--per-host keeps its rows)". Replace the `--host` filter paragraph with:

```markdown
--host NAME (repeatable) filters by exact hosting-branch display
name; --topic SLUG (repeatable) filters by exact topic slug; several
values of one filter unite, and the two filters compose — an entry
(or row) survives both. The own-branch requirement stands first: a
filter never resurrects a topic without an own branch. An unknown
name or slug leaves an empty board (or [] under --json) with exit 0 —
never an error.
```

3. **Auditing every hosting branch** — replace "one row per topic and
   hosting branch, showing that branch's own statuses — complete including topics without an own
   branch" with "one row per topic and hosting branch of the own-branched topics, showing that
   branch's own statuses".
4. **Deleting topics** — replace the back half of the section (from "The deletion is symmetric to
   creation-and-publication:" to the end of the section) with:

```markdown
The deletion removes the topic's own branch — the local branch and
its origin twin, the local first; a failed remote deletion restores
the local branch and stops with one clean error. The topic directory
joins the deletion exactly when no branch surviving the deletion
carries the topic — the target's own branch is not a gate. A topic
without its own branch is a clean error: there is no branch and
nothing to delete — it is history. The current branch hosting a
target is a clean error — switch away first. Unmerged commits never
block: the deletion is unconditional after the confirmation.
```

5. **Insert the new section** after "Deleting topics":

```markdown
## Clearing merged topics

    goga topics clear
    goga topics clear --base-ref origin/release/2.0.0
    goga topics --year 2025 clear --base-ref release/2.0.0
    goga topics clear -y

Removes every own-branched topic of the scoped year whose history
the base carries — the base tree contains the topic directory of the
year. The base comes from --base-ref or topics.base_ref of
.goga/config.yml; no base at all is a clean error before anything
else, naming the flag and the configuration line. The base is any
resolvable revision (a local branch, origin/..., a tag), is only
read, is never moved or pushed, and being on it is not an error.

Branchless topics are out of scope silently. A year without merged
topics succeeds with one result line (exit 0). One confirmation for
the whole list — "Clear N topics? [y/N]" with the topic-to-branch
pairs; --yes/-y skips it (a non-terminal without --yes is a clean
error; the -y collision with the group --year is resolved by
position). The deletion of each target is that of `goga topics
delete` — own branch and origin twin, restore-on-failure with one
clean error, earlier targets stay removed, topic_deleted fires per
fully removed target. Other hosts of a target are untouched. The
current branch being a target's own branch is a clean error — switch
away first.
```

6. **Exit codes** — replace with:

```markdown
Every subcommand exits 0 on success (an empty board, [], an empty
clear scope, and a declined confirmation included) and 1 on error,
with the error on stderr and no traceback.
```

The "Consuming the board as JSON", "Creating fresh work", "Creating and publishing fresh work", and
"Switching to existing work" sections stay verbatim.

### Cell 3 — `goga/commands` (MODIFIED)

#### CODEMANIFEST — change set

**Header.** `Imports` and `Usages` — no change (the `From: goga/commands/topics` block with the
`topics` type and the `topics-command` practice stays verbatim). `Annotations` — one edit: in the
`topics-command` sentence, replace "the board table, the creation flow, the switching flow, the
deletion flow, and the exit codes" with "the board table with its filters, the creation flow, the
switching flow, the deletion and clear flows, and the exit codes".

No body changes; no `.usages/` changes. The `->topics: {}` embedding stays valid — the group
entity persists and the new `clear` method is additive.

---

## Dependency Map

```
goga/history ────────┐
goga/topics/git ─────┤   (domain import sets unchanged)
goga/topics/editor ──┼──→ goga/topics ──────────────→ goga/commands/topics ──→ goga/commands
goga/topics/hooks ──┘        MOD:                         MOD:                  MOD:
                              • resolve_clear_targets      • +import resolve_    one annotation
                                (NEW, deletion.py)           clear_targets       sentence only
                              • DeleteTarget.has_dir       • group: clear        (practice
                              • resolve_delete_targets       (NEW), board        coverage); the
                              • collect_topic_board           +--topic (MOD)     topics group is
                              • aggregate_topic_board                             re-exported
                                                                                  unchanged

goga/config (+ goga/config/hooks) ──→ goga/commands/topics   (unchanged)
```

No cycles; the direction `commands → commands/topics → topics → {git, history, editor, hooks}` is
preserved. The single new edge is `resolve_clear_targets` inside the existing `From: goga/topics`
import block of the CLI cell. `goga/commands` consumes the CLI cell only through the unchanged
group embedding and the `topics-command` practice import; its single annotation sentence is the
sole touch.

## Verification Checklist

After **`goga/topics`**:

- `goga lint` passes for the cell (DSL syntax, links, import usage).
- `resolve_clear_targets`: scope = intersection (own-branched ∧ base-tree-carried); unresolvable
  base → clean error with reason; branchless topics silently out; empty scope → empty list;
  current-branch guard aborts; read-only (base never moved/pushed); targets alphabetical by topic.
- `resolve_delete_targets`: branchless topic → clean error "no branch, nothing to delete"; topic
  with own refs + carriers → own refs only, directory survivor-gated; unhosted directory still
  targetable; no hosting-branch advice in errors.
- `DeleteTarget.has_dir`: survivor gate = inventory minus the target's own refs; the own branch is
  not a gate.
- Board: `collect_topic_board` yields no branchless records in any mode (local, remote);
  `topics` filter exact/union/composed-with-`hosts`, unknown slug → empty list;
  `aggregate_topic_board` composes both filters and never resurrects; todo summary, twin collapse,
  sorting, current marker unchanged.
- Tests per the `convention` practice (pytest, direct calls; REPL-driven development cycle).
- Practices `topic-board.md` and `deleting.md` match the implemented behavior (no completeness
  clause, no hosting-branch advice).

After **`goga/commands/topics`**:

- `goga lint` passes; the new import entry `resolve_clear_targets` is used by the `clear` method.
- `goga topics clear`: base ladder flag → `topics.base_ref` → clean error naming `--base-ref` and
  `topics.base_ref`; empty scope → one line, exit 0; one confirmation for the whole list;
  `--yes/-y` skips (positional disambiguation with `--year`); non-terminal without `--yes` →
  clean error; declined → exit 0; delegation prints the single result line and propagates the
  exit code; amendment summary lines to stderr.
- `goga topics board --topic`: repeatable, exact, union, AND with `--host`; unknown slug → empty
  table / `[]` under `--json`, exit 0; works in default, `--per-host`, and `--json` forms;
  `--json --info` still a clean error.
- Renderers unchanged; pointer-only output in all three forms comes from the domain.
- Practice `topics-command.md` matches the implemented behavior.

After **`goga/commands`**:

- `goga lint` passes; the practice-coverage sentence names the board filters and the deletion and
  clear flows; no other line of the cell changed; the `->topics: {}` embedding stays valid.

Full gates: `pytest tests/ -x` passes, `ruff check` clean, `goga lint` passes across the project.
