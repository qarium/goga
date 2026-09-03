"""Contract and logic tests for the routines declared in
``goga/history/CODEMANIFEST`` with ``location: naming.py``:

- ``normalize_topic_slug(name: str) -> str`` — the pure slug transformer
- ``current_year() -> str`` — the single current-year point of the domain

Both routines are pure; the only mock target is ``naming.datetime`` (the
mandated bare-``now()`` point), patched at the import site.
"""

from __future__ import annotations

import inspect
import typing
from datetime import datetime
from unittest import mock

import pytest
from goga.history import naming
from goga.history.naming import current_year, normalize_topic_slug


class _FixedClock:
    """Stand-in for ``datetime`` answering a fixed naive date."""

    @staticmethod
    def now() -> datetime:
        return datetime(2031, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock


# --- Contract tests ---


class TestNamingContract:
    def test_routines_are_importable_from_module_and_callable(self) -> None:
        """Both routines are importable from ``goga.history.naming`` and callable."""
        assert callable(normalize_topic_slug)
        assert callable(current_year)
        assert naming.normalize_topic_slug is normalize_topic_slug
        assert naming.current_year is current_year

    def test_facade_reexports_the_naming_names(self) -> None:
        """The naming routines are importable from the domain facade."""
        import goga.history

        assert goga.history.normalize_topic_slug is normalize_topic_slug
        assert goga.history.current_year is current_year
        assert "current_year" in goga.history.__all__
        assert "normalize_topic_slug" in goga.history.__all__

    def test_normalize_topic_slug_signature(self) -> None:
        """``normalize_topic_slug(name: str) -> str`` — one positional-or-keyword parameter."""
        signature = inspect.signature(normalize_topic_slug)
        assert list(signature.parameters) == ["name"]
        assert all(
            parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for parameter in signature.parameters.values()
        )
        hints = typing.get_type_hints(normalize_topic_slug)
        assert hints == {"name": str, "return": str}

    def test_current_year_signature(self) -> None:
        """``current_year() -> str`` — no parameters."""
        signature = inspect.signature(current_year)
        assert list(signature.parameters) == []
        hints = typing.get_type_hints(current_year)
        assert hints == {"return": str}


# --- Logic tests ---


class TestNormalizeTopicSlug:
    @pytest.mark.parametrize(
        ("name", "slug"),
        [
            ("Feature/Foo_Bar", "feature-foo-bar"),
            ("release/1.3.0", "release-1-3-0"),
            ("Релиз/Один", ""),
            ("aБb", "ab"),
            ("-a--b-", "a-b"),
            ("My Tool", "my-tool"),
            ("feat///x", "feat-x"),
            ("UPPER", "upper"),
            ("123", "123"),
            ("release-1-3-0", "release-1-3-0"),
        ],
    )
    def test_normalize_topic_slug_parametrized(self, name: str, slug: str) -> None:
        """The slug grammar: lowercase → ASCII filter → hyphenate → collapse → trim.

        The last pair is idempotence — an already-normalized slug maps to
        itself.
        """
        assert normalize_topic_slug(name) == slug

    def test_normalize_topic_slug_fully_non_ascii_empty(self) -> None:
        """A fully non-ASCII name yields the empty slug — deterministically."""
        assert normalize_topic_slug("Релиз/Один") == ""
        assert normalize_topic_slug("Релиз/Один") == normalize_topic_slug("Релиз/Один")


class TestCurrentYear:
    def test_current_year_returns_four_digits(self) -> None:
        """The pinned clock answers the zero-padded 4-digit year, no parameters."""
        with mock.patch.object(naming, "datetime", _FixedClock):
            year = current_year()
        assert year == "2031"
        assert len(year) == 4
        assert list(inspect.signature(current_year).parameters) == []

    def test_current_year_has_no_override_and_is_uncached(self) -> None:
        """Each call asks the clock anew — two pinned calls, two answers."""

        class _SteppingClock:
            calls = 0

            @classmethod
            def now(cls) -> datetime:
                cls.calls += 1
                return datetime(2031 + cls.calls, 6, 15)  # noqa: DTZ001 — a fixed naive date is the point of the clock

        with mock.patch.object(naming, "datetime", _SteppingClock):
            assert current_year() == "2032"
            assert current_year() == "2033"
