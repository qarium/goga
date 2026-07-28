"""Config-driven status check of synchronized cell-level usages against the remote.

For every declared ``<group>/<dep>`` git dependency, compares the on-disk synced
tree under ``.goga/usages/<group>/<dep>/`` against the current remote state and
reports one of ``new`` / ``up to date`` / ``out of date`` / ``error`` per dep.
Config-load errors propagate fail-loud at the boundary; per-dep clone/checkout/
deploy failures are best-effort (logged credential-free and recorded as an
``error`` dep) so one failing dep never aborts the rest. The check is read-only:
it never writes to ``.goga/usages/``.

The data-model contract entities are re-exported here so they stay importable
from their contract location ``status.py`` (they are defined in the internal
:mod:`goga.usages.status.models` to break the ``status.py`` <-> ``compare.py``
import cycle — see that module's docstring).
"""

import logging
from pathlib import Path

from ...config import DepConfig, load_project_config
from .compare import compute_dep_status
from .models import DepStatus, EntryChange, EntryKind, EntryStatus, UsageState, UsageStatusReport

__all__ = [
    "DepStatus",
    "EntryChange",
    "EntryKind",
    "EntryStatus",
    "UsageState",
    "UsageStatusReport",
    "status",
]

logger = logging.getLogger(__name__)


def status(group: str | None = None, dep: str | None = None) -> UsageStatusReport:
    """Check every declared dep's synced usages against the current remote state.

    Loads project config and iterates the declared ``usages`` deps. The optional
    ``group``/``dep`` filters narrow the check (non-matching deps are skipped, NOT
    errors). A dep whose target directory does not exist is ``new``; otherwise its
    expected tree is rebuilt from the remote (via :func:`compute_dep_status`) and
    compared to the synced target. A per-dep clone/checkout/deploy failure is
    caught, logged credential-free, and recorded as an ``error`` dep, then
    iteration continues. The whole check is read-only with respect to
    ``.goga/usages/``.

    Args:
        group: When set, only check deps under this group.
        dep: When set, only check deps with this name (within any matched group).

    Returns:
        A :class:`UsageStatusReport` over the matched deps; ``deps`` is empty and
        ``exit_code`` is ``0`` when the ``usages`` section is absent/empty or no dep
        matches the filters.

    Raises:
        FileNotFoundError, KeyError, ValueError, yaml.YAMLError: propagated
            fail-loud from ``load_project_config`` at the config boundary.
    """
    config = load_project_config()

    if not config.usages:
        return UsageStatusReport(deps=[])

    logger.info(
        "usages status started",
        extra={"group": group, "dep": dep},
    )

    collected: list[DepStatus] = []
    for group_name, deps in config.usages.items():
        if group is not None and group_name != group:
            continue
        for dep_name, depcfg in deps.items():
            if dep is not None and dep_name != dep:
                continue
            collected.append(_check_dep(group_name, dep_name, depcfg))

    logger.info(
        "usages status completed",
        extra={"deps": len(collected)},
    )

    return UsageStatusReport(deps=collected)


def _check_dep(group_name: str, dep_name: str, depcfg: DepConfig) -> DepStatus:
    """Compute the status of one declared dep, isolating its failure mode.

    A missing on-disk target is ``new`` (the dep has never been synced). An existing
    target is compared to a fresh rebuild of the remote via
    :func:`compute_dep_status`. Any clone/checkout/deploy failure is caught and
    turned into an ``error`` :class:`DepStatus` with a credential-free message,
    while the exception is logged without its text/traceback (a clone failure's
    ``subprocess.CalledProcessError`` embeds the full git URL, which may carry
    embedded credentials — the same discipline ``sync.py`` follows).

    Args:
        group_name: Group name of the dep.
        dep_name: Dep name.
        depcfg: Declared git dependency (URL/ref/root) for the dep.

    Returns:
        A :class:`DepStatus`: ``new`` when the target is absent, otherwise the
        result of :func:`compute_dep_status`, or ``error`` on a caught failure.
    """
    target = Path(".goga/usages") / group_name / dep_name
    try:
        if not target.exists():
            return DepStatus(
                group=group_name,
                dep=dep_name,
                state=UsageState.new,
                entries=[],
            )
        return compute_dep_status(group_name, dep_name, depcfg, target)
    except Exception:
        logger.error(
            "usages status dep failed",
            extra={"group": group_name, "dep": dep_name},
        )
        return DepStatus(
            group=group_name,
            dep=dep_name,
            state=UsageState.error,
            error=f"failed to check usages status for {group_name}/{dep_name}",
            entries=[],
        )
