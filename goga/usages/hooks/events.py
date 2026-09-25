"""The checkpoint surface of the usages domain — the events cell of the zone.

The entity declared in the cell CODEMANIFEST with ``location: events.py``:
``UsagesHooks`` — the four moment emissions of the sync and status
operations over the platform facade. Construction is cheap and every
context is built from the values the caller passes; one lazily-built run
registry carries every moment of a command, so the package enumeration
happens once per run whatever the number of moments. All four actions are
soft fire-and-forget notifications: a failing hook is skipped with a
warning inside the platform and never affects the operation, and no
moment reads a configuration, a repository, or a file — the zone is
notification-only.
"""

from __future__ import annotations

from ...hooks import HookRegistry, emit_hook_event
from .contexts import StatusCompleted, StatusStarted, SyncCompleted, SyncStarted
from .facts import Completion, DepDrift, SyncDepOutcome, UsagesMoment


class UsagesHooks:
    """The checkpoint surface of the usages domain.

    Emits the four run-level moments of the sync and status operations
    over the hooks platform — every method resolves its address against
    ``declared_actions`` inside ``emit_hook_event``, builds the read-only
    context from the caller's values, and delivers it to the subscribed
    hooks under the soft error class of the action.

    Requirements:
        - Cheap construction — no enumeration and no imports happen at
          construction
        - One ``HookRegistry`` per run carries every moment of a command —
          the assembly runs once per run whatever the number of moments
        - Every context is built from the values the caller passes — no
          configuration reads, no git access, and no file reads happen at
          a moment
    """

    def __init__(self) -> None:
        """Create the checkpoint surface of one run.

        Nothing is enumerated and nothing is imported: the run registry
        builds lazily on the first moment that needs it.
        """
        self._registry: HookRegistry | None = None

    def _ensure_registry(self) -> HookRegistry:
        """Build the run registry once — the shared state of every moment.

        Returns:
            The assembled registry of the run — built on the first call and
            reused by every moment; never rebuilt on the same surface.

        Raises:
            ImportError: A tool package exists but its facade fails to
                import — the single fatal case; the message names the
                package.
        """
        if self._registry is None:
            registry = HookRegistry()
            registry.build_once()
            self._registry = registry

        return self._registry

    def emit_sync_started(self, moment: UsagesMoment, force: bool) -> None:
        """Emit the sync-start moment — what the sync run was asked to do.

        Algorithm:
            1. Resolve the address ``usages.sync_started`` against
               ``declared_actions`` — inside ``emit_hook_event``
            2. Build the ``SyncStarted`` context from ``moment`` and
               ``force``
            3. Emit the resolved address — the same context instance is
               shared by every receiving tool: the facts are frozen and the
               delivery proxy closes writes

        Args:
            moment: The identity envelope of the run.
            force: The force flag as applied by the run.
        """
        context = SyncStarted(moment=moment, force=force)

        emit_hook_event(
            self._ensure_registry(),
            "usages",
            "sync_started",
            context_for=lambda _tool: context,
        )

    # The parameter list is fixed by the cell contract — the CODEMANIFEST
    # declares every fact the context carries.
    def emit_sync_completed(
        self,
        moment: UsagesMoment,
        deps: list[SyncDepOutcome],
        success: bool,
        completion: Completion,
        reason: str | None = None,
    ) -> None:
        """Emit the sync-completion moment — the outcomes of a started sync run.

        Fire-and-forget: nothing is collected and no value returns. The
        emission happens on every return path of a started run — finished
        and crashed alike; completion is a fact, not a success claim. A
        failing hook is skipped with a warning under the soft error class
        of the action — the operation is unaffected.

        Algorithm:
            1. Resolve the address ``usages.sync_completed`` against
               ``declared_actions`` — inside ``emit_hook_event``
            2. Build the ``SyncCompleted`` context from the values
            3. Emit the resolved address — the same context instance is
               shared by every receiving tool

        Args:
            moment: The identity envelope of the run.
            deps: One ``SyncDepOutcome`` per matched dep, in iteration order.
            success: The run's overall success.
            completion: The terminal marker — finished or crashed.
            reason: The credential-free crash reason; None unless crashed.
        """
        context = SyncCompleted(
            moment=moment,
            deps=deps,
            success=success,
            completion=completion,
            reason=reason,
        )

        emit_hook_event(
            self._ensure_registry(),
            "usages",
            "sync_completed",
            context_for=lambda _tool: context,
        )

    def emit_status_started(self, moment: UsagesMoment) -> None:
        """Emit the status-start moment — what the status run was asked to do.

        Algorithm:
            1. Resolve the address ``usages.status_started`` against
               ``declared_actions`` — inside ``emit_hook_event``
            2. Build the ``StatusStarted`` context from ``moment``
            3. Emit the resolved address — the same context instance is
               shared by every receiving tool

        Args:
            moment: The identity envelope of the run.
        """
        context = StatusStarted(moment=moment)

        emit_hook_event(
            self._ensure_registry(),
            "usages",
            "status_started",
            context_for=lambda _tool: context,
        )

    # The parameter list is fixed by the cell contract — the CODEMANIFEST
    # declares every fact the context carries.
    def emit_status_completed(
        self,
        moment: UsagesMoment,
        changed: list[DepDrift],
        success: bool,
        completion: Completion,
        reason: str | None = None,
    ) -> None:
        """Emit the status-completion moment — the changed-set records of a started check.

        Fire-and-forget: nothing is collected and no value returns. The
        emission happens on every return path of a started run — finished
        and crashed alike; completion is a fact, not a success claim. A
        failing hook is skipped with a warning under the soft error class
        of the action — the check is unaffected.

        Algorithm:
            1. Resolve the address ``usages.status_completed`` against
               ``declared_actions`` — inside ``emit_hook_event``
            2. Build the ``StatusCompleted`` context from the values
            3. Emit the resolved address — the same context instance is
               shared by every receiving tool

        Args:
            moment: The identity envelope of the run.
            changed: One ``DepDrift`` per changed matched dep.
            success: The check's overall outcome.
            completion: The terminal marker — finished or crashed.
            reason: The credential-free crash reason; None unless crashed.
        """
        context = StatusCompleted(
            moment=moment,
            changed=changed,
            success=success,
            completion=completion,
            reason=reason,
        )

        emit_hook_event(
            self._ensure_registry(),
            "usages",
            "status_completed",
            context_for=lambda _tool: context,
        )
