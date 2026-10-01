"""The run-event contexts of the build domain — read-only fact bundles.

Five dataclasses carrying the facts a hook observes at the build
checkpoints: ``BuildValidation`` (the gate's per-tool view — the same
read-only facts plus the veto buffer of that one tool), ``BuildStarted``
(the resolved facts the gate saw, immediately before the first pass
launch), ``PassStarted`` / ``PassCompleted`` (the facts of a pass at its
start and completion moments — completion is a fact, not a success
claim), and ``BuildCompleted`` (the outcome facts of the started run).

Read-only facts of the observed moment — a hook observes and cannot
alter. The single write channel is :meth:`BuildValidation.veto`, and it
buffers into the tool's private buffer alone: the call changes nothing
until the gate walk collects it, and the delivery proxy closes every
context against attribute writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import BuildMoment, RelocationOutcome, StageFacts


@dataclass(kw_only=True)
class BuildValidation:
    """The gate's delivered view of one tool — the facts plus the veto buffer.

    The read-only facts of the run about to start, delivered to every
    validation hook of one tool, plus the veto buffer belonging to that
    tool alone.

    Args:
        moment: the uniform envelope of the run.
        tasks: the resolved facts of the tasks stage.
        review: the resolved facts of the review stage — always present,
            including a skipped review; the facts describe the resolved
            settings, not the execution.
        skip: the resolved review skip state of the run.
    """

    moment: BuildMoment
    tasks: StageFacts
    review: StageFacts
    skip: bool

    _veto: str | None = field(init=False, default=None, repr=False)

    def veto(self, reason: str) -> None:
        """Buffer this tool's veto of the run.

        The replacement is whole — a later call replaces the earlier
        reason. The view records no hook identity: the walk attributes
        the veto to a hook by observing the buffer change around each
        call. The call changes nothing until the walk collects it — it
        does not cancel, redirect, or defer the operation; a veto stops
        the run through the collected verdict only.

        Args:
            reason: the human-readable violation reason — an empty or
                whitespace-only reason is stored as given, and the
                merged error renders it verbatim.
        """
        self._veto = reason


@dataclass(kw_only=True)
class BuildStarted:
    """The read-only context of the start notification.

    The same resolved facts the gate saw, delivered immediately before
    the first pass launch — a hook observes and cannot alter.

    Args:
        moment: the uniform envelope of the run.
        tasks: the resolved facts of the tasks stage.
        review: the resolved facts of the review stage.
        skip: the resolved review skip state of the run.
    """

    moment: BuildMoment
    tasks: StageFacts
    review: StageFacts
    skip: bool


@dataclass(kw_only=True)
class PassStarted:
    """The read-only context of the pass-start notification.

    The facts of the pass about to launch — a hook observes and cannot
    alter.

    Args:
        moment: the uniform envelope of the run.
        facts: the stage facts of the pass about to launch.
    """

    moment: BuildMoment
    facts: StageFacts


@dataclass(kw_only=True)
class PassCompleted:
    """The read-only context of the pass-completion notification.

    The facts of the finished pass plus its actual exit code —
    completion is a fact, not a success claim.

    Args:
        moment: the uniform envelope of the run.
        facts: the stage facts of the finished pass.
        exit_code: the actual exit code of the pass — zero, non-zero,
            or a spawn-failure code.
    """

    moment: BuildMoment
    facts: StageFacts
    exit_code: int


@dataclass(kw_only=True)
class BuildCompleted:
    """The read-only context of the completion notification.

    The outcome facts of the started run at the completion moment — the
    artifact to history-status integration builds from these facts
    alone.

    Args:
        moment: the uniform envelope of the run.
        exit_code: the final exit code of the run — the last executed
            pass's code.
        stages: the executed stage sequence in execution order — a
            skipped review is absent.
        relocation: the outcome of the plan relocation attempt.
        statuses: the work's current history statuses at the completion
            moment, recomputed after the relocation attempt; an empty
            list in the branch-only form.
    """

    moment: BuildMoment
    exit_code: int
    stages: list[str]
    relocation: RelocationOutcome
    statuses: list[str]
