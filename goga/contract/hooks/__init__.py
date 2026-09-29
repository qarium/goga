"""Hooks zone of the contract domain — the amendment checkpoint surface.

The zone owns the per-cell comparison read view (``CellFacts`` with its
``TypeFacts`` / ``FormFacts`` / ``MemberFacts`` records), the per-tool
contribution model (``ContractAmendment`` buffering a tool's contributions,
``ToolContribution`` / ``merge_type_contributions`` composing them), and the
``ContractHooks`` checkpoint surface delivering the hard
``contract/amend_contract`` action over the platform facade. The eight
contract names of the zone are re-exported below.
"""

from .amendments import ContractAmendment
from .events import ContractHooks
from .facts import CellFacts, FormFacts, MemberFacts, TypeFacts
from .overlay import ToolContribution, merge_type_contributions

__all__: list[str] = [
    "CellFacts",
    "ContractAmendment",
    "ContractHooks",
    "FormFacts",
    "MemberFacts",
    "ToolContribution",
    "TypeFacts",
    "merge_type_contributions",
]
