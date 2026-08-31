"""Fixtures of the emission tests — the catalog boundary of a hard action.

The real catalog declares a single address, ``statuses.register_statuses``,
and it is soft. The hard failure treatment needs a hard-class record, so the
fixture below pins ``declared_actions`` in the ``goga.hooks.dispatch.emit``
namespace — the single point the emission resolves addresses against. The
statuses record stays: within a pinned test the soft behavior keeps working
beside the hard one.
"""

from __future__ import annotations

import pytest
from goga.hooks.catalog import Action

_HARD_CATALOG: list[Action] = [
    Action(domain="d", name="act", error_class="hard"),
    Action(domain="statuses", name="register_statuses", error_class="soft"),
]
"""The pinned catalog — the real one plus the hard-class address ``d.act``."""


@pytest.fixture
def hard_action_catalog(monkeypatch: pytest.MonkeyPatch) -> list[Action]:
    """Pin the emission's catalog with one hard-class address ``d.act``.

    While pinned, the emission resolves ``("d", "act")`` as a hard action —
    the first failing hook stops the sequence with a clean error — and keeps
    resolving the statuses address as soft.

    Args:
        monkeypatch: the pytest patcher restoring the real catalog on teardown.

    Returns:
        The records the pinned emission resolves addresses against.
    """
    from goga.hooks.dispatch import emit

    def pinned() -> list[Action]:
        """The pinned catalog — a fresh list, as the real routine returns."""
        return list(_HARD_CATALOG)

    monkeypatch.setattr(emit, "declared_actions", pinned)

    return pinned()
