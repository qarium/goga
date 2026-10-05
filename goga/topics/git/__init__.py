"""Git-access cell for the topics domain."""

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
    resolve_commit_message,
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
    "resolve_commit_message",
    "resolve_commit_tree",
    "resolve_ref_commit",
]
