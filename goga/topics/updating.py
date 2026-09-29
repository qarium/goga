"""The update operation of the topics domain.

The entity declared in the cell CODEMANIFEST with
``location: updating.py``: ``update_topic`` — bringing a topic up to
its base under the configured strategy, checkout-free for every other
topic and in place — always behind a read-only pre-flight — for the
current one, with an optional publication push of the refreshed
branch. Every conflict is detected read-only before any topic
mutation; a reconciliation the shared base resolution wrote is rolled
back to the captured pre-resolution tip whenever the update fails that
pre-mutation gauntlet. The already-current state is an idempotent
success — nothing mutates and nothing publishes. The rebase
publication pushes under a lease bound to the pre-rebase own tip; the
publish push is the one atomicity exception — a failed push leaves the
confirmed update standing. The facts of every completed update fire
over the nested hooks zone as ``topic_updated``. The strategy
whitelist lives here and fires before anything else; the addressee and
base resolutions and the message template belong to the exchange
core; the bounded git mutations to the nested git cell; the
checkpoints to the nested hooks zone. Git infrastructure failures
surface as ``click.ClickException`` — the clean-error boundary of the
domain.
"""

from __future__ import annotations

import contextlib
import subprocess

import click

from ..history import current_year
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
    fast_forward_current_branch,
    is_ancestor,
    is_working_tree_clean,
    list_branch_refs,
    merge_into_current,
    merge_tree,
    origin_configured,
    point_branch_at_commit,
    push_branch,
    push_branch_with_lease,
    rebase_current_onto,
    replay_commits,
    resolve_ref_commit,
)
from .hooks import TopicHooks, TopicIdentity

_STRATEGIES = ("merge", "rebase", "ff-else-merge", "ff-else-rebase")
"""The update strategy whitelist — validated in the domain, nowhere else."""

_STRATEGY_KEY = "topics.update.strategy"
"""The configuration key an invalid strategy names."""

_FF_ELSE_STRATEGIES = ("ff-else-merge", "ff-else-rebase")
"""The strategies whose fast-forward arm the no-own-work state takes."""

_OUTCOMES = {"merge": "merged", "rebase": "rebased", "fast-forward": "fast-forwarded"}
"""The realized kind of each update — the outcome half of the result line."""

_DEFAULT_COMMIT_MESSAGE = "Update topic '{slug}' from '{base}'"
"""The built-in commit message template — rendered through the shared template engine."""

_RESULT_LINE = "Updated topic {year}/{slug} from '{base}' via {strategy} ({outcome})"
"""The single result line of the operation."""

_MANUAL_HINT = (
    "the update conflicts — apply it manually with git "
    "(merge the base into the topic or rebase the topic onto it), then retry"
)
"""The suggestion of every pre-mutation conflict — nothing was mutated."""


def update_topic(  # noqa: PLR0913, PLR0917 — the CODEMANIFEST-declared signature
    identifier: str | None,
    base_ref: str,
    strategy: str | None,
    commit_message: str | None,
    publish: bool = False,
    year: str | None = None,
) -> str:
    """Bring a topic up to its base — the update operation of the domain.

    Args:
        identifier: The addressee input — a branch name, a topic slug,
            or their prefix; ``None`` addresses the current topic.
        base_ref: The base revision string as resolved by the caller.
        strategy: The strategy name from ``topics.update.strategy`` —
            ``None`` applies the built-in default ``merge``; an invalid
            value is a clean configuration error naming the key.
        commit_message: The message template from
            ``topics.update.commit`` — ``None`` applies the built-in
            default ``Update topic '{slug}' from '{base}'``.
        publish: ``True`` pushes the refreshed branch after success.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        One line describing the outcome — the addressee, the base, the
        configured strategy, and the realized outcome.

    Algorithm:
        1. Validate ``strategy`` against the whitelist — an invalid
           value is a clean configuration error naming
           ``topics.update.strategy``, before anything else
        2. Resolve the addressee via ``resolve_exchange_target`` and
           the own tip via ``resolve_ref_commit``
        3. Capture the local base branch's current tip as the rollback
           tip — before the base resolution may write a reconciliation
           onto it — then resolve the base via ``resolve_exchange_base``
        4. ``is_ancestor`` reporting the effective tip contained in the
           own tip -> the already-current idempotent success: emit
           ``topic_updated`` with ``published`` False and return the
           line — ``publish`` publishes nothing in this case
        5. The ff decision: an ff-else strategy with the effective tip
           containing the own tip — the topic has no own work — takes
           the fast-forward; otherwise the named base strategy applies
        6. Render the message via ``render_commit_template`` — the
           template or the built-in default
        7. The current topic: probe ``is_working_tree_clean`` — a
           dirty tree is a clean error before any mutation; the
           read-only pre-flight — ``merge_tree`` of the own tip with
           the effective tip, ``replay_commits`` of the own line onto
           the effective tip — a conflict is a clean error suggesting
           manual git; then the real mutation —
           ``merge_into_current``, ``rebase_current_onto``, or
           ``fast_forward_current_branch``. Another topic — fully
           checkout-free: merge -> one two-parent commit of the own
           tip and the effective tip via ``create_commit_from_tree``,
           planted via ``point_branch_at_commit``; rebase ->
           ``replay_commits`` planted at the replayed tip;
           fast-forward -> the plant at the effective tip, no commit
           authored. Every conflict of this gauntlet restores the
           captured pre-resolution tip of the base's local branch when
           the resolution wrote a reconciliation
        8. ``publish``: ``origin_configured`` reading False is a clean
           error; merge or fast-forward -> ``push_branch`` of the
           addressee's branch; rebase -> the origin twin exists ?
           ``push_branch_with_lease`` with the addressee's branch and
           the pre-rebase own tip : ``push_branch``; a failed publish
           push leaves the confirmed update standing and surfaces
           git's reason as a clean error — the single atomicity
           exception
        9. Emit ``topic_updated`` — the identity, the base name, the
           effective tip, the configured strategy name, the outcome,
           the published flag — and return the single result line

    Requirements:
        No confirmation is asked.

        Every conflict is detected read-only before any topic mutation
        — a conflicted update leaves the repository at its
        pre-operation state.

        The in-place path never runs without its pre-flight; the
        checkout-free paths are atomic by construction — objects
        dangle until the single ref update.

        The rebase lease binds to the own tip immediately before the
        rebase, with no extra fetch of the topic twin.

        The result is exactly one line and names the addressee.

    Constraints:
        Do not rewrite history beyond the topic's own branch under the
        configured rebase.

        Do not push without ``publish``.

    Raises:
        click.ClickException: an invalid strategy, an unaddressable
            addressee (the resolution's reason), a dirty working tree
            of the current topic, any pre-mutation conflict, a missing
            origin remote on publish, a rejected or failed push, a git
            infrastructure failure (its stderr when git reports one,
            or a missing git binary), the git-version gate, or the
            fatal ``ImportError`` of the hooks-registry assembly.
    """
    try:
        return _update_topic(identifier, base_ref, strategy, commit_message, publish, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        # The update notification builds the run registry on first
        # delivery — a broken ``goga_tool_*`` package is the platform's
        # single fatal case and surfaces here as one clean error, the
        # ``switch_topic`` and ``ensure_topic`` boundary.
        raise click.ClickException(str(exc)) from exc
    except RuntimeError as exc:
        # The git-version gate may leak raw from the plumbing chain —
        # the boundary keeps the public surface one clean error.
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        # An OS-level failure can strike at any phase — a git
        # invocation failing to spawn or the in-place moves failing at
        # the filesystem — so the message stays phase-neutral; it
        # surfaces here as one clean error instead of a raw traceback.
        raise click.ClickException(f"cannot complete the update: {exc}") from exc


def _update_topic(  # noqa: PLR0913, PLR0917 — the unwrapped mirror of the declared signature
    identifier: str | None,
    base_ref: str,
    strategy: str | None,
    commit_message: str | None,
    publish: bool,
    year: str | None,
) -> str:
    """Run the traced update — the unwrapped orchestration.

    Args:
        identifier: The addressee input as given, or ``None`` for the
            current topic.
        base_ref: The base revision string as resolved by the caller.
        strategy: The strategy name from the configuration, verbatim.
        commit_message: The message template from the configuration,
            verbatim.
        publish: ``True`` pushes the refreshed branch after success.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        The single result line of the outcome.
    """
    effective = _validated_strategy(strategy)
    resolved_year = year or current_year()

    target = resolve_exchange_target(identifier, year)
    own_tip = resolve_ref_commit(target.branch)

    # The rollback tip is captured before the resolution may write a
    # reconciliation onto the local base branch; the twin-exists probe
    # of the publish step reads the same inventory — no extra fetch.
    refs = list_branch_refs()
    local, _twin = _base_branch_names(base_ref, refs)
    rollback_tip = resolve_ref_commit(local) if _has_local_branch(refs, local) else None

    base = resolve_exchange_base(base_ref, target.branch, own_tip)

    if is_ancestor(base.tip, own_tip):
        # The idempotent success — the topic already carries its base,
        # so nothing mutates and there is no refreshed branch to push.
        _emit_updated(target, base, resolved_year, effective, "already-current", False)
        return _result_line(target, base, resolved_year, effective, "already-current")

    realized = effective
    if effective in _FF_ELSE_STRATEGIES:
        # The ff decision: the effective tip containing the own tip —
        # no own work — takes the fast-forward; otherwise the named
        # base strategy applies — ``ff-else-merge`` merges,
        # ``ff-else-rebase`` rebases.
        realized = "fast-forward" if is_ancestor(own_tip, base.tip) else effective.removeprefix("ff-else-")
    message = render_commit_template(
        commit_message if commit_message is not None else _DEFAULT_COMMIT_MESSAGE,
        target.topic,
        base.name,
    )

    if target.current:
        _update_in_place(realized, base, message, own_tip, rollback_tip)
    else:
        _update_checkout_free(realized, target, base, message, own_tip, rollback_tip)

    if publish:
        _publish_refreshed_branch(realized, target, own_tip, refs)

    outcome = _OUTCOMES[realized]
    _emit_updated(target, base, resolved_year, effective, outcome, publish)
    return _result_line(target, base, resolved_year, effective, outcome)


def _validated_strategy(strategy: str | None) -> str:
    """Validate the strategy input against the whitelist.

    Args:
        strategy: The strategy name from ``topics.update.strategy``,
            verbatim — ``None`` means unset.

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
            f"unknown update strategy {strategy!r} — {_STRATEGY_KEY} accepts one of: {', '.join(_STRATEGIES)}"
        )
    return strategy


def _update_in_place(realized: str, base: ExchangeBase, message: str, own_tip: str, rollback_tip: str | None) -> None:
    """Move the current topic in place — always behind the read-only pre-flight.

    Args:
        realized: The realized strategy kind — merge, rebase, or
            fast-forward.
        base: The resolved base — the pre-flight oracle and the
            rollback holder.
        message: The rendered commit message of the merge.
        own_tip: The topic's own branch tip before the move.
        rollback_tip: The captured pre-resolution tip of the base's
            local branch, or ``None``.

    Raises:
        click.ClickException: A dirty working tree, or a pre-flight
            conflict — nothing was mutated in either case.
        subprocess.CalledProcessError: A git infrastructure failure of
            the pre-flight or the move — the base is restored first.
        OSError: An OS-level failure of the same gauntlet — the base is
            restored first.
    """
    if not is_working_tree_clean():
        _restore_base(base, rollback_tip)
        raise click.ClickException(
            "the working tree is not clean — commit or stash before updating the current topic in place"
        )

    try:
        if realized == "merge":
            conflicted = merge_tree(own_tip, base.tip) is None
        elif realized == "rebase":
            conflicted = replay_commits(base.tip, own_tip) is None
        else:
            # A fast-forward cannot conflict — git's own --ff-only fails
            # cleanly before touching anything.
            conflicted = False

        if conflicted:
            raise click.ClickException(_MANUAL_HINT)

        if realized == "merge":
            merge_into_current(base.tip, message)
        elif realized == "rebase":
            rebase_current_onto(base.tip)
        else:
            fast_forward_current_branch(base.tip)
    except (click.ClickException, subprocess.CalledProcessError, OSError):
        # Every failure of the gauntlet — a conflict, an infrastructure
        # error of the build, a failed move — leaves the base's local
        # branch at its pre-operation tip.
        _restore_base(base, rollback_tip)
        raise


def _update_checkout_free(  # noqa: PLR0913, PLR0917 — the mutation step over the operation's own facts
    realized: str,
    target: ExchangeTarget,
    base: ExchangeBase,
    message: str,
    own_tip: str,
    rollback_tip: str | None,
) -> None:
    """Move another topic without checkout — the checkout-free build and plant.

    Every built object dangles until the single ref update; a build
    conflict restores the reconciliation and surfaces the manual hint
    with the topic branch untouched.

    Args:
        realized: The realized strategy kind — merge, rebase, or
            fast-forward.
        target: The addressed target — the plant branch holder.
        base: The resolved base.
        message: The rendered commit message of the merge commit.
        own_tip: The topic's own branch tip before the move.
        rollback_tip: The captured pre-resolution tip of the base's
            local branch, or ``None``.

    Raises:
        click.ClickException: A build conflict — nothing was planted.
        subprocess.CalledProcessError: A git infrastructure failure of
            the build or the plant — the base is restored first.
        OSError: An OS-level failure of the same gauntlet — the base is
            restored first.
    """
    try:
        if realized == "merge":
            tree = merge_tree(own_tip, base.tip)
            if tree is None:
                raise click.ClickException(_MANUAL_HINT)
            commit = create_commit_from_tree(tree, [own_tip, base.tip], message)
            point_branch_at_commit(target.branch, commit)
        elif realized == "rebase":
            tip = replay_commits(base.tip, own_tip)
            if tip is None:
                raise click.ClickException(_MANUAL_HINT)
            point_branch_at_commit(target.branch, tip)
        else:
            point_branch_at_commit(target.branch, base.tip)
    except (click.ClickException, subprocess.CalledProcessError, OSError):
        # Every failure of the gauntlet — a conflict, an infrastructure
        # error of the build, a failed plant — leaves the base's local
        # branch at its pre-operation tip.
        _restore_base(base, rollback_tip)
        raise


def _publish_refreshed_branch(realized: str, target: ExchangeTarget, own_tip: str, refs: list) -> None:
    """Push the refreshed branch — the lease path of the rebase.

    Args:
        realized: The realized strategy kind — merge, rebase, or
            fast-forward.
        target: The addressed target — the pushed branch holder.
        own_tip: The topic's pre-rebase own tip — the lease value.
        refs: The branch inventory read before the move — the
            twin-exists oracle, with no extra fetch of the twin.

    Raises:
        click.ClickException: No origin remote is configured.
        subprocess.CalledProcessError: The push failed — the wrapper
            surfaces git's reason; the confirmed update stands.
    """
    if not origin_configured():
        raise click.ClickException("origin is not configured — publishing the updated branch needs an origin remote")

    if realized == "rebase" and _has_remote_ref(refs, f"origin/{target.branch}"):
        # The lease binds to the pre-rebase own tip — the exact commit
        # origin must still stand at for the rewritten push to be safe.
        push_branch_with_lease(target.branch, own_tip)
    else:
        push_branch(target.branch)


def _restore_base(base: ExchangeBase, rollback_tip: str | None) -> None:
    """Undo a reconciliation the base resolution wrote.

    Invoked on the dirty-tree error and every failure of either
    mutation gauntlet — a conflict signal or a raised infrastructure
    failure alike — a failed update leaves the base's local branch at
    its pre-operation tip. A failure of the restore itself is
    suppressed so the original error surfaces.

    Args:
        base: The resolved base — the reconciliation marker and the
            restore target.
        rollback_tip: The captured pre-resolution tip, or ``None`` —
            nothing to restore in that case.
    """
    if base.reconciled and rollback_tip is not None:
        with contextlib.suppress(subprocess.CalledProcessError, OSError):
            point_branch_at_commit(base.local_branch, rollback_tip)


def _emit_updated(  # noqa: PLR0913, PLR0917 — the six facts are the declared checkpoint signature
    target: ExchangeTarget, base: ExchangeBase, year: str, strategy: str, outcome: str, published: bool
) -> None:
    """Emit the update notification — the facts of one completed update.

    Args:
        target: The addressed target — the identity source.
        base: The resolved base — the name and the effective tip.
        year: The resolved year of the operation.
        strategy: The configured strategy name — the realized kind is
            the outcome.
        outcome: The outcome kind.
        published: ``True`` when the update published the refreshed
            branch.
    """
    identity = TopicIdentity(slug=target.topic, year=year, branch=target.branch)
    TopicHooks().emit_updated(
        identity,
        base=base.name,
        effective_tip=base.tip,
        strategy=strategy,
        outcome=outcome,
        published=published,
    )


def _result_line(target: ExchangeTarget, base: ExchangeBase, year: str, strategy: str, outcome: str) -> str:
    """Render the single result line of one outcome.

    Args:
        target: The addressed target — the addressee of the line.
        base: The resolved base — the named base of the line.
        year: The resolved year of the operation.
        strategy: The configured strategy name.
        outcome: The outcome kind.

    Returns:
        The result line.
    """
    return _RESULT_LINE.format(year=year, slug=target.topic, base=base.name, strategy=strategy, outcome=outcome)
