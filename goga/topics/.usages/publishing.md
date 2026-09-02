# topics — publishing fresh work

How to create and publish a topic branch without leaving the current branch
with the `goga.topics` facade. For consumers that register new work on the
remote board while the user keeps working: the topics command group,
higher-level orchestration.

`publish_topic` takes the branch name as entered, a required multi-line
todo, an explicit base, and a commit message template; `commit_message`
omitted — the built-in default `goga: create topic {slug}`. The branch keeps the
name verbatim; the topic directory takes the normalized slug of the year —
the two may deliberately differ.

## Publishing fresh work

```python
from goga.topics import publish_topic

result = publish_topic(
    "Feature/Foo_Bar",
    "Fix payment retries.\n\nRetries ignore the backoff cap.",
    "origin/main",
    "goga: create topic {slug}",
)
print(result)  # one line: created and published on the remote
```

- The caller stays on their branch: the working copy, the index, and HEAD
  are untouched — a dirty tree and a detached HEAD do not interfere.
- The branch carries exactly one commit on top of the base: the todo file
  `todo.md` — the text as entered plus a trailing newline, UTF-8 — in the
  topic directory of the year; the topic shows the `todo` status.
- The todo is required and non-empty — an empty todo is a clean error
  before any mutation.
- The message template replaces {slug} with the topic slug; a template
  without the placeholder is used as is.
- A failed publication rolls back fully — the branch is deleted and one
  clean error names the reason; a re-run after the cause is resolved
  succeeds.
- The base resolves as git resolves it — a local branch is valid; no fetch
  happens.

## Occupancy

- An occupied name, an empty slug, or a slug already hosted by any branch
  of the inventory is a clean error with a hint to the board.
- `check_slug_occupancy` exposes the branch-tree oracle — the slug
  duplicate check across the inventory; the three local oracles stay in
  `check_branch_occupancy`.

## Preconditions

- The origin remote must be configured — a clean error otherwise, before
  any mutation.
- The repository git identity must be set — an unset identity is a clean
  git error.
- The current branch must not host the same slug — the fast path is only
  for fresh work.
