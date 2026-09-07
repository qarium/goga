"""Topics command cell — the CLI surface of the topics domain.

A thin wrapper: the ``topics`` group resolves the inputs and delegates
every computation to the domain routines of ``goga.topics``, and the board
renderer shapes the collected records into the three-column table. No
inventory walking, no switch resolution, and no git access live here;
domain errors surface as clean CLI errors.
"""

from .render import render_topic_board
from .topics import topics

__all__: list[str] = ["render_topic_board", "topics"]
