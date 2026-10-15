"""Hooks zone of the drift domain — the run moments, the report amendment, the entry-facts
amendment, and the checkpoint surface over the hooks platform.

The zone is built incrementally — each entity task of the extension adds its
module and its names to the facade.
"""

from .amendments import EntryAmendment, ReportAmendment
from .facts import DriftFilters, EntryFacts, ReportEntry, RunCompletion, RunOutcome
from .overlay import ToolContribution, merge_entry_contributions

__all__: list[str] = [
    "DriftFilters",
    "EntryAmendment",
    "EntryFacts",
    "ReportAmendment",
    "ReportEntry",
    "RunCompletion",
    "RunOutcome",
    "ToolContribution",
    "merge_entry_contributions",
]
