"""The ``resolve_build_workflow`` routine — selecting and loading the workflow of a build."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..pipeline.workflow import LoadedWorkflow, load_workflow


def resolve_build_workflow(
    workflow_cli: str | None,
    workflow_env: str | None,
    cli_profile: str | None = None,
    env_profile: str | None = None,
    home_profiles: dict[str, dict[str, Any]] | None = None,
) -> LoadedWorkflow | None:
    """Select and load the workflow that drives a build — the CLI flag beats the environment value.

    Args:
        workflow_cli: the ``-w/--workflow`` flag value, or ``None``.
        workflow_env: the ``GOGA_WORKFLOW`` value, or ``None``.
        cli_profile: the ``--profile`` flag value, or ``None``.
        env_profile: the ``GOGA_PROFILE`` value, or ``None``.
        home_profiles: the decoded home bundle, or ``None``.

    Returns:
        The loaded workflow, or ``None`` when no workflow is in effect —
        neither channel set a name, and profile activation is then ignored
        entirely (nothing loads).

    Raises:
        ValueError: If the name resolves to a path escaping the workflows
            directory (``invalid workflow name``) or the workflow file is
            missing — an explicit selection is strict, never a silent miss;
            both errors name the workflow. Structural profile/render/parse
            failures of the loading chain propagate unchanged.
    """
    name = workflow_cli if workflow_cli else workflow_env

    if not name:
        return None

    workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
    workflow_path = workflows_root / f"{name}.yml"

    # Containment guard — an explicit build selection is strict (unlike the
    # pipeline silent miss): a name whose resolved path escapes the workflows
    # directory is refused, never a traversal into the wider filesystem.
    try:
        workflow_path.resolve().relative_to(workflows_root)
    except ValueError:
        raise ValueError(f"invalid workflow name: {name}") from None

    if not workflow_path.exists():
        raise ValueError(f"workflow {name} not found in {workflows_root}")

    return load_workflow(workflow_path, cli_profile, env_profile, home_profiles)
