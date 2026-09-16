"""The topics domain hooks zone — the lifecycle checkpoint surface.

Owner of the event identity, the notification contexts, the amendment
drafts, and the checkpoint surface over the hooks platform. Importing the
package imports no tool package and enumerates nothing.
"""

from .identity import TopicIdentity

__all__: list[str] = ["TopicIdentity"]
