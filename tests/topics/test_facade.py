"""Facade tests of the topics domain — the assembled exchange surface.

``goga/topics/__init__.py`` re-exports exactly the twenty-seven contract
names of the cell: the seventeen pre-existing board/creation/deletion/
ensuring/publishing/switching names plus the ten exchange names — the
two exchange fact bags and the base/addressee resolution of
``exchange``, the template engine it contributes, the update operation
of ``updating``, the propagation plan and its two halves of
``propagating``, and the board divergence marker of ``board``. This
suite pins the facade rule: the alphabetical ``__all__`` list of
twenty-seven names and each exchange name resolving to the implementing
entity of its declaring module — the CLI imports the operations from
the package root, never from the declaring modules.
"""

from __future__ import annotations

import goga.topics as domain
from goga.topics import (
    ExchangeBase,
    ExchangeTarget,
    PropagationPlan,
    execute_propagation,
    render_commit_template,
    resolve_divergence,
    resolve_exchange_base,
    resolve_exchange_target,
    resolve_propagation,
    update_topic,
)
from goga.topics.board import resolve_divergence as resolve_divergence_of_board
from goga.topics.exchange import resolve_exchange_base as resolve_exchange_base_of_exchange
from goga.topics.propagating import resolve_propagation as resolve_propagation_of_propagating
from goga.topics.updating import update_topic as update_topic_of_updating

_EXCHANGE_IMPLEMENTING = {
    "ExchangeBase": ExchangeBase,
    "ExchangeTarget": ExchangeTarget,
    "PropagationPlan": PropagationPlan,
    "execute_propagation": execute_propagation,
    "render_commit_template": render_commit_template,
    "resolve_divergence": resolve_divergence,
    "resolve_exchange_base": resolve_exchange_base,
    "resolve_exchange_target": resolve_exchange_target,
    "resolve_propagation": resolve_propagation,
    "update_topic": update_topic,
}
"""The ten exchange names mapped to the names imported from the facade."""


def test_topics_facade_exports_operations() -> None:
    """All ten exchange names live on the twenty-seven-name facade.

    Every name imports from the package root, resolves to the
    implementing entity of its declaring module, and appears in the
    alphabetical ``__all__`` list — the CLI's import path follows the
    facade-only rule.
    """
    assert domain.resolve_divergence is resolve_divergence_of_board
    assert domain.resolve_exchange_base is resolve_exchange_base_of_exchange
    assert domain.resolve_propagation is resolve_propagation_of_propagating
    assert domain.update_topic is update_topic_of_updating

    for name, entity in _EXCHANGE_IMPLEMENTING.items():
        exported = getattr(domain, name)

        assert exported is entity
        assert name in domain.__all__

    assert len(domain.__all__) == 27
    assert domain.__all__ == sorted(domain.__all__)
