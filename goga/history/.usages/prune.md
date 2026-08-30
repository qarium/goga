# history — pruning orphan topics

How to clean up the orphan topics of a year with the `goga.history`
facade. For consumers that maintain the tree: CLI cleanup commands,
maintenance scripts.

A topic is an orphan when no branch of the repository inventory hosts
its slug: a local branch whose name normalizes to it, or a
remote-tracking ref whose short name — the part after the first "/" —
normalizes to it. The protection
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
- The slugs come out normalized: a manually unnormalized directory name
  is listed yet stays on disk — only the normalized twin path is deleted.
  Treat the list as the candidate set, not a receipt of deletions.
- `year` defaults to the current year; other years are never touched.
- Filesystem-only: no branch, ref, or index of git is mutated in any
  mode. The ref listing is the one git call of the flow; its failures —
  a git infrastructure error or a missing git binary — propagate to the
  caller, so wrap them where a clean message is required.

## Reading the branch inventory

The protection oracle of the prune is the full branch inventory, read
with `list_branch_refs`:

```python
from goga.history import BranchRef, list_branch_refs

refs = list_branch_refs()
for ref in refs:
    print(ref.name, "remote" if ref.remote else "local")
```

- Local branches and remote-tracking refs come back in one list,
  sorted by display name; `name` is `<remote>/<branch>` for a
  remote-tracking ref, and a local branch and its remote twin stay two
  distinct refs.
- Read-only and offline — the refs as they exist locally; a git failure
  of the listing propagates to the caller.

## Deleting one topic directory

```python
from goga.history import remove_topic_dir

existed = remove_topic_dir("release-1-3-0", year="2025")
```

- True when the directory existed and was deleted, False when it was
  absent — idempotent absence.
- Deletes the whole directory with every artifact inside; the orphan
  decision belongs to the caller.
