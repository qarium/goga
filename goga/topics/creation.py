"""The fresh-work creation and the todo entry of the topics domain.

The entities declared in the cell CODEMANIFEST with
``location: creation.py``: the three-oracle occupancy check of a fresh-work
name, the branch-tree slug oracle that reads the topic directory of a slug
across every branch tree of the inventory — without checkout, so a topic
hosted only on a branch (or only on ``origin``) is visible — the
orchestrator that creates fresh work off an explicit base — the branch
named exactly as entered with its topic of the year: by default planted
at one quarantined commit carrying the topic todo file while the caller
stays on their branch, or — under the switch flag — planted at the base
commit and checked out together with its topic directory of the year and
its topic todo file in the working copy: a given value or the editor
session of the nested editor cell, every decision read-only before the
first input and the first mutation, every conflict one clean error, and
an optional publication ask that delegates to the fast cycle of the
publishing module — and the todo entry of a topic — the editor session
over the topic's todo.md and the write of the saved text, without a
commit. Topic identity and addressing belong to the history facade; the
bounded git mutation belongs to the nested git cell; the editor session
belongs to the nested editor cell. Git infrastructure failures surface
as ``click.ClickException`` — the clean-error boundary of the domain;
the interactive moments follow the ``click`` practice. The status scale
is never assembled here — creation is not a status consumer.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys

import click

from ..history import (
    current_year,
    ensure_topic_dir,
    normalize_topic_slug,
    resolve_current_branch_name,
    resolve_history_root,
    resolve_topic_file,
    topic_exists,
)
from .editor import edit_text
from .git import (
    checkout_local_branch,
    create_branch_at_commit,
    delete_local_branch,
    list_branch_refs,
    read_ref_tree_paths,
    resolve_ref_commit,
)

# The board hint of an occupancy conflict — where the occupied names are
# visible to the user.
_BOARD_HINT = "run 'goga topics board' to see the board"


def check_branch_occupancy(branch_name: str, slug: str, year: str | None = None) -> str | None:
    """Decide whether the entered branch name and the topic slug are free.

    Probes three oracles in order and returns the human-readable reason of
    the first occupied one; the remaining oracles are not probed:

    1. a local ``BranchRef`` of the inventory named exactly ``branch_name``;
    2. a remote-tracking ``BranchRef`` whose short name — the part after the
       first slash of its display name — equals ``branch_name`` (the local
       inventory only, no network);
    3. the topic directory of ``slug`` in the year via ``topic_exists`` —
       only a directory occupies a topic.

    The git oracles check the name as entered; the history oracle checks the
    slug — the two may deliberately differ (``Feature/Foo_Bar`` vs
    ``feature-foo-bar``).

    Args:
        branch_name: Branch name as entered (checked against the inventory).
        slug: Normalized topic slug (checked against the topic directory).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The human-readable reason of the first occupied oracle, or ``None``
        when everything is free.

    Constraints:
        Read-only — no ref or directory is created.
        Do not resolve remote state over the network — the local inventory
        only.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr when
            git reports one, or a missing git binary).
    """
    try:
        return _occupancy_conflict(branch_name, slug, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc


def check_slug_occupancy(slug: str, year: str | None = None) -> str | None:
    """Decide whether any branch of the inventory already hosts the topic directory of the slug.

    Reads the branch trees through ``read_ref_tree_paths`` — the local
    branches and the remote-tracking refs as they exist locally, without
    checkout — one ref at a time; the first ref whose tree carries paths
    under the topic directory prefix of the slug is the conflict. A topic
    hosted only on ``origin`` blocks the slug the same way a local one
    does; a topic living only in the working copy does not — that is the
    file oracle's domain.

    Args:
        slug: Normalized topic slug (checked across every branch tree).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The human-readable reason naming the hosting branch, or ``None``
        when no branch hosts the slug.

    Constraints:
        Read-only — no ref or directory is created; no checkout, no
        worktree.
        Do not resolve remote state over the network — the local inventory
        only.
        Do not probe the working copy — a topic living only on disk is the
        file oracle's domain.

    Raises:
        click.ClickException: a git infrastructure failure (its stderr when
            git reports one, or a missing git binary).
    """
    try:
        return _slug_conflict(slug, year)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc


def create_topic(  # noqa: PLR0913, PLR0917 — the CODEMANIFEST-declared signature
    branch_name: str,
    base_ref: str,
    todo: str | None = None,
    publish: bool = False,
    commit_message: str | None = None,
    year: str | None = None,
    switch: bool = False,
) -> str:
    """Create fresh work — a branch off an explicit base with the name as entered.

    The default path plants the branch at one quarantined commit carrying
    the topic todo file — the working copy, the index, and HEAD stay
    untouched and the caller stays on their branch; ``switch`` moves the
    repository onto the fresh branch instead, with the topic directory
    created in the working copy and the todo written uncommitted. The
    publication ask may hand the work to the fast publication cycle
    instead.

    Args:
        branch_name: Branch name as entered by the user.
        base_ref: Base revision the branch starts from — any revision
            string, resolved as git resolves it (``"HEAD"`` for the
            current commit).
        todo: Optional multi-line todo — a non-empty value is used as
            given; without a value an interactive terminal opens the
            editor entry (a cancelled session leaves no todo) and a
            non-interactive terminal is a clean error naming the value
            option. An empty string counts as no value.
        publish: ``True`` takes the publication path without the ask.
        commit_message: Commit message template of the publication;
            ``None`` applies the publication's own built-in default.
        year: Optional year as four digits; ``None`` means the current year.
        switch: ``True`` checks out the fresh branch after the creation —
            the topic directory and the todo land in the working copy,
            uncommitted, and the todo is optional; the default path plants
            the branch at a commit carrying ``todo.md`` and needs the
            todo.

    Returns:
        One line describing the outcome — the created work of the normal
        path or the created and published work of the fast cycle.

    Algorithm:
        1. Preflight — read-only, before any input: the empty-slug guard
           via ``normalize_topic_slug``, the current-branch conflict (the
           current branch already hosting the slug is a conflict — there
           is no idempotent path), the occupancy oracles
           ``check_branch_occupancy`` then ``check_slug_occupancy``, and
           the base resolution via ``resolve_ref_commit``
        2. Todo resolution — a non-empty value wins; without one an
           interactive terminal opens the editor session via
           ``edit_text`` (its cancellation leaves no todo), otherwise a
           clean error naming the value option
        3. ``publish`` without a resolved todo -> clean error asking for
           the todo
        4. Neither ``publish`` nor ``switch`` without a resolved todo ->
           clean error — the no-switch work exists only through its
           committed ``todo.md``
        5. The ask — an interactive terminal, ``publish`` not set, a todo
           resolved: ``click.confirm`` offers the publication (an empty
           answer reads the default no; Ctrl-C or EOF aborts); no ask
           otherwise
        6. The normal path — ``switch`` set: ``create_branch_at_commit``
           plants the branch at the base commit, ``checkout_local_branch``
           switches to it (a failed checkout rolls the plant back — the
           ``publish_topic`` precedent), ``ensure_topic_dir`` creates the
           topic directory of the year, and a resolved todo writes the
           todo file ``todo.md`` — the write is the last action of the
           path; ``switch`` unset: the quarantined plant of
           ``publishing`` — one commit carrying ``todo.md`` on the base
           commit, the branch planted at it, the caller stays on their
           branch
        7. The publication path — the fast cycle of ``publishing`` via a
           call-time import; the cycle re-runs its own preflight — the
           delegation is deliberately whole
        8. Return the single result line

    Requirements:
        Every decision — the preflight, the todo, the ask — precedes the
        first mutation; the read-only preflight precedes any input, so a
        failing base never wastes an entered todo.
        The branch keeps the name as entered; the topic directory takes the
        slug — the two may deliberately differ.
        The todo.md file carries the todo as entered plus a single trailing
        newline, encoded UTF-8 — empty lines inside the text stay as
        entered.
        The no-switch normal path builds its commit with the built-in
        domain message — ``commit_message`` stays publication-only.
        On the switch path the todo.md file is written only when a todo
        resolved, and the topic directory exists before the file is
        written.
        The caller stays on their branch unless ``switch`` is set.

    Constraints:
        Do not validate branch-name characters — git owns name validity.
        Do not re-ask a conflicted name — every conflict is one clean
        error.
        Do not write artifact files other than the topic todo file inside
        the topic directory.

    Raises:
        click.ClickException: an empty slug, the current branch hosting
            the slug, an occupancy conflict, an unresolvable base, no todo
            without a terminal, ``publish`` or the no-switch creation
            without a todo, or a git infrastructure failure (its stderr
            when git reports one, or a missing git binary).
        click.Abort: Ctrl-C or EOF at the publication ask.
    """
    try:
        return _create_topic(branch_name, base_ref, todo, publish, commit_message, year, switch)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or str(exc)
        raise click.ClickException(f"git failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise click.ClickException(f"git is not available: {exc}") from exc
    except OSError as exc:
        # ``ensure_topic_dir`` propagates the mkdir failures — a stray file
        # named like the slug occupies no topic for the oracle, so the
        # failure can only surface here, after the branch was created. The
        # todo write shares the boundary: one clean error for both. The
        # quarantined plant of the no-switch path raises its OS-level
        # failures here too — one clean error covers the whole path.
        raise click.ClickException(f"cannot create the topic directory or write the todo file: {exc}") from exc


def enter_topic_todo(topic: str, year: str | None = None) -> bool:
    """Enter the todo of a topic.

    The editor session with the topic's todo.md and the write of the saved
    text, without a commit.

    Args:
        topic: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        True when the saved text was written; False when the entry was
        cancelled.

    Algorithm:
        1. Resolve the todo.md path of the topic via ``resolve_topic_file``;
           an existing file provides the initial text
        2. Open the editor session via ``edit_text`` with the initial text
        3. A cancelled entry -> False — the file stays untouched
        4. The saved text -> write todo.md as entered plus a single
           trailing newline, encoded UTF-8, without a commit -> True

    Requirements:
        The write is the last action — nothing follows it.
        The topic directory exists — directory creation belongs to the
        caller.

    Constraints:
        Do not create the topic directory.
        Do not commit the write.

    Raises:
        click.ClickException: a failed editor session (the editor cell's
            own clean error), or a filesystem failure of the read or the
            write.
    """
    try:
        return _enter_topic_todo(topic, year)
    except OSError as exc:
        # The boundary covers the prefill read and the saved write alike.
        raise click.ClickException(f"cannot read or write the todo file: {exc}") from exc


def _occupancy_conflict(branch_name: str, slug: str, year: str | None) -> str | None:
    """Probe the three occupancy oracles — the traced algorithm, unwrapped.

    Args:
        branch_name: Branch name as entered (checked against the inventory).
        slug: Normalized topic slug (checked against the topic directory).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The reason of the first occupied oracle, or ``None``.
    """
    resolved_year = year or current_year()
    refs = list_branch_refs()

    if any(not ref.remote and ref.name == branch_name for ref in refs):
        return f"branch '{branch_name}' already exists"
    if any(ref.remote and ref.name.partition("/")[2] == branch_name for ref in refs):
        return f"remote-tracking branch '{branch_name}' already exists"

    if topic_exists(slug, resolved_year):
        return f"history topic '{slug}' already exists for {resolved_year}"

    return None


def _slug_conflict(slug: str, year: str | None) -> str | None:
    """Probe the branch-tree slug oracle — the traced algorithm, unwrapped.

    Args:
        slug: Normalized topic slug (checked across every branch tree).
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        The reason naming the first hosting branch, or ``None``.
    """
    resolved_year = year or current_year()
    # The trailing slash is load-bearing: it keeps a sibling slug that only
    # shares the prefix text ("feature-foo-bar" of "feature-foo") free.
    prefix = f"{resolve_history_root().as_posix()}/{resolved_year}/{slug}/"

    for ref in list_branch_refs():
        if read_ref_tree_paths(ref.name, prefix):
            return f"topic '{slug}' of {resolved_year} is already hosted by branch '{ref.name}'"

    return None


def _create_topic(  # noqa: PLR0913, PLR0917 — the unwrapped mirror of the declared signature
    branch_name: str,
    base_ref: str,
    todo: str | None,
    publish: bool,
    commit_message: str | None,
    year: str | None,
    switch: bool,
) -> str:
    """Run the traced creation procedure — the unwrapped orchestration.

    Args:
        branch_name: Branch name as entered by the user.
        base_ref: Base revision the branch starts from.
        todo: The todo as entered, or ``None``/empty for no value.
        publish: ``True`` takes the publication path without the ask.
        commit_message: Commit message template of the publication;
            ``None`` applies the publication's own default.
        year: Optional year as four digits; ``None`` means the current year.
        switch: ``True`` checks out the fresh branch after the creation.

    Returns:
        The single result line of the outcome.
    """
    resolved_year = year or current_year()

    # The preflight — read-only and before any input: a failing base or a
    # conflicted name must never waste an entered todo.
    slug = normalize_topic_slug(branch_name)
    if slug == "":
        raise click.ClickException(f"branch name '{branch_name}' normalizes to an empty topic slug")

    current = resolve_current_branch_name()
    if current is not None and normalize_topic_slug(current) == slug:
        raise click.ClickException(
            f"branch {current} already hosts topic {resolved_year}/{slug} — switch to it instead of re-creating it"
        )

    conflict = check_branch_occupancy(branch_name, slug, year)
    if conflict is None:
        conflict = check_slug_occupancy(slug, year)
    if conflict is not None:
        raise click.ClickException(f"{conflict} — {_BOARD_HINT}")

    base_commit = resolve_ref_commit(base_ref)

    resolved_todo = _resolve_todo(todo)

    if publish and resolved_todo is None:
        raise click.ClickException("the publication needs a todo — the board reads the topic through todo.md")

    if not publish and not switch and resolved_todo is None:
        # Git keeps no empty directories: without a committed todo.md the
        # no-switch work exists in no tree — the board and the slug oracle
        # cannot see it. The publication enforces the same for its own
        # path.
        raise click.ClickException(
            "the local creation needs a todo — the board reads the topic through todo.md; "
            "pass --todo/-t or --switch/-s to create on the spot without one"
        )

    if not _publication_asked(publish, resolved_todo):
        if not switch:
            # The no-switch plant goes through the same quarantined
            # mechanics as the publication — the call-time import breaks
            # the creation ↔ publishing import cycle exactly like the
            # publication delegation below; the built-in message applies,
            # ``commit_message`` stays publication-only.
            from .publishing import _plant_topic_branch  # noqa: PLC0415 — breaks the creation ↔ publishing import cycle

            _plant_topic_branch(branch_name, resolved_todo, base_commit, slug, resolved_year, None)
            return f"Created branch {branch_name} and topic {resolved_year}/{slug}"

        _enter_fresh_branch(branch_name, base_commit, resolved_todo, year, resolved_year)
        return f"Created branch {branch_name} and topic {resolved_year}/{slug}"

    # The publication delegates to the fast cycle through a call-time
    # import: publishing imports this module's occupancy oracles, so a
    # module-level import would be circular and crash the facade load in
    # either order. The cycle re-runs its own preflight — the delegation
    # is deliberately whole, no partial pre-sharing of results.
    from .publishing import publish_topic  # noqa: PLC0415 — breaks the creation ↔ publishing import cycle

    return publish_topic(branch_name, resolved_todo, base_ref, commit_message, year)


def _enter_fresh_branch(
    branch_name: str,
    base_commit: str,
    resolved_todo: str | None,
    year: str | None,
    resolved_year: str,
) -> None:
    """Plant the branch at the base commit and switch to it — the traced
    switch path of the creation, with the topic directory and the todo
    written into the working copy.

    Args:
        branch_name: Branch name as entered by the user.
        base_commit: The base commit hash the preflight resolved.
        resolved_todo: The resolved todo text, or ``None`` for no todo.
        year: The year argument as passed — ``None`` means the current
            year for the directory creation.
        resolved_year: Year as four digits — the directory and the todo
            file segment.
    """
    create_branch_at_commit(branch_name, base_commit)
    try:
        checkout_local_branch(branch_name)
    except (subprocess.CalledProcessError, OSError):
        # A failed checkout would strand the planted branch: the
        # occupancy oracle blocks the retry ("already exists") and the
        # deletion flow cannot remove it (a bare branch hosts no
        # topic), so only a raw ``git branch -D`` recovers. Roll the
        # plant back — the ``publish_topic`` precedent; a failure of
        # the rollback itself is suppressed so the checkout reason
        # surfaces.
        with contextlib.suppress(subprocess.CalledProcessError, OSError):
            delete_local_branch(branch_name)
        raise

    ensure_topic_dir(branch_name, year)
    if resolved_todo is not None:
        _write_todo(branch_name, resolved_year, resolved_todo)


def _resolve_todo(todo: str | None) -> str | None:
    """Resolve the todo of the fresh work — the value, the editor, or an
    error.

    A non-empty value wins; without one an interactive terminal opens the
    editor session (its cancellation leaves no todo), and a
    non-interactive terminal is a clean error naming the value option.

    Args:
        todo: The todo as entered, or ``None``/empty for no value.

    Returns:
        The resolved todo text, or ``None`` when no todo accompanies the
        work.

    Raises:
        click.ClickException: no value and no interactive terminal.
    """
    if todo:
        return todo
    if not sys.stdin.isatty():
        raise click.ClickException(
            "the todo needs a value — pass --todo/-t or run the creation on an interactive terminal"
        )

    return edit_text()


def _publication_asked(publish: bool, todo: str | None) -> bool:
    """Decide between the normal path and the publication — the ask.

    The ask runs only on an interactive terminal, without ``publish``,
    and with a resolved todo: an empty answer reads the default no and
    Ctrl-C or EOF aborts. Without the ask ``publish`` decides directly.

    Args:
        publish: ``True`` takes the publication path without the ask.
        todo: The resolved todo, or ``None``.

    Returns:
        ``True`` when the work goes to the publication path.
    """
    if not publish and todo is not None and sys.stdin.isatty():
        return click.confirm("Publish the branch to origin?")

    return publish


def _enter_topic_todo(topic: str, year: str | None) -> bool:
    """Run the traced todo-entry procedure — the unwrapped orchestration.

    Args:
        topic: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` means the current year.

    Returns:
        True when the saved text was written; False when the entry was
        cancelled.
    """
    resolved_year = year or current_year()

    path = resolve_topic_file(topic, "todo.md", resolved_year)
    # The read is display data — the editor prefill — so a byte outside
    # UTF-8 (a hand edit saved in another encoding) decodes with the
    # replacement character: a ``UnicodeDecodeError`` is a ``ValueError``,
    # it matches none of the module's handlers and would pierce the
    # clean-error boundary — mirroring ``_run_git`` of the git cell.
    initial = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None

    saved = edit_text(initial)

    if saved is None:
        return False

    _write_todo(topic, resolved_year, saved)
    return True


def _write_todo(name: str, year: str, todo: str) -> None:
    """Write the topic todo file of a topic directory.

    The file carries the todo as entered plus a single trailing newline,
    encoded UTF-8 — created when absent, overwritten when present; a text
    that already ends in a newline keeps exactly that one. The topic
    directory must already exist; only directories are created here.

    Args:
        name: Topic input — a branch name or an already-normalized slug.
        year: Year as four digits.
        todo: Multi-line todo text as entered — a fresh-work value or the
            editor session's saved text.
    """
    content = todo if todo.endswith("\n") else f"{todo}\n"
    resolve_topic_file(name, "todo.md", year).write_text(content, encoding="utf-8")
