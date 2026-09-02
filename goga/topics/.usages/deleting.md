# topics — deleting identified topics

How to resolve and delete identified topics with the `goga.topics`
facade. For consumers that tear down work: the topics command layer.

`resolve_delete_targets` turns identifiers into targets — everything is
checked before anything is removed. `delete_topics` executes the
confirmed deletion.

## Resolving targets

    from goga.topics import resolve_delete_targets

    targets = resolve_delete_targets(["feature-foo", "release-1-3-0"])
    for target in targets:
        print(target.topic, target.branch, target.remote, target.has_dir)

- Identifier tiers: exact branch name, exact topic slug, prefixes —
  plus topic directories of the year no branch hosts.
- No match or several matches -> a clean error, no interactive
  selection; the whole call is cancelled — all-or-nothing.
- A local branch and its origin twin form one target; repeated
  identifiers collapse.
- Merged work is out of scope: a topic hosted by a branch that is not
  its own topic branch (the post-merge state) is a clean error naming
  the hosting branch — remove it from the hosting branch's tree
  instead.
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
- A directory without branches is removed from disk.
- The deletion push is a network operation of the domain; no fetch
  ever happens.
