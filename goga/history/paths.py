"""Topic addressing for the history domain.

The routines declared in the cell CODEMANIFEST with ``location: paths.py``:
the public history-root composer (the private helper delegates to it), the
two pure path composers (topic directory and artifact file), the read-only
occupancy oracle, the idempotent directory creator, and the idempotent
directory remover. Composers never touch the filesystem — creation belongs
to ``ensure_topic_dir`` alone, deletion to ``remove_topic_dir`` alone.
"""

from __future__ import annotations

import shutil
from pathlib import Path, PurePath

from .naming import current_year, normalize_topic_slug


def resolve_history_root() -> Path:
    """Return the root path of the history tree.

    The single source of the tree location for every consumer reading the
    topic tree of a git ref — the path is composed at the caller's working
    directory and nothing is created or checked.

    Returns:
        The history tree path ``.goga/history/`` — relative to the caller's
        working directory, not created.
    """
    return Path(".goga") / "history"


def _history_root() -> Path:
    """Return the history tree root — delegated to the public composer."""
    return resolve_history_root()


def resolve_topic_dir(topic: str, year: str | None = None) -> Path:
    """Compute the directory path of a history topic.

    The topic input is normalized via the slug grammar — a branch name and an
    already-normalized slug compose identically. A falsy year (``None`` or the
    empty string an empty CLI value produces) means "not set" and falls back
    to the current year; without that rule an empty string would degrade the
    composed path to the year's parent directory.

    Args:
        topic: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` and the empty string mean the current year.

    Returns:
        The topic directory path ``.goga/history/<year>/<slug>/`` — relative
        to the caller's working directory, not created.

    Raises:
        ValueError: The topic input normalizes to an empty slug — no fallback
            name or year is returned; the error is the result.
    """
    slug = normalize_topic_slug(topic)
    if slug == "":
        raise ValueError(f"topic input {topic!r} normalizes to an empty topic slug")
    resolved_year = year or current_year()
    return _history_root() / resolved_year / slug


def resolve_topic_file(topic: str, filename: str, year: str | None = None) -> Path:
    """Compute the path of an artifact file inside a history topic.

    The filename is taken verbatim — no normalization, no case change — and
    must carry an extension: a dot separating a non-empty stem from a
    non-empty suffix. A leading dot alone (a dotfile name such as ``.md``) is
    a hidden-file marker, not an extension separator, and a trailing dot
    alone (``plan.``) is an empty extension — both are rejected explicitly,
    because ``PurePath.suffix`` reports a lone trailing dot as the suffix
    ``"."`` starting from Python 3.14.

    Args:
        topic: Topic input — a branch name or an already-normalized slug.
        filename: Artifact filename — arbitrary, must carry an extension.
        year: Optional year as four digits; ``None`` and the empty string mean the current year.

    Returns:
        The artifact file path ``.goga/history/<year>/<slug>/<filename>`` —
        neither created nor checked for existence.

    Raises:
        ValueError: The filename carries no extension, or the topic input
            normalizes to an empty slug (the directory composer's error).
    """
    if PurePath(filename).suffix in ("", "."):
        raise ValueError(f"filename {filename!r} must carry an extension")
    return resolve_topic_dir(topic, year) / filename


def topic_exists(topic: str, year: str | None = None) -> bool:
    """Decide whether a history topic already exists for the year.

    True only when the composed topic path exists as a directory — a stray
    file named like the slug does not occupy a topic, and a missing history
    root is simply "no", not an error.

    Args:
        topic: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` and the empty string mean the current year.

    Returns:
        True when the topic directory exists, otherwise False.
    """
    return resolve_topic_dir(topic, year).is_dir()


def ensure_topic_dir(name: str, year: str | None = None) -> Path:
    """Create the directory of a history topic of a year.

    Idempotent: an existing topic directory is a success, not a conflict —
    deciding whether a topic may be created belongs to the caller.
    Directories only: no artifact file inside the tree is created or touched.

    Args:
        name: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` and the empty string mean the current year.

    Returns:
        The topic directory path that now exists.

    Raises:
        ValueError: The name normalizes to an empty slug.
        OSError: Propagated from ``mkdir`` — unexpected OS failures are not
            swallowed.
    """
    topic_dir = resolve_topic_dir(name, year)
    topic_dir.mkdir(parents=True, exist_ok=True)
    return topic_dir


def remove_topic_dir(name: str, year: str | None = None) -> bool:
    """Delete the directory of a history topic of a year.

    The whole topic directory goes — every artifact including nested
    directories such as ``completed/`` — and nothing else: sibling topic
    directories and the year directory itself stay untouched. Deciding
    whether a topic deserves deletion belongs to the caller; this routine
    only executes the decision. A pure filesystem mutation — no git branch,
    ref, or index is touched. A stray file named like the slug does not
    occupy a topic (the ``topic_exists`` semantics), so it yields False
    and stays in place.

    Args:
        name: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` and the empty string mean the current year.

    Returns:
        True when the topic directory existed and was deleted, False when
        it was absent.

    Raises:
        ValueError: The name normalizes to an empty slug (the directory
            composer's error).
        OSError: Propagated from ``rmtree`` — unexpected OS failures are
            not swallowed.
    """
    topic_dir = resolve_topic_dir(name, year)
    if not topic_dir.is_dir():
        return False
    shutil.rmtree(topic_dir)
    return True
