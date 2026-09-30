# topics — publishing work

How to publish topic work without leaving the current branch through the
`goga.topics` facade — fresh work via `publish_topic`, an existing branch
via `publish_existing_topic`. For consumers that register new or finished
work on the remote board while the user keeps working: the topics command
group, higher-level orchestration.

`publish_topic` takes the branch name as entered, a required multi-line
todo, an explicit base, and a commit message template; `commit_message`
omitted — the built-in default `Create topic '{slug}'`. The branch keeps the
name verbatim; the topic directory takes the normalized slug of the year —
the two may deliberately differ.

## Publishing fresh work

```python
from goga.topics import publish_topic

result = publish_topic(
    "Feature/Foo_Bar",
    "Fix payment retries.\n\nRetries ignore the backoff cap.",
    "origin/main",
    "Create topic '{slug}'",
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
- The message template replaces {slug} with the topic slug and {base}
  with the base name; a template without the placeholders is used as
  is. The template source is the create-section key resolved by the
  caller; the built-in default is `Create topic '{slug}'`.
- A failed publication rolls back fully — the branch is deleted and one
  clean error names the reason; a re-run after the cause is resolved
  succeeds.
- The base resolves as git resolves it — a local branch is valid; no fetch
  happens.

## Publishing an existing branch

`publish_existing_topic` delivers a topic's own branch to origin as an
operation of its own — creating fresh work is not part of it.

    from goga.topics import publish_existing_topic

    result = publish_existing_topic("feat-x")
    print(result)  # one line: the outcome kind

| origin twin vs own tip | Outcome |
|---|---|
| twin absent | pushed — the push creates the twin |
| twin == tip | up-to-date — success, nothing to do |
| twin strictly ahead | remote-ahead — success, nothing to push |
| diverged | clean error naming both tips; reconcile via git, re-run |

- One targeted fetch of the topic's own twin, reported by one stdout
  line before it runs; no confirmation; a dirty tree is irrelevant.
- Delivery only — no force, no lease, ever; the local branch and the
  working copy stay untouched.
- Every completed publication — the idempotent outcomes included —
  emits `topic_published` with `remote_branch=origin/<branch>`, the
  commit facts of the twin tip, and the outcome kind.
- `origin` unconfigured is a clean error before any network operation.

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
