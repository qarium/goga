"""Local constants of the topics hooks zone tests — the platform environment.

The zone consumes the hooks platform through its facade, never around it:
the only outside points of a zone test are the two the shared fixtures of
``tests/conftest.py`` already pin — the installed-distributions mapping read
by ``packages_distributions`` and the ``sys.modules`` entry of a
``goga_tool_*`` package. The fixtures themselves are inherited from
``tests/conftest.py`` and the parent ``tests/topics/conftest.py`` (the
registry reset, the recording hooks, and the two-tool environment constant
the checkpoint tests pin); this module declares the zone facade contract
the contract tests of the zone assert against.
"""

from __future__ import annotations

ZONE_ALL: list[str] = [
    "CreationAmendment",
    "CreationDraft",
    "TodoEntryAmendment",
    "TodoEntryDraft",
    "TopicCreated",
    "TopicDeleted",
    "TopicHooks",
    "TopicIdentity",
    "TopicPropagated",
    "TopicPublished",
    "TopicSwitched",
    "TopicTodoEntered",
    "TopicUpdated",
]
"""The final zone facade — the thirteen names, alphabetical."""
