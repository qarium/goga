"""Hooks zone of the schema domain — the cell-amendment checkpoint surface.

The zone will own the per-cell authored-facts read view (``CellFacts`` /
``DependencyFacts``), the per-tool read-and-contribute view
(``CellAmendment``), the deterministic tools-area composition
(``ToolContribution`` / ``merge_cell_contributions``), and the
``SchemaHooks`` checkpoint surface delivering the hard ``schema/amend_cell``
action over the platform facade.

Built incrementally: each entity task adds its module. The six contract
names of the zone are re-exported here as they land.
"""

__all__: list[str] = []
