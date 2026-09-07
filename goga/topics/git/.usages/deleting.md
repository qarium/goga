# topics/git — deleting a branch on origin

How to remove a branch from the origin remote (and its local twin) with
the `goga.topics.git` facade. For consumers that tear down published
work: the topics domain, higher-level orchestration.

The deletion is unconditional after the caller's confirmation — no
merge checks, no force flags. Every policy decision — when deletion is
allowed, what a failed deletion means — belongs to the caller.

## Deleting a branch on origin

    from goga.topics.git import delete_remote_branch

    delete_remote_branch("feature-foo")   # gone from origin

- The deletion push is a network operation of the cell — the other one
  publishes branches; no fetch ever happens.
- The local branch and the working copy stay untouched.
- A git failure surfaces as a clean error carrying the reason.

## Deleting a local and remote pair with restore

    from goga.topics.git import (
        create_branch_at_commit,
        delete_local_branch,
        delete_remote_branch,
        resolve_ref_commit,
    )

    commit = resolve_ref_commit("feature-foo")   # capture BEFORE deletion
    delete_local_branch("feature-foo")
    try:
        delete_remote_branch("feature-foo")
    except Exception:
        create_branch_at_commit("feature-foo", commit)   # restore
        raise

- Capture the commit before the local deletion — after it the name no
  longer resolves.
- A failed remote deletion leaves the pair recoverable: the local
  branch is restored at the captured commit and the error propagates —
  the caller decides the reporting.
