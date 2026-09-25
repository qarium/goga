"""The checkpoint surface of the build domain — the events cell of the zone.

The entity declared in the cell CODEMANIFEST with ``location: events.py``:
``BuildHooks`` — the verdict-collecting gate delivery and the four
notification emissions of the build cycle over the platform facade.
Construction is cheap and every context is built from the values the
caller passes; one lazily-built run registry carries every checkpoint of
a run, so the package enumeration happens once whatever the number of
checkpoints. The gate is the domain's hard action with one domain-local
deviation: the staged per-tool walk never stops early — every subscribed
tool's validation hooks run to completion and the vetoes are collected
into one verdict — while the four notifications are soft
fire-and-forget emissions: a failing hook warns inside the platform and
never affects the run.
"""

from __future__ import annotations

from ...hooks import (
    HookRegistry,
    build_hook_arguments,
    declared_actions,
    emit_hook_event,
    wrap_context,
)
from .contexts import BuildCompleted, BuildStarted, BuildValidation, PassCompleted, PassStarted
from .facts import BuildMoment, GateVerdict, RelocationOutcome, StageFacts, Violation


class BuildHooks:
    """The checkpoint surface of the build domain.

    Owns the single run registry shared by the validation gate and the
    four notifications, and drives the gate's staged walk over the public
    primitives of the hooks platform. Tools are mutually blind — every
    tool's validation view is a fresh read-only bundle over the same
    delivered facts with a veto buffer of that tool alone — and the walk
    collects the vetoes instead of stopping at the first failure.

    Requirements:
        - Cheap construction — no enumeration and no imports happen at
          construction
        - One ``HookRegistry`` per run carries every checkpoint of a
          command — the assembly runs once per run whatever the number of
          checkpoints
        - Every context is built from the values the caller passes — no
          repository reads happen at a checkpoint
    """

    def __init__(self) -> None:
        """Create the checkpoint surface of one build run.

        Nothing is enumerated and nothing is imported: the run registry
        builds lazily on the first checkpoint that needs it.
        """
        self._registry: HookRegistry | None = None

    def _ensure_registry(self) -> HookRegistry:
        """Build the run registry once — the shared state of every checkpoint.

        Returns:
            The assembled registry of the run — built on the first call and
            reused by every checkpoint; never rebuilt on the same surface.

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

    def validate_build(
        self,
        moment: BuildMoment,
        tasks: StageFacts,
        review: StageFacts,
        skip: bool,
    ) -> GateVerdict:
        """Deliver the validation gate and return the collected verdict.

        Algorithm:
            1. Resolve the address ``build.validate_build`` against
               ``declared_actions`` — an unknown address is a clean error
               of the emitting side
            2. Walk the subscriptions of the address per tool in
               enumeration order: build the tool's ``BuildValidation``
               view over the delivered facts — every tool reads the same
               facts through a fresh view — wrap it via ``wrap_context``,
               project the call arguments via ``build_hook_arguments``
               with the tool's own context, and call each hook of the
               tool; the veto buffer is snapshotted before each call — a
               buffer change during a call attributes the veto to that
               hook's subscription name (a later veto replaces the
               earlier attribution whole, mirroring the buffer rule)
            3. A raising hook is the tool's single crash violation — the
               crash reason, never a raw traceback — and stops that
               tool's remaining hooks; the crash overrides the tool's
               buffered veto; the walk continues with the next tool and
               never stops between tools whatever a tool returned or
               raised
            4. A tool whose every hook returned and whose buffer carries
               a veto contributes exactly one ``Violation`` with the
               attributed hook; a tool whose buffer stayed empty approves
               silently — no record
            5. Return the ``GateVerdict`` with the violations in
               enumeration order — an address without subscriptions
               returns the empty, approved verdict

        Args:
            moment: The uniform envelope of the run.
            tasks: The resolved facts of the tasks stage.
            review: The resolved facts of the review stage — always
                present, including a skipped review.
            skip: The resolved review skip state of the run.

        Returns:
            The :class:`~goga.build.hooks.GateVerdict` — approved when no
            tool vetoed or crashed.

        Raises:
            ValueError: The address is not declared.
        """
        registry = self._ensure_registry()

        record = next(
            (entry for entry in declared_actions() if entry.domain == "build" and entry.name == "validate_build"),
            None,
        )
        if record is None:
            raise ValueError("unknown hook action: build.validate_build")

        groups: dict[str, list] = {}
        for subscription in registry.subscriptions_for("build", "validate_build"):
            groups.setdefault(subscription.tool, []).append(subscription)

        violations: list[Violation] = []

        for tool, subscriptions in groups.items():
            # A fresh view per tool — the same delivered facts, a veto
            # buffer belonging to this tool alone.
            view = BuildValidation(moment=moment, tasks=tasks, review=review, skip=skip)
            proxy = wrap_context(view)

            attributed_hook = ""
            crash: tuple[str, str] | None = None

            for subscription in subscriptions:
                before = view._veto
                try:
                    subscription.hook(
                        **build_hook_arguments(subscription.hook, proxy, registry.self_context(tool))
                    )
                except Exception as reason:
                    # One crash violation for the tool — the crash reason
                    # overrides any buffered veto; the tool's remaining
                    # hooks stop, the walk does not.
                    crash = (subscription.name, str(reason))
                    break

                if view._veto != before:
                    attributed_hook = subscription.name

            if crash is not None:
                violations.append(Violation(tool=tool, hook=crash[0], reason=crash[1]))
            elif view._veto is not None:
                # The buffer only changes through veto(), so a non-empty
                # buffer always carries an observed attribution.
                violations.append(Violation(tool=tool, hook=attributed_hook, reason=view._veto))

        return GateVerdict(violations=violations)

    def emit_build_started(
        self,
        moment: BuildMoment,
        tasks: StageFacts,
        review: StageFacts,
        skip: bool,
    ) -> None:
        """Emit the start notification — the resolved facts the gate saw.

        Fire-and-forget: nothing is collected and no value returns. The
        same context instance is delivered to every subscribed tool — the
        notification contexts carry no buffer — and a failing hook is
        skipped with a warning under the soft error class of the action:
        the run proceeds.

        Args:
            moment: The uniform envelope of the run.
            tasks: The resolved facts of the tasks stage.
            review: The resolved facts of the review stage.
            skip: The resolved review skip state of the run.
        """
        context = BuildStarted(moment=moment, tasks=tasks, review=review, skip=skip)

        emit_hook_event(
            self._ensure_registry(),
            "build",
            "build_started",
            context_for=lambda _tool: context,
        )

    def emit_pass_started(self, moment: BuildMoment, facts: StageFacts) -> None:
        """Emit the pass-start notification — the facts of the launching pass.

        Fire-and-forget: nothing is collected and no value returns. A
        failing hook is skipped with a warning under the soft error class
        of the action — the pass launches.

        Args:
            moment: The uniform envelope of the run.
            facts: The stage facts of the pass about to launch.
        """
        context = PassStarted(moment=moment, facts=facts)

        emit_hook_event(
            self._ensure_registry(),
            "build",
            "pass_started",
            context_for=lambda _tool: context,
        )

    def emit_pass_completed(self, moment: BuildMoment, facts: StageFacts, exit_code: int) -> None:
        """Emit the pass-completion notification — the finished pass's facts.

        Fire-and-forget: nothing is collected and no value returns. The
        emission happens on every pass return path — zero, non-zero, and
        spawn failures alike; completion is a fact, not a success claim —
        and a failing hook warns under the soft error class: the exit code
        of the pass is never affected.

        Args:
            moment: The uniform envelope of the run.
            facts: The stage facts of the finished pass.
            exit_code: The actual exit code of the pass return.
        """
        context = PassCompleted(moment=moment, facts=facts, exit_code=exit_code)

        emit_hook_event(
            self._ensure_registry(),
            "build",
            "pass_completed",
            context_for=lambda _tool: context,
        )

    # The parameter list is fixed by the cell contract — the CODEMANIFEST
    # declares every fact the context carries.
    def emit_build_completed(
        self,
        moment: BuildMoment,
        exit_code: int,
        stages: list[str],
        relocation: RelocationOutcome,
        statuses: list[str],
    ) -> None:
        """Emit the completion notification — the outcome of the started run.

        Fire-and-forget: nothing is collected and no value returns. The
        emission happens on every return path of a started run — zero,
        non-zero, and spawn failures alike — and a failing hook warns
        under the soft error class: the exit code of the run is never
        affected.

        Args:
            moment: The uniform envelope of the run.
            exit_code: The final exit code of the run — the last executed
                pass's code.
            stages: The executed stage sequence in execution order.
            relocation: The outcome of the plan relocation attempt.
            statuses: The work's history statuses recomputed at the
                completion moment.
        """
        context = BuildCompleted(
            moment=moment,
            exit_code=exit_code,
            stages=stages,
            relocation=relocation,
            statuses=statuses,
        )

        emit_hook_event(
            self._ensure_registry(),
            "build",
            "build_completed",
            context_for=lambda _tool: context,
        )
