"""The propagation operation of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: propagating.py``: ``PropagationPlan`` — the self-contained
plan the caller confirms —, ``resolve_propagation`` — the fully
read-only resolution of that plan, every decision before the
confirmation and before any mutation, the network included —, and
``execute_propagation`` — the checkout-free delivery: the delivery is
built from trees, planted onto the base's local branch with a single
ref update, and pushed inherently, with one retry cycle answering a
concurrent remote movement and a uniform rollback restoring the
pre-resolution tip of the base's local branch on every failure. Both
forms of the nothing-to-do idempotency — the base already carrying
the topic's commits, or already carrying its content under a
different commit — are successes that emit and return like any other
and plant nothing. The strategy whitelist lives here and fires before
anything else; the addressee and base resolutions and the message
template belong to the exchange core; the bounded git mutations to
the nested git cell; the notification to the nested hooks zone. Git
infrastructure failures surface as ``click.ClickException`` — the
clean-error boundary of the domain.
"""

from __future__ import annotations

import contextlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import click

from ..history import current_year, resolve_current_branch_name
from .exchange import (
    ExchangeBase,
    ExchangeTarget,
    _base_branch_names,
    _has_local_branch,
    _has_remote_ref,
    render_commit_template,
    resolve_exchange_base,
    resolve_exchange_target,
)
from .git import (
    create_commit_from_tree,
    is_ancestor,
    list_branch_refs,
    merge_tree,
    origin_configured,
    point_branch_at_commit,
    push_branch,
    push_revision_to_branch,
    resolve_commit_message,
    resolve_commit_tree,
    resolve_ref_commit,
)
from .hooks import TopicHooks, TopicIdentity

_STRATEGIES = ("merge", "ff", "squash")
"""The propagation strategy whitelist — validated in the domain, nowhere else."""

_STRATEGY_KEY = "topics.propagate.strategy"
"""The configuration key an invalid strategy names."""

_OUTCOMES = {"merge": "merged", "ff": "fast-forwarded", "squash": "squashed"}
"""The realized kind of each delivery — the outcome half of the result line."""

_DEFAULT_COMMIT_MESSAGE = "Propagate topic '{slug}' into '{base}'"
"""The built-in commit message template — rendered through the shared template engine."""

_RESULT_LINE = "Propagated topic {year}/{slug} into '{base}' via {strategy} ({outcome})"
"""The single result line of the operation."""

_CONFLICT_HINT = (
    "the propagation conflicts — deliver it manually with git (merge or squash the topic into the base), then retry"
)
"""The suggestion of a conflicting delivery build — nothing was planted."""

_NOT_FAST_FORWARDABLE_HINT = (
    "the base carries commits the topic does not and the ff strategy cannot deliver — "
    "deliver it manually with git or propagate with the merge strategy, then retry"
)
"""The suggestion of a non-fast-forwardable ff delivery — nothing was planted."""

_REJECTION_SIGNATURES = ("rejected", "non-fast-forward", "fetch first")
"""The stderr markers of a push the remote rejected for concurrent movement."""


@dataclass(frozen=True, kw_only=True)
class PropagationPlan:
    """The resolved propagation — the self-contained plan the caller confirms and executes.

    Attributes:
        target: The addressed topic of the delivery.
        base_ref: The base revision string as resolved by the caller.
        strategy: The validated strategy — merge, ff, or squash.
        message: The rendered commit message.
        year: The resolved year of the operation.
    """

    target: ExchangeTarget
    base_ref: str
    strategy: str
    message: str
    year: str


def resolve_propagation(
    identifier: str | None,
    base_ref: str,
    strategy: str | None,
    commit_message: str | None,
    year: str | None = None,
) -> PropagationPlan:
    """Resolve the delivery read-only — every decision before the confirmation.

    Args:
        identifier: The addressee input — a branch name, a topic slug,
            or their prefix; ``None`` addresses the current topic.
        base_ref: The base revision string as resolved by the caller.
        strategy: The strategy name from ``topics.propagate.strategy``
            — ``None`` applies the built-in default ``merge``; an
            invalid value is a clean configuration error naming the
            key.
        commit_message: The message template from
            ``topics.propagate.commit`` — ``None`` applies the
            built-in default ``Propagate topic '{slug}' into
            '{base}'``.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        The plan — the addressee, the base, the validated strategy,
        the rendered message, and the resolved year.

    Algorithm:
        1. Validate ``strategy`` against merge, ff, squash — an
           invalid value is a clean configuration error naming
           ``topics.propagate.strategy``, before anything else
        2. Resolve the addressee via ``resolve_exchange_target``
        3. ``origin_configured`` reading False is a clean error — the
           push is inherent to the delivery, the remote must exist
        4. A base naming no branch of the inventory — neither a local
           branch nor an origin twin, so a tag or a hash — is a clean
           error: the delivery lands on a branch
        5. The local branch named by the base being the current branch
           — read via ``resolve_current_branch_name`` — is a clean
           error asking to switch away first
        6. Render the message via ``render_commit_template`` — the
           template or the built-in default
        7. Return the plan

    Requirements:
        Fully read-only — no fetch, no ref write, no working-copy
        touch: a declined confirmation performs nothing at all.

        The ff fast-forwardability is verified authoritatively at
        execution against the effective tip.

    Constraints:
        Do not confirm — the confirmation belongs to the caller.

    Raises:
        click.ClickException: an invalid strategy, an unaddressable
            addressee (the resolution's reason), a missing origin
            remote, a base naming no branch (a tag or a hash), the
            base naming the current branch, a git infrastructure
            failure (its stderr when git reports one, or a missing git
            binary), or the fatal ``ImportError`` of the
            hooks-registry assembly.
    """
    try:
        return _resolve_propagation(identifier, base_ref, strategy, commit_message, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        # The propagate notification builds the run registry on first
        # delivery — a broken ``goga_tool_*`` package is the platform's
        # single fatal case and surfaces here as one clean error, the
        # boundary of every emitting operation.
        raise click.ClickException(str(exc)) from exc
    except RuntimeError as exc:
        # The git-version gate may leak raw from the plumbing chain —
        # the boundary keeps the public surface one clean error.
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        # An OS-level failure can strike at any phase — a git
        # invocation failing to spawn or a ref write failing at the
        # filesystem — so the message stays phase-neutral; it surfaces
        # here as one clean error instead of a raw traceback.
        raise click.ClickException(f"cannot complete the propagation: {exc}") from exc


def _resolve_propagation(
    identifier: str | None,
    base_ref: str,
    strategy: str | None,
    commit_message: str | None,
    year: str | None,
) -> PropagationPlan:
    """Run the traced plan resolution — the unwrapped orchestration.

    Args:
        identifier: The addressee input as given, or ``None`` for the
            current topic.
        base_ref: The base revision string as resolved by the caller.
        strategy: The strategy name from the configuration, verbatim.
        commit_message: The message template from the configuration,
            verbatim.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        The resolved plan of the delivery.
    """
    effective = _validated_strategy(strategy)
    resolved_year = year or current_year()

    target = resolve_exchange_target(identifier, year)

    if not origin_configured():
        raise click.ClickException(
            "origin is not configured — propagating delivers with a push, which needs an origin remote"
        )

    refs = list_branch_refs()
    local, twin = _base_branch_names(base_ref, refs)

    if not (_has_local_branch(refs, local) or _has_remote_ref(refs, twin)):
        # A tag or a hash pins a commit — no branch to deliver onto. The
        # write-through of a local-less base would otherwise invent a
        # remote branch named after the tag or the hash, delivering the
        # topic nowhere the user intended.
        raise click.ClickException(f"the propagation base must be a branch — {base_ref!r} names a tag or a commit hash")

    if local == resolve_current_branch_name():
        raise click.ClickException(f"base branch {local!r} is checked out — switch away before propagating")

    message = render_commit_template(
        commit_message if commit_message is not None else _DEFAULT_COMMIT_MESSAGE,
        target.topic,
        base_ref,
    )

    return PropagationPlan(target=target, base_ref=base_ref, strategy=effective, message=message, year=resolved_year)


def execute_propagation(plan: PropagationPlan) -> str:
    """Execute the confirmed delivery — build, plant, push, with one retry cycle and a uniform rollback.

    Args:
        plan: The resolved plan — the caller has confirmed it.

    Returns:
        One line describing the outcome — the topic, the target base,
        the strategy, and the outcome.

    Algorithm:
        1. Resolve the own tip via ``resolve_ref_commit``; when the
           base names a local branch, capture its current tip as the
           rollback tip — before the resolution may write a
           reconciliation onto it
        2. Resolve the base via ``resolve_exchange_base`` — the
           version gate, the reported fetch, the effective tip, a
           possible reconciliation; the base's local branch being the
           current branch is a clean error asking to switch away
           first
        3. ``is_ancestor`` reporting the own tip contained in the
           effective tip is the nothing-to-do idempotent success:
           emit ``topic_propagated`` with the outcome
           ``nothing-to-do`` and return the line — a reconciliation
           the resolution wrote stands as sanctioned base bookkeeping
        4. Build the delivery: merge -> ``merge_tree`` of the
           effective tip with the own tip, then a two-parent commit
           via ``create_commit_from_tree``; squash -> the same tree
           over the single parent — the effective tip; ff -> the
           effective tip must be contained in the own tip, otherwise
           a clean error suggesting manual git; the delivery tree
           equal to the effective tip's tree is the second,
           content-based nothing-to-do success — nothing is planted
           or pushed
        5. Plant: the base's local branch exists ->
           ``point_branch_at_commit`` of the base's local branch at
           the delivery; a remote-only base plants nothing locally —
           the write-through
        6. Push — inherent: the local path via ``push_branch`` of the
           base's local branch, creating the remote branch when
           absent; the write-through via ``push_revision_to_branch``
           with the delivery and the base name. After a successful
           inherent push — both step 6 paths and the retry-cycle
           success included — emit ``topic_published``: the identity,
           the remote branch ``origin/<base>``, the commit facts of
           the delivery commit the base twin carries
           (``resolve_commit_message``), and the outcome ``pushed``
           — before the propagate notification
        7. A push rejected for concurrent remote movement gets one
           retry cycle — the base's local branch is first rolled back
           to the captured pre-resolution tip (removing the planted
           delivery, so the re-resolution sees the pre-attempt pair),
           then the re-resolution runs its own reported fetch and
           re-resolves the effective tip, the delivery is rebuilt,
           re-planted, and re-pushed; a second rejection is a clean
           error carrying git's reason
        8. Every failure rolls back fully — the base's local branch
           returns to the captured pre-resolution tip via
           ``point_branch_at_commit``, removing a reconciliation the
           resolution wrote and a delivery the attempt planted
        9. Emit ``topic_propagated`` — the identity, the base name,
           the strategy, the outcome
        10. Return the single result line

    Requirements:
        Always checkout-free — the working copy, the index, and HEAD
        are never touched.

        Idempotency is content-based — both the commit-reachability
        form and the identical-delivery-tree form are the
        nothing-to-do success and emit like any other.

        The topic stays alive — its branch and directory are
        untouched.

        Failure atomicity is uniform — a conflict or a failed push
        leaves the pre-operation state.

        The retry cycle runs exactly once.

        A nothing-to-do delivery pushes nothing and emits no
        publication — the publication event fires exactly when the
        inherent push completed.

    Constraints:
        Do not re-resolve the addressee — the plan carries it.

        Do not clean the topic up — clear stays separate.

    Raises:
        click.ClickException: a conflicting delivery build, a
            non-fast-forwardable ff delivery, a push rejected twice
            for concurrent movement, the base naming the current
            branch, a git infrastructure failure (its stderr when git
            reports one, or a missing git binary), the git-version
            gate, or the fatal ``ImportError`` of the hooks-registry
            assembly.
    """
    try:
        return _execute_propagation(plan)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        # The propagate notification builds the run registry on first
        # delivery — a broken ``goga_tool_*`` package is the platform's
        # single fatal case and surfaces here as one clean error.
        raise click.ClickException(str(exc)) from exc
    except RuntimeError as exc:
        # The git-version gate may leak raw from the plumbing chain —
        # the boundary keeps the public surface one clean error.
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        # An OS-level failure can strike at any phase — a git
        # invocation failing to spawn or a ref write failing at the
        # filesystem — so the message stays phase-neutral; it surfaces
        # here as one clean error instead of a raw traceback.
        raise click.ClickException(f"cannot complete the propagation: {exc}") from exc


def _execute_propagation(plan: PropagationPlan) -> str:
    """Run the traced delivery — the unwrapped orchestration.

    Args:
        plan: The confirmed plan of the delivery.

    Returns:
        The single result line of the outcome.
    """
    own_tip = resolve_ref_commit(plan.target.branch)

    # The rollback tip is captured before the resolution may write a
    # reconciliation onto the local base branch; it stays the one
    # restore point of the whole operation, retry cycle included.
    refs = list_branch_refs()
    local, _twin = _base_branch_names(plan.base_ref, refs)
    rollback_tip = resolve_ref_commit(local) if _has_local_branch(refs, local) else None

    base = resolve_exchange_base(plan.base_ref, plan.target.branch, own_tip)
    _reject_checked_out_base(base)

    try:
        try:
            return _deliver(plan, base, own_tip)
        except _RejectedDeliveryError:
            # The one retry cycle: roll the failed attempt's plant back
            # to the pre-resolution tip first — the re-resolution must
            # see the pre-attempt pair, not the pair contaminated by
            # this operation's own planted delivery, or the
            # reconciliation it writes would contain the own tip and
            # the retry would read as a false nothing-to-do. The
            # re-resolution then runs its own reported fetch, refreshes
            # the twin, and re-resolves the effective tip; the delivery
            # is rebuilt, re-planted, and re-pushed.
            _rollback(base, rollback_tip)
            base = resolve_exchange_base(plan.base_ref, plan.target.branch, own_tip)
            try:
                return _deliver(plan, base, own_tip)
            except _RejectedDeliveryError as second:
                raise click.ClickException(
                    f"origin rejected the propagation of {plan.target.topic!r} twice — {_git_reason(second.failure)}"
                ) from second
    except (click.ClickException, subprocess.CalledProcessError, OSError, RuntimeError):
        _rollback(base, rollback_tip)
        raise


def _validated_strategy(strategy: str | None) -> str:
    """Validate the strategy input against the whitelist.

    Args:
        strategy: The strategy name from
            ``topics.propagate.strategy``, verbatim — ``None`` means
            unset.

    Returns:
        The effective strategy — the input, or ``merge`` when unset.

    Raises:
        click.ClickException: The input is not on the whitelist — the
            message names the configuration key and the value.
    """
    if strategy is None:
        return "merge"
    if strategy not in _STRATEGIES:
        raise click.ClickException(
            f"unknown propagate strategy {strategy!r} — {_STRATEGY_KEY} accepts one of: {', '.join(_STRATEGIES)}"
        )
    return strategy


def _reject_checked_out_base(base: ExchangeBase) -> None:
    """Refuse a base whose local branch hosts the current working branch.

    The plan may be executed long after it was resolved — the guard
    re-checks the state of the execution moment, before any build: a
    plant onto the checked-out branch would leave HEAD pointing past
    the files on disk.

    Args:
        base: The resolved base of the execution moment.

    Raises:
        click.ClickException: The base's local branch is the current
            branch.
    """
    if base.local_branch is not None and base.local_branch == resolve_current_branch_name():
        raise click.ClickException(f"base branch {base.local_branch!r} is checked out — switch away before propagating")


class _RejectedDeliveryError(Exception):
    """A delivery push the remote rejected for concurrent movement — the retry signal.

    Attributes:
        failure: The push failure as git reported it — the reason the
            clean error of a second rejection carries.
    """

    def __init__(self, failure: subprocess.CalledProcessError) -> None:
        super().__init__(str(failure))
        self.failure = failure


def _deliver(plan: PropagationPlan, base: ExchangeBase, own_tip: str) -> str:
    """Deliver once — the idempotency checks, the build, the plant, the push.

    Args:
        plan: The confirmed plan of the delivery.
        base: The resolved base the delivery lands on.
        own_tip: The topic's own branch tip.

    Returns:
        The single result line of the outcome — a delivery or a
        nothing-to-do.

    Raises:
        click.ClickException: a conflicting build, or a
            non-fast-forwardable ff delivery — nothing was planted.
        subprocess.CalledProcessError: a push failure outside the
            concurrent-movement signature.
        _RejectedDeliveryError: a push the remote rejected for
            concurrent movement — the retry signal; the caller decides
            whether a retry cycle remains.
    """
    if is_ancestor(own_tip, base.tip):
        # The reachability idempotency — the base already carries the
        # topic's commits; a reconciliation the resolution wrote
        # stands as sanctioned base bookkeeping.
        return _nothing_to_do(plan, base)

    base_tree = resolve_commit_tree(base.tip)
    tree: str | None = None

    if plan.strategy in ("merge", "squash"):
        tree = merge_tree(base.tip, own_tip)
        if tree is None:
            raise click.ClickException(_CONFLICT_HINT)
        delivery_tree = tree
    else:
        if not is_ancestor(base.tip, own_tip):
            raise click.ClickException(_NOT_FAST_FORWARDABLE_HINT)
        delivery = own_tip
        delivery_tree = resolve_commit_tree(own_tip)

    if delivery_tree == base_tree:
        # The content idempotency — the base already carries the
        # topic's state under a different commit, a squash that landed
        # before; nothing is planted or pushed.
        return _nothing_to_do(plan, base)

    if plan.strategy == "merge":
        delivery = create_commit_from_tree(tree, [base.tip, own_tip], plan.message)
    elif plan.strategy == "squash":
        delivery = create_commit_from_tree(tree, [base.tip], plan.message)

    _plant_and_push(plan, base, delivery)

    _emit_published_delivery(plan, base, delivery)
    outcome = _OUTCOMES[plan.strategy]

    _emit_propagated(plan.target, base, plan.strategy, outcome, plan.year)
    return _RESULT_LINE.format(
        year=plan.year, slug=plan.target.topic, base=base.name, strategy=plan.strategy, outcome=outcome
    )


def _nothing_to_do(plan: PropagationPlan, base: ExchangeBase) -> str:
    """Close a nothing-to-do delivery — the idempotent success line.

    Args:
        plan: The confirmed plan of the delivery.
        base: The resolved base that already carries the topic.

    Returns:
        The result line naming the nothing-to-do outcome.
    """
    _emit_propagated(plan.target, base, plan.strategy, "nothing-to-do", plan.year)
    return _RESULT_LINE.format(
        year=plan.year,
        slug=plan.target.topic,
        base=base.name,
        strategy=plan.strategy,
        outcome="nothing-to-do",
    )


def _plant_and_push(plan: PropagationPlan, base: ExchangeBase, delivery: str) -> None:
    """Plant the delivery and push it — the local path or the write-through.

    Args:
        plan: The confirmed plan of the delivery.
        base: The resolved base — the plant branch holder.
        delivery: The delivery commit.

    Raises:
        subprocess.CalledProcessError: a push failure outside the
            concurrent-movement signature.
        _RejectedDeliveryError: a push the remote rejected for
            concurrent movement — the retry signal.
    """
    if base.local_branch is not None:
        point_branch_at_commit(base.local_branch, delivery)
        _push_with_retry(push_branch, base.local_branch)
    else:
        # The remote branch name is the base spelling minus a leading
        # ``origin/`` only — a slash-free base (``main``) or a nested
        # one (``origin/feature/x``) must survive verbatim, where the
        # after-the-first-slash short form would yield an empty or
        # truncated refspec.
        _push_with_retry(push_revision_to_branch, delivery, plan.base_ref.removeprefix("origin/"))


def _emit_published_delivery(plan: PropagationPlan, base: ExchangeBase, delivery: str) -> None:
    """Emit the publication notification — the delivery facts of the inherent push.

    The branch spelling mirrors the refspec target of the push that
    just landed — the base's local branch name, or the base spelling
    minus a leading ``origin/`` for the write-through — so a nested
    base (``origin/feature/x``) survives verbatim.

    Args:
        plan: The confirmed plan — the identity source and the base
            spelling holder.
        base: The resolved base — the local branch holder of the
            delivery.
        delivery: The delivery commit the base twin carries.
    """
    remote = base.local_branch if base.local_branch is not None else plan.base_ref.removeprefix("origin/")
    TopicHooks().emit_published(
        TopicIdentity(slug=plan.target.topic, year=plan.year, branch=plan.target.branch),
        remote_branch=f"origin/{remote}",
        commit_hash=delivery,
        commit_message=resolve_commit_message(delivery),
        outcome="pushed",
    )


def _push_with_retry(operation: Callable[..., None], *arguments: str) -> None:
    """Run one push, translating the concurrent-movement rejection into the retry signal.

    Args:
        operation: The push routine of the path — ``push_branch`` or
            ``push_revision_to_branch``.
        arguments: The push arguments.

    Raises:
        subprocess.CalledProcessError: the push failed outside the
            concurrent-movement signature.
        _RejectedDeliveryError: the push failed with the signature —
            the caller decides whether a retry cycle remains.
    """
    try:
        operation(*arguments)
    except subprocess.CalledProcessError as failure:
        if _concurrent_movement(failure):
            raise _RejectedDeliveryError(failure) from failure
        raise


def _concurrent_movement(failure: subprocess.CalledProcessError) -> bool:
    """Report whether a push failure carries the concurrent-movement signature.

    Args:
        failure: The push failure as git reported it.

    Returns:
        ``True`` when the stderr names the rejection a concurrent
        remote movement causes — the one wording pair across the
        supported git floor.
    """
    stderr = failure.stderr or ""
    return any(signature in stderr for signature in _REJECTION_SIGNATURES)


def _git_reason(failure: subprocess.CalledProcessError) -> str:
    """Extract git's own reason from a failure — the stderr or the exception text.

    Args:
        failure: The git failure as reported.

    Returns:
        The detail the clean error carries.
    """
    return (failure.stderr or "").strip() or str(failure)


def _rollback(base: ExchangeBase, rollback_tip: str | None) -> None:
    """Restore the base's local branch to the captured pre-resolution tip.

    Invoked on every failure of the delivery — a conflict, a failed
    push, the second rejection — and once before the retry's
    re-resolution, removing both a reconciliation the resolution wrote
    and a delivery an attempt planted; a base without a local branch,
    or one whose tip was never captured, rolls back nothing. A failure
    of the restore itself is suppressed so the original error surfaces.

    Args:
        base: The resolved base of the moment — the restore target.
        rollback_tip: The captured pre-resolution tip, or ``None`` —
            nothing to restore in that case.
    """
    if base.local_branch is not None and rollback_tip is not None:
        with contextlib.suppress(subprocess.CalledProcessError, OSError):
            point_branch_at_commit(base.local_branch, rollback_tip)


def _emit_propagated(target: ExchangeTarget, base: ExchangeBase, strategy: str, outcome: str, year: str) -> None:
    """Emit the propagate notification — the facts of one completed delivery.

    Args:
        target: The addressed target — the identity source.
        base: The resolved base — the name the line and the context
            carry.
        strategy: The applied strategy.
        outcome: The outcome kind.
        year: The resolved year of the operation.
    """
    identity = TopicIdentity(slug=target.topic, year=year, branch=target.branch)
    TopicHooks().emit_propagated(identity, base=base.name, strategy=strategy, outcome=outcome)
