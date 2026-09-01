# topics/git — building and publishing a branch

How to create a committed branch off a base and publish it to origin with
the `goga.topics.git` facade, without touching the working copy. For
consumers that start work on behalf of the user while the user stays on
their branch: the topics domain, higher-level orchestration.

The quarantined path never touches the working copy, the repository index,
or HEAD — a dirty tree and a detached HEAD do not interfere. The push to
origin is the only network operation; everything else is local. Every
policy decision — when to roll back, what a conflict means — belongs to
the caller.

## Resolving a base

```python
from goga.topics.git import resolve_ref_commit

commit = resolve_ref_commit("origin/main")   # any rev string
```

- The revision resolves as git resolves it — a branch, a remote-tracking
  ref, a tag, or a hash; a local branch is a valid base.
- An unresolvable revision is a clean error carrying the git reason —
  resolve the base before any mutation.
- Read-only, no fetch — a stale remote-tracking base is the caller's
  accepted condition.

## Building a commit without the working copy

```python
from goga.topics.git import commit_file_on_base

commit = commit_file_on_base(
    base,                                                  # from resolve_ref_commit
    ".goga/history/2026/feature-foo/todo.md",              # repo-root-relative
    "Fix payment retries.\n\nRetries ignore the cap.\n",   # content as text
    "goga: create topic feature-foo",                      # final message
)
```

- One commit that adds exactly one file on top of the parent — the tree is
  built in a temporary index isolated from the repository; nothing
  persists after the call and no temporary directories appear outside
  .git.
- The message is final — placeholders belong to the caller.
- The commit carries the repository git identity; an unset identity is a
  clean git error.
- The commit exists only as a hash — no branch points to it until the
  caller plants one.

## Planting and publishing a branch

```python
from goga.topics.git import (
    create_branch_at_commit,
    origin_configured,
    push_branch,
)

if not origin_configured():
    ...  # clean error: origin is not configured — before any mutation

create_branch_at_commit("Feature/Foo_Bar", commit)   # name verbatim, no switch
push_branch("Feature/Foo_Bar")                        # push -u origin
```

- `create_branch_at_commit` takes the branch name exactly as entered and
  leaves the working copy on its current branch.
- `push_branch` publishes exactly the named branch and binds its upstream
  — later push and pull need no arguments; the local branch stays in the
  repository.
- Probe `origin_configured` before creating anything — the probe is
  read-only and never raises.

## Rolling back

```python
from goga.topics.git import delete_local_branch

delete_local_branch("Feature/Foo_Bar")   # full rollback of a failed publication
```

- `delete_local_branch` removes the local branch ref; the working copy, the
  index, and HEAD stay untouched — nothing else was ever mutated.
- The cell never decides to roll back — a git failure of the push
  propagates with its message; the caller owns the failure policy.
