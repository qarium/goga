# topics — deleting topics and clearing merged topics

How to resolve and delete identified topics — and how to resolve and
clear the merged topics of a year — with the `goga.topics` facade.
For consumers that tear down work: the topics command layer.

A topic exists exactly as long as its own branch exists. Deleting a
topic deletes its own branch — the local branch and its origin twin —
and nothing else: no host tree is touched, no commit is created,
history is communal and stays. The topic directory of the working
copy is litter when no branch surviving the deletion carries the
topic — it goes with the deletion; a surviving branch carrying the
topic keeps the directory, it is history.

## Resolving targets

    from goga.topics import resolve_delete_targets

    targets = resolve_delete_targets(["feature-foo", "release-1-3-0"])
    for target in targets:
        print(target.topic, target.branch, target.remote, target.has_dir)

- Identifier tiers: exact branch name, exact topic slug, prefixes —
  plus topic directories of the year no branch hosts. An exact branch
  name hosting nothing falls through to the slug tier: an unpublished
  topic (its todo uncommitted) resolves through its disk directory,
  while the bare branch itself never resolves.
- No match or several matches -> a clean error, no interactive
  selection; the whole call is cancelled — all-or-nothing.
- A local branch and its origin twin form one target; repeated
  identifiers collapse.
- A topic without its own branch — its history hosted by other
  branches only — is a clean error: the topic has no branch, there is
  nothing to delete, it is history.
- A topic directory no branch hosts stays targetable — working-copy
  hygiene (no refs, directory only).
- The current branch hosting a target -> a clean error asking to
  switch away first.

## Deleting confirmed targets

    from goga.topics import delete_topics

    result = delete_topics(targets)   # the caller has confirmed
    print(result)                      # one line — the outcome

- The confirmation belongs to the caller; the deletion is
  unconditional — no merge checks.
- Local branch + origin twin: both removed, the local first; a failed
  remote deletion restores the local branch at its former commit and
  raises one clean error — targets removed before the failure stay
  removed.
- The topic directory joins the deletion exactly when no branch
  surviving the deletion carries the topic — the target's own branch
  is not a gate; a surviving host carrying the topic keeps it.
- The deletion push is a network operation of the domain; no fetch
  ever happens.

## Resolving the clear scope of a year

    from goga.topics import resolve_clear_targets

    targets = resolve_clear_targets("origin/release/2.0.0")
    targets = resolve_clear_targets("release/2.0.0", year="2025")
    result = delete_topics(targets)   # confirm first, then delete

- The clear scope: every own-branched topic of the year whose topic
  directory the base ref's tree carries — the merged topics of the
  year. The base is any resolvable revision (a local branch, an
  `origin/...` ref, a tag), is only read, and being on it is not an
  error.
- Branchless topics are out of scope silently; a year without merged
  topics yields the empty list — print one line and succeed.
- The targets are ordinary `DeleteTarget`s: confirm once for the
  whole list, then delete via `delete_topics` — the deletion
  semantics, the restore-on-failure behavior, and the `topic_deleted`
  events are those of the machinery above.
- Only the target's own refs enter a target — the other hosts of a
  target are untouched.
- The current branch being a target's own branch -> a clean error
  asking to switch away first.
