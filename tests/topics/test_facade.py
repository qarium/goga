"""Facade tests of the topics domain — the assembled exchange surface.

``goga/topics/__init__.py`` re-exports exactly the twenty-nine contract
names of the cell: the seventeen pre-existing board/creation/deletion/
ensuring/publishing/switching names plus the ten exchange names — the
two exchange fact bags and the base/addressee resolution of
``exchange``, the template engine it contributes, the update operation
of ``updating``, the propagation plan and its two halves of
``propagating``, and the board divergence marker of ``board`` — plus
the two delivery names of ``publishing``: the ``publish_existing_topic``
operation and its ``resolve_publication_outcome`` classifier. This
suite pins the facade rule: the alphabetical ``__all__`` list of
twenty-nine names and each exchange name resolving to the implementing
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
    """All ten exchange names live on the twenty-nine-name facade.

    Every name imports from the package root, resolves to the
    implementing entity of its declaring module, and appears in the
    alphabetical ``__all__`` list — the CLI's import path follows the
    facade-only rule. The two delivery names of ``publishing`` count
    toward the same pin — the re-export grew by exactly them.
    """
    assert domain.resolve_divergence is resolve_divergence_of_board
    assert domain.resolve_exchange_base is resolve_exchange_base_of_exchange
    assert domain.resolve_propagation is resolve_propagation_of_propagating
    assert domain.update_topic is update_topic_of_updating

    for name, entity in _EXCHANGE_IMPLEMENTING.items():
        exported = getattr(domain, name)

        assert exported is entity
        assert name in domain.__all__

    assert len(domain.__all__) == 29
    assert domain.__all__ == sorted(domain.__all__)


def test_topics_facade_reexports_publish_routines() -> None:
    """The publication surface imports from every facade that owes it.

    ``publish_existing_topic`` and ``resolve_publication_outcome``
    resolve from the ``goga.topics`` package root and sit in its
    ``__all__``; the git zone re-exports ``resolve_commit_message`` and
    the config facade re-exports ``load_tool_config`` — the three
    package roots the CLI and the tool dispatcher import from, never
    the declaring modules.
    """
    import goga.config
    import goga.topics.git
    from goga.config import load_tool_config
    from goga.topics import publish_existing_topic, resolve_publication_outcome
    from goga.topics.git import resolve_commit_message

    for routine in (publish_existing_topic, resolve_publication_outcome):
        assert callable(routine)
    assert domain.publish_existing_topic is publish_existing_topic
    assert domain.resolve_publication_outcome is resolve_publication_outcome
    assert "publish_existing_topic" in domain.__all__
    assert "resolve_publication_outcome" in domain.__all__

    assert callable(resolve_commit_message)
    assert goga.topics.git.resolve_commit_message is resolve_commit_message
    assert "resolve_commit_message" in goga.topics.git.__all__

    assert callable(load_tool_config)
    assert goga.config.load_tool_config is load_tool_config
    assert "load_tool_config" in goga.config.__all__
