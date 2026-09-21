"""The fact vocabulary of the build domain run events — pure fact carriers.

Seven dataclasses shared by every context of the zone: ``WorkIdentity``
(the identity of the current work — the branch, with the topic slug and
year when the branch hosts a topic), ``BuildMoment`` (the uniform envelope
of every build context), ``AdditionalFacts`` (the delivered mirror of the
external-review block), ``StageFacts`` (the resolved facts of one stage
part of the run), ``RelocationOutcome`` (the outcome of the plan
relocation attempt), ``Violation`` (one collected veto of the gate walk),
and ``GateVerdict`` (the collected verdict of the gate walk — data only,
acting on it belongs to the operation).

Nothing is read or derived here — the constructing operation passes
resolved values with inheritance already applied. Env values never appear
anywhere: ``StageFacts.env`` carries names only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkIdentity:
    """The identity of the current work — the branch and its hosted topic.

    Args:
        branch: the current branch name as resolved by the operation
            (``"unknown"`` when resolution failed).
        slug: the normalized topic slug — present when the branch hosts a
            topic; ``None`` in the branch-only form.
        year: the resolved year as four digits — present when the branch
            hosts a topic; ``None`` in the branch-only form.
    """

    branch: str
    slug: str | None = None
    year: str | None = None


@dataclass(kw_only=True)
class BuildMoment:
    """The uniform envelope of every build context.

    Args:
        plan: the plan file path of the run.
        work: the current work identity.
        dry_run: ``True`` when the run rehearses the cycle without
            launching passes.
    """

    plan: str
    work: WorkIdentity
    dry_run: bool


@dataclass(kw_only=True)
class AdditionalFacts:
    """The delivered mirror of the external-review block.

    The documented facts of ``build.review.additional`` for tool authors.

    Args:
        agent: the external review agent name (after inheritance), or
            ``None`` when unset.
        patience: the external-review stop threshold — ``0`` means
            disabled; ``None`` when unset.
        max_iterations: the external review iteration cap — ``0`` means
            ralphex auto; ``None`` when unset.
    """

    agent: str | None
    patience: int | None
    max_iterations: int | None


@dataclass(kw_only=True)
class StageFacts:
    """The resolved facts of one stage part of the run.

    The delivered projection of the operation's resolved settings for that
    stage — the review-only members are ``None`` on the tasks part.

    Args:
        stage: the stage identity — exactly ``tasks`` or ``review``.
        agent: the executor agent name of the stage.
        env: the env presence of the stage layer as names — values never
            appear; an empty list means no env layer.
        max_iterations: the resolved iteration cap of the stage.
        session_timeout: the resolved session timeout of the stage.
        idle_timeout: the resolved idle timeout of the stage.
        wait: the resolved rate-limit wait of the stage.
        roles: the declared reviewer composition — review stage only;
            ``None`` on the tasks part.
        base_ref: the review diff base — review stage only; ``None`` on
            the tasks part.
        strategy: the resolved review strategy (full, medium, short) —
            review stage only; ``None`` on the tasks part.
        finalize: the full finalize prompt text when configured —
            ``None`` when unset or on the tasks part.
        additional: the external-review facts — review stage only;
            ``None`` on the tasks part.
    """

    stage: str
    agent: str | None
    env: list[str]
    max_iterations: int | None
    session_timeout: str | None
    idle_timeout: str | None
    wait: str | None
    roles: list[str] | None
    base_ref: str | None
    strategy: str | None
    finalize: str | None
    additional: AdditionalFacts | None


@dataclass(kw_only=True)
class RelocationOutcome:
    """The outcome of the plan relocation attempt.

    Args:
        moved: ``True`` when the plan was relocated into the completed
            directory.
        destination: the relocation destination when moved, ``None`` when
            not moved.
    """

    moved: bool
    destination: str | None


@dataclass(kw_only=True)
class Violation:
    """One collected veto of the gate walk.

    Args:
        tool: the tool identity assigned by the platform.
        hook: the hook name that vetoed or crashed.
        reason: the veto reason — a hook-authored message or the crash
            reason; never a raw traceback.
    """

    tool: str
    hook: str
    reason: str


@dataclass(kw_only=True)
class GateVerdict:
    """The collected verdict of the gate walk.

    Every veto of every subscribed tool, in enumeration order — the
    verdict is data only; acting on it (the merged error, the exit code)
    belongs to the operation.

    Args:
        violations: the collected violations; an empty list means
            approved.
    """

    violations: list[Violation]

    @property
    def approved(self) -> bool:
        """``True`` when no violation was collected — the run may proceed."""
        return not self.violations
