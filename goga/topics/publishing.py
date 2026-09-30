"""The fast creation-and-publication of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: publishing.py``: the fast cycle that creates fresh work and
publishes it in one go — a branch off an explicit base carrying exactly one
commit with the topic todo file, pushed to origin, while the caller stays
on their branch — and the delivery of an existing topic branch to origin
as an operation of its own, with its pure four-outcome classification.
Every decision of the fast cycle is made before the first mutation; every
conflict of the decision chain is one clean error — there is no re-ask;
the mutation sequence is the quarantined commit build, the branch plant,
and the push, and a failed publication rolls back fully — the planted
branch is deleted and nothing else was ever mutated. After the successful push
the routine emits the publication pair — the creation and the
publication notifications over the nested hooks zone, with the applied
commit message and the captured commit hash; a rolled-back publication
fires nothing, and the creation amendment belongs to the creating
orchestration. The delivery operation publishes a topic's own branch as
it stands — one targeted fetch of its origin twin, the four-outcome
resolution over the own-twin pair, one push only when the twin is
absent, and the publication notification on every success, the
idempotent outcomes included; it never rewrites history and never
touches a local ref. The commit message default lives here as the
built-in domain template, and every authored message composes through
the shared template engine of the exchange module — the ``{slug}`` and
``{base}`` placeholders. The quarantined
commit build and the branch plant also serve the no-switch creation of
``creation`` through the shared plant helper. The occupancy oracles
belong to ``creation``; the bounded git mutations to the nested git cell;
the lifecycle checkpoints to the nested hooks zone.
Git infrastructure failures surface as ``click.ClickException`` — the
clean-error boundary of the domain.
"""

from __future__ import annotations

import contextlib
import subprocess

import click

from ..history import (
    current_year,
    normalize_topic_slug,
    resolve_current_branch_name,
    resolve_topic_file,
)
from .creation import _BOARD_HINT, check_branch_occupancy, check_slug_occupancy
from .exchange import _FETCHING_LINE, _projection, render_commit_template, resolve_exchange_target
from .git import (
    commit_file_on_base,
    create_branch_at_commit,
    delete_local_branch,
    fetch_branch,
    is_ancestor,
    origin_configured,
    push_branch,
    resolve_commit_message,
    resolve_ref_commit,
)
from .hooks import TopicHooks, TopicIdentity

# The built-in commit message template of the fast path — rendered through
# the shared template engine with the ``{slug}`` and ``{base}``
# placeholders. The domain owns the default, so every caller (the CLI
# flags, the configuration section) may omit the template.
_DEFAULT_COMMIT_MESSAGE = "Create topic '{slug}'"

# The result-line template of the delivery operation — the year, the slug,
# and the outcome kind of the completed publication; exactly one line, the
# outcome kind always named.
_PUBLISH_RESULT_LINE = "Published topic {year}/{slug} — {outcome}"


def publish_topic(
    branch_name: str,
    todo: str,
    base_ref: str,
    commit_message: str | None = None,
    year: str | None = None,
) -> str:
    """Create fresh work and publish it.

    A branch off an explicit base carrying one commit with the topic todo,
    pushed to origin, while the caller stays on their branch.

    Args:
        branch_name: Branch name as entered by the user.
        todo: The multi-line todo of the fresh work — written to the topic
            todo file todo.md as entered plus a single trailing newline
            (exactly one — a todo already ending in a newline keeps it);
            required and non-empty, an empty todo is a clean error asking
            for it.
        base_ref: Base revision the branch starts from — any revision
            string, resolved as git resolves it.
        commit_message: Commit message template — the ``{slug}`` and
            ``{base}`` placeholders are replaced through
            ``render_commit_template`` (unknown placeholders verbatim);
            ``None`` applies the built-in default
            ``Create topic '{slug}'``.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        One line describing the created and published work.

    Algorithm:
        1. Normalize ``branch_name`` into a slug — an empty slug is one
           clean error, before any mutation
        2. An empty todo, or the current branch hosting the same slug ->
           clean error, before any mutation
        3. The occupancy oracles ``check_branch_occupancy`` then
           ``check_slug_occupancy`` report a conflict -> clean error with
           a hint to the board
        4. ``origin_configured`` reads False -> clean error with the
           reason
        5. Resolve ``base_ref`` into its commit via ``resolve_ref_commit``
           — an unresolvable base is a clean error with the reason, before
           any mutation
        6. Build the publication commit via ``_plant_topic_branch`` — one
           quarantined commit carrying ``todo.md`` on the base commit with
           the applied commit message — and capture the returned commit
           hash
        7. Publish via ``push_branch``; a failed publication deletes the
           planted branch via ``delete_local_branch`` and surfaces one
           clean error carrying the reason — nothing fires on the failure
        8. After the successful push, emit over ``TopicHooks`` with the
           identity via ``TopicIdentity`` — the normalized slug, the
           resolved year, ``branch_name`` as entered: ``topic_created``
           (``checked_out`` False, ``published`` True, the final todo,
           the applied commit message, the captured commit hash), then
           ``topic_published`` — the origin twin that received the work,
           the built commit's hash and message, and the ``pushed``
           outcome
        9. Return the single result line

    Requirements:
        Every decision is made before the first mutation; the mutation
        sequence is the commit build, the branch plant, and the push.
        A failed publication rolls back fully — the planted branch is
        deleted and nothing else was ever mutated.
        The creation amendment belongs to the creating orchestration —
        this routine fires the publication checkpoints only; a direct
        call publishes without ``amend_creation``.
        The two publication checkpoints fire only after the push
        succeeds, in the order ``topic_created`` then
        ``topic_published``; a failed publication that rolls back fires
        nothing.

    Raises:
        click.ClickException: an empty slug, an empty todo, the current
            branch already hosting the slug, an occupancy conflict, a
            missing origin remote, a git infrastructure failure (its
            stderr when git reports one, or a missing git binary), or the
            fatal ``ImportError`` of the hooks-registry assembly.
    """
    try:
        return _publish_topic(branch_name, todo, base_ref, commit_message, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        # The publication checkpoints build the run registry on first
        # delivery — a broken ``goga_tool_*`` package is the platform's
        # single fatal case and surfaces here as one clean error, the
        # ``switch_topic`` and ``ensure_topic`` boundary.
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        # An OS-level failure can strike at any phase — the quarantined
        # chain creating or removing its temporary index under ``.git``, or a
        # git invocation failing to spawn — so the message stays
        # phase-neutral; it surfaces here as one clean error instead of a
        # raw traceback, mirroring ``create_topic``.
        raise click.ClickException(f"cannot complete the publication: {exc}") from exc


def _publish_topic(
    branch_name: str,
    todo: str,
    base_ref: str,
    commit_message: str | None,
    year: str | None,
) -> str:
    """Run the traced fast cycle — the unwrapped orchestration.

    Args:
        branch_name: Branch name as entered by the user.
        todo: The multi-line todo of the fresh work as entered by the user.
        base_ref: Base revision the branch starts from.
        commit_message: Commit message template with ``{slug}`` optional;
            ``None`` applies the built-in default.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The single result line of the outcome.
    """
    resolved_year = year or current_year()

    slug = normalize_topic_slug(branch_name)
    if slug == "":
        raise click.ClickException(f"branch name '{branch_name}' normalizes to an empty topic slug")

    if not todo:
        raise click.ClickException("the fast path needs a non-empty todo — pass the text or enter it interactively")

    current = resolve_current_branch_name()
    if current is not None and normalize_topic_slug(current) == slug:
        raise click.ClickException(
            f"branch {current} already hosts topic {resolved_year}/{slug} — the fast path is only for fresh work"
        )

    conflict = check_branch_occupancy(branch_name, slug, resolved_year)
    if conflict is None:
        conflict = check_slug_occupancy(slug, resolved_year)
    if conflict is not None:
        raise click.ClickException(f"{conflict} — {_BOARD_HINT}")

    if not origin_configured():
        raise click.ClickException("origin is not configured — the fast mode publishes to origin")

    base_commit = resolve_ref_commit(base_ref)

    # The applied message is composed once — through the shared template
    # engine, both placeholders substituted with the base as addressed —
    # so the commit and both notifications carry one value; the plant
    # helper's own render is a no-op on the applied text. A direct call
    # keeps its ``is not None`` predicate: only ``None`` takes the
    # built-in default (the delegated creation normalizes an empty
    # template itself).
    applied = render_commit_template(
        commit_message if commit_message is not None else _DEFAULT_COMMIT_MESSAGE,
        slug,
        base_ref,
    )
    commit = _plant_topic_branch(branch_name, todo, base_commit, base_ref, slug, resolved_year, applied)

    try:
        push_branch(branch_name)
    except (subprocess.CalledProcessError, OSError):
        # Full rollback before the one clean error — a git failure and a
        # spawn-level OS failure of the push alike leave nothing of this
        # cycle behind. A failure of the rollback itself is suppressed so
        # the original push reason surfaces; a branch left behind stays
        # visible on the board. Nothing fires on the failure — a
        # rolled-back publication leaves no event trail.
        with contextlib.suppress(subprocess.CalledProcessError, OSError):
            delete_local_branch(branch_name)
        raise

    # The publication pair fires only after the successful push, in the
    # fixed order, with the identical final facts — the identity from the
    # operation's own data; no repository reads at a checkpoint.
    identity = TopicIdentity(slug=slug, year=resolved_year, branch=branch_name)
    hooks = TopicHooks()
    hooks.emit_created(
        identity,
        checked_out=False,
        published=True,
        todo=todo,
        commit_message=applied,
        commit_hash=commit,
    )
    hooks.emit_published(
        identity,
        remote_branch=f"origin/{branch_name}",
        commit_hash=commit,
        commit_message=applied,
        outcome="pushed",
    )

    return f"Created branch {branch_name} and published topic {resolved_year}/{slug}"


def _plant_topic_branch(  # noqa: PLR0913, PLR0917 — the shared plant step of the two commit-building paths
    branch_name: str,
    todo: str,
    base_commit: str,
    base_ref: str,
    slug: str,
    resolved_year: str,
    commit_message: str | None,
) -> str:
    """Plant the branch at one quarantined commit carrying the topic todo file.

    The shared step of the two commit-building paths — the fast
    publication and the no-switch creation of ``creation``: the commit is
    built through quarantined git plumbing over ``base_commit`` and the
    branch is planted at it, without touching the working copy, the index,
    or HEAD.

    Args:
        branch_name: Branch name as entered by the user.
        todo: The todo text as entered by the user.
        base_commit: The parent commit hash the commit is built on.
        base_ref: The base revision as addressed — the ``{base}``
            placeholder value, the name every other render site
            substitutes.
        slug: The normalized topic slug — the topic directory of the todo
            file and the ``{slug}`` placeholder value.
        resolved_year: Year as four digits — the topic directory segment.
        commit_message: Commit message template — the ``{slug}`` and
            ``{base}`` placeholders are replaced through
            ``render_commit_template`` (unknown placeholders verbatim);
            ``None`` applies the built-in default
            ``Create topic '{slug}'``.

    Returns:
        The hash of the built commit the branch was planted at.

    Raises:
        subprocess.CalledProcessError: a git infrastructure failure of the
            chain itself (propagated raw — the caller wraps it).
        OSError: unexpected OS-level failures of the chain (e.g. a missing
            git binary or a quarantined-index failure under ``.git``).
    """
    # The single-trailing-newline rule: an editor-sourced todo already ends
    # with a newline (click's read-back), so an unconditional append would
    # publish a blank trailing line; a bare value gains exactly one.
    content = todo if todo.endswith("\n") else todo + "\n"
    message = commit_message if commit_message is not None else _DEFAULT_COMMIT_MESSAGE
    path = resolve_topic_file(slug, "todo.md", resolved_year).as_posix()
    # The render is the shared-engine formality: both callers hand the
    # already-applied text (a no-op here), and the D3 fallback of a nulled
    # message applies the built-in default — the only raw template that
    # ever reaches this call.
    commit = commit_file_on_base(
        base_commit,
        path,
        content,
        render_commit_template(message, slug, base_ref),
    )

    create_branch_at_commit(branch_name, commit)
    return commit


def publish_existing_topic(identifier: str | None, year: str | None = None) -> str:
    """Deliver an existing topic branch to origin.

    The publication of a topic's own branch as an operation of its own —
    creating fresh work is not part of it.

    Args:
        identifier: The addressee input — a branch name, a topic slug,
            or their prefix; ``None`` addresses the current topic.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        One line naming the outcome kind.

    Algorithm:
        1. Resolve the addressee via ``resolve_exchange_target``
        2. ``origin_configured`` reads False -> clean error before any
           network operation
        3. Resolve the own tip via ``resolve_ref_commit``
        4. Echo one stdout line ``Fetching origin/<branch>...`` then
           ``fetch_branch`` of the own branch; the twin projection after
           the fetch — an absent twin reads as ``None``
        5. Classify the pair via ``resolve_publication_outcome``
        6. pushed -> ``push_branch`` of the own branch — the twin is
           created
        7. up-to-date and remote-ahead -> success with nothing to do and
           nothing mutated
        8. Read the publication facts of the twin tip via
           ``resolve_commit_message``
        9. Emit ``topic_published`` over ``TopicHooks`` with the
           identity via ``TopicIdentity`` — the slug, the resolved year,
           the branch as entered — the remote branch
           ``origin/<branch>``, the commit facts, and the outcome kind;
           every success emits, the idempotent outcomes included
        10. Return the single result line naming the outcome kind

    Requirements:
        Delivery, never history rewriting — no force and no lease under
        any outcome.
        No confirmation is asked; the working-tree state is irrelevant
        to the push.
        The result is exactly one line and names the outcome kind.

    Constraints:
        Do not move, create, or delete any local ref — the branch itself
        stays untouched.
        Do not push anything but the topic's own branch.

    Raises:
        click.ClickException: a missing origin remote, a diverged origin
            twin, or a git infrastructure failure (its stderr when git
            reports one, or a missing git binary), or the fatal
            ``ImportError`` of the hooks-registry assembly.
    """
    try:
        return _publish_existing_topic(identifier, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        # The publication notification builds the run registry on first
        # delivery — a broken ``goga_tool_*`` package is the platform's
        # single fatal case and surfaces here as one clean error, the
        # ``publish_topic`` boundary verbatim.
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        # An OS-level failure can strike at any phase — a git invocation
        # failing to spawn or the commit-message read failing — so the
        # message stays phase-neutral; it surfaces here as one clean
        # error instead of a raw traceback, mirroring ``publish_topic``.
        raise click.ClickException(f"cannot complete the publication: {exc}") from exc


def _publish_existing_topic(identifier: str | None, year: str | None) -> str:
    """Run the traced delivery — the unwrapped orchestration.

    Args:
        identifier: The addressee input; ``None`` addresses the current
            topic.
        year: Optional year as four digits; ``None`` means the current
            year.

    Returns:
        The single result line of the outcome.
    """
    resolved_year = year or current_year()

    target = resolve_exchange_target(identifier, year)
    if not origin_configured():
        raise click.ClickException("origin is not configured — publishing delivers to origin")

    own_tip = resolve_ref_commit(target.branch)

    # The single sanctioned fetch of the own branch, reported by one
    # stdout line before it runs — the reporting line belongs to the
    # caller. The twin projection after the fetch reads an absent twin
    # as None — the fetch of a missing remote ref is not a failure.
    click.echo(_FETCHING_LINE.format(branch=target.branch))
    fetch_branch(target.branch)
    twin_tip = _projection(f"origin/{target.branch}")

    outcome = resolve_publication_outcome(own_tip, twin_tip)
    if outcome == "pushed":
        push_branch(target.branch)

    # The publication facts are read after the operation: the twin tip
    # as it stands now — the push's upstream binding leaves the
    # remote-tracking ref current without network — and the commit
    # message of that tip as git stores it.
    twin = _projection(f"origin/{target.branch}")
    message = resolve_commit_message(twin)

    identity = TopicIdentity(slug=target.topic, year=resolved_year, branch=target.branch)
    TopicHooks().emit_published(
        identity,
        remote_branch=f"origin/{target.branch}",
        commit_hash=twin,
        commit_message=message,
        outcome=outcome,
    )

    return _PUBLISH_RESULT_LINE.format(year=resolved_year, slug=target.topic, outcome=outcome)


def resolve_publication_outcome(own_tip: str, twin_tip: str | None) -> str:
    """Classify the own-twin pair into the publication outcome.

    The pure decision of the publication operation — no repository
    access, no mutation, no network; only the containment probe touches
    git, read-only.

    Args:
        own_tip: The tip commit of the topic's own branch.
        twin_tip: The tip commit of the origin twin as it exists after
            the fetch; ``None`` when the twin is absent.

    Returns:
        The outcome kind — pushed, up-to-date, or remote-ahead.

    Algorithm:
        1. ``twin_tip`` ``None`` -> pushed — the push creates the twin
        2. ``twin_tip`` equals ``own_tip`` -> up-to-date — the twin
           already carries the tip, nothing to do
        3. ``own_tip`` contained in ``twin_tip`` via ``is_ancestor`` ->
           remote-ahead — the remote strictly carries the local work
        4. Otherwise a clean error naming both tips; reconciliation is
           manual git, then a re-run

    Requirements:
        Read-only — containment probes via ``is_ancestor`` only; no
        mutation and no network.
        The equality probe precedes the containment probes.

    Constraints:
        Do not reconcile — divergence is surfaced to the caller.

    Raises:
        click.ClickException: a diverged own-twin pair — both tips named
            with the manual-git hint.
    """
    if twin_tip is None:
        return "pushed"
    if twin_tip == own_tip:
        return "up-to-date"
    if is_ancestor(own_tip, twin_tip):
        return "remote-ahead"
    raise click.ClickException(
        f"branch and origin twin diverged — own tip {own_tip}, twin tip {twin_tip}; "
        "reconcile manually with git, then re-run"
    )
