"""Hooks zone of the drift domain — the run moments, the report amendment, the entry-facts
amendment, and the checkpoint surface over the hooks platform.

The zone was built incrementally — each entity task of the extension added
its module and its names to the facade; this is the assembled state of all
five modules.
"""

from .amendments import EntryAmendment, ReportAmendment
from .events import DriftHooks
from .facts import DriftFilters, EntryFacts, ReportEntry, RunCompletion, RunOutcome
from .overlay import ToolContribution, merge_entry_contributions

__all__: list[str] = [
    "DriftFilters",
    "DriftHooks",
    "EntryAmendment",
    "EntryFacts",
    "ReportAmendment",
    "ReportEntry",
    "RunCompletion",
    "RunOutcome",
    "ToolContribution",
    "merge_entry_contributions",
]
