"""The ensure orchestration of the topics domain.

The entity declared in the cell CODEMANIFEST with
``location: ensuring.py``: the combined orchestrator that brings the
repository onto the requested work — by switching when a branch hosts the
identifier, by the fast creation from the current HEAD when nothing does;
with the todo flag the todo entry of the ensured work runs after the
switch or the creation. The resolution and the switch orchestration belong
to the switching module; the occupancy oracles and the todo entry belong
to the creation module; the topic-directory creation belongs to the
history facade; the bounded git mutation belongs to the nested git cell.
Git infrastructure failures and the fatal scale-assembly ``ImportError``
surface as ``click.ClickException`` — the clean-error boundary of the
domain; the interactive moments follow the ``click`` practice.
"""

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
    check_branch_occupancy,
    check_slug_occupancy,
    enter_topic_todo,
)
from .git import create_and_switch_branch
from .switching import SwitchCandidate, resolve_switch_candidates, switch_topic


def ensure_topic(identifier: str, todo: bool = False, year: str | None = None) -> str:
    """Bring the repository onto the requested work, creating it when nothing
    hosts the identifier; with the todo flag, enter the todo of the work
    after the switch or the creation.

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
           slug guard and the occupancy oracles are clean errors, then the
           branch named as entered is created and switched to via
           ``create_and_switch_branch``, the topic directory of the year is
           created via ``ensure_topic_dir``, and with ``todo`` the todo of
           the fresh topic is entered — the entry starts only after the
           switch
        4. Otherwise -> the switch orchestration via ``switch_topic``
           without the entry; with ``todo`` the hosted topic comes from the
           step-2 resolution candidate whose branch is the current branch
           read via ``resolve_current_branch_name`` (a remote-tracking
           candidate matches by its short name): a hosted topic is entered
           via ``enter_topic_todo``; a hosting branch without one gets its
           topic directory created via ``ensure_topic_dir`` — an empty slug
           of its name is a clean error — then the fresh entry
        5. Return the single result line

    Requirements:
        Creation happens only at zero candidates — a resolvable identifier
        never creates anything.
        The creation always starts from the current HEAD — the
        configuration base is never read here.
        With ``todo``, no step follows the todo write.
        Every mutation is local — no network, no fetch, no push.
        The result is exactly one line.

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

    The branch keeps the name as entered and starts at git's default start
    point (the current HEAD); the topic directory takes the normalized
    slug. The decisions — the slug guard and the occupancy oracles —
    precede the first mutation; the todo entry starts only after the
    switch.

    Args:
        identifier: The user input as entered — becomes the branch name.
        todo: ``True`` enters the todo of the fresh topic after the switch.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The creation line — the branch as entered and the topic of the
        normalized slug.
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

    create_and_switch_branch(identifier)
    ensure_topic_dir(identifier, year)
    if todo:
        enter_topic_todo(identifier, year)

    return f"Created branch {identifier} and topic {resolved_year}/{slug}"


def _enter_switched_todo(candidates: list[SwitchCandidate], year: str | None) -> None:
    """Enter the todo of the switched work — the post-switch todo path.

    The hosted topic comes from the step-2 resolution candidate whose
    branch is the current branch, never from the normalized current-branch
    name: a topic merged into another branch is entered as itself, and no
    directory of the hosting branch's name is created. A hosting branch
    without a topic gets its topic directory created first — the fresh
    entry needs a place to land — unless its name normalizes to an empty
    slug, which is a clean error (the history facade's ``ValueError`` on
    an empty slug never escapes the module).

    Args:
        candidates: The step-2 resolution candidates — the topic lookup
            never depends on which candidate the switch chose.
        year: Optional year as four digits; ``None`` means the current year.
    """
    current = resolve_current_branch_name()

    topic = _hosted_topic_of_current(candidates, current)

    if topic is not None:
        enter_topic_todo(topic, year)
        return

    if current is None or normalize_topic_slug(current) == "":
        raise click.ClickException(f"branch name '{current}' normalizes to an empty topic slug")

    ensure_topic_dir(current, year)
    enter_topic_todo(current, year)


def _hosted_topic_of_current(candidates: list[SwitchCandidate], current: str | None) -> str | None:
    """Find the hosted topic of the current branch among the candidates.

    A local candidate matches by its full branch name; a remote-tracking
    candidate matches by its short name — the local branch the switch
    created from it. The first candidate of the resolution order wins: a
    branch hosting several topics contributes its first entry, the same
    choice the switch orchestration's own todo path makes.

    Args:
        candidates: The step-2 resolution candidates.
        current: The current branch name, or ``None`` when there is none.

    Returns:
        The hosted topic slug of the matching candidate, or ``None`` when
        the current branch hosts none of the candidates.
    """
    for candidate in candidates:
        hosted_by = _short_name(candidate.branch) if candidate.remote else candidate.branch
        if hosted_by == current:
            return candidate.topic

    return None
