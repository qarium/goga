"""Git-environment introspection cell for the history domain — the branch reader, the branch inventory."""

from .branch import resolve_current_branch_name
from .refs import BranchRef, list_branch_refs

__all__: list[str] = ["BranchRef", "list_branch_refs", "resolve_current_branch_name"]
