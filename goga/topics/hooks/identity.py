"""The identity vocabulary of the topics lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass

from ...history import resolve_topic_dir


@dataclass(frozen=True, kw_only=True)
class TopicIdentity:
    """The identity vocabulary of every topics event — slug, home path, branch.

    Attributes:
        slug: The normalized topic slug, or None in the branch-only form —
            a switch onto a branch hosting no topic.
        year: The resolved year as four digits — the composition input of
            the home path; it always arrives resolved — the constructing
            operation passes its year input when given, otherwise the
            current year.
        branch: The branch name as entered by the operation, or None only
            in the deletion context, whose removal composition carries the
            branch names.

    Requirements:
        Pure composition — the home path derives from ``slug`` and ``year``
        without repository reads and without creating anything.
    """

    slug: str | None
    year: str
    branch: str | None

    @property
    def home_path(self) -> str | None:
        """Return the topic home path as a posix string — None without a slug.

        Returns:
            The topic home path ``.goga/history/<year>/<slug>`` as a posix
            string, composed through ``resolve_topic_dir`` — the slug
            re-normalized, nothing read or created — or None when the
            slug is None.
        """
        if self.slug is None:
            return None

        return resolve_topic_dir(self.slug, self.year).as_posix()
