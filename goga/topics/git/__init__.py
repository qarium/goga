"""Git-access cell for the topics domain.

The branch-ref inventory, the file-path reading of a ref tree, the file
contents of a ref tree, the bounded set of host-side branch mutations
— checking out a local branch, creating a local branch from a
remote-tracking ref, create-and-switch to a new branch, and the
working-tree cleanliness probe — and the quarantined publication:
resolving a revision into its commit, building one commit over a base
through a temporary index without touching the working copy, planting and
deleting a branch without switching, pushing a branch to origin with
upstream binding, and the origin probe. It is environment access, not
topic logic — every decision belongs to the caller.
"""

from .publish import (
    commit_file_on_base,
    create_branch_at_commit,
    delete_local_branch,
    origin_configured,
    push_branch,
    resolve_ref_commit,
)
from .refs import BranchRef, list_branch_refs
from .switch import (
    checkout_local_branch,
    create_and_switch_branch,
    create_branch_from_remote_tracking,
    is_working_tree_clean,
)
from .trees import read_ref_file, read_ref_tree_paths

__all__: list[str] = [
    "BranchRef",
    "checkout_local_branch",
    "commit_file_on_base",
    "create_and_switch_branch",
    "create_branch_at_commit",
    "create_branch_from_remote_tracking",
    "delete_local_branch",
    "is_working_tree_clean",
    "list_branch_refs",
    "origin_configured",
    "push_branch",
    "read_ref_file",
    "read_ref_tree_paths",
    "resolve_ref_commit",
]
