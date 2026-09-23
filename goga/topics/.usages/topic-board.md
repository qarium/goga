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
