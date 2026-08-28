"""Git-environment introspection cell for the history domain — the branch reader."""

from .branch import resolve_current_branch_name

__all__: list[str] = ["resolve_current_branch_name"]
