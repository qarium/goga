"""Event delivery cell — the mediation and the emission of the hooks platform.

The owner of the transparent delivery view of an emitted domain object, the
fixed-name injection of hook arguments, and the emission of an action to its
subscribed hooks under the action's error class. Importing the package
enumerates nothing and builds no registry — the single build of a run happens
on the first emission.
"""

from .delivery import build_hook_arguments, wrap_context
from .emit import emit_hook_event

__all__: list[str] = [
    "build_hook_arguments",
    "emit_hook_event",
    "wrap_context",
]
