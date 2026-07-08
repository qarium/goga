"""Runtime directory path composition for host-side container launchers.

This package owns the single shared formula for host-side runtime directories:

    ~/.goga/runtime/<purpose>/<normalized_project>/<branch>/<*suffix_parts>

It is a pure leaf utilities module: its routines return paths and strings, they
never create directories or write files. Directory creation and cleanup belong
to the consumer (e.g. `goga/commands/build` and `goga/commands/pipeline`).
"""

from .paths import normalize_project_path, resolve_git_branch, resolve_runtime_dir

__all__ = ["normalize_project_path", "resolve_git_branch", "resolve_runtime_dir"]
