# topics — creating fresh work

How to create a new branch with its topic directory using the `goga.topics`
facade. For consumers that start new work.

`create_topic` takes the branch name as entered. The branch keeps the name
verbatim; the topic directory takes the normalized slug of the year — the
two may deliberately differ (Feature/Foo_Bar branches into the
feature-foo-bar topic).

## Creating

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar")             # current year
result = create_topic("Feature/Foo_Bar", year="2025")
print(result)  # one line describing what was created
```

- A free name creates the branch, switches to it, and creates the topic
  directory of the year.
- The current branch already hosting the same slug is an idempotent
  success — no mutation.
- An occupied name or an empty slug triggers a re-ask on an interactive
  terminal, or a clean error with the reason and a hint otherwise.
- Occupancy oracles: a local branch ref, a remote-tracking ref, and the
  topic directory of the year — exposed as `check_branch_occupancy`.
- No artifact files are written inside the topic directory — artifacts
  belong to their producers.

## Creating with a title

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar", title="Payment retry")
```

- Fresh work: the branch, the switch, the topic directory, and the
  title file `title.txt` — the text as entered plus a trailing newline,
  UTF-8.
- The current branch already hosting the same slug with an explicit
  title: the topic directory is ensured and `title.txt` is created or
  overwritten — nothing else mutates, no switch happens.
- Without a title the behavior carries no title file at all.
- `title.txt` marks the `new` status on the topic status scale; no
  other artifact is written — artifacts belong to their producers.
