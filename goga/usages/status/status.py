"""Config-driven status check of synchronized cell-level usages against the remote.

For every declared ``<group>/<dep>`` git dependency, compares the on-disk synced
tree under ``.goga/usages/<group>/<dep>/`` against the current remote state and
reports one of ``new`` / ``up to date`` / ``out of date`` / ``error`` per dep.
After the load the config-amendment checkpoint delivers the effective
configuration (its summary lines print to stderr; the report rendering stays
with the command). Config-load errors and checkpoint failures propagate
fail-loud at the boundary; per-dep clone/checkout/deploy failures are
best-effort (logged credential-free and recorded as an ``error`` dep) so one
failing dep never aborts the rest. The check is read-only: it never writes to
``.goga/usages/``.

The run owns its two moments, notification-only, delivered over the usages
hooks zone: the status-start moment fires once the effective configuration
is resolved and the status-completion moment on every return path after the
start, carrying the changed set — one drift record per matched dep that is
not up to date.

The data-model contract entities are re-exported here so they stay importable
from their contract location ``status.py`` (they are defined in the internal
:mod:`goga.usages.status.models` to break the ``status.py`` <-> ``compare.py``
import cycle — see that module's docstring).
"""

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

    Returns the effective configuration of the run after printing the
    amendment summary lines to stderr — the exact body ``sync.py`` already
    carries, extracted verbatim so both operations share one delivery shape.
    Kept beside ``status`` so the orchestrator stays within the lint
    complexity budget — the delivery is the first statement of the run,
    before any usages moment fires.

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
    """Check every declared dep's synced usages against the current remote state.

    Loads project config, delivers the config-amendment checkpoint (the check
    iterates the effective ``usages`` deps; the summary lines print to stderr),
    and checks each declared dep. The optional ``group``/``dep`` filters narrow
    the check (non-matching deps are skipped, NOT errors). A dep whose target
    directory does not exist is ``new``; otherwise its expected tree is rebuilt
    from the remote (via :func:`compute_dep_status`) and compared to the synced
    target. A per-dep clone/checkout/deploy failure is caught, logged
    credential-free, and recorded as an ``error`` dep, then iteration continues.
    The whole check is read-only with respect to ``.goga/usages/``.

    The run owns its two moments, notification-only: the status-start moment
    fires once the effective configuration is resolved — an abort at the
    configuration boundary fires no moment — and the status-completion
    moment fires on every return path after the start (the no-op return,
    the finished return, and an unexpected break-off alike), carrying one
    ``DepDrift`` per matched dep that is not up to date.

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

    Mutates the caller-owned ``changed`` accumulator as the loop progresses,
    so the partial drift survives a crash of this helper — the crashed
    completion in ``status`` reads whatever was recorded before the
    break-off. A dep filtered out by the filters is silently absent from
    the records.

    Args:
        config: The effective configuration of the run.
        group: The applied group filter; None checks all groups.
        dep: The applied dep filter; None checks all deps.
        changed: The caller-owned accumulator of ``DepDrift`` records.

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

    An up-to-date dep projects to ``None`` — absent from the changed set, so
    an empty changed set reads as no drift among the matched deps. The
    ``new`` and ``error`` verdicts carry the empty change list (only the
    error carries its credential-free message); the out-of-date verdict
    populates it from the entry diff: files only (directory nodes dropped),
    changed files only (``unchanged`` is not a key of ``_FILE_CHANGE``), in
    the path-sorted order the diff already carries — filtering a sorted
    list keeps it sorted.

    Args:
        dep_status: The checked dep's status record.

    Returns:
        The :class:`DepDrift` record for a non-up-to-date dep; ``None`` for
        an up-to-date dep.
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
