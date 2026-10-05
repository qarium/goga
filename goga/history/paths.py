"""Topic addressing for the history domain."""

from __future__ import annotations

import shutil
from pathlib import Path, PurePath

from .naming import current_year, normalize_topic_slug


def resolve_history_root() -> Path:
    """Return the root path of the history tree.

    Returns:
        The history tree path ``.goga/history/`` — relative to the caller's
        working directory, not created.
    """
    return Path(".goga") / "history"


def _history_root() -> Path:
    """Return the history tree root — delegated to the public composer.

    Returns:
        The history tree path ``.goga/history/``, not created.
    """
    return resolve_history_root()


def resolve_topic_dir(topic: str, year: str | None = None) -> Path:
    """Compute the directory path of a history topic.

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

    Args:
        topic: Topic input — a branch name or an already-normalized slug.
        filename: Artifact filename — arbitrary, taken verbatim (no
            normalization), must carry an extension.
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

    Args:
        topic: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` and the empty string mean the current year.

    Returns:
        True only when the topic path exists as a directory — a stray file
        named like the slug does not occupy a topic; otherwise False.
    """
    return resolve_topic_dir(topic, year).is_dir()


def ensure_topic_dir(name: str, year: str | None = None) -> Path:
    """Create the directory of a history topic of a year — idempotently, directories only.

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
    """Delete the whole directory of a history topic of a year — nothing outside it, filesystem only.

    Args:
        name: Topic input — a branch name or an already-normalized slug.
        year: Optional year as four digits; ``None`` and the empty string mean the current year.

    Returns:
        True when the topic directory existed and was deleted; False when
        absent — a stray file named like the slug does not occupy a topic
        and stays in place.

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
