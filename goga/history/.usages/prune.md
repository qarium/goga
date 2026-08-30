# history — pruning orphan topics

How to clean up the orphan topics of a year with the `goga.history`
facade. For consumers that maintain the tree: CLI cleanup commands,
maintenance scripts.

A topic is an orphan when no branch of the repository inventory hosts
its slug: a local branch named so, or a remote-tracking ref whose short
name — the part after the first "/" — normalizes to it. The protection
is year-independent: a branch protects same-named topics of every year.
Deletion is unconditional — no status protects a topic, and the whole
topic directory goes with all of its artifacts. The tree lives outside
git, so a deleted topic directory is unrecoverable; run the dry pass
first.

## Pruning a year

```python
from goga.history import prune_topics

candidates = prune_topics(dry_run=True)  # lists candidates, deletes nothing
removed = prune_topics()                 # current year, deletes orphans
removed = prune_topics(year="2025")      # an explicit year
print("\n".join(removed))
```

- One slug per result entry, sorted alphabetically; an empty result is
  an empty list — not an error.
- `year` defaults to the current year; other years are never touched.
- Filesystem-only: no branch, ref, or index of git is mutated in any
  mode.

## Deleting one topic directory

```python
from goga.history import remove_topic_dir

removed = remove_topic_dir("release-1-3-0", year="2025")
```

- True when the directory existed and was deleted, False when it was
  absent — idempotent absence.
- Deletes the whole directory with every artifact inside; the orphan
  decision belongs to the caller.
