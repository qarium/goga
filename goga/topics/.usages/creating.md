# topics — creating fresh work

How to create a new branch off an explicit base with its topic using
the `goga.topics` facade. For consumers that start new work —
interactive callers and scripted pipelines alike.

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
- The todo resolves through an acquisition ladder, in order: an
  explicit `todo` value; else the declared stdin source
  (`todo_from_stdin=True`) when the piped content carries at least one
  non-whitespace character; else the external editor on an interactive
  terminal; else no todo — the path rules decide what a missing todo
  means.
- Stdin rules: a terminal stdin is never read; a non-terminal stdin
  is read fully exactly once, at todo-resolution time. Piped bytes
  that are not UTF-8 are a clean error naming the todo. Piped content
  without any declared source — no `todo` value and no
  `todo_from_stdin` — is a clean error naming the todo: piped content
  is never silently ignored. An empty or whitespace-only stdin counts
  as no content: the editor opens on a terminal, and headless the path
  rules apply.
- The stdin-resolved todo behaves exactly like a value: written as
  entered plus a trailing newline, UTF-8, through the same amendment
  hooks. When the todo came from stdin, the publication ask never
  appears — publication happens only through `publish=True`.
- The default path quarantines the topic into the branch: one commit
  carrying `todo.md` — the text as entered plus a trailing newline,
  UTF-8 — on top of the base, the branch planted at it, the working
  copy untouched. The todo is required on this path — git keeps no
  empty directories, so an unresolved todo is a clean error naming the
  todo source and the switch form; the built-in message applies.
- `switch=True` checks out the fresh branch instead: the topic
  directory appears in the working copy and the resolved todo is
  written as `todo.md` — uncommitted, the last action of the path; the
  todo is optional on this path.
- On an interactive terminal without an explicit publish decision, the
  publication ask runs when a todo was obtained and did not come from
  stdin — the answer chooses between the local path and the
  publication path.
- The written todo.md content and the built commit message are the
  final amended values when a tool package subscribes an amendment
  hook — the creation amendment runs before the first mutation of the
  chosen path.

## Scripted creation with the todo from stdin

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar", "origin/main", todo_from_stdin=True)
result = create_topic("Feature/Foo_Bar", "origin/main", todo_from_stdin=True, switch=True)
```

- Pipe the multi-line todo into the process and declare
  `todo_from_stdin=True`; the piped content becomes the todo with the
  value-form semantics. No editor opens and nothing is asked — the
  call runs fully non-interactive.
- Works on every creation path — the quarantined default,
  `switch=True`, and `publish=True`.
- An explicit `todo` value wins over piped content; content-free
  stdin falls through to the editor on a terminal and to the path
  rules headless.

## Occupancy

- Occupancy oracles: a local branch ref, a remote-tracking ref, and
  the topic directory of the year — exposed as
  `check_branch_occupancy`; the branch-tree oracle is
  `check_slug_occupancy`.
- No artifact files are written inside the topic directory beyond the
  todo file — artifacts belong to their producers.
