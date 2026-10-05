"""Config-driven status check of synchronized cell-level usages against the remote."""

import logging
from pathlib import Path

import click

from ...config import DepConfig, ProjectConfig, load_project_config
from ...config.hooks import ConfigHooks
from ..hooks import (
    ChangeVerdict,
    Completion,
    DepDrift,
    DriftVerdict,
    FileChange,
    UsagesHooks,
    UsagesMoment,
)
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

_FILE_CHANGE = {
    EntryChange.added: ChangeVerdict.added,
    EntryChange.modified: ChangeVerdict.modified,
    EntryChange.removed: ChangeVerdict.removed,
}
"""The entry-diff to change-verdict mapping of the drift projection.

``unchanged`` is deliberately absent: an unchanged file is no change, so the
``in _FILE_CHANGE`` filter of ``_derive_drift`` drops it together with the
directory nodes."""


def _effective_config() -> ProjectConfig:
    """Load the authored config and deliver the config-amendment checkpoint.

    Returns:
        The effective configuration of the run, after the amendment summary lines print to stderr.

    Raises:
        FileNotFoundError, KeyError, ValueError, ImportError, yaml.YAMLError:
            propagated fail-loud from ``load_project_config``;
            ``ValueError`` also covers a hard checkpoint failure and
            ``ImportError`` a broken tool package.
    """
    config = load_project_config()
    overlay = ConfigHooks().amend_config(config=config)
    for line in overlay.summary_lines:
        click.echo(line, err=True)
    return overlay.config


def status(group: str | None = None, dep: str | None = None) -> UsageStatusReport:
    """Check every declared dep's synced usages against the current remote state — read-only over ``.goga/usages/``.

    Args:
        group: When set, only check deps under this group.
        dep: When set, only check deps with this name (within any matched group).

    Returns:
        A :class:`UsageStatusReport` over the matched deps; ``deps`` is empty and
        ``exit_code`` is ``0`` when the ``usages`` section is absent/empty or no dep
        matches the filters.

    Raises:
        FileNotFoundError, KeyError, ValueError, ImportError, yaml.YAMLError:
            propagated fail-loud from ``load_project_config`` at the config
            boundary; ``ValueError`` also covers a hard checkpoint failure and
            ``ImportError`` a broken tool package (the ``goga usages`` wrapper
            converts both to a clean error).
    """
    config = _effective_config()

    moment = UsagesMoment(operation="status", group=group, dep=dep)
    hooks = UsagesHooks()
    hooks.emit_status_started(moment)

    changed: list[DepDrift] = []

    try:
        report = _status_work(config, group, dep, changed)
    except Exception as reason:
        # The moment never masks the operation's own failure: the crashed
        # completion carries the partial drift recorded so far and the
        # credential-free reason, then the original exception propagates
        # unchanged. ``Exception`` only — a ``BaseException`` such as
        # ``KeyboardInterrupt`` completes nothing, matching the platform's
        # own catch policy.
        hooks.emit_status_completed(moment, changed, False, Completion.crashed, reason=str(reason))
        raise

    hooks.emit_status_completed(moment, changed, not changed, Completion.finished)

    return report


def _status_work(
    config: ProjectConfig,
    group: str | None,
    dep: str | None,
    changed: list[DepDrift],
) -> UsageStatusReport:
    """Run the per-dep work of a started status check, recording the changed set.

    Args:
        config: The effective configuration of the run.
        group: The applied group filter; None checks all groups.
        dep: The applied dep filter; None checks all deps.
        changed: The caller-owned accumulator of ``DepDrift`` records, mutated as the loop
            progresses so the partial drift survives a crash.

    Returns:
        A :class:`UsageStatusReport` over the matched deps; ``deps`` is empty
        when the ``usages`` section is absent/empty or no dep matches the
        filters.
    """
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
            dep_status = _check_dep(group_name, dep_name, depcfg)
            collected.append(dep_status)
            drift = _derive_drift(dep_status)
            if drift is not None:
                changed.append(drift)

    logger.info(
        "usages status completed",
        extra={"deps": len(collected)},
    )

    return UsageStatusReport(deps=collected)


def _derive_drift(dep_status: DepStatus) -> DepDrift | None:
    """Project one checked dep onto its changed-set record.

    Args:
        dep_status: The checked dep's status record.

    Returns:
        The :class:`DepDrift` record for a non-up-to-date dep; ``None`` for an up-to-date dep. The
        out-of-date change list carries changed files only, in the diff's path-sorted order; the
        ``new`` and ``error`` verdicts carry an empty list.
    """
    if dep_status.state is UsageState.up_to_date:
        return None

    if dep_status.state is UsageState.new:
        return DepDrift(group=dep_status.group, dep=dep_status.dep, verdict=DriftVerdict.new, changes=[])

    if dep_status.state is UsageState.error:
        return DepDrift(
            group=dep_status.group,
            dep=dep_status.dep,
            verdict=DriftVerdict.error,
            changes=[],
            message=dep_status.error,
        )

    return DepDrift(
        group=dep_status.group,
        dep=dep_status.dep,
        verdict=DriftVerdict.out_of_date,
        changes=[
            FileChange(path=entry.path, change=_FILE_CHANGE[entry.change])
            for entry in dep_status.entries
            if entry.kind is EntryKind.file and entry.change in _FILE_CHANGE
        ],
    )


def _check_dep(group_name: str, dep_name: str, depcfg: DepConfig) -> DepStatus:
    """Compute the status of one declared dep, isolating its failure mode.

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
