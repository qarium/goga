# topics/git — refs and branch switching

How to enumerate branch refs, read ref trees, and switch branches with the
`goga.topics.git` facade. For consumers building inventories and switching
work: the topics domain, higher-level orchestration.

The cell is pure git access — read-only inventory plus the bounded local
mutation set. Every policy decision (when to check cleanliness, which branch
wins a duplicate, what a conflict means) belongs to the caller.

## Enumerating branch refs

```python
from goga.topics.git import list_branch_refs

refs = list_branch_refs()
for ref in refs:
    print(ref.name, "remote" if ref.remote else "local")
```

- Local branches and remote-tracking refs come back in one list, sorted by
  display name; a local branch and its remote twin are two distinct refs.
- Read-only, no network.

## Reading a ref tree

```python
from goga.topics.git import read_ref_tree_paths

prefix = ".goga/history/"  # the history tree root, repo-root-relative
paths = read_ref_tree_paths("feature-foo", prefix)
```

- Paths come back relative to the repository root; no checkout, no
  worktree, no temp directory — the working copy stays untouched.
- One git invocation per ref; a ref or prefix without matches yields an
  empty list.

## Reading one file of a ref

```python
from goga.topics.git import read_ref_file

path = ".goga/history/2026/feature-foo/todo.md"  # repo-root-relative
content = read_ref_file("feature-foo", path)
if content is not None:
    first = next(
        (line.lstrip("#").strip() for line in content.splitlines() if line.lstrip("#").strip()),
        "",
    )
    print(first)
```

- Returns the file content as text, or None when the file cannot be read
  at the ref — an absent file is the normal case, not an error; any other
  git failure reads the same way.
- One git invocation per file; no checkout, no worktree, no temp
  directory — the working copy stays untouched.

## Switching branches

```python
from goga.topics.git import (
    BranchRef,
    checkout_local_branch,
    create_and_switch_branch,
    create_branch_from_remote_tracking,
    is_working_tree_clean,
)

if is_working_tree_clean():
    checkout_local_branch("feature-foo")  # existing local branch
    create_and_switch_branch("Feature/Foo_Bar")  # fresh work, name verbatim

remote_ref = BranchRef(name="origin/feature-foo", remote=True)
create_branch_from_remote_tracking(remote_ref)  # remote-only host
```

- `checkout_local_branch` takes a short local branch name; the branch must
  exist.
- `create_and_switch_branch` takes the branch name exactly as entered — no
  normalization, no suffixing; git owns name validity.
- `create_branch_from_remote_tracking` takes a remote `BranchRef` obtained
  from `list_branch_refs` and creates a local branch with its short name at
  the ref's commit — no network.
- Probe cleanliness with `is_working_tree_clean` before any mutation — the
  cell never decides on its own.
