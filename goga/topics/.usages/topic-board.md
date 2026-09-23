# topics — the topic board

How to collect the cross-branch topic inventory of one year with the
`goga.topics` facade, in its two projections. For consumers that show
all work of a repository: CLI boards, reviews, overviews, tools.

The board sees one year at a time. The per-host collection is the
single source of facts: one record per topic and hosting branch,
twin-collapsed, complete including topics that no longer have their
own branch. The default view is a projection of those records — one
entry per topic that still has its own branch. Local mode reads the
full branch inventory and the current branch from the working copy —
uncommitted progress is visible. Remote mode lists remote-tracking
refs instead; the current branch shows through its remote twin. No
checkout happens: every ref is read through git plumbing, so the
working copy and .git stay untouched.

## Collecting the per-host records

```python
from goga.topics import collect_topic_board

records = collect_topic_board()  # current year, local — every topic × host row
records = collect_topic_board(year="2025", remote=True)
records = collect_topic_board(hosts=("main", "release/1.3"))  # named hosts only
```

- One `BoardRecord` per topic and hosting branch: the slug, the
  hosting branch display name, that branch's maximal status names in
  scale order, the current and remote markers, and the todo summary —
  the first line of the topic's `todo.md` that yields text after
  leading `#` markers are stripped and the edges trimmed, or None
  when the topic has none. Rows hosted by other branches read their
  summaries from the ref trees without checkout; the current branch's
  row reads the working copy, so an uncommitted todo edit shows at
  once. The file is never modified — the stripping is for display.
- A local branch and its remote twin collapse to one row — the local
  branch wins. Two different branches hosting one slug stay two rows.
- `hosts` keeps the records of the named hosting branches only —
  exact display-name match, several names unite; an unknown name
  yields the empty list, never an error.
- Sorting: scale order of the first maximal status, then topic
  alphabet.
- A year without topics yields an empty list — not an error.
- Strictly read-only.

## Aggregating the one-entry-per-topic view

```python
from goga.topics import aggregate_topic_board

entries = aggregate_topic_board(records)  # one entry per topic with an own branch
entries = aggregate_topic_board(records, hosts=("main",))
for entry in entries:
    print(entry.topic, entry.branch, entry.hosts, entry.statuses, entry.current, entry.todo)
```

- One `BoardEntry` per topic that still has an own branch — a hosting
  branch whose branch part (the whole name of a local branch, the
  short name of a remote-tracking ref) normalizes into the topic
  slug; a remote-tracking ref qualifies, so remote-only topics keep
  their entry. A topic whose history survives only in merged hosts
  produces no entry — its rows live in the per-host records.
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
- The `hosts` filter keeps the entries whose hosts list contains any
  given name — union, exact match; an own branch is still required,
  the filter never resurrects a hidden topic; an unknown name yields
  the empty list, never an error.
- The entries sort like the records: scale order of the first maximal
  status, then topic alphabet. Strictly read-only over the records —
  no second git read happens; both views derive from one collection
  pass.
