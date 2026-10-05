"""The ensure orchestration of the topics domain."""

from __future__ import annotations

import subprocess
import sys

import click

from ..history import (
    current_year,
    ensure_topic_dir,
    normalize_topic_slug,
    resolve_current_branch_name,
)
from .board import _short_name
from .creation import (
    _BOARD_HINT,
    _enter_topic_todo,
    check_branch_occupancy,
    check_slug_occupancy,
    enter_topic_todo,
)
from .git import create_and_switch_branch
from .hooks import TopicHooks, TopicIdentity
from .switching import SwitchCandidate, resolve_switch_candidates, switch_topic


def ensure_topic(identifier: str, todo: bool = False, year: str | None = None) -> str:
    """Bring the repository onto the requested work, creating it when nothing hosts the identifier.

    Args:
        identifier: The user input — a branch name, a topic slug, or their
            prefix.
        todo: ``True`` enters the todo of the ensured work.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        One line describing the outcome — the switch line of the delegated
        switch orchestration or the creation line of the fast creation.

    Algorithm:
        1. ``todo`` without an interactive terminal -> clean error before
           any action
        2. Resolve the candidates via ``resolve_switch_candidates``
        3. No candidate -> the fast creation from the current HEAD: the
           slug guard and the occupancy oracles are clean errors; the
           creation amendment is delivered over ``TopicHooks`` with the
           identity via ``TopicIdentity`` — the normalized slug, the
           resolved year, the branch name as entered — ``checked_out``
           True, ``published`` False, no draft commit message (the path
           builds no commit), and no draft todo (the todo resolves later
           through the entry); the branch named as entered is created and
           switched to via ``create_and_switch_branch``, the topic
           directory of the year is created via ``ensure_topic_dir``, and
           with ``todo`` the todo of the fresh topic is entered via the
           private mirror ``_enter_topic_todo``, passing the branch name
           as the branch fact — the entry starts only after the switch;
           after the creation completes, ``topic_created`` is emitted over
           ``TopicHooks`` — the identity, ``checked_out`` True,
           ``published`` False, the final todo when the entry resolved
           one, and no commit facts
        4. Otherwise -> the switch orchestration via ``switch_topic``
           without the entry — the switch notification fires inside it;
           with ``todo`` the hosted topic comes from the step-2 resolution
           candidate whose branch is the current branch read via
           ``resolve_current_branch_name`` (a remote-tracking candidate
           matches by its short name): a hosted topic is entered via
           ``enter_topic_todo`` with the branch fact; a hosting branch
           without one gets its topic directory created via
           ``ensure_topic_dir`` — an empty slug of its name is a clean
           error — then the fresh entry via ``enter_topic_todo`` with the
           derived identity and the branch fact; no creation checkpoint
           fires for the directory creation
        5. Return the single result line

    Requirements:
        Creation happens only at zero candidates — a resolvable identifier
        never creates anything.
        The creation always starts from the current HEAD — the
        configuration base is never read here.
        With ``todo``, no step follows the todo write.
        Every mutation is local — no network, no fetch, no push.
        The result is exactly one line.
        The fast creation delivers the creation amendment exactly once,
        immediately before its first mutation — the identity-only form is
        the norm on this path: the returned holder stays unread, an
        amended todo does not land there (the entry's own todo-entry
        amendment owns the written text) — and emits ``topic_created``
        after the creation completes.
        The todo entries pass the operation's branch fact — the identifier
        of the fast creation, the current branch of the switched work.

    Constraints:
        Do not ask about publication — the fast process publishes nothing.
        Do not manage the stages of the hosting pipeline — continuation
        belongs to the pipeline itself.

    Raises:
        click.ClickException: ``todo`` without an interactive terminal, an
            unusable (empty-slug) or occupied name of the fast creation,
            several candidates without an interactive terminal, a dirty
            working tree on a switch mutation, a git infrastructure failure
            (its stderr when git reports one, or a missing git binary), an
            OS failure of the topic-directory creation or the todo write,
            or the fatal ``ImportError`` of the scale assembly.
        click.Abort: Ctrl-C or EOF at a selection prompt — the repository
            is left untouched.
    """
    try:
        return _ensure_topic(identifier, todo, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc
    except OSError as exc:
        # ``ensure_topic_dir`` propagates the mkdir failures — the same
        # boundary ``create_topic`` keeps for its directory creation and
        # todo write, so the pipeline-driven path pierces no further than
        # the CLI one (``FileNotFoundError``, an ``OSError`` subclass, is
        # handled above as the missing git binary).
        raise click.ClickException(f"cannot create the topic directory or write the todo file: {exc}") from exc


def _ensure_topic(identifier: str, todo: bool, year: str | None) -> str:
    """Run the traced ensure procedure — the unwrapped orchestration.

    Args:
        identifier: The user input as entered.
        todo: ``True`` enters the todo of the ensured work.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The single result line of the outcome.

    Raises:
        click.ClickException: ``todo`` without an interactive terminal, or
            any clean error of the delegated creation or switch.
    """
    if todo and not sys.stdin.isatty():
        raise click.ClickException("the todo entry needs an interactive terminal")

    candidates = resolve_switch_candidates(identifier, year)

    if not candidates:
        return _create_fresh_work(identifier, todo, year)

    line = switch_topic(identifier, todo=False, year=year)

    if todo:
        _enter_switched_todo(candidates, year)

    return line


def _create_fresh_work(identifier: str, todo: bool, year: str | None) -> str:
    """Create the fresh work off the current HEAD — the zero-candidate path.

    Args:
        identifier: The user input as entered — becomes the branch name.
        todo: ``True`` enters the todo of the fresh topic after the switch.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The creation line — the branch as entered and the topic of the
        normalized slug.

    Raises:
        click.ClickException: an empty-normalizing name or an occupancy
            conflict.
    """
    resolved_year = year or current_year()

    slug = normalize_topic_slug(identifier)
    if slug == "":
        raise click.ClickException(f"branch name '{identifier}' normalizes to an empty topic slug")

    conflict = check_branch_occupancy(identifier, slug, year)
    if conflict is None:
        conflict = check_slug_occupancy(slug, year)
    if conflict is not None:
        raise click.ClickException(f"{conflict} — {_BOARD_HINT}")

    # The creation amendment — the identity-only form, delivered exactly
    # once immediately before the branch creation (the first mutation).
    # The returned holder stays unread on purpose: an amended todo does
    # not land on this path (the entry's own todo-entry amendment owns the
    # written text), and the path builds no commit — nothing to amend.
    identity = TopicIdentity(slug=slug, year=resolved_year, branch=identifier)
    TopicHooks().amend_creation(
        identity,
        checked_out=True,
        published=False,
        commit_message=None,
        todo=None,
    )

    create_and_switch_branch(identifier)
    ensure_topic_dir(identifier, year)

    final_todo = _enter_topic_todo(identifier, year, branch=identifier) if todo else None

    # The creation notification fires after the creation completes — after
    # the entry, so the final todo it reports is the written one; the path
    # builds no commit, so no commit fact is carried.
    TopicHooks().emit_created(
        identity,
        checked_out=True,
        published=False,
        todo=final_todo,
        commit_message=None,
        commit_hash=None,
    )

    return f"Created branch {identifier} and topic {resolved_year}/{slug}"


def _enter_switched_todo(candidates: list[SwitchCandidate], year: str | None) -> None:
    """Enter the todo of the switched work — the post-switch todo path.

    Args:
        candidates: The step-2 resolution candidates — the hosted topic
            comes from the candidate whose branch is the current branch,
            never from the normalized current-branch name: a topic merged
            into another branch is entered as itself.
        year: Optional year as four digits; ``None`` means the current year.

    Raises:
        click.ClickException: a hosting branch without a topic whose name
            normalizes to an empty slug — no directory can be created.
    """
    current = resolve_current_branch_name()

    topic = _hosted_topic_of_current(candidates, current)

    if topic is not None:
        enter_topic_todo(topic, year, branch=current)
        return

    if current is None or normalize_topic_slug(current) == "":
        raise click.ClickException(f"branch name '{current}' normalizes to an empty topic slug")

    ensure_topic_dir(current, year)
    enter_topic_todo(current, year, branch=current)


def _hosted_topic_of_current(candidates: list[SwitchCandidate], current: str | None) -> str | None:
    """Find the hosted topic of the current branch among the candidates.

    Args:
        candidates: The step-2 resolution candidates.
        current: The current branch name, or ``None`` when there is none.

    Returns:
        The hosted topic slug of the first candidate matching the current
        branch — a local candidate by its full branch name, a
        remote-tracking one by its short name — or ``None`` when the
        current branch hosts none of the candidates.
    """
    for candidate in candidates:
        hosted_by = _short_name(candidate.branch) if candidate.remote else candidate.branch
        if hosted_by == current:
            return candidate.topic

    return None
