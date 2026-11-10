"""Shared fixtures of the drift hooks zone tests — the platform boundary.

Re-exports the two boundary fixtures of the hooks platform tests
(``pin_package_environment`` / ``install_tool_package``) so the zone suites pin
the same two outside-world points — the ``packages_distributions`` read and the
``sys.modules`` entry of a ``goga_tool_*`` package — with the platform code
under test running for real.
"""

import pytest

from tests.hooks.conftest import install_tool_package, pin_package_environment  # noqa: F401


@pytest.fixture
def report() -> object:
    """A minimal scoped report — the shared read surface of every amending tool."""
    from goga.drift.hooks import EntryFacts

    return [
        EntryFacts(kind="schema_only", cell="goga/config", types=["ProjectConfig"]),
        EntryFacts(kind="codegraph_only", cell="goga/extra", types=None),
    ]


@pytest.fixture
def entry() -> object:
    """A minimal report entry — the shared read surface of every contributing tool."""
    from goga.drift.hooks import EntryFacts

    return EntryFacts(kind="schema_only", cell="goga/config", types=["ProjectConfig"])


@pytest.fixture
def report_view(report: object) -> object:
    """The read-and-adjust view of one tool."""
    from goga.drift.hooks import ReportAmendment

    return ReportAmendment(report=report)


@pytest.fixture
def entry_view(entry: object) -> object:
    """The read-and-contribute view of one tool."""
    from goga.drift.hooks import EntryAmendment

    return EntryAmendment(entry=entry)
