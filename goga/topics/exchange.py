"""The exchange core of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: exchange.py``: one resolved logical branch base — the
shared resolution result of the update and propagate operations —,
one addressed topic of an exchange, the base resolution — the git
version gate, the self-base and checked-out-base guards, the single
reported fetch, the projection containment, and the reconciliation
merge of a diverged local/origin pair —, the addressee resolution
reusing the switch tiers over the current branch or an identifier,
and the commit-message template engine — the single renderer of the
domain's authored messages. The base resolution is the one place a
diverged base pair reconciles: the merge lands on the local base
branch only and is never pushed here, and a tag or hash base never
fetches. Topic identity and addressing belong to the history facade;
git access belongs to the nested git cell; the numbered candidate
selection belongs to ``switching.py`` — one selection surface in the
package. Git infrastructure failures, a missing git binary, and the
git-version gate surface as ``click.ClickException`` — the clean-error
boundary of the domain.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import click

from ..history import resolve_current_branch_name
from .board import _short_name
from .git import (
    BranchRef,
    create_commit_from_tree,
    fetch_branch,
    is_ancestor,
    list_branch_refs,
    merge_tree,
    point_branch_at_commit,
    require_git_version,
    resolve_ref_commit,
)
from .switching import SwitchCandidate, _choose_candidate, resolve_switch_candidates

_FETCHING_LINE = "Fetching origin/{branch}..."
"""The stdout reporting line of the one fetch a base resolution runs."""

_RECONCILE_MESSAGE = "Reconcile base '{name}'"
"""The fixed message of a base-pair reconciliation commit."""


@dataclass(frozen=True, kw_only=True)
class ExchangeBase:
    """One resolved logical branch base — the shared resolution result of the exchange operations.

    Attributes:
        name: The base as addressed by the operation — the revision
            string it resolved from.
        tip: The effective tip commit of the logical branch.
        local_branch: The local branch of the base, or ``None`` when the
            base is remote-only or a tag/hash.
        reconciled: ``True`` when the resolution wrote a reconciliation
            merge onto the local base branch.
    """

    name: str
    tip: str
    local_branch: str | None
    reconciled: bool


@dataclass(frozen=True, kw_only=True)
class ExchangeTarget:
    """One addressed topic of an exchange operation.

    Attributes:
        topic: The topic slug of the addressed topic.
        branch: The own branch name — local form; a remote-only own
            branch is refused by the resolution.
        current: ``True`` when the own branch hosts the current working
            branch.
    """

    topic: str
    branch: str
    current: bool


def render_commit_template(template: str, slug: str, base: str) -> str:
    """Render a commit message from a template — the single template engine of the domain's authored messages.

    Args:
        template: The message template.
        slug: The topic slug.
        base: The base name as addressed.

    Returns:
        The rendered message — ``{slug}`` and ``{base}`` substituted,
        every unknown placeholder verbatim, nothing else transformed.

    Algorithm:
        1. Replace ``{slug}`` with ``slug`` and ``{base}`` with ``base``
        2. Return the message

    Requirements:
        Pure text transformation — no repository reads.

    Constraints:
        Do not validate the grammar — a template is configuration
        text, never a contract.
    """
    return template.replace("{slug}", slug).replace("{base}", base)


def resolve_exchange_base(base_ref: str, own_branch: str, own_tip: str) -> ExchangeBase:
    """Resolve the base as one logical branch — the shared machinery of the update and propagate operations.

    Args:
        base_ref: The base revision string as resolved by the caller.
        own_branch: The topic's own branch name — the self-base oracle.
        own_tip: The topic's own branch tip — the idempotency oracle.

    Returns:
        The resolved base — the effective tip the caller applies its
        strategy to, the local branch a rollback may restore, and the
        reconciliation marker.

    Algorithm:
        1. ``require_git_version`` — the exchange gate fires here, once
           for every caller
        2. A ``base_ref`` naming the ``own_branch`` — bare or
           origin-twin form — is a clean error: the topic is its own
           base
        3. Split ``base_ref`` into its local-branch/origin-twin pair;
           neither carried by the inventory -> the base resolves as a
           revision — a tag or a hash, read-only with no fetch. The
           local branch of a branch-shaped base being the current
           branch is a clean error asking to switch away first — a
           reconciliation must never move the checked-out branch under
           the working copy
        4. The branch-shaped base: echo one stdout line
           ``Fetching origin/<base>...`` then ``fetch_branch`` — the
           single sanctioned fetch; a fetch reporting the remote branch
           absent leaves the twin absent
        5. The projections as they stand after the fetch — the local
           tip and the twin tip, an unresolvable side skipped; one
           projection alone is the effective tip
        6. Both projections: one containing the other via
           ``is_ancestor`` -> the descendant is the effective tip
        7. The projections diverged: ``own_tip`` containing every
           projection -> the effective tip is ``own_tip`` itself and
           nothing is written — the already-carried state; otherwise
           the reconciliation — ``merge_tree`` of the pair, a conflict
           is a clean error asking to reconcile the branch manually
           with nothing mutated, a tree is committed via
           ``create_commit_from_tree`` with the fixed message
           ``Reconcile base '<name>'`` and planted onto the local base
           branch via ``point_branch_at_commit`` — the reconciliation
           commit is the effective tip

    Requirements:
        Exactly one fetch per resolution, reported before it runs —
        branch-shaped bases only; a tag or hash base never fetches.

        The local branch of a branch-shaped base being the current
        branch is refused before the fetch — a checked-out base is
        never moved under the working copy.

        The already-carried check precedes the reconciliation write —
        an up-to-date topic mutates nothing at all.

        The reconciliation lands only on the local base branch and is
        never pushed by the resolution itself.

        Atomicity: the reconciliation is the only mutation — built
        objects dangle until the single ref update.

    Constraints:
        Do not decide the strategy — the caller applies it to the tip.

        Do not resolve a base for a topic without its own branch — the
        caller resolves the addressee first.

    Raises:
        click.ClickException: the base naming the topic's own branch,
            the local base being the current branch, an unresolvable
            base (git's own reason via the wrapper), a fetch failure
            other than the absent twin, a conflicting reconciliation,
            a git older than the exchange floor, a missing git binary,
            or a git infrastructure failure.
    """
    try:
        return _resolve_exchange_base(base_ref, own_branch, own_tip)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except RuntimeError as exc:
        # The git-version gate of the exchange machinery fires inside
        # the resolution — once for every caller of the shared base
        # resolution.
        raise click.ClickException(str(exc)) from exc


def _resolve_exchange_base(base_ref: str, own_branch: str, own_tip: str) -> ExchangeBase:
    """Run the traced base resolution — the unwrapped orchestration.

    Args:
        base_ref: The base revision string as given.
        own_branch: The topic's own branch name.
        own_tip: The topic's own branch tip.

    Returns:
        The resolved base of the exchange.
    """
    require_git_version()

    if base_ref in (own_branch, f"origin/{own_branch}"):
        raise click.ClickException(f"the topic is its own base — {base_ref!r} names the addressed topic's branch")

    refs = list_branch_refs()
    local, twin = _base_branch_names(base_ref, refs)

    if not (_has_local_branch(refs, local) or _has_remote_ref(refs, twin)):
        # A tag or a hash — pinned by name, read-only, never fetched.
        return ExchangeBase(name=base_ref, tip=resolve_ref_commit(base_ref), local_branch=None, reconciled=False)

    if local == resolve_current_branch_name():
        # ``update-ref`` bypasses git's own current-branch protection —
        # a reconciliation planted here would leave HEAD pointing past
        # the files on disk.
        raise click.ClickException(f"base branch {local!r} is checked out — switch away before exchanging")

    click.echo(_FETCHING_LINE.format(branch=local))
    fetch_branch(local)

    local_tip = _projection(local)
    twin_tip = _projection(twin)

    if local_tip is None and twin_tip is None:
        raise click.ClickException(f"base {base_ref!r} no longer resolves — retry the exchange")

    effective, written = _effective_tip(base_ref, local, local_tip, twin_tip, own_tip)

    return ExchangeBase(
        name=base_ref,
        tip=effective,
        local_branch=local if local_tip is not None else None,
        reconciled=written,
    )


def resolve_exchange_target(identifier: str | None, year: str | None = None) -> ExchangeTarget:
    """Resolve the addressee of an exchange operation — the current topic when the identifier is omitted.

    Args:
        identifier: The user input — a branch name, a topic slug, or
            their prefix; ``None`` addresses the current topic.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        The addressed target — the topic slug, its own local branch,
        and the current-branch marker.

    Algorithm:
        1. ``identifier`` ``None`` -> the current branch via
           ``resolve_current_branch_name``; a detached HEAD or a branch
           hosting no topic is a clean error naming the branch; the
           hosted topic of the branch is the addressee
        2. Otherwise resolve the switch tiers via
           ``resolve_switch_candidates``; none -> a clean error with a
           hint to the board; several -> the numbered list with
           statuses and the number prompt — the ``switching.py``
           selection, or the failure with the list without interactive
           input; the chosen candidate's ``topic`` being ``None`` is a
           clean error — a branch without a topic is no addressee
        3. The chosen candidate remote-tracking — its local twin was
           dropped by the tier collapse, so it is remote-only -> a
           clean error hinting ``goga topics switch`` first
        4. Return the target with the current-branch marker

    Requirements:
        Read-only — nothing is mutated before the operation itself.

        The remote-only refusal fires here for both exchange
        operations.

    Constraints:
        Do not switch — the operations work without checkout.

    Raises:
        click.ClickException: no current branch, a branch hosting no
            topic, an identifier nothing hosts, a remote-only own
            branch, a git infrastructure failure (its stderr when git
            reports one, or a missing git binary), or the fatal
            ``ImportError`` of the scale assembly — the broken tool
            package is named in the message.
        click.Abort: Ctrl-C or EOF at the selection prompt — the
            repository is left untouched.
    """
    try:
        return _resolve_exchange_target(identifier, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc


def _resolve_exchange_target(identifier: str | None, year: str | None) -> ExchangeTarget:
    """Run the traced addressee resolution — the unwrapped orchestration.

    Args:
        identifier: The user input as entered, or ``None`` for the
            current topic.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        The addressed target of the exchange.
    """
    if identifier is None:
        chosen = _current_topic_candidate(year)
    else:
        candidates = resolve_switch_candidates(identifier, year)

        if not candidates:
            raise click.ClickException(f"no branch hosts {identifier!r} — run 'goga topics board' to see the board")

        chosen = candidates[0] if len(candidates) == 1 else _choose_candidate(candidates)

        if chosen.topic is None:
            raise click.ClickException(f"branch {chosen.branch!r} hosts no topic — it is no exchange addressee")

    if chosen.remote:
        raise click.ClickException(f"branch {chosen.branch!r} exists only on origin — run 'goga topics switch' first")

    return ExchangeTarget(
        topic=chosen.topic,
        branch=chosen.branch,
        current=chosen.branch == resolve_current_branch_name(),
    )


def _current_topic_candidate(year: str | None) -> SwitchCandidate:
    """Resolve the current branch's own topic candidate.

    Args:
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        The current branch's candidate — the one entry of the switch
        resolution whose branch is the current branch.

    Raises:
        click.ClickException: a detached HEAD, or a current branch
            hosting no topic of the year — the branch is named.
    """
    current = resolve_current_branch_name()

    if current is None:
        raise click.ClickException("no current branch — name a topic or switch to a topic branch first")

    candidates = [candidate for candidate in resolve_switch_candidates(current, year) if candidate.branch == current]

    if not candidates or candidates[0].topic is None:
        raise click.ClickException(f"branch {current!r} hosts no topic — it is no exchange addressee")

    return candidates[0]


def _base_branch_names(base_ref: str, refs: list[BranchRef]) -> tuple[str, str]:
    """Split a base revision string into its local-branch and origin-twin names.

    The one spelling rule of the exchange — the branch-shape handling,
    the rollback capture, and the checked-out-base guard of every
    exchange operation spell a base through this helper. An
    ``origin/``-prefixed base contributes its short form as the local
    name and itself as the twin; every other base keeps its name
    locally and spells its twin under ``origin/``.

    Args:
        base_ref: The base revision string as addressed.
        refs: The branch inventory of the moment — a name it carries as
            a local branch is a local spelling even when it starts with
            ``origin/``, so the inventory breaks the one ambiguous
            prefix.

    Returns:
        The ``(local, twin)`` name pair — the local branch name and its
        origin remote-tracking twin, existing or not.
    """
    if base_ref.startswith("origin/") and not _has_local_branch(refs, base_ref):
        return _short_name(base_ref), base_ref

    return base_ref, f"origin/{base_ref}"


def _has_local_branch(refs: list[BranchRef], name: str) -> bool:
    """Report whether the inventory carries a local branch by name.

    Args:
        refs: The branch inventory.
        name: The local branch name.

    Returns:
        ``True`` when a non-remote ref of the inventory carries the
        name — the existence half of the branch-shape detection.
    """
    return any(not ref.remote and ref.name == name for ref in refs)


def _has_remote_ref(refs: list[BranchRef], name: str) -> bool:
    """Report whether the inventory carries a remote-tracking ref by name.

    Args:
        refs: The branch inventory.
        name: The remote-tracking ref display name.

    Returns:
        ``True`` when a remote ref of the inventory carries the name —
        the existence half of the branch-shape detection.
    """
    return any(ref.remote and ref.name == name for ref in refs)


def _projection(ref_name: str) -> str | None:
    """Resolve one base side as it stands after the fetch.

    Args:
        ref_name: The local branch or twin name to resolve.

    Returns:
        The commit the name resolves to, or ``None`` when it resolves
        to nothing — the fetch may have created the twin, and an absent
        side is a fact of the projection, never a failure.
    """
    try:
        return resolve_ref_commit(ref_name)
    except subprocess.CalledProcessError:
        return None


def _effective_tip(
    base_ref: str, local: str, local_tip: str | None, twin_tip: str | None, own_tip: str
) -> tuple[str, bool]:
    """Decide the effective tip of the projected pair — and write the reconciliation when needed.

    Args:
        base_ref: The base revision string as addressed — the name the
            reconciliation commit carries.
        local: The local branch name of the base — the reconciliation
            plant target.
        local_tip: The local projection, or ``None`` when the local
            branch is absent.
        twin_tip: The twin projection, or ``None`` when the twin is
            absent.
        own_tip: The topic's own branch tip — the already-carried
            oracle.

    Returns:
        The effective tip and the reconciliation marker — the written
        flag is ``True`` only for the reconciliation commit.

    Raises:
        click.ClickException: a diverged pair whose reconciliation
            conflicts — nothing was mutated.
    """
    if local_tip is None:
        return twin_tip, False
    if twin_tip is None:
        return local_tip, False

    if is_ancestor(local_tip, twin_tip):
        return twin_tip, False
    if is_ancestor(twin_tip, local_tip):
        return local_tip, False

    if is_ancestor(local_tip, own_tip) and is_ancestor(twin_tip, own_tip):
        # The already-carried state — the check precedes the write, so
        # an up-to-date topic mutates nothing at all.
        return own_tip, False

    tree = merge_tree(local_tip, twin_tip)

    if tree is None:
        raise click.ClickException(
            f"base {base_ref!r} diverged with its origin twin and the reconciliation conflicts — "
            "reconcile it manually with git, then retry"
        )

    commit = create_commit_from_tree(tree, [local_tip, twin_tip], _RECONCILE_MESSAGE.format(name=base_ref))
    point_branch_at_commit(local, commit)

    return commit, True
