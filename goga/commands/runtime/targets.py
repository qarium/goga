"""Target and branch resolution routines for the goga runtime command cell."""

from __future__ import annotations

from pathlib import Path

from ...runtime import resolve_git_branch, resolve_runtime_dir


def resolve_effective_branch(branch: str | None = None) -> str:
    """Resolve the effective branch segment of the location identity.

    Args:
        branch: The raw group option value; None and the empty string mean
            no branch given. A non-empty value is slugified (every forward
            slash replaced by a hyphen) and used directly — git is not
            consulted and no validation is performed; the state of a deleted
            branch is a legitimate address.

    Returns:
        The effective branch segment — a single filesystem-safe path
        component: the slugified explicit branch, or the slugified current
        git branch with its ``"default"`` fallback.
    """
    if branch:
        return branch.replace("/", "-")

    return resolve_git_branch()


def resolve_build_target_dir(branch_segment: str) -> Path:
    """Resolve the build artifacts directory of the current project.

    Args:
        branch_segment: The effective branch segment produced by
            :func:`resolve_effective_branch`.

    Returns:
        The absolute host path
        ``~/.goga/runtime/builds/<normalized_project>/<branch_segment>`` —
        the same directory the build command bind-mounts. Pure with respect
        to the filesystem: the directory is not created.
    """
    return resolve_runtime_dir("builds", branch=branch_segment)


def sanitize_pipeline_name(name: str) -> str:
    """Sanitize a pipeline name into its host path segment and target label.

    Args:
        name: The pipeline name as used at run time.

    Returns:
        The colon-free segment — every colon replaced by a hyphen, the same
        transformation the run composes for its state directory. Literal
        one-to-one replacement: no collapsing, no trimming.
    """
    return name.replace(":", "-")


def resolve_pipeline_target_dir(pipeline_name: str, branch_segment: str) -> Path:
    """Resolve the artifacts directory of the named pipeline of the current project.

    Args:
        pipeline_name: The pipeline name as used at run time; sanitized
            exactly as the run composes its state segment.
        branch_segment: The effective branch segment produced by
            :func:`resolve_effective_branch`.

    Returns:
        The absolute host path
        ``~/.goga/runtime/pipelines/<normalized_project>/<branch_segment>/<sanitized>``
        — the directory the run actually uses. Pure with respect to the
        filesystem: the directory is not created.
    """
    sanitized = sanitize_pipeline_name(pipeline_name)

    return resolve_runtime_dir("pipelines", sanitized, branch=branch_segment)
