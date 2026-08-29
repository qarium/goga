"""Git-access cell for the topics domain.

The branch-ref inventory, the file-path reading of a ref tree, and the
bounded set of host-side branch mutations — checking out a local branch,
creating a local branch from a remote-tracking ref, create-and-switch to a
new branch, and the working-tree cleanliness probe. It is environment
access, not topic logic — every decision belongs to the caller.
"""

from .refs import BranchRef, list_branch_refs
from .switch import (
    checkout_local_branch,
    create_and_switch_branch,
    create_branch_from_remote_tracking,
    is_working_tree_clean,
)
from .trees import read_ref_tree_paths

__all__: list[str] = [
    "BranchRef",
    "checkout_local_branch",
    "create_and_switch_branch",
    "create_branch_from_remote_tracking",
    "is_working_tree_clean",
    "list_branch_refs",
    "read_ref_tree_paths",
]
