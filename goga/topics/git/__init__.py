"""Git-access cell for the topics domain.

The branch-ref inventory, the file-path reading of a ref tree, the file
contents of a ref tree, the bounded set of host-side branch mutations
— checking out a local branch, creating a local branch from a
remote-tracking ref, create-and-switch to a new branch, the
working-tree cleanliness probe, and the three in-place moves of the
current branch (merge, rebase, fast-forward) — and the quarantined
publication: resolving a revision into its commit, building one commit
over a base through a temporary index without touching the working
copy, planting and deleting a branch without switching, the network
operations of the cell — pushing a branch to origin with upstream
binding, deleting a branch on the origin remote, the targeted fetch of
one base branch, the lease-protected push, and the write-through push
of a revision — and the origin probe. The exchange zone adds the
checkout-free surface: the git version gate, the containment check, the
commit-to-tree peel, the tree merge with its conflict signal, the
commit construction over parents, the scripted commit replay, and the
single-ref plant. It is environment access, not topic logic — every
decision belongs to the caller.
"""

from .exchange import (
    create_commit_from_tree,
    is_ancestor,
    merge_tree,
    point_branch_at_commit,
    replay_commits,
    require_git_version,
    resolve_commit_tree,
)
from .publish import (
    commit_file_on_base,
    create_branch_at_commit,
    delete_local_branch,
    delete_remote_branch,
    fetch_branch,
    origin_configured,
    push_branch,
    push_branch_with_lease,
    push_revision_to_branch,
    resolve_ref_commit,
)
from .refs import BranchRef, list_branch_refs
from .switch import (
    checkout_local_branch,
    create_and_switch_branch,
    create_branch_from_remote_tracking,
    fast_forward_current_branch,
    is_working_tree_clean,
    merge_into_current,
    rebase_current_onto,
)
from .trees import read_ref_file, read_ref_tree_paths

__all__: list[str] = [
    "BranchRef",
    "checkout_local_branch",
    "commit_file_on_base",
    "create_and_switch_branch",
    "create_branch_at_commit",
    "create_branch_from_remote_tracking",
    "create_commit_from_tree",
    "delete_local_branch",
    "delete_remote_branch",
    "fast_forward_current_branch",
    "fetch_branch",
    "is_ancestor",
    "is_working_tree_clean",
    "list_branch_refs",
    "merge_into_current",
    "merge_tree",
    "origin_configured",
    "point_branch_at_commit",
    "push_branch",
    "push_branch_with_lease",
    "push_revision_to_branch",
    "read_ref_file",
    "read_ref_tree_paths",
    "rebase_current_onto",
    "replay_commits",
    "require_git_version",
    "resolve_commit_tree",
    "resolve_ref_commit",
]
