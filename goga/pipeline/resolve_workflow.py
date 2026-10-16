"""Resolve the optional workflow: ``no_workflow`` > explicit name > basename auto-match."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .workflow import LoadedWorkflow, load_workflow

logger = logging.getLogger(__name__)


def resolve_workflow(  # noqa: PLR0913, PLR0917 — the 6-parameter signature is the CODEMANIFEST contract
    pipeline_name: str,
    workflow_name: str | None,
    no_workflow: bool,
    cli_profile: str | None = None,
    env_profile: str | None = None,
    home_profiles: dict[str, dict[str, Any]] | None = None,
) -> LoadedWorkflow | None:
    """Resolve an optional workflow: ``no_workflow`` > explicit name > basename auto-match.

    Args:
        pipeline_name: The pipeline name — used only for the basename fallback
            path.
        workflow_name: The explicit workflow name, or ``None``/``""`` for the
            basename fallback. Owned by the caller (parameters on both paths)
            — never read from the environment here.
        no_workflow: ``True`` disables the workflow entirely (wins over any
            name).
        cli_profile: The CLI activation channel value (the ``--profile``
            flag), or ``None`` — forwarded into the loading chain.
        env_profile: The environment activation channel value (the
            ``GOGA_PROFILE`` engine variable), or ``None`` — forwarded into
            the loading chain.
        home_profiles: The decoded home bundle, or ``None`` (treated as
            empty) — forwarded into the loading chain.

    Returns:
        The loaded :class:`~goga.pipeline.workflow.LoadedWorkflow` — the
        parsed document of the rendered text plus the active profile —
        resolved from the project-only ``<cwd>/.goga/workflows/<name>.yml``,
        or ``None`` when workflow is disabled, the path escapes the workflows
        dir, or no file is found.

    Raises:
        WorkflowSyntaxError: On a structural defect in a resolved
            workflow-file, propagated unchanged from the loading chain's
            ``parse_workflow``.
        ValueError: When the activation resolves a missing or malformed
            profile, or the rendering fails — propagated unchanged from the
            loading chain.
    """
    if no_workflow:
        logger.debug("workflow disabled", extra={"pipeline": pipeline_name})
        return None

    workflows_root = (Path.cwd() / ".goga" / "workflows").resolve()
    wf_name = workflow_name if workflow_name not in (None, "") else pipeline_name
    workflow_path = workflows_root / f"{wf_name}.yml"

    # Containment guard — workflow paths are project-only by design (CODEMANIFEST
    # step 6b). A name carrying a ``..`` segment or an absolute prefix that
    # escapes the workflows dir is a silent miss, never a traversal into the
    # wider filesystem (the name may originate from a less-trusted source than
    # the host CLI).
    try:
        workflow_path.resolve().relative_to(workflows_root)
    except ValueError:
        logger.debug("workflow path escapes the workflows dir", extra={"workflow": wf_name})
        return None

    if not workflow_path.exists():
        logger.debug("workflow file missing (silent miss)", extra={"workflow": workflow_path.name})
        return None

    logger.debug("workflow file resolved", extra={"workflow": workflow_path.name})

    return load_workflow(workflow_path, cli_profile, env_profile, home_profiles)
