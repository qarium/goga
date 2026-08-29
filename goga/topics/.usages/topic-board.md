# topics — the topic board

How to collect the cross-branch topic inventory with the `goga.topics`
facade. For consumers that show all work of a repository: CLI boards,
reviews, overviews.

The board sees one year at a time. Local mode reads the full branch inventory
and the current branch from the working copy — uncommitted progress is
visible, and a local branch absorbs its remote twin into one row. Remote mode
lists remote-tracking refs instead; the current branch
shows through its remote twin. No checkout happens: every ref is read
through git plumbing, so the working copy and .git stay untouched.

## Collecting the board

```python
from goga.topics import collect_topic_board

records = collect_topic_board()                          # current year, local
records = collect_topic_board(year="2025", remote=True)  # remote-tracking refs
for record in records:
    print(record.topic, record.branch, record.statuses, record.current)
```

- One `BoardRecord` per hosted topic: the slug, the hosting branch display
  name, the maximal status names in scale order, and the current marker.
- A local branch and its remote twin collapse to one row — the local branch
  wins. Two different branches hosting one slug stay two rows.
- Sorting: scale order of the first maximal status, then topic alphabet.
- A year without topics yields an empty list — not an error.
- Strictly read-only.
