"""The topics domain hooks zone — the lifecycle checkpoint surface.

Owner of the event identity, the notification contexts, the amendment
drafts, and the checkpoint surface over the hooks platform. Importing the
package imports no tool package and enumerates nothing.
"""

from .amendments import (
    CreationAmendment,
    CreationDraft,
    TodoEntryAmendment,
    TodoEntryDraft,
)
from .contexts import (
    TopicCreated,
    TopicDeleted,
    TopicPublished,
    TopicSwitched,
    TopicTodoEntered,
)
from .events import TopicHooks
from .identity import TopicIdentity

__all__: list[str] = [
    "CreationAmendment",
    "CreationDraft",
    "TodoEntryAmendment",
    "TodoEntryDraft",
    "TopicCreated",
    "TopicDeleted",
    "TopicHooks",
    "TopicIdentity",
    "TopicPublished",
    "TopicSwitched",
    "TopicTodoEntered",
]
