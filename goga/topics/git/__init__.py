"""Git-access cell for the topics domain.

The branch-ref inventory, the file-path reading of a ref tree, and the
bounded set of host-side branch mutations — checking out a local branch,
creating a local branch from a remote-tracking ref, create-and-switch to a
new branch, and the working-tree cleanliness probe. It is environment
access, not topic logic — every decision belongs to the caller.
"""

from .refs import BranchRef, list_branch_refs

__all__: list[str] = ["BranchRef", "list_branch_refs"]
