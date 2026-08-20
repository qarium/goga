"""The ``resolve_workflow`` routine — the single point of optional-workflow resolution.

Both workflow-aware consumers meet here: the run path
(:func:`~goga.pipeline.run_pipeline.run_pipeline`, whose decision arrives from
the container environment) and the info-card path
(:func:`~goga.pipeline.describe_pipeline.describe_pipeline`, whose decision
arrives from CLI flags). The rule set is parameterized so the same code answers
"which workflow applies?" for both — the structural guarantee that what the
card shows is what the run executes.

The rule set (in precedence order):

    ``no_workflow is True``          → ``None`` (disabled wins)
    ``workflow_name`` not None/``""``→ that file
    otherwise                         → basename auto-match (pipeline name)
    containment escape                → ``None`` (silent miss)
    missing file                      → ``None`` (silent miss)
    malformed file                    → ``WorkflowSyntaxError`` propagates

This module never reads environment variables — the owners of the flags
(``run_pipeline`` reads env; ``describe_pipeline`` reads CLI) decide them and
pass the decision in.
"""

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
    """Resolve an optional workflow per the shared workflow rule set.

    Precedence: ``no_workflow`` (disabled wins) > ``workflow_name`` (explicit
    name; an empty string counts as no name — the basename auto-match still
    applies) > basename fallback (the same name as the pipeline). The
    workflow-file path is project-only and CWD-based — ``Path.cwd() / ".goga"
    / "workflows" / "<name>.yml"`` — NOT derived from ``project_dir.parent``:
    ``project_dir`` is ``/workspace/.goga/pipelines``, so ``project_dir.parent``
    is ``/workspace/.goga`` and a parent-based composition would produce a
    double ``.goga`` segment. ``Path.cwd()`` is ``/workspace`` in-container,
    i.e. the project root. The host-side launcher performs explicit
    ``--workflow`` existence validation before launch; inside the container a
    missing file is a defensive silent miss, not an error.

    A structurally malformed workflow-file surfaces its
    :class:`~goga.pipeline.workflow.WorkflowSyntaxError` from
    :func:`parse_workflow` unchanged.

    Args:
        pipeline_name: The pipeline name — used only for the basename fallback
            path.
        workflow_name: The explicit workflow name, or ``None``/``""`` for the
            basename fallback. Owned by the caller (env on the run path, CLI
            flags on the card path) — never read from the environment here.
        no_workflow: ``True`` disables the workflow entirely (wins over any
            name).

    Returns:
        The parsed :class:`WorkflowDocument` when a workflow-file resolves and
        exists, or ``None`` when workflow is disabled or no file is found.
    """
    if no_workflow:
        logger.debug("workflow disabled for pipeline %s", pipeline_name)
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
        logger.debug("workflow path escapes the workflows dir: %s", wf_name)
        return None

    if not workflow_path.exists():
        logger.debug("workflow file missing (silent miss): %s", workflow_path.name)
        return None

    logger.debug("workflow file resolved: %s", workflow_path.name)
    return parse_workflow(workflow_path)
