# topics — creating fresh work

How to create a new branch off an explicit base with its topic using
the `goga.topics` facade. For consumers that start new work.

`create_topic` takes the branch name as entered and the base revision.
The branch keeps the name verbatim; the topic directory takes the
normalized slug of the year — the two may deliberately differ
(Feature/Foo_Bar branches into the feature-foo-bar topic).

## Creating

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar", "origin/main", todo="Fix.")  # current year
result = create_topic("Feature/Foo_Bar", "origin/main", todo="Fix.", year="2025")
result = create_topic("Feature/Foo_Bar", "origin/main", todo="Fix.", switch=True)
print(result)  # one line describing what was created
```

- The base is explicit — any revision git resolves; the branch starts
  at it and, by default, the repository stays on the caller's branch.
- The preflight runs before any input: an empty slug, an occupied
  branch name or slug, or the current branch hosting the same slug is
  a clean error with a hint to the board — creating the existing is an
  error, not an update.
- The todo: passed by value it is the todo; without a value an
  interactive terminal opens the external editor; without a terminal
  and without a value the call is a clean error naming the value
  option.
- The default path quarantines the topic into the branch: one commit
  carrying `todo.md` — the text as entered plus a trailing newline,
  UTF-8 — on top of the base, the branch planted at it, the working
  copy untouched. The todo is required on this path — git keeps no
  empty directories, so a cancelled entry is a clean error naming the
  value option and the switch form; the built-in message applies.
- `switch=True` checks out the fresh branch instead: the topic
  directory appears in the working copy and the resolved todo is
  written as `todo.md` — uncommitted, the last action of the path; the
  todo is optional on this path.
- On an interactive terminal without an explicit publish decision, the
  publication ask runs when a todo was obtained — the answer chooses
  between the local path and the publication path.

## Occupancy

- Occupancy oracles: a local branch ref, a remote-tracking ref, and
  the topic directory of the year — exposed as
  `check_branch_occupancy`; the branch-tree oracle is
  `check_slug_occupancy`.
- No artifact files are written inside the topic directory beyond the
  todo file — artifacts belong to their producers.
