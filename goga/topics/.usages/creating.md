# topics — creating fresh work

How to create a new branch off an explicit base with its topic
directory using the `goga.topics` facade. For consumers that start new
work.

`create_topic` takes the branch name as entered and the base revision.
The branch keeps the name verbatim; the topic directory takes the
normalized slug of the year — the two may deliberately differ
(Feature/Foo_Bar branches into the feature-foo-bar topic).

## Creating

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar", "origin/main")  # current year
result = create_topic("Feature/Foo_Bar", "origin/main", year="2025")
print(result)  # one line describing what was created
```

- The base is explicit — any revision git resolves; the branch starts
  at it and the repository switches to it.
- The preflight runs before any input: an empty slug, an occupied
  branch name or slug, or the current branch hosting the same slug is
  a clean error with a hint to the board — creating the existing is an
  error, not an update.
- The todo: passed by value it is the todo; without a value an
  interactive terminal opens the external editor — a cancelled entry
  creates without a todo; a non-interactive terminal without a value
  is a clean error naming the value option.
- On an interactive terminal without an explicit publish decision, the
  publication ask runs when a todo was obtained — the answer chooses
  between the normal path and the publication path.
- The normal path: branch off the base, switch, the topic directory,
  and todo.md as the last action — the text as entered plus a trailing
  newline, UTF-8.
- No todo resolved — no todo.md is written.

## Occupancy

- Occupancy oracles: a local branch ref, a remote-tracking ref, and
  the topic directory of the year — exposed as
  `check_branch_occupancy`; the branch-tree oracle is
  `check_slug_occupancy`.
- No artifact files are written inside the topic directory beyond the
  todo file — artifacts belong to their producers.
