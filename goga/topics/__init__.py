"""Topics domain cell — the work-tracker view of the history tree.

The cross-branch topic inventory of one year with per-topic statuses, the
switch-identifier resolution and switching orchestration, and the
fresh-work creation procedure. Topic identity, addressing, and statuses
belong to the history facade; git access belongs to the nested leaf cell
``goga.topics.git``. Mutations are local-only and happen strictly after
every decision is made.
"""

__all__: list[str] = []
