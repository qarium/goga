"""Status scale cell — the owner of the topic status scale.

The built-in artifact axis, the registration of tool statuses over installed
``goga_tool_*`` packages, and the computation of a topic's maximal present
statuses. Pure scale logic — no filesystem probing of topic directories, no
git access, no CLI, no output rendering.
"""

from .assembly import assemble_status_scale
from .registry import StatusRegistry
from .scale import Stage, StatusScale

__all__: list[str] = [
    "Stage",
    "StatusRegistry",
    "StatusScale",
    "assemble_status_scale",
]
