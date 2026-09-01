"""The fast creation-and-publication of the topics domain.

The entity declared in the cell CODEMANIFEST with
``location: publishing.py``: the fast cycle that creates fresh work and
publishes it in one go — a branch off an explicit base carrying exactly one
commit with the topic todo file, pushed to origin, while the caller stays
on their branch. Every decision is made before the first mutation; the
mutation sequence is the quarantined commit build, the branch plant, and
the push, and a failed publication rolls back fully — the planted branch
is deleted and nothing else was ever mutated. The occupancy oracles and the
re-ask machinery belong to ``creation``; the bounded git mutations to the
nested git cell. Git infrastructure failures surface as
``click.ClickException`` — the clean-error boundary of the domain.
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
from .creation import _BOARD_HINT, _reask, check_branch_occupancy, check_slug_occupancy
from .git import (
    commit_file_on_base,
    create_branch_at_commit,
    delete_local_branch,
    origin_configured,
    push_branch,
    resolve_ref_commit,
)


def publish_topic(
    branch_name: str,
    todo: str,
    base_ref: str,
    commit_message: str,
    year: str | None = None,
) -> str:
    """Create fresh work and publish it — a branch off an explicit base
    carrying one commit with the topic todo, pushed to origin, while the
    caller stays on their branch.

    Args:
        branch_name: Branch name as entered by the user.
        todo: The multi-line todo of the fresh work — written to the topic
            todo file todo.md as entered plus a single trailing newline;
            required and non-empty, an empty todo is a clean error asking
            for it.
        base_ref: Base revision the branch starts from — any revision
            string, resolved as git resolves it.
        commit_message: Commit message template — the ``{slug}``
            placeholder is replaced with the topic slug; a template
            without the placeholder is used as is.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        One line describing the created and published work.

    Raises:
        click.ClickException: an empty todo, the current branch already
            hosting the slug, a missing origin remote, an unresolved
            occupancy conflict without a terminal, a git infrastructure
            failure (its stderr when git reports one, or a missing git
            binary).
        click.Abort: Ctrl-C or EOF at the re-ask prompt — nothing was
            mutated.
    """
    try:
        return _publish_topic(branch_name, todo, base_ref, commit_message, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
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
    commit_message: str,
    year: str | None,
) -> str:
    """Run the traced fast cycle — the unwrapped orchestration.

    Args:
        branch_name: Branch name as entered by the user.
        todo: The multi-line todo of the fresh work as entered by the user.
        base_ref: Base revision the branch starts from.
        commit_message: Commit message template with ``{slug}`` optional.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The single result line of the outcome.
    """
    resolved_year = year or current_year()

    while True:
        slug = normalize_topic_slug(branch_name)

        if slug == "":
            reason = f"branch name '{branch_name}' normalizes to an empty topic slug"
            branch_name = _reask(reason)
            continue

        if not todo:
            raise click.ClickException(
                "the fast path needs a non-empty todo"
                " — pass the text or enter it interactively"
            )

        current = resolve_current_branch_name()
        if current is not None and normalize_topic_slug(current) == slug:
            raise click.ClickException(
                f"branch {current} already hosts topic {resolved_year}/{slug}"
                " — the fast path is only for fresh work"
            )

        conflict = check_branch_occupancy(branch_name, slug, resolved_year)
        if conflict is None:
            conflict = check_slug_occupancy(slug, resolved_year)
        if conflict is not None:
            branch_name = _reask(conflict, _BOARD_HINT)
            continue

        if not origin_configured():
            raise click.ClickException(
                "origin is not configured — the fast mode publishes to origin"
            )

        base_commit = resolve_ref_commit(base_ref)

        path = resolve_topic_file(slug, "todo.md", resolved_year).as_posix()
        commit = commit_file_on_base(
            base_commit,
            path,
            f"{todo}\n",
            commit_message.replace("{slug}", slug),
        )

        create_branch_at_commit(branch_name, commit)
        try:
            push_branch(branch_name)
        except (subprocess.CalledProcessError, OSError):
            # Full rollback before the one clean error — a git failure and a
            # spawn-level OS failure of the push alike leave nothing of this
            # cycle behind. A failure of the rollback itself is suppressed so
            # the original push reason surfaces; a branch left behind stays
            # visible on the board.
            with contextlib.suppress(subprocess.CalledProcessError, OSError):
                delete_local_branch(branch_name)
            raise

        return (
            f"Created branch {branch_name} and published topic {resolved_year}/{slug}"
        )
