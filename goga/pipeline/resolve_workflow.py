"""Resolve the optional workflow: ``no_workflow`` > explicit name > basename auto-match."""

from __future__ import annotations

import logging
from pathlib import Path

from .workflow import WorkflowDocument, parse_workflow

logger = logging.getLogger(__name__)


def resolve_workflow(
    pipeline_name: str,
    workflow_name: str | None,
    no_workflow: bool,
) -> WorkflowDocument | None:
    """Resolve an optional workflow: ``no_workflow`` > explicit name > basename auto-match.

    Args:
        pipeline_name: The pipeline name — used only for the basename fallback
            path.
        workflow_name: The explicit workflow name, or ``None``/``""`` for the
            basename fallback. Owned by the caller (parameters on both paths)
            — never read from the environment here.
        no_workflow: ``True`` disables the workflow entirely (wins over any
            name).

    Returns:
        The parsed :class:`WorkflowDocument` resolved from the project-only
        ``<cwd>/.goga/workflows/<name>.yml``, or ``None`` when workflow is
        disabled, the path escapes the workflows dir, or no file is found.

    Raises:
        WorkflowSyntaxError: On a structural defect in a resolved
            workflow-file, propagated unchanged from :func:`parse_workflow`.
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
    return parse_workflow(workflow_path)
