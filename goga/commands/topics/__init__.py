"""Topics command cell — the CLI surface of the topics domain.

A thin wrapper: the ``topics`` group resolves the inputs and delegates
every computation to the domain routines of ``goga.topics`` — the board
rendered in its two views (the aggregated default table and the
``--per-host`` audit rows) and its ``--json`` machine-readable form, the
creation with the optional-value ``--todo`` option mapped into the
domain's source declaration (a value is the todo, the value-less form
declares the piped stdin, absent or empty declares nothing), and the
switching, deletion, and clear procedures. No inventory walking, no switch
resolution, no editor or stdin read, and no git access live here; domain
errors surface as clean CLI errors.
"""

from .render import render_board_json, render_topic_board, render_topic_host_rows
from .topics import topics

__all__: list[str] = ["render_board_json", "render_topic_board", "render_topic_host_rows", "topics"]
