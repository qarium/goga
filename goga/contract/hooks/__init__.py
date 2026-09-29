"""Hooks zone of the contract domain — the amendment checkpoint surface.

The zone owns the per-cell comparison read view (``CellFacts`` with its
``TypeFacts`` / ``FormFacts`` / ``MemberFacts`` records), the per-tool
contribution model (``ContractAmendment`` buffering a tool's contributions,
``ToolContribution`` / ``merge_type_contributions`` composing them), and the
``ContractHooks`` checkpoint surface delivering the hard
``contract/amend_contract`` action over the platform facade. The eight
contract names of the zone are re-exported by the facade below — the
re-export block is assembled as the zone modules land.
"""
